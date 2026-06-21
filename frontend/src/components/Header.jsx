export default function Header({ stats }) {
  return (
    <header className="border-b border-bg-line bg-bg-panel px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-signal/10 border border-signal/30 flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 1L14 4V8C14 11.5 11.5 14.2 8 15C4.5 14.2 2 11.5 2 8V4L8 1Z" stroke="#3DDBFF" strokeWidth="1.3" />
            <circle cx="8" cy="7.5" r="1.3" fill="#3DDBFF" />
            <path d="M6.3 10.2C6.6 9.2 7.2 8.7 8 8.7C8.8 8.7 9.4 9.2 9.7 10.2" stroke="#3DDBFF" strokeWidth="1.1" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-ink">Identity Risk Console</h1>
          <p className="text-[11px] text-ink-faint font-mono">cross-platform privilege audit</p>
        </div>
      </div>

      {stats && (
        <div className="flex items-center gap-5 font-mono text-xs">
          <Stat label="identities" value={stats.total_identities} />
          <Stat label="critical" value={stats.by_tier?.critical || 0} color="#FF3B3B" />
          <Stat label="high" value={stats.by_tier?.high || 0} color="#FF9F1C" />
          <Stat label="orphaned" value={stats.orphaned_count} color="#FF3B3B" />
          <Stat label="offboard gaps" value={stats.offboarding_gaps} color="#FF3B3B" />
        </div>
      )}
    </header>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-semibold text-sm" style={{ color: color || "#E6E9EF" }}>{value}</span>
      <span className="text-ink-faint uppercase tracking-wide text-[10px]">{label}</span>
    </div>
  );
}
