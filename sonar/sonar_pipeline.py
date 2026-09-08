from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .ictineu_denoising import denoise_sonar_image
from .knowledge_base import enrich_detection

import cv2
import numpy as np

from .detector import detect_targets
from .preprocessing import preprocess_sonar_image
from .spatialization import localize_bounding_box


# ============================================================
# INLINE SCHEMAS (Bypassing restrictive .schemas imports)
# ============================================================

class SonarTarget:
    def __init__(self, bounding_box, detection_confidence, target_class, range_m=None, bearing_deg=None, latitude=None, longitude=None):
        self.bounding_box = bounding_box
        self.detection_confidence = detection_confidence
        self.target_class = target_class
        self.range_m = range_m
        self.bearing_deg = bearing_deg
        self.latitude = latitude
        self.longitude = longitude

class SonarObservation:
    def __init__(self, observation_id, source_type, targets, range_m, bearing_deg, observed_at):
        self.observation_id = observation_id
        self.source_type = source_type
        self.targets = targets
        self.range_m = range_m
        self.bearing_deg = bearing_deg
        self.observed_at = observed_at

    def to_dict(self):
        return {
            "observation_id": self.observation_id,
            "source_type": self.source_type,
            "sonar": {
                "targets": [
                    {
                        "bounding_box": t.bounding_box,
                        "detection_confidence": t.detection_confidence,
                        "target_class": t.target_class,
                    }
                    for t in self.targets
                ],
                "range_m": self.range_m,
                "bearing_deg": self.bearing_deg,
            },
            "observed_at": self.observed_at,
        }


# ============================================================
# DEFAULT SONAR GEOMETRY
# ============================================================

DEFAULT_MAX_RANGE_M = 100.0
DEFAULT_FOV_DEG = 90.0


# ============================================================
# IMAGE LOADING
# ============================================================

def _load_image(image) -> np.ndarray:
    if isinstance(image, (str, Path)):
        loaded = cv2.imread(
            str(image),
            cv2.IMREAD_UNCHANGED,
        )

        if loaded is None:
            raise ValueError(
                f"Could not load sonar image: {image}"
            )

        return loaded

    if isinstance(image, np.ndarray):
        return image

    raise TypeError(
        "image must be either a file path or numpy.ndarray"
    )


# ============================================================
# DETECTION HELPERS
# ============================================================

def _get_detection_bbox(detection):
    bbox = detection.bbox

    if len(bbox) != 4:
        raise ValueError(
            f"Invalid detection bounding box: {bbox}"
        )

    return tuple(
        int(value)
        for value in bbox
    )


def _get_detection_confidence(detection):
    return float(
        detection.detection_score
    )


def _get_detection_class(detection):
    return getattr(
        detection,
        "target_class",
        None,
    )


# ============================================================
# DRAW DETECTIONS
# ============================================================

