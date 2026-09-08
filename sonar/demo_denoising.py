from pathlib import Path

import cv2
import numpy as np

from .ictineu_denoising import (
    denoise_sonar_image,
    clean_target_mask,
)


# ============================================================
# PATHS
# ============================================================

IMAGE_PATH = Path(
    "data/sonar/data/raw/"
    "marine-debris-watertank-release/"
    "fls-images/"
    "marine-debris-aris3k-0.png"
)

OUTPUT_DIR = Path(
    "sonar/outputs/demo"
)


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 60)
    print("SONAR DENOISING DEMO")
    print("=" * 60)

    # --------------------------------------------------------
    # LOAD IMAGE
    # --------------------------------------------------------

    image = cv2.imread(
        str(IMAGE_PATH),
        cv2.IMREAD_UNCHANGED,
    )

    if image is None:
        raise FileNotFoundError(
            f"Could not load image:\n{IMAGE_PATH}"
        )

    print(f"Input image: {IMAGE_PATH}")
    print(f"Image shape: {image.shape}")

    # --------------------------------------------------------
    # DENOISING
    # --------------------------------------------------------

    result = denoise_sonar_image(
        image
    )

    # --------------------------------------------------------
    # SAVE ORIGINAL
    # --------------------------------------------------------

    cv2.imwrite(
        str(
            OUTPUT_DIR / "01_original.png"
        ),
        result.original,
    )

    # --------------------------------------------------------
    # SAVE DENOISED
    # --------------------------------------------------------

    cv2.imwrite(
        str(
            OUTPUT_DIR / "02_denoised.png"
        ),
        result.final,
    )

    # --------------------------------------------------------
    # SAVE MASK
    # --------------------------------------------------------

    mask = clean_target_mask(
        result.final
    )

    cv2.imwrite(
        str(
            OUTPUT_DIR / "03_mask.png"
        ),
        mask,
    )

    # --------------------------------------------------------
    # CREATE SIDE-BY-SIDE COMPARISON
    # --------------------------------------------------------

    original = result.original
    denoised = result.final

    # Make sure both have identical dimensions.
    if original.shape != denoised.shape:
        denoised = cv2.resize(
            denoised,
            (
                original.shape[1],
                original.shape[0],
            ),
        )

    comparison = np.hstack(
        [
            original,
            denoised,
        ]
    )

    cv2.imwrite(
        str(
            OUTPUT_DIR / "04_comparison.png"
        ),
        comparison,
    )

    print()
    print("Denoising complete.")
    print()
    print("Generated files:")

    for file in sorted(
        OUTPUT_DIR.glob("*.png")
    ):
        print(f"  {file}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()