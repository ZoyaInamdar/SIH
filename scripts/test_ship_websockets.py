import asyncio
import json

import websockets


async def test_ship_websocket():

    uri = "ws://127.0.0.1:8000/ws/ship"

    async with websockets.connect(uri) as websocket:

        ship_positions = [
            {
                "latitude": -64.1230,
                "longitude": 72.4560,
                "speed_knots": 12.5,
                "heading_degrees": 135,
                "timestamp": "2026-09-06T16:40:00"
            },
            {
                "latitude": -64.1240,
                "longitude": 72.4575,
                "speed_knots": 12.6,
                "heading_degrees": 135,
                "timestamp": "2026-09-06T16:40:05"
            },
            {
                "latitude": -64.1250,
                "longitude": 72.4590,
                "speed_knots": 12.7,
                "heading_degrees": 136,
                "timestamp": "2026-09-06T16:40:10"
            },
            {
                "latitude": -64.1260,
                "longitude": 72.4605,
                "speed_knots": 12.8,
                "heading_degrees": 136,
                "timestamp": "2026-09-06T16:40:15"
            },
            {
                "latitude": -64.1270,
                "longitude": 72.4620,
                "speed_knots": 12.8,
                "heading_degrees": 137,
                "timestamp": "2026-09-06T16:40:20"
            }
        ]

        for position in ship_positions:

            print(
                f"Sending position: "
                f"{position['latitude']}, "
                f"{position['longitude']}"
            )

            await websocket.send(
                json.dumps(position)
            )

            response = await websocket.recv()

            print(
                f"Server response: {response}"
            )

            print("-" * 60)

            # Wait before sending the next position
            await asyncio.sleep(2)


asyncio.run(test_ship_websocket())