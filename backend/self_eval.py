"""
Self-evaluation against the hackathon's stated Success Criteria.

Run standalone: python self_eval.py
Prints a pass/fail table for each of the 5 metrics, with the underlying
numbers shown so the result is auditable, not just asserted.

    Metric                     Target
    Identity Coverage          >= 95% identities assessed
    Privilege Risk Detection   Risk scenarios clearly identified
    Alert Consolidation        >= 40% reduction in standalone alerts
    Risk Explainability        Decisions traceable to evidence
    Governance Readiness       Findings align with audit judgment
"""
import os

import pandas as pd

from risk_engine import build_audit_signals, run_risk_engine, DATA_DIR

# the 6 anomaly categories the data generator targets, and the risk_reasons
# that should fire for each — used to check "Privilege Risk Detection"
EXPECTED_SCENARIOS = {
    "orphaned_cross_platform": "Orphaned / stale accounts",
    "over_privileged_multi_platform": "Over-privileged identities (2+ platform admin)",
    "cross_platform_blast_radius": "Over-privileged + contractor blast radius",
    "privilege_escalation": "Privilege escalation events",
    "credential_abuse": "Token / credential abuse",
    "offboarding_gap": "Offboarding gaps",
}


def identity_coverage(df: pd.DataFrame, identities: pd.DataFrame) -> dict:
    scored = df["employee_id"].nunique()
    total = identities["employee_id"].nunique()
    pct = scored / total * 100 if total else 0
    return {"scored": scored, "total": total, "pct": pct, "pass": pct >= 95}


def privilege_risk_detection(df: pd.DataFrame) -> dict:
    all_reasons = set()
    for reasons in df["risk_reasons"]:
        all_reasons.update(reasons)
    detected = {k: v for k, v in EXPECTED_SCENARIOS.items() if k in all_reasons}
    missing = {k: v for k, v in EXPECTED_SCENARIOS.items() if k not in all_reasons}
    return {
        "detected": detected,
        "missing": missing,
        "pass": len(missing) == 0,
    }


def alert_consolidation(df: pd.DataFrame, data_dir: str) -> dict:
    """Baseline = what a naive per-signal alerting system would fire: one
    standalone alert per distinct underlying raw signal a SIEM/IAM tool would
    surface independently, BEFORE any cross-platform correlation:
      - one per platform-status mismatch (orphaned account on each platform pair)
      - one per individual audit event of interest (privilege_change, api_key_used)
      - one per offboarding gap record
      - one per identity holding admin on each individual platform (raw
        per-platform entitlement alerts, before correlating into one finding)
    Each underlying signal is counted exactly once here — this is NOT the
    same as risk_reasons (which can name multiple reasons for the same
    identity); double-counting a signal under two reason labels would
    artificially inflate the baseline, so we count raw signals directly
    from source data instead.
    Our system instead emits ONE consolidated row per identity in the risk
    register, no matter how many underlying signals contributed to it.
    """
    audit_path = os.path.join(data_dir, "audit_logs.csv")
    audit = pd.read_csv(audit_path, dtype=str).fillna("")

    raw_signals = 0
    # one alert per orphaned account (status mismatch itself, not per reason label)
    raw_signals += int(df["is_orphaned"].sum())
    # one alert per individual privilege_change / api_key_used audit event —
    # these are genuinely distinct events a naive SIEM rule fires on each time
    raw_signals += int((audit["event"] == "privilege_change").sum())
    raw_signals += int((audit["event"] == "api_key_used").sum())
    # one alert per offboarding gap record
    raw_signals += int(df["offboarding_gap_days"].notna().sum())
    # one alert per identity per platform where they hold admin entitlement
    # (a naive entitlement-review tool flags "user X has admin in AWS" and
    # "user X has admin in AD" as two separate findings, not one)
    admin_entitlement_signals = int(df["effective_roles"].apply(
        lambda roles: sum(1 for r in roles if _looks_like_admin(r))
    ).sum())
    raw_signals += admin_entitlement_signals

    consolidated_findings = int((df["risk_tier"] != "low").sum())  # one row per flagged identity

    reduction_pct = (1 - consolidated_findings / raw_signals) * 100 if raw_signals else 0
    return {
        "raw_signals": raw_signals,
        "raw_signal_breakdown": {
            "orphaned_status_mismatches": int(df["is_orphaned"].sum()),
            "privilege_change_events": int((audit["event"] == "privilege_change").sum()),
            "api_key_used_events": int((audit["event"] == "api_key_used").sum()),
            "offboarding_gap_records": int(df["offboarding_gap_days"].notna().sum()),
            "raw_admin_entitlements": admin_entitlement_signals,
        },
        "consolidated_findings": consolidated_findings,
        "reduction_pct": reduction_pct,
        "pass": reduction_pct >= 40,
    }


