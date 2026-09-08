import { SHAPE_TEMPLATES } from "./icebergShapes";
import "./hazardPanel.css";

function IcebergProfile({ berg, highlighted = false }) {
  const shape =
    berg.shape_class in SHAPE_TEMPLATES
      ? berg.shape_class
      : "tabular";

  const freeboardH = Number(berg.estimated_freeboard_m ?? berg.freeboard_m) || 35;
  const draftH = Number(berg.estimated_draft_m) || 100;
  const confidence = Math.max(
    0,
    Math.min(1, Number(berg.draft_confidence ?? berg.confidence ?? 0.8))
  );

  const totalH = 200;
  const canvasW = 120;

  const waterlineY =
    totalH * (freeboardH / (freeboardH + draftH));

  const underwaterH = totalH - waterlineY;

  const underwaterOpacity =
    0.15 + confidence * 0.5;

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

  return (
    <div
      className={`iceberg-profile-card ${
        highlighted ? "highlighted" : ""
      }`}
    >
      <div className="profile-status">
        <span
          className={
            highlighted
              ? "status-dot active"
              : "status-dot"
          }
        />

        {highlighted
          ? "CLOSEST HAZARD"
          : "STRUCTURE PROFILE"}
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
            strokeOpacity="0.12"
          />

          <line
            x1={canvasW * 0.25}
            y1="0"
            x2={canvasW * 0.25}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.06"
          />

          <line
            x1={canvasW * 0.5}
            y1="0"
            x2={canvasW * 0.5}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.06"
          />

          <line
            x1={canvasW * 0.75}
            y1="0"
            x2={canvasW * 0.75}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.06"
          />

          {/* Underwater silhouette */}
          <path
            d={SHAPE_TEMPLATES[shape](
              canvasW,
              underwaterH
            )}
            transform={`translate(0, ${waterlineY})`}
            fill="#00e5ff"
            opacity={underwaterOpacity}
            style={{
              filter:
                "drop-shadow(0 0 7px rgba(0,229,255,0.7))",
            }}
          />

          {/* Underwater center line */}
          <line
            x1={canvasW / 2}
            y1={waterlineY}
            x2={canvasW / 2}
            y2={totalH}
            stroke="#00e5ff"
            strokeOpacity="0.15"
            strokeDasharray="2,3"
          />

          {/* Surface silhouette */}
          <path
            d={SHAPE_TEMPLATES[shape](
              canvasW,
              waterlineY
            )}
            fill="#ffffff"
          />

          {/* Waterline */}
          <line
            x1="0"
            y1={waterlineY}
            x2={canvasW}
            y2={waterlineY}
            stroke="#ffffff"
            strokeOpacity="0.8"
            strokeDasharray="4,3"
          />

          {/* Waterline label */}
          <text
            x="4"
            y={waterlineY - 4}
            fill="#8ffcff"
            fontSize="5"
            fontFamily="monospace"
          >
            WATERLINE
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
          Freeboard: {freeboardH.toFixed(1)}m
        </div>

        <div>
          Draft:{" "}
          <strong>{draftH.toFixed(1)}m</strong>
        </div>

        <div>
          Confidence:{" "}
          <span className="cyan-text">
            {confidenceLabel}
          </span>
        </div>

        <div>
          Source: {sourceText}
        </div>
      </div>
    </div>
  );
}

export default IcebergProfile;
