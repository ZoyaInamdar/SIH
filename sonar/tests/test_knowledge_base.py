from sonar.knowledge_base import (
    get_target_knowledge,
    get_hazard_score,
    enrich_detection,
)


def test_known_target():

    knowledge = get_target_knowledge(
        "chain"
    )

    assert knowledge.target_class == "chain"
    assert knowledge.category == (
        "underwater_obstruction"
    )
    assert knowledge.hazard_relevance == "high"


def test_low_risk_target():

    knowledge = get_target_knowledge(
        "bottle"
    )

    assert knowledge.category == (
        "marine_debris"
    )
    assert knowledge.hazard_relevance == "low"


def test_unknown_target():

    knowledge = get_target_knowledge(
        "unknown-object"
    )

    assert knowledge.target_class == (
        "unknown-object"
    )

    assert knowledge.category == (
        "unknown_underwater_object"
    )


def test_missing_target_class():

    knowledge = get_target_knowledge(None)

    assert knowledge.category == (
        "unknown_underwater_object"
    )


def test_hazard_score():

    score = get_hazard_score(
        detection_confidence=0.8,
        hazard_relevance="high",
    )

    assert score == 0.8


def test_hazard_score_is_clamped():

    score = get_hazard_score(
        detection_confidence=1.5,
        hazard_relevance="high",
    )

    assert score == 1.0


def test_enrich_detection():

    result = enrich_detection(
        target_class="chain",
        detection_confidence=0.9,
    )

    assert result["target_class"] == "chain"
    assert result["category"] == (
        "underwater_obstruction"
    )
    assert result["hazard_relevance"] == "high"
    assert result["detection_confidence"] == 0.9
    assert result["hazard_score"] == 0.9