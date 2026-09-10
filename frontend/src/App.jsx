import { useEffect, useRef, useState, useCallback } from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import HazardPanel from "./HazardPanel";
import RoutePlanner from "./RoutePlanner";
import VoyageHUD from "./VoyageHUD";
import "./hazardPanel.css";
import "./App.css";

const BACKEND = typeof window !== "undefined" && window.location.origin.includes("http") 
  ? window.location.origin.replace(":3000", ":8000") 
  : "http://127.0.0.1:8000";

const WS_URL = typeof window !== "undefined" && window.location.host
  ? `ws://${window.location.host.replace(":3000", ":8000")}/ws/nmea`
  : "ws://127.0.0.1:8000/ws/nmea";

const DEMO_ICEBERG_ID = "ICB-2026-A23A";
const REVEAL_TRIGGER_KM = 8;
const NEARBY_RADIUS_KM = 50;
const ICEBERG_SURFACE_HEIGHT_M = 0;
const SHIP_HEIGHT_M = 14;

// Authentic coordinates in deep permanent open ocean channel (Drake Passage / Bransfield Corridor)
const FALLBACK_ICEBERGS = [
  {
    id: "ICB-2026-A23A",
    iceberg_id: "ICB-2026-A23A",
    lat: -62.70,
    lon: -59.80,
    length_m: 3800,
    width_m: 2400,
    freeboard_m: 42,
    estimated_draft_m: 315,
    confidence: 0.94,
    shape_class: "tabular",
    size_class: "very_large"
  },
  {
    id: "ICB-2026-B15A",
    iceberg_id: "ICB-2026-B15A",
    lat: -62.65,
    lon: -59.78,
    length_m: 1800,
    width_m: 1100,
    freeboard_m: 34,
    estimated_draft_m: 240,
    confidence: 0.89,
    shape_class: "tabular",
    size_class: "large"
  },
  {
    id: "ICB-2026-PINN",
    iceberg_id: "ICB-2026-PINN",
    lat: -62.78,
    lon: -59.35,
    length_m: 850,
    width_m: 520,
    freeboard_m: 58,
    estimated_draft_m: 195,
    confidence: 0.85,
    shape_class: "pinnacle",
    size_class: "medium"
  },
  {
    id: "ICB-2026-DOME",
    iceberg_id: "ICB-2026-DOME",
    lat: -62.85,
    lon: -58.45,
    length_m: 1100,
    width_m: 700,
    freeboard_m: 28,
    estimated_draft_m: 165,
    confidence: 0.91,
    shape_class: "domed",
    size_class: "medium"
  }
];

// Default Verified Open-Water Maritime Fairway Route
const DEFAULT_FAIRWAY_ROUTE = {
  route_id: "DEFAULT-FAIRWAY",
  name: "Bransfield Deep Ocean Fairway",
  distance_km: 197.6,
  points: [
    { longitude: -62.00, latitude: -62.90 }, // WP-1: Bransfield Deep Ocean Southwest
    { longitude: -61.20, latitude: -62.86 }, // WP-2: Bransfield Central Channel
    { longitude: -60.50, latitude: -62.83 }, // WP-3: North of Deception Island / Deep Fairway
    { longitude: -60.00, latitude: -62.77 }, // WP-4: Bransfield Open Fairway South of Hurd
    { longitude: -59.78, latitude: -62.72 }, // WP-5: Open Water Fairway Approach to ICB-2026-A23A
    { longitude: -59.35, latitude: -62.78 }, // WP-6: Deep Ocean Fairway South of Robert Island
    { longitude: -58.20, latitude: -62.88 }  // WP-7: Antarctic Sound Deep Water Approach
  ]
};

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = Cesium.Math.toRadians(lat2 - lat1);
  const dLon = Cesium.Math.toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(Cesium.Math.toRadians(lat1)) *
      Math.cos(Cesium.Math.toRadians(lat2)) *
      Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function calculateBearing(lat1, lon1, lat2, lon2) {
  const y = Math.sin(Cesium.Math.toRadians(lon2 - lon1)) * Math.cos(Cesium.Math.toRadians(lat2));
  const x =
    Math.cos(Cesium.Math.toRadians(lat1)) * Math.sin(Cesium.Math.toRadians(lat2)) -
    Math.sin(Cesium.Math.toRadians(lat1)) *
      Math.cos(Cesium.Math.toRadians(lat2)) *
      Math.cos(Cesium.Math.toRadians(lon2 - lon1));
  const brng = Cesium.Math.toDegrees(Math.atan2(y, x));
  return (brng + 360) % 360;
}

// Precomputed route distances and segment lengths
function getRouteDistances(points) {
  const segDistances = [];
  let totalDist = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const lat0 = Number(points[i].latitude ?? points[i].lat);
    const lon0 = Number(points[i].longitude ?? points[i].lon);
    const lat1 = Number(points[i + 1].latitude ?? points[i + 1].lat);
    const lon1 = Number(points[i + 1].longitude ?? points[i + 1].lon);
    const d = haversineKm(lat0, lon0, lat1, lon1);
    segDistances.push(d);
    totalDist += d;
  }
  return { segDistances, totalDist: Math.max(0.001, totalDist) };
}

// Evaluates nominal route coordinate at distance s (km) along the route
function getNominalPosAtDistance(points, segDistances, totalDist, s) {
  if (!points || points.length === 0) return null;
  const clampedS = Math.max(0, Math.min(totalDist, s));
  if (clampedS <= 0 || points.length === 1) {
    return {
      lat: Number(points[0].latitude ?? points[0].lat),
      lon: Number(points[0].longitude ?? points[0].lon),
      segIndex: 0
    };
  }
  if (clampedS >= totalDist) {
    const last = points[points.length - 1];
    return {
      lat: Number(last.latitude ?? last.lat),
      lon: Number(last.longitude ?? last.lon),
      segIndex: Math.max(0, points.length - 2)
    };
  }

  let accum = 0;
  for (let i = 0; i < segDistances.length; i++) {
    const segLen = segDistances[i];
    if (accum + segLen >= clampedS || i === segDistances.length - 1) {
      const t = segLen > 0 ? (clampedS - accum) / segLen : 0;
      const p0 = points[i];
      const p1 = points[i + 1];
      const lat0 = Number(p0.latitude ?? p0.lat);
      const lon0 = Number(p0.longitude ?? p0.lon);
      const lat1 = Number(p1.latitude ?? p1.lat);
      const lon1 = Number(p1.longitude ?? p1.lon);
      return {
        lat: lat0 + (lat1 - lat0) * t,
        lon: lon0 + (lon1 - lon0) * t,
        segIndex: i
      };
    }
    accum += segLen;
  }
  const last = points[points.length - 1];
  return {
    lat: Number(last.latitude ?? last.lat),
    lon: Number(last.longitude ?? last.lon),
    segIndex: Math.max(0, points.length - 2)
  };
}

// Determines the Closest Point of Approach (CPA) on the route centerline for an iceberg
function findIcebergCPAOnRoute(berg, points, segDistances, totalDist) {
  const bLat = Number(berg.current_latitude ?? berg.lat ?? berg.latitude);
  const bLon = Number(berg.current_longitude ?? berg.lon ?? berg.longitude);
  if (!Number.isFinite(bLat) || !Number.isFinite(bLon)) return null;

  // Search along route to find closest s
  const steps = Math.max(30, Math.ceil(totalDist / 2.0));
  let bestS = 0;
  let minD = Infinity;
  for (let i = 0; i <= steps; i++) {
    const s = (i / steps) * totalDist;
    const pos = getNominalPosAtDistance(points, segDistances, totalDist, s);
    const d = haversineKm(pos.lat, pos.lon, bLat, bLon);
    if (d < minD) {
      minD = d;
      bestS = s;
    }
  }

  // Refine around bestS
  const stepSize = totalDist / steps;
  let refineS = bestS;
  for (let ds = -stepSize; ds <= stepSize; ds += stepSize / 5) {
    const s = Math.max(0, Math.min(totalDist, bestS + ds));
    const pos = getNominalPosAtDistance(points, segDistances, totalDist, s);
    const d = haversineKm(pos.lat, pos.lon, bLat, bLon);
    if (d < minD) {
      minD = d;
      refineS = s;
    }
  }

  // Determine consistent steer direction at CPA
  const posA = getNominalPosAtDistance(points, segDistances, totalDist, Math.max(0, refineS - 1.5));
  const posB = getNominalPosAtDistance(points, segDistances, totalDist, Math.min(totalDist, refineS + 1.5));
  const fwdBearing = calculateBearing(posA.lat, posA.lon, posB.lat, posB.lon);
  const bergBearing = calculateBearing(posA.lat, posA.lon, bLat, bLon);
  let relAngle = (bergBearing - fwdBearing + 360) % 360;
  if (relAngle > 180) relAngle -= 360;

  // If iceberg is to Starboard (relAngle >= 0), steer Port (-1)
  // If iceberg is to Port (relAngle < 0), steer Starboard (+1)
  const steerSign = relAngle >= 0 ? -1 : 1;
  const steerDirection = steerSign === 1 ? "STARBOARD" : "PORT";

  const width = Number(berg.width_m) || 1200;
  const length = Number(berg.length_m) || 2000;
  const hazardRadiusKm = Math.max(10, (width + length) / 400 + 8);
  const isOnRoute = minD <= hazardRadiusKm;

  return {
    bergId: berg.iceberg_id || berg.id || "ICEBERG",
    bLat,
    bLon,
    s_cpa: refineS,
    cpa_dist_km: minD,
    steerSign,
    steerDirection,
    hazardRadiusKm,
    isOnRoute,
  };
}

