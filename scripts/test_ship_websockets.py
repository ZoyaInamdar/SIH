import asyncio
import json
import websockets

async def test_ship_websocket():
    uri = "ws://127.0.0.1:8000/ws/nmea"
    async with websockets.connect(uri) as websocket:
        ship_positions = [
            {"latitude": -64.1230, "longitude": 72.4560, "speed_knots": 12.5, "heading_degrees": 135, "timestamp": "2026-09-06T16:40:00"},
            {"latitude": -64.1240, "longitude": 72.4575, "speed_knots": 12.6, "heading_degrees": 135, "timestamp": "2026-09-06T16:40:05"}
        ]
        for position in ship_positions:
            print(f"Sending position: {position['latitude']}, {position['longitude']}")
            await websocket.send(json.dumps(position))
            response = await websocket.recv()
            print(f"Server response: {response}")
            print("-" * 60)
            await asyncio.sleep(2)

asyncio.run(test_ship_websocket())