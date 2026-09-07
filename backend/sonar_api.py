from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

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