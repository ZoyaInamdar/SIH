import React, { useState } from "react";
import CircularGauge from "./CircularGauge";
import CompassDial from "./CompassDial";
import IcebergProfile from "./IcebergProfile";

function WeatherHazardSidebar({
  isOpen = false,
  onClose,
  ship,
  nearbyIcebergs = [],
  closestIcebergId,
  activeAlertIceberg,
  alertETA,
  routeHazardIcebergs = [],
  isDeterring = false,
  deterOffsetKm = 0,
  deterDirection = "STARBOARD",
  deterTarget = null,
  distanceKm = Infinity,
  routeStatus = "OPTIMAL FAIRWAY",
  seaIceConcentration = 12.0,
  iceThicknessMeters = 0.5,
  windSpeedKnots = 20.6,
  windDirectionDeg = 287,
  gustKnots = 27.8,
  waveHeightMeters = 4.9,
  swellPeriodSeconds = 7.8,
  wmoZone = "SAFE",
  operationalRisk = "SAFE",
  weatherSource = "ERA5_ECMWF_GLORYS12V1",
  forecast48h = null,
  onOpenForecastModal = () => {},
  showDriftForecast = true,
  onToggleDriftForecast = () => {}
}) {
  const [activeTab, setActiveTab] = useState("all"); // "all" | "hazards" | "weather"

  const headingDeg = Number(ship?.heading ?? ship?.heading_deg ?? 75);

  const otherIcebergs = nearbyIcebergs.filter(
    (b) => (b.id ?? b.iceberg_id) !== (activeAlertIceberg?.id ?? activeAlertIceberg?.iceberg_id)
  );

  return (
    <aside className={`maritime-sidebar right-sidebar ${isOpen ? "open" : ""}`} id="sidebar-weather-hazard">
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <div className="sidebar-title-group">
          <h2 className="sidebar-title">Weather & Hazard Info.</h2>
        </div>
        <button className="sidebar-close-btn" onClick={onClose} title="Close Sidebar">
          ✕
        </button>
      </div>

      <div className="sidebar-scrollable-content">
        {/* Top Weather Image / Radar Button (Matching Reference Image) */}
        <div className="weather-top-cta">
          <button className="btn-weather-scan" onClick={() => setActiveTab(activeTab === "all" ? "hazards" : "all")}>
            <span>{activeTab === "hazards" ? "Show All Environmental Data" : "Satellite & Sonar Scan"}</span>
          </button>
        </div>

        {/* Compass Rose Dial Card (Matching Reference Image) */}
        <div className="sidebar-card compass-card">
          <div className="card-sub-header">
            <span className="card-label">WIND & HEADING ORIENTATION</span>
            <span className="card-tag">ERA5 &amp; GLORYS</span>
          </div>
          <div className="compass-wrapper">
            <CompassDial heading={headingDeg} windDirection={windDirectionDeg} size={150} />
          </div>
        </div>

        {/* Circular Gauges Row (Matching Reference Image: Wind Speed & Wave Height) */}
        <div className="sidebar-gauges-row">
          <div className="gauge-card-wrap">
            <CircularGauge
              label="Wind Speed"
              value={windSpeedKnots}
              unit="KTS"
              min={0}
              max={60}
              color="#D69A3E"
              size={120}
              subLabel={`GUSTS ${gustKnots ? gustKnots.toFixed(1) : (windSpeedKnots * 1.35).toFixed(1)} KTS`}
            />
          </div>
          <div className="gauge-card-wrap">
            <CircularGauge
              label="Wave"
              value={waveHeightMeters}
              unit="m"
              min={0}
              max={15}
              color="#8C8D89"
              size={120}
              subLabel={`SWELL PERIOD ${swellPeriodSeconds ? swellPeriodSeconds.toFixed(1) : "7.8"}s`}
            />
          </div>
        </div>

        {/* ICE Environmental Bars (Matching Reference Image: Thickness & Fraction) */}
        <div className="sidebar-card ice-environment-card">
          <div className="card-sub-header">
            <span className="card-label">ICE CONDITIONS</span>
            <span className="card-tag ice-class-tag">{`ZONE: ${wmoZone || "SAFE"}`}</span>
          </div>

          <div className="ice-metric-item">
            <div className="ice-metric-hdr">
              <span className="lbl">Thickness</span>
              <span className="val text-brass">{iceThicknessMeters.toFixed(1)} m</span>
            </div>
            <div className="ice-bar-track">
              <div
                className="ice-bar-fill thickness"
                style={{ width: `${Math.min(100, (iceThicknessMeters / 3.0) * 100)}%` }}
              />
            </div>
          </div>

          <div className="ice-metric-item">
            <div className="ice-metric-hdr">
              <span className="lbl">Fraction / Concentration</span>
              <span className="val text-cyan">{seaIceConcentration.toFixed(1)} %</span>
            </div>
            <div className="ice-bar-track">
              <div
                className="ice-bar-fill concentration"
                style={{ width: `${Math.min(100, seaIceConcentration)}%` }}
              />
            </div>
          </div>
        </div>

        {/* 48-Hour Environmental & Route Forecast Outlook Card */}
        <div className="sidebar-card forecast-preview-card" id="card-forecast-outlook">
          <div className="card-sub-header">
            <div className="forecast-title-row">
              <span className="card-label">48-HOUR ROUTE FORECAST OUTLOOK</span>
              <span className="card-tag forecast-tag">ERA5 + GLORYS</span>
            </div>
          </div>

          <div className="forecast-metrics-summary">
            <div className="forecast-mini-chip">
              <span className="mini-lbl">PEAK WIND</span>
              <span className="mini-val text-amber">{forecast48h?.summary?.max_wind_knots?.toFixed(1) ?? "30.7"} kn</span>
            </div>
            <div className="forecast-mini-chip">
              <span className="mini-lbl">MAX SWELL</span>
              <span className="mini-val text-blue">{forecast48h?.summary?.max_wave_height_m?.toFixed(1) ?? "6.2"} m</span>
            </div>
            <div className="forecast-mini-chip">
              <span className="mini-lbl">MAX ICE</span>
              <span className="mini-val text-cyan">{forecast48h?.summary?.max_sic_percent?.toFixed(1) ?? "30.2"}%</span>
            </div>
            <div className="forecast-mini-chip">
              <span className="mini-lbl">OVERALL</span>
              <span className={`mini-val ${forecast48h?.summary?.overall_risk === "CAUTION" ? "text-amber" : "text-green"}`}>
                {forecast48h?.summary?.overall_risk ?? "SAFE"}
              </span>
            </div>
          </div>

          {/* Forward 6-Hourly Timeline Glance */}
          <div className="forecast-timeline-glance">
            {(forecast48h?.timeline || [
              { forecast_hour_label: "NOW", wind: { speed_knots: 16.1 }, waves: { significant_height_m: 2.8 }, sea_ice: { concentration_percent: 15.3 } },
              { forecast_hour_label: "+6h", wind: { speed_knots: 30.7 }, waves: { significant_height_m: 6.2 }, sea_ice: { concentration_percent: 21.7 } },
              { forecast_hour_label: "+12h", wind: { speed_knots: 26.5 }, waves: { significant_height_m: 5.0 }, sea_ice: { concentration_percent: 25.0 } },
              { forecast_hour_label: "+24h", wind: { speed_knots: 21.0 }, waves: { significant_height_m: 3.8 }, sea_ice: { concentration_percent: 28.4 } },
              { forecast_hour_label: "+48h", wind: { speed_knots: 16.8 }, waves: { significant_height_m: 2.6 }, sea_ice: { concentration_percent: 19.2 } }
            ]).slice(0, 5).map((step, idx) => (
              <div key={idx} className="timeline-glance-col">
                <span className="t-time">{step.forecast_hour_label}</span>
                <span className="t-wind" title="Wind Speed">{Math.round(step.wind?.speed_knots || 0)}kn</span>
                <span className="t-wave" title="Significant Wave Height">{step.waves?.significant_height_m?.toFixed(1)}m</span>
                <span className="t-ice" title="Sea Ice Concentration">{Math.round(step.sea_ice?.concentration_percent || 0)}%</span>
              </div>
            ))}
          </div>

          <button
            className="btn-open-forecast-modal"
            onClick={onOpenForecastModal}
            id="btn-open-forecast-modal"
            title="Open Interactive 48-Hour Route Forecast Panel with Scrubbers & Sparklines"
          >
            <span>OPEN FULL 48H ROUTE TIMELINE</span>
            <span className="arrow-icon">↗</span>
          </button>
        </div>

        {/* Active CPA Collision Hazard Early Warning Alert Card */}
        {activeAlertIceberg && alertETA && (
          <div className="sidebar-card alert-collision-card">
            <div className="alert-card-header">
              <span className="alert-badge-alarm">COLLISION HAZARD CPA PROXIMITY</span>
              <span className="alert-eta-chip">
                {alertETA.formattedETA || `${Math.round(alertETA.hours * 60)} MIN`} ETA
              </span>
            </div>
            <div className="alert-card-details">
              <div className="alert-target-name">
                <span>TARGET: <strong>{activeAlertIceberg.id}</strong></span>
                <span className="cpa-dist text-amber">{alertETA.distanceKm.toFixed(1)} km</span>
              </div>
              <div className="alert-deter-status">
                {isDeterring ? (
                  <span className="text-amber">
                    <strong>COURSE DETERRENCE ACTIVE:</strong> +{deterOffsetKm.toFixed(1)} km {deterDirection}
                  </span>
                ) : (
                  <span className="text-cyan">
                    <strong>STATUS:</strong> AUTONAV AVOIDANCE VECTOR ARMED
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Iceberg Sonar Profiles & 3D Keel Geometry */}
        <div className="sidebar-card iceberg-sonar-section">
          <div className="card-sub-header">
            <span className="card-label">SONAR ICEBERG PROFILES</span>
            <button
              className={`drift-toggle-mini-btn ${showDriftForecast ? "active" : ""}`}
              onClick={onToggleDriftForecast}
              title="Toggle 3D Globe Iceberg Drift Vectors"
            >
              DRIFT: {showDriftForecast ? "ON" : "OFF"}
            </button>
          </div>

          {/* Featured Active Alert Iceberg */}
          {activeAlertIceberg && (
            <div className="featured-iceberg-wrap">
              <IcebergProfile
                berg={activeAlertIceberg}
                highlighted={true}
                alertETA={alertETA}
                isOnRoute={true}
              />
            </div>
          )}

          {/* Tracked Icebergs List */}
          <div className="iceberg-list">
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
        </div>
      </div>
    </aside>
  );
}

export default React.memo(WeatherHazardSidebar);
