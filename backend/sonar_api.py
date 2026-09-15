from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .database import update_iceberg_sonar_feedback
from .services.sonar_hazard_service import (
    process_sonar_observation,
    get_sonar_hazards,
    get_localized_sonar_hazards,
)


router = APIRouter(
    prefix="/api/sonar",
    tags=["sonar"],
)


# ---------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------

class SonarObservationRequest(BaseModel):

    observation: Dict[str, Any]

    vessel_latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
    )

    vessel_longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
    )


class SonarIcebergFeedbackRequest(BaseModel):
    iceberg_id: str
    estimated_draft_m: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "sonar-corrected"


# ---------------------------------------------------------------------
# Submit sonar observation
# ---------------------------------------------------------------------

@router.post("/observation")
def submit_sonar_observation(
    request: SonarObservationRequest,
):

    hazards = process_sonar_observation(
        observation=request.observation,

        vessel_latitude=request.vessel_latitude,

        vessel_longitude=request.vessel_longitude,
    )

    # If observation provides iceberg feedback, update the IcebergRecord
    obs = request.observation
    iceberg_id = obs.get("iceberg_id")
    draft_m = obs.get("estimated_draft_m") or obs.get("draft_m")
    conf = obs.get("confidence") or obs.get("draft_confidence")
    if iceberg_id and draft_m is not None:
        update_iceberg_sonar_feedback(
            iceberg_id=iceberg_id,
            estimated_draft_m=float(draft_m),
            confidence=float(conf) if conf is not None else 0.90,
            source="sonar-corrected"
        )

    return {
        "status": "accepted",

        "observation_id":
            request.observation.get(
                "observation_id"
            ),

        "hazards_created":
            len(hazards),

        "hazards": [
            hazard.to_dict()
            for hazard in hazards
        ],
    }


# ---------------------------------------------------------------------
# Sonar Feedback Loop for Iceberg Draft & Confidence
# ---------------------------------------------------------------------

@router.post("/feedback/iceberg")
def submit_sonar_iceberg_feedback(request: SonarIcebergFeedbackRequest):
    """
    Direct Sonar Feedback Loop:
    Updates an existing IcebergRecord's estimated_draft_m and confidence.
    This then propagates directly down into the RiskState aggregation layer.
    """
    updated = update_iceberg_sonar_feedback(
        iceberg_id=request.iceberg_id,
        estimated_draft_m=request.estimated_draft_m,
        confidence=request.confidence,
        source=request.source,
    )
    return {
        "status": "success" if updated else "not_found",
        "iceberg_id": request.iceberg_id,
        "estimated_draft_m": request.estimated_draft_m,
        "confidence": request.confidence,
        "propagated_to_risk_state": True
    }


# ---------------------------------------------------------------------
# Get all sonar hazards
# ---------------------------------------------------------------------

@router.get("/hazards")
def list_sonar_hazards():

    hazards = get_sonar_hazards()

    return {
        "count": len(hazards),

        "hazards": hazards,
    }


# ---------------------------------------------------------------------
# Get only geographically localized hazards
# ---------------------------------------------------------------------

@router.get("/hazards/localized")
def list_localized_sonar_hazards():

    hazards = get_localized_sonar_hazards()

    return {
        "count": len(hazards),

        "hazards": hazards,
    }