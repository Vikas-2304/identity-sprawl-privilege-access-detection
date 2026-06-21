"""
FastAPI backend for the Identity Risk Console.

Endpoints:
  GET /api/risk-register          -> sorted list of users + risk scores + reasons
  GET /api/user/{id}/graph        -> nodes/edges for React Flow (effective access map)
  GET /api/user/{id}/remediation  -> step-by-step remediation instructions

Run with: uvicorn main:app --reload --port 8000
"""
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph_builder import load_graph
from risk_engine import run_risk_engine

app = FastAPI(title="Identity Risk Console API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon: wide open. Tighten if you have time.
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Cached data layer ----------
# Re-running the risk engine on every request would be wasteful; cache it and
# expose a /api/refresh endpoint so the frontend can force a recompute after
# teammates drop in new CSVs, without restarting the server.

@lru_cache(maxsize=1)
def get_risk_df():
    return run_risk_engine()


@lru_cache(maxsize=1)
def get_graph():
    return load_graph()


# ---------- Response models ----------

class RiskRegisterEntry(BaseModel):
    employee_id: str
    display_name: str
    department: str
    employment_status: str
    risk_score: int
    risk_tier: str
    risk_reasons: list[str]
    platforms_active: list[str]
    is_orphaned: bool
    is_oncall: bool
    offboarding_gap_days: Optional[int] = None
    last_login: str
    manager: str


class GraphNode(BaseModel):
    id: str
    type: str
    is_self: bool
    on_risk_path: bool


class GraphEdge(BaseModel):
    source: str
    target: str
    platform: str
    on_risk_path: bool


class GraphResponse(BaseModel):
    employee_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RemediationStep(BaseModel):
    order: int
    description: str
    command: Optional[str] = None


class RemediationResponse(BaseModel):
    employee_id: str
    display_name: str
    risk_tier: str
    summary: str
    steps: list[RemediationStep]


# ---------- Endpoints ----------

@app.get("/api/risk-register", response_model=list[RiskRegisterEntry])
def risk_register(
    tier: Optional[str] = Query(None, description="Filter by risk_tier: critical|high|medium|low"),
    offboarding_gaps_only: bool = Query(False, description="Only show offboarding gap cases"),
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or employee_id"),
):
    df = get_risk_df()

    if tier:
        df = df[df["risk_tier"] == tier]
    if offboarding_gaps_only:
        df = df[df["offboarding_gap_days"].notna()]
    if department:
        df = df[df["department"] == department]
    if search:
        s = search.lower()
        df = df[
            df["display_name"].str.lower().str.contains(s)
            | df["employee_id"].str.lower().str.contains(s)
        ]

    return df.to_dict(orient="records")


@app.get("/api/user/{employee_id}/graph", response_model=GraphResponse)
def user_graph(employee_id: str):
    graph = get_graph()
    if employee_id not in graph.graph:
        raise HTTPException(status_code=404, detail=f"Identity '{employee_id}' not found in privilege graph")
    result = graph.subgraph_for_user(employee_id)
    return {"employee_id": employee_id, **result}


@app.get("/api/user/{employee_id}/remediation", response_model=RemediationResponse)
def user_remediation(employee_id: str):
    df = get_risk_df()
    match = df[df["employee_id"] == employee_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Identity '{employee_id}' not found")
    row = match.iloc[0]

    steps = []
    order = 1

    if "orphaned_cross_platform" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="Account is disabled in one platform but still active in another. Disable the active sessions immediately.",
            command="aws iam update-login-profile --user-name <aws_username> --password-reset-required",
        ))
        order += 1
        steps.append(RemediationStep(
            order=order,
            description="Revoke any active AWS access keys for this orphaned identity.",
            command="aws iam list-access-keys --user-name <aws_username> && aws iam delete-access-key --access-key-id <key-id> --user-name <aws_username>",
        ))
        order += 1

    if "cross_platform_blast_radius" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="Contractor holds admin privileges across multiple platforms. Downgrade to least-privilege role pending manager review.",
            command="aws iam remove-user-from-group --user-name <aws_username> --group-name grp-PlatformEng",
        ))
        order += 1
        steps.append(RemediationStep(
            order=order,
            description="Remove from AD Domain Admins group.",
            command="Remove-ADGroupMember -Identity 'GG-DomainAdmins' -Members <ad_username>",
        ))
        order += 1

    if "offboarding_gap" in row["risk_reasons"]:
        gap_days = int(row['offboarding_gap_days']) if row['offboarding_gap_days'] is not None else "?"
        steps.append(RemediationStep(
            order=order,
            description=f"HR termination was recorded {gap_days} days ago but accounts remain active. Disable all platform access now.",
            command="Disable-ADAccount -Identity <ad_username>",
        ))
        order += 1

    if "no_hr_owner" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="Service account has no assigned HR owner. Assign an accountable owner or schedule for decommission.",
            command=None,
        ))
        order += 1
        if any("GlobalAdmin" in r or "DomainAdmin" in r for r in row["effective_roles"]):
            steps.append(RemediationStep(
                order=order,
                description="This service account reaches admin privilege through a nested group chain. Move it out of the privileged group and into a scoped role.",
                command="aws iam remove-user-from-group --user-name <aws_username> --group-name grp-PlatformEng",
            ))
            order += 1

    if "dormant_admin" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="Admin privilege unused for 90+ days. Revoke standing access; re-grant via just-in-time elevation if needed.",
            command=None,
        ))
        order += 1

    if "over_privileged_multi_platform" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="Identity holds admin-tier access on 2+ platforms with no on-call justification or recent role transition on file. Review with manager and scope down to least privilege.",
            command="aws iam remove-user-from-group --user-name <aws_username> --group-name grp-PlatformEng",
        ))
        order += 1
        steps.append(RemediationStep(
            order=order,
            description="Remove from AD Domain Admins group pending review.",
            command="Remove-ADGroupMember -Identity 'GG-DomainAdmins' -Members <ad_username>",
        ))
        order += 1

    if "privilege_escalation" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="A privilege_change event placed this identity into an admin-scoped group within the last 14 days. Verify the change was approved through change management; if not, revert immediately.",
            command=None,
        ))
        order += 1
        steps.append(RemediationStep(
            order=order,
            description="If unapproved, remove from the admin group and open an incident for the unauthorized escalation.",
            command="aws iam remove-user-from-group --user-name <aws_username> --group-name grp-PlatformEng",
        ))
        order += 1

    if "credential_abuse" in row["risk_reasons"]:
        steps.append(RemediationStep(
            order=order,
            description="API key usage detected from an unrecognized external IP. Rotate the credential immediately and investigate the source.",
            command="aws iam create-access-key --user-name <aws_username> && aws iam delete-access-key --access-key-id <old-key-id> --user-name <aws_username>",
        ))
        order += 1
        steps.append(RemediationStep(
            order=order,
            description="Review CloudTrail/audit logs for this identity over the last 30 days to scope any unauthorized resource access.",
            command=None,
        ))
        order += 1

    if not steps:
        steps.append(RemediationStep(
            order=1,
            description="No immediate action required. Continue routine access review on standard cadence.",
            command=None,
        ))

    summary = (
        f"{row['display_name']} ({employee_id}) scored {row['risk_score']}/100 "
        f"({row['risk_tier']}). {len(steps)} remediation step(s) identified."
    )

    return {
        "employee_id": employee_id,
        "display_name": row["display_name"],
        "risk_tier": row["risk_tier"],
        "summary": summary,
        "steps": [s.model_dump() for s in steps],
    }


@app.post("/api/refresh")
def refresh_data():
    """Call this after dropping new CSVs into backend/data/ to force a recompute
    without restarting the server."""
    get_risk_df.cache_clear()
    get_graph.cache_clear()
    return {"status": "refreshed", "identities_scored": len(get_risk_df())}


@app.get("/api/stats")
def stats():
    """Summary numbers for a dashboard header."""
    df = get_risk_df()
    return {
        "total_identities": len(df),
        "by_tier": df["risk_tier"].value_counts().to_dict(),
        "orphaned_count": int(df["is_orphaned"].sum()),
        "offboarding_gaps": int(df["offboarding_gap_days"].notna().sum()),
    }


@app.get("/")
def root():
    return {"status": "ok", "service": "Identity Risk Console API"}
