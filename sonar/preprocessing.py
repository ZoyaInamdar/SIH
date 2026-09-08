from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class PreprocessedSonar:
    original_gray: np.ndarray
    denoised: np.ndarray
    enhanced: np.ndarray
    mask: np.ndarray


def _normalize_uint8(image: np.ndarray) -> np.ndarray:
    image = image.astype(np.float32)

    min_val = float(np.min(image))
    max_val = float(np.max(image))

    if max_val <= min_val:
        return np.zeros_like(image, dtype=np.uint8)

    normalized = (image - min_val) / (max_val - min_val)
    return np.clip(normalized * 255.0, 0, 255).astype(np.uint8)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image is None:
        raise ValueError("Image cannot be None.")

    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] == 4:
        gray = image[:, :, :3].mean(axis=2)
    elif image.ndim == 3 and image.shape[2] == 3:
        gray = (
            0.299 * image[:, :, 0]
            + 0.587 * image[:, :, 1]
            + 0.114 * image[:, :, 2]
        )
    else:
        raise ValueError(f"Unsupported image shape: {image.shape}")

    return _normalize_uint8(gray)


def preprocess_sonar_image(
    image: np.ndarray,
    denoise_kernel: int = 3,
    clahe_clip_limit: float = 2.0,
    clahe_grid_size: int = 8,
    threshold_method: str = "otsu",
) -> PreprocessedSonar:

    import cv2

    gray = to_grayscale(image)

    if denoise_kernel % 2 == 0:
        raise ValueError("denoise_kernel must be odd.")

    denoised = cv2.GaussianBlur(
        gray,
        (denoise_kernel, denoise_kernel),
        0,
    )

    clahe = cv2.createCLAHE(
        clipLimit=clahe_clip_limit,
        tileGridSize=(clahe_grid_size, clahe_grid_size),
    )

    enhanced = clahe.apply(denoised)

    if threshold_method == "otsu":
        _, mask = cv2.threshold(
            enhanced,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
    elif threshold_method == "adaptive":
        mask = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )
    else:
        raise ValueError(
            "threshold_method must be 'otsu' or 'adaptive'."
        )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (3, 3),
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel,
        iterations=1,
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=1,
    )

    return PreprocessedSonar(
        original_gray=gray,
        denoised=denoised,
        enhanced=enhanced,
        mask=mask,
    )
