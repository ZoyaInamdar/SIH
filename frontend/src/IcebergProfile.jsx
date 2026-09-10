import { SHAPE_TEMPLATES } from "./icebergShapes";
import "./hazardPanel.css";

function IcebergProfile({ berg, highlighted = false, alertETA = null, isOnRoute = false }) {
  const rawShape = String(berg.shape_class || "tabular").toLowerCase();
  const shape = rawShape.includes("pinn")
    ? "pinnacle"
    : rawShape.includes("dom")
    ? "domed"
    : rawShape.includes("wedg")
    ? "wedge"
    : rawShape.includes("block")
    ? "blocky"
    : "tabular";

  const freeboardH = Number(berg.estimated_freeboard_m ?? berg.freeboard_m) || 35;
  const draftH = Number(berg.estimated_draft_m) || (freeboardH * 6.5);
  const confidence = Math.max(
    0,
    Math.min(1, Number(berg.draft_confidence ?? berg.confidence ?? 0.85))
  );

  const totalH = 200;
  const canvasW = 120;

  // Calculate proportional waterline Y based on real above/below ratio
  const waterlineY = Math.max(28, Math.min(65, totalH * (freeboardH / (freeboardH + draftH))));
  const underwaterH = totalH - waterlineY;
  const underwaterOpacity = 0.25 + confidence * 0.55;

  const sourceText =
    berg.data_source?.includes("BYU")
      ? "SATELLITE ESTIMATE"
      : berg.source ?? "SATELLITE ESTIMATE";

  const confidenceLabel =
    berg.draft_confidence_label ??
    (confidence >= 0.8
      ? "HIGH"
      : confidence >= 0.5
      ? "MEDIUM"
      : "LOW");

  const ratio =
    draftH > 0
      ? `1:${(draftH / freeboardH).toFixed(1)}`
      : "—";

  const shapeFunction = SHAPE_TEMPLATES[shape] || SHAPE_TEMPLATES.tabular;

  return (
    <div
      className={`iceberg-profile-card ${
        highlighted ? "highlighted" : ""
      }`}
    >
      <div className="profile-status">
        <span
          className={
            alertETA
              ? "status-dot active pulse"
              : highlighted
              ? "status-dot active"
              : "status-dot"
          }
        />

        {alertETA
          ? `🚨 ROUTE PROXIMITY ALERT (${alertETA.formattedETA || `${Math.round(alertETA.hours * 60)} min`} ETA)`
          : isOnRoute
          ? "⚪ ON-ROUTE HAZARD"
          : highlighted
          ? "CLOSEST HAZARD"
          : "STRUCTURE PROFILE"}
      </div>

      {/* Structure Split Badges: Above vs Below Water */}
      <div className="structure-split-badges">
        <div className="structure-badge badge-above">
          <span>▲ ABOVE WATER</span>
          <strong>{freeboardH.toFixed(1)}m</strong>
          <span>Freeboard</span>
        </div>
        <div className="structure-badge badge-below">
          <span>▼ BELOW WATER</span>
          <strong>{draftH.toFixed(1)}m</strong>
          <span>Keel Draft</span>
        </div>
      </div>

      <div className="profile-svg-wrap">
        <svg
          viewBox={`0 0 ${canvasW} ${totalH}`}
          width="100%"
          height="180"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Subtle sonar grid */}
          <line
            x1="0"
            y1={waterlineY}
            x2={canvasW}
            y2={waterlineY}
            stroke="#00e5ff"
            strokeOpacity="0.25"
          />

          <line
            x1={canvasW * 0.25}
            y1="0"
            x2={canvasW * 0.25}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.08"
          />

          <line
            x1={canvasW * 0.5}
            y1="0"
            x2={canvasW * 0.5}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.08"
          />

          <line
            x1={canvasW * 0.75}
            y1="0"
            x2={canvasW * 0.75}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.08"
          />

          {/* Underwater Subsurface Keel Silhouette */}
          <path
            d={shapeFunction(
              canvasW,
              underwaterH
            )}
            transform={`translate(0, ${waterlineY})`}
            fill="#00e5ff"
            opacity={underwaterOpacity}
            style={{
              filter: "drop-shadow(0 0 8px rgba(0,229,255,0.75))",
            }}
          />

          {/* Underwater center line */}
          <line
            x1={canvasW / 2}
            y1={waterlineY}
            x2={canvasW / 2}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.2"
            strokeDasharray="2,3"
          />

          {/* Above-Water Surface Sail Silhouette */}
          <path
            d={shapeFunction(
              canvasW,
              waterlineY
            )}
            fill="#ffffff"
            style={{
              filter: "drop-shadow(0 0 4px rgba(255,255,255,0.8))",
            }}
          />

          {/* Waterline */}
          <line
            x1="0"
            y1={waterlineY}
            x2={canvasW}
            y2={waterlineY}
            stroke="#ffffff"
            strokeOpacity="0.85"
            strokeDasharray="4,3"
          />

          {/* Waterline label */}
          <text
            x="4"
            y={waterlineY - 4}
            fill="#8ffcff"
            fontSize="6"
            fontFamily="monospace"
            fontWeight="bold"
          >
            WATERLINE (0m)
          </text>

          {/* Subsurface Keel Label */}
          <text
            x="4"
            y={totalH - 6}
            fill="#00e5ff"
            fontSize="5.5"
            fontFamily="monospace"
            opacity="0.85"
          >
            KEEL DRAFT: -{draftH.toFixed(0)}m
          </text>
        </svg>
      </div>

      <div className="profile-ratio">
        <span>HEIGHT : DRAFT</span>
        <strong>{ratio}</strong>
      </div>

      <div className="iceberg-caption">
        <div className="iceberg-id">
          {berg.id ?? berg.iceberg_id}
        </div>

        <div>
          Shape:{" "}
          <strong>
            {shape.toUpperCase()}
          </strong>
        </div>

        <div>
          Visible Freeboard: <strong>{freeboardH.toFixed(1)}m</strong>
        </div>

        <div>
          Subsurface Draft:{" "}
          <strong className="cyan-text">{draftH.toFixed(1)}m</strong>
        </div>

        <div>
          Confidence:{" "}
          <span className="cyan-text">
            {confidenceLabel} ({Math.round(confidence * 100)}%)
          </span>
        </div>

        <div>
          Detection: {sourceText}
        </div>
      </div>
    </div>
  );
}

export default IcebergProfile;
