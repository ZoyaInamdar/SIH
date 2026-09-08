from pathlib import Path
import json

import cv2

from .ictineu_denoising import denoise_sonar_image
from .detector import detect_targets
from .knowledge_base import enrich_detection
from .spatialization import localize_bounding_box


# ============================================================
# INPUT
# ============================================================

IMAGE_PATH = Path(
    "data/sonar/data/raw/"
    "marine-debris-watertank-release/"
    "fls-images/"
    "marine-debris-aris3k-0.png"
)


# ============================================================
# OUTPUT
# ============================================================

OUTPUT_DIR = Path(
    "sonar/outputs/end_to_end"
)


# ============================================================
# SIMULATED VESSEL STATE
# ============================================================

# IMPORTANT:
# These are demonstration navigation values.
# Replace them with the real ship position/heading
# when connecting this to the NMEA system.

VESSEL_LAT = -69.1234567
VESSEL_LON = 76.1234567
VESSEL_HEADING = 45.0


# ============================================================
# SONAR GEOMETRY
# ============================================================

MAX_RANGE_M = 100.0
FOV_DEG = 90.0

CONFIDENCE_THRESHOLD = 0.25


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print("FULL SONAR END-TO-END DEMO")
    print("=" * 70)

    # --------------------------------------------------------
    # STEP 1 — LOAD IMAGE
    # --------------------------------------------------------

    image = cv2.imread(
        str(IMAGE_PATH),
        cv2.IMREAD_UNCHANGED,
    )

    if image is None:
        raise FileNotFoundError(
            f"Could not load:\n{IMAGE_PATH}"
        )

    image_height, image_width = image.shape[:2]

    print()
    print("[1/6] FLS image loaded")
    print(f"      Size: {image_width} x {image_height}")

    # --------------------------------------------------------
    # STEP 2 — DENOISING
    # --------------------------------------------------------

    denoised = denoise_sonar_image(
        image
    )

    cv2.imwrite(
        str(
            OUTPUT_DIR / "denoised.png"
        ),
        denoised.final,
    )

    print(
        "[2/6] Ictineu-inspired "
        "sonar denoising complete"
    )

    # --------------------------------------------------------
    # STEP 3 — YOLO DETECTION
    # --------------------------------------------------------

    detections = detect_targets(
        denoised.final,
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )

    print(
        f"[3/6] YOLO26 detected "
        f"{len(detections)} target(s)"
    )

    # --------------------------------------------------------
    # NO DETECTIONS
    # --------------------------------------------------------

    if not detections:

        result = {
            "status": "no_target_detected",
            "vessel": {
                "latitude": VESSEL_LAT,
                "longitude": VESSEL_LON,
                "heading_deg": VESSEL_HEADING,
            },
            "detections": [],
        }

        output_path = (
            OUTPUT_DIR /
            "sonar_hazard_observation.json"
        )

        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                result,
                file,
                indent=2,
            )

        print()
        print(
            "No targets detected. "
            "Observation saved."
        )

        return

    # --------------------------------------------------------
    # STEP 4 — KNOWLEDGE BASE + SPATIALIZATION
    # --------------------------------------------------------

    targets = []

    for index, detection in enumerate(
        detections,
        start=1,
    ):

        bbox = [
            int(value)
            for value in detection.bounding_box
        ]

        confidence = float(
            detection.detection_confidence
        )

        target_class = (
            detection.target_class
        )

        # ----------------------------------------------------
        # KNOWLEDGE BASE
        # ----------------------------------------------------

        knowledge = enrich_detection(
            target_class=target_class,
            detection_confidence=confidence,
        )

        # ----------------------------------------------------
        # SPATIALIZATION
        # ----------------------------------------------------

        (
            range_m,
            bearing_deg,
            target_lat,
            target_lon,
        ) = localize_bounding_box(
            bbox=bbox,
            img_width=image_width,
            img_height=image_height,
            vessel_lat=VESSEL_LAT,
            vessel_lon=VESSEL_LON,
            vessel_heading=VESSEL_HEADING,
            max_range_m=MAX_RANGE_M,
            fov_deg=FOV_DEG,
        )

        target = {
            "target_id": (
                f"SONAR_TARGET_{index:03d}"
            ),

            "bounding_box": bbox,

            "target_class": target_class,

            "detection_confidence": round(
                confidence,
                4,
            ),

            "knowledge": knowledge,

            "range_m": range_m,

            "bearing_deg": bearing_deg,

            "latitude": round(
                target_lat,
                7,
            ),

            "longitude": round(
                target_lon,
                7,
            ),
        }

        targets.append(target)

    print(
        "[4/6] Knowledge-base enrichment "
        "and spatialization complete"
    )

    # --------------------------------------------------------
    # STEP 5 — DRAW DETECTIONS
    # --------------------------------------------------------

    detected_image = cv2.cvtColor(
        denoised.final,
        cv2.COLOR_GRAY2BGR,
    )

    for target in targets:

        x, y, w, h = target[
            "bounding_box"
        ]

        x2 = x + w
        y2 = y + h

        cv2.rectangle(
            detected_image,
            (x, y),
            (x2, y2),
            (255, 255, 255),
            2,
        )

        label = (
            f'{target["target_class"]} '
            f'{target["detection_confidence"]:.2f}'
        )

        cv2.putText(
            detected_image,
            label,
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    cv2.imwrite(
        str(
            OUTPUT_DIR / "detected.png"
        ),
        detected_image,
    )

    print(
        "[5/6] Detection visualization saved"
    )

    # --------------------------------------------------------
    # STEP 6 — STRUCTURED HAZARD OBSERVATION
    # --------------------------------------------------------

    from datetime import datetime, timezone
    import uuid

    observation = {
        "observation_id": (
            f"OBS_{uuid.uuid4().hex[:8].upper()}"
        ),

        "source_type": "SONAR",

        "vessel": {
            "latitude": VESSEL_LAT,
            "longitude": VESSEL_LON,
            "heading_deg": VESSEL_HEADING,
        },

        "sonar": {
            "targets": targets,

            "geometry": {
                "method": (
                    "prototype_fov_projection"
                ),
                "max_range_m": MAX_RANGE_M,
                "fov_deg": FOV_DEG,
                "calibrated": False,
            },
        },

        "observed_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }

    output_path = (
        OUTPUT_DIR /
        "sonar_hazard_observation.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            observation,
            file,
            indent=2,
        )

    print(
        "[6/6] Structured sonar observation saved"
    )

    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SONAR DETECTION RESULTS")
    print("=" * 70)

    for target in targets:

        print()
        print(
            f"Target: "
            f"{target['target_class']}"
        )

        print(
            f"Confidence: "
            f"{target['detection_confidence']}"
        )

        print(
            f"Bounding box: "
            f"{target['bounding_box']}"
        )

        print(
            f"Range: "
            f"{target['range_m']} m"
        )

        print(
            f"Bearing: "
            f"{target['bearing_deg']}°"
        )

        print(
            f"Estimated position: "
            f"{target['latitude']}, "
            f"{target['longitude']}"
        )

        print(
            f"Hazard category: "
            f"{target['knowledge']['category']}"
        )

        print(
            f"Hazard relevance: "
            f"{target['knowledge']['hazard_relevance']}"
        )

        print(
            f"Hazard score: "
            f"{target['knowledge']['hazard_score']}"
        )

    print()
    print("=" * 70)
    print("END-TO-END DEMO COMPLETE")
    print("=" * 70)

    print()
    print("Output directory:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()