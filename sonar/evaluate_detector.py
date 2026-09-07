from pathlib import Path
import json

import cv2
import numpy as np

from sonar.preprocessing import preprocess_sonar_image
from sonar.detector import detect_targets
from sonar.dataset import (
    load_annotations,
    get_image_annotations,
    convert_box,
)


# ============================================================
# PATHS
# ============================================================

DATASET = Path(
    r".\data\sonar\data\raw\marine-debris-watertank-release\fls-images"
)

ANNOTATIONS = DATASET / "annotations.json"

# CORRECT OUTPUT PATH
OUTPUT_DIR = Path(
    r".\data\sonar\outputs\evaluation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# IOU
# ============================================================

def iou(box_a, box_b):
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    ax2 = ax + aw
    ay2 = ay + ah

    bx2 = bx + bw
    by2 = by + bh

    ix1 = max(ax, bx)
    iy1 = max(ay, by)

    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)

    intersection = iw * ih

    area_a = aw * ah
    area_b = bw * bh

    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


# ============================================================
# MATCH DETECTIONS TO GROUND TRUTH
# ============================================================

def match_detections(
    detections,
    ground_truth,
    iou_threshold=0.30,
):
    candidates = []

    for det_index, detection in enumerate(detections):

        for gt_index, gt in enumerate(ground_truth):

            score = iou(
                detection.bbox,
                gt,
            )

            candidates.append(
                (
                    score,
                    det_index,
                    gt_index,
                )
            )

    # Highest IoU first
    candidates.sort(
        reverse=True
    )

    matched_detections = set()
    matched_ground_truth = set()

    true_positives = 0

    for score, det_index, gt_index in candidates:

        if score < iou_threshold:
            break

        if det_index in matched_detections:
            continue

        if gt_index in matched_ground_truth:
            continue

        matched_detections.add(
            det_index
        )

        matched_ground_truth.add(
            gt_index
        )

        true_positives += 1

    false_positives = (
        len(detections) - true_positives
    )

    false_negatives = (
        len(ground_truth) - true_positives
    )

    return (
        true_positives,
        false_positives,
        false_negatives,
    )


# ============================================================
# DRAW GROUND TRUTH + DETECTIONS
# ============================================================

