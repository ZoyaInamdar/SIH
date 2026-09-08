from pathlib import Path
import json
import random
import shutil


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_DIR = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "data"
    / "raw"
    / "marine-debris-watertank-release"
    / "fls-images"
)

ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"

YOLO_ROOT = (
    PROJECT_ROOT
    / "data"
    / "sonar"
    / "yolo"
)

TRAIN_IMAGES = YOLO_ROOT / "images" / "train"
VAL_IMAGES = YOLO_ROOT / "images" / "val"

TRAIN_LABELS = YOLO_ROOT / "labels" / "train"
VAL_LABELS = YOLO_ROOT / "labels" / "val"

DATASET_YAML = YOLO_ROOT / "dataset.yaml"


# ============================================================
# DATASET CLASSES
# ============================================================

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


# ============================================================
# SETTINGS
# ============================================================

VAL_FRACTION = 0.20
RANDOM_SEED = 42


# ============================================================
# HELPERS
# ============================================================

def clean_output_directories():

    for directory in [
        TRAIN_IMAGES,
        VAL_IMAGES,
        TRAIN_LABELS,
        VAL_LABELS,
    ]:

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        for item in directory.iterdir():

            if item.is_file():

                item.unlink()


def load_annotations():

    with ANNOTATIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def find_annotation_entry(
    annotations,
    image_name,
):

    if image_name in annotations:

        return annotations[image_name]

    stem = Path(image_name).stem

    if stem in annotations:

        return annotations[stem]

    raise KeyError(
        f"No annotation found for {image_name}"
    )


def convert_box_to_yolo(
    box,
    image_width,
    image_height,
):

    x = float(box["top-left-x"])
    y = float(box["top-left-y"])
    w = float(box["width"])
    h = float(box["height"])

    # Clamp box to image boundaries
    x = max(0.0, min(x, image_width))
    y = max(0.0, min(y, image_height))

    w = max(
        0.0,
        min(w, image_width - x),
    )

    h = max(
        0.0,
        min(h, image_height - y),
    )

    if w <= 0 or h <= 0:

        return None

    x_center = (
        x + w / 2.0
    ) / image_width

    y_center = (
        y + h / 2.0
    ) / image_height

    width_normalized = (
        w / image_width
    )

    height_normalized = (
        h / image_height
    )

    return (
        x_center,
        y_center,
        width_normalized,
        height_normalized,
    )


def get_class_id(box):

    if "class-id" in box:

        return int(
            box["class-id"]
        )

    class_name = box.get(
        "class"
    )

    for class_id, name in CLASS_ID_TO_NAME.items():

        if name == class_name:

            return class_id

    raise ValueError(
        f"Unknown class: {class_name}"
    )


