from pathlib import Path
import json

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

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "outputs"
    / "yolo"
    / "evaluation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("SONAR YOLO EVALUATION")
    print("=" * 60)

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Trained model not found:\n{MODEL_PATH}\n\n"
            "Run train_detector.py first."
        )

    model = YOLO(
        str(MODEL_PATH)
    )

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    metrics = model.val(
        data=str(
            DATASET_YAML
        ),

        imgsz=640,

        batch=8,

        device="cpu",

        project=str(
            OUTPUT_DIR
        ),

        name="validation",

        exist_ok=True,

        plots=True,

        verbose=True,
    )

    # --------------------------------------------------------
    # Extract useful metrics
    # --------------------------------------------------------

    results = {
        "model": str(MODEL_PATH),

        "box_map50": float(
            metrics.box.map50
        ),

        "box_map50_95": float(
            metrics.box.map
        ),

        "box_precision": float(
            metrics.box.mp
        ),

        "box_recall": float(
            metrics.box.mr
        ),
    }

    results_path = (
        OUTPUT_DIR
        / "evaluation_results.json"
    )

    with results_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
        )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("FINAL YOLO RESULTS")
    print("=" * 60)

    print(
        f"Precision : "
        f"{results['box_precision']:.4f}"
    )

    print(
        f"Recall    : "
        f"{results['box_recall']:.4f}"
    )

    print(
        f"mAP@0.50 : "
        f"{results['box_map50']:.4f}"
    )

    print(
        f"mAP@0.50:0.95 : "
        f"{results['box_map50_95']:.4f}"
    )

    print()

    print(
        "Results saved to:"
    )

    print(
        results_path
    )


if __name__ == "__main__":

    main()

