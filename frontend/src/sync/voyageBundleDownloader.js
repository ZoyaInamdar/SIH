/**
 * NEW MODULE: sync/voyageBundleDownloader.js
 * Pre-Departure Voyage Bundle Downloader (Purely Additive Feature)
 * Designed to run once while vessel is at dock with high-speed uplink.
 * Pre-downloads extensive geographic & temporal coverage into local cache.
 */

import { writeToLocalCacheWithValidation } from "./validatedCacheWriter";

const BUNDLE_STORAGE_KEY = "polaris_voyage_bundle_manifest";

export function estimateSize(data) {
  try {
    const jsonStr = JSON.stringify(data);
    const bytes = new Blob([jsonStr]).size;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  } catch {
    return "Unknown Size";
  }
}

export function getSavedVoyageBundleManifest() {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(BUNDLE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Downloads a complete multi-tier voyage bundle for offline navigation.
 *
 * @param {Array} routeCorridor - Waypoints/corridor coordinates defining the voyage
 * @param {number} forecastHorizonDays - Forecast horizon in days (e.g. 7 or 14)
 * @param {Object} existingFetchFunctions - Dictionary of existing data fetching functions
 * @param {Function} onProgress - Progress callback (layer, percent)
 */
export async function downloadVoyageBundle(
  routeCorridor = [],
  forecastHorizonDays = 7,
  existingFetchFunctions = {},
  onProgress = null
) {
  const bundle = {
    metadata: {
      generatedAt: new Date().toISOString(),
      forecastHorizonDays,
      waypointCount: routeCorridor.length,
      routeSummary: "Drake Passage & Bransfield Strait Polar Corridor",
    },
    layers: {},
  };

  const layersToFetch = [
    { key: "sea_ice", label: "Copernicus High-Res Sea Ice Grids" },
    { key: "iceberg_tracks", label: "Iceberg Drift & Sonar Profiles" },
    { key: "bathymetry", label: "GEBCO Bathymetric Grounding Depths" },
    { key: "weather_wind", label: "ECMWF ERA5 Wind, Waves & Temperatures" },
  ];

  let completed = 0;

  for (const { key, label } of layersToFetch) {
    if (onProgress) {
      onProgress(label, Math.round((completed / layersToFetch.length) * 100));
    }

    const fetchFn = existingFetchFunctions[key];
    if (typeof fetchFn === "function") {
      try {
        const layerData = await fetchFn({
          region: routeCorridor,
          horizonDays: forecastHorizonDays,
        });
        bundle.layers[key] = layerData;

        // Write safely into validated cache
        await writeToLocalCacheWithValidation(
          `bundle_${key}`,
          layerData,
          async (val) => {
            if (typeof localStorage !== "undefined") {
              try {
                localStorage.setItem(`polaris_cache_${key}`, JSON.stringify(val));
              } catch (e) {
                console.warn(`Local storage quota warning for ${key}:`, e);
              }
            }
          }
        );
      } catch (err) {
        console.warn(`Could not download bundle layer ${key}:`, err);
        bundle.layers[key] = { error: err.message || String(err) };
      }
    } else {
      bundle.layers[key] = { status: "cached_baseline" };
    }

    completed++;
  }

  if (onProgress) {
    onProgress("Finalizing Voyage Bundle Manifest...", 100);
  }

  const manifest = {
    bundleId: `BUNDLE-${Date.now()}`,
    downloadedAt: new Date().toISOString(),
    forecastHorizonDays,
    bundleSizeEstimate: estimateSize(bundle),
    layerStatus: Object.keys(bundle.layers).map((k) => ({
      layer: k,
      ready: !bundle.layers[k]?.error,
    })),
  };

  if (typeof localStorage !== "undefined") {
    localStorage.setItem(BUNDLE_STORAGE_KEY, JSON.stringify(manifest));
  }

  return {
    success: true,
    bundle,
    manifest,
    bundleSizeEstimate: manifest.bundleSizeEstimate,
    downloadedAt: manifest.downloadedAt,
  };
}
