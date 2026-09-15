import React from "react";

/**
 * Compass Rose component matching the circular weather compass in the reference image
 * Uses professional maritime palette: #0A0D0C base, #121614 panel, #232823 border,
 * #B8944A brass accent, #C4392E danger/North, #E8E8E0 own-ship pin.
 */
export default function CompassDial({
  heading = 75,
  windDirection = 120,
  size = 140
}) {
  const center = size / 2;
  const radius = size * 0.42;

  // Degrees ticks (every 30 degrees)
  const ticks = [];
  for (let deg = 0; deg < 360; deg += 30) {
    const isCardinal = deg % 90 === 0;
    const tickLen = isCardinal ? size * 0.08 : size * 0.04;
    const rad = ((deg - 90) * Math.PI) / 180;
    const x1 = center + (radius - tickLen) * Math.cos(rad);
    const y1 = center + (radius - tickLen) * Math.sin(rad);
    const x2 = center + radius * Math.cos(rad);
    const y2 = center + radius * Math.sin(rad);

    ticks.push(
      <line
        key={`tick-${deg}`}
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={isCardinal ? "#B8944A" : "#232823"}
        strokeWidth={isCardinal ? 2 : 1}
      />
    );
  }

  return (
    <div className="compass-dial-container" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Outer Ring */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="#121614"
          stroke="#232823"
          strokeWidth="1.5"
        />

        {/* Inner Ring */}
        <circle
          cx={center}
          cy={center}
          r={radius * 0.72}
          fill="#0A0D0C"
          stroke="#232823"
          strokeWidth="1"
        />

        {/* Compass Ticks */}
        {ticks}

        {/* Cardinal Points */}
        <text x={center} y={center - radius * 0.78} textAnchor="middle" fill="#C4392E" fontSize={size * 0.11} fontWeight="800">
          N
        </text>
        <text x={center + radius * 0.82} y={center + size * 0.035} textAnchor="middle" fill="#7A7D72" fontSize={size * 0.09} fontWeight="700">
          E
        </text>
        <text x={center} y={center + radius * 0.88} textAnchor="middle" fill="#7A7D72" fontSize={size * 0.09} fontWeight="700">
          S
        </text>
        <text x={center - radius * 0.82} y={center + size * 0.035} textAnchor="middle" fill="#7A7D72" fontSize={size * 0.09} fontWeight="700">
          W
        </text>

        {/* Heading Needle (North/South pointer styled like ECDIS needle) */}
        <g transform={`rotate(${heading}, ${center}, ${center})`}>
          {/* North Tip (Red #C4392E) */}
          <polygon
            points={`${center},${center - radius * 0.65} ${center - 4},${center} ${center + 4},${center}`}
            fill="#C4392E"
          />
          {/* South Tip (Muted #7A7D72) */}
          <polygon
            points={`${center},${center + radius * 0.65} ${center - 4},${center} ${center + 4},${center}`}
            fill="#7A7D72"
          />
          {/* Center Pin (Own-Ship Outline #E8E8E0) */}
          <circle cx={center} cy={center} r={4} fill="#E8E8E0" stroke="#121614" strokeWidth="1.5" />
        </g>

        {/* Wind Arrow (Brass Pointer #B8944A) */}
        <g transform={`rotate(${windDirection}, ${center}, ${center})`}>
          <line
            x1={center}
            y1={center - radius * 0.45}
            x2={center}
            y2={center - radius * 0.78}
            stroke="#B8944A"
            strokeWidth="2"
            strokeDasharray="2,2"
          />
          <polygon
            points={`${center},${center - radius * 0.88} ${center - 3},${center - radius * 0.75} ${center + 3},${center - radius * 0.75}`}
            fill="#B8944A"
          />
        </g>
      </svg>
      <div className="compass-caption">
        <span className="compass-heading-text">HDG {Math.round(heading)}°</span>
        <span className="compass-wind-text">WIND {Math.round(windDirection)}°</span>
      </div>
    </div>
  );
}
