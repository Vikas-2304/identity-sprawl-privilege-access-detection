import { useEffect, useState } from "react";
import Header from "./components/Header";
import RiskRegister from "./components/RiskRegister";
import IdentityGraph from "./components/IdentityGraph";
import RemediationPanel from "./components/RemediationPanel";
import { getStats } from "./lib/api";

export default function App() {
  const [selectedId, setSelectedId] = useState(null);
  const [stats, setStats] = useState(null);
  const [inspectorTab, setInspectorTab] = useState("graph"); // "graph" | "remediation"

  useEffect(() => {
    getStats().then(setStats).catch(() => {});
  }, [selectedId]);

  return (
    <div className="h-screen flex flex-col bg-bg text-ink">
      <Header stats={stats} />

      <div className="flex-1 flex overflow-hidden">
        {/* Main: Risk Register */}
        <div className="flex-1 min-w-0 border-r border-bg-line">
          <RiskRegister onSelectUser={setSelectedId} selectedId={selectedId} />
        </div>

        {/* Inspector pane */}
        <div className="w-[480px] flex-shrink-0 flex flex-col bg-bg-panel">
          <div className="flex border-b border-bg-line">
            <TabButton
              label="Identity graph"
              active={inspectorTab === "graph"}
              onClick={() => setInspectorTab("graph")}
            />
            <TabButton
              label="Remediation"
              active={inspectorTab === "remediation"}
              onClick={() => setInspectorTab("remediation")}
            />
          </div>
          <div className="flex-1 overflow-hidden">
            {inspectorTab === "graph" ? (
              <IdentityGraph employeeId={selectedId} />
            ) : (
              <RemediationPanel employeeId={selectedId} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TabButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 px-4 py-2.5 text-xs font-mono uppercase tracking-wide border-b-2 transition-colors ${
        active
          ? "border-signal text-signal bg-bg-raised/40"
          : "border-transparent text-ink-faint hover:text-ink-dim"
      }`}
    >
      {label}
    </button>
  );
}
