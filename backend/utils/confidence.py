from typing import Optional


def clamp_confidence(
    value: Optional[float]
) -> float:

    if value is None:
        return 0.5

    return max(
        0.0,
        min(
            1.0,
            float(value)
        )
    )


def get_confidence_level(
    confidence: Optional[float]
) -> str:

    confidence = clamp_confidence(
        confidence
    )

    if confidence >= 0.75:
        return "high"

    if confidence >= 0.50:
        return "medium"

    return "low"


def get_confidence_status(
    confidence: Optional[float]
) -> dict:

    confidence = clamp_confidence(
        confidence
    )

    return {
        "confidence": round(
            confidence,
            3
        ),
        "confidence_level": get_confidence_level(
            confidence
        )
    }