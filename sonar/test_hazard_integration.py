from pathlib import Path

from sonar.sonar_pipeline import (
    detect_sonar_target,
)

from backend.services.sonar_hazard_service import (
    clear_sonar_hazards,
    process_sonar_observation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


IMAGE = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "data"
    / "raw"
    / "marine-debris-watertank-release"
    / "fls-images"
    / "marine-debris-aris3k-0.png"
)


def test_real_yolo_to_hazard_pipeline():

    clear_sonar_hazards()

    (
        processed,
        detections,
        detected_image,
        observation,
    ) = detect_sonar_target(
        IMAGE,
        observation_id="OBS_REAL_0001",
        confidence_threshold=0.25,
    )

    observation_dict = (
        observation.to_dict()
    )

    hazards = process_sonar_observation(
        observation_dict
    )

    # The important architectural check:
    # every YOLO target should become a sonar
    # hazard observation.
    assert len(hazards) == len(
        detections
    )

    for hazard, detection in zip(
        hazards,
        detections,
    ):

        assert (
            hazard.bounding_box
            == list(detection.bbox)
        )

        assert (
            hazard.detection_confidence
            == detection.detection_score
        )

        assert (
            hazard.target_class
            == detection.target_class
        )

        # Dataset does not provide range/bearing.
        assert hazard.range_m is None
        assert hazard.bearing_deg is None

        # Therefore geographic localization
        # must remain false.
        assert hazard.localized is False