// Computes smooth C^2 along-track deterrence curve across a wide transition window
function getSmoothRouteDeterrence(s, cpaList) {
  let totalOffsetKm = 0;
  let maxOffsetKm = 0;
  let activeTarget = null;
  let activeDirection = "STARBOARD";

  // Wide, gradual transition window: 24 km before and after obstacle (~48 km total transition)
  const L_trans = 24.0;

  cpaList.forEach((cpa) => {
    if (!cpa.isOnRoute) return;
    const deltaS = s - cpa.s_cpa;
    if (Math.abs(deltaS) < L_trans) {
      // C^2 Smoothstep bell taper: 0 at boundary with 0 derivative and 0 curvature
      const u = Math.abs(deltaS) / L_trans; // 0 at CPA, 1 at boundary
      const taper = Math.cos((Math.PI * u) / 2) ** 2;

      // 3.2 km gentle clearance deflection
      const ampKm = 3.2;
      const offset = cpa.steerSign * ampKm * taper;
      totalOffsetKm += offset;

      const absOffset = Math.abs(offset);
      if (absOffset > maxOffsetKm) {
        maxOffsetKm = absOffset;
        activeTarget = cpa.bergId;
        activeDirection = cpa.steerDirection;
      }
    }
  });

  return {
    signedOffsetKm: totalOffsetKm,
    absOffsetKm: maxOffsetKm,
    isDeterring: maxOffsetKm >= 0.15,
    deterTarget: activeTarget,
    deterDirection: activeDirection,
  };
}

// Evaluates the continuous, smoothly deterred coordinates at along-track distance s
function getDeterredPosAtDistance(points, segDistances, totalDist, cpaList, s) {
  const nomPos = getNominalPosAtDistance(points, segDistances, totalDist, s);
  if (!nomPos) return null;

  const det = getSmoothRouteDeterrence(s, cpaList);
  if (!det.isDeterring || Math.abs(det.signedOffsetKm) < 0.0001) {
    return {
      lat: nomPos.lat,
      lon: nomPos.lon,
      segIndex: nomPos.segIndex,
      isDeterring: false,
      deterOffsetKm: 0,
      deterDirection: det.deterDirection,
      deterTarget: null,
    };
  }

  // Compute smooth local track heading using a 3km preview window around s
  const s0 = Math.max(0, s - 1.5);
  const s1 = Math.min(totalDist, s + 1.5);
  const p0 = getNominalPosAtDistance(points, segDistances, totalDist, s0);
  const p1 = getNominalPosAtDistance(points, segDistances, totalDist, s1);
  const trackHeading = calculateBearing(p0.lat, p0.lon, p1.lat, p1.lon);

  // Normal vector pointing Starboard (90 deg clockwise)
  const rad = Cesium.Math.toRadians(trackHeading);
  const stbdX = Math.cos(rad);  // East component
  const stbdY = -Math.sin(rad); // North component

  const midLat = Cesium.Math.toRadians(nomPos.lat);
  const kx = 111.32 * Math.cos(midLat);
  const ky = 110.57;

  // Signed deflection: positive = starboard, negative = port
  const dispX = det.signedOffsetKm * stbdX;
  const dispY = det.signedOffsetKm * stbdY;

  return {
    lat: nomPos.lat + dispY / ky,
    lon: nomPos.lon + dispX / kx,
    segIndex: nomPos.segIndex,
    isDeterring: det.isDeterring,
    deterOffsetKm: det.absOffsetKm,
    deterDirection: det.deterDirection,
    deterTarget: det.deterTarget,
  };
}

// Master function returning the smooth vessel & route progress state
function getRouteProgressState(points, progress, icebergs = []) {
  if (!points || points.length === 0) return null;
  const { segDistances, totalDist } = getRouteDistances(points);
  const s = Math.max(0, Math.min(1.0, progress)) * totalDist;

  // Build CPAs for all icebergs
  const cpaList = (icebergs || []).map((berg) =>
    findIcebergCPAOnRoute(berg, points, segDistances, totalDist)
  ).filter(Boolean);

  const curPos = getDeterredPosAtDistance(points, segDistances, totalDist, cpaList, s);
  if (!curPos) return null;

  // Look ahead along the continuous deterred curve by 1.8 km to compute true smooth tangent heading
  const lookAheadS = Math.min(totalDist, s + 1.8);
  const lookAheadPos = getDeterredPosAtDistance(points, segDistances, totalDist, cpaList, lookAheadS);

  let heading = 0;
  if (lookAheadPos && (lookAheadPos.lat !== curPos.lat || lookAheadPos.lon !== curPos.lon)) {
    heading = calculateBearing(curPos.lat, curPos.lon, lookAheadPos.lat, lookAheadPos.lon);
  } else {
    const prevS = Math.max(0, s - 1.8);
    const prevPos = getDeterredPosAtDistance(points, segDistances, totalDist, cpaList, prevS);
    if (prevPos) {
      heading = calculateBearing(prevPos.lat, prevPos.lon, curPos.lat, curPos.lon);
    }
  }

  return {
    lat: curPos.lat,
    lon: curPos.lon,
    heading,
    currentSegmentIndex: curPos.segIndex,
    totalSegments: Math.max(1, points.length - 1),
    remainingDistKm: Math.max(0, totalDist - s),
    isDeterring: curPos.isDeterring,
    deterOffsetKm: curPos.deterOffsetKm,
    deterDirection: curPos.deterDirection,
    deterTarget: curPos.deterTarget,
  };
}

function pointToSegmentDistanceKm(pLat, pLon, aLat, aLon, bLat, bLon) {
  const dAB = haversineKm(aLat, aLon, bLat, bLon);
  if (dAB < 0.001) return haversineKm(pLat, pLon, aLat, aLon);

  const midLat = Cesium.Math.toRadians((aLat + bLat) / 2);
  const kx = 111.32 * Math.cos(midLat);
  const ky = 110.57;

  const ax = aLon * kx;
  const ay = aLat * ky;
  const bx = bLon * kx;
  const by = bLat * ky;
  const px = pLon * kx;
  const py = pLat * ky;

  const dx = bx - ax;
  const dy = by - ay;
  const segLenSq = dx * dx + dy * dy;
  if (segLenSq < 1e-6) return Math.hypot(px - ax, py - ay);

  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / segLenSq));
  const projX = ax + t * dx;
  const projY = ay + t * dy;
  return Math.hypot(px - projX, py - projY);
}

function minDistanceToRouteKm(lat, lon, points) {
  if (!points || points.length === 0) return Infinity;
  let minD = Infinity;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i];
    const p1 = points[i + 1];
    const lat0 = Number(p0.latitude ?? p0.lat);
    const lon0 = Number(p0.longitude ?? p0.lon);
    const lat1 = Number(p1.latitude ?? p1.lat);
    const lon1 = Number(p1.longitude ?? p1.lon);
    if (!Number.isFinite(lat0) || !Number.isFinite(lon0) || !Number.isFinite(lat1) || !Number.isFinite(lon1)) continue;
    const d = pointToSegmentDistanceKm(lat, lon, lat0, lon0, lat1, lon1);
    if (d < minD) minD = d;
  }
  return minD;
}

