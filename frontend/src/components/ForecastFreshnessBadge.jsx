import React, { useState, useEffect } from "react";
import "./forecastFreshnessBadge.css";

/**
 * ForecastFreshnessBadge
 * Reads last_updated from whichever data object is currently displayed.
 * Does NOT recompute or estimate this value, only displays what already exists.
 * Follows the confirmed 72-hour staleness rule.
 */
export default function ForecastFreshnessBadge({
  lastUpdatedTimestamp,
  dataLayerName = "ENVIRONMENTAL & ICE DATA",
  isSimulatedOffline = false,
  onPrepareBundleClick = null,
}) {
  const [now, setNow] = useState(Date.now());
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  // Live timer to keep age fresh without altering data
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15000);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      clearInterval(timer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  if (!lastUpdatedTimestamp) {
    return (
      <div className="freshness-badge stale">
        <span className="freshness-dot pulse-amber" />
        <span className="layer-name">{dataLayerName}</span>
        <span className="timestamp">Last updated: UNKNOWN / CACHED</span>
        <span className="age">(No timestamp — STALE, use caution)</span>
      </div>
    );
  }

  const updatedDate = new Date(lastUpdatedTimestamp);
  const validDate = isNaN(updatedDate.getTime()) ? new Date() : updatedDate;
  const ageHours = Math.max(0, (now - validDate.getTime()) / 3600000);
  const isStale = ageHours > 72; // Strict 72-hour confirmed rule

  const effectivelyOffline = isSimulatedOffline || !isOnline;

  return (
    <div
      className={`freshness-badge ${isStale ? "stale" : "fresh"} ${
        effectivelyOffline ? "offline-mode" : "online-mode"
      }`}
      id="forecast-freshness-badge"
    >
      <div className="freshness-left">
        <span
          className={`freshness-dot ${
            isStale ? "pulse-amber" : "pulse-green"
          }`}
        />
        <span className="layer-name">{dataLayerName}</span>
        <span className="mode-pill">
          {effectivelyOffline ? "LOCAL DB / OFFLINE" : "SYNCED"}
        </span>
      </div>

      <div className="freshness-center">
        <span className="timestamp">
          Last updated: {validDate.toLocaleString()}
        </span>
        <span className={`age ${isStale ? "text-amber" : "text-cyan"}`}>
          ({ageHours < 1 ? "<1h" : `${ageHours.toFixed(1)}h`} ago
          {isStale ? " — STALE_WARNING, use caution" : ""})
        </span>
      </div>

      {onPrepareBundleClick && (
        <button
          className="btn-bundle-quick-launch"
          onClick={onPrepareBundleClick}
          title="Open Pre-Departure Voyage Bundle Manager"
        >
          VOYAGE BUNDLE
        </button>
      )}
    </div>
  );
}
