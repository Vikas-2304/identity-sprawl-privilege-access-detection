"""
Deterministic risk scoring engine (Option B — no ML, fully debuggable).
Reads identities.csv + offboarding.csv + the privilege graph, scores every
identity, and explains *why* in plain rule names the frontend can render
as badges.
"""
import os
from datetime import datetime

import pandas as pd

from graph_builder import PrivilegeGraph, load_graph

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
NOW = datetime(2026, 6, 20)

ADMIN_KEYWORDS = ("admin", "globaladmin", "domainadmin", "securityadmin")


def _is_admin_role(role: str) -> bool:
    return any(k in role.lower() for k in ADMIN_KEYWORDS)


def _days_since(date_str: str) -> int | None:
    if not date_str or pd.isna(date_str):
        return None
    try:
        dt = pd.to_datetime(date_str)
        return int((NOW - dt.to_pydatetime().replace(tzinfo=None)).days)
    except Exception:
        return None


def _is_private_ip(ip: str) -> bool:
    if not ip:
        return True
    octets = ip.split(".")
    if len(octets) != 4:
        return True
    try:
        first, second = int(octets[0]), int(octets[1])
    except ValueError:
        return True
    # our gen_ip() "office/vpn" pools all use 10.x.x.x; anything else is external
    return first == 10


def build_audit_signals(data_dir: str) -> dict:
    """Reads audit_logs.csv once and pre-computes per-employee signals used by
    the privilege-escalation and credential-abuse rules, so risk_engine doesn't
    re-scan the whole log per identity."""
    path = os.path.join(data_dir, "audit_logs.csv")
    try:
        audit = pd.read_csv(path, dtype=str).fillna("")
    except FileNotFoundError:
        return {}

    signals = {}
    for eid, group in audit.groupby("employee_id"):
        recent_priv_change = group[group["event"] == "privilege_change"]
        recent_priv_change_days = None
        if not recent_priv_change.empty:
            most_recent = recent_priv_change["timestamp"].max()
            recent_priv_change_days = _days_since(most_recent)

        api_key_events = group[group["event"] == "api_key_used"]
        suspicious_ip_events = group[group.get("source_ip", "").apply(_is_private_ip) == False]
        has_old_then_suspicious = False
        if not api_key_events.empty and not suspicious_ip_events.empty:
            has_old_then_suspicious = True

        signals[eid] = {
            "recent_priv_change_days": recent_priv_change_days,
            "has_suspicious_ip_activity": not suspicious_ip_events.empty,
            "has_api_key_usage": not api_key_events.empty,
        }
    return signals


