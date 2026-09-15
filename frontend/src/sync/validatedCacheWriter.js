/**
 * NEW MODULE: sync/validatedCacheWriter.js
 * Sync Validation with Rollback (Purely Additive Wrapper)
 * Protects existing cache from corruption by bad or partial sync payloads.
 * Stores a ring buffer of the last 3 known-good snapshots per layer.
 */

const HISTORY_STORE_KEY = "polaris_cache_history_snapshots";
const MAX_SNAPSHOTS_PER_LAYER = 3;

/**
 * Validates payload structure, checking for empty, malformed, or corrupt data.
 */
export function isValidPayload(data) {
  if (!data || typeof data !== "object") return false;

  // Handle arrays
  if (Array.isArray(data)) {
    if (data.length === 0) return true; // Valid empty set
    // Check first element is an object
    return typeof data[0] === "object" && data[0] !== null;
  }

  // Handle wrapped API data responses: { data: [...] } or { status: "success", data: ... }
  if (data.status === "error") return false;

  // Check object has keys
  const keys = Object.keys(data);
  if (keys.length === 0) return false;

  return true;
}

/**
 * Reads the snapshot history for all layers from localStorage.
 */
export function getBackupHistory(layer) {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(HISTORY_STORE_KEY);
    const historyMap = raw ? JSON.parse(raw) : {};
    return layer ? historyMap[layer] || [] : historyMap;
  } catch (err) {
    console.warn("Could not read backup history:", err);
    return [];
  }
}

/**
 * Saves a snapshot to the layer's ring buffer (keeping last 3).
 */
export function saveToBackupHistory(layer, snapshot) {
  if (!snapshot || typeof localStorage === "undefined") return;
  try {
    const raw = localStorage.getItem(HISTORY_STORE_KEY);
    const historyMap = raw ? JSON.parse(raw) : {};
    const layerHistory = historyMap[layer] || [];

    // Prepend new snapshot with timestamp
    const record = {
      timestamp: new Date().toISOString(),
      data: snapshot,
    };

    const updated = [record, ...layerHistory].slice(0, MAX_SNAPSHOTS_PER_LAYER);
    historyMap[layer] = updated;

    localStorage.setItem(HISTORY_STORE_KEY, JSON.stringify(historyMap));
  } catch (err) {
    console.warn(`Could not save backup history for ${layer}:`, err);
  }
}

/**
 * Main wrapper function for safe atomic cache writes with rollback.
 *
 * @param {string} layer - The layer name (e.g., 'sea_ice', 'icebergs', 'weather')
 * @param {any} newData - The incoming payload to validate and write
 * @param {Function} existingWriteFunction - The existing write callback
 * @param {Function} existingReadFunction - The existing read callback to capture current state
 */
export async function writeToLocalCacheWithValidation(
  layer,
  newData,
  existingWriteFunction,
  existingReadFunction = null
) {
  // 1. Validate payload integrity
  if (!isValidPayload(newData)) {
    console.warn(`[ValidatedCacheWriter] Payload validation failed for ${layer} — keeping existing cache.`);
    return { success: false, keptExisting: true, reason: "INVALID_PAYLOAD" };
  }

  // 2. Read backup snapshot from existing read function if available
  let backupSnapshot = null;
  if (typeof existingReadFunction === "function") {
    try {
      backupSnapshot = await existingReadFunction(layer);
      if (backupSnapshot) {
        saveToBackupHistory(layer, backupSnapshot);
      }
    } catch (readErr) {
      console.warn(`[ValidatedCacheWriter] Non-fatal error reading backup for ${layer}:`, readErr);
    }
  }

  // 3. Attempt write using existing write logic
  try {
    if (typeof existingWriteFunction === "function") {
      await existingWriteFunction(newData);
    }
    return { success: true, layer, timestamp: new Date().toISOString() };
  } catch (err) {
    console.error(`[ValidatedCacheWriter] Write failed for ${layer}, initiating rollback:`, err);

    // 4. Rollback to last known-good snapshot
    if (backupSnapshot && typeof existingWriteFunction === "function") {
      try {
        await existingWriteFunction(backupSnapshot);
        console.info(`[ValidatedCacheWriter] Successfully rolled back ${layer} to last known-good snapshot.`);
      } catch (rollbackErr) {
        console.error(`[ValidatedCacheWriter] Critical: Rollback failed for ${layer}:`, rollbackErr);
      }
    }

    return {
      success: false,
      rolledBack: Boolean(backupSnapshot),
      error: err.message || String(err),
    };
  }
}
