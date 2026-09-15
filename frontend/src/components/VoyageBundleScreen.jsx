import React, { useState, useEffect } from "react";
import {
  downloadVoyageBundle,
  getSavedVoyageBundleManifest,
} from "../sync/voyageBundleDownloader";
import "./voyageBundleScreen.css";

/**
 * Pre-Departure Voyage Bundle Screen
 * A dedicated offline preparation utility screen, completely separate
 * from the live navigation dashboard.
 */
export default function VoyageBundleScreen({
  isOpen = false,
  onClose,
  routePoints = [],
  existingFetchFunctions = {},
}) {
  const [horizonDays, setHorizonDays] = useState(7);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [manifest, setManifest] = useState(null);

  useEffect(() => {
    setManifest(getSavedVoyageBundleManifest());
  }, [isOpen]);

  if (!isOpen) return null;

  const handleStartDownload = async () => {
    setIsDownloading(true);
    setDownloadProgress(5);
    setStatusMessage("Connecting to Copernicus & ECMWF high-speed dock uplink...");

    try {
      const result = await downloadVoyageBundle(
        routePoints,
        horizonDays,
        existingFetchFunctions,
        (stepLabel, percent) => {
          setStatusMessage(stepLabel);
          setDownloadProgress(percent);
        }
      );

      setManifest(result.manifest);
      setStatusMessage("Voyage Bundle Successfully Cached to Local Storage!");
    } catch (err) {
      setStatusMessage(`Error downloading bundle: ${err.message || String(err)}`);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="voyage-bundle-backdrop" onClick={onClose}>
      <div
        className="voyage-bundle-modal"
        onClick={(e) => e.stopPropagation()}
        id="modal-voyage-bundle"
      >
        {/* Modal Header */}
        <div className="bundle-header">
          <div className="bundle-header-left">
            <div>
              <h2 className="bundle-title">PRE-DEPARTURE VOYAGE BUNDLE DOWNLOADER</h2>
              <span className="bundle-subtitle">
                Offline Mode Preparation Utility — Run Once Prior to Harbor Departure
              </span>
            </div>
          </div>
          <button className="bundle-close-btn" onClick={onClose} title="Close">
            ✕
          </button>
        </div>

        {/* Modal Content */}
        <div className="bundle-content">
          <div className="bundle-intro-card">
            <p>
              This utility pre-packages comprehensive environmental, sea-ice, iceberg
              tracking, and bathymetric grids along your designated Antarctic fairway.
              Once downloaded, the entire system operates <strong>100% offline</strong> without
              requiring an active satellite link.
            </p>
          </div>

          {/* Configuration Grid */}
          <div className="bundle-config-grid">
            <div className="config-item">
              <label>PLANNED TRANSIT CORRIDOR:</label>
              <div className="config-val">
                Drake Passage → Bransfield Strait ({routePoints.length || 7} Waypoints)
              </div>
            </div>

            <div className="config-item">
              <label>OFFLINE FORECAST HORIZON:</label>
              <div className="horizon-selector">
                {[3, 7, 14].map((d) => (
                  <button
                    key={d}
                    className={`horizon-btn ${horizonDays === d ? "active" : ""}`}
                    onClick={() => setHorizonDays(d)}
                    disabled={isDownloading}
                  >
                    {d} DAYS
                  </button>
                ))}
              </div>
            </div>

            <div className="config-item">
              <label>DATA TIERS INCLUDED IN BUNDLE:</label>
              <ul className="tiers-list">
                <li>Copernicus GLORYS12V1 Daily Sea-Ice Concentration (SIC/SIT)</li>
                <li>Master Iceberg Geometries, Keel Drafts & 48h Drift Vectors</li>
                <li>GEBCO Undersea Bathymetry & Standoff Shallow Contours</li>
                <li>ECMWF ERA5 10m Winds, Swell Heights & Polar Surface Temps</li>
              </ul>
            </div>
          </div>

          {/* Download Progress Bar */}
          {isDownloading && (
            <div className="bundle-progress-section">
              <div className="progress-labels">
                <span className="status-txt">{statusMessage}</span>
                <span className="percent-txt">{downloadProgress}%</span>
              </div>
              <div className="bundle-progress-track">
                <div
                  className="bundle-progress-fill"
                  style={{ width: `${downloadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Existing Manifest / Status */}
          {manifest && !isDownloading && (
            <div className="bundle-manifest-card">
              <div className="manifest-header">
                <span className="status-badge ready">OFFLINE VOYAGE CACHE READY</span>
                <span className="manifest-id">{manifest.bundleId}</span>
              </div>
              <div className="manifest-details">
                <div>
                  DOWNLOADED AT: <strong>{new Date(manifest.downloadedAt).toLocaleString()}</strong>
                </div>
                <div>
                  FORECAST HORIZON: <strong>{manifest.forecastHorizonDays} DAYS AHEAD</strong>
                </div>
                <div>
                  ESTIMATED BUNDLE SIZE: <strong>{manifest.bundleSizeEstimate}</strong>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="bundle-footer">
          <button
            className="btn-cancel-bundle"
            onClick={onClose}
            disabled={isDownloading}
          >
            Cancel
          </button>
          <button
            className={`btn-download-bundle ${isDownloading ? "loading" : ""}`}
            onClick={handleStartDownload}
            disabled={isDownloading}
            id="btn-trigger-bundle-download"
          >
            {isDownloading
              ? "Downloading Voyage Bundle..."
              : manifest
              ? "Re-Download Fresh Voyage Bundle"
              : "Download Offline Voyage Bundle"}
          </button>
        </div>
      </div>
    </div>
  );
}
