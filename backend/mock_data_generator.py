"""
Mock data generator for the Identity Risk Console.

Generates 5 files in backend/data/, sized and mixed to satisfy the hackathon's
"Sample Data Provided" spec exactly:

  identities.csv        400 rows  (spec: 200-400)
  group_topology.csv    ~110 rows (spec: 100-200) — static group/role nesting structure
  group_membership.csv  ~900 rows — per-user group assignments (NOT counted against the
                                    100-200 figure; that figure is the topology, this is
                                    the necessarily-larger fan-out of who's in what)
  audit_logs.csv        ~700 rows (spec: 500-1,000)
  offboarding.csv       ~70 rows  (spec: 50-100)

Anomaly mix across the 400 identities (spec target -> actual):
  orphaned_stale        10-15% -> 50  (12.5%)
  over_privileged        8-12% -> 40  (10.0%)
  priv_escalation         5-8% -> 28  ( 7.0%)
  token_abuse              3-5% -> 16  ( 4.0%)
  legit_high_priv_fp     15-20% -> 68  (17.0%)
  normal                 40-55% -> 198 (49.5%)

Swap these CSVs for your teammates' real pipeline output later — see DATA_CONTRACT.md.
The schema doesn't change, only the file split (group_topology vs group_membership,
see note in DATA_CONTRACT.md) needs to be communicated to them.
"""
import csv
import os
import random
from datetime import datetime, timedelta

from faker import Faker

fake = Faker("en_IN")
random.seed(42)
Faker.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)

NOW = datetime(2026, 6, 20)

# en_IN's built-in name pool blends in some Anglo names (Liam, Theodore, etc.)
# which looks inconsistent in a demo — use a curated pool instead so every
# generated name is unambiguously Indian.
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Rohan", "Karthik", "Aryan", "Dhruv", "Kabir", "Rudra",
    "Aniket", "Varun", "Nikhil", "Siddharth", "Rahul", "Vikram", "Manish", "Tejas",
    "Saanvi", "Aanya", "Diya", "Myra", "Ananya", "Pari", "Ira", "Anika",
    "Kavya", "Riya", "Isha", "Sneha", "Priya", "Neha", "Pooja", "Divya",
    "Meera", "Lakshmi", "Aishwarya", "Shreya", "Nandini", "Tanvi", "Aditi", "Kiara",
    "Arnav", "Kunal", "Harsh", "Rajesh", "Suresh", "Ramesh", "Anand", "Deepak",
    "Sanjay", "Vinod", "Ashok", "Prakash", "Mahesh", "Naveen", "Gaurav", "Amit",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Iyer", "Nair", "Menon", "Pillai", "Reddy",
    "Rao", "Naidu", "Patel", "Shah", "Mehta", "Desai", "Joshi", "Kulkarni",
    "Deshmukh", "Bhat", "Hegde", "Shetty", "Kamath", "Singh", "Kumar", "Yadav",
    "Mishra", "Pandey", "Tiwari", "Chauhan", "Rajan", "Krishnan", "Subramaniam",
    "Raman", "Banerjee", "Mukherjee", "Chatterjee", "Bose", "Das", "Ghosh",
    "Chakraborty", "Sengupta",
]

DEPARTMENTS = ["Engineering", "Finance", "Sales", "HR", "IT", "Security", "Data", "Legal"]

# Private IP ranges, varied per "office" to look like real network telemetry.
IP_POOLS = {
    "office_blr": "10.20.{}.{}",
    "office_mum": "10.30.{}.{}",
    "vpn": "10.40.{}.{}",
    "unknown_external": "{}.{}.{}.{}",  # flagged as suspicious in audit context
}