def draw_comparison(
    image,
    ground_truth,
    detections,
    output_path,
):

    if image.ndim == 2:

        output = cv2.cvtColor(
            image,
            cv2.COLOR_GRAY2BGR,
        )

    else:

        output = image.copy()

    # --------------------------------------------------------
    # Ground truth boxes
    # --------------------------------------------------------

    for x, y, w, h in ground_truth:

        cv2.rectangle(
            output,
            (x, y),
            (x + w, y + h),
            (255, 255, 255),
            2,
        )

        cv2.putText(
            output,
            "GT",
            (x, max(15, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # --------------------------------------------------------
    # Detector boxes
    # --------------------------------------------------------

    for detection in detections:

        x, y, w, h = detection.bbox

        cv2.rectangle(
            output,
            (x, y),
            (x + w, y + h),
            (180, 180, 180),
            1,
        )

        cv2.putText(
            output,
            f"D {detection.detection_score:.2f}",
            (
                x,
                min(
                    image.shape[0] - 5,
                    y + h + 15,
                ),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 180, 180),
            1,
            cv2.LINE_AA,
        )

    cv2.imwrite(
        str(output_path),
        output,
    )


# ============================================================
# MAIN EVALUATION
# ============================================================

def main():

    annotations = load_annotations(
        ANNOTATIONS
    )

    image_files = sorted(
        DATASET.glob(
            "marine-debris-aris3k-*.png"
        )
    )

    print(
        "========================================"
    )
    print(
        "SONAR DETECTOR EVALUATION"
    )
    print(
        "========================================"
    )

    print(
        "Images:",
        len(image_files),
    )

    print(
        "Annotations:",
        len(annotations),
    )

    print()

    total_gt = 0
    total_predictions = 0

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    iou_values = []
    detection_scores = []

    example_counter = 0

    # --------------------------------------------------------
    # Process every image
    # --------------------------------------------------------

    for index, image_path in enumerate(
        image_files
    ):

        image = cv2.imread(
            str(image_path),
            cv2.IMREAD_UNCHANGED,
        )

        if image is None:

            print(
                "WARNING: could not read",
                image_path.name,
            )

            continue

        # Ground truth
        boxes = get_image_annotations(
            annotations,
            image_path.name,
        )

        ground_truth = [
            convert_box(box)
            for box in boxes
        ]

        # Preprocessing
        processed = preprocess_sonar_image(
            image
        )

        # Detection
        detections = detect_targets(
            processed.mask
        )

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        total_gt += len(
            ground_truth
        )

        total_predictions += len(
            detections
        )

        tp, fp, fn = match_detections(
            detections,
            ground_truth,
            iou_threshold=0.30,
        )

        true_positives += tp
        false_positives += fp
        false_negatives += fn

        # Detection scores
        for detection in detections:

            detection_scores.append(
                detection.detection_score
            )

        # IoU values
        for detection in detections:

            for gt in ground_truth:

                value = iou(
                    detection.bbox,
                    gt,
                )

                if value >= 0.30:

                    iou_values.append(
                        value
                    )

        # ----------------------------------------------------
        # Save visual examples
        # ----------------------------------------------------

        if (
            example_counter < 10
            and len(ground_truth) > 0
        ):

            draw_comparison(
                image,
                ground_truth,
                detections,
                OUTPUT_DIR
                / f"example_{example_counter:02d}.png",
            )

            example_counter += 1

        # Progress
        if (
            (index + 1) % 250 == 0
        ):

            print(
                f"Processed "
                f"{index + 1}/"
                f"{len(image_files)} images..."
            )

    # ========================================================
    # FINAL METRICS
    # ========================================================

    precision = (
        true_positives
        / (
            true_positives
            + false_positives
        )
        if (
            true_positives
            + false_positives
            > 0
        )
        else 0.0
    )

    recall = (
        true_positives
        / (
            true_positives
            + false_negatives
        )
        if (
            true_positives
            + false_negatives
            > 0
        )
        else 0.0
    )

    f1 = (
        2
        * precision
        * recall
        / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    mean_iou = (
        float(
            np.mean(iou_values)
        )
        if iou_values
        else 0.0
    )

    mean_score = (
        float(
            np.mean(
                detection_scores
            )
        )
        if detection_scores
        else 0.0
    )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results = {

        "images": len(image_files),

        "ground_truth_boxes": total_gt,

        "predicted_boxes": total_predictions,

        "true_positives": true_positives,

        "false_positives": false_positives,

        "false_negatives": false_negatives,

        "iou_threshold": 0.30,

        "precision": precision,

        "recall": recall,

        "f1": f1,

        "mean_matched_iou": mean_iou,

        "mean_detection_score": mean_score,
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

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print()

    print(
        "========================================"
    )
    print(
        "RESULTS"
    )
    print(
        "========================================"
    )

    print(
        f"Ground truth boxes : {total_gt}"
    )

    print(
        f"Predicted boxes    : {total_predictions}"
    )

    print(
        f"True positives     : {true_positives}"
    )

    print(
        f"False positives    : {false_positives}"
    )

    print(
        f"False negatives    : {false_negatives}"
    )

    print(
        f"Precision          : {precision:.4f}"
    )

    print(
        f"Recall             : {recall:.4f}"
    )

    print(
        f"F1 score           : {f1:.4f}"
    )

    print(
        f"Mean matched IoU   : {mean_iou:.4f}"
    )

    print(
        f"Mean detection score: {mean_score:.4f}"
    )

    print()

    print(
        "Saved evaluation results to:"
    )

    print(
        results_path
    )

    print()

    print(
        "Saved visual examples:"
    )

    for file in sorted(
        OUTPUT_DIR.glob(
            "example_*.png"
        )
    ):

        print(
            " ",
            file.name
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()

