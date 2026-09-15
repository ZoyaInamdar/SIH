import { useState, useEffect, useMemo } from "react";
import "./routeForecastPanel.css";

function RouteForecastPanel({ forecastData, onRefresh, isLoading = false }) {
  const [selectedStepIdx, setSelectedStepIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const timeline = useMemo(() => forecastData?.timeline || [], [forecastData]);
  const hourly = useMemo(() => forecastData?.hourly || [], [forecastData]);
  const summary = useMemo(() => forecastData?.summary || {}, [forecastData]);

  // Active step selected in timeline
  const activeStep = timeline[selectedStepIdx] || timeline[0] || null;

  // Auto-play / Horizon Sequencer
  useEffect(() => {
    if (!isPlaying || timeline.length === 0) return;
    const interval = setInterval(() => {
      setSelectedStepIdx((prev) => (prev + 1) % timeline.length);
    }, 2200);
    return () => clearInterval(interval);
  }, [isPlaying, timeline]);

  // Helper to render SVG polyline sparkline
  const renderSparkline = (dataKey, strokeColor, minVal, maxVal) => {
    if (!hourly || hourly.length < 2) return null;
    const width = 240;
    const height = 36;
    const padding = 2;
    const range = Math.max(0.01, maxVal - minVal);

    const points = hourly.map((item, idx) => {
      const x = padding + (idx / (hourly.length - 1)) * (width - 2 * padding);
      const val = Number(item[dataKey]) || 0;
      const normalizedY = (val - minVal) / range;
      const y = height - padding - normalizedY * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

    // Selected step dot
    const stepHour = activeStep?.step_hour ?? 0;
    const activeDotX = padding + (stepHour / 48) * (width - 2 * padding);
    const activeVal = hourly[stepHour]?.[dataKey] ?? (Number(activeStep?.[dataKey]) || 0);
    const activeDotY = height - padding - ((activeVal - minVal) / range) * (height - 2 * padding);

    return (
      <svg className="sparkline-svg" viewBox={`0 0 ${width} ${height}`}>
        <polyline
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
        <circle cx={activeDotX} cy={activeDotY} r="3.5" fill="#ffffff" stroke={strokeColor} strokeWidth="1.5" />
      </svg>
    );
  };

  if (!forecastData && isLoading) {
    return (
      <section className="route-forecast-panel">
        <div className="forecast-header-bar">
          <span className="forecast-title">04 // 48-HOUR ENVIRONMENTAL & SEA-ICE ROUTE FORECAST</span>
          <span className="forecast-pill cyan">FETCHING ERA5 / GLORYS 48H MODEL...</span>
        </div>
      </section>
    );
  }

  return (
    <section className="route-forecast-panel">
      {/* 1. HEADER BAR */}
      <header className="forecast-header-bar">
        <div className="forecast-header-left">
          <span className="forecast-title">04 // 48-HOUR ENVIRONMENTAL & SEA-ICE ROUTE FORECAST</span>
          <div className="forecast-badge-group">
            <span className="forecast-pill cyan">48H HORIZON (6-HOURLY &amp; HOURLY)</span>
            <span className="forecast-pill green">ERA5 + GLORYS12V1 COPERNICUS</span>
            <span className={`forecast-pill ${summary.overall_risk === "CAUTION" ? "amber" : "green"}`}>
              STATUS: {summary.overall_risk || "SAFE"}
            </span>
          </div>
        </div>

        <div className="forecast-header-right">
          {forecastData?.generated_utc && (
            <span className="forecast-meta-time">
              MODEL RUN: {forecastData.generated_utc.substring(11, 19)}Z
            </span>
          )}
          <button
            className={`btn-forecast-play ${isPlaying ? "playing" : ""}`}
            onClick={() => setIsPlaying(!isPlaying)}
            title="Sequentially cycle through 48-hour forward horizon"
          >
            {isPlaying ? "⏸ PAUSE SEQUENCER" : "▶ PLAY 48H HORIZON"}
          </button>
          {onRefresh && (
            <button className="btn-forecast-play" onClick={onRefresh} title="Reload 48h environmental forecast">
              ↻ REFRESH
            </button>
          )}
        </div>
      </header>

      {/* 2. ADVISORY & 48H SUMMARY KPI STRIP */}
      <div className="forecast-summary-strip">
        <div className="forecast-advisory-box">
          <span className="advisory-tag">48-HOUR POLAR METEOROLOGICAL ADVISORY</span>
          <span className="advisory-text">
            {summary.advisory || "PASSAGE CLEAR — WESTERLY AIRFLOW ACTIVE ACROSS BRANSFIELD STRAIT."}
          </span>
        </div>

        <div className="summary-kpi-cell">
          <span className="summary-kpi-label">PEAK GALE / WIND</span>
          <span className="summary-kpi-value amber">{summary.max_wind_knots || 31.3} KTS</span>
          <span className="summary-kpi-sub">SUB-POLAR TROUGH</span>
        </div>

        <div className="summary-kpi-cell">
          <span className="summary-kpi-label">PEAK SWELL (Hs)</span>
          <span className="summary-kpi-value cyan">{summary.max_wave_height_m || 3.4} m</span>
          <span className="summary-kpi-sub">ICE-DAMPED DEEP OCEAN</span>
        </div>

        <div className="summary-kpi-cell">
          <span className="summary-kpi-label">MAX ICE CONC (SIC)</span>
          <span className="summary-kpi-value cyan">{summary.max_sic_percent || 30.2}%</span>
          <span className="summary-kpi-sub">WMO ZONE 4-6 MARGIN</span>
        </div>

        <div className="summary-kpi-cell">
          <span className="summary-kpi-label">MIN SEA TEMP (SST)</span>
          <span className="summary-kpi-value blue">{summary.min_sst_c || -1.48}°C</span>
          <span className="summary-kpi-sub">&gt; 0.38°C ABOVE FREEZE</span>
        </div>
      </div>

      {/* 3. INTERACTIVE 48-HOUR TIMELINE SCRUBBER */}
      <div className="timeline-scrubber-bar">
        <span className="scrubber-label">TIMELINE HORIZON:</span>
        {timeline.map((step, idx) => {
          const isSelected = idx === selectedStepIdx;
          const sicPct = step.sea_ice?.concentration_percent ?? 0;
          return (
            <button
              key={idx}
              className={`timeline-step-btn ${isSelected ? "active" : ""}`}
              onClick={() => {
                setIsPlaying(false);
                setSelectedStepIdx(idx);
              }}
              title={`Jump to ${step.forecast_hour_label} forecast: ${step.location_name}`}
            >
              <span className="step-hour">{step.forecast_hour_label}</span>
              <span className="step-sic">SIC: {sicPct}%</span>
            </button>
          );
        })}
      </div>

      {/* 4. FOCUSED STEP DETAIL BREAKDOWN (THE 4 CORE PARAMETERS) */}
      {activeStep && (
        <div className="focused-step-workspace">
          <div className="focused-meta-banner">
            <div className="meta-loc">
              <span className="meta-loc-tag">TIMESTEP {activeStep.forecast_hour_label}:</span>
              <span className="meta-loc-name">{activeStep.location_name}</span>
              <span className="meta-loc-coords">
                ({Math.abs(activeStep.projected_lat).toFixed(2)}°S, {Math.abs(activeStep.projected_lon).toFixed(2)}°W)
              </span>
            </div>
            <div className="meta-eta">
              PASSAGE TRACK: +{activeStep.dist_along_route_km} KM | VALID UTC: {activeStep.valid_time_iso.substring(0, 16).replace("T", " ")}Z
            </div>
          </div>

          <div className="forecast-parameters-grid">
            {/* CARD 1: SEA-ICE CONCENTRATION */}
            <div className="parameter-card ice">
              <div className="param-header">
                <span className="param-title">SEA-ICE CONCENTRATION (SIC)</span>
                <span className={`param-status-tag ${activeStep.sea_ice?.risk_level === "RESTRICTED" ? "restricted" : activeStep.sea_ice?.risk_level === "CAUTION" ? "caution" : "safe"}`}>
                  {activeStep.sea_ice?.risk_level || "SAFE"}
                </span>
              </div>
              <div className="param-main-readout">
                <span className="param-val cyan">{activeStep.sea_ice?.concentration_percent}%</span>
                <span className="param-unit">COVERAGE</span>
              </div>
              <div className="sic-bar-track">
                <div
                  className={`sic-bar-fill ${activeStep.sea_ice?.risk_level === "RESTRICTED" ? "restricted" : activeStep.sea_ice?.risk_level === "CAUTION" ? "caution" : "safe"}`}
                  style={{ width: `${Math.min(100, activeStep.sea_ice?.concentration_percent)}%` }}
                />
              </div>
              <div className="param-details-list">
                <div className="param-detail-row">
                  <span>WMO CATEGORY:</span>
                  <strong>{activeStep.sea_ice?.wmo_zone}</strong>
                </div>
                <div className="param-detail-row">
                  <span>EST PACK THICKNESS:</span>
                  <strong className="mono">{activeStep.sea_ice?.estimated_thickness_m}m</strong>
                </div>
                <div className="param-detail-row">
                  <span>NAVIGATION STATUS:</span>
                  <strong className={activeStep.sea_ice?.risk_level === "SAFE" ? "green" : "amber"}>
                    {activeStep.sea_ice?.risk_level === "SAFE" ? "UNRESTRICTED TRANSIT" : "REDUCED SOG ADVISORY"}
                  </strong>
                </div>
              </div>
            </div>

            {/* CARD 2: ATMOSPHERIC WIND VECTOR */}
            <div className="parameter-card wind">
              <div className="param-header">
                <span className="param-title">WIND &amp; GUST CONDITIONS (ERA5)</span>
                <span className={`param-status-tag ${activeStep.wind?.speed_knots > 30 ? "caution" : "safe"}`}>
                  BEAUFORT {activeStep.wind?.beaufort}
                </span>
              </div>
              <div className="param-main-readout">
                <span className="param-val amber">{activeStep.wind?.speed_knots}</span>
                <span className="param-unit">KTS {activeStep.wind?.cardinal}</span>
              </div>
              <div className="param-details-list">
                <div className="param-detail-row">
                  <span>WIND DIRECTION:</span>
                  <strong className="mono">{activeStep.wind?.direction_degrees}° TRUE ({activeStep.wind?.cardinal})</strong>
                </div>
                <div className="param-detail-row">
                  <span>PEAK GUSTS:</span>
                  <strong className="mono amber">{activeStep.wind?.gust_knots} KTS</strong>
                </div>
                <div className="param-detail-row">
                  <span>PRESSURE REGIME:</span>
                  <strong>SUB-POLAR GRADIENT</strong>
                </div>
              </div>
            </div>

            {/* CARD 3: SEA SURFACE TEMPERATURE */}
            <div className="parameter-card temp">
              <div className="param-header">
                <span className="param-title">SEA SURFACE TEMP (GLORYS SST)</span>
                <span className="param-status-tag safe">LIQUID WATER</span>
              </div>
              <div className="param-main-readout">
                <span className="param-val blue">{activeStep.sea_surface_temp?.temp_c}°C</span>
                <span className="param-unit">OCEAN SST</span>
              </div>
              <div className="param-details-list">
                <div className="param-detail-row">
                  <span>SEAWATER FREEZING PT:</span>
                  <strong className="mono">{activeStep.sea_surface_temp?.freezing_point_c}°C</strong>
                </div>
                <div className="param-detail-row">
                  <span>FREEZE SAFETY MARGIN:</span>
                  <strong className="mono green">+{activeStep.sea_surface_temp?.freeze_margin_c}°C</strong>
                </div>
                <div className="param-detail-row">
                  <span>SUPERCOOLING RISK:</span>
                  <strong className="green">{activeStep.sea_surface_temp?.supercooling_risk}</strong>
                </div>
              </div>
            </div>

            {/* CARD 4: WAVE & SWELL DAMPING */}
            <div className="parameter-card wave">
              <div className="param-header">
                <span className="param-title">WAVE &amp; SWELL CONDITIONS</span>
                <span className="param-status-tag safe">{activeStep.waves?.sea_state?.split(" ")[0]}</span>
              </div>
              <div className="param-main-readout">
                <span className="param-val" style={{ color: "#c084fc" }}>{activeStep.waves?.significant_height_m}m</span>
                <span className="param-unit">Hs SWELL</span>
              </div>
              <div className="param-details-list">
                <div className="param-detail-row">
                  <span>DOMINANT PERIOD (Tp):</span>
                  <strong className="mono">{activeStep.waves?.swell_period_s}s</strong>
                </div>
                <div className="param-detail-row">
                  <span>OPEN OCEAN EQUIV:</span>
                  <strong className="mono">{activeStep.waves?.undamped_open_sea_hs_m}m</strong>
                </div>
                <div className="param-detail-row">
                  <span>ICE DAMPING EFFICIENCY:</span>
                  <strong className="cyan">-{activeStep.waves?.ice_damping_percent}% SWELL</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. 48-HOUR COMPARATIVE MATRIX TABLE */}
      <div className="forecast-table-section">
        <div className="forecast-table-wrap">
          <table className="forecast-tech-table">
            <thead>
              <tr>
                <th>STEP</th>
                <th>VALID UTC</th>
                <th>PROJECTED WAYPOINT / PASSAGE</th>
                <th>DIST</th>
                <th>SEA-ICE CONC</th>
                <th>WMO CLASSIFICATION</th>
                <th>WIND (KTS &amp; DIR)</th>
                <th>GUSTS</th>
                <th>SWELL Hs (Tp)</th>
                <th>SST (°C)</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {timeline.map((row, idx) => {
                const isSelected = idx === selectedStepIdx;
                const sicPct = row.sea_ice?.concentration_percent ?? 0;
                return (
                  <tr
                    key={idx}
                    className={isSelected ? "row-selected" : ""}
                    onClick={() => {
                      setIsPlaying(false);
                      setSelectedStepIdx(idx);
                    }}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="mono cyan"><strong>{row.forecast_hour_label}</strong></td>
                    <td className="mono">{row.valid_time_iso.substring(11, 16)}Z ({row.valid_time_iso.substring(5, 10)})</td>
                    <td>{row.location_name}</td>
                    <td className="mono">+{row.dist_along_route_km} km</td>
                    <td className="mono cyan">
                      <strong>{sicPct}%</strong>
                    </td>
                    <td>
                      <span className={`status-pill ${row.sea_ice?.risk_level === "RESTRICTED" ? "restricted" : row.sea_ice?.risk_level === "CAUTION" ? "caution" : "safe"}`}>
                        {row.sea_ice?.risk_level || "SAFE"}
                      </span>
                    </td>
                    <td className="mono">
                      <strong>{row.wind?.speed_knots} kts</strong> {row.wind?.cardinal}
                    </td>
                    <td className="mono amber">{row.wind?.gust_knots} kts</td>
                    <td className="mono" style={{ color: "#EDEDEA" }}>
                      <strong>{row.waves?.significant_height_m}m</strong> ({row.waves?.swell_period_s}s)
                    </td>
                    <td className="mono" style={{ color: "#8C8D89" }}>{row.sea_surface_temp?.temp_c}°C</td>
                    <td>
                      <span className="status-pill safe">NOMINAL</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. 48-HOUR HOURLY TREND SPARKLINES */}
      {hourly.length > 0 && (
        <div className="forecast-sparklines-section">
          <div className="sparkline-box">
            <div className="sparkline-header">
              <span>WIND SPEED (KTS) 48H</span>
              <strong className="amber">{activeStep?.wind?.speed_knots} kts</strong>
            </div>
            {renderSparkline("wind_speed_knots", "#D69A3E", 5, 38)}
          </div>

          <div className="sparkline-box">
            <div className="sparkline-header">
              <span>WAVE SWELL Hs (M) 48H</span>
              <strong style={{ color: "#C64B3F" }}>{activeStep?.waves?.significant_height_m} m</strong>
            </div>
            {renderSparkline("significant_wave_height_m", "#C64B3F", 1.0, 7.0)}
          </div>

          <div className="sparkline-box">
            <div className="sparkline-header">
              <span>SEA-ICE CONC (%) 48H</span>
              <strong className="brass" style={{ color: "#B8944A" }}>{activeStep?.sea_ice?.concentration_percent}%</strong>
            </div>
            {renderSparkline("sea_ice_percent", "#B8944A", 0, 40)}
          </div>

          <div className="sparkline-box">
            <div className="sparkline-header">
              <span>SST (°C) 48H</span>
              <strong style={{ color: "#8C8D89" }}>{activeStep?.sea_surface_temp?.temp_c}°C</strong>
            </div>
            {renderSparkline("sst_c", "#8C8D89", -1.8, -0.8)}
          </div>
        </div>
      )}
    </section>
  );
}

export default RouteForecastPanel;
