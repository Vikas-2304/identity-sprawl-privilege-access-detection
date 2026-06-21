# Data Contract — Phase 1 → Phase 2 Handoff

Give this file to your teammates building the data generator / graph builder / risk engine.
**If they produce CSVs matching these exact column names, the backend works with zero code changes.**

The backend reads from `backend/data/`. Drop these 5 CSVs in and restart the
server (or call `POST /api/refresh`).

This schema also satisfies the hackathon's stated data-volume and anomaly-mix
requirements — see the targets in each section below. The mock generator
(`mock_data_generator.py`) already hits every target; treat its row counts
as the floor your teammates' real pipeline should also clear.

---

## 1. `identities.csv` — target 200-400 rows

One row per human/service account, already resolved to a canonical identity.

| column | type | notes |
|---|---|---|
| `employee_id` | string | canonical key, e.g. `E1001` |
| `display_name` | string | |
| `ad_username` | string \| empty | |
| `ad_status` | `active` \| `disabled` \| `` (not present in AD) | |
| `aws_username` | string \| empty | |
| `aws_status` | `active` \| `disabled` \| `` | |
| `okta_username` | string \| empty | |
| `okta_status` | `active` \| `disabled` \| `` | |
| `manager` | string | empty = no HR owner (flags service-account orphans) |
| `department` | string | |
| `employment_status` | `employee` \| `contractor` \| `service_account` | |
| `termination_date` | ISO date \| empty | empty = still employed |
| `last_login` | ISO datetime \| empty | most recent login across any platform |
| `is_oncall` | `true` \| `false` | for false-positive suppression |

## 2. `group_topology.csv` — target 100-200 rows

The **static nesting structure**: which groups contain which sub-groups, and
which groups grant which roles. This is topology only — independent of which
users belong to what. One row per edge in the structure.

| column | type | notes |
|---|---|---|
| `source_id` | string | a group or role name |
| `source_type` | `group` \| `role` | |
| `target_id` | string | parent group or role this grants |
| `target_type` | `group` \| `role` | |
| `platform` | `ad` \| `aws` \| `okta` | |

## 3. `group_membership.csv` — per-user assignment edges (NOT counted against the 100-200 topology figure; this necessarily scales with user count, ~2-3 edges/user is typical)

Which users belong to which groups. Same shape as topology but `source_type`
is always `user`.

| column | type | notes |
|---|---|---|
| `source_id` | string | an `employee_id` |
| `source_type` | `user` | always `user` in this file |
| `target_id` | string | a group name from `group_topology.csv` |
| `target_type` | `group` | |
| `platform` | `ad` \| `aws` \| `okta` | |

> The backend loads `group_topology.csv` + `group_membership.csv` together as
> one directed graph into NetworkX. Effective privilege =
> `nx.descendants(graph, employee_id)`, filtered to `target_type == 'role'`.
> Node names must be **globally unique** — prefix per platform
> (e.g. `aws:role-GlobalAdmin`, `ad:GG-Finance-RW`) so AWS and AD groups never collide.
>
> **Legacy fallback:** if your teammates can't split topology/membership in
> time, a single `groups.csv` with the same 5 columns (everything in one
> file) still works — `graph_builder.py` falls back to it automatically.

## 4. `audit_logs.csv` — target 500-1,000 rows

| column | type | notes |
|---|---|---|
| `employee_id` | string | |
| `platform` | `ad` \| `aws` \| `okta` | |
| `event` | string | `login`, `privilege_change`, `resource_access`, `api_key_used` |
| `timestamp` | ISO datetime | |
| `source_ip` | string | IPv4. `10.x.x.x` = trusted office/VPN range; anything else is treated as an unrecognized external IP and feeds the credential-abuse detector |

Event types that drive specific risk rules:
- `privilege_change` within the last 14 days + identity currently holds an
  admin role → **privilege escalation** rule fires
- `api_key_used` paired with a non-`10.x.x.x` `source_ip` for the same
  identity → **credential/token abuse** rule fires

## 5. `offboarding.csv` — target 50-100 rows

A subset of identities who have left — most should be clean (disabled on
time), a minority (~15-20%) should show a gap, since that's what the
offboarding-gap detector needs to find.

| column | type | notes |
|---|---|---|
| `employee_id` | string | |
| `hr_termination_date` | ISO date | source of truth from HR |
| `ad_disabled_date` | ISO date \| empty | empty = not yet disabled (the gap) |
| `aws_disabled_date` | ISO date \| empty | |
| `okta_disabled_date` | ISO date \| empty | |

---

## Anomaly mix your data should hit (across the 200-400 identities)

| category | target share | how it's detected |
|---|---|---|
| Orphaned/stale (disabled in one platform, active in another) | 10-15% | `ad_status`/`aws_status`/`okta_status` mismatch |
| Over-privileged (admin on 2+ platforms, no justification) | 8-12% | effective_roles spans 2+ platform admin roles |
| Privilege escalation (recent unexpected group addition) | 5-8% | `privilege_change` audit event within 14 days + current admin role |
| Token/credential abuse (old token, anomalous API usage) | 3-5% | `api_key_used` + suspicious `source_ip` |
| Legitimate high-privilege (on-call, role transition) — **false positive trap** | 15-20% | `is_oncall=true` + admin role → score suppressed, not flagged |
| Normal activity | 40-55% | no rules fire |

The risk engine's `oncall_suppressed` rule depends on the false-positive
slice existing in the data — without it, you can't demo that the engine
tells real risk apart from expected admin access.

---

## Risk score output (what the backend computes — Phase 1 doesn't need to do this)

`risk_engine.py` reads all 5 files above and computes, per identity:

```json
{
  "employee_id": "E1001",
  "risk_score": 95,
  "risk_tier": "critical",
  "risk_reasons": ["cross_platform_blast_radius"],
  "effective_roles": ["aws:role-GlobalAdmin", "ad:role-DomainAdmin"],
  "platforms_active": ["ad", "aws"],
  "is_orphaned": false,
  "offboarding_gap_days": null
}
```

**If your teammates would rather hand off pre-computed risk scores instead of raw CSVs**,
they can write a 6th file `risk_scores.csv` with these exact columns, and the backend
will skip its own scoring and just serve their numbers. Tell them to ping you before
doing this so the schema stays in sync — easier to agree now than mid-demo.

---

## Quick way to unblock yourself RIGHT NOW

You don't need to wait. Run:

```bash
cd backend
python mock_data_generator.py
```

This generates all 5 CSVs with realistic fake data, hitting every volume
target above and the exact anomaly-mix percentages, so you can build + demo
the full stack today. Verify it yourself with:

```bash
python self_eval.py
```

This prints a pass/fail table against the hackathon's stated Success
Criteria (identity coverage, detection coverage, alert consolidation,
explainability, governance readiness) — useful as a slide for judges.

When your teammates' real generator/risk engine is ready, just drop their
CSVs into `backend/data/` (matching the schema above) and call
`POST /api/refresh` — the backend rebuilds from their files, nothing else
changes.
