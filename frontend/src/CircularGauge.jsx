import React from "react";

/**
 * Circular arc gauge inspired by maritime ECDIS instrumentation
 * Matches the RPM, SOG, Wind Speed, and Wave Height gauges in the reference UI
 */
function CircularGauge({
  label = "SOG",
  value = 0,
  unit = "KTS",
  min = 0,
  max = 40,
  color = "#B8944A",
  size = 110,
  subLabel = null
}) {
  const radius = size * 0.38;
  const strokeWidth = size * 0.08;
  const center = size / 2;

  // 240-degree arc from 150° to 390° (-30°)
  const startAngle = 140;
  const endAngle = 400;
  const totalAngle = endAngle - startAngle;

  const clampedVal = Math.max(min, Math.min(max, Number(value) || 0));
  const fraction = (clampedVal - min) / (max - min || 1);
  const currentAngle = startAngle + fraction * totalAngle;

  // Polar to Cartesian conversion
  const polarToCartesian = (cx, cy, r, angleInDegrees) => {
    const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
    return {
      x: cx + r * Math.cos(angleInRadians),
      y: cy + r * Math.sin(angleInRadians),
    };
  };

  const describeArc = (x, y, r, startAng, endAng) => {
    const start = polarToCartesian(x, y, r, startAng);
    const end = polarToCartesian(x, y, r, endAng);
    const largeArcFlag = endAng - startAng > 180 ? "1" : "0";
    return ["M", start.x, start.y, "A", r, r, 0, largeArcFlag, 1, end.x, end.y].join(" ");
  };

  const backgroundArc = describeArc(center, center, radius, startAngle, endAngle);
  const targetEnd = Math.max(startAngle + 0.8, Math.min(endAngle, currentAngle));
  const valueArc = describeArc(center, center, radius, startAngle, targetEnd);

  const safeId = String(label || "gauge").replace(/[^a-zA-Z0-9_-]/g, "_");

  return (
    <div className="circular-gauge-container" style={{ width: size, minWidth: size }}>
      <svg width={size} height={size * 0.9} viewBox={`0 0 ${size} ${size * 0.9}`}>
        <defs>
          <linearGradient id={`grad-${safeId}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.8" />
            <stop offset="100%" stopColor={color} stopOpacity="1" />
          </linearGradient>
          <filter id={`glow-${safeId}`} x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor={color} floodOpacity="0.3" />
          </filter>
        </defs>

        {/* Track Background */}
        <path
          d={backgroundArc}
          fill="none"
          stroke="#2C2F33"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Active Progress Arc */}
        <path
          d={valueArc}
          fill="none"
          stroke={`url(#grad-${safeId})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          filter={`url(#glow-${safeId})`}
        />

        {/* Needle point tick */}
        {(() => {
          const pt = polarToCartesian(center, center, radius, currentAngle);
          return <circle cx={pt.x} cy={pt.y} r={strokeWidth * 0.65} fill="#EDEDEA" />;
        })()}

        {/* Value Text */}
        <text
          x={center}
          y={center * 0.92}
          textAnchor="middle"
          className="gauge-val-text"
          fill="#EDEDEA"
          fontSize={size * 0.21}
          fontWeight="800"
          fontFamily="'JetBrains Mono', Consolas, monospace"
        >
          {typeof value === "number" ? (value % 1 === 0 ? value : value.toFixed(1)) : value}
        </text>

        {/* Unit Text */}
        <text
          x={center}
          y={center * 0.92 + size * 0.16}
          textAnchor="middle"
          className="gauge-unit-text"
          fill="#8C8D89"
          fontSize={size * 0.11}
          fontWeight="600"
          fontFamily="'JetBrains Mono', monospace"
        >
          {unit}
        </text>
      </svg>
      <div className="gauge-label-caption">
        <span className="gauge-label-name">{label}</span>
        {subLabel && <span className="gauge-label-sub">{subLabel}</span>}
      </div>
    </div>
  );
}

export default React.memo(CircularGauge);
