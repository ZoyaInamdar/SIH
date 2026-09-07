import numpy as np
from sonar.preprocessing import to_grayscale, preprocess_sonar_image


def test_grayscale_conversion():
    image = np.zeros((100, 100, 4), dtype=np.uint8)

    gray = to_grayscale(image)

    assert gray.shape == (100, 100)
    assert gray.dtype == np.uint8


def test_preprocessing_output():
    image = np.zeros((100, 100, 4), dtype=np.uint8)

    image[40:60, 40:60, :3] = 255

    result = preprocess_sonar_image(image)

    assert result.original_gray.shape == (100, 100)
    assert result.denoised.shape == (100, 100)
    assert result.enhanced.shape == (100, 100)
    assert result.mask.shape == (100, 100)
