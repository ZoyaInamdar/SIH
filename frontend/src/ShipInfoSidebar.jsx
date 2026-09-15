import React, { useState } from "react";
import CircularGauge from "./CircularGauge";

function ShipInfoSidebar({
  isOpen = false,
  onClose,
  ship,
  gpsFix = true,
  activeRoute,
  isVoyaging = false,
  voyageProgress = 0,
  speedMultiplier = 1,
  followCamera = false,
  voyageLeg = "WP-2 → WP-3",
  remainingDistKm = 119.3,
  onTogglePlay,
  onReset,
  onProgressScrub,
  onSetSpeed,
  onToggleFollowCamera,
  onRouteCalculated,
  vesselMetrics = null,
  riskMetrics = null,
  routeMetrics = null,
  backendUrl = "http://127.0.0.1:8000"
}) {
  const [showPlanner, setShowPlanner] = useState(false);
  const [showWaypoints, setShowWaypoints] = useState(false);

  // Inline Route Planning State
  const [startLat, setStartLat] = useState("-62.8800");
  const [startLon, setStartLon] = useState("-60.5000");
  const [destLat, setDestLat] = useState("-62.8000");
  const [destLon, setDestLon] = useState("-58.8000");
  const [isCalculating, setIsCalculating] = useState(false);
  const [routeResult, setRouteResult] = useState(null);

  const PRESETS = [
    { name: "Bransfield Deep Fairway", sLat: -62.88, sLon: -60.80, dLat: -62.80, dLon: -58.50 },
    { name: "Drake Passage → Channel", sLat: -62.44, sLon: -60.50, dLat: -62.80, dLon: -58.78 },
    { name: "King George → Iceberg Alley", sLat: -62.15, sLon: -58.40, dLat: -62.70, dLon: -59.80 }
  ];

  const handleApplyPreset = (p) => {
    setStartLat(p.sLat.toFixed(4));
    setStartLon(p.sLon.toFixed(4));
    setDestLat(p.dLat.toFixed(4));
    setDestLon(p.dLon.toFixed(4));
    setRouteResult(null);
  };

  const handleSyncVesselPos = () => {
    if (ship) {
      const lat = Number(ship.lat ?? ship.latitude ?? -62.82);
      const lon = Number(ship.lon ?? ship.longitude ?? -60.46);
      setStartLat(lat.toFixed(4));
      setStartLon(lon.toFixed(4));
    }
  };

  const handleCalculateRoute = async () => {
    setIsCalculating(true);
    try {
      const payload = {
        start_latitude: parseFloat(startLat),
        start_longitude: parseFloat(startLon),
        destination_latitude: parseFloat(destLat),
        destination_longitude: parseFloat(destLon),
        vessel_id: "MV-VG-001"
      };
      const res = await fetch(`${backendUrl}/routes/calculate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        setRouteResult(data);
        if (onRouteCalculated) onRouteCalculated(data.fuel_efficient_route || data);
      }
    } catch (err) {
      console.warn("Route calc error", err);
    } finally {
      setIsCalculating(false);
    }
  };

  const sogKnots = Number(ship?.speed_knots ?? 14.5);
  const headingDeg = Number(ship?.heading ?? ship?.heading_deg ?? 75);
  const progressPercent = Math.min(100, Math.max(0, Math.round(voyageProgress * 100)));

  // Real backend-backed propulsion metrics: dynamically tracking vessel speed & ice resistance
  const shaftRpm = vesselMetrics?.shaft_rpm ?? Math.round(45.0 + (sogKnots / 14.5) * 68.0);
  const powerKw = vesselMetrics?.power_required_kw ?? 6166;
  const resistanceKn = vesselMetrics?.channel_resistance_kn ?? 492.0;
  const loadPercent = vesselMetrics?.actual_load_percent ?? Math.round(28.0 + (sogKnots / 14.5) * 46.0);

  const etaDisplay = routeMetrics?.etaHours ? `~${routeMetrics.etaHours} hrs` : "~7.8 hrs";
  const distDisplay = routeMetrics?.distanceKm ? `${routeMetrics.distanceKm.toFixed(1)} km` : (remainingDistKm > 0 ? `${remainingDistKm.toFixed(1)} km` : "197.6 km");
  const fuelDisplay = routeMetrics?.fuelSavedPercent ? `+${routeMetrics.fuelSavedPercent}%` : "+18.7%";
  const riskDisplay = `${riskMetrics?.operationalRisk || "SAFE"} (RIO ${riskMetrics?.polarisRio != null ? (riskMetrics.polarisRio > 0 ? `+${riskMetrics.polarisRio}` : riskMetrics.polarisRio) : "+14"})`;

  return (
    <aside className={`maritime-sidebar left-sidebar ${isOpen ? "open" : ""}`} id="sidebar-ship-info">
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <div className="sidebar-title-group">
          <h2 className="sidebar-title">Ship Info.</h2>
        </div>
        <button className="sidebar-close-btn" onClick={onClose} title="Close Sidebar">
          ✕
        </button>
      </div>

      <div className="sidebar-scrollable-content">
        {/* Primary Simulation CTA Button (Matching Reference Image) */}
        <div className="sim-cta-wrap">
          <button
            className={`btn-simulate-nav ${isVoyaging ? "active" : ""}`}
            onClick={onTogglePlay}
            id="btn-simulate-nav"
          >
            <span className="sim-icon">{isVoyaging ? "⏸" : "▶"}</span>
            <span>{isVoyaging ? "Pause Navigation" : "Simulate Navigation"}</span>
          </button>
        </div>

        {/* Navigation Progress Scrub Bar */}
        <div className="sim-scrub-section">
          <div
            className="sim-progress-track"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const p = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
              if (onProgressScrub) onProgressScrub(p);
            }}
          >
            <div className="sim-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <div className="sim-progress-meta">
            <span>{voyageLeg} ({progressPercent}%)</span>
            <span>{remainingDistKm > 0 ? `${remainingDistKm.toFixed(1)} km left` : "Reached"}</span>
          </div>
          <div className="sim-rate-row">
            <span className="rate-lbl">PACE:</span>
            {[0.5, 1, 1.5, 2.5].map((s) => (
              <button
                key={s}
                className={`rate-btn ${speedMultiplier === s ? "active" : ""}`}
                onClick={() => onSetSpeed(s)}
              >
                {s}x
              </button>
            ))}
            <button
              className={`rate-btn follow-cam ${followCamera ? "active" : ""}`}
              onClick={onToggleFollowCamera}
              title="Camera follows vessel"
            >
              Follow
            </button>
            <button className="rate-btn reset-btn" onClick={onReset} title="Reset vessel">
              ⏮ Reset
            </button>
          </div>
        </div>

        {/* Vessel Specifications Table (Matching Reference Image) */}
        <div className="sidebar-card vessel-spec-card">
          <div className="spec-row">
            <span className="spec-label">Ship Name</span>
            <span className="spec-val bold">MV VASILIY GOLOVNIN</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">IMO / Callsign</span>
            <span className="spec-val mono">8603418 / UBUT</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Static Draft</span>
            <span className="spec-val mono">8.5 m</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Ice Class</span>
            <span className="spec-val badge-ice">Arc5 / PC4 (ULA)</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Channel Resist.</span>
            <span className="spec-val mono text-cyan">{resistanceKn} kN</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Shaft RPM / Power</span>
            <span className="spec-val mono text-cyan">{shaftRpm} RPM ({powerKw.toLocaleString()} kW)</span>
          </div>
        </div>

        {/* Voyage & Fairway Navigation Block (Matching Reference Image) */}
        <div className="sidebar-card voyage-route-card">
          <div className="route-header-row">
            <span className="card-badge green">FUEL FAIRWAY OPTIMAL</span>
            <span className="gps-indicator">{gpsFix ? "● DGPS FIX" : "○ SEARCHING"}</span>
          </div>

          <div className="port-leg-group">
            <div className="port-field">
              <span className="port-label">Departure</span>
              <div className="port-box">Drake Passage Fairway</div>
            </div>
            <div className="port-arrow">↓</div>
            <div className="port-field">
              <span className="port-label">Arrival</span>
              <div className="port-box">Bharati Station (Antarctic)</div>
            </div>
          </div>

          <div className="voyage-stats-grid">
            <div className="stat-box">
              <span className="stat-label">ETA</span>
              <span className="stat-num text-cyan">{etaDisplay}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Distance</span>
              <span className="stat-num text-white">{distDisplay}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Fuel Saved</span>
              <span className="stat-num text-green">{fuelDisplay}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Polar Risk</span>
              <span className="stat-num text-green">{riskDisplay}</span>
            </div>
          </div>

          {/* Action Buttons: Plan Route & Waypoint RTZ (Matching Reference Image) */}
          <div className="route-action-buttons">
            <button
              className={`btn-sub-action ${showPlanner ? "active" : ""}`}
              onClick={() => {
                setShowPlanner(!showPlanner);
                setShowWaypoints(false);
              }}
            >
              {showPlanner ? "Close Planner" : "Voyage Planning"}
            </button>
            <button
              className={`btn-sub-action ${showWaypoints ? "active" : ""}`}
              onClick={() => {
                setShowWaypoints(!showWaypoints);
                setShowPlanner(false);
              }}
            >
              Waypoints
            </button>
          </div>
        </div>

        {/* Collapsible Inline Route Planner Drawer */}
        {showPlanner && (
          <div className="sidebar-drawer-card planner-drawer">
            <div className="drawer-title">A* Environmental Route Planner</div>

            <div className="quick-presets-row">
              {PRESETS.map((p, idx) => (
                <button key={idx} className="preset-pill" onClick={() => handleApplyPreset(p)}>
                  {p.name.split("→")[0]}
                </button>
              ))}
            </div>

            <div className="coord-inputs-grid">
              <div className="coord-col">
                <div className="coord-hdr">
                  <span>START</span>
                  <button className="sync-btn" onClick={handleSyncVesselPos}>Sync Vessel</button>
                </div>
                <input
                  className="coord-in"
                  value={startLat}
                  onChange={(e) => setStartLat(e.target.value)}
                  placeholder="Lat"
                />
                <input
                  className="coord-in"
                  value={startLon}
                  onChange={(e) => setStartLon(e.target.value)}
                  placeholder="Lon"
                />
              </div>
              <div className="coord-col">
                <div className="coord-hdr">
                  <span>DESTINATION</span>
                </div>
                <input
                  className="coord-in"
                  value={destLat}
                  onChange={(e) => setDestLat(e.target.value)}
                  placeholder="Lat"
                />
                <input
                  className="coord-in"
                  value={destLon}
                  onChange={(e) => setDestLon(e.target.value)}
                  placeholder="Lon"
                />
              </div>
            </div>

            <button
              className="btn-compute-route"
              onClick={handleCalculateRoute}
              disabled={isCalculating}
            >
              {isCalculating ? "Calculating Optimal A*..." : "Calculate Fuel-Efficient Route"}
            </button>

            {routeResult && (
              <div className="route-calc-result">
                <div className="result-metric">
                  <span className="lbl">Fairway Distance:</span>
                  <span className="val text-cyan">{routeResult.fuel_efficient_route?.distance_km} km</span>
                </div>
                <div className="result-metric">
                  <span className="lbl">Fuel Savings:</span>
                  <span className="val text-green">+{routeResult.fuel_saved_percent}%</span>
                </div>
                <button
                  className="btn-apply-route"
                  onClick={() => {
                    if (onRouteCalculated && routeResult.fuel_efficient_route) {
                      onRouteCalculated(routeResult.fuel_efficient_route);
                    }
                  }}
                >
                  Engage Fairway in 3D
                </button>
              </div>
            )}
          </div>
        )}

        {/* Collapsible Waypoint List */}
        {showWaypoints && (
          <div className="sidebar-drawer-card waypoints-drawer">
            <div className="drawer-title">ECDIS RTZ Fairway Waypoints</div>
            <div className="waypoints-table-wrap">
              <table className="wp-table">
                <thead>
                  <tr>
                    <th>WP</th>
                    <th>LAT</th>
                    <th>LON</th>
                    <th>ZONE</th>
                  </tr>
                </thead>
                <tbody>
                  {(activeRoute?.points || []).map((pt, idx) => (
                    <tr key={idx}>
                      <td>WP-{idx + 1}</td>
                      <td>{(pt.latitude ?? pt.lat)?.toFixed(3)}°</td>
                      <td>{(pt.longitude ?? pt.lon)?.toFixed(3)}°</td>
                      <td className="text-green">OPEN WATER</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Telemetry Readout Strip */}
        <div className="sidebar-card telemetry-metrics-strip">
          <div className="tele-item">
            <span className="tele-lbl">Heading</span>
            <span className="tele-val">{Math.round(headingDeg)}°</span>
          </div>
          <div className="tele-item">
            <span className="tele-lbl">Depth / UKC</span>
            <span className="tele-val text-cyan">165 m</span>
          </div>
          <div className="tele-item">
            <span className="tele-lbl">Status</span>
            <span className="tele-val text-green">{isVoyaging ? "UNDERWAY" : "NOMINAL"}</span>
          </div>
        </div>

        {/* Circular Gauges Row (Matching Reference Image: RPM & SOG) */}
        <div className="sidebar-gauges-row">
          <div className="gauge-card-wrap">
            <CircularGauge
              label="Shaft RPM"
              value={shaftRpm}
              unit="RPM"
              min={0}
              max={150}
              color="#B8944A"
              size={120}
              subLabel={`${loadPercent}% LOAD`}
            />
          </div>
          <div className="gauge-card-wrap">
            <CircularGauge
              label="SOG"
              value={sogKnots}
              unit="KTS"
              min={0}
              max={35}
              color="#5B9B6F"
              size={120}
              subLabel="SPEED OVER GROUND"
            />
          </div>
        </div>
      </div>
    </aside>
  );
}

export default React.memo(ShipInfoSidebar);
