import { useEffect, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "./dagreLayout";
import { getUserGraph } from "../lib/api";

const NODE_COLORS = {
  user: { border: "#3DDBFF", text: "#3DDBFF", icon: "◆" },
  group: { border: "#5A6275", text: "#E6E9EF", icon: "▢" },
  role: { border: "#FF3B3B", text: "#FF3B3B", icon: "⚠" },
};

function CustomNode({ data }) {
  const colors = NODE_COLORS[data.nodeType] || NODE_COLORS.group;
  const dim = !data.onRiskPath;
  return (
    <div
      className="rounded-lg px-3 py-2 font-mono text-[11px]"
      style={{
        background: "#1B202B",
        border: `1.5px solid ${dim ? "#262C38" : colors.border}`,
        color: dim ? "#5A6275" : colors.text,
        width: 170,
        boxShadow: data.isSelf ? "0 0 0 2px rgba(61,219,255,0.4)" : "none",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "#262C38", border: "none" }} />
      <div className="flex items-center gap-1.5">
        <span style={{ opacity: dim ? 0.4 : 1 }}>{colors.icon}</span>
        <span className="truncate font-medium">{data.label}</span>
      </div>
      {data.platform && (
        <div className="text-[9px] uppercase tracking-wide mt-0.5 opacity-60">{data.platform}</div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: "#262C38", border: "none" }} />
    </div>
  );
}

const nodeTypes = { custom: CustomNode };

function shortLabel(id) {
  // "aws:role-GlobalAdmin" -> "GlobalAdmin" (aws)
  const [platform, rest] = id.includes(":") ? id.split(":") : [null, id];
  const clean = rest.replace(/^(role-|grp-|GG-)/, "");
  return { clean, platform };
}

function toFlowElements(graphData) {
  const nodes = graphData.nodes.map((n) => {
    const { clean, platform } = shortLabel(n.id);
    return {
      id: n.id,
      type: "custom",
      data: { label: clean, platform, isSelf: n.is_self, nodeType: n.type, onRiskPath: n.on_risk_path },
      position: { x: 0, y: 0 },
    };
  });

  const edges = graphData.edges.map((e, i) => ({
    id: `e${i}-${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    animated: e.on_risk_path,
    style: {
      stroke: e.on_risk_path ? "#FF3B3B" : "#262C38",
      strokeWidth: e.on_risk_path ? 1.8 : 1,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: e.on_risk_path ? "#FF3B3B" : "#5A6275",
      width: 14,
      height: 14,
    },
  }));

  return { nodes, edges };
}

export default function IdentityGraph({ employeeId }) {
  const [raw, setRaw] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!employeeId) return;
    setLoading(true);
    setError(null);
    getUserGraph(employeeId)
      .then(setRaw)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [employeeId]);

  useEffect(() => {
    if (!raw) return;
    const { nodes: flowNodes, edges: flowEdges } = toFlowElements(raw);
    const laidOut = dagre(flowNodes, flowEdges);
    setNodes(laidOut);
    setEdges(flowEdges);
  }, [raw, setNodes, setEdges]);

  if (!employeeId) {
    return (
      <div className="h-full flex items-center justify-center text-ink-faint text-sm font-mono">
        Select an identity from the register to inspect its access graph.
      </div>
    );
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center text-ink-dim text-sm font-mono">Tracing privilege paths…</div>;
  }

  if (error) {
    return <div className="h-full flex items-center justify-center text-risk-critical text-sm font-mono">{error}</div>;
  }

  return (
    <div className="h-full relative">
      <div className="absolute top-3 left-3 z-10 bg-bg-panel/90 backdrop-blur border border-bg-line rounded px-3 py-2 text-[11px] font-mono">
        <div className="flex items-center gap-2 text-ink-dim">
          <span className="w-2 h-2 rounded-full bg-risk-critical inline-block" />
          highlighted path = reachable admin/role privilege
        </div>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1B202B" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
