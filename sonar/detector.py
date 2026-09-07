from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------

@dataclass
class Detection:
    """
    One sonar target detected by the trained YOLO model.

    bbox:
        (x, y, width, height) in original image pixels.

    detection_score:
        Actual YOLO model confidence.

    target_class:
        Predicted class name.

    class_id:
        Numeric YOLO class ID.
    """

    bbox: Tuple[int, int, int, int]
    detection_score: float
    target_class: Optional[str] = None
    class_id: Optional[int] = None

    @property
    def area(self) -> int:
        return self.bbox[2] * self.bbox[3]

    @property
    def aspect_ratio(self) -> float:
        width = self.bbox[2]
        height = self.bbox[3]

        if height == 0:
            return 0.0

        return width / height


# ---------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

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


_MODEL = None


def load_model(model_path: Optional[str | Path] = None):
    """
    Load the trained YOLO26n model.

    The model is cached after the first load so repeated
    sonar observations do not reload the weights.
    """

    global _MODEL

    if _MODEL is not None:
        return _MODEL

    from ultralytics import YOLO

    path = Path(model_path) if model_path else MODEL_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"Trained sonar model not found: {path}"
        )

    _MODEL = YOLO(str(path))

    return _MODEL


# ---------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------

def detect_targets(
    image: np.ndarray,
    confidence_threshold: float = 0.25,
    model_path: Optional[str | Path] = None,
    max_detections: int = 20,
) -> List[Detection]:
    """
    Detect underwater objects in an FLS sonar image.

    Parameters
    ----------
    image:
        Original sonar image as a NumPy array.

    confidence_threshold:
        Minimum YOLO confidence required.

    model_path:
        Optional custom path to best.pt.

    max_detections:
        Maximum number of targets returned.

    Returns
    -------
    List[Detection]
    """

    if image is None:
        raise ValueError("Input image cannot be None.")

    if image.size == 0:
        raise ValueError("Input image is empty.")

    model = load_model(model_path)

    results = model.predict(
        source=image,
        conf=confidence_threshold,
        max_det=max_detections,
        verbose=False,
        device="cpu",
    )

    detections: List[Detection] = []

    if not results:
        return detections

    result = results[0]

    if result.boxes is None:
        return detections

    names = result.names

    for box in result.boxes:

        # xyxy = x1, y1, x2, y2
        xyxy = box.xyxy[0].cpu().numpy()

        x1, y1, x2, y2 = xyxy

        x1 = int(round(x1))
        y1 = int(round(y1))
        x2 = int(round(x2))
        y2 = int(round(y2))

        width = max(0, x2 - x1)
        height = max(0, y2 - y1)

        if width <= 0 or height <= 0:
            continue

        confidence = float(
            box.conf[0].cpu().item()
        )

        class_id = int(
            box.cls[0].cpu().item()
        )

        class_name = names.get(
            class_id,
            str(class_id)
        )

        detections.append(
            Detection(
                bbox=(x1, y1, width, height),
                detection_score=confidence,
                target_class=class_name,
                class_id=class_id,
            )
        )

    return detections


# ---------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------

def draw_detections(
    image: np.ndarray,
    detections: List[Detection],
) -> np.ndarray:
    """
    Draw YOLO detections on the original image.
    """

    if image is None:
        raise ValueError("Input image cannot be None.")

    output = image.copy()

    # Convert grayscale to BGR for visualization.
    if output.ndim == 2:
        output = cv2.cvtColor(
            output,
            cv2.COLOR_GRAY2BGR
        )

    elif output.ndim == 3 and output.shape[2] == 4:
        output = cv2.cvtColor(
            output,
            cv2.COLOR_BGRA2BGR
        )

    for detection in detections:

        x, y, width, height = detection.bbox

        x2 = x + width
        y2 = y + height

        cv2.rectangle(
            output,
            (x, y),
            (x2, y2),
            (0, 255, 0),
            2,
        )

        label = (
            f"{detection.target_class} "
            f"{detection.detection_score:.2f}"
        )

        text_y = max(
            20,
            y - 8
        )

        cv2.putText(
            output,
            label,
            (x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

    return output