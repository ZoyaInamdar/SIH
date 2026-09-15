/**
 * NEW MODULE: fallback/climatologyLayer.js
 * Climatological Last-Resort Layer (Purely Additive Module)
 * Shipped with the app, not fetched at runtime.
 * Activated ONLY when zero cached real data exists for a geographic region.
 */

import { lookupClimatologyTable } from "./climatologyData";

function isEmpty(val) {
  if (val == null) return true;
  if (typeof val === "object" && Object.keys(val).length === 0) return true;
  if (Array.isArray(val) && val.length === 0) return true;
  return false;
}

/**
 * Reads ice concentration from local cache; if missing or empty,
 * seamlessly falls back to 30-year climatological average clearly flagged.
 *
 * @param {number} lat - Latitude in degrees
 * @param {number} lon - Longitude in degrees
 * @param {Function} existingCacheReadFunction - Read callback for local cache
 * @param {number} monthIdx - Optional month index (0-11)
 */
export async function getIceConcentrationWithFallback(
  lat,
  lon,
  existingCacheReadFunction = null,
  monthIdx = null
) {
  let realData = null;

  if (typeof existingCacheReadFunction === "function") {
    try {
      realData = await existingCacheReadFunction(lat, lon);
    } catch (err) {
      console.warn("[ClimatologyLayer] Cache read encountered error, using fallback:", err);
    }
  }

  // 1. If authentic cached data exists, return it cleanly marked as real-time
  if (realData && !isEmpty(realData)) {
    return {
      ...realData,
      isClimatological: false,
      dataConfidence: realData.confidence ?? "HIGH",
      dataSource: realData.source ?? "COPERNICUS_CACHED",
    };
  }

  // 2. Otherwise, fall back to historical seasonal climatology table
  const climatological = lookupClimatologyTable(lat, lon, monthIdx);

  return {
    ...climatological,
    isClimatological: true,
    dataConfidence: "CLIMATOLOGICAL_ESTIMATE",
    confidenceLevel: "low",
    label: "CLIMATOLOGICAL AVERAGE — not real-time data",
    visualHatchingRequired: true,
    warning: "NO ACTIVE OR CACHED SATELLITE DATA FOR THIS REGION. SHOWING 30-YR SEASONAL AVERAGE.",
  };
}

/**
 * Returns rendering styles for a map tile/polygon depending on whether
 * it is authentic real-time data or climatological fallback.
 */
export function getClimatologyStyle(isClimatological) {
  if (!isClimatological) {
    return {
      fillPattern: "solid",
      borderStyle: "solid",
      badgeText: "REAL-TIME / CACHED MODEL",
      badgeClass: "badge-realtime",
    };
  }

  return {
    fillPattern: "diagonal-stripes",
    borderStyle: "dashed",
    borderColor: "#f59e0b",
    badgeText: "CLIMATOLOGICAL AVERAGE — NOT REAL-TIME",
    badgeClass: "badge-climatology-warning",
  };
}