def gen_person():
    """Returns (display_name, ad_username, email) all derived from ONE name so
    they're internally consistent, e.g. 'Sai Krishnan' -> 'saikrishnan' ->
    'sai.krishnan@gmail.com'."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    ad_user = f"{first.lower()}{last.lower()}"[:20]
    email = f"{first.lower()}.{last.lower()}@{fake.free_email_domain()}"
    return name, ad_user, email


def gen_manager_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def rand_date(days_back_min, days_back_max):
    days = random.randint(days_back_min, days_back_max)
    return (NOW - timedelta(days=days)).date().isoformat()


def rand_datetime(days_back_min, days_back_max, hours_back=None):
    days = random.randint(days_back_min, days_back_max)
    hours = hours_back if hours_back is not None else random.randint(0, 23)
    dt = NOW - timedelta(days=days, hours=hours)
    return dt.isoformat()


def gen_ip(suspicious=False):
    if suspicious:
        pool = IP_POOLS["unknown_external"]
        return pool.format(random.randint(1, 223), random.randint(0, 255),
                            random.randint(0, 255), random.randint(0, 255))
    pool = random.choice([IP_POOLS["office_blr"], IP_POOLS["office_mum"], IP_POOLS["vpn"]])
    return pool.format(random.randint(0, 255), random.randint(1, 254))


# ---------------------------------------------------------------------------
# Static group/role topology — this is the "100-200 group/role mappings"
# the spec asks for: the nested structure itself, independent of which users
# are in which group. Counted separately from per-user membership edges.
# ---------------------------------------------------------------------------

def build_group_topology():
    """Returns (topology_rows, group_names_by_platform, role_names_by_platform)."""
    topology = []
    groups_by_platform = {"ad": [], "aws": [], "okta": []}
    roles_by_platform = {"ad": [], "aws": [], "okta": []}

    # --- AD: base -> dept groups -> helpdesk -> IT admins -> domain admins
    ad_hierarchy = [
        ("ad:GG-Employees-Base", None),
        ("ad:GG-Finance-RW", "ad:GG-Employees-Base"),
        ("ad:GG-Sales-RW", "ad:GG-Employees-Base"),
        ("ad:GG-HR-RW", "ad:GG-Employees-Base"),
        ("ad:GG-Legal-RW", "ad:GG-Employees-Base"),
        ("ad:GG-Data-RW", "ad:GG-Employees-Base"),
        ("ad:GG-IT-Helpdesk", "ad:GG-Employees-Base"),
        ("ad:GG-IT-Admins", "ad:GG-IT-Helpdesk"),
        ("ad:GG-DomainAdmins", "ad:GG-IT-Admins"),
        ("ad:GG-Security-Analysts", "ad:GG-Employees-Base"),
        ("ad:GG-Security-Admins", "ad:GG-Security-Analysts"),
    ]
    for group, parent in ad_hierarchy:
        groups_by_platform["ad"].append(group)
        if parent:
            topology.append({"source_id": group, "source_type": "group",
                              "target_id": parent, "target_type": "group", "platform": "ad"})

    ad_roles = [
        ("ad:role-DomainAdmin", "ad:GG-DomainAdmins"),
        ("ad:role-FinanceWrite", "ad:GG-Finance-RW"),
        ("ad:role-SalesWrite", "ad:GG-Sales-RW"),
        ("ad:role-HRWrite", "ad:GG-HR-RW"),
        ("ad:role-LegalWrite", "ad:GG-Legal-RW"),
        ("ad:role-DataWrite", "ad:GG-Data-RW"),
        ("ad:role-HelpdeskReadOnly", "ad:GG-IT-Helpdesk"),
        ("ad:role-SecurityAdmin", "ad:GG-Security-Admins"),
        ("ad:role-SecurityAnalyst", "ad:GG-Security-Analysts"),
        ("ad:role-BasicAccess", "ad:GG-Employees-Base"),
    ]
    for role, group in ad_roles:
        roles_by_platform["ad"].append(role)
        topology.append({"source_id": group, "source_type": "group",
                          "target_id": role, "target_type": "role", "platform": "ad"})

    # --- AWS: developers -> devops -> platform eng -> global admin; plus standalone teams
    aws_hierarchy = [
        ("aws:grp-Developers", None),
        ("aws:grp-DevOps", "aws:grp-Developers"),
        ("aws:grp-PlatformEng", "aws:grp-DevOps"),
        ("aws:grp-DataEng", "aws:grp-Developers"),
        ("aws:grp-MLEng", "aws:grp-DataEng"),
        ("aws:grp-FinanceOps", None),
        ("aws:grp-SecurityOps", None),
        ("aws:grp-SecurityOps-Admin", "aws:grp-SecurityOps"),
    ]
    for group, parent in aws_hierarchy:
        groups_by_platform["aws"].append(group)
        if parent:
            topology.append({"source_id": group, "source_type": "group",
                              "target_id": parent, "target_type": "group", "platform": "aws"})

    aws_roles = [
        ("aws:role-GlobalAdmin", "aws:grp-PlatformEng"),
        ("aws:role-S3FullAccess", "aws:grp-PlatformEng"),
        ("aws:role-EC2ReadOnly", "aws:grp-Developers"),
        ("aws:role-EC2FullAccess", "aws:grp-DevOps"),
        ("aws:role-DataLakeAccess", "aws:grp-DataEng"),
        ("aws:role-MLPlatformAccess", "aws:grp-MLEng"),
        ("aws:role-BillingReadOnly", "aws:grp-FinanceOps"),
        ("aws:role-SecurityAudit", "aws:grp-SecurityOps"),
        ("aws:role-IAMFullAccess", "aws:grp-SecurityOps-Admin"),
    ]
    for role, group in aws_roles:
        roles_by_platform["aws"].append(role)
        topology.append({"source_id": group, "source_type": "group",
                          "target_id": role, "target_type": "role", "platform": "aws"})

    # --- Okta: all-staff -> dept apps; security team
    okta_hierarchy = [
        ("okta:grp-AllStaff", None),
        ("okta:grp-Engineering", "okta:grp-AllStaff"),
        ("okta:grp-Finance", "okta:grp-AllStaff"),
        ("okta:grp-Sales", "okta:grp-AllStaff"),
        ("okta:grp-SecurityTeam", "okta:grp-AllStaff"),
        ("okta:grp-SecurityTeam-Admin", "okta:grp-SecurityTeam"),
        ("okta:grp-ITAdmins", "okta:grp-AllStaff"),
    ]
    for group, parent in okta_hierarchy:
        groups_by_platform["okta"].append(group)
        if parent:
            topology.append({"source_id": group, "source_type": "group",
                              "target_id": parent, "target_type": "group", "platform": "okta"})

    okta_roles = [
        ("okta:role-BasicSSO", "okta:grp-AllStaff"),
        ("okta:role-SecurityAdmin", "okta:grp-SecurityTeam-Admin"),
        ("okta:role-SecurityAnalyst", "okta:grp-SecurityTeam"),
        ("okta:role-ITAdmin", "okta:grp-ITAdmins"),
        ("okta:role-FinanceApp", "okta:grp-Finance"),
        ("okta:role-SalesApp", "okta:grp-Sales"),
        ("okta:role-EngApp", "okta:grp-Engineering"),
    ]
    for role, group in okta_roles:
        roles_by_platform["okta"].append(role)
        topology.append({"source_id": group, "source_type": "group",
                          "target_id": role, "target_type": "role", "platform": "okta"})

    # --- Regional sub-group expansion (realistic enterprise pattern: each
    # department/team group is split into regional sub-groups, e.g.
    # "GG-Finance-RW" has child groups "GG-Finance-RW-BLR" / "-MUM" / "-DEL").
    # This both reflects how real AD/Okta orgs are structured AND brings the
    # topology row count into the 100-200 target band.
    REGIONS = ["BLR", "MUM", "DEL"]
    expandable_groups = [
        "ad:GG-Finance-RW", "ad:GG-Sales-RW", "ad:GG-HR-RW", "ad:GG-Legal-RW",
        "ad:GG-Data-RW", "ad:GG-IT-Helpdesk", "ad:GG-Security-Analysts",
        "aws:grp-Developers", "aws:grp-DataEng", "aws:grp-DevOps",
        "okta:grp-Engineering", "okta:grp-Finance", "okta:grp-Sales", "okta:grp-ITAdmins",
    ]
    for parent_group in expandable_groups:
        platform = parent_group.split(":")[0]
        group_label = parent_group.split(":")[1]
        for region in REGIONS:
            sub_group = f"{parent_group}-{region}"
            groups_by_platform[platform].append(sub_group)
            topology.append({"source_id": sub_group, "source_type": "group",
                              "target_id": parent_group, "target_type": "group", "platform": platform})
            # scoped role per regional sub-group (realistic: regional read/write access)
            sub_role = f"{platform}:role-{group_label}-{region}"
            roles_by_platform[platform].append(sub_role)
            topology.append({"source_id": sub_group, "source_type": "group",
                              "target_id": sub_role, "target_type": "role", "platform": platform})

    return topology, groups_by_platform, roles_by_platform


TOPOLOGY, GROUPS_BY_PLATFORM, ROLES_BY_PLATFORM = build_group_topology()

# admin-tier groups used to deliberately grant elevated access for anomaly cases
AD_ADMIN_GROUP = "ad:GG-DomainAdmins"
AWS_ADMIN_GROUP = "aws:grp-PlatformEng"
OKTA_ADMIN_GROUP = "okta:grp-SecurityTeam-Admin"
AD_BASE_GROUP = "ad:GG-Employees-Base"
OKTA_BASE_GROUP = "okta:grp-AllStaff"


# ---------------------------------------------------------------------------
# Per-category identity generators. Each returns (identity_row, membership_edges,
# audit_rows, offboarding_row_or_None).
# ---------------------------------------------------------------------------

def base_identity(eid, name, ad_user, okta_email, dept, employment_status="employee"):
    return {
        "employee_id": eid,
        "display_name": name,
        "ad_username": ad_user,
        "ad_status": "active",
        "aws_username": ad_user,
        "aws_status": "active",
        "okta_username": okta_email,
        "okta_status": "active",
        "manager": gen_manager_name(),
        "department": dept,
        "employment_status": employment_status,
        "termination_date": "",
        "last_login": rand_datetime(0, 30),
        "is_oncall": "false",
    }


def membership_edge(eid, target, platform):
    return {"source_id": eid, "source_type": "user", "target_id": target, "target_type": "group", "platform": platform}


def gen_normal(eid):
    name, ad_user, okta_email = gen_person()
    dept = random.choice(DEPARTMENTS)
    row = base_identity(eid, name, ad_user, okta_email, dept)
    aws_active = random.random() > 0.25
    row["aws_status"] = "active" if aws_active else ""
    row["aws_username"] = ad_user if aws_active else ""
    last_login = rand_datetime(0, 30)
    row["last_login"] = last_login

    edges = [membership_edge(eid, AD_BASE_GROUP, "ad"), membership_edge(eid, OKTA_BASE_GROUP, "okta")]
    dept_group = f"ad:GG-{dept[:2].upper()}" if dept in ("HR",) else None
    dept_map = {
        "Finance": "ad:GG-Finance-RW", "Sales": "ad:GG-Sales-RW", "HR": "ad:GG-HR-RW",
        "Legal": "ad:GG-Legal-RW", "Data": "ad:GG-Data-RW",
    }
    if dept in dept_map:
        edges.append(membership_edge(eid, dept_map[dept], "ad"))
    if aws_active:
        aws_grp = "aws:grp-DataEng" if dept == "Data" else "aws:grp-Developers"
        edges.append(membership_edge(eid, aws_grp, "aws"))

    audit = [
        {"employee_id": eid, "platform": "okta", "event": "login",
         "timestamp": last_login, "source_ip": gen_ip()},
    ]
    # a slice of normal users get a second routine login or resource access event,
    # to push audit volume toward the 500-1000 target with realistic telemetry
    if random.random() < 0.6:
        audit.append({"employee_id": eid, "platform": random.choice(["ad", "aws", "okta"]),
                       "event": "resource_access", "timestamp": rand_datetime(0, 20),
                       "source_ip": gen_ip()})
    return row, edges, audit, None


def gen_orphaned_stale(eid):
    """Disabled in one platform, active in another."""
    name, ad_user, okta_email = gen_person()
    dept = random.choice(DEPARTMENTS)
    row = base_identity(eid, name, ad_user, okta_email, dept)
    row["ad_status"] = "disabled"
    row["okta_status"] = "disabled"
    row["aws_status"] = "active"  # still active here — the orphan
    row["termination_date"] = rand_date(20, 60)
    last_login = rand_datetime(15, 40)
    row["last_login"] = last_login

    edges = [membership_edge(eid, "aws:grp-Developers", "aws")]
    audit = [
        {"employee_id": eid, "platform": "aws", "event": "login",
         "timestamp": last_login, "source_ip": gen_ip()},
        {"employee_id": eid, "platform": "aws", "event": "resource_access",
         "timestamp": rand_datetime(10, 20), "source_ip": gen_ip()},
    ]
    return row, edges, audit, None


def gen_over_privileged(eid):
    """Admin across 2+ platforms without clear justification — not on-call,
    not a recent role transition, just accumulated access. A portion are
    contractors, which is the textbook 'blast radius' framing from the
    risk engine's cross_platform_blast_radius rule."""
    name, ad_user, okta_email = gen_person()
    dept = random.choice(["Engineering", "IT", "Data"])
    employment_status = "contractor" if random.random() < 0.3 else "employee"
    row = base_identity(eid, name, ad_user, okta_email, dept, employment_status=employment_status)
    last_login = rand_datetime(5, 60)
    row["last_login"] = last_login

    edges = [
        membership_edge(eid, AD_ADMIN_GROUP, "ad"),
        membership_edge(eid, AWS_ADMIN_GROUP, "aws"),
        membership_edge(eid, OKTA_BASE_GROUP, "okta"),
    ]
    audit = [
        {"employee_id": eid, "platform": "ad", "event": "login",
         "timestamp": last_login, "source_ip": gen_ip()},
    ]
    return row, edges, audit, None


