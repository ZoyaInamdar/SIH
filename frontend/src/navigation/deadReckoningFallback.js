/**
 * NEW MODULE: navigation/deadReckoningFallback.js
 * Dead-Reckoning Fallback for Ship Position (Purely Additive Wrapper)
 * Wraps existing NMEA/GPS handler. If the live feed drops (>30 seconds),
 * projects ship position forward using last known speed and heading rather
 * than freezing or blanking the vessel.
 */

let lastKnownFix = null;

/**
 * Projects a geographic coordinate along a rhumb line heading by a given nautical distance.
 *
 * @param {number} lat - Latitude in degrees
 * @param {number} lon - Longitude in degrees
 * @param {number} headingDeg - True vessel heading in degrees
 * @param {number} distanceNm - Distance traveled in Nautical Miles
 */
export function projectPosition(lat, lon, headingDeg, distanceNm) {
  const dRad = distanceNm / (60 * (180 / Math.PI)); // Angular distance in radians
  const headingRad = (headingDeg * Math.PI) / 180;
  const latRad = (lat * Math.PI) / 180;
  const lonRad = (lon * Math.PI) / 180;

  const newLatRad = Math.asin(
    Math.sin(latRad) * Math.cos(dRad) +
      Math.cos(latRad) * Math.sin(dRad) * Math.cos(headingRad)
  );

  const newLonRad =
    lonRad +
    Math.atan2(
      Math.sin(headingRad) * Math.sin(dRad) * Math.cos(latRad),
      Math.cos(dRad) - Math.sin(latRad) * Math.sin(newLatRad)
    );

  return {
    lat: (newLatRad * 180) / Math.PI,
    lon: (newLonRad * 180) / Math.PI,
  };
}

/**
 * Higher-order wrapper around the existing position handler.
 * Keeps track of the last authentic NMEA fix.
 */
export function onRealPositionUpdate(existingHandler) {
  return (nmeaData) => {
    if (nmeaData && (nmeaData.lat || nmeaData.latitude)) {
      const lat = Number(nmeaData.lat ?? nmeaData.latitude);
      const lon = Number(nmeaData.lon ?? nmeaData.longitude);
      const speed = Number(nmeaData.speed_knots ?? nmeaData.speed ?? 12.4);
      const heading = Number(nmeaData.heading_deg ?? nmeaData.heading ?? 90);

      lastKnownFix = {
        ...nmeaData,
        lat,
        lon,
        latitude: lat,
        longitude: lon,
        speed_knots: speed,
        heading_deg: heading,
        heading,
        timestamp: new Date().toISOString(),
        estimated: false,
      };
    }

    if (typeof existingHandler === "function") {
      existingHandler(nmeaData);
    }
  };
}

/**
 * Evaluates current position:
 * Returns authentic fix if fresh (<30s).
 * If feed dropped (>=30s), returns dead-reckoning projected coordinates
 * flagged with `estimated: true`.
 */
export function getDisplayPosition(fallbackShip = null) {
  const baseFix = lastKnownFix || fallbackShip;
  if (!baseFix) return null;

  const fixTime = baseFix.timestamp ? new Date(baseFix.timestamp).getTime() : Date.now();
  const secondsSinceFix = Math.max(0, (Date.now() - fixTime) / 1000);

  // Recent fix (< 30 seconds): use authentic telemetry
  if (secondsSinceFix < 30) {
    return {
      ...baseFix,
      estimated: false,
      secondsSinceFix: Math.round(secondsSinceFix),
    };
  }

  // GPS feed dropped: calculate dead-reckoning projection
  const speed = Number(baseFix.speed_knots ?? 12.4);
  const heading = Number(baseFix.heading_deg ?? baseFix.heading ?? 90);
  const distanceNm = (speed * secondsSinceFix) / 3600;

  const startLat = Number(baseFix.lat ?? baseFix.latitude ?? -62.8);
  const startLon = Number(baseFix.lon ?? baseFix.longitude ?? -60.5);

  const projected = projectPosition(startLat, startLon, heading, distanceNm);

  return {
    ...baseFix,
    lat: projected.lat,
    lon: projected.lon,
    latitude: projected.lat,
    longitude: projected.lon,
    speed_knots: speed,
    heading_deg: heading,
    heading,
    estimated: true,
    confidence: "ESTIMATED (DEAD RECKONING)",
    confidenceLevel: "low",
    basedOn: baseFix.timestamp || new Date(Date.now() - secondsSinceFix * 1000).toISOString(),
    secondsDeadReckoning: Math.round(secondsSinceFix),
    distanceProjectedNm: distanceNm.toFixed(2),
    label: `ESTIMATED POSITION (GPS SIGNAL LOST ${Math.round(secondsSinceFix)}s AGO)`,
  };
}

/**
 * Manually inject a fix (useful for simulated GPS loss in testing).
 */
export function setLastKnownFixForTesting(fix) {
  lastKnownFix = fix;
}

/**
 * Resets the dead-reckoning state.
 */
export function resetDeadReckoning() {
  lastKnownFix = null;
}
