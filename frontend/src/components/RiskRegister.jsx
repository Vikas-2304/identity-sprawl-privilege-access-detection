import { useEffect, useMemo, useState } from "react";
import { getRiskRegister } from "../lib/api";
import RiskDial from "./RiskDial";
import ReasonBadge from "./ReasonBadge";

const TIERS = ["critical", "high", "medium", "low"];

const TIER_BUTTON_ACTIVE = {
  critical: "bg-risk-critical/15 border-risk-critical/50 text-risk-critical",
  high: "bg-risk-high/15 border-risk-high/50 text-risk-high",
  medium: "bg-risk-medium/15 border-risk-medium/50 text-risk-medium",
  low: "bg-risk-low/15 border-risk-low/50 text-risk-low",
};

export default function RiskRegister({ onSelectUser, selectedId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tierFilter, setTierFilter] = useState(null);
  const [gapsOnly, setGapsOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("risk_score");
  const [sortDir, setSortDir] = useState("desc");

  useEffect(() => {
    setLoading(true);
    setError(null);
    getRiskRegister({ tier: tierFilter, offboardingGapsOnly: gapsOnly, search: search || undefined })
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tierFilter, gapsOnly, search]);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? av - bv : bv - av;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-bg-line bg-bg-panel">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name or ID…"
          className="bg-bg-raised border border-bg-line rounded px-3 py-1.5 text-xs font-mono text-ink placeholder:text-ink-faint focus:outline-none focus:border-signal/50 w-48"
        />
        <div className="flex items-center gap-1">
          {TIERS.map((t) => (
            <button
              key={t}
              onClick={() => setTierFilter((cur) => (cur === t ? null : t))}
              className={`px-2.5 py-1.5 rounded text-[11px] font-mono uppercase tracking-wide border transition-colors ${
                tierFilter === t
                  ? TIER_BUTTON_ACTIVE[t]
                  : "border-bg-line text-ink-dim hover:border-ink-faint"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <button
          onClick={() => setGapsOnly((v) => !v)}
          className={`ml-auto px-2.5 py-1.5 rounded text-[11px] font-mono border transition-colors ${
            gapsOnly
              ? "bg-risk-critical/15 border-risk-critical/50 text-risk-critical"
              : "border-bg-line text-ink-dim hover:border-ink-faint"
          }`}
        >
          Offboarding gaps only
        </button>
        <span className="text-[11px] text-ink-faint font-mono">{sorted.length} results</span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {loading && <div className="p-6 text-ink-dim text-sm font-mono">Loading register…</div>}
        {error && (
          <div className="p-6 text-risk-critical text-sm font-mono">
            Failed to reach API: {error}
            <div className="text-ink-faint mt-1">Is the backend running on :8000?</div>
          </div>
        )}
        {!loading && !error && (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-bg-panel border-b border-bg-line text-[11px] uppercase tracking-wide text-ink-faint">
              <tr>
                <Th label="Risk" onClick={() => toggleSort("risk_score")} active={sortKey === "risk_score"} dir={sortDir} />
                <Th label="Identity" onClick={() => toggleSort("display_name")} active={sortKey === "display_name"} dir={sortDir} />
                <th className="text-left px-4 py-2 font-medium">Platforms</th>
                <th className="text-left px-4 py-2 font-medium">Top risk factor</th>
                <Th label="Dept" onClick={() => toggleSort("department")} active={sortKey === "department"} dir={sortDir} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr
                  key={r.employee_id}
                  onClick={() => onSelectUser(r.employee_id)}
                  className={`cursor-pointer border-b border-bg-line/60 hover:bg-bg-raised transition-colors ${
                    selectedId === r.employee_id ? "bg-bg-raised" : ""
                  }`}
                >
                  <td className="px-4 py-2.5">
                    <RiskDial score={r.risk_score} tier={r.risk_tier} size={32} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ink">{r.display_name}</div>
                    <div className="text-[11px] font-mono text-ink-faint">{r.employee_id}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-1">
                      {r.platforms_active.map((p) => (
                        <span key={p} className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-bg-raised text-ink-dim border border-bg-line">
                          {p}
                        </span>
                      ))}
                      {r.platforms_active.length === 0 && <span className="text-ink-faint text-[11px]">none</span>}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <ReasonBadge reason={r.risk_reasons[0]} />
                  </td>
                  <td className="px-4 py-2.5 text-ink-dim text-xs">{r.department}</td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-ink-faint text-sm font-mono">
                    No identities match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Th({ label, onClick, active, dir }) {
  return (
    <th onClick={onClick} className="text-left px-4 py-2 font-medium cursor-pointer select-none hover:text-ink-dim">
      {label} {active && <span className="text-signal">{dir === "asc" ? "↑" : "↓"}</span>}
    </th>
  );
}
