from backend.services.sonar_hazard_service import (
    clear_sonar_hazards,
    process_sonar_observation,
    get_sonar_hazards,
)


def test_sonar_observation_creates_hazard():

    clear_sonar_hazards()

    observation = {
        "observation_id": "OBS_TEST_001",

        "source_type": "SONAR",

        "sonar": {
            "targets": [
                {
                    "bounding_box": [
                        100,
                        120,
                        80,
                        60,
                    ],

                    "detection_confidence": 0.91,

                    "target_class": "tire",
                }
            ],

            "range_m": None,

            "bearing_deg": None,
        },

        "observed_at":
            "2026-09-07T00:00:00Z",
    }

    hazards = process_sonar_observation(
        observation
    )

    assert len(hazards) == 1

    hazard = hazards[0]

    assert (
        hazard.observation_id
        == "OBS_TEST_001"
    )

    assert (
        hazard.source_type
        == "SONAR"
    )

    assert (
        hazard.target_class
        == "tire"
    )

    assert (
        hazard.detection_confidence
        == 0.91
    )

    assert (
        hazard.bounding_box
        == [100, 120, 80, 60]
    )

    # No range/bearing means we MUST NOT
    # invent a geographic position.
    assert hazard.range_m is None
    assert hazard.bearing_deg is None

    assert hazard.latitude is None
    assert hazard.longitude is None

    assert hazard.localized is False

    assert hazard.advisory_only is True


def test_sonar_hazard_with_localization():

    clear_sonar_hazards()

    observation = {
        "observation_id": "OBS_TEST_002",

        "source_type": "SONAR",

        "sonar": {
            "targets": [
                {
                    "bounding_box": [
                        200,
                        200,
                        50,
                        50,
                    ],

                    "detection_confidence": 0.88,

                    "target_class": "propeller",
                }
            ],

            "range_m": 42.6,

            "bearing_deg": 18.4,
        },

        "observed_at":
            "2026-09-07T00:00:00Z",
    }

    hazards = process_sonar_observation(
        observation,

        vessel_latitude=-69.123,

        vessel_longitude=39.456,
    )

    assert len(hazards) == 1

    hazard = hazards[0]

    assert hazard.range_m == 42.6
    assert hazard.bearing_deg == 18.4

    assert hazard.latitude == -69.123
    assert hazard.longitude == 39.456

    assert hazard.localized is True

    assert hazard.advisory_only is True


def test_multiple_sonar_targets():

    clear_sonar_hazards()

    observation = {
        "observation_id": "OBS_TEST_003",

        "source_type": "SONAR",

        "sonar": {
            "targets": [

                {
                    "bounding_box": [
                        50,
                        50,
                        30,
                        30,
                    ],

                    "detection_confidence": 0.91,

                    "target_class": "tire",
                },

                {
                    "bounding_box": [
                        200,
                        100,
                        40,
                        50,
                    ],

                    "detection_confidence": 0.84,

                    "target_class": "chain",
                },
            ],

            "range_m": None,

            "bearing_deg": None,
        },

        "observed_at":
            "2026-09-07T00:00:00Z",
    }

    hazards = process_sonar_observation(
        observation
    )

    assert len(hazards) == 2

    assert (
        hazards[0].target_class
        == "tire"
    )

    assert (
        hazards[1].target_class
        == "chain"
    )

    assert all(
        hazard.localized is False
        for hazard in hazards
    )