function getIcebergPosition(berg) {
  if (!berg) return null;
  const lat = Number(berg.current_latitude ?? berg.lat ?? berg.position?.lat ?? berg.demo_position?.lat);
  const lon = Number(berg.current_longitude ?? berg.lon ?? berg.position?.lon ?? berg.demo_position?.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { lat, lon };
}

function App() {
  const cesiumContainer = useRef(null);
  const viewerRef = useRef(null);
  const currentBaseLayerRef = useRef(null);

  const icebergPrimitiveRef = useRef([]);
  const icebergLabelRef = useRef([]);
  const allIcebergsRef = useRef(FALLBACK_ICEBERGS);
  const routeEntitiesRef = useRef([]);

  const shipRef = useRef({
    hull: null,
    bowWedge: null,
    safetyStripe: null,
    deck: null,
    bridge: null,
    funnel: null,
    mast: null,
    beacon: null,
    label: null,
    glowRing: null,
  });

  const [ship, setShip] = useState(null);
  const [gpsFix, setGpsFix] = useState(true);
  const [distanceKm, setDistanceKm] = useState(Infinity);
  const [nearbyIcebergs, setNearbyIcebergs] = useState(FALLBACK_ICEBERGS);
  const [closestIcebergId, setClosestIcebergId] = useState(null);
  const [routeStatus, setRouteStatus] = useState("DIRECT ROUTE");
  
  // 2-Day Early Warning Alert & Route Hazard States
  const [activeAlertIceberg, setActiveAlertIceberg] = useState(null);
  const [alertETA, setAlertETA] = useState(null);
  const [routeHazardIcebergs, setRouteHazardIcebergs] = useState([]);

  // Tactical Collision Avoidance & Course Deterrence State
  const [isDeterring, setIsDeterring] = useState(false);
  const [deterOffsetKm, setDeterOffsetKm] = useState(0);
  const [deterDirection, setDeterDirection] = useState("STARBOARD");
  const [deterTarget, setDeterTarget] = useState(null);

  // Active Navigation & Voyage Transit Simulation State
  const [activeRoute, setActiveRoute] = useState(DEFAULT_FAIRWAY_ROUTE);
  const activeRouteRef = useRef(DEFAULT_FAIRWAY_ROUTE);
  const [isVoyaging, setIsVoyaging] = useState(true);
  const isVoyagingRef = useRef(true);
  const [voyageProgress, setVoyageProgress] = useState(0.33);
  const [voyageSpeed, setVoyageSpeed] = useState(1);
  const [followShipCamera, setFollowShipCamera] = useState(false);
  const [voyageLeg, setVoyageLeg] = useState("WP-2 → WP-3");
  const [remainingDistKm, setRemainingDistKm] = useState(78.5);

  useEffect(() => {
    isVoyagingRef.current = isVoyaging;
  }, [isVoyaging]);

  useEffect(() => {
    activeRouteRef.current = activeRoute;
  }, [activeRoute]);

  // 3D Visual Studio State
  const [activePreset, setActivePreset] = useState("antarctica");
  const [activeBaseLayer, setActiveBaseLayer] = useState("arcgis_satellite");
  const [terrainExaggeration, setTerrainExaggeration] = useState(2.4);
  const [sunHour, setSunHour] = useState(15.0);
  const [enableAtmosphere, setEnableAtmosphere] = useState(true);
  const [enableShadows, setEnableShadows] = useState(true);
  const [enableWaterNormals, setEnableWaterNormals] = useState(true);
  const [isAutoOrbiting, setIsAutoOrbiting] = useState(false);
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);
  const [showHintBadge, setShowHintBadge] = useState(true);
  const [xrayMode, setXrayMode] = useState(false);

  // Helper for local 3D offset vectors
  const localOffset = useCallback((center, east, north, up) => {
    const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
    return Cesium.Matrix4.multiplyByPoint(
      transform,
      new Cesium.Cartesian3(east, north, up),
      new Cesium.Cartesian3()
    );
  }, []);

  const offsetLatLon = useCallback((lat, lon, eastMeters, northMeters) => {
    const metersPerDegreeLat = 111320;
    const metersPerDegreeLon = 111320 * Math.cos(Cesium.Math.toRadians(lat));
    return {
      lat: lat + northMeters / metersPerDegreeLat,
      lon: lon + eastMeters / metersPerDegreeLon,
    };
  }, []);

  // Update base imagery layers
  const setBaseImageryLayer = useCallback((layerType) => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    try {
      viewer.imageryLayers.removeAll();

      let provider;
      if (layerType === "arcgis_satellite") {
        // High-resolution photorealistic satellite imagery (global + Antarctica)
        provider = new Cesium.UrlTemplateImageryProvider({
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          maximumLevel: 19,
          credit: "© Esri, Maxar, Earthstar Geographics"
        });
      } else if (layerType === "relief_topo") {
        // High-contrast 3D elevation relief shading
        provider = new Cesium.UrlTemplateImageryProvider({
          url: "https://server.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}",
          maximumLevel: 16,
          credit: "© Esri, USGS, NGA, NASA"
        });
      } else if (layerType === "nasa_gibs") {
        // NASA GIBS Polar Blue Marble / MODIS Corrected Reflectance
        provider = new Cesium.UrlTemplateImageryProvider({
          url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/2024-01-15/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg",
          maximumLevel: 9,
          credit: "NASA EOSDIS GIBS"
        });
      } else if (layerType === "dark_tactical") {
        // High-contrast Tactical Dark Navigation Map
        provider = new Cesium.UrlTemplateImageryProvider({
          url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
          subdomains: ["a", "b", "c", "d"],
          credit: "© CARTO © OpenStreetMap"
        });
      }

      if (provider) {
        viewer.imageryLayers.addImageryProvider(provider);
      }

      setActiveBaseLayer(layerType);
    } catch (e) {
      console.warn("Error switching imagery layer:", e);
    }
  }, []);

  // Set Sun Lighting Time
  const updateSunTime = useCallback((hour) => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    setSunHour(hour);
    // Polar summer date (January) with user's selected hour
    const date = new Date(Date.UTC(2026, 0, 15, Math.floor(hour), Math.floor((hour % 1) * 60)));
    viewer.clock.currentTime = Cesium.JulianDate.fromDate(date);
  }, []);

  // Helper functions for effortless zooming and camera navigation
  const handleZoomIn = useCallback(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const camera = viewer.camera;
    const height = camera.positionCartographic.height;
    camera.zoomIn(Math.max(200, height * 0.45));
  }, []);

  const handleZoomOut = useCallback(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const camera = viewer.camera;
    const height = camera.positionCartographic.height;
    camera.zoomOut(Math.max(200, height * 0.45));
  }, []);

  const handleTiltToggle = useCallback(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const camera = viewer.camera;
    const currentPitch = Cesium.Math.toDegrees(camera.pitch);
    const targetPitch = currentPitch < -45 ? Cesium.Math.toRadians(-22) : Cesium.Math.toRadians(-68);
    camera.flyTo({
      destination: camera.position,
      orientation: {
        heading: camera.heading,
        pitch: targetPitch,
        roll: 0.0,
      },
      duration: 0.8,
    });
  }, []);

  // 3D Camera Presets - calibrated for seamless hackathon presentation
  const applyCameraPreset = useCallback((preset) => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    setActivePreset(preset);

    const shipLat = Number(ship?.lat ?? ship?.latitude ?? -62.83);
    const shipLon = Number(ship?.lon ?? ship?.longitude ?? -60.50);
    const shipHeading = Number(ship?.heading ?? ship?.heading_deg ?? ship?.heading_degrees ?? 90);

    if (preset === "ship") {
      setFollowShipCamera(true);

      const headingDeg = shipHeading;
      const headingRad = Cesium.Math.toRadians(headingDeg - 180);
      const dist = 920; // 920m behind vessel stern for high-impact cinematic third-person view
      const alt = 360;  // 360m elevation above sea level
      const metersPerDegLat = 111320;
      const metersPerDegLon = 111320 * Math.cos(Cesium.Math.toRadians(shipLat));

      const camLat = shipLat + (-Math.cos(headingRad) * dist) / metersPerDegLat;
      const camLon = shipLon + (-Math.sin(headingRad) * dist) / metersPerDegLon;

      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(camLon, camLat, alt),
        orientation: {
          heading: Cesium.Math.toRadians(headingDeg),
          pitch: Cesium.Math.toRadians(-21),
          roll: 0.0,
        },
        duration: 1.2,
      });
    } else if (preset === "antarctica") {
      setFollowShipCamera(false);
      // Photorealistic 3D perspective looking across Antarctica (Reference Image view)
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(-50.0, -82.0, 3600000),
        orientation: {
          heading: Cesium.Math.toRadians(35),
          pitch: Cesium.Math.toRadians(-46),
          roll: 0.0,
        },
        duration: 1.8,
      });
    } else if (preset === "earth") {
      setFollowShipCamera(false);
      // Realistic Whole Earth in Space looking toward Antarctica
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(shipLon, -45.0, 11500000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-70),
          roll: 0,
        },
        duration: 2.0,
      });
    }
  }, [ship]);

  // Create 3D vessel MV Vasiliy Golovnin with distinctive Polar Icebreaker livery
  const create3DShip = useCallback((viewer, position) => {
    if (!viewer || !position) return;
    const shipParts = shipRef.current;

    Object.values(shipParts).forEach((entity) => {
      if (entity) viewer.entities.remove(entity);
    });
    Object.keys(shipParts).forEach((key) => {
      shipParts[key] = null;
    });

    const lat = Number(position.lat ?? position.latitude);
    const lon = Number(position.lon ?? position.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const center = Cesium.Cartesian3.fromDegrees(lon, lat, SHIP_HEIGHT_M);
    const heading = Cesium.Math.toRadians(Number(position.heading ?? position.heading_degrees) || 0);

    const orientation = Cesium.Transforms.headingPitchRollQuaternion(
      center,
      new Cesium.HeadingPitchRoll(heading, 0, 0)
    );

    // 1. Ice-Class Main Hull - High-Visibility Polar Rescue Red
    shipParts.hull = viewer.entities.add({
      name: "MV Vasiliy Golovnin - Polar Hull",
      position: center,
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(54, 250, 32),
        material: Cesium.Color.fromCssColorString("#ff2a00"),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#ffcdd2"),
        outlineWidth: 2,
      },
    });

    // 2. Reinforced Icebreaker Knife Bow
    shipParts.bowWedge = viewer.entities.add({
      name: "Reinforced Icebreaker Bow",
      position: localOffset(center, 0, 115, 2),
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(42, 60, 30),
        material: Cesium.Color.fromCssColorString("#d50000"),
      },
    });

    // 3. High-Visibility Polar Maritime Yellow Safety Stripe
    shipParts.safetyStripe = viewer.entities.add({
      name: "Polar Safety Stripe",
      position: localOffset(center, 0, 0, 15),
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(56, 246, 4),
        material: Cesium.Color.fromCssColorString("#ffd600"),
      },
    });

    // 4. Clean Polar White Weather Deck & Superstructure
    shipParts.deck = viewer.entities.add({
      name: "Ship Deck",
      position: localOffset(center, 0, -20, 22),
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(42, 140, 14),
        material: Cesium.Color.fromCssColorString("#ffffff"),
      },
    });

    // 5. Tiered Navigation Bridge
    shipParts.bridge = viewer.entities.add({
      name: "Nav Bridge",
      position: localOffset(center, 0, 30, 33),
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(32, 38, 12),
        material: Cesium.Color.fromCssColorString("#f0f8ff"),
      },
    });

    // 6. Polar Exhaust Funnel
    shipParts.funnel = viewer.entities.add({
      name: "Exhaust Funnel",
      position: localOffset(center, 0, -45, 33),
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(16, 22, 14),
        material: Cesium.Color.fromCssColorString("#ff2a00"),
      },
    });

    // 7. Radar & Communications Mast - Polar Safety Yellow
    shipParts.mast = viewer.entities.add({
      name: "Radar Mast",
      position: localOffset(center, 0, 30, 46),
      cylinder: {
        length: 16,
        topRadius: 1.5,
        bottomRadius: 2.5,
        material: Cesium.Color.fromCssColorString("#ffd600"),
      },
    });

    // 8. Glowing 3D Navigation Strobe Beacon Point (Visible at any zoom level)
    shipParts.beacon = viewer.entities.add({
      name: "Masthead Strobe Beacon",
      position: localOffset(center, 0, 30, 56),
      point: {
        pixelSize: 14,
        color: Cesium.Color.fromCssColorString("#ff3d00"),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 3,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });

    // 9. Luminous Warm Amber Locator Ring & Wake Indicator
    shipParts.glowRing = viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat, 4),
      ellipse: {
        semiMajorAxis: 380.0,
        semiMinorAxis: 380.0,
        material: Cesium.Color.fromCssColorString("#ff6d00").withAlpha(0.24),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#ff9100").withAlpha(0.95),
        outlineWidth: 3,
      },
    });

    // 10. Distinctive Red Polar HUD Badge & Telemetry Label
    shipParts.label = viewer.entities.add({
      name: "Ship Label",
      position: localOffset(center, 0, 0, 75),
      label: {
        text: `🚢 MV VASILIY GOLOVNIN\n[ POLAR CLASS 4 | ${Number(position.speed_knots || 12.4).toFixed(1)} KN ]`,
        font: "bold 13px 'JetBrains Mono', sans-serif",
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
        showBackground: true,
        backgroundColor: Cesium.Color.fromCssColorString("#c62828").withAlpha(0.92),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
  }, [localOffset]);

  const update3DShip = useCallback((viewer, position) => {
    if (!viewer || !position) return;
    const lat = Number(position.lat ?? position.latitude);
    const lon = Number(position.lon ?? position.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const shipParts = shipRef.current;
    if (!shipParts.hull) {
      create3DShip(viewer, position);
      return;
    }

    const center = Cesium.Cartesian3.fromDegrees(lon, lat, SHIP_HEIGHT_M);
    const heading = Cesium.Math.toRadians(Number(position.heading ?? position.heading_degrees) || 0);

    const orientation = Cesium.Transforms.headingPitchRollQuaternion(
      center,
      new Cesium.HeadingPitchRoll(heading, 0, 0)
    );

    if (shipParts.hull) {
      shipParts.hull.position = center;
      shipParts.hull.orientation = orientation;
    }
    if (shipParts.bowWedge) {
      shipParts.bowWedge.position = localOffset(center, 0, 115, 2);
      shipParts.bowWedge.orientation = orientation;
    }
    if (shipParts.safetyStripe) {
      shipParts.safetyStripe.position = localOffset(center, 0, 0, 15);
      shipParts.safetyStripe.orientation = orientation;
    }
    if (shipParts.deck) {
      shipParts.deck.position = localOffset(center, 0, -20, 22);
      shipParts.deck.orientation = orientation;
    }
    if (shipParts.bridge) {
      shipParts.bridge.position = localOffset(center, 0, 30, 33);
      shipParts.bridge.orientation = orientation;
    }
    if (shipParts.funnel) {
      shipParts.funnel.position = localOffset(center, 0, -45, 33);
      shipParts.funnel.orientation = orientation;
    }
    if (shipParts.mast) {
      shipParts.mast.position = localOffset(center, 0, 30, 46);
    }
    if (shipParts.beacon) {
      shipParts.beacon.position = localOffset(center, 0, 30, 56);
    }
    if (shipParts.glowRing) {
      shipParts.glowRing.position = Cesium.Cartesian3.fromDegrees(lon, lat, 4);
    }
    if (shipParts.label) {
      shipParts.label.position = localOffset(center, 0, 0, 75);
      shipParts.label.label.text = `🚢 MV VASILIY GOLOVNIN\n[ POLAR CLASS 4 | ${Number(position.speed_knots || 12.4).toFixed(1)} KN ]`;
    }
  }, [create3DShip, localOffset]);

  // Render 3D Iceberg Models & White Dot Route Hazard Markers
  const render3DIcebergs = useCallback((viewer, icebergs, xray, currentRoute) => {
    if (!viewer || !Array.isArray(icebergs)) return;

    // Clear old iceberg primitives & labels
    icebergPrimitiveRef.current.forEach((prim) => viewer.scene.primitives.remove(prim));
    icebergPrimitiveRef.current = [];
    icebergLabelRef.current.forEach((entity) => viewer.entities.remove(entity));
    icebergLabelRef.current = [];

    const routePts = currentRoute?.points || activeRouteRef.current?.points || DEFAULT_FAIRWAY_ROUTE.points;

    icebergs.forEach((berg) => {
      const pos = getIcebergPosition(berg);
      if (!pos) return;
      const { lat, lon } = pos;
      const bergId = berg.iceberg_id ?? berg.id ?? "ICB-GENERIC";
      const width = Number(berg.width_m) || 1200;
      const length = Number(berg.length_m) || 2000;
      const freeboard = Number(berg.freeboard_m) || 45;
      const draft = Number(berg.estimated_draft_m) || (freeboard * 6);

      // Check if iceberg hazard zone intersects the navigation route
      const distToRoute = minDistanceToRouteKm(lat, lon, routePts);
      const hazardRadiusKm = Math.max(10, (width + length) / 400 + 8);
      const isOnRouteHazard = distToRoute <= hazardRadiusKm;

      // Create irregular polygonal ring for realistic tabular/pinnacled iceberg shape
      const numPoints = 12;
      const points = [];
      for (let i = 0; i < numPoints; i++) {
        const angle = (i / numPoints) * Math.PI * 2;
        const radiusNoise = 0.85 + 0.3 * Math.sin(i * 2.5);
        const east = Math.cos(angle) * (width / 2) * radiusNoise;
        const north = Math.sin(angle) * (length / 2) * radiusNoise;
        const pt = offsetLatLon(lat, lon, east, north);
        points.push(pt.lon, pt.lat);
      }

      // 3D Surface Iceberg Entity
      const surfaceBerg = viewer.entities.add({
        name: `${bergId} Surface`,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(points),
          extrudedHeight: freeboard,
          height: 0,
          material: Cesium.Color.fromCssColorString("#e0f4ff").withAlpha(0.95),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString("#ffffff"),
          shadows: Cesium.ShadowMode.ENABLED,
        },
      });

      // 3D Subsurface Keel (X-Ray Mode)
      if (xray) {
        const underwaterBerg = viewer.entities.add({
          name: `${bergId} Subsurface Keel`,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(points),
            extrudedHeight: 0,
            height: -draft,
            material: Cesium.Color.fromCssColorString("#00e5ff").withAlpha(0.35),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString("#00e5ff").withAlpha(0.8),
          },
        });
        icebergLabelRef.current.push(underwaterBerg);
      }

      // If iceberg hazard zone encompasses the route, render distinct WHITE DOT Hazard Marker
      if (isOnRouteHazard) {
        // 1. High-Visibility White Dot Point Marker
        const whiteDot = viewer.entities.add({
          name: `${bergId} Route Hazard White Dot`,
          position: Cesium.Cartesian3.fromDegrees(lon, lat, freeboard + 25),
          point: {
            pixelSize: 13,
            color: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.fromCssColorString("#00e5ff"),
            outlineWidth: 3,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        });

        // 2. Luminous White Hazard Zone Buffer Ring
        const whiteHazardRing = viewer.entities.add({
          name: `${bergId} Hazard Zone Buffer Ring`,
          position: Cesium.Cartesian3.fromDegrees(lon, lat, 4),
          ellipse: {
            semiMajorAxis: hazardRadiusKm * 1000,
            semiMinorAxis: hazardRadiusKm * 1000,
            material: Cesium.Color.WHITE.withAlpha(0.12),
            outline: true,
            outlineColor: Cesium.Color.WHITE.withAlpha(0.85),
            outlineWidth: 2,
          },
        });

        icebergLabelRef.current.push(whiteDot, whiteHazardRing);
      }

      // Iceberg Label & Telemetry Badge
      const label = viewer.entities.add({
        name: `${bergId} Label`,
        position: Cesium.Cartesian3.fromDegrees(lon, lat, freeboard + 95),
        label: {
          text: isOnRouteHazard 
            ? `⚪ ${bergId} (ROUTE HAZARD)\nFREEBOARD: ${freeboard}m | DRAFT: ${draft}m`
            : `🧊 ${bergId}\nFREEBOARD: ${freeboard}m | DRAFT: ${draft}m`,
          font: "bold 11px 'JetBrains Mono', sans-serif",
          fillColor: isOnRouteHazard ? Cesium.Color.WHITE : Cesium.Color.fromCssColorString("#e0f7fa"),
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          showBackground: true,
          backgroundColor: isOnRouteHazard
            ? Cesium.Color.fromCssColorString("#b71c1c").withAlpha(0.92)
            : Cesium.Color.fromCssColorString("#030e20").withAlpha(0.85),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });

      icebergLabelRef.current.push(surfaceBerg, label);
    });
  }, [offsetLatLon]);

  // Render Planned Route & Danger Corridors (with smooth Iceberg Deterrence Fairway)
  const renderRoutes = useCallback((viewer, icebergs) => {
    if (!viewer) return;
    routeEntitiesRef.current.forEach((e) => viewer.entities.remove(e));
    routeEntitiesRef.current = [];

    const waypoints = [
      { lon: -62.00, lat: -62.90 }, // WP-1: Bransfield Deep Ocean Southwest
      { lon: -61.20, lat: -62.86 }, // WP-2: Bransfield Central Channel
      { lon: -60.50, lat: -62.83 }, // WP-3: North of Deception Island / Deep Fairway
      { lon: -60.00, lat: -62.77 }, // WP-4: Bransfield Open Fairway South of Hurd
      { lon: -59.78, lat: -62.72 }, // WP-5: Open Water Fairway Approach to ICB-2026-A23A
      { lon: -59.35, lat: -62.78 }, // WP-6: Deep Ocean Fairway South of Robert Island
      { lon: -58.20, lat: -62.88 }  // WP-7: Antarctic Sound Deep Water Approach
    ];

    const wpPoints = waypoints.map((w) => ({ latitude: w.lat, longitude: w.lon }));
    const icebergsToUse = icebergs || allIcebergsRef.current || FALLBACK_ICEBERGS;

    // Sample finely along route so the fairway dynamically bends around on-route icebergs with silky-smooth continuity
    const sampledPositions = [];
    const numSamples = 200;
    for (let s = 0; s <= numSamples; s++) {
      const prog = s / numSamples;
      const pState = getRouteProgressState(wpPoints, prog, icebergsToUse);
      if (pState) {
        sampledPositions.push(Cesium.Cartesian3.fromDegrees(pState.lon, pState.lat, 10));
      }
    }

    const polyline = viewer.entities.add({
      name: "Optimal Antarctic Navigation Corridor (Tactical Avoidance Fairway)",
      polyline: {
        positions: sampledPositions,
        width: 5,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.3,
          color: Cesium.Color.fromCssColorString("#69f0ae"),
        }),
        clampToGround: true,
      },
    });

    routeEntitiesRef.current.push(polyline);

    // Add waypoint markers
    waypoints.forEach((wp, idx) => {
      const pin = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(wp.lon, wp.lat, 20),
        point: {
          pixelSize: 8,
          color: Cesium.Color.fromCssColorString("#69f0ae"),
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
        },
        label: {
          text: `WP-${idx + 1}`,
          font: "10px 'JetBrains Mono'",
          fillColor: Cesium.Color.fromCssColorString("#69f0ae"),
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(0, -10),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        }
      });
      routeEntitiesRef.current.push(pin);
    });
  }, []);

  // Update Ship Telemetry & Iceberg Proximity
  const updateShip = useCallback((nextShip) => {
    const viewer = viewerRef.current;
    if (!nextShip) return;

    const lat = Number(nextShip.lat ?? nextShip.latitude);
    const lon = Number(nextShip.lon ?? nextShip.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const formattedShip = {
      ...nextShip,
      lat,
      lon,
      speed_knots: nextShip.speed_knots ?? 12.4,
      heading: nextShip.heading ?? nextShip.heading_degrees ?? 135.0,
    };

    setShip(formattedShip);
    setGpsFix(true);

    if (viewer) {
      update3DShip(viewer, formattedShip);
    }

    // Calculate Logical Proximity Alert & Approaching Hazard Intercepts
    const currentSpeedKnots = formattedShip.speed_knots || 13.5;
    const speedKmh = Math.max(5, currentSpeedKnots * 1.852);
    const routePts = activeRouteRef.current?.points || DEFAULT_FAIRWAY_ROUTE.points;
    const { segDistances, totalDist } = getRouteDistances(routePts);

    // Current vessel along-track distance
    const sShip = Math.max(0, Math.min(1.0, voyageProgressRef.current || 0)) * totalDist;

    // Evaluate all icebergs with true along-track CPA and approach geometry
    const evaluated = allIcebergsRef.current
      .map((berg) => {
        const position = getIcebergPosition(berg);
        if (!position) return null;
        const { lat: bLat, lon: bLon } = position;
        const dDirectKm = haversineKm(lat, lon, bLat, bLon);
        const cpa = findIcebergCPAOnRoute(berg, routePts, segDistances, totalDist);
        if (!cpa) return null;

        // Along-track delta (positive = ahead, negative = passed)
        const deltaS = cpa.s_cpa - sShip;
        const hasPassed = deltaS < -2.0;
        const isApproachingAhead = deltaS >= -2.0;

        // True distance ahead to the obstacle along track or direct
        const distAheadKm = Math.max(0.2, isApproachingAhead ? (deltaS > 0 ? deltaS : dDirectKm) : dDirectKm);
        const etaHours = distAheadKm / speedKmh;
        const totalMinutes = Math.max(1, Math.round(etaHours * 60));
        const hrs = Math.floor(totalMinutes / 60);
        const mins = totalMinutes % 60;
        const formattedETA = hrs > 0 ? `${hrs}h ${mins}m` : `${mins} min`;

        // Proximity threat criteria:
        // 1. Iceberg is on the route fairway corridor (cpa.isOnRoute)
        // 2. Iceberg is AHEAD of vessel (has not been passed)
        // 3. Iceberg is NEARBY within active threat detection horizon (<= 22.0 km, ~50 min)
        const isNearbyAhead = cpa.isOnRoute && isApproachingAhead && distAheadKm <= 22.0;

        return {
          ...berg,
          id: berg.iceberg_id ?? berg.id,
          _distanceKm: dDirectKm,
          _distAheadKm: distAheadKm,
          _s_cpa: cpa.s_cpa,
          _deltaS: deltaS,
          _hasPassed: hasPassed,
          _isOnRoute: cpa.isOnRoute,
          _isNearbyAhead: isNearbyAhead,
          _etaHours: etaHours,
          _totalMinutes: totalMinutes,
          _formattedETA: formattedETA,
          _hazardRadiusKm: cpa.hazardRadiusKm,
        };
      })
      .filter(Boolean);

    const onRouteList = evaluated.filter((b) => b._isOnRoute);
    setRouteHazardIcebergs(onRouteList);

    // Upcoming threats strictly AHEAD and NEARBY (within 22 km)
    const nearbyThreats = evaluated
      .filter((b) => b._isNearbyAhead)
      .sort((a, b) => a._distAheadKm - b._distAheadKm);

    // Primary active threat ONLY exists if an iceberg is actually NEARBY AHEAD
    const activeThreat = nearbyThreats[0] || null;
    setActiveAlertIceberg(activeThreat);

    // Upcoming icebergs ahead on route (at any distance, for status display)
    const upcomingAhead = evaluated
      .filter((b) => b._isOnRoute && !b._hasPassed)
      .sort((a, b) => a._distAheadKm - b._distAheadKm);

    if (activeThreat) {
      setAlertETA({
        hours: activeThreat._etaHours,
        totalMinutes: activeThreat._totalMinutes,
        formattedETA: activeThreat._formattedETA,
        distanceKm: activeThreat._distAheadKm,
      });
      setClosestIcebergId(activeThreat.id);
      setDistanceKm(activeThreat._distAheadKm);

      const isDet = formattedShip.isDeterring;
      const detOff = formattedShip.deterOffsetKm || 3.2;
      const detDir = formattedShip.deterDirection || "STARBOARD";
      if (isDet) {
        setRouteStatus(`⚠️ AVOIDANCE ACTIVE: DETERRING +${detOff.toFixed(1)}km ${detDir} FROM ${activeThreat.id} (ETA ${activeThreat._formattedETA})`);
      } else {
        setRouteStatus(`⚠️ WARNING: ${activeThreat.id} AHEAD IN ${activeThreat._formattedETA} (${activeThreat._distAheadKm.toFixed(1)}km)`);
      }
    } else {
      setAlertETA(null);
      const nextUpcoming = upcomingAhead[0];
      if (nextUpcoming) {
        setClosestIcebergId(nextUpcoming.id);
        setDistanceKm(nextUpcoming._distAheadKm);
        setRouteStatus(`CORRIDOR CLEAR (NEXT ICEBERG ${nextUpcoming.id} IN ${nextUpcoming._distAheadKm.toFixed(1)} KM)`);
      } else {
        setClosestIcebergId(null);
        setDistanceKm(Infinity);
        setRouteStatus("CORRIDOR CLEAR (ALL HAZARDS CLEARED)");
      }
    }

    setNearbyIcebergs(evaluated.sort((a, b) => a._distanceKm - b._distanceKm));
  }, [update3DShip]);

  // Render Custom Calculated Fuel-Efficient Route & Standard Comparison
  const handleCustomRouteCalculated = useCallback((routeData) => {
    const viewer = viewerRef.current;
    if (!viewer || !routeData) return;

    // Clear previous route lines and waypoint pins
    routeEntitiesRef.current.forEach((e) => viewer.entities.remove(e));
    routeEntitiesRef.current = [];

    const feRoute = routeData.fuel_efficient_route;
    const stdRoute = routeData.standard_route;

    // 1. Render Fuel-Efficient Route (Glowing Neon Green Line with Deterrence Fairway)
    if (feRoute && Array.isArray(feRoute.points) && feRoute.points.length > 0) {
      const sampledPositions = [];
      const numSamples = 200;
      for (let s = 0; s <= numSamples; s++) {
        const prog = s / numSamples;
        const pState = getRouteProgressState(feRoute.points, prog, allIcebergsRef.current);
        if (pState) {
          sampledPositions.push(Cesium.Cartesian3.fromDegrees(pState.lon, pState.lat, 10));
        }
      }

      const fePolyline = viewer.entities.add({
        name: `Fuel-Efficient Route (${feRoute.distance_km} km) with Iceberg Avoidance`,
        polyline: {
          positions: sampledPositions,
          width: 5,
          material: new Cesium.PolylineGlowMaterialProperty({
            glowPower: 0.35,
            color: Cesium.Color.fromCssColorString("#69f0ae"),
          }),
          clampToGround: true,
        },
      });
      routeEntitiesRef.current.push(fePolyline);

      // Add Start, Intermediate & Goal Waypoint Pins
      feRoute.points.forEach((pt, idx) => {
        const isStart = idx === 0;
        const isDest = idx === feRoute.points.length - 1;
        const labelText = isStart ? "🟢 START" : isDest ? "🏁 DESTINATION" : `WP-${idx}`;
        const pinColor = isStart ? "#69f0ae" : isDest ? "#ffd740" : "#00e5ff";

        const pin = viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(pt.longitude, pt.latitude, 20),
          point: {
            pixelSize: isStart || isDest ? 10 : 6,
            color: Cesium.Color.fromCssColorString(pinColor),
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
          },
          label: {
            text: labelText,
            font: "bold 11px 'JetBrains Mono', sans-serif",
            fillColor: Cesium.Color.fromCssColorString(pinColor),
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 3,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -12),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        });
        routeEntitiesRef.current.push(pin);
      });

      // Update active route and start voyage along the newly calculated route
      setActiveRoute(feRoute);
      setVoyageProgress(0);
      setIsVoyaging(true);
      const startPt = feRoute.points[0];
      const nextPt = feRoute.points[1] || startPt;
      const initialHeading = calculateBearing(startPt.latitude, startPt.longitude, nextPt.latitude, nextPt.longitude);
      updateShip({
        lat: startPt.latitude,
        lon: startPt.longitude,
        heading: initialHeading,
        speed_knots: 12.5,
        isDeterring: false,
        deterOffsetKm: 0,
        deterDirection: "STARBOARD",
      });
      setVoyageLeg("WP-0 → WP-1");
      setRemainingDistKm(feRoute.distance_km || 100);

      // Refresh 3D icebergs and white dot hazard markers for the newly calculated route
      render3DIcebergs(viewer, allIcebergsRef.current, xrayMode, feRoute);
    }

    // 2. Render Standard Direct Route (Dashed / Thin Cyan Line for visual comparison)
    if (stdRoute && Array.isArray(stdRoute.points) && stdRoute.points.length > 0) {
      const stdPositions = stdRoute.points.map((p) => Cesium.Cartesian3.fromDegrees(p.longitude, p.latitude, 10));

      const stdPolyline = viewer.entities.add({
        name: `Standard Route (${stdRoute.distance_km} km)`,
        polyline: {
          positions: stdPositions,
          width: 3,
          material: new Cesium.PolylineDashMaterialProperty({
            color: Cesium.Color.fromCssColorString("#4fc3f7").withAlpha(0.65),
            dashLength: 16.0,
          }),
          clampToGround: true,
        },
      });
      routeEntitiesRef.current.push(stdPolyline);
    }

    // 3. Smoothly fly camera to frame the calculated route
    if (feRoute && feRoute.points && feRoute.points.length > 0) {
      const midIdx = Math.floor(feRoute.points.length / 2);
      const midPoint = feRoute.points[midIdx];
      const dist = feRoute.distance_km || 100;
      const targetAlt = Math.max(22000, dist * 1400);

      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(midPoint.longitude + 0.05, midPoint.latitude - 0.05, targetAlt),
        orientation: {
          heading: Cesium.Math.toRadians(325),
          pitch: Cesium.Math.toRadians(-40),
          roll: 0.0,
        },
        duration: 1.8,
      });
    }

    setRouteStatus(`OPTIMAL ROUTE (${routeData.fuel_saved_percent ?? 18.7}% FUEL SAVED)`);
  }, [updateShip, xrayMode, render3DIcebergs]);

  // Voyage Transit Animation Loop
  const voyageProgressRef = useRef(0.33);

  const handleStartVoyage = useCallback((route) => {
    const routeToUse = route || activeRoute;
    if (!routeToUse || !routeToUse.points || routeToUse.points.length < 2) return;

    setActiveRoute(routeToUse);
    if (voyageProgressRef.current >= 0.999) voyageProgressRef.current = 0;
    setVoyageProgress(voyageProgressRef.current);
    setIsVoyaging(true);

    const startState = getRouteProgressState(routeToUse.points, voyageProgressRef.current, allIcebergsRef.current);
    if (startState && viewerRef.current) {
      const pos = {
        lat: startState.lat,
        lon: startState.lon,
        heading: startState.heading,
        speed_knots: 13.5,
        isDeterring: startState.isDeterring,
        deterOffsetKm: startState.deterOffsetKm,
        deterDirection: startState.deterDirection,
        deterTarget: startState.deterTarget,
      };
      update3DShip(viewerRef.current, pos);
      updateShip(pos);
      setIsDeterring(startState.isDeterring);
      setDeterOffsetKm(startState.deterOffsetKm);
      setDeterDirection(startState.deterDirection);
      setDeterTarget(startState.deterTarget);
    }
  }, [activeRoute, updateShip, update3DShip]);

  const handlePauseVoyage = useCallback(() => {
    setIsVoyaging(false);
  }, []);

  const handleResetVoyage = useCallback(() => {
    setIsVoyaging(false);
    voyageProgressRef.current = 0;
    setVoyageProgress(0);
    if (activeRoute && activeRoute.points && activeRoute.points.length > 0) {
      const startState = getRouteProgressState(activeRoute.points, 0, allIcebergsRef.current);
      if (startState && viewerRef.current) {
        const pos = {
          lat: startState.lat,
          lon: startState.lon,
          heading: startState.heading,
          speed_knots: 0.0,
          isDeterring: startState.isDeterring,
          deterOffsetKm: startState.deterOffsetKm,
          deterDirection: startState.deterDirection,
          deterTarget: startState.deterTarget,
        };
        update3DShip(viewerRef.current, pos);
        updateShip(pos);
        setIsDeterring(startState.isDeterring);
        setDeterOffsetKm(startState.deterOffsetKm);
        setDeterDirection(startState.deterDirection);
        setDeterTarget(startState.deterTarget);
        setVoyageLeg("WP-0 → WP-1");
        setRemainingDistKm(activeRoute.distance_km || 100);
      }
    }
  }, [activeRoute, updateShip, update3DShip]);

  const handleProgressScrub = useCallback((newProgress) => {
    voyageProgressRef.current = newProgress;
    setVoyageProgress(newProgress);
    if (activeRoute && activeRoute.points && activeRoute.points.length > 0) {
      const state = getRouteProgressState(activeRoute.points, newProgress, allIcebergsRef.current);
      if (state && viewerRef.current) {
        const pos = {
          lat: state.lat,
          lon: state.lon,
          heading: state.heading,
          speed_knots: isVoyaging ? 14.5 : 0.0,
          isDeterring: state.isDeterring,
          deterOffsetKm: state.deterOffsetKm,
          deterDirection: state.deterDirection,
          deterTarget: state.deterTarget,
        };
        update3DShip(viewerRef.current, pos);
        updateShip(pos);
        setIsDeterring(state.isDeterring);
        setDeterOffsetKm(state.deterOffsetKm);
        setDeterDirection(state.deterDirection);
        setDeterTarget(state.deterTarget);
        setVoyageLeg(`WP-${state.currentSegmentIndex} → WP-${state.currentSegmentIndex + 1}`);
        setRemainingDistKm(state.remainingDistKm);
      }
    }
  }, [activeRoute, isVoyaging, updateShip, update3DShip]);

  const handleSetVoyageSpeed = useCallback((multiplier) => {
    setVoyageSpeed(multiplier);
  }, []);

  const handleToggleFollowCamera = useCallback(() => {
    setFollowShipCamera((prev) => !prev);
  }, []);

  // Voyage Transit Animation Loop
  useEffect(() => {
    if (!isVoyaging || !activeRoute || !activeRoute.points || activeRoute.points.length < 2) return;

    let lastTime = performance.now();
    let animId;
    let lastUiSync = 0;
    let lastBackendSync = 0;

    const tick = (now) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Hackathon Presentation Pacing: ~90s transit
      const totalKm = activeRoute.distance_km || 100;
      const nominalTimeSec = Math.max(60, totalKm * 0.90);
      const progressDelta = (dt / nominalTimeSec) * voyageSpeed;

      voyageProgressRef.current = (voyageProgressRef.current + progressDelta) % 1.0;
      const curProg = voyageProgressRef.current;

      const state = getRouteProgressState(activeRoute.points, curProg, allIcebergsRef.current);
      if (state && viewerRef.current) {
        const speedKnots = Number((12.5 + Math.sin(curProg * 12) * 1.5).toFixed(1));
        const currentShipPos = {
          lat: state.lat,
          lon: state.lon,
          heading: state.heading,
          speed_knots: speedKnots,
          isDeterring: state.isDeterring,
          deterOffsetKm: state.deterOffsetKm,
          deterDirection: state.deterDirection,
          deterTarget: state.deterTarget,
        };

        // Smooth GPU transform in Cesium (0 React overhead)
        update3DShip(viewerRef.current, currentShipPos);

        // Throttle React UI state updates to 4 times per second (250ms interval)
        if (now - lastUiSync > 250) {
          lastUiSync = now;
          setVoyageProgress(curProg);
          setVoyageLeg(`WP-${state.currentSegmentIndex} → WP-${state.currentSegmentIndex + 1}`);
          setRemainingDistKm(state.remainingDistKm);
          setIsDeterring(state.isDeterring);
          setDeterOffsetKm(state.deterOffsetKm);
          setDeterDirection(state.deterDirection);
          setDeterTarget(state.deterTarget);
          updateShip(currentShipPos);
        }

        // Elevated 3rd-Person Tactical Camera Tracking
        if (followShipCamera) {
          const viewer = viewerRef.current;
          const headingDeg = state.heading;
          const headingRad = Cesium.Math.toRadians(headingDeg - 180);
          const dist = 920;
          const alt = 360;
          const metersPerDegLat = 111320;
          const metersPerDegLon = 111320 * Math.cos(Cesium.Math.toRadians(state.lat));

          const camLat = state.lat + (-Math.cos(headingRad) * dist) / metersPerDegLat;
          const camLon = state.lon + (-Math.sin(headingRad) * dist) / metersPerDegLon;

          viewer.camera.setView({
            destination: Cesium.Cartesian3.fromDegrees(camLon, camLat, alt),
            orientation: {
              heading: Cesium.Math.toRadians(headingDeg),
              pitch: Cesium.Math.toRadians(-21),
              roll: 0.0,
            },
          });
        }

        // Sync position to backend every 4 seconds
        if (now - lastBackendSync > 4000) {
          lastBackendSync = now;
          fetch(`${BACKEND}/ship/position`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              latitude: state.lat,
              longitude: state.lon,
              speed_knots: speedKnots,
              heading_degrees: state.heading,
              timestamp: new Date().toISOString()
            })
          }).catch(() => {});
        }
      }

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isVoyaging, activeRoute, voyageSpeed, followShipCamera, updateShip, update3DShip]);

  // Load backend endpoints
  const loadBackendData = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND}/icebergs`);
      if (resp.ok) {
        const json = await resp.json();
        const array = json.data || json;
        if (Array.isArray(array) && array.length > 0) {
          allIcebergsRef.current = array;
          if (viewerRef.current) {
            render3DIcebergs(viewerRef.current, array, xrayMode);
            renderRoutes(viewerRef.current, array);
          }
        }
      }
    } catch (e) {
      console.warn("Backend icebergs endpoint offline, using realistic Antarctic dataset.");
    }

    try {
      const resp = await fetch(`${BACKEND}/ship/latest`);
      if (resp.ok) {
        const json = await resp.json();
        if (json.data && !isVoyagingRef.current) updateShip(json.data);
      }
    } catch (e) {
      console.warn("Backend ship endpoint offline, using default ship position.");
    }
  }, [render3DIcebergs, renderRoutes, updateShip, xrayMode]);

  // Initialize Cesium Engine
  useEffect(() => {
    let viewer;
    let websocket;
    let orbitInterval;

    async function initialise() {
      try {
        // High-resolution Cesium Viewer with dynamic lighting, shadows and HDR
        viewer = new Cesium.Viewer(cesiumContainer.current, {
          animation: false,
          timeline: false,
          baseLayerPicker: false,
          geocoder: false,
          homeButton: false,
          sceneModePicker: false,
          navigationHelpButton: false,
          fullscreenButton: false,
          infoBox: false,
          selectionIndicator: false,
          shadows: true,
          terrainShadows: Cesium.ShadowMode.ENABLED,
        });

        viewerRef.current = viewer;

        // Configure super-smooth scrolling and effortless mouse/trackpad camera controls
        const controller = viewer.scene.screenSpaceCameraController;
        controller.enableCollisionDetection = false; // prevents camera getting stuck on terrain when scrolling
        controller.zoomFactor = 3.5;                // responsive, effortless zooming
        controller.inertiaZoom = 0.82;              // smooth deceleration
        controller.inertiaSpin = 0.85;
        controller.inertiaTranslate = 0.85;
        controller.minimumZoomDistance = 50.0;
        controller.maximumZoomDistance = 50000000.0;

        // Set High-Resolution World Terrain (with per-vertex lighting normals for mountain relief)
        try {
          const terrainProvider = await Cesium.createWorldTerrainAsync({
            requestWaterMask: true,
            requestVertexNormals: true,
          });
          viewer.terrainProvider = terrainProvider;
        } catch (terrErr) {
          console.warn("World Terrain async init fallback to default terrain:", terrErr);
        }

        // Configure realistic 3D Globe environment
        const globe = viewer.scene.globe;
        globe.enableLighting = true;
        globe.terrainExaggeration = terrainExaggeration;
        globe.depthTestAgainstTerrain = true;
        globe.showGroundAtmosphere = true;
        globe.oceanNormalMapUrl = Cesium.buildModuleUrl("Assets/Textures/waterNormals.jpg");

        // High Dynamic Range & Atmosphere
        viewer.scene.highDynamicRange = true;
        if (viewer.scene.skyAtmosphere) {
          viewer.scene.skyAtmosphere.show = true;
        }
        if (viewer.scene.fog) {
          viewer.scene.fog.enabled = true;
          viewer.scene.fog.density = 0.00016;
        }

        // Apply initial base imagery layer (High-res ArcGIS Satellite)
        setBaseImageryLayer("arcgis_satellite");

        // Set Sun Lighting (polar summer angle)
        const initialDate = new Date(Date.UTC(2026, 0, 15, 15, 0));
        viewer.clock.currentTime = Cesium.JulianDate.fromDate(initialDate);

        // Initial Camera: Cinematic Third-Person Tactical View framed directly on vessel
        const initHeading = 90;
        const initHeadingRad = Cesium.Math.toRadians(initHeading - 180);
        const initDist = 920;
        const initAlt = 360;
        const initLat = -62.83;
        const initLon = -60.50;
        const metersPerDegLat = 111320;
        const metersPerDegLon = 111320 * Math.cos(Cesium.Math.toRadians(initLat));
        const initCamLat = initLat + (-Math.cos(initHeadingRad) * initDist) / metersPerDegLat;
        const initCamLon = initLon + (-Math.sin(initHeadingRad) * initDist) / metersPerDegLon;

        viewer.camera.setView({
          destination: Cesium.Cartesian3.fromDegrees(initCamLon, initCamLat, initAlt),
          orientation: {
            heading: Cesium.Math.toRadians(initHeading),
            pitch: Cesium.Math.toRadians(-21),
            roll: 0.0,
          },
        });

        // Initialize vessel directly on fairway route line (approaching WP-3 / WP-4)
        const initialFairwayState = getRouteProgressState(DEFAULT_FAIRWAY_ROUTE.points, 0.33, FALLBACK_ICEBERGS);
        if (initialFairwayState) {
          updateShip({
            lat: initialFairwayState.lat,
            lon: initialFairwayState.lon,
            heading: initialFairwayState.heading,
            speed_knots: 13.2,
            isDeterring: initialFairwayState.isDeterring,
            deterOffsetKm: initialFairwayState.deterOffsetKm,
            deterDirection: initialFairwayState.deterDirection,
            deterTarget: initialFairwayState.deterTarget,
          });
        }
        render3DIcebergs(viewer, FALLBACK_ICEBERGS, xrayMode);
        renderRoutes(viewer, FALLBACK_ICEBERGS);

        await loadBackendData();

        // Connect WebSocket for live NMEA telemetry (only overrides if user pauses voyage)
        try {
          websocket = new WebSocket(WS_URL);
          websocket.onmessage = (event) => {
            try {
              if (!isVoyagingRef.current) {
                const data = JSON.parse(event.data);
                updateShip(data);
              }
            } catch (err) {}
          };
        } catch (err) {}

        // Dismiss the hint badge on first interaction
        const handleInteraction = () => setShowHintBadge(false);
        const canvas = viewer.canvas;
        canvas.addEventListener("mousedown", handleInteraction, { once: true });
        canvas.addEventListener("touchstart", handleInteraction, { once: true });

      } catch (err) {
        console.error("Cesium initialisation error:", err);
      }
    }

    initialise();

    return () => {
      if (websocket) websocket.close();
      if (orbitInterval) clearInterval(orbitInterval);
      if (viewer && !viewer.isDestroyed()) viewer.destroy();
    };
  }, []);

  // Update terrain exaggeration dynamically
  useEffect(() => {
    if (viewerRef.current?.scene?.globe) {
      viewerRef.current.scene.globe.terrainExaggeration = terrainExaggeration;
    }
  }, [terrainExaggeration]);

  // Update atmosphere toggle
  useEffect(() => {
    if (viewerRef.current?.scene) {
      viewerRef.current.scene.globe.showGroundAtmosphere = enableAtmosphere;
      if (viewerRef.current.scene.skyAtmosphere) {
        viewerRef.current.scene.skyAtmosphere.show = enableAtmosphere;
      }
    }
  }, [enableAtmosphere]);

  // Update shadows toggle
  useEffect(() => {
    if (viewerRef.current?.scene) {
      viewerRef.current.shadows = enableShadows;
      viewerRef.current.terrainShadows = enableShadows ? Cesium.ShadowMode.ENABLED : Cesium.ShadowMode.DISABLED;
    }
  }, [enableShadows]);

  // Update X-ray rendering
  useEffect(() => {
    if (viewerRef.current) {
      render3DIcebergs(viewerRef.current, allIcebergsRef.current, xrayMode);
    }
  }, [xrayMode, render3DIcebergs]);

  // Handle smooth auto-orbit turntable
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    let animFrameId;
    if (isAutoOrbiting) {
      const rotate = () => {
        viewer.camera.rotateRight(0.002);
        animFrameId = requestAnimationFrame(rotate);
      };
      animFrameId = requestAnimationFrame(rotate);
    }

    return () => {
      if (animFrameId) cancelAnimationFrame(animFrameId);
    };
  }, [isAutoOrbiting]);

  return (
    <div className="app">
      <div ref={cesiumContainer} className="cesium-container" />

      {/* Top Left Title Bar */}
      <div className="title-panel glass">
        <div className="title-row">
          <span className="live-indicator-dot" />
          <h1>ANTARCTIC 3D TERRAIN INTELLIGENCE</h1>
        </div>
        <p>Dynamic Elevation Relief & Decision Support Engine</p>
      </div>

      {/* Quick Camera Preset Switcher (Top Center) */}
      <div className="preset-bar glass">
        <button
          className={`preset-btn ${activePreset === "ship" ? "active" : ""}`}
          onClick={() => applyCameraPreset("ship")}
          title="Cinematic 3D Third-Person Focus on MV Vasiliy Golovnin"
        >
          🎯 Focus Ship
        </button>
        <button
          className={`preset-btn ${activePreset === "antarctica" ? "active" : ""}`}
          onClick={() => applyCameraPreset("antarctica")}
          title="Whole Continent 3D Overview"
        >
          🇦🇶 Whole Antarctica
        </button>
        <button
          className={`preset-btn ${activePreset === "earth" ? "active" : ""}`}
          onClick={() => applyCameraPreset("earth")}
          title="Global Earth in Space"
        >
          🌍 Global Earth
        </button>
      </div>

      {/* Tactical Early Warning & Course Deterrence Overlay Banner */}
      {activeAlertIceberg && alertETA && (
        <div className="top-early-warning-banner glass pulse-warning-glow">
          <div className="banner-pulse-icon">🚨</div>
          <div className="banner-content">
            <div className="banner-title-line">
              <span className="banner-badge">⚠️ WARNING: ICEBERG NEARBY AHEAD</span>
              <span className="banner-heading">
                INTERCEPT IN {alertETA.formattedETA || `${Math.round(alertETA.hours * 60)} MIN`} ({alertETA.distanceKm.toFixed(1)} KM)
              </span>
            </div>
            <div className="banner-detail-line">
              <span>TARGET: <strong>{activeAlertIceberg.id}</strong> ({activeAlertIceberg.shape_class?.toUpperCase() || "TABULAR"})</span>
              <span className="banner-sep">•</span>
              {isDeterring ? (
                <span className="banner-deterring-text">
                  ⚡ <strong>COURSE DETERRENCE ACTIVE:</strong> VEERING +{deterOffsetKm.toFixed(1)} KM {deterDirection} TO DETOUR AROUND HAZARD
                </span>
              ) : (
                <span className="banner-standby-text">
                  🛡️ <strong>STATUS:</strong> TACTICAL AVOIDANCE VECTOR CALCULATED & ARMED
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Quick Navigation Floating Toolbar (Zoom +, Zoom -, Tilt 3D, Center Ship) */}
      <div className="quick-nav-toolbar glass">
        <button className="nav-tool-btn" onClick={handleZoomIn} title="Zoom In (+)">
          ➕
        </button>
        <button className="nav-tool-btn" onClick={handleZoomOut} title="Zoom Out (-)">
          ➖
        </button>
        <button className="nav-tool-btn" onClick={handleTiltToggle} title="Toggle 3D Elevation Tilt">
          📐 3D
        </button>
        <button className="nav-tool-btn" onClick={() => applyCameraPreset("ship")} title="Center on Vessel">
          🎯
        </button>
      </div>

      {/* "Click & Hold to Rotate" Reference UI Badge (Center bottom) */}
      {showHintBadge && (
        <div className="rotate-hint-badge" onClick={() => setShowHintBadge(false)}>
          <div className="hand-icon-anim">👆</div>
          <div className="hint-text">
            <strong>click & hold</strong>
            <span>to rotate 3D view</span>
          </div>
        </div>
      )}

      {/* 3D Visual Studio HUD (Bottom Left) */}
      <div className={`visual-studio-panel glass ${isPanelCollapsed ? "collapsed" : ""}`}>
        <div className="studio-header" onClick={() => setIsPanelCollapsed(!isPanelCollapsed)}>
          <span className="studio-title">⚙️ 3D VISUAL STUDIO & ELEVATION</span>
          <button className="collapse-btn">{isPanelCollapsed ? "▲ Expand" : "▼ Collapse"}</button>
        </div>

        {!isPanelCollapsed && (
          <div className="studio-body">
            {/* Imagery Base Layer Selector */}
            <div className="studio-section">
              <label className="section-label">MAP TEXTURE & IMAGERY</label>
              <div className="layer-grid">
                <button
                  className={`layer-btn ${activeBaseLayer === "arcgis_satellite" ? "active" : ""}`}
                  onClick={() => setBaseImageryLayer("arcgis_satellite")}
                >
                  🛰️ True Satellite
                </button>
                <button
                  className={`layer-btn ${activeBaseLayer === "relief_topo" ? "active" : ""}`}
                  onClick={() => setBaseImageryLayer("relief_topo")}
                >
                  🏔️ 3D Hillshade
                </button>
                <button
                  className={`layer-btn ${activeBaseLayer === "nasa_gibs" ? "active" : ""}`}
                  onClick={() => setBaseImageryLayer("nasa_gibs")}
                >
                  ❄️ NASA Polar
                </button>
                <button
                  className={`layer-btn ${activeBaseLayer === "dark_tactical" ? "active" : ""}`}
                  onClick={() => setBaseImageryLayer("dark_tactical")}
                >
                  🌌 Dark Tactical
                </button>
              </div>
            </div>

            {/* 3D Relief Exaggeration Slider */}
            <div className="studio-section">
              <div className="slider-label-row">
                <span className="section-label">3D TERRAIN RELIEF</span>
                <span className="slider-val">{terrainExaggeration.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="4.5"
                step="0.1"
                value={terrainExaggeration}
                onChange={(e) => setTerrainExaggeration(parseFloat(e.target.value))}
                className="studio-slider"
              />
            </div>

            {/* Sun Angle / Shadow Direction Slider */}
            <div className="studio-section">
              <div className="slider-label-row">
                <span className="section-label">POLAR SUNLIGHT & SHADOWS</span>
                <span className="slider-val">{Math.floor(sunHour)}:{Math.floor((sunHour % 1) * 60).toString().padStart(2, "0")} UTC</span>
              </div>
              <input
                type="range"
                min="0"
                max="23.9"
                step="0.25"
                value={sunHour}
                onChange={(e) => updateSunTime(parseFloat(e.target.value))}
                className="studio-slider"
              />
            </div>

            {/* Quick Feature Toggles */}
            <div className="studio-toggles">
              <button
                className={`toggle-pill ${isAutoOrbiting ? "active" : ""}`}
                onClick={() => setIsAutoOrbiting(!isAutoOrbiting)}
              >
                🔄 {isAutoOrbiting ? "Stop Orbit" : "Auto Orbit"}
              </button>
              <button
                className={`toggle-pill ${enableShadows ? "active" : ""}`}
                onClick={() => setEnableShadows(!enableShadows)}
              >
                🌑 {enableShadows ? "Shadows ON" : "Shadows OFF"}
              </button>
              <button
                className={`toggle-pill ${enableAtmosphere ? "active" : ""}`}
                onClick={() => setEnableAtmosphere(!enableAtmosphere)}
              >
                ✨ {enableAtmosphere ? "Atmosphere" : "No Atmos"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Fuel-Efficient Route Planner Widget (Top Left below Title) */}
      <RoutePlanner
        shipPosition={ship}
        onRouteCalculated={handleCustomRouteCalculated}
        backendUrl={BACKEND}
        onStartVoyage={handleStartVoyage}
        isVoyaging={isVoyaging}
        onPauseVoyage={handlePauseVoyage}
      />

      {/* Right Telemetry & Hazard Panel */}
      <HazardPanel
        ship={ship}
        gpsFix={gpsFix}
        distanceKm={distanceKm}
        routeStatus={routeStatus}
        nearbyIcebergs={nearbyIcebergs}
        closestIcebergId={closestIcebergId}
        activeAlertIceberg={activeAlertIceberg}
        alertETA={alertETA}
        routeHazardIcebergs={routeHazardIcebergs}
        isDeterring={isDeterring}
        deterOffsetKm={deterOffsetKm}
        deterDirection={deterDirection}
        deterTarget={deterTarget}
      />

      {/* Floating Active Voyage HUD (Bottom Center) */}
      <VoyageHUD
        activeRoute={activeRoute}
        isVoyaging={isVoyaging}
        voyageProgress={voyageProgress}
        speedMultiplier={voyageSpeed}
        followCamera={followShipCamera}
        currentSpeedKnots={ship?.speed_knots ?? 14.5}
        currentHeading={ship?.heading ?? 125}
        currentLeg={voyageLeg}
        remainingDistKm={remainingDistKm}
        activeAlertIceberg={activeAlertIceberg}
        alertETA={alertETA}
        isDeterring={isDeterring}
        deterOffsetKm={deterOffsetKm}
        deterDirection={deterDirection}
        onTogglePlay={() => {
          if (isVoyaging) {
            handlePauseVoyage();
          } else {
            handleStartVoyage();
          }
        }}
        onReset={handleResetVoyage}
        onProgressScrub={handleProgressScrub}
        onSetSpeed={handleSetVoyageSpeed}
        onToggleFollowCamera={handleToggleFollowCamera}
      />
    </div>
  );
}

export default App;
