from pathlib import Path
from typing import Optional

import cv2
from ultralytics import YOLO

from sonar.schemas import (
    SonarObservation,
    SonarTarget,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent.parent
)

DEFAULT_MODEL = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "outputs"
    / "yolo"
    / "sonar_yolo26n"
    / "weights"
    / "best.pt"
)


class YOLOSonarDetector:

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.25,
    ):

        if model_path is None:

            model_path = str(
                DEFAULT_MODEL
            )

        self.model_path = Path(
            model_path
        )

        if not self.model_path.exists():

            raise FileNotFoundError(
                f"YOLO model not found:\n"
                f"{self.model_path}\n\n"
                "Train the model first."
            )

        self.confidence_threshold = (
            confidence_threshold
        )

        self.model = YOLO(
            str(self.model_path)
        )

    def detect(
        self,
        image_path,
    ):

        image_path = Path(
            image_path
        )

        image = cv2.imread(
            str(image_path),
            cv2.IMREAD_UNCHANGED,
        )

        if image is None:

            raise ValueError(
                f"Could not read image:\n"
                f"{image_path}"
            )

        results = self.model.predict(
            source=str(
                image_path
            ),

            conf=self.confidence_threshold,

            device="cpu",

            verbose=False,
        )

        result = results[0]

        targets = []

        if result.boxes is not None:

            boxes = (
                result.boxes.xyxy
                .cpu()
                .numpy()
            )

            confidences = (
                result.boxes.conf
                .cpu()
                .numpy()
            )

            class_ids = (
                result.boxes.cls
                .cpu()
                .numpy()
                .astype(int)
            )

            names = result.names

            for box, confidence, class_id in zip(
                boxes,
                confidences,
                class_ids,
            ):

                x1, y1, x2, y2 = box

                x = int(
                    round(x1)
                )

                y = int(
                    round(y1)
                )

                width = int(
                    round(
                        x2 - x1
                    )
                )

                height = int(
                    round(
                        y2 - y1
                    )
                )

                class_name = names.get(
                    int(class_id),
                    str(class_id),
                )

                targets.append(
                    SonarTarget(
                        bounding_box=(
                            x,
                            y,
                            width,
                            height,
                        ),

                        detection_confidence=float(
                            confidence
                        ),

                        target_class=class_name,
                    )
                )

        return image, targets

    def detect_observation(
        self,
        image_path,
        observation_id="OBS_SONAR_0001",
    ):

        image, targets = self.detect(
            image_path
        )

        observation = SonarObservation(
            observation_id=observation_id,

            source_type="SONAR",

            targets=targets,

            range_m=None,

            bearing_deg=None,

            observed_at=None,
        )

        return image, targets, observation


def draw_yolo_detections(
    image,
    targets,
):

    if image is None:

        raise ValueError(
            "Image cannot be None."
        )

    if image.ndim == 2:

        output = cv2.cvtColor(
            image,
            cv2.COLOR_GRAY2BGR,
        )

    elif (
        image.ndim == 3
        and image.shape[2] == 4
    ):

        output = cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2BGR,
        )

    else:

        output = image.copy()

    for target in targets:

        x, y, w, h = (
            target.bounding_box
        )

        cv2.rectangle(
            output,

            (x, y),

            (
                x + w,
                y + h,
            ),

            (255, 255, 255),

            2,
        )

        label = (
            f"{target.target_class} "
            f"{target.detection_confidence:.2f}"
        )

        cv2.putText(
            output,

            label,

            (
                x,
                max(
                    15,
                    y - 5,
                ),
            ),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.5,

            (255, 255, 255),

            1,

            cv2.LINE_AA,
        )

    return output

