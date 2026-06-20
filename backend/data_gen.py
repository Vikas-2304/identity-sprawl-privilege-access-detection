import pandas as pd
import networkx as nx
from faker import Faker
import random
from datetime import datetime, timedelta

# ============================================================
# DATA GENERATOR
#
# Outputs:
#   identities.csv
#   group_mappings.csv
#   audit_events.csv
#   offboarding_records.csv
#
# Dataset Targets
# ------------------------------------------------------------
# Identities: 300
# Group/Role Mappings: ~200
# Audit Events: 1000
# Offboarding Records: 75
#
# Anomalies
# ------------------------------------------------------------
# Orphaned Accounts: 10% (30 users)
# Over-Privileged Identities: 10% (30 users)
# Dormant Admins: 5% (15 users)
# Token Abuse Users: 3% (9 users)
# Legitimate High Privilege (On-call): 15% (45 users)
#
# Events
# ------------------------------------------------------------
# Privilege Escalation: 6% (60 events)
# Token Abuse: 4% (40 events)
# Remaining events are normal activity
# ============================================================

fake = Faker()
Faker.seed(42)
random.seed(42)

TOTAL_USERS = 300
TOTAL_EVENTS = 1000
TOTAL_OFFBOARDING = 75



users = []

for i in range(1, TOTAL_USERS + 1):

    emp_id = f"EMP{i:04d}"

    name = fake.name()

    user_type = random.choices(
        ["Employee", "Contractor", "Service Account"],
        weights=[75, 15, 10]
    )[0]

    first_name = name.split()[0].lower()

    try:
        last_name = name.split()[1].lower()
    except IndexError:
        last_name = "user"

    users.append(
        {
            "employee_id": emp_id,
            "name": name,
            "type": user_type,
            "is_oncall": False,
            "ad_username": f"{first_name[0]}.{last_name}@corp.local",
            "aws_username": f"aws-user-{i:04d}",
            "okta_username": f"{first_name}.{last_name}@company.com",
            "ad_status": "active",
            "aws_status": "active",
            "okta_status": "active",
            "last_login_days_ago": random.randint(1, 30),
            "token_age_days": random.randint(1, 90),
        }
    )

users_df = pd.DataFrame(users)



all_ids = list(users_df["employee_id"])

random.shuffle(all_ids)

# 15% legitimate high privilege
oncall_ids = all_ids[:45]

# 10% orphaned
orphan_ids = all_ids[45:75]

# 10% overprivileged
overpriv_ids = all_ids[75:105]

# 5% dormant admins
dormant_ids = all_ids[105:120]

# 3% token abuse
token_abuse_ids = all_ids[120:129]


users_df.loc[
    users_df["employee_id"].isin(oncall_ids),
    "is_oncall"
] = True

users_df.loc[
    users_df["employee_id"].isin(oncall_ids),
    "type"
] = "Employee"



users_df.loc[
    users_df["employee_id"].isin(orphan_ids),
    "ad_status"
] = "disabled"

users_df.loc[
    users_df["employee_id"].isin(orphan_ids),
    "last_login_days_ago"
] = random.randint(40, 120)



users_df.loc[
    users_df["employee_id"].isin(overpriv_ids),
    "type"
] = "Contractor"


users_df.loc[
    users_df["employee_id"].isin(dormant_ids),
    "last_login_days_ago"
] = random.randint(95, 180)



users_df.loc[
    users_df["employee_id"].isin(token_abuse_ids),
    "token_age_days"
] = random.randint(365, 730)



G = nx.DiGraph()

groups = [
    "AD_Group_DevOps",
    "AD_Group_Nested_Billing",
    "AD_Group_Helpdesk",
    "AWS_Role_BillingAccess",
    "AWS_Role_AdminAccess",
    "Okta_Group_SuperAdmin",
    "Okta_Group_Readonly",
]

roles = [
    "AD_Domain_Admin",
    "AWS_S3_FullAccess",
    "Okta_App_Salesforce_Admin",
]

for g in groups:
    G.add_node(g, type="Group")

for r in roles:
    G.add_node(r, type="Role")


G.add_edge(
    "AD_Group_DevOps",
    "AWS_Role_BillingAccess",
    platform="AD-to-AWS"
)

G.add_edge(
    "AD_Group_Nested_Billing",
    "AD_Group_DevOps",
    platform="AD-Internal"
)

G.add_edge(
    "AD_Group_Helpdesk",
    "Okta_Group_Readonly",
    platform="AD-to-Okta"
)

mappings = []


mapped_users = random.sample(all_ids, 80)

for emp in mapped_users:

    group = random.choice(groups)

    G.add_edge(
        emp,
        group,
        platform="Mixed"
    )

    mappings.append(
        {
            "source": emp,
            "target": group,
            "platform": "Mixed",
        }
    )



for emp in overpriv_ids:

    G.add_edge(
        emp,
        "AWS_Role_AdminAccess",
        platform="AWS"
    )

    G.add_edge(
        emp,
        "Okta_Group_SuperAdmin",
        platform="Okta"
    )

    mappings.append(
        {
            "source": emp,
            "target": "AWS_Role_AdminAccess",
            "platform": "AWS",
        }
    )

    mappings.append(
        {
            "source": emp,
            "target": "Okta_Group_SuperAdmin",
            "platform": "Okta",
        }
    )



for emp in dormant_ids:

    G.add_edge(
        emp,
        "AD_Domain_Admin",
        platform="AD"
    )

    mappings.append(
        {
            "source": emp,
            "target": "AD_Domain_Admin",
            "platform": "AD",
        }
    )



