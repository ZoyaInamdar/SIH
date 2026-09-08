from pathlib import Path

from sonar.sonar_pipeline import (
    run_sonar_pipeline,
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


OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "outputs"
    / "yolo_test"
)


if __name__ == "__main__":

    print(
        "Testing image:"
    )

    print(IMAGE)

    if not IMAGE.exists():
        raise FileNotFoundError(
            f"Test image not found:\n{IMAGE}"
        )

    observation = run_sonar_pipeline(
        image_path=IMAGE,

        output_dir=OUTPUT_DIR,

        observation_id="OBS_YOLO_TEST_0001",

        confidence_threshold=0.25,
    )

    print("\n")
    print("FINAL OBSERVATION:")
    print(
        observation.to_dict()
    )