def score_identity(row: pd.Series, graph: PrivilegeGraph, offboarding_lookup: dict, audit_signals: dict) -> dict:
    eid = row["employee_id"]
    reasons = []
    score = 0

    platforms_active = []
    if row.get("ad_status") == "active":
        platforms_active.append("ad")
    if row.get("aws_status") == "active":
        platforms_active.append("aws")
    if row.get("okta_status") == "active":
        platforms_active.append("okta")

    effective_roles = graph.effective_privileges(eid)
    has_admin = any(_is_admin_role(r) for r in effective_roles)
    admin_platform_count = sum(
        1 for plat, active in [("ad", row.get("ad_status") == "active"),
                                ("aws", row.get("aws_status") == "active"),
                                ("okta", row.get("okta_status") == "active")]
        if active and any(_is_admin_role(r) and r.startswith(plat) for r in effective_roles)
    )
    is_oncall = str(row.get("is_oncall", "")).lower() == "true"
    employment_status = row.get("employment_status", "")
    last_login_days = _days_since(row.get("last_login", ""))
    signals = audit_signals.get(eid, {})

    # --- Rule 1: Orphaned account — disabled in one platform, active in another ---
    statuses = [row.get("ad_status"), row.get("aws_status"), row.get("okta_status")]
    has_disabled = "disabled" in statuses
    has_active = "active" in statuses
    is_orphaned = has_disabled and has_active
    if is_orphaned:
        score = max(score, 90)
        reasons.append("orphaned_cross_platform")

    # --- Rule 2: Dormant admin — has admin effective privilege, no login in 90d ---
    if has_admin and (last_login_days is None or last_login_days > 90):
        score = max(score, 85)
        reasons.append("dormant_admin")

    # --- Rule 3: Cross-platform blast radius — admin + contractor ---
    if has_admin and employment_status == "contractor":
        score = max(score, 95)
        reasons.append("cross_platform_blast_radius")

    # --- Rule 4: Over-privileged — admin on 2+ platforms without contractor/dormant context ---
    if admin_platform_count >= 2 and "cross_platform_blast_radius" not in reasons:
        score = max(score, 88)
        reasons.append("over_privileged_multi_platform")

    # --- Rule 5: Privilege escalation — recent privilege_change event landing in admin scope ---
    if signals.get("recent_priv_change_days") is not None and signals["recent_priv_change_days"] <= 14 and has_admin:
        score = max(score, 92)
        reasons.append("privilege_escalation")

    # --- Rule 6: Token/credential abuse — API key usage paired with non-private-IP access ---
    if signals.get("has_api_key_usage") and signals.get("has_suspicious_ip_activity"):
        score = max(score, 90)
        reasons.append("credential_abuse")

    # --- Bonus: no HR owner at all (service account orphan) ---
    if not row.get("manager") and employment_status == "service_account":
        score = max(score, 80)
        reasons.append("no_hr_owner")

    # --- Offboarding gap: terminated but still active somewhere ---
    offboarding_gap_days = None
    ob = offboarding_lookup.get(eid)
    if ob and ob.get("hr_termination_date") and has_active:
        offboarding_gap_days = _days_since(ob["hr_termination_date"])
        if offboarding_gap_days and offboarding_gap_days > 0:
            score = max(score, 95)
            reasons.append("offboarding_gap")

    # --- False positive suppression: on-call + admin is expected, lower the score ---
    if is_oncall and has_admin and "offboarding_gap" not in reasons:
        score = max(0, score - 40)
        reasons.append("oncall_suppressed")

    if not reasons:
        reasons.append("clear")

    tier = "critical" if score >= 90 else "high" if score >= 70 else "medium" if score >= 40 else "low"

    return {
        "employee_id": eid,
        "display_name": row.get("display_name"),
        "department": row.get("department"),
        "employment_status": employment_status,
        "risk_score": score,
        "risk_tier": tier,
        "risk_reasons": reasons,
        "effective_roles": effective_roles,
        "platforms_active": platforms_active,
        "is_orphaned": is_orphaned,
        "is_oncall": is_oncall,
        "offboarding_gap_days": offboarding_gap_days,
        "last_login": row.get("last_login"),
        "manager": row.get("manager"),
    }


def run_risk_engine(data_dir: str = DATA_DIR) -> pd.DataFrame:
    identities = pd.read_csv(os.path.join(data_dir, "identities.csv"), dtype=str).fillna("")
    try:
        offboarding = pd.read_csv(os.path.join(data_dir, "offboarding.csv"), dtype=str).fillna("")
        offboarding_lookup = offboarding.set_index("employee_id").to_dict(orient="index")
    except FileNotFoundError:
        offboarding_lookup = {}

    graph = load_graph(data_dir)
    audit_signals = build_audit_signals(data_dir)

    results = [score_identity(row, graph, offboarding_lookup, audit_signals) for _, row in identities.iterrows()]
    df = pd.DataFrame(results).sort_values("risk_score", ascending=False).reset_index(drop=True)
    # NaN isn't valid JSON — convert to None so FastAPI/pydantic serializes cleanly.
    df["offboarding_gap_days"] = df["offboarding_gap_days"].astype(object).where(
        df["offboarding_gap_days"].notna(), None
    )
    return df


if __name__ == "__main__":
    df = run_risk_engine()
    print(df[["employee_id", "display_name", "risk_score", "risk_tier", "risk_reasons"]].head(20).to_string())
    print(f"\nTotal: {len(df)} identities scored")
    print(df["risk_tier"].value_counts())