for emp in oncall_ids:

    G.add_edge(
        emp,
        "AWS_Role_AdminAccess",
        platform="AWS"
    )

    mappings.append(
        {
            "source": emp,
            "target": "AWS_Role_AdminAccess",
            "platform": "AWS",
        }
    )



mappings.extend(
    [
        {
            "source": "AD_Group_DevOps",
            "target": "AWS_Role_BillingAccess",
            "platform": "AD-to-AWS",
        },
        {
            "source": "AD_Group_Nested_Billing",
            "target": "AD_Group_DevOps",
            "platform": "AD-Internal",
        },
        {
            "source": "AD_Group_Helpdesk",
            "target": "Okta_Group_Readonly",
            "platform": "AD-to-Okta",
        },
    ]
)

mappings_df = pd.DataFrame(mappings)



events = []

normal_ids = [
    emp
    for emp in all_ids
    if emp not in dormant_ids
]



for _ in range(500):

    emp = random.choice(normal_ids)

    events.append(
        {
            "event_id": fake.uuid4(),
            "employee_id": emp,
            "timestamp": (
                datetime.now()
                - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23)
                )
            ).isoformat(),
            "source_platform": random.choice(
                ["AD", "AWS", "Okta"]
            ),
            "event_type": "Login",
            "ip_address": fake.ipv4_public(),
            "success": True,
            "details": "Standard_SSO_Login",
        }
    )

for _ in range(400):

    emp = random.choice(normal_ids)

    events.append(
        {
            "event_id": fake.uuid4(),
            "employee_id": emp,
            "timestamp": (
                datetime.now()
                - timedelta(days=random.randint(0, 30))
            ).isoformat(),
            "source_platform": random.choice(
                ["AWS", "Okta"]
            ),
            "event_type": random.choice(
                ["API_Call", "Resource_Access"]
            ),
            "ip_address": fake.ipv4_public(),
            "success": random.choices(
                [True, False],
                weights=[95, 5]
            )[0],
            "details": "Normal_Activity",
        }
    )



for _ in range(60):

    emp = random.choice(all_ids)

    events.append(
        {
            "event_id": fake.uuid4(),
            "employee_id": emp,
            "timestamp": (
                datetime.now()
                - timedelta(days=random.randint(1, 30))
            ).isoformat(),
            "source_platform": random.choice(
                ["AWS", "Okta"]
            ),
            "event_type": "Role_Change",
            "ip_address": fake.ipv4_public(),
            "success": True,
            "details": "Assumed_Admin_Role",
        }
    )


for _ in range(40):

    emp = random.choice(token_abuse_ids)

    events.append(
        {
            "event_id": fake.uuid4(),
            "employee_id": emp,
            "timestamp": (
                datetime.now()
                - timedelta(days=random.randint(0, 5))
            ).isoformat(),
            "source_platform": "AWS",
            "event_type": "API_Call",
            "ip_address": fake.ipv4_public(),
            "success": True,
            "details": (
                f"API_Call_Old_Token_Age_"
                f"{random.randint(365,730)}d"
            ),
        }
    )

events_df = pd.DataFrame(events)



eligible_users = list(
    users_df[
        users_df["type"] != "Service Account"
    ]["employee_id"]
)

offboarded_emps = random.sample(
    eligible_users,
    TOTAL_OFFBOARDING
)

offboarding_records = []

for emp in offboarded_emps:

    term_date = (
        datetime.now()
        - timedelta(days=random.randint(10, 90))
    )

    is_orphan = emp in orphan_ids

    offboarding_records.append(
        {
            "employee_id": emp,
            "termination_date": term_date.strftime(
                "%Y-%m-%d"
            ),
            "ad_disabled": True,
            "aws_disabled": False if is_orphan else True,
            "okta_disabled": False if is_orphan else True,
        }
    )

offboarding_df = pd.DataFrame(
    offboarding_records
)



users_df.to_csv(
    "identities.csv",
    index=False
)

mappings_df.to_csv(
    "group_mappings.csv",
    index=False
)

events_df.to_csv(
    "audit_events.csv",
    index=False
)

offboarding_df.to_csv(
    "offboarding_records.csv",
    index=False
)


print("\nDATASET GENERATED")

print(f"Identities: {len(users_df)}")
print(f"Mappings: {len(mappings_df)}")
print(f"Audit Events: {len(events_df)}")
print(f"Offboarding Records: {len(offboarding_df)}")

print("\n=== ANOMALY SUMMARY ===")

print(
    f"On-Call Users: "
    f"{len(oncall_ids)} "
    f"({len(oncall_ids)/TOTAL_USERS:.1%})"
)

print(
    f"Orphaned Accounts: "
    f"{len(orphan_ids)} "
    f"({len(orphan_ids)/TOTAL_USERS:.1%})"
)

print(
    f"Over-Privileged Users: "
    f"{len(overpriv_ids)} "
    f"({len(overpriv_ids)/TOTAL_USERS:.1%})"
)

print(
    f"Dormant Admins: "
    f"{len(dormant_ids)} "
    f"({len(dormant_ids)/TOTAL_USERS:.1%})"
)

print(
    f"Token Abuse Users: "
    f"{len(token_abuse_ids)} "
    f"({len(token_abuse_ids)/TOTAL_USERS:.1%})"
)

print(
    f"Privilege Escalation Events: "
    f"60 ({60/TOTAL_EVENTS:.1%})"
)

print(
    f"Token Abuse Events: "
    f"40 ({40/TOTAL_EVENTS:.1%})"
)

print("\nCSV files written successfully.")