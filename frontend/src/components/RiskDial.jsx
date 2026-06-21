const TIER_COLORS = {
  critical: "#FF3B3B",
  high: "#FF9F1C",
  medium: "#E8C547",
  low: "#2DD4A8",
};

// The signature element: a small radial "blast radius" ring next to each
// score, rather than a plain colored badge. Filled arc length = score / 100.
export default function RiskDial({ score, tier, size = 36 }) {
  const color = TIER_COLORS[tier] || TIER_COLORS.low;
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;
  const center = size / 2;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className={tier === "critical" ? "pulse-critical rounded-full" : ""}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#262C38"
          strokeWidth="3"
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeDasharray={`${filled} ${circumference}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${center} ${center})`}
        />
      </svg>
      <span
        className="absolute font-mono font-semibold"
        style={{ fontSize: size * 0.32, color }}
      >
        {score}
      </span>
    </div>
  );
}
