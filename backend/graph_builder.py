"""
Builds a directed graph of user -> group -> subgroup -> role edges from groups.csv
and exposes effective-privilege resolution via nx.descendants().

This is intentionally the "hackathon way" described in the strategy doc:
no recursive loop, just NetworkX traversal.
"""
import os

import networkx as nx
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class PrivilegeGraph:
    def __init__(self, groups_df: pd.DataFrame):
        self.graph = nx.DiGraph()
        for _, row in groups_df.iterrows():
            self.graph.add_node(row["source_id"], node_type=row["source_type"])
            self.graph.add_node(row["target_id"], node_type=row["target_type"])
            self.graph.add_edge(row["source_id"], row["target_id"], platform=row["platform"])

    def effective_privileges(self, employee_id: str) -> list[str]:
        """All roles reachable from this user, however deeply nested."""
        if employee_id not in self.graph:
            return []
        descendants = nx.descendants(self.graph, employee_id)
        return sorted(
            n for n in descendants
            if self.graph.nodes[n].get("node_type") == "role"
        )

    def effective_groups(self, employee_id: str) -> list[str]:
        if employee_id not in self.graph:
            return []
        descendants = nx.descendants(self.graph, employee_id)
        return sorted(
            n for n in descendants
            if self.graph.nodes[n].get("node_type") == "group"
        )

    def subgraph_for_user(self, employee_id: str) -> dict:
        """Nodes + edges for React Flow: the user's full reachable subgraph,
        with the path(s) to any *role* node flagged so the frontend can
        highlight the dangerous path in red."""
        if employee_id not in self.graph:
            return {"nodes": [], "edges": []}

        reachable = nx.descendants(self.graph, employee_id) | {employee_id}
        sub = self.graph.subgraph(reachable)

        # Find every node that sits on a path to a role node -> highlight
        role_nodes = {n for n in reachable if sub.nodes[n].get("node_type") == "role"}
        on_dangerous_path = set()
        for role in role_nodes:
            for path in nx.all_simple_paths(sub, employee_id, role):
                on_dangerous_path.update(path)

        nodes = []
        for n in sub.nodes:
            nodes.append({
                "id": n,
                "type": sub.nodes[n].get("node_type", "unknown"),
                "is_self": n == employee_id,
                "on_risk_path": n in on_dangerous_path,
            })

        edges = []
        for src, dst, data in sub.edges(data=True):
            edges.append({
                "source": src,
                "target": dst,
                "platform": data.get("platform"),
                "on_risk_path": src in on_dangerous_path and dst in on_dangerous_path,
            })

        return {"nodes": nodes, "edges": edges}


def load_graph(data_dir: str = DATA_DIR) -> PrivilegeGraph:
    """Loads the privilege graph from group_topology.csv + group_membership.csv
    (the static nesting structure + per-user assignments, split per
    DATA_CONTRACT.md). Falls back to a single legacy groups.csv if that's all
    that's present, so older data drops still work."""
    topology_path = os.path.join(data_dir, "group_topology.csv")
    membership_path = os.path.join(data_dir, "group_membership.csv")
    legacy_path = os.path.join(data_dir, "groups.csv")

    frames = []
    if os.path.exists(topology_path) and os.path.exists(membership_path):
        frames.append(pd.read_csv(topology_path, dtype=str).fillna(""))
        frames.append(pd.read_csv(membership_path, dtype=str).fillna(""))
    elif os.path.exists(legacy_path):
        frames.append(pd.read_csv(legacy_path, dtype=str).fillna(""))
    else:
        raise FileNotFoundError(
            "No group data found — expected group_topology.csv + group_membership.csv "
            "(or legacy groups.csv) in " + data_dir
        )

    groups_df = pd.concat(frames, ignore_index=True)
    return PrivilegeGraph(groups_df)


if __name__ == "__main__":
    g = load_graph()
    # quick smoke test against the injected token-abuse / escalation service accounts
    import pandas as pd_check
    ids_df = pd_check.read_csv(os.path.join(DATA_DIR, "identities.csv"), dtype=str)
    sample_ids = ids_df["employee_id"].head(5).tolist()
    for eid in sample_ids:
        print(eid, "->", g.effective_privileges(eid))
