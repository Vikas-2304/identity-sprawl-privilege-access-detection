const REASON_LABELS = {
  orphaned_cross_platform: "Orphaned account",
  dormant_admin: "Dormant admin",
  cross_platform_blast_radius: "Cross-platform admin",
  over_privileged_multi_platform: "Over-privileged (multi-platform)",
  privilege_escalation: "Privilege escalation",
  credential_abuse: "Credential / token abuse",
  no_hr_owner: "No HR owner",
  offboarding_gap: "Offboarding gap",
  oncall_suppressed: "On-call (suppressed)",
  clear: "Clear",
};

const REASON_TIER = {
  orphaned_cross_platform: "high",
  dormant_admin: "high",
  cross_platform_blast_radius: "critical",
  over_privileged_multi_platform: "high",
  privilege_escalation: "critical",
  credential_abuse: "critical",
  no_hr_owner: "high",
  offboarding_gap: "critical",
  oncall_suppressed: "low",
  clear: "low",
};

const TIER_CLASSES = {
  critical: "bg-risk-critical/10 text-risk-critical border-risk-critical/30",
  high: "bg-risk-high/10 text-risk-high border-risk-high/30",
  medium: "bg-risk-medium/10 text-risk-medium border-risk-medium/30",
  low: "bg-risk-low/10 text-risk-low border-risk-low/30",
};

export default function ReasonBadge({ reason }) {
  const label = REASON_LABELS[reason] || reason;
  const tier = REASON_TIER[reason] || "low";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border ${TIER_CLASSES[tier]}`}
    >
      {label}
    </span>
  );
}