def read_image_size(image_path):

    from PIL import Image

    with Image.open(image_path) as image:

        return image.size


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("SONAR DATASET → YOLO FORMAT")
    print("=" * 60)

    if not DATASET_DIR.exists():

        raise FileNotFoundError(
            f"Dataset directory not found:\n{DATASET_DIR}"
        )

    if not ANNOTATIONS_FILE.exists():

        raise FileNotFoundError(
            f"annotations.json not found:\n{ANNOTATIONS_FILE}"
        )

    print(
        f"Dataset:\n{DATASET_DIR}"
    )

    print(
        f"Annotations:\n{ANNOTATIONS_FILE}"
    )

    print()

    annotations = load_annotations()

    image_files = sorted(
        DATASET_DIR.glob(
            "marine-debris-aris3k-*.png"
        )
    )

    if not image_files:

        raise RuntimeError(
            "No FLS images found."
        )

    print(
        f"Images found: {len(image_files)}"
    )

    print(
        f"Annotation entries: {len(annotations)}"
    )

    print()

    # --------------------------------------------------------
    # Reproducible train/validation split
    # --------------------------------------------------------

    random.seed(
        RANDOM_SEED
    )

    shuffled = image_files.copy()

    random.shuffle(
        shuffled
    )

    validation_count = int(
        len(shuffled)
        * VAL_FRACTION
    )

    val_files = set(
        shuffled[:validation_count]
    )

    train_files = [
        image
        for image in shuffled
        if image not in val_files
    ]

    print(
        f"Training images: {len(train_files)}"
    )

    print(
        f"Validation images: {len(val_files)}"
    )

    print()

    # --------------------------------------------------------
    # Clean previous generated dataset
    # --------------------------------------------------------

    clean_output_directories()

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    train_boxes = 0
    val_boxes = 0

    skipped_boxes = 0

    class_counts = {
        class_id: 0
        for class_id in CLASS_ID_TO_NAME
    }

    # --------------------------------------------------------
    # Convert images and annotations
    # --------------------------------------------------------

    for split_name, files in [
        ("train", train_files),
        ("val", list(val_files)),
    ]:

        if split_name == "train":

            image_destination = TRAIN_IMAGES
            label_destination = TRAIN_LABELS

        else:

            image_destination = VAL_IMAGES
            label_destination = VAL_LABELS

        print(
            f"Converting {split_name} set..."
        )

        for index, image_path in enumerate(
            files,
            start=1,
        ):

            image_width, image_height = (
                read_image_size(
                    image_path
                )
            )

            entry = find_annotation_entry(
                annotations,
                image_path.name,
            )

            boxes = entry.get(
                "bounding-boxes",
                [],
            )

            label_lines = []

            for box in boxes:

                class_id = get_class_id(
                    box
                )

                converted = (
                    convert_box_to_yolo(
                        box,
                        image_width,
                        image_height,
                    )
                )

                if converted is None:

                    skipped_boxes += 1
                    continue

                (
                    x_center,
                    y_center,
                    width,
                    height,
                ) = converted

                label_lines.append(
                    (
                        f"{class_id} "
                        f"{x_center:.6f} "
                        f"{y_center:.6f} "
                        f"{width:.6f} "
                        f"{height:.6f}"
                    )
                )

                class_counts[
                    class_id
                ] += 1

            # Copy image
            shutil.copy2(
                image_path,
                image_destination
                / image_path.name,
            )

            # Write label
            label_path = (
                label_destination
                / f"{image_path.stem}.txt"
            )

            label_path.write_text(
                "\n".join(
                    label_lines
                )
                + "\n",
                encoding="utf-8",
            )

            if split_name == "train":

                train_boxes += len(
                    label_lines
                )

            else:

                val_boxes += len(
                    label_lines
                )

            if index % 250 == 0:

                print(
                    f"  {index}/{len(files)}"
                )

    # --------------------------------------------------------
    # Create dataset.yaml
    # --------------------------------------------------------

    yaml_lines = [
        "path: "
        + str(YOLO_ROOT.resolve()).replace(
            "\\",
            "/",
        ),
        "train: images/train",
        "val: images/val",
        "",
        f"nc: {len(CLASS_ID_TO_NAME)}",
        "names:",
    ]

    for class_id in sorted(
        CLASS_ID_TO_NAME
    ):

        yaml_lines.append(
            f"  {class_id}: "
            f"{CLASS_ID_TO_NAME[class_id]}"
        )

    DATASET_YAML.write_text(
        "\n".join(yaml_lines)
        + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)

    print(
        f"Training images : {len(train_files)}"
    )

    print(
        f"Validation images: {len(val_files)}"
    )

    print(
        f"Training boxes  : {train_boxes}"
    )

    print(
        f"Validation boxes: {val_boxes}"
    )

    print(
        f"Skipped boxes   : {skipped_boxes}"
    )

    print()
    print("CLASS DISTRIBUTION")

    for class_id in sorted(
        CLASS_ID_TO_NAME
    ):

        print(
            f"{class_id:2d} "
            f"{CLASS_ID_TO_NAME[class_id]:20s} "
            f"{class_counts[class_id]}"
        )

    print()

    print(
        f"Dataset YAML:\n{DATASET_YAML}"
    )


if __name__ == "__main__":

    main()

