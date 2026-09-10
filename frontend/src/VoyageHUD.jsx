import { useState } from "react";
import "./voyageHUD.css";

function VoyageHUD({
  activeRoute,
  isVoyaging,
  voyageProgress,
  speedMultiplier,
  followCamera,
  currentSpeedKnots = 14.5,
  currentHeading = 125,
  currentLeg = "WP-0 → WP-1",
  remainingDistKm = 0,
  activeAlertIceberg = null,
  alertETA = null,
  isDeterring = false,
  deterOffsetKm = 0,
  deterDirection = "STARBOARD",
  onTogglePlay,
  onReset,
  onProgressScrub,
  onSetSpeed,
  onToggleFollowCamera,
}) {
  const [isMinimized, setIsMinimized] = useState(false);

  if (!activeRoute || !activeRoute.points || activeRoute.points.length === 0) {
    return null;
  }

  const progressPercent = Math.min(100, Math.max(0, Math.round(voyageProgress * 100)));
  const isCompleted = voyageProgress >= 0.999;

  const handleProgressBarClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const newProgress = Math.max(0, Math.min(1, clickX / rect.width));
    if (onProgressScrub) {
      onProgressScrub(newProgress);
    }
  };

  const getCompassDirection = (deg) => {
    const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    const index = Math.round(deg / 45) % 8;
    return directions[index];
  };

  return (
    <div className={`voyage-hud-container ${isMinimized ? "minimized" : ""}`}>
      {/* Header Row */}
      <div className="voyage-hud-header">
        <div className="hud-title-group">
          <span className="hud-ship-icon">🚢</span>
          <span className="hud-ship-name">MV VASILIY GOLOVNIN</span>
          <span
            className={`hud-status-badge ${
              isCompleted
                ? "arrived"
                : isDeterring
                ? "deterring"
                : isVoyaging
                ? "sailing"
                : voyageProgress > 0
                ? "paused"
                : "sailing"
            }`}
          >
            <span className="pulse-dot"></span>
            {isCompleted
              ? "ARRIVED AT DESTINATION"
              : isDeterring
              ? `⚡ DETERRING AROUND ICEBERG (+${deterOffsetKm.toFixed(1)}km)`
              : isVoyaging
              ? "SAILING ON FAIRWAY"
              : voyageProgress > 0
              ? "VOYAGE PAUSED"
              : "READY TO SAIL"}
          </span>
        </div>

        {!isMinimized && (
          <div className="hud-telemetry-pills">
            <div className="hud-pill">
              SPEED: <span className="val">{currentSpeedKnots.toFixed(1)} KN</span>
            </div>
            <div className="hud-pill">
              HEADING: <span className="val">{Math.round(currentHeading)}° {getCompassDirection(currentHeading)}</span>
            </div>
            <div className="hud-pill">
              LEG: <span className="val">{currentLeg}</span>
            </div>
          </div>
        )}

        <button
          className="hud-min-toggle"
          onClick={() => setIsMinimized(!isMinimized)}
          title={isMinimized ? "Expand Nav HUD" : "Minimize Nav HUD"}
        >
          {isMinimized ? "▲ Expand" : "▼"}
        </button>
      </div>

      {!isMinimized && (
        <>
          {/* Proximity Warning & Deterrence HUD Strip */}
          {activeAlertIceberg && alertETA && (
            <div className="hud-48h-warning-strip">
              <div className="warning-strip-left">
                <span className="hud-warn-badge">⚠️ PROXIMITY ALERT</span>
                <span className="hud-warn-text">
                  ICEBERG <strong>{activeAlertIceberg.id}</strong> NEARBY ON ROUTE
                </span>
                <span className="hud-warn-eta">
                  ETA: {alertETA.formattedETA || `${Math.round(alertETA.hours * 60)} min`} ({alertETA.distanceKm.toFixed(1)} km)
                </span>
              </div>
              <div className="warning-strip-right">
                {isDeterring ? (
                  <span className="hud-deter-active">
                    ⚡ DETERRING +{deterOffsetKm.toFixed(1)} KM {deterDirection}
                  </span>
                ) : (
                  <span className="hud-deter-standby">
                    🛡️ COLLISION DETERRENCE ARMED
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Interactive Progress Track */}
          <div className="voyage-progress-section">
            <div className="voyage-progress-bar-wrap" onClick={handleProgressBarClick} title="Click to scrub voyage position">
              <div
                className="voyage-progress-fill"
                style={{ width: `${progressPercent}%` }}
              ></div>
            </div>
            <div className="voyage-progress-meta">
              <span>{currentLeg} ({progressPercent}% Completed)</span>
              <span>{remainingDistKm > 0 ? `${remainingDistKm.toFixed(1)} km remaining` : "Destination Reached"}</span>
            </div>
          </div>

          {/* Control Buttons */}
          <div className="voyage-hud-controls">
            <div className="controls-left">
              <button
                className={`hud-btn primary ${isVoyaging ? "active" : ""}`}
                onClick={onTogglePlay}
              >
                {isCompleted ? "🔄 Sail Again" : isVoyaging ? "⏸ Pause" : "▶ Sail Route"}
              </button>
              <button className="hud-btn" onClick={onReset} title="Reset vessel to starting position">
                ⏮ Start
              </button>

              {/* Speed Multiplier calibrated for Hackathon Presentation */}
              <div className="speed-group">
                <span className="speed-tag">SPEED:</span>
                {[0.5, 1, 1.5, 2.5].map((s) => (
                  <button
                    key={s}
                    className={`speed-btn ${speedMultiplier === s ? "selected" : ""}`}
                    onClick={() => onSetSpeed(s)}
                    title={s === 1 ? "1x Hackathon Presentation Pace (~90s)" : `${s}x Speed`}
                  >
                    {s === 1 ? "1x (Normal)" : `${s}x`}
                  </button>
                ))}
              </div>
            </div>

            <div className="controls-right">
              {/* Third-Person Camera Tracking Toggle */}
              <button
                className={`hud-btn ${followCamera ? "active" : ""}`}
                onClick={onToggleFollowCamera}
                title="Third-Person perspective overlooking the ship and fairway ahead"
              >
                🎥 {followCamera ? "3rd Person Tracking ON" : "Tactical Overview"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default VoyageHUD;
