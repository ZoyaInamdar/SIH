from pathlib import Path

from ultralytics import YOLO


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

DATASET_YAML = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "yolo"
    / "dataset.yaml"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "outputs"
    / "yolo"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# TRAINING CONFIGURATION
# ============================================================

MODEL_NAME = "yolo26n.pt"

EPOCHS = 40

IMAGE_SIZE = 640

BATCH_SIZE = 8

WORKERS = 2


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("SONAR YOLO TRAINING")
    print("=" * 60)

    print(
        f"Dataset:\n{DATASET_YAML}"
    )

    print(
        f"Model: {MODEL_NAME}"
    )

    print(
        f"Epochs: {EPOCHS}"
    )

    print(
        f"Image size: {IMAGE_SIZE}"
    )

    print(
        f"Batch size: {BATCH_SIZE}"
    )

    print()

    if not DATASET_YAML.exists():

        raise FileNotFoundError(
            "dataset.yaml not found.\n"
            "Run convert_to_yolo.py first."
        )

    # --------------------------------------------------------
    # Load pretrained lightweight model
    # --------------------------------------------------------

    model = YOLO(
        MODEL_NAME
    )

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    results = model.train(
        data=str(
            DATASET_YAML
        ),

        epochs=EPOCHS,

        imgsz=IMAGE_SIZE,

        batch=BATCH_SIZE,

        workers=WORKERS,

        project=str(
            OUTPUT_DIR
        ),

        name="sonar_yolo26n",

        exist_ok=True,

        pretrained=True,

        patience=10,

        device="cpu",

        verbose=True,
    )

    print()
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)

    print(
        "Training output:"
    )

    print(
        OUTPUT_DIR
        / "sonar_yolo26n"
    )

    print()

    print(
        "Best model:"
    )

    print(
        OUTPUT_DIR
        / "sonar_yolo26n"
        / "weights"
        / "best.pt"
    )


if __name__ == "__main__":

    main()

