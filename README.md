# Identity Risk Console

Cross-platform identity risk dashboard. Backend (FastAPI + Pandas + NetworkX)
gives a deterministic risk-scoring engine; frontend (React + Vite + React Flow)
shows the risk and the employee's reach in graph and remediation advice.

## Two-tier architecture
 
- `backend/` — FastAPI service, mock data generator, graph builder, risk engine
- `frontend/` — React + Vite dashboard with the risk table, identity graph, and remediation panel

## How to run:

**Terminal 1 — backend:**
```bash
cd backend
pip install -r requirements.txt
python mock_data_generator.py   #if you want to generate your datasets with variation
uvicorn main:app --reload --port 8000
```

**Terminal 2 — frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend talks to the backend at
`http://localhost:8000` (configurable via `frontend/.env.example`).

## Backend setup and checks

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

`python mock_data_generator.py` creates the CSVs in `backend/data/`.


## Backend endpoints

- `GET /api/risk-register` — sorted identities with risk scores; supports `tier`, `offboarding_gaps_only`, `department`, and `search`
- `GET /api/user/{id}/graph` — nodes and edges for the privilege graph
- `GET /api/user/{id}/remediation` — step-by-step remediation instructions
- `GET /api/stats` — dashboard summary counts
- `POST /api/refresh` — recompute after replacing CSVs in `backend/data/`

## What's in the dashboard

1. **Risk Register** (left pane) — sortable table of all identities, risk
   score shown as a radial dial, filterable by tier
2. **Identity graph** (right pane, tab 1) — click any row to see that
   identity's full reachable privilege graph via React Flow. The path to any
   admin/role node it can reach is highlighted in red 
3. **Remediation playbook** (right pane, tab 2) — concrete, copyable CLI
   commands generated from which risk rules fired for that identity.

## Backend files

- `mock_data_generator.py` — mock data generator in csv format
- `graph_builder.py` — NetworkX graph used for privilege display
- `risk_engine.py` — rule engine used for scoring
- `main.py` — FastAPI app


## Project layout

```
backend/
  mock_data_generator.py   # Faker-based fake data, 4 risk cases injected
  graph_builder.py         # NetworkX privilege graph + nx.descendants()
  risk_engine.py            # deterministic Option-B scoring rules
  main.py                  # FastAPI app, 3 main endpoints and stats/refresh
  data/                    # generated CSVs folders

frontend/
  src/components/
    RiskRegister.jsx       # Page 1
    IdentityGraph.jsx      # Page 2 (React Flow + dagre auto-layout)
    RemediationPanel.jsx   # Page 3
    RiskDial.jsx           # signature radial score indicator
    ReasonBadge.jsx        # risk-reason chips
    Header.jsx             # stats bar
  src/lib/api.js           # fetch wrapper for all backend calls
```


