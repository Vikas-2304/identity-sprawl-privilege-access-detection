# Identity Risk Console — Backend (Phase 2)

FastAPI service that serves risk-scored identities, the privilege graph, and
remediation steps to the frontend.

## Setup

```bash
cd backend
pip install -r requirements.txt
```

## 1. Generate mock data (unblocks you immediately, no need to wait on teammates)

```bash
python mock_data_generator.py
```

This writes `identities.csv`, `group_topology.csv`, `group_membership.csv`,
`audit_logs.csv`, `offboarding.csv` into `backend/data/`, sized and mixed to
satisfy the hackathon's data-volume spec exactly (400 identities, 131
topology rows, ~700 audit events, 70 offboarding records, exact anomaly-mix
percentages).

When your teammates' real data pipeline is ready, see `DATA_CONTRACT.md` —
just drop their CSVs into `backend/data/` with matching column names and
restart the server (or call `POST /api/refresh`). No code changes needed.

## 2. Verify against the Success Criteria

```bash
python self_eval.py
```

Prints a pass/fail table for all 5 stated success criteria (identity
coverage, privilege risk detection, alert consolidation, explainability,
governance readiness) with the underlying numbers shown — good as a slide
for judges, and re-runnable any time the data changes.

## 3. Run the server

```bash
uvicorn main:app --reload --port 8000
```

Swagger docs auto-generated at: http://localhost:8000/docs

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/risk-register` | Sorted list of identities with risk scores. Query params: `tier`, `offboarding_gaps_only`, `department`, `search` |
| GET | `/api/user/{id}/graph` | Nodes + edges for the privilege graph (React Flow shape) |
| GET | `/api/user/{id}/remediation` | Step-by-step remediation instructions |
| GET | `/api/stats` | Summary counts for a dashboard header |
| POST | `/api/refresh` | Force recompute after dropping in new CSVs |

## Files

- `mock_data_generator.py` — Faker-based fake data, 400 users, exact anomaly-mix percentages
- `graph_builder.py` — NetworkX graph + `nx.descendants()` effective-privilege resolution
- `risk_engine.py` — deterministic Option-B rule engine (no ML), 8 detection rules
- `main.py` — FastAPI app wiring it all together
- `self_eval.py` — measures the 5 stated Success Criteria against the live data
- `DATA_CONTRACT.md` — schema your Phase-1 teammates need to match

## Sanity-test it standalone (no server needed)

```bash
python graph_builder.py   # prints effective privileges for the injected service accounts
python risk_engine.py     # prints top 20 riskiest identities
```
