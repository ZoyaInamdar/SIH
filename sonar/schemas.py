from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from datetime import datetime, timezone
import json


@dataclass
class SonarTarget:
    bounding_box: Tuple[int, int, int, int]
    detection_confidence: float
    target_class: Optional[str] = None


@dataclass
class SonarObservation:
    observation_id: str
    source_type: str
    targets: List[SonarTarget]
    range_m: Optional[float]
    bearing_deg: Optional[float]
    observed_at: str

    def to_dict(self):
        return {
            "observation_id": self.observation_id,
            "source_type": self.source_type,
            "sonar": {
                "targets": [
                    {
                        "bounding_box": list(target.bounding_box),
                        "detection_confidence": round(
                            target.detection_confidence,
                            4,
                        ),
                        "target_class": target.target_class,
                    }
                    for target in self.targets
                ],
                "range_m": self.range_m,
                "bearing_deg": self.bearing_deg,
            },
            "observed_at": self.observed_at,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            indent=2,
        )


def create_observation(
    detections,
    observation_id: str,
    observed_at: Optional[str] = None,
    range_m: Optional[float] = None,
    bearing_deg: Optional[float] = None,
):
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat()

    targets = [
        SonarTarget(
            bounding_box=d.bbox,
            detection_confidence=d.detection_score,
        )
        for d in detections
    ]

    return SonarObservation(
        observation_id=observation_id,
        source_type="SONAR",
        targets=targets,
        range_m=range_m,
        bearing_deg=bearing_deg,
        observed_at=observed_at,
    )
