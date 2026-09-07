import cv2
import numpy as np

from sonar.ictineu_denoising import (
    denoise_sonar_image,
    reduce_acoustic_noise,
    enhance_sonar_contrast,
    suppress_background_clutter,
    clean_target_mask,
)


def create_test_sonar_image():

    image = np.zeros(
        (300, 400),
        dtype=np.uint8,
    )

    # Simulated target
    cv2.rectangle(
        image,
        (170, 120),
        (240, 190),
        220,
        -1,
    )

    # Simulated acoustic noise
    noise = np.random.default_rng(42).normal(
        0,
        25,
        image.shape,
    )

    noisy = image.astype(
        np.float32
    ) + noise

    return np.clip(
        noisy,
        0,
        255,
    ).astype(np.uint8)


def test_noise_reduction():

    image = create_test_sonar_image()

    result = reduce_acoustic_noise(image)

    assert result.shape == image.shape
    assert result.dtype == np.uint8


def test_clahe_enhancement():

    image = create_test_sonar_image()

    result = enhance_sonar_contrast(image)

    assert result.shape == image.shape
    assert result.dtype == np.uint8


def test_background_suppression():

    image = create_test_sonar_image()

    result = suppress_background_clutter(
        image
    )

    assert result.shape == image.shape
    assert result.dtype == np.uint8


def test_mask_generation():

    image = create_test_sonar_image()

    mask = clean_target_mask(image)

    assert mask.shape == image.shape
    assert mask.dtype == np.uint8

    unique_values = set(
        np.unique(mask).tolist()
    )

    assert unique_values.issubset(
        {0, 255}
    )


def test_complete_ictineu_pipeline():

    image = create_test_sonar_image()

    result = denoise_sonar_image(image)

    assert result.original.shape == image.shape
    assert result.normalized.shape == image.shape
    assert result.denoised.shape == image.shape
    assert result.enhanced.shape == image.shape
    assert result.background_removed.shape == image.shape
    assert result.final.shape == image.shape

    assert result.final.dtype == np.uint8