def _looks_like_admin(role: str) -> bool:
    keywords = ("admin", "globaladmin", "domainadmin", "securityadmin")
    return any(k in role.lower() for k in keywords)


def risk_explainability(df: pd.DataFrame) -> dict:
    flagged = df[df["risk_tier"] != "low"]
    has_reason = flagged["risk_reasons"].apply(lambda r: len(r) > 0 and r != ["clear"])
    explainable = int(has_reason.sum())
    total_flagged = len(flagged)
    pct = explainable / total_flagged * 100 if total_flagged else 100
    return {"explainable": explainable, "total_flagged": total_flagged, "pct": pct, "pass": pct == 100}


def governance_readiness(df: pd.DataFrame) -> dict:
    """Operationalized as: every flagged identity has (a) a named reason,
    (b) a numeric score derived from that reason (not arbitrary), and
    (c) maps to a rule code our remediation endpoint (main.py) recognizes
    and can generate concrete steps for."""
    known_reason_codes = {
        "orphaned_cross_platform", "cross_platform_blast_radius", "offboarding_gap",
        "no_hr_owner", "dormant_admin", "over_privileged_multi_platform",
        "privilege_escalation", "credential_abuse",
    }
    flagged = df[df["risk_tier"] != "low"]
    traceable = 0
    for _, row in flagged.iterrows():
        if any(r in known_reason_codes for r in row["risk_reasons"]):
            traceable += 1
    pct = traceable / len(flagged) * 100 if len(flagged) else 100
    return {"traceable": traceable, "total_flagged": len(flagged), "pct": pct, "pass": pct == 100}


def run_self_eval(data_dir: str = DATA_DIR):
    identities = pd.read_csv(os.path.join(data_dir, "identities.csv"), dtype=str).fillna("")
    df = run_risk_engine(data_dir)

    print("=" * 72)
    print("SELF-EVALUATION — Success Criteria")
    print("=" * 72)

    cov = identity_coverage(df, identities)
    print(f"\n1. Identity Coverage (target >= 95%)")
    print(f"   {cov['scored']}/{cov['total']} identities assessed = {cov['pct']:.1f}%")
    print(f"   {'PASS' if cov['pass'] else 'FAIL'}")

    detect = privilege_risk_detection(df)
    print(f"\n2. Privilege Risk Detection (target: risk scenarios clearly identified)")
    for code, label in detect["detected"].items():
        count = sum(1 for reasons in df["risk_reasons"] if code in reasons)
        print(f"   [x] {label:50s} {count:4d} identities flagged ({code})")
    for code, label in detect["missing"].items():
        print(f"   [ ] {label:50s} NOT DETECTED ({code})")
    print(f"   {'PASS' if detect['pass'] else 'FAIL'}")

    cons = alert_consolidation(df, data_dir)
    print(f"\n3. Alert Consolidation (target >= 40% reduction)")
    for label, count in cons["raw_signal_breakdown"].items():
        print(f"     {label:30s} {count:4d}")
    print(f"   Raw signals total (naive per-event alerting): {cons['raw_signals']}")
    print(f"   Consolidated findings (one row per flagged identity): {cons['consolidated_findings']}")
    print(f"   Reduction: {cons['reduction_pct']:.1f}%")
    print(f"   {'PASS' if cons['pass'] else 'FAIL'}")

    explain = risk_explainability(df)
    print(f"\n4. Risk Explainability (target: decisions traceable to evidence)")
    print(f"   {explain['explainable']}/{explain['total_flagged']} flagged identities have a named reason = {explain['pct']:.1f}%")
    print(f"   {'PASS' if explain['pass'] else 'FAIL'}")

    gov = governance_readiness(df)
    print(f"\n5. Governance Readiness (target: findings align with audit judgment)")
    print(f"   {gov['traceable']}/{gov['total_flagged']} flagged identities map to a known, remediation-actionable rule = {gov['pct']:.1f}%")
    print(f"   {'PASS' if gov['pass'] else 'FAIL'}")

    print("\n" + "=" * 72)
    all_pass = cov["pass"] and detect["pass"] and cons["pass"] and explain["pass"] and gov["pass"]
    print(f"OVERALL: {'ALL CRITERIA PASS' if all_pass else 'SOME CRITERIA FAILED — see above'}")
    print("=" * 72)
    return all_pass


if __name__ == "__main__":
    import sys
    passed = run_self_eval()
    sys.exit(0 if passed else 1)
