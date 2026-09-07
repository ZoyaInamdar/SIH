from pathlib import Path
from typing import Dict, List, Any, Tuple
import json


CLASS_ID_TO_NAME = {
    0: "can",
    1: "bottle",
    2: "drink-carton",
    3: "chain",
    4: "propeller",
    5: "tire",
    6: "hook",
    7: "valve",
    8: "shampoo-bottle",
    9: "standing-bottle",
}


def load_annotations(annotation_path: str | Path) -> Dict[str, Any]:
    path = Path(annotation_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Annotation file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Expected annotations.json to contain an object.")

    return data


def get_image_annotations(
    annotations: Dict[str, Any],
    image_name: str,
) -> List[Dict[str, Any]]:

    entry = annotations.get(image_name)

    if entry is None:
        stem = Path(image_name).stem
        entry = annotations.get(stem)

    if entry is None:
        raise KeyError(
            f"No annotation found for image: {image_name}"
        )

    boxes = entry.get("bounding-boxes", [])

    if not isinstance(boxes, list):
        raise ValueError(
            f"Invalid bounding-boxes for image: {image_name}"
        )

    return boxes


def convert_box(box: Dict[str, Any]) -> Tuple[int, int, int, int]:
    x = int(box["top-left-x"])
    y = int(box["top-left-y"])
    w = int(box["width"])
    h = int(box["height"])

    return x, y, w, h


def get_class_name(box: Dict[str, Any]) -> str:
    class_name = box.get("class")

    if class_name is not None:
        return str(class_name)

    class_id = int(box["class-id"])

    if class_id not in CLASS_ID_TO_NAME:
        raise KeyError(
            f"Unknown class ID: {class_id}"
        )

    return CLASS_ID_TO_NAME[class_id]
