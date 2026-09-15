/**
 * 3D Iceberg Geometry Engine
 * Authoritative 2D Outline Extrusion per shape_class (NOT a box, circle, or star)
 * Directly implements MANICE / International Ice Patrol (IIP) morphology
 */

// Refined, irregular normalized [0,1] x [0,1] point sets matching real IIP/MANICE classes
export const SHAPE_OUTLINES = {
  // Flat-topped elongated table shelf with sheer fracture edges and irregular corners
  TABULAR: [
    [0.04, 0.18], [0.28, 0.05], [0.68, 0.02], [0.96, 0.14], [1.00, 0.42],
    [0.94, 0.72], [0.82, 0.94], [0.45, 0.98], [0.16, 0.95], [0.02, 0.78],
    [0.00, 0.45]
  ],

  // Steep, sheer vertical cliff walls with flat top and angular asymmetric facets
  BLOCKY: [
    [0.08, 0.06], [0.55, 0.02], [0.92, 0.14], [1.00, 0.52], [0.90, 0.88],
    [0.52, 0.98], [0.14, 0.94], [0.02, 0.62], [0.04, 0.26]
  ],

  // Smoothly curved, rounded mound-like contour with gentle glacial erosion
  DOMED: [
    [0.22, 0.04], [0.50, 0.01], [0.78, 0.05], [0.94, 0.22], [1.00, 0.48],
    [0.93, 0.74], [0.76, 0.92], [0.50, 0.99], [0.24, 0.96], [0.08, 0.78],
    [0.01, 0.50], [0.06, 0.20]
  ],

  // Asymmetric wedge: high and wide at one end, tapering down to a narrow knife-edge
  WEDGE: [
    [0.02, 0.88], [0.06, 0.45], [0.18, 0.16], [0.45, 0.04], [0.85, 0.02],
    [1.00, 0.18], [0.86, 0.48], [0.65, 0.72], [0.38, 0.92], [0.12, 0.98]
  ],

  // Prominent sharp spires and central pyramid peaks radiating outwards
  PINNACLE: [
    [0.34, 0.02], [0.44, 0.24], [0.58, 0.04], [0.72, 0.28], [1.00, 0.40],
    [0.78, 0.60], [0.92, 0.86], [0.60, 0.74], [0.46, 1.00], [0.30, 0.80],
    [0.14, 0.92], [0.02, 0.54], [0.20, 0.36], [0.08, 0.16]
  ],

  // U-shaped central pool / eroded canyon between two flanking promontory horns
  DRYDOCK: [
    [0.08, 0.08], [0.34, 0.02], [0.36, 0.40], [0.64, 0.40], [0.66, 0.02],
    [0.92, 0.08], [1.00, 0.46], [0.88, 0.86], [0.52, 0.98], [0.22, 0.94],
    [0.06, 0.78], [0.00, 0.42]
  ],

  // Naturally irregular, asymmetric glacial fragment
  UNKNOWN: [
    [0.12, 0.12], [0.44, 0.02], [0.80, 0.06], [0.98, 0.32], [0.92, 0.68],
    [0.68, 0.96], [0.28, 0.98], [0.04, 0.68], [0.06, 0.32]
  ]
};

/**
 * Normalizes backend shape_class string into one of the 7 standard keys
 */
export function normalizeShapeClass(shapeClass) {
  if (!shapeClass) return "UNKNOWN";
  const s = String(shapeClass).trim().toUpperCase();
  if (s.includes("TABULAR") && !s.includes("NON")) return "TABULAR";
  if (s.includes("BLOCK")) return "BLOCKY";
  if (s.includes("DOME")) return "DOMED";
  if (s.includes("WEDGE")) return "WEDGE";
  if (s.includes("PINN")) return "PINNACLE";
  if (s.includes("DOCK")) return "DRYDOCK";
  return "UNKNOWN";
}

/**
 * Step 3: Scales normalized outline to real iceberg footprint dimensions (meters)
 * Centered on origin [0, 0]
 */
export function scaleOutlineToRealSize(normalizedOutline, length_m, width_m) {
  return normalizedOutline.map(([x, y]) => [
    (x - 0.5) * length_m,
    (y - 0.5) * width_m
  ]);
}

/**
 * Converts centered meter footprint to geographic [longitude, latitude] array for Cesium
 * @param {string} shapeClass - One of the 7 MANICE classes
 * @param {number} length_m - Real length in meters
 * @param {number} width_m - Real width in meters
 * @param {number} centerLat - Latitude center
 * @param {number} centerLon - Longitude center
 * @param {number} scale - Scale factor (1.0 for surface, 0.85 for tapered keel)
 * @returns {number[]} Array of [lon0, lat0, lon1, lat1, ...]
 */
export function getScaledIcebergOutline(shapeClass, length_m, width_m, centerLat, centerLon, scale = 1.0) {
  const normKey = normalizeShapeClass(shapeClass);
  const rawOutline = SHAPE_OUTLINES[normKey] || SHAPE_OUTLINES.UNKNOWN;
  
  const length = Number(length_m) || 1200;
  const width = Number(width_m) || 800;

  const latRad = (centerLat * Math.PI) / 180;
  const metersPerDegLat = 111320;
  const metersPerDegLon = 111320 * Math.cos(latRad);

  const flatCoords = [];
  rawOutline.forEach(([nx, ny]) => {
    // Length scaled along east-west axis, width scaled along north-south axis
    const eastMeters = (nx - 0.5) * length * scale;
    const northMeters = (ny - 0.5) * width * scale;

    const lon = centerLon + (eastMeters / metersPerDegLon);
    const lat = centerLat + (northMeters / metersPerDegLat);
    flatCoords.push(lon, lat);
  });

  return flatCoords;
}

/**
 * Steps 4 & 5: Material & Subsurface parameter derivation
 */
export function getIcebergMaterialProperties(iceberg) {
  const draftConfidence = typeof iceberg.draft_confidence === "number"
    ? iceberg.draft_confidence
    : typeof iceberg.confidence === "number"
      ? iceberg.confidence
      : 0.70;

  // Base confidence-driven opacity: 0.15 + (confidence * 0.55)
  let underwaterOpacity = 0.15 + (draftConfidence * 0.55);
  let underwaterColorHex = "#00e5ff"; // Glacial ice blue for subsurface keel

  const source = String(iceberg.source || "satellite").toLowerCase();

  if (source === "sonar_corrected") {
    // Solid, measurement-refined estimate
    underwaterOpacity = Math.min(0.90, underwaterOpacity + 0.25);
    underwaterColorHex = "#00e5ff"; // High confidence verified blue keel
  } else if (source === "crew_report") {
    // Amber / gold for newly discovered unvalidated report
    underwaterColorHex = "#ffaa00";
  }

  const hasDraft = iceberg.estimated_draft_m !== null &&
                   iceberg.estimated_draft_m !== undefined &&
                   !isNaN(Number(iceberg.estimated_draft_m)) &&
                   Number(iceberg.estimated_draft_m) > 0;

  return {
    hasDraft,
    underwaterOpacity,
    underwaterColorHex,
    draftConfidence,
    source
  };
}