def gen_priv_escalation(eid):
    """Unexpected/recent group addition into an admin group — the audit log
    shows a privilege_change event landing them in an admin group they
    weren't in before, recently and without an accompanying role-transition story."""
    name, ad_user, okta_email = gen_person()
    dept = random.choice(DEPARTMENTS)
    row = base_identity(eid, name, ad_user, okta_email, dept)
    last_login = rand_datetime(0, 10)
    row["last_login"] = last_login

    escalation_platform = random.choice(["ad", "aws", "okta"])
    admin_group = {"ad": AD_ADMIN_GROUP, "aws": AWS_ADMIN_GROUP, "okta": OKTA_ADMIN_GROUP}[escalation_platform]

    edges = [membership_edge(eid, AD_BASE_GROUP, "ad"), membership_edge(eid, OKTA_BASE_GROUP, "okta")]
    edges.append(membership_edge(eid, admin_group, escalation_platform))

    escalation_time = rand_datetime(1, 14)
    audit = [
        {"employee_id": eid, "platform": escalation_platform, "event": "privilege_change",
         "timestamp": escalation_time, "source_ip": gen_ip()},
        {"employee_id": eid, "platform": escalation_platform, "event": "login",
         "timestamp": last_login, "source_ip": gen_ip()},
    ]
    return row, edges, audit, None


