import { useState } from "react";
import IcebergProfile from "./IcebergProfile";
import "./hazardPanel.css";

export const REVEAL_TRIGGER_KM = 8;

function HazardPanel({
  ship,
  gpsFix,
  distanceKm,
  routeStatus,
  nearbyIcebergs,
  closestIcebergId,
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const safeShip = ship || {};

  const lat = Number(safeShip.lat ?? safeShip.latitude);
  const lon = Number(safeShip.lon ?? safeShip.longitude);
  const speed = Number(safeShip.speed_knots);
  const heading = Number(
    safeShip.heading_deg ?? safeShip.heading ?? safeShip.heading_degrees
  );

  const validLat = Number.isFinite(lat) ? lat : -62.50;
  const validLon = Number.isFinite(lon) ? lon : -60.50;
  const validSpeed = Number.isFinite(speed) ? speed : 12.4;
  const validHeading = Number.isFinite(heading) ? heading : 135.0;

  const inWarningArea =
    Number.isFinite(distanceKm) &&
    distanceKm <= REVEAL_TRIGGER_KM;

  if (isCollapsed) {
    return (
      <div className="hazard-panel collapsed" onClick={() => setIsCollapsed(false)}>
        <div className="collapsed-pill">
          <span className="pill-dot" />
          <span className="pill-title">NAV TELEMETRY</span>
          <span className="pill-val">{validSpeed.toFixed(1)} kn</span>
          <span className="pill-val">{validHeading.toFixed(0)}°</span>
          <span className="pill-expand">▼ Open</span>
        </div>
      </div>
    );
  }

  return (
    <div className="hazard-panel">
      <div className="panel-header" onClick={() => setIsCollapsed(!isCollapsed)}>
        <div>
          <div className="panel-title">ANTARCTIC NAVIGATION</div>
          <div className="panel-subtitle">LIVE NMEA & SONAR TRACK</div>
        </div>
        <button
          className="panel-collapse-btn"
          onClick={(e) => {
            e.stopPropagation();
            setIsCollapsed(true);
          }}
          title="Minimize Panel"
        >
          ▲ Minimize
        </button>
      </div>

      <div className="telemetry-block">
        <div className="tele-row">
          <span className="tele-lbl">GPS</span>
          <span className={gpsFix ? "telemetry-good" : "telemetry-warning"}>
            {gpsFix ? "FIX" : "NO FIX"}
          </span>
        </div>
        <div className="tele-row">
          <span className="tele-lbl">LAT</span>
          <span>{validLat.toFixed(4)}°</span>
        </div>
        <div className="tele-row">
          <span className="tele-lbl">LON</span>
          <span>{validLon.toFixed(4)}°</span>
        </div>
        <div className="tele-row">
          <span className="tele-lbl">SPEED</span>
          <span>{validSpeed.toFixed(1)} kn</span>
        </div>
        <div className="tele-row">
          <span className="tele-lbl">COURSE</span>
          <span>{validHeading.toFixed(0)}°</span>
        </div>
      </div>

      <div className="hazard-block">
        <div className="hazard-row">
          <span className="hazard-lbl">HAZARD DIST</span>
          <span className={inWarningArea ? "distance-warning" : "distance-good"}>
            {Number.isFinite(distanceKm) ? `${distanceKm.toFixed(1)} km` : "—"}
          </span>
        </div>
        <div className="hazard-row">
          <span className="hazard-lbl">ROUTE</span>
          <span className="route-status">{routeStatus}</span>
        </div>
      </div>

      {inWarningArea && (
        <div className="alert-banner">
          ⚠ WARNING: {routeStatus}
        </div>
      )}

      <div className="iceberg-gallery">
        <div className="gallery-title">
          <span>ICEBERG PROFILES</span>
          <span className="sub-tag">SONAR X-RAY</span>
        </div>

        {nearbyIcebergs.length === 0 ? (
          <div className="no-hazards">NO ICEBERGS WITHIN 50 KM</div>
        ) : (
          <div className="gallery-grid">
            {nearbyIcebergs.map((berg) => (
              <IcebergProfile
                key={berg.id ?? berg.iceberg_id}
                berg={berg}
                highlighted={(berg.id ?? berg.iceberg_id) === closestIcebergId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default HazardPanel;
