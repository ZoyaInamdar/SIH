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
    estimated_draft_m: 280,
    confidence: 0.94,
    shape_class: "tabular",
    size_class: "very_large"
  },
  {
    id: "ICB-2026-B15A",
    iceberg_id: "ICB-2026-B15A",
    lat: -62.90,
    lon: -59.10,
    length_m: 1600,
    width_m: 950,
    freeboard_m: 32,
    estimated_draft_m: 210,
    confidence: 0.88,
    shape_class: "tabular",
    size_class: "large"
  },
  {
    id: "ICB-2026-PINN",
    iceberg_id: "ICB-2026-PINN",
    lat: -62.35,
    lon: -61.00,
    length_m: 750,
    width_m: 480,
    freeboard_m: 55,
    estimated_draft_m: 195,
    confidence: 0.81,
    shape_class: "pinnacled",
    size_class: "medium"
  }
];

// Default Verified Open-Water Maritime Fairway Route
const DEFAULT_FAIRWAY_ROUTE = {
  route_id: "DEFAULT-FAIRWAY",
  name: "Bransfield Deep Ocean Fairway",
  distance_km: 118.5,
  points: [
    { longitude: -62.00, latitude: -62.10 },
    { longitude: -61.20, latitude: -62.30 },
    { longitude: -60.50, latitude: -62.44 },
    { longitude: -60.06, latitude: -62.48 },
    { longitude: -59.86, latitude: -62.68 },
    { longitude: -59.50, latitude: -62.80 },
    { longitude: -58.20, latitude: -62.88 }
  ]
};

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

