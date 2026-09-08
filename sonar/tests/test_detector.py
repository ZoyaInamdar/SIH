from pathlib import Path

from sonar.detector import (
    load_model,
    detect_targets,
)


# Project root:
# SIH/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


MODEL_PATH = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "outputs"
    / "yolo"
    / "sonar_yolo26n"
    / "weights"
    / "best.pt"
)


SAMPLE_IMAGE = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "data"
    / "raw"
    / "marine-debris-watertank-release"
    / "fls-images"
    / "marine-debris-aris3k-0.png"
)


def test_trained_model_exists():
    """
    Verify that the trained YOLO model exists
    in the expected project location.
    """

    assert MODEL_PATH.exists(), (
        f"Trained YOLO model not found:\n"
        f"{MODEL_PATH}"
    )


def test_trained_model_loads():
    """
    Verify that best.pt can actually be loaded
    by Ultralytics.
    """

    model = load_model(
        model_path=MODEL_PATH
    )

    assert model is not None


def test_detector_runs_on_sonar_image():
    """
    Verify that the YOLO detector can process
    an actual FLS sonar image.
    """

    assert SAMPLE_IMAGE.exists(), (
        f"Sample sonar image not found:\n"
        f"{SAMPLE_IMAGE}"
    )

    import cv2

    image = cv2.imread(
        str(SAMPLE_IMAGE),
        cv2.IMREAD_UNCHANGED,
    )

    assert image is not None

    detections = detect_targets(
        image,
        confidence_threshold=0.25,
        model_path=MODEL_PATH,
    )

    assert isinstance(
        detections,
        list,
    )


def test_detection_results_are_valid():
    """
    If YOLO detects targets, verify that every
    detection contains valid bbox and confidence data.
    """

    import cv2

    image = cv2.imread(
        str(SAMPLE_IMAGE),
        cv2.IMREAD_UNCHANGED,
    )

    detections = detect_targets(
        image,
        confidence_threshold=0.25,
        model_path=MODEL_PATH,
    )

    for detection in detections:

        # Bounding box must be:
        # (x, y, width, height)
        assert len(
            detection.bbox
        ) == 4

        x, y, width, height = (
            detection.bbox
        )

        assert x >= 0
        assert y >= 0
        assert width > 0
        assert height > 0

        # YOLO confidence must be in [0, 1].
        assert 0.0 <= (
            detection.detection_score
        ) <= 1.0

        # A trained detector should return
        # a class name.
        assert detection.target_class is not None
        assert isinstance(
            detection.target_class,
            str,
        )