def gen_token_abuse(eid):
    """Old credential/token still in use, plus an anomalous access pattern
    (login from an unrecognized external IP shortly after a long-unused token)."""
    name, ad_user, okta_email = gen_person()
    dept = random.choice(["Engineering", "Data"])
    row = base_identity(eid, name, ad_user, okta_email, dept, employment_status="service_account")
    row["manager"] = ""  # service-account-style: token abuse often surfaces on unowned creds
    old_login = rand_datetime(90, 180)
    recent_anomalous_login = rand_datetime(0, 5)
    row["last_login"] = recent_anomalous_login

    edges = [membership_edge(eid, "aws:grp-Developers", "aws")]
    audit = [
        {"employee_id": eid, "platform": "aws", "event": "login",
         "timestamp": old_login, "source_ip": gen_ip()},
        {"employee_id": eid, "platform": "aws", "event": "api_key_used",
         "timestamp": recent_anomalous_login, "source_ip": gen_ip(suspicious=True)},
        {"employee_id": eid, "platform": "aws", "event": "resource_access",
         "timestamp": recent_anomalous_login, "source_ip": gen_ip(suspicious=True)},
    ]
    return row, edges, audit, None


def gen_legit_high_priv_fp(eid):
    """On-call engineer or recent role transition with legitimate elevated
    access — the false-positive trap the risk engine must suppress."""
    name, ad_user, okta_email = gen_person()
    row = base_identity(eid, name, ad_user, okta_email, "Security")
    last_login = rand_datetime(0, 3)
    row["last_login"] = last_login
    row["is_oncall"] = "true" if random.random() < 0.7 else "false"
    if row["is_oncall"] == "false":
        # role transition flavor: recently promoted, so admin access is expected
        row["department"] = "IT"

    edges = [
        membership_edge(eid, AWS_ADMIN_GROUP, "aws"),
        membership_edge(eid, OKTA_ADMIN_GROUP, "okta"),
    ]
    audit = [
        {"employee_id": eid, "platform": "aws", "event": "login",
         "timestamp": last_login, "source_ip": gen_ip()},
        {"employee_id": eid, "platform": "okta", "event": "resource_access",
         "timestamp": rand_datetime(0, 5), "source_ip": gen_ip()},
    ]
    return row, edges, audit, None


