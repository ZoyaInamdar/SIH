from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SonarKnowledge:
    """
    Knowledge associated with a detected sonar target.

    This does NOT claim that a marine-debris class is
    an iceberg. It describes the type of underwater
    object and its potential hazard relevance.
    """

    target_class: str
    category: str
    hazard_relevance: str
    recommended_action: str
    description: str


SONAR_KNOWLEDGE_BASE = {

    "can": SonarKnowledge(
        target_class="can",
        category="marine_debris",
        hazard_relevance="low",
        recommended_action="monitor",
        description="Small marine-debris object.",
    ),

    "bottle": SonarKnowledge(
        target_class="bottle",
        category="marine_debris",
        hazard_relevance="low",
        recommended_action="monitor",
        description="Bottle-like marine-debris object.",
    ),

    "drink-carton": SonarKnowledge(
        target_class="drink-carton",
        category="marine_debris",
        hazard_relevance="low",
        recommended_action="monitor",
        description="Carton-like marine-debris object.",
    ),

    "chain": SonarKnowledge(
        target_class="chain",
        category="underwater_obstruction",
        hazard_relevance="high",
        recommended_action="avoid_if_confirmed",
        description="Chain-like underwater obstruction.",
    ),

    "propeller": SonarKnowledge(
        target_class="propeller",
        category="underwater_obstruction",
        hazard_relevance="high",
        recommended_action="avoid_if_confirmed",
        description="Propeller-like underwater object.",
    ),

    "tire": SonarKnowledge(
        target_class="tire",
        category="marine_debris",
        hazard_relevance="medium",
        recommended_action="monitor",
        description="Large marine-debris object.",
    ),

    "hook": SonarKnowledge(
        target_class="hook",
        category="underwater_obstruction",
        hazard_relevance="high",
        recommended_action="avoid_if_confirmed",
        description="Hook-like underwater obstruction.",
    ),

    "valve": SonarKnowledge(
        target_class="valve",
        category="underwater_obstruction",
        hazard_relevance="high",
        recommended_action="avoid_if_confirmed",
        description="Valve-like underwater object.",
    ),

    "shampoo-bottle": SonarKnowledge(
        target_class="shampoo-bottle",
        category="marine_debris",
        hazard_relevance="low",
        recommended_action="monitor",
        description="Bottle-like marine-debris object.",
    ),

    "standing-bottle": SonarKnowledge(
        target_class="standing-bottle",
        category="marine_debris",
        hazard_relevance="low",
        recommended_action="monitor",
        description="Standing bottle-like object.",
    ),
}


DEFAULT_SONAR_KNOWLEDGE = SonarKnowledge(
    target_class="unknown",
    category="unknown_underwater_object",
    hazard_relevance="medium",
    recommended_action="monitor",
    description="Unclassified underwater sonar target.",
)


def get_target_knowledge(
    target_class: Optional[str],
) -> SonarKnowledge:
    """
    Return knowledge for a detected target class.

    Unknown classes are handled safely rather than
    causing the navigation pipeline to fail.
    """

    if not target_class:
        return DEFAULT_SONAR_KNOWLEDGE

    return SONAR_KNOWLEDGE_BASE.get(
        target_class.lower(),
        SonarKnowledge(
            target_class=target_class,
            category=DEFAULT_SONAR_KNOWLEDGE.category,
            hazard_relevance=DEFAULT_SONAR_KNOWLEDGE.hazard_relevance,
            recommended_action=DEFAULT_SONAR_KNOWLEDGE.recommended_action,
            description=DEFAULT_SONAR_KNOWLEDGE.description,
        ),
    )


def get_hazard_score(
    detection_confidence: float,
    hazard_relevance: str,
) -> float:
    """
    Combine detector confidence with qualitative
    hazard relevance.

    This is a prototype prioritization score.
    It is NOT a calibrated probability of collision.
    """

    confidence = max(
        0.0,
        min(1.0, float(detection_confidence)),
    )

    relevance_multiplier = {
        "low": 0.5,
        "medium": 0.75,
        "high": 1.0,
    }.get(
        hazard_relevance.lower(),
        0.75,
    )

    return round(
        confidence * relevance_multiplier,
        4,
    )


def enrich_detection(
    target_class: Optional[str],
    detection_confidence: float,
) -> dict:
    """
    Convert a raw YOLO detection into a
    knowledge-enriched sonar hazard description.
    """

    knowledge = get_target_knowledge(
        target_class
    )

    hazard_score = get_hazard_score(
        detection_confidence,
        knowledge.hazard_relevance,
    )

    return {
        "target_class": knowledge.target_class,
        "category": knowledge.category,
        "hazard_relevance": knowledge.hazard_relevance,
        "recommended_action": knowledge.recommended_action,
        "description": knowledge.description,
        "detection_confidence": round(
            float(detection_confidence),
            4,
        ),
        "hazard_score": hazard_score,
    }