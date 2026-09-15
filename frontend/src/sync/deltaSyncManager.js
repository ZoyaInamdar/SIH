/**
 * NEW MODULE: sync/deltaSyncManager.js
 * Delta/Priority Sync Manager (Purely Additive Wrapper)
 * Sits BETWEEN whatever triggers a data refresh and existing API-calling code.
 * Decides when, in what order, and with what geographic priority to fetch data.
 */

export const SYNC_PRIORITY_ORDER = [
  { layer: "ship_position", intervalSeconds: 5 },      // continuous tier (5s)
  { layer: "weather_wind",   intervalSeconds: 3600 },   // hourly tier (1h)
  { layer: "sea_ice",        intervalSeconds: 86400 },  // daily tier (24h)
  { layer: "iceberg_tracks", intervalSeconds: 86400 },  // daily tier (24h)
  { layer: "charts",         intervalSeconds: 604800 }, // weekly/periodic tier (7d)
];

const STORAGE_KEY = "polaris_delta_sync_timestamps";

// Retrieve locally persisted sync timestamps
export function loadSyncTimestamps() {
  if (typeof localStorage === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    console.warn("Could not read sync timestamps:", err);
    return {};
  }
}

// Persist sync timestamp locally
export function saveSyncTimestamp(layer, timestampIso) {
  if (typeof localStorage === "undefined") return;
  try {
    const current = loadSyncTimestamps();
    current[layer] = timestampIso || new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch (err) {
    console.warn("Could not save sync timestamp:", err);
  }
}

/**
 * Geographic prioritization helper:
 * Computes Haversine distance between two coordinates in kilometers.
 */
export function haversineDistanceKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Filter and sort items/regions by distance to ship position + route corridor.
 * Items nearest to vessel and corridor are prioritized first for low-bandwidth links.
 */
export function prioritizeGeographically(items = [], shipPos, routePoints = []) {
  if (!items || !Array.isArray(items) || items.length === 0) return items;
  if (!shipPos?.lat && (!routePoints || routePoints.length === 0)) return items;

  const sLat = Number(shipPos?.lat ?? shipPos?.latitude ?? -62.8);
  const sLon = Number(shipPos?.lon ?? shipPos?.longitude ?? -60.5);

  return [...items].sort((a, b) => {
    const aLat = Number(a.lat ?? a.latitude ?? a.current_latitude ?? 0);
    const aLon = Number(a.lon ?? a.longitude ?? a.current_longitude ?? 0);
    const bLat = Number(b.lat ?? b.latitude ?? b.current_latitude ?? 0);
    const bLon = Number(b.lon ?? b.longitude ?? b.current_longitude ?? 0);

    const distA = haversineDistanceKm(sLat, sLon, aLat, aLon);
    const distB = haversineDistanceKm(sLat, sLon, bLat, bLon);

    return distA - distB;
  });
}

/**
 * Executes a prioritized delta-sync cycle across registered layers.
 * Only calls existing fetch functions if the tier interval has expired.
 * Failures in a higher tier do not block lower tiers.
 */
export async function runDeltaSync(existingFetchFunctions = {}, context = {}) {
  const lastSyncedAt = loadSyncTimestamps();
  const syncResults = {};
  const { shipPosition, routePoints, forceAll = false } = context;

  for (const { layer, intervalSeconds } of SYNC_PRIORITY_ORDER) {
    const lastSync = lastSyncedAt[layer];
    const now = Date.now();
    const secondsSinceLast = lastSync
      ? (now - new Date(lastSync).getTime()) / 1000
      : Infinity;

    const dueForSync = forceAll || !lastSync || secondsSinceLast >= intervalSeconds;

    if (!dueForSync) {
      syncResults[layer] = { skipped: true, reason: "NOT_DUE", secondsSinceLast };
      continue;
    }

    const fetchFn = existingFetchFunctions[layer];
    if (typeof fetchFn !== "function") {
      syncResults[layer] = { skipped: true, reason: "NO_FETCH_FUNCTION" };
      continue;
    }

    try {
      // Pass since timestamp so backend can return delta updates if supported
      const params = {
        since: lastSync || null,
        shipPosition,
        routeCorridor: routePoints,
      };

      const result = await fetchFn(params);
      const isSuccess = result?.success ?? (result != null && !result.error);

      if (isSuccess) {
        const syncTime = new Date().toISOString();
        saveSyncTimestamp(layer, syncTime);
        syncResults[layer] = {
          success: true,
          syncedAt: syncTime,
          dataCount: Array.isArray(result?.data) ? result.data.length : 1,
        };
      } else {
        syncResults[layer] = {
          success: false,
          error: result?.error || "Fetch returned unsuccessful state",
        };
      }
    } catch (err) {
      // Non-blocking: record error and continue to next tier
      console.warn(`[DeltaSync] Layer ${layer} failed, continuing:`, err);
      syncResults[layer] = { success: false, error: err.message || String(err) };
    }
  }

  return syncResults;
}