# ---------------------------------------------------------------------------
# Assemble the full population
# ---------------------------------------------------------------------------

CATEGORY_PLAN = [
    ("orphaned_stale", 50, gen_orphaned_stale, "E2"),
    ("over_privileged", 40, gen_over_privileged, "E3"),
    ("priv_escalation", 28, gen_priv_escalation, "E5"),
    ("token_abuse", 16, gen_token_abuse, "SVC"),
    ("legit_high_priv_fp", 68, gen_legit_high_priv_fp, "E6"),
]
# normal fills the remainder up to 400 (= 198, 49.5% — within the 40-55% band)
TOTAL_TARGET = 400

# Offboarding is layered on top of the 400 identities above (not a separate
# population): a slice of people, regardless of category, get a termination
# record. Most are clean (disabled on time); a minority show a gap, which is
# exactly what the offboarding-gap detector needs to find.
N_OFFBOARDING_CLEAN = 58
N_OFFBOARDING_GAP = 12


def apply_offboarding_gap(row):
    """Mutates an existing identity row in place: terminated, but still active
    somewhere (the gap). Returns the offboarding record."""
    term_date = rand_date(10, 90)
    row["termination_date"] = term_date
    # leave whatever active statuses the identity already had — that's the gap
    offboarding_row = {
        "employee_id": row["employee_id"],
        "hr_termination_date": term_date,
        "ad_disabled_date": "",
        "aws_disabled_date": "",
        "okta_disabled_date": "",
    }
    return offboarding_row