def _draw_detections(
    image: np.ndarray,
    detections,
) -> np.ndarray:
    if image.ndim == 2:
        output = cv2.cvtColor(
            image,
            cv2.COLOR_GRAY2BGR,
        )
    else:
        output = image.copy()

    for detection in detections:
        x, y, w, h = _get_detection_bbox(
            detection
        )

        confidence = _get_detection_confidence(
            detection
        )

        target_class = _get_detection_class(
            detection
        )

        # Bounding box
        cv2.rectangle(
            output,
            (x, y),
            (x + w, y + h),
            (255, 255, 255),
            2,
        )

        # Label
        label = (
            f"{target_class or 'target'} "
            f"{confidence:.2f}"
        )

        cv2.putText(
            output,
            label,
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return output


# ============================================================
# CREATE SONAR TARGET
# ============================================================

def _create_sonar_target(
    detection,
) -> SonarTarget:
    bbox = _get_detection_bbox(
        detection
    )

    confidence = _get_detection_confidence(
        detection
    )

    target_class = _get_detection_class(
        detection
    )

    return SonarTarget(
        bounding_box=bbox,
        detection_confidence=confidence,
        target_class=target_class,
    )


# ============================================================
# BASIC SONAR DETECTION PIPELINE
# ============================================================

def detect_sonar_target(
    image,
    observation_id: Optional[str] = None,
    confidence_threshold: float = 0.25,
):
    original_image = _load_image(
        image
    )

    processed = preprocess_sonar_image(
    original_image
    )

    denoised = denoise_sonar_image(
        original_image
    )

    # YOLO receives the denoised/enhanced FLS image.
    detections = detect_targets(
        denoised.final,
        confidence_threshold=confidence_threshold,
    )

    detected_image = _draw_detections(
        processed.enhanced,
        detections,
    )

    targets = []

    for detection in detections:
        target = _create_sonar_target(
            detection
        )
        targets.append(target)

    if observation_id is None:
        observation_id = (
            f"OBS_{uuid.uuid4().hex[:8].upper()}"
        )

    observed_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    observation = SonarObservation(
        observation_id=observation_id,
        source_type="SONAR",
        targets=targets,
        range_m=None,
        bearing_deg=None,
        observed_at=observed_at,
    )

    return (
    processed,
    detections,
    detected_image,
    observation,
    )


# ============================================================
# SPATIALIZED SONAR PIPELINE
# ============================================================

def process_sonar_feed(
    image_path: str,
    iceberg_id: Optional[str],
    vessel_lat: float,
    vessel_lon: float,
    vessel_heading: float,
    max_range_m: float = DEFAULT_MAX_RANGE_M,
    fov_deg: float = DEFAULT_FOV_DEG,
    confidence_threshold: float = 0.25,
) -> dict:
    image = _load_image(
        image_path
    )

    image_height, image_width = (
        image.shape[:2]
    )

    processed = preprocess_sonar_image(
        image
    )

    detections = detect_targets(
        processed.enhanced,
        confidence_threshold=confidence_threshold,
    )

    observation_id = (
        f"OBS_{uuid.uuid4().hex[:8].upper()}"
    )

    observed_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    if not detections:
        return {
            "status": "no_target_detected",
            "iceberg_id": iceberg_id,
            "observation_id": observation_id,
            "source_type": "SONAR",
            "sonar": {
                "targets": [],
                "range_m": None,
                "bearing_deg": None,
            },
            "observed_at": observed_at,
            "spatialization": {
                "method": "prototype_fov_projection",
                "max_range_m": max_range_m,
                "fov_deg": fov_deg,
                "calibrated": False,
            },
        }

    targets = []

    for detection in detections:
        bbox = _get_detection_bbox(
            detection
        )

        confidence = _get_detection_confidence(
            detection
        )

        target_class = _get_detection_class(
            detection
        )

        (
            range_m,
            bearing_deg,
            target_lat,
            target_lon,
        ) = localize_bounding_box(
            bbox=list(bbox),
            img_width=image_width,
            img_height=image_height,
            vessel_lat=vessel_lat,
            vessel_lon=vessel_lon,
            vessel_heading=vessel_heading,
            max_range_m=max_range_m,
            fov_deg=fov_deg,
        )

        target = SonarTarget(
            bounding_box=bbox,
            detection_confidence=confidence,
            target_class=target_class,
            range_m=range_m,
            bearing_deg=bearing_deg,
            latitude=target_lat,
            longitude=target_lon,
        )

        targets.append(target)

    observation = SonarObservation(
        observation_id=observation_id,
        source_type="SONAR",
        targets=targets,
        range_m=targets[0].range_m,
        bearing_deg=targets[0].bearing_deg,
        observed_at=observed_at,
    )

    result = observation.to_dict()

    result["iceberg_id"] = iceberg_id
    result["spatialization"] = {
        "method": "prototype_fov_projection",
        "max_range_m": max_range_m,
        "fov_deg": fov_deg,
        "calibrated": False,
    }

    return result


# ============================================================
# FILE-BASED SONAR PIPELINE
# ============================================================

def run_sonar_pipeline(
    image_path: str,
    output_dir: str = "sonar/outputs",
    confidence_threshold: float = 0.25,
):
    image_path = Path(
        image_path
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    image = _load_image(
        image_path
    )

    processed = preprocess_sonar_image(
        image
    )

    detections = detect_targets(
        processed.enhanced,
        confidence_threshold=confidence_threshold,
    )

    detected_image = _draw_detections(
        processed.enhanced,
        detections,
    )

    cv2.imwrite(
        str(
            output_dir / "original.png"
        ),
        processed.original_gray,
    )

    cv2.imwrite(
        str(
            output_dir / "processed.png"
        ),
        processed.enhanced,
    )

    cv2.imwrite(
        str(
            output_dir / "mask.png"
        ),
        processed.mask,
    )

    cv2.imwrite(
        str(
            output_dir / "detected.png"
        ),
        detected_image,
    )

    targets = []

    for detection in detections:
        target = _create_sonar_target(
            detection
        )
        targets.append(target)

    observation = SonarObservation(
        observation_id=(
            f"OBS_{uuid.uuid4().hex[:8].upper()}"
        ),
        source_type="SONAR",
        targets=targets,
        range_m=None,
        bearing_deg=None,
        observed_at=(
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    )

    observation_path = (
        output_dir
        / "sonar_observation.json"
    )

    with open(
        observation_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            observation.to_dict(),
            file,
            indent=2,
        )

    return {
        "processed": processed,
        "detections": detections,
        "detected_image": detected_image,
        "observation": observation,
        "output_dir": str(
            output_dir
        ),
    }