function getRouteProgressState(points, progress) {
  if (!points || points.length === 0) return null;
  if (points.length === 1 || progress <= 0) {
    const p0 = points[0];
    const p1 = points[1] || points[0];
    const heading = calculateBearing(p0.latitude, p0.longitude, p1.latitude, p1.longitude);
    return {
      lat: p0.latitude,
      lon: p0.longitude,
      heading,
      currentSegmentIndex: 0,
      totalSegments: Math.max(1, points.length - 1),
      remainingDistKm: 0
    };
  }

  // Calculate cumulative distances
  const distances = [];
  let totalDist = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const d = haversineKm(points[i].latitude, points[i].longitude, points[i + 1].latitude, points[i + 1].longitude);
    distances.push(d);
    totalDist += d;
  }

  if (progress >= 1.0) {
    const pLast = points[points.length - 1];
    const pPrev = points[points.length - 2] || pLast;
    const heading = calculateBearing(pPrev.latitude, pPrev.longitude, pLast.latitude, pLast.longitude);
    return {
      lat: pLast.latitude,
      lon: pLast.longitude,
      heading,
      currentSegmentIndex: points.length - 2,
      totalSegments: points.length - 1,
      remainingDistKm: 0
    };
  }

  const targetDist = progress * totalDist;
  let accumulated = 0;
  for (let i = 0; i < distances.length; i++) {
    const segLen = distances[i];
    if (accumulated + segLen >= targetDist || i === distances.length - 1) {
      const segT = segLen > 0 ? (targetDist - accumulated) / segLen : 0;
      const p0 = points[i];
      const p1 = points[i + 1];
      const lat = p0.latitude + (p1.latitude - p0.latitude) * segT;
      const lon = p0.longitude + (p1.longitude - p0.longitude) * segT;
      const heading = calculateBearing(p0.latitude, p0.longitude, p1.latitude, p1.longitude);
      return {
        lat,
        lon,
        heading,
        currentSegmentIndex: i,
        totalSegments: points.length - 1,
        remainingDistKm: Math.max(0, totalDist - targetDist)
      };
    }
    accumulated += segLen;
  }

  const pLast = points[points.length - 1];
  return {
    lat: pLast.latitude,
    lon: pLast.longitude,
    heading: 0,
    currentSegmentIndex: points.length - 2,
    totalSegments: points.length - 1,
    remainingDistKm: 0
  };
}

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
  
  // Active Navigation & Voyage Transit Simulation State
  const [activeRoute, setActiveRoute] = useState(DEFAULT_FAIRWAY_ROUTE);
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

    const shipLat = Number(ship?.lat ?? -62.50);
    const shipLon = Number(ship?.lon ?? -60.50);

    if (preset === "ship") {
      // Elevated 3D Third-Person Tactical View (Overlooking vessel and fairway)
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(shipLon + 0.035, shipLat - 0.045, 4800),
        orientation: {
          heading: Cesium.Math.toRadians(325),
          pitch: Cesium.Math.toRadians(-42),
          roll: 0.0,
        },
        duration: 1.4,
      });
    } else if (preset === "route") {
      // 30km Tactical Navigation Corridor (Ship, Route line, Waypoints & Hazards)
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(shipLon + 0.08, shipLat - 0.07, 14500),
        orientation: {
          heading: Cesium.Math.toRadians(325),
          pitch: Cesium.Math.toRadians(-36),
          roll: 0.0,
        },
        duration: 1.6,
      });
    } else if (preset === "iceberg") {
      // Zoomed in on A23-A Tabular Iceberg hazard with 3D elevation & draft
      const demo = allIcebergsRef.current[0] || { lat: -62.70, lon: -59.80 };
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(demo.lon + 0.035, demo.lat - 0.028, 1800),
        orientation: {
          heading: Cesium.Math.toRadians(330),
          pitch: Cesium.Math.toRadians(-28),
          roll: 0.0,
        },
        duration: 1.5,
      });
    } else if (preset === "relief") {
      // Antarctic Peninsula 3D Mountain Coast (Shows 3D relief texture around ship sector)
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(shipLon + 0.45, shipLat - 0.35, 75000),
        orientation: {
          heading: Cesium.Math.toRadians(320),
          pitch: Cesium.Math.toRadians(-38),
          roll: 0.0,
        },
        duration: 1.8,
      });
    } else if (preset === "antarctica") {
      // Photorealistic 3D perspective looking across Antarctica (Reference Image view)
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(-50.0, -82.0, 3600000),
        orientation: {
          heading: Cesium.Math.toRadians(35),
          pitch: Cesium.Math.toRadians(-46),
          roll: 0.0,
        },
        duration: 2.0,
      });
    } else if (preset === "earth") {
      // Realistic Whole Earth in Space looking toward Antarctica
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(shipLon, -45.0, 11500000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-70),
          roll: 0,
        },
        duration: 2.2,
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

  // Render 3D Iceberg Models
  const render3DIcebergs = useCallback((viewer, icebergs, xray) => {
    if (!viewer || !Array.isArray(icebergs)) return;

    // Clear old iceberg primitives & labels
    icebergPrimitiveRef.current.forEach((prim) => viewer.scene.primitives.remove(prim));
    icebergPrimitiveRef.current = [];
    icebergLabelRef.current.forEach((entity) => viewer.entities.remove(entity));
    icebergLabelRef.current = [];

    icebergs.forEach((berg) => {
      const pos = getIcebergPosition(berg);
      if (!pos) return;
      const { lat, lon } = pos;
      const bergId = berg.iceberg_id ?? berg.id ?? "ICB-GENERIC";
      const width = Number(berg.width_m) || 1200;
      const length = Number(berg.length_m) || 2000;
      const freeboard = Number(berg.freeboard_m) || 45;
      const draft = Number(berg.estimated_draft_m) || (freeboard * 6);

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

      // Iceberg Label & Telemetry Badge
      const label = viewer.entities.add({
        name: `${bergId} Label`,
        position: Cesium.Cartesian3.fromDegrees(lon, lat, freeboard + 90),
        label: {
          text: `🧊 ${bergId}\nFREEBOARD: ${freeboard}m | DRAFT: ${draft}m`,
          font: "bold 11px 'JetBrains Mono', sans-serif",
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          showBackground: true,
          backgroundColor: Cesium.Color.fromCssColorString("#030e20").withAlpha(0.85),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });

      icebergLabelRef.current.push(surfaceBerg, label);
    });
  }, [offsetLatLon]);

  // Render Planned Route & Danger Corridors
  const renderRoutes = useCallback((viewer) => {
    if (!viewer) return;
    routeEntitiesRef.current.forEach((e) => viewer.entities.remove(e));
    routeEntitiesRef.current = [];

    const waypoints = [
      { lon: -62.00, lat: -62.10 }, // Drake Passage Deep Open Ocean
      { lon: -61.20, lat: -62.30 }, // South Shetland Outer Channel
      { lon: -60.50, lat: -62.44 }, // Drake Passage Deep Blue Ocean Water (North of Livingston)
      { lon: -60.06, lat: -62.48 }, // English Strait Approach
      { lon: -59.86, lat: -62.68 }, // Natural Marine Channel Passage
      { lon: -59.50, lat: -62.80 }, // Bransfield Strait Deep Sea
      { lon: -58.20, lat: -62.88 }  // Antarctic Sound Approach (Open Water)
    ];

    const polyline = viewer.entities.add({
      name: "Optimal Antarctic Navigation Corridor",
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(waypoints.flatMap(w => [w.lon, w.lat])),
        width: 4,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.25,
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

    const calculated = allIcebergsRef.current
      .map((berg) => {
        const position = getIcebergPosition(berg);
        if (!position) return null;
        const d = haversineKm(lat, lon, position.lat, position.lon);
        return { ...berg, id: berg.iceberg_id ?? berg.id, _distanceKm: d };
      })
      .filter(Boolean)
      .filter((berg) => berg._distanceKm <= NEARBY_RADIUS_KM)
      .sort((a, b) => a._distanceKm - b._distanceKm);

    setNearbyIcebergs(calculated);
    const closest = calculated[0];
    setClosestIcebergId(closest?.id ?? null);

    if (closest) {
      const distance = closest._distanceKm;
      setDistanceKm(distance);
      if (distance <= REVEAL_TRIGGER_KM) {
        setRouteStatus("WARNING AREA ACTIVE");
      } else {
        setRouteStatus("DIRECT ROUTE");
      }
    } else {
      setDistanceKm(Infinity);
      setRouteStatus("NO ACTIVE ICEBERG HAZARD");
    }
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

    // 1. Render Fuel-Efficient Route (Glowing Neon Green Line)
    if (feRoute && Array.isArray(feRoute.points) && feRoute.points.length > 0) {
      const positions = feRoute.points.map((p) => Cesium.Cartesian3.fromDegrees(p.longitude, p.latitude, 10));

      const fePolyline = viewer.entities.add({
        name: `Fuel-Efficient Route (${feRoute.distance_km} km)`,
        polyline: {
          positions,
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
        speed_knots: 12.5
      });
      setVoyageLeg("WP-0 → WP-1");
      setRemainingDistKm(feRoute.distance_km || 100);
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
  }, [updateShip]);

  // Voyage Control Actions
  const handleStartVoyage = useCallback((route) => {
    const routeToUse = route || activeRoute;
    if (!routeToUse || !routeToUse.points || routeToUse.points.length < 2) return;

    setActiveRoute(routeToUse);
    setVoyageProgress((prev) => (prev >= 0.999 ? 0 : prev));
    setIsVoyaging(true);

    if (voyageProgress <= 0.001 || voyageProgress >= 0.999) {
      const startState = getRouteProgressState(routeToUse.points, 0);
      if (startState) {
        updateShip({
          lat: startState.lat,
          lon: startState.lon,
          heading: startState.heading,
          speed_knots: 13.5,
        });
      }
    }
  }, [activeRoute, voyageProgress, updateShip]);

  const handlePauseVoyage = useCallback(() => {
    setIsVoyaging(false);
  }, []);

  const handleResetVoyage = useCallback(() => {
    setIsVoyaging(false);
    setVoyageProgress(0);
    if (activeRoute && activeRoute.points && activeRoute.points.length > 0) {
      const startState = getRouteProgressState(activeRoute.points, 0);
      if (startState) {
        updateShip({
          lat: startState.lat,
          lon: startState.lon,
          heading: startState.heading,
          speed_knots: 0.0,
        });
        setVoyageLeg("WP-0 → WP-1");
        setRemainingDistKm(activeRoute.distance_km || 100);
      }
    }
  }, [activeRoute, updateShip]);

  const handleProgressScrub = useCallback((newProgress) => {
    setVoyageProgress(newProgress);
    if (activeRoute && activeRoute.points && activeRoute.points.length > 0) {
      const state = getRouteProgressState(activeRoute.points, newProgress);
      if (state) {
        updateShip({
          lat: state.lat,
          lon: state.lon,
          heading: state.heading,
          speed_knots: isVoyaging ? 14.5 : 0.0,
        });
        setVoyageLeg(`WP-${state.currentSegmentIndex} → WP-${state.currentSegmentIndex + 1}`);
        setRemainingDistKm(state.remainingDistKm);
      }
    }
  }, [activeRoute, isVoyaging, updateShip]);

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
    let lastBackendSync = 0;

    const tick = (now) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Hackathon Presentation Pacing:
      // A ~100 km transit takes ~90 seconds at 1x speed so judges can follow every leg
      const totalKm = activeRoute.distance_km || 100;
      const nominalTimeSec = Math.max(60, totalKm * 0.90);
      const progressDelta = (dt / nominalTimeSec) * voyageSpeed;

      setVoyageProgress((prev) => {
        let next = prev + progressDelta;
        if (next >= 1.0) {
          next = 0.0;
        }

        const state = getRouteProgressState(activeRoute.points, next);
        if (state) {
          const speedKnots = Number((12.5 + Math.sin(next * 12) * 1.5).toFixed(1));
          updateShip({
            lat: state.lat,
            lon: state.lon,
            heading: state.heading,
            speed_knots: speedKnots,
          });
          setVoyageLeg(`WP-${state.currentSegmentIndex} → WP-${state.currentSegmentIndex + 1}`);
          setRemainingDistKm(state.remainingDistKm);

          // Elevated 3rd-Person Tactical Camera Tracking
          if (followShipCamera && viewerRef.current) {
            const viewer = viewerRef.current;
            const headingDeg = state.heading;
            const headingRad = Cesium.Math.toRadians(headingDeg - 180);
            const dist = 6500;  // 6.5 km pulled back in 3rd person
            const alt = 4800;   // 4.8 km altitude overlooking the vessel
            const metersPerDegLat = 111320;
            const metersPerDegLon = 111320 * Math.cos(Cesium.Math.toRadians(state.lat));

            const camLat = state.lat + (-Math.cos(headingRad) * dist) / metersPerDegLat;
            const camLon = state.lon + (-Math.sin(headingRad) * dist) / metersPerDegLon;

            viewer.camera.setView({
              destination: Cesium.Cartesian3.fromDegrees(camLon, camLat, alt),
              orientation: {
                heading: Cesium.Math.toRadians(headingDeg),
                pitch: Cesium.Math.toRadians(-42), // Elevated third-person angle
                roll: 0.0,
              },
            });
          }

          // Sync position to backend every 3 seconds
          if (now - lastBackendSync > 3000) {
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

        return next;
      });

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isVoyaging, activeRoute, voyageSpeed, followShipCamera, updateShip]);

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
  }, [render3DIcebergs, updateShip, xrayMode]);

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

        // Initial Camera: Elevated Third-Person Tactical View overlooking vessel and open water fairway
        viewer.camera.setView({
          destination: Cesium.Cartesian3.fromDegrees(-60.50 + 0.040, -62.44 - 0.055, 5200),
          orientation: {
            heading: Cesium.Math.toRadians(325),
            pitch: Cesium.Math.toRadians(-40),
            roll: 0.0,
          },
        });

        // Initialize vessel directly on fairway route line (approaching WP-3 / WP-4)
        const initialFairwayState = getRouteProgressState(DEFAULT_FAIRWAY_ROUTE.points, 0.33);
        if (initialFairwayState) {
          updateShip({
            lat: initialFairwayState.lat,
            lon: initialFairwayState.lon,
            heading: initialFairwayState.heading,
            speed_knots: 13.2,
          });
        }
        render3DIcebergs(viewer, FALLBACK_ICEBERGS, xrayMode);
        renderRoutes(viewer);

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
          title="Close 3D focus on MV Vasiliy Golovnin"
        >
          🎯 Focus Ship
        </button>
        <button
          className={`preset-btn ${activePreset === "route" ? "active" : ""}`}
          onClick={() => applyCameraPreset("route")}
          title="30km Tactical Navigation Corridor"
        >
          🗺️ Route Corridor
        </button>
        <button
          className={`preset-btn ${activePreset === "iceberg" ? "active" : ""}`}
          onClick={() => applyCameraPreset("iceberg")}
          title="Close 3D focus on A23-A Tabular Iceberg"
        >
          🧊 Iceberg A23-A
        </button>
        <button
          className={`preset-btn ${activePreset === "relief" ? "active" : ""}`}
          onClick={() => applyCameraPreset("relief")}
          title="3D Coast & Mountain Relief"
        >
          🏔️ 3D Coast Relief
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
                className={`toggle-pill ${xrayMode ? "active" : ""}`}
                onClick={() => setXrayMode(!xrayMode)}
              >
                🩻 {xrayMode ? "X-Ray Active" : "Sonar X-Ray"}
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