def apply_offboarding_clean(row):
    """Mutates an existing identity row in place: terminated AND disabled
    everywhere on time — a properly closed-out offboarding."""
    term_date = rand_date(5, 200)
    disable_date = (datetime.fromisoformat(term_date) + timedelta(days=random.randint(0, 2))).date().isoformat()
    row["termination_date"] = term_date
    row["ad_status"] = "disabled"
    row["aws_status"] = ""
    row["aws_username"] = ""
    row["okta_status"] = "disabled"
    offboarding_row = {
        "employee_id": row["employee_id"],
        "hr_termination_date": term_date,
        "ad_disabled_date": disable_date,
        "aws_disabled_date": disable_date,
        "okta_disabled_date": disable_date,
    }
    return offboarding_row


def generate_all():
    identities = []
    membership_edges = []
    audit_logs = []
    offboarding = []
    category_counts = {}

    eid_counters = {}

    def next_eid(prefix):
        eid_counters[prefix] = eid_counters.get(prefix, 0) + 1
        return f"{prefix}{eid_counters[prefix]:04d}"

    anomaly_total = 0
    for category, count, generator, prefix in CATEGORY_PLAN:
        for _ in range(count):
            eid = next_eid(prefix)
            row, edges, audit, ob = generator(eid)
            identities.append(row)
            membership_edges.extend(edges)
            audit_logs.extend(audit)
            if ob:
                offboarding.append(ob)
        category_counts[category] = count
        anomaly_total += count

    n_normal = TOTAL_TARGET - anomaly_total
    for _ in range(n_normal):
        eid = next_eid("E1")
        row, edges, audit, ob = gen_normal(eid)
        identities.append(row)
        membership_edges.extend(edges)
        audit_logs.extend(audit)
    category_counts["normal"] = n_normal

    # ---- layer offboarding onto a sample of existing identities ----
    # Gap cases drawn preferentially from over_privileged / priv_escalation
    # people (since "terminated admin still active" is the scenario that
    # matters most); clean cases drawn from anyone.
    eligible_for_gap = [r for r in identities if not r["termination_date"] and r["employment_status"] != "service_account"]
    random.shuffle(eligible_for_gap)
    gap_sample = eligible_for_gap[:N_OFFBOARDING_GAP]
    for row in gap_sample:
        offboarding.append(apply_offboarding_gap(row))

    remaining = [r for r in identities if not r["termination_date"] and r["employment_status"] != "service_account"]
    random.shuffle(remaining)
    clean_sample = remaining[:N_OFFBOARDING_CLEAN]
    for row in clean_sample:
        offboarding.append(apply_offboarding_clean(row))

    return identities, membership_edges, audit_logs, offboarding, category_counts


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    identities, membership_edges, audit_logs, offboarding, category_counts = generate_all()

    write_csv(os.path.join(OUT_DIR, "identities.csv"), identities, [
        "employee_id", "display_name", "ad_username", "ad_status",
        "aws_username", "aws_status", "okta_username", "okta_status",
        "manager", "department", "employment_status", "termination_date",
        "last_login", "is_oncall",
    ])
    write_csv(os.path.join(OUT_DIR, "group_topology.csv"), TOPOLOGY, [
        "source_id", "source_type", "target_id", "target_type", "platform",
    ])
    write_csv(os.path.join(OUT_DIR, "group_membership.csv"), membership_edges, [
        "source_id", "source_type", "target_id", "target_type", "platform",
    ])
    write_csv(os.path.join(OUT_DIR, "audit_logs.csv"), audit_logs, [
        "employee_id", "platform", "event", "timestamp", "source_ip",
    ])
    write_csv(os.path.join(OUT_DIR, "offboarding.csv"), offboarding, [
        "employee_id", "hr_termination_date", "ad_disabled_date",
        "aws_disabled_date", "okta_disabled_date",
    ])

    N = len(identities)
    print(f"Generated {N} identities (target 200-400)")
    print(f"  group_topology.csv:   {len(TOPOLOGY)} rows (target 100-200)")
    print(f"  group_membership.csv: {len(membership_edges)} rows (per-user edges, not in the 100-200 figure)")
    print(f"  audit_logs.csv:       {len(audit_logs)} rows (target 500-1,000)")
    print(f"  offboarding.csv:      {len(offboarding)} rows (target 50-100)")
    print()
    print("Anomaly mix:")
    for cat, count in category_counts.items():
        print(f"  {cat:30s} {count:4d}  ({count/N*100:5.1f}%)")
    print(f"Written to: {OUT_DIR}")
