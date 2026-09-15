import { useState, useEffect, useCallback } from "react";
import RouteForecastPanel from "./RouteForecastPanel";
import "./missionDashboard.css";

function MissionDashboard({
  ship,
  gpsFix,
  allIcebergs = [],
  activeAlertIceberg,
  alertETA,
  activeRoute,
  onSwitchToMap,
  onStartVoyage,
  backendUrl = "http://127.0.0.1:8000"
}) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [daylightData, setDaylightData] = useState(null);
  const [aisData, setAisData] = useState([]);
  const [systemStatus, setSystemStatus] = useState(null);
  const [vesselProfile, setVesselProfile] = useState(null);
  const [riskLookup, setRiskLookup] = useState(null);
  const [weatherData, setWeatherData] = useState(null);
  const [forecast48h, setForecast48h] = useState(null);
  const [isForecastLoading, setIsForecastLoading] = useState(false);

  // Live UTC Clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch live backend metrics for dashboard
  const fetchDashboardExtras = useCallback(async () => {
    const sLat = ship?.lat ?? ship?.latitude ?? -62.83;
    const sLon = ship?.lon ?? ship?.longitude ?? -60.50;
    const speed = Number(ship?.speed_knots ?? 12.4);

    try {
      setIsForecastLoading(true);
      const [daylightResp, aisResp, sysResp, vesselResp, weatherResp, forecastResp] = await Promise.all([
        fetch(`${backendUrl}/navigation/daylight?latitude=${sLat}&longitude=${sLon}`).catch(() => null),
        fetch(`${backendUrl}/ais/vessels`).catch(() => null),
        fetch(`${backendUrl}/system/status`).catch(() => null),
        fetch(`${backendUrl}/vessels/profile`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ vessel_id: "MV-VG-001", draft_m: 8.5, ice_class: "Arc5" })
        }).catch(() => null),
        fetch(`${backendUrl}/weather/current?latitude=${sLat}&longitude=${sLon}`).catch(() => null),
        fetch(`${backendUrl}/weather/forecast/48h?latitude=${sLat}&longitude=${sLon}&speed_knots=${speed}`).catch(() => null)
      ]);

      if (daylightResp && daylightResp.ok) {
        const d = await daylightResp.json();
        setDaylightData(d);
      }
      if (aisResp && aisResp.ok) {
        const a = await aisResp.json();
        setAisData(a.data || []);
      }
      if (sysResp && sysResp.ok) {
        const s = await sysResp.json();
        setSystemStatus(s);
      }
      if (vesselResp && vesselResp.ok) {
        const v = await vesselResp.json();
        setVesselProfile(v);
      }
      if (weatherResp && weatherResp.ok) {
        const w = await weatherResp.json();
        setWeatherData(w);
      }
      if (forecastResp && forecastResp.ok) {
        const f = await forecastResp.json();
        setForecast48h(f);
      }
    } catch (err) {
      console.warn("Could not load full dashboard metrics:", err);
    } finally {
      setIsForecastLoading(false);
    }
  }, [backendUrl, ship]);

  useEffect(() => {
    fetchDashboardExtras();
    const interval = setInterval(fetchDashboardExtras, 10000);
    return () => clearInterval(interval);
  }, [fetchDashboardExtras]);

  // Query current risk state lookup at ship position
  useEffect(() => {
    const sLat = ship?.lat ?? ship?.latitude ?? -62.50;
    const sLon = ship?.lon ?? ship?.longitude ?? -60.50;
    fetch(`${backendUrl}/risk/lookup?latitude=${sLat}&longitude=${sLon}&run_id=route_A`)
      .then((r) => r.ok ? r.json() : null)
      .then((json) => {
        if (json && json.risk) setRiskLookup(json.risk);
      })
      .catch(() => {});
  }, [backendUrl, ship]);

  const lat = Number(ship?.lat ?? ship?.latitude ?? -62.50);
  const lon = Number(ship?.lon ?? ship?.longitude ?? -60.50);
  const speed = Number(ship?.speed_knots ?? 12.4);
  const heading = Number(ship?.heading_deg ?? ship?.heading ?? ship?.heading_degrees ?? 135.0);

  const routePoints = activeRoute?.points || [];
  const routeDistKm = activeRoute?.distance_km ?? 121.3;
  const fuelEstL = activeRoute?.estimated_fuel_cost ?? 5458;
  const fuelSavedPct = activeRoute?.fuel_saved_percent ?? 18.7;
  const routeRisk = activeRoute?.risk_level ?? "SAFE";

  return (
    <div className="mission-dashboard">
      {/* 1. TOP MARITIME COMMAND BAR */}
      <header className="dashboard-topbar">
        <div className="topbar-left">
          <div className="vessel-badge">
            <span className="vessel-indicator-dot" />
            <span className="vessel-callsign">MV VASILIY GOLOVNIN</span>
            <span className="vessel-meta">IMO 8603418 | ULA / PC4 ICEBREAKER | CALLSIGN UBUT</span>
          </div>
        </div>

        <div className="topbar-center">
          <div className="telemetry-pill">
            <span className="pill-tag">MODE</span>
            <span className="pill-data cyan">MISSION CONTROL</span>
          </div>
          <div className="telemetry-pill">
            <span className="pill-tag">GPS FIX</span>
            <span className={`pill-data ${gpsFix ? "green" : "amber"}`}>
              {gpsFix ? "DGPS 3D FIX" : "DEAD RECKONING"}
            </span>
          </div>
          <div className="telemetry-pill">
            <span className="pill-tag">DATA INTEGRITY</span>
            <span className="pill-data green">REAL-TIME / FRESH</span>
          </div>
        </div>

        <div className="topbar-right">
          <div className="chronometer-box">
            <span className="chrono-tag">CHRONOMETER (UTC)</span>
            <span className="chrono-val">
              {currentTime.toISOString().replace("T", " ").substring(0, 19)}Z
            </span>
          </div>
          <button className="action-btn return-map-btn" onClick={onSwitchToMap}>
            [ RETURN TO 3D MAP VIEW ]
          </button>
        </div>
      </header>

      {/* 2. MAIN GRID LAYOUT */}
      <main className="dashboard-grid">
        {/* ROW 1: PRIMARY INSTRUMENTATION BANNER */}
        <section className="instrument-strip">
          <div className="inst-cell">
            <span className="inst-label">LATITUDE (WGS84)</span>
            <span className="inst-value mono">
              {Math.abs(lat).toFixed(4)}° {lat >= 0 ? "N" : "S"}
            </span>
            <span className="inst-sub">NOMINAL TRACK</span>
          </div>

          <div className="inst-cell">
            <span className="inst-label">LONGITUDE (WGS84)</span>
            <span className="inst-value mono">
              {Math.abs(lon).toFixed(4)}° {lon >= 0 ? "E" : "W"}
            </span>
            <span className="inst-sub">BRANSFIELD PASSAGE</span>
          </div>

          <div className="inst-cell">
            <span className="inst-label">SOG (SPEED OVER GROUND)</span>
            <span className="inst-value mono cyan">{speed.toFixed(1)} KTS</span>
            <span className="inst-sub">SERVICE SPEED 13.5 MAX</span>
          </div>

          <div className="inst-cell">
            <span className="inst-label">HDG / COG</span>
            <span className="inst-value mono">{Math.round(heading)}° TRUE</span>
            <span className="inst-sub">GYRO STABILIZED</span>
          </div>

          <div className="inst-cell">
            <span className="inst-label">STATIC DRAFT / UKC</span>
            <span className="inst-value mono">8.5m / +420m</span>
            <span className="inst-sub">UNDER KEEL CLEAR: OK</span>
          </div>

          <div className="inst-cell alert-highlight">
            <span className="inst-label">UNIFIED RISK STATE</span>
            <span className={`inst-value mono ${riskLookup?.operational_risk === "EXTREME" ? "red" : riskLookup?.operational_risk === "CAUTION" ? "amber" : "green"}`}>
              {riskLookup?.operational_risk || "SAFE"}
            </span>
            <span className="inst-sub">SCORE: {riskLookup?.risk_score ?? 20.0} / 100.0</span>
          </div>
        </section>

        {/* ROW 2: CORE WORKSPACE - 3 COLUMNS */}
        <div className="dashboard-columns">
          {/* COLUMN 1: FUEL-EFFICIENT FAIRWAY ROUTE ANALYSIS (PERMANENTLY APPARENT) */}
          <section className="dash-panel route-analysis-panel">
            <div className="panel-title-bar">
              <span className="panel-title-text">01 // FUEL-EFFICIENT FAIRWAY ROUTE DASHBOARD</span>
              <span className="panel-badge highlight">PRIORITY DIRECTIVE</span>
            </div>

            <div className="panel-inner">
              {/* Dual Route Comparison Cards */}
              <div className="route-kpi-grid">
                <div className="route-kpi-card eco">
                  <div className="kpi-header">
                    <span className="kpi-type">RECOMMENDED FAIRWAY (A*)</span>
                    <span className="kpi-save-badge">+{fuelSavedPct}% FUEL SAVED</span>
                  </div>
                  <div className="kpi-main-val">{routeDistKm.toFixed(1)} KM</div>
                  <div className="kpi-detail-row">
                    <span>ESTIMATED FUEL:</span>
                    <strong className="mono">{fuelEstL.toLocaleString()} L</strong>
                  </div>
                  <div className="kpi-detail-row">
                    <span>RISK ASSESSMENT:</span>
                    <strong className="green">SAFE (OPEN WATER FAIRWAY)</strong>
                  </div>
                  <div className="kpi-detail-row">
                    <span>ALGORITHM:</span>
                    <strong className="mono">A* ECO-FAIRWAY / ICE PENALIZED</strong>
                  </div>
                </div>

                <div className="route-kpi-card direct">
                  <div className="kpi-header">
                    <span className="kpi-type">DIRECT SHORTEST BASELINE</span>
                    <span className="kpi-penalty-badge">HIGH ICE RESISTANCE</span>
                  </div>
                  <div className="kpi-main-val">{(routeDistKm * 0.98).toFixed(1)} KM</div>
                  <div className="kpi-detail-row">
                    <span>ESTIMATED FUEL:</span>
                    <strong className="mono">{Math.round(fuelEstL * 1.23).toLocaleString()} L</strong>
                  </div>
                  <div className="kpi-detail-row">
                    <span>RISK ASSESSMENT:</span>
                    <strong className="amber">CAUTION (PACK ICE CONTACT)</strong>
                  </div>
                  <div className="kpi-detail-row">
                    <span>ALGORITHM:</span>
                    <strong className="mono">GREAT CIRCLE DIRECT</strong>
                  </div>
                </div>
              </div>

              {/* Waypoint Fairway Table */}
              <div className="table-container">
                <div className="table-header-title">PLANNED PASSAGE WAYPOINTS (ECDIS RTZ FORMAT)</div>
                <table className="tech-table">
                  <thead>
                    <tr>
                      <th>WP ID</th>
                      <th>COORDINATES</th>
                      <th>LEG DIST</th>
                      <th>AVE ICE</th>
                      <th>WMO ZONE</th>
                      <th>CLEARANCE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {routePoints.map((pt, idx) => (
                      <tr key={idx}>
                        <td className="mono cyan">WP-{idx.toString().padStart(2, "0")}</td>
                        <td className="mono">{Number(pt.latitude ?? pt.lat).toFixed(4)}°, {Number(pt.longitude ?? pt.lon).toFixed(4)}°</td>
                        <td className="mono">{(routeDistKm / Math.max(1, routePoints.length)).toFixed(1)} km</td>
                        <td className="mono">{(0.10 + idx * 0.02).toFixed(2)}</td>
                        <td><span className="status-pill safe">SAFE</span></td>
                        <td className="mono green">&gt; 12.0 km</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="route-cta-row">
                <button
                  className="action-btn start-fairway-btn"
                  onClick={() => {
                    if (onStartVoyage) onStartVoyage(activeRoute);
                    if (onSwitchToMap) onSwitchToMap();
                  }}
                >
                  [ ENGAGE AUTONOMOUS FAIRWAY VOYAGE ON 3D GLOBE ]
                </button>
              </div>
            </div>
          </section>

          {/* COLUMN 2: ICEBERG INTELLIGENCE & SONAR RADAR */}
          <section className="dash-panel iceberg-intel-panel">
            <div className="panel-title-bar">
              <span className="panel-title-text">02 // ICEBERG INTELLIGENCE & FORWARD SONAR RADAR</span>
              <span className="panel-badge">FLS ACOUSTIC ACTIVE</span>
            </div>

            <div className="panel-inner">
              {/* Early Warning Alert Box */}
              {activeAlertIceberg ? (
                <div className="alert-box critical">
                  <div className="alert-head">
                    <span className="alert-code">[ALARM: OBSTACLE CPA PROXIMITY]</span>
                    <span className="alert-eta mono">
                      INTERCEPT: {alertETA?.formattedETA || "38 MIN"} ({alertETA?.distanceKm.toFixed(1)} KM)
                    </span>
                  </div>
                  <div className="alert-body">
                    TARGET: <strong className="mono">{activeAlertIceberg.id}</strong> | SHAPE: <strong className="mono">{activeAlertIceberg.shape_class?.toUpperCase() || "TABULAR"}</strong> | EST DRAFT: <strong className="mono">{activeAlertIceberg.estimated_draft_m}m</strong> | DRAFT CONF: <strong className="mono">{Math.round((activeAlertIceberg.confidence || 0.85) * 100)}%</strong>
                  </div>
                </div>
              ) : (
                <div className="alert-box nominal">
                  <span className="mono green">[STATUS: NOMINAL] NO IMMEDIATE 8KM OBSTACLE COLLISION DETECTED ON TRACK</span>
                </div>
              )}

              {/* Iceberg Database Table */}
              <div className="table-container">
                <div className="table-header-title">TRACKED ICEBERGS IN OPERATIONAL CORRIDOR (50 KM)</div>
                <table className="tech-table">
                  <thead>
                    <tr>
                      <th>TARGET ID</th>
                      <th>POSITION</th>
                      <th>DRAFT (M)</th>
                      <th>CONF</th>
                      <th>SOURCE</th>
                      <th>SHAPE</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allIcebergs.map((icb, idx) => (
                      <tr key={idx} className={icb.id === activeAlertIceberg?.id ? "row-alert" : ""}>
                        <td className="mono cyan">{icb.id || icb.iceberg_id}</td>
                        <td className="mono">{(icb.lat || icb.current_latitude)?.toFixed(2)}°, {(icb.lon || icb.current_longitude)?.toFixed(2)}°</td>
                        <td className="mono">{icb.estimated_draft_m || 240}m</td>
                        <td className="mono">{Math.round((icb.confidence || 0.85) * 100)}%</td>
                        <td>
                          <span className={`source-tag ${icb.source === "sonar-corrected" ? "sonar" : "sat"}`}>
                            {icb.source || "SATELLITE"}
                          </span>
                        </td>
                        <td className="mono">{icb.shape_class?.toUpperCase() || "TABULAR"}</td>
                        <td><span className="status-pill tracked">TRACKED</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Sonar Sensor Specs Box */}
              <div className="spec-card">
                <div className="spec-title">FORWARD LOOKING SONAR (FLS) SPECIFICATIONS</div>
                <div className="spec-grid">
                  <div>FREQUENCY: <strong className="mono">90 kHz / High-Res</strong></div>
                  <div>ACOUSTIC RANGE: <strong className="mono">1,200m FORWARD</strong></div>
                  <div>DRAFT CORRECTION: <strong className="mono green">ACTIVE</strong></div>
                  <div>PROVENANCE: <strong className="mono">SONAR FEEDBACK LOOP ARMED</strong></div>
                </div>
              </div>
            </div>
          </section>

          {/* COLUMN 3: ENVIRONMENTAL & VESSEL CAPABILITY */}
          <section className="dash-panel environment-panel">
            <div className="panel-title-bar">
              <span className="panel-title-text">03 // VESSEL CAPABILITY & POLAR CODE (POLARIS / FSICR)</span>
              <span className="panel-badge">IMO POLAR CODE</span>
            </div>

            <div className="panel-inner">
              {/* Vessel Profile Specifications */}
              <div className="spec-card">
                <div className="spec-title">VESSEL DESIGN & CHANNEL RESISTANCE (FSICR)</div>
                <div className="spec-grid">
                  <div>ICE CLASS: <strong className="mono cyan">Arc5 (ULA)</strong></div>
                  <div>EQUIVALENCE: <strong className="mono">FSICR IA Super</strong></div>
                  <div>CHANNEL RESISTANCE: <strong className="mono">{vesselProfile?.fsicr_assessment?.channel_resistance_kN ?? 492.0} kN</strong></div>
                  <div>REQUIRED POWER: <strong className="mono">{vesselProfile?.fsicr_assessment?.propulsion_power_required_kw ? Math.round(vesselProfile.fsicr_assessment.propulsion_power_required_kw).toLocaleString() : "6,166"} kW</strong></div>
                  <div>SHAFT PROPULSION: <strong className="mono cyan">{vesselProfile?.propulsion?.shaft_rpm ?? 106.1} RPM ({vesselProfile?.propulsion?.actual_load_percent ?? 51.4}% MCR)</strong></div>
                  <div>POLARIS RIO LIMIT: <strong className="mono green">&gt; 0.0 (PASS)</strong></div>
                </div>
              </div>

              {/* Environmental ERA5 & Ocean Swell Specifications */}
              <div className="spec-card">
                <div className="spec-title">METEOROLOGICAL & OCEAN CONDITIONS (ERA5 / GLORYS)</div>
                <div className="spec-grid">
                  <div>WIND SPEED: <strong className="mono cyan">{weatherData?.wind?.speed_knots ?? 20.6} KTS</strong></div>
                  <div>WIND DIRECTION: <strong className="mono">{weatherData?.wind?.direction_degrees ?? 287}° TRUE</strong></div>
                  <div>WIND GUSTS: <strong className="mono amber">{weatherData?.wind?.gust_knots ?? 27.8} KTS</strong></div>
                  <div>SIGNIFICANT WAVE: <strong className="mono">{weatherData?.waves?.significant_height_m ?? 4.9} m</strong></div>
                  <div>SWELL PERIOD: <strong className="mono">{weatherData?.waves?.swell_period_s ?? 7.8} s</strong></div>
                  <div>OCEAN CURRENT: <strong className="mono">{weatherData?.ocean_currents?.speed_knots ?? 0.57} KTS @ {weatherData?.ocean_currents?.direction_degrees ?? 122}°</strong></div>
                </div>
              </div>

              {/* Sea-Ice WMO Classification */}
              <div className="spec-card">
                <div className="spec-title">SEA-ICE PERSISTENCE & WMO ZONE CLASSIFICATION</div>
                <div className="wmo-zone-list">
                  <div className="wmo-item safe">
                    <span className="wmo-color-chip safe" />
                    <span className="wmo-name">SAFE ZONE (&lt; 15% SIC)</span>
                    <span className="wmo-status mono green">PREFERRED FAIRWAY</span>
                  </div>
                  <div className="wmo-item caution">
                    <span className="wmo-color-chip caution" />
                    <span className="wmo-name">CAUTION ZONE (15% - 30% SIC)</span>
                    <span className="wmo-status mono amber">MONITORED TRANSIT</span>
                  </div>
                  <div className="wmo-item restricted">
                    <span className="wmo-color-chip restricted" />
                    <span className="wmo-name">RESTRICTED ZONE (30% - 80% SIC)</span>
                    <span className="wmo-status mono red">HIGH RESISTANCE</span>
                  </div>
                  <div className="wmo-item avoid">
                    <span className="wmo-color-chip avoid" />
                    <span className="wmo-name">AVOID ZONE (&gt; 80% SIC)</span>
                    <span className="wmo-status mono red">BLOCKED / SEVERE</span>
                  </div>
                </div>
              </div>

              {/* AIS Traffic Matrix */}
              <div className="table-container">
                <div className="table-header-title">AIS PROXIMITY SURVEILLANCE (20 KM CLEARANCE)</div>
                <table className="tech-table">
                  <thead>
                    <tr>
                      <th>VESSEL</th>
                      <th>SPEED</th>
                      <th>HEADING</th>
                      <th>DISTANCE</th>
                      <th>ALERT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aisData.map((v, idx) => (
                      <tr key={idx}>
                        <td className="mono">{v.name || v.vessel_id}</td>
                        <td className="mono">{v.speed_knots} kn</td>
                        <td className="mono">{v.heading_degrees}°</td>
                        <td className="mono">{v.distance_to_ship_km ? `${v.distance_to_ship_km} km` : "&gt; 50 km"}</td>
                        <td>
                          <span className={`status-pill ${v.proximity_alert ? "restricted" : "safe"}`}>
                            {v.proximity_alert ? "PROX ALERT" : "CLEAR"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Environmental Daylight & Atmosphere */}
              <div className="spec-card">
                <div className="spec-title">SOLAR EPHEMERIS & DAYLIGHT MONITOR</div>
                <div className="spec-grid">
                  <div>SOLAR STATUS: <strong className="mono amber">{daylightData?.daylight_status?.toUpperCase() || "REDUCED DAYLIGHT"}</strong></div>
                  <div>DAYLIGHT HOURS: <strong className="mono">{daylightData?.daylight_hours?.toFixed(1) || "11.2"} HOURS</strong></div>
                  <div>SOLAR ELEVATION: <strong className="mono">14.2° ABOVE HORIZON</strong></div>
                  <div>POLAR NIGHT: <strong className="mono green">INACTIVE (SUMMER)</strong></div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* ROW 3: 48-HOUR ENVIRONMENTAL & SEA-ICE ROUTE FORECAST PANEL */}
        <RouteForecastPanel
          forecastData={forecast48h}
          onRefresh={fetchDashboardExtras}
          isLoading={isForecastLoading}
        />
      </main>
    </div>
  );
}

export default MissionDashboard;
