import asyncio
import json
from typing import Optional

import pynmea2


class NMEAService:

    def __init__(self):

        self.latest_position = None

        self.clients = set()

    async def register(
        self,
        websocket
    ):

        self.clients.add(
            websocket
        )

    async def unregister(
        self,
        websocket
    ):

        self.clients.discard(
            websocket
        )

    def parse_sentence(
        self,
        sentence: str
    ) -> Optional[dict]:

        sentence = sentence.strip()

        if not sentence:
            return None

        try:

            message = pynmea2.parse(
                sentence
            )

        except Exception:

            return None

        latitude = getattr(
            message,
            "latitude",
            None
        )

        longitude = getattr(
            message,
            "longitude",
            None
        )

        if latitude is None or longitude is None:

            return None

        speed_knots = getattr(
            message,
            "spd_over_grnd",
            None
        )

        heading = getattr(
            message,
            "true_course",
            None
        )

        if speed_knots is None:
            speed_knots = 0.0

        if heading is None:
            heading = 0.0

        position = {
            "latitude": float(
                latitude
            ),
            "longitude": float(
                longitude
            ),
            "speed_knots": float(
                speed_knots
            ),
            "heading_degrees": float(
                heading
            ),
            "timestamp": getattr(
                message,
                "timestamp",
                None
            ).isoformat()
            if getattr(
                message,
                "timestamp",
                None
            )
            else ""
        }

        self.latest_position = position

        return position

    async def broadcast(
        self,
        position: dict
    ):

        disconnected = []

        payload = json.dumps(
            position
        )

        for websocket in self.clients:

            try:

                await websocket.send_text(
                    payload
                )

            except Exception:

                disconnected.append(
                    websocket
                )

        for websocket in disconnected:

            await self.unregister(
                websocket
            )


nmea_service = NMEAService()