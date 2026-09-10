import { useState } from "react";
import IcebergProfile from "./IcebergProfile";
import "./hazardPanel.css";

export const REVEAL_TRIGGER_KM = 8;

function HazardPanel({
  ship,
  gpsFix,
  distanceKm,
  routeStatus,
  nearbyIcebergs = [],
  closestIcebergId,
  activeAlertIceberg = null,
  alertETA = null,
  routeHazardIcebergs = [],
  isDeterring = false,
  deterOffsetKm = 0,
  deterDirection = "STARBOARD",
  deterTarget = null,
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
          {activeAlertIceberg && (
            <span className="alert-badge-red" style={{ marginLeft: 4 }}>
              🚨 NEARBY ALERT
            </span>
          )}
          <span className="pill-expand">▼ Open</span>
        </div>
      </div>
    );
  }

  // Combine active alert iceberg with gallery list without duplicates
  const otherIcebergs = nearbyIcebergs.filter(
    (b) => (b.id ?? b.iceberg_id) !== (activeAlertIceberg?.id ?? activeAlertIceberg?.iceberg_id)
  );

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
          <span className={activeAlertIceberg ? "distance-warning" : inWarningArea ? "distance-warning" : "distance-good"}>
            {Number.isFinite(distanceKm) ? `${distanceKm.toFixed(1)} km` : "—"}
          </span>
        </div>
        <div className="hazard-row">
          <span className="hazard-lbl">ROUTE</span>
          <span className="route-status">{routeStatus}</span>
        </div>
      </div>

      {/* Nearby Early Warning Alert Card */}
      {activeAlertIceberg && alertETA && (
        <div className="two-day-alert-card pulse-danger">
          <div className="alert-card-header">
            <span className="alert-badge-red">🚨 WARNING: ICEBERG NEARBY AHEAD</span>
            <span className="alert-eta-chip">
              ETA: {alertETA.formattedETA || `${Math.round(alertETA.hours * 60)} min`}
            </span>
          </div>
          <div className="alert-card-body">
            <div className="alert-berg-name">
              <strong>{activeAlertIceberg.id}</strong>
              <span className="alert-route-tag">ON ROUTE HAZARD</span>
            </div>
            <div className="alert-metrics-grid">
              <div className="metric-col">
                <span className="metric-lbl">TIME TO INTERCEPT</span>
                <span className="metric-val text-cyan">
                  {alertETA.formattedETA || `${Math.round(alertETA.hours * 60)} min`}
                </span>
              </div>
              <div className="metric-col">
                <span className="metric-lbl">HAZARD STANDOFF</span>
                <span className="metric-val text-warning">
                  {alertETA.distanceKm.toFixed(1)} km
                </span>
              </div>
            </div>

            {/* Tactical Course Deterrence Status */}
            <div className="deterrence-status-box">
              <div className="deter-label">
                <span className="deter-dot"></span>
                <strong>TACTICAL COURSE DETERRENCE:</strong>
              </div>
              <div className="deter-val">
                {isDeterring ? (
                  <span className="text-warning font-bold">
                    ⚡ VEERING +{deterOffsetKm.toFixed(1)} KM {deterDirection} TO DETOUR AROUND {deterTarget || activeAlertIceberg.id}
                  </span>
                ) : (
                  <span className="text-cyan">
                    🛡️ ARMED: AUTOMATIC AVOIDANCE READY UPON INTERCEPT PROXIMITY
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {inWarningArea && !activeAlertIceberg && typeof routeStatus === "string" && routeStatus.startsWith("⚠️") && (
        <div className="alert-banner">
          ⚠ WARNING: {routeStatus}
        </div>
      )}

      <div className="iceberg-gallery">
        <div className="gallery-title">
          <span>ICEBERG PROFILES</span>
          <span className="sub-tag">ABOVE & BELOW WATER SONAR</span>
        </div>

        {/* Featured 2-Day Alerting Target */}
        {activeAlertIceberg && (
          <div style={{ marginBottom: 8 }}>
            <IcebergProfile
              key={`alert-${activeAlertIceberg.id}`}
              berg={activeAlertIceberg}
              highlighted={true}
              alertETA={alertETA}
              isOnRoute={true}
            />
          </div>
        )}

        {/* Other Detected Icebergs */}
        {otherIcebergs.length === 0 && !activeAlertIceberg ? (
          <div className="no-hazards">NO ICEBERGS WITHIN 50 KM</div>
        ) : (
          <div className="gallery-grid">
            {otherIcebergs.map((berg) => {
              const bId = berg.id ?? berg.iceberg_id;
              const isHazard = routeHazardIcebergs.some((rh) => (rh.id ?? rh.iceberg_id) === bId);
              return (
                <IcebergProfile
                  key={bId}
                  berg={berg}
                  highlighted={bId === closestIcebergId}
                  isOnRoute={isHazard}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default HazardPanel;
