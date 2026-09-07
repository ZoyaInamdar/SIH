from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class DenoisedSonar:
    """
    Result of the sonar noise-reduction pipeline.

    original:
        Original grayscale sonar image.

    normalized:
        Intensity-normalized image.

    denoised:
        Image after acoustic-noise reduction.

    enhanced:
        CLAHE-enhanced image.

    background_removed:
        Image after local-background/clutter suppression.

    final:
        Final image passed to the detector.
    """

    original: np.ndarray
    normalized: np.ndarray
    denoised: np.ndarray
    enhanced: np.ndarray
    background_removed: np.ndarray
    final: np.ndarray


def _normalize(image: np.ndarray) -> np.ndarray:
    """
    Normalize an image to uint8 [0, 255].
    """

    image = image.astype(np.float32)

    min_value = float(np.min(image))
    max_value = float(np.max(image))

    if max_value <= min_value:
        return np.zeros_like(
            image,
            dtype=np.uint8,
        )

    normalized = (
        (image - min_value)
        / (max_value - min_value)
    )

    return np.clip(
        normalized * 255.0,
        0,
        255,
    ).astype(np.uint8)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """
    Convert an input sonar image to grayscale.

    Supports:
        H x W
        H x W x 3
        H x W x 4
    """

    if image is None:
        raise ValueError("Input image cannot be None.")

    if not isinstance(image, np.ndarray):
        raise TypeError(
            "Input image must be a numpy.ndarray."
        )

    if image.ndim == 2:
        gray = image

    elif image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

    elif image.ndim == 3 and image.shape[2] == 4:
        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2GRAY,
        )

    else:
        raise ValueError(
            "Expected grayscale, BGR, or BGRA image."
        )

    return _normalize(gray)


def reduce_acoustic_noise(
    gray: np.ndarray,
    median_kernel: int = 3,
    gaussian_kernel: int = 3,
) -> np.ndarray:
    """
    Reduce small isolated acoustic/speckle-like noise
    while preserving target boundaries.

    Median filtering is applied first, followed by
    a light Gaussian filter.
    """

    if median_kernel < 3 or median_kernel % 2 == 0:
        raise ValueError(
            "median_kernel must be an odd integer >= 3."
        )

    if gaussian_kernel < 3 or gaussian_kernel % 2 == 0:
        raise ValueError(
            "gaussian_kernel must be an odd integer >= 3."
        )

    median = cv2.medianBlur(
        gray,
        median_kernel,
    )

    denoised = cv2.GaussianBlur(
        median,
        (gaussian_kernel, gaussian_kernel),
        0,
    )

    return denoised


def enhance_sonar_contrast(
    image: np.ndarray,
    clip_limit: float = 2.0,
    grid_size: int = 8,
) -> np.ndarray:
    """
    Local contrast enhancement using CLAHE.

    CLAHE is useful for sonar imagery because
    target intensity can vary across the image.
    """

    if clip_limit <= 0:
        raise ValueError(
            "clip_limit must be > 0."
        )

    if grid_size <= 0:
        raise ValueError(
            "grid_size must be > 0."
        )

    clahe = cv2.createCLAHE(
        clipLimit=clip_limit,
        tileGridSize=(
            grid_size,
            grid_size,
        ),
    )

    return clahe.apply(image)


def suppress_background_clutter(
    image: np.ndarray,
    background_kernel_size: int = 31,
) -> np.ndarray:
    """
    Suppress slowly varying background/clutter.

    A morphological opening estimates the local
    background. Subtracting it emphasizes localized
    structures such as potential targets.

    This is an image-processing approximation for
    FLS clutter suppression, not a proprietary
    ICTINEU algorithm.
    """

    if background_kernel_size < 3:
        raise ValueError(
            "background_kernel_size must be >= 3."
        )

    if background_kernel_size % 2 == 0:
        background_kernel_size += 1

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (
            background_kernel_size,
            background_kernel_size,
        ),
    )

    background = cv2.morphologyEx(
        image,
        cv2.MORPH_OPEN,
        kernel,
    )

    foreground = cv2.subtract(
        image,
        background,
    )

    return _normalize(foreground)


def clean_target_mask(
    image: np.ndarray,
    threshold_method: str = "otsu",
) -> np.ndarray:
    """
    Create a cleaned binary mask for potential
    target regions.

    This mask is primarily useful for visualization
    and classical analysis. YOLO remains the primary
    detector.
    """

    if threshold_method == "otsu":

        _, mask = cv2.threshold(
            image,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

    elif threshold_method == "adaptive":

        mask = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )

    else:

        raise ValueError(
            "threshold_method must be 'otsu' "
            "or 'adaptive'."
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

    return mask


def denoise_sonar_image(
    image: np.ndarray,
    median_kernel: int = 3,
    gaussian_kernel: int = 3,
    clahe_clip_limit: float = 2.0,
    clahe_grid_size: int = 8,
    background_kernel_size: int = 31,
) -> DenoisedSonar:
    """
    Complete FLS sonar denoising pipeline.

    Pipeline:

        Input
          ↓
        Grayscale
          ↓
        Normalization
          ↓
        Median + Gaussian noise reduction
          ↓
        CLAHE contrast enhancement
          ↓
        Background/clutter suppression
          ↓
        Final normalized sonar image

    The final image can be passed to YOLO.
    """

    original = to_grayscale(image)

    normalized = _normalize(original)

    denoised = reduce_acoustic_noise(
        normalized,
        median_kernel=median_kernel,
        gaussian_kernel=gaussian_kernel,
    )

    enhanced = enhance_sonar_contrast(
        denoised,
        clip_limit=clahe_clip_limit,
        grid_size=clahe_grid_size,
    )

    background_removed = suppress_background_clutter(
        enhanced,
        background_kernel_size=background_kernel_size,
    )

    final = _normalize(background_removed)

    return DenoisedSonar(
        original=original,
        normalized=normalized,
        denoised=denoised,
        enhanced=enhanced,
        background_removed=background_removed,
        final=final,
    )