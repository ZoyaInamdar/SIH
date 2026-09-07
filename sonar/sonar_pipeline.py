from __future__ import annotations

import json
from pathlib import Path

import cv2

from .detector import (
    detect_targets,
    draw_detections,
)
from .preprocessing import preprocess_sonar_image
from .schemas import create_observation


def detect_sonar_target(
    image_path: str | Path,
    observation_id: str = "OBS_SONAR_0001",
    confidence_threshold: float = 0.25,
):
    """
    Complete FLS sonar detection pipeline.

    Flow:

        sonar image
             ↓
        preprocessing
             ↓
        YOLO26n detector
             ↓
        bounding boxes
             ↓
        model confidence
             ↓
        structured sonar observation
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Sonar image not found: {image_path}"
        )

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_UNCHANGED,
    )

    if image is None:
        raise ValueError(
            f"Could not read sonar image: {image_path}"
        )

    # Keep preprocessing for the processing/debugging stage.
    processed = preprocess_sonar_image(image)

    # IMPORTANT:
    # YOLO receives the ORIGINAL sonar image.
    #
    # We don't feed the heavily thresholded binary mask
    # to YOLO because the trained model learned from the
    # original FLS appearance.
    detections = detect_targets(
        image,
        confidence_threshold=confidence_threshold,
    )

    detected_image = draw_detections(
        image,
        detections,
    )

    observation = create_observation(
        detections,
        observation_id=observation_id,
        range_m=None,
        bearing_deg=None,
    )

    return (
        processed,
        detections,
        detected_image,
        observation,
    )


def run_sonar_pipeline(
    image_path: str | Path,
    output_dir: str | Path = "data/sonar/outputs",
    observation_id: str = "OBS_SONAR_0001",
    confidence_threshold: float = 0.25,
):
    """
    Run the complete sonar pipeline and save outputs.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        processed,
        detections,
        detected_image,
        observation,
    ) = detect_sonar_target(
        image_path,
        observation_id=observation_id,
        confidence_threshold=confidence_threshold,
    )

    image_path = Path(image_path)

    # -------------------------------------------------------------
    # Save original grayscale image
    # -------------------------------------------------------------

    cv2.imwrite(
        str(output_dir / "original.png"),
        processed.original_gray,
    )

    # -------------------------------------------------------------
    # Save denoised image
    # -------------------------------------------------------------

    cv2.imwrite(
        str(output_dir / "denoised.png"),
        processed.denoised,
    )

    # -------------------------------------------------------------
    # Save CLAHE-enhanced image
    # -------------------------------------------------------------

    cv2.imwrite(
        str(output_dir / "processed.png"),
        processed.enhanced,
    )

    # -------------------------------------------------------------
    # Save segmentation mask for debugging
    # -------------------------------------------------------------

    cv2.imwrite(
        str(output_dir / "mask.png"),
        processed.mask,
    )

    # -------------------------------------------------------------
    # Save YOLO detections
    # -------------------------------------------------------------

    cv2.imwrite(
        str(output_dir / "detected.png"),
        detected_image,
    )

    # -------------------------------------------------------------
    # Save structured observation
    # -------------------------------------------------------------

    observation_path = (
        output_dir / "sonar_observation.json"
    )

    with observation_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            observation.to_dict(),
            f,
            indent=2,
        )

    # -------------------------------------------------------------
    # Print useful summary
    # -------------------------------------------------------------

    print("=" * 60)
    print("SONAR DETECTION COMPLETE")
    print("=" * 60)

    print(f"Image: {image_path}")

    print(
        f"Targets detected: {len(detections)}"
    )

    for i, detection in enumerate(
        detections,
        start=1,
    ):

        print(
            f"\nTarget {i}"
        )

        print(
            f"  Class       : "
            f"{detection.target_class}"
        )

        print(
            f"  Confidence  : "
            f"{detection.detection_score:.4f}"
        )

        print(
            f"  Bounding box: "
            f"{detection.bbox}"
        )

    print(
        f"\nObservation JSON:"
        f"\n{observation_path}"
    )

    return observation