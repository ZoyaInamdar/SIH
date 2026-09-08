import heapq
import math
from typing import List, Tuple, Optional

from .cost import haversine_distance_km, movement_cost

GridPoint = Tuple[int, int]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_distance_km(lat1, lon1, lat2, lon2)

def point_inside_hazard(latitude: float, longitude: float, hazards: List[dict]) -> bool:
    for hazard in hazards:
        radius_m = float(hazard.get("radius_m", 0))
        h_lat = float(hazard.get("latitude", 0))
        h_lon = float(hazard.get("longitude", 0))
        # Rapid bounding box rejection before trigonometric haversine
        max_deg = (radius_m / 111000.0) + 0.02
        if abs(latitude - h_lat) > max_deg or abs(longitude - h_lon) > max_deg * 2.5:
            continue
        distance_m = haversine_distance_km(latitude, longitude, h_lat, h_lon) * 1000
        if distance_m <= radius_m:
            return True
    return False

class AStarRouter:
    def __init__(self, grid: List[List[dict]], hazards: Optional[List[dict]] = None, ignore_environmental_penalties: bool = False):
        if not grid or not grid[0]:
            raise ValueError("Grid cannot be empty.")
        width = len(grid[0])
        for row in grid:
            if len(row) != width:
                raise ValueError("Grid must be rectangular.")
        self.grid = grid
        self.rows = len(grid)
        self.cols = width
        self.hazards = hazards or []
        self.ignore_environmental_penalties = ignore_environmental_penalties

    def valid_point(self, point: GridPoint) -> bool:
        row, col = point
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_blocked(self, point: GridPoint) -> bool:
        if not self.valid_point(point): return True
        cell = self.grid[point[0]][point[1]]
        if cell.get("blocked", False) or cell.get("land", False): return True
        if point_inside_hazard(cell["latitude"], cell["longitude"], self.hazards): return True
        return False

    def neighbors(self, point: GridPoint) -> List[GridPoint]:
        row, col = point
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        return [
            (row + dr, col + dc) for dr, dc in directions 
            if self.valid_point((row + dr, col + dc))
        ]

    def heuristic(self, point: GridPoint, goal: GridPoint) -> float:
        curr = self.grid[point[0]][point[1]]
        dest = self.grid[goal[0]][goal[1]]
        dlat = (dest["latitude"] - curr["latitude"]) * 111.12
        dlon = (dest["longitude"] - curr["longitude"]) * 52.0  # Cosine factor at ~62S
        return math.sqrt(dlat * dlat + dlon * dlon)

    def calculate_cell_cost(self, current: GridPoint, neighbor: GridPoint) -> float:
        current_cell = self.grid[current[0]][current[1]]
        next_cell = self.grid[neighbor[0]][neighbor[1]]
        distance_km = haversine_distance(
            current_cell["latitude"], current_cell["longitude"],
            next_cell["latitude"], next_cell["longitude"]
        )
        if self.ignore_environmental_penalties:
            return distance_km
        return movement_cost(
            distance_km=distance_km,
            sea_ice_concentration=next_cell.get("sea_ice", 0.0),
            wave_height_m=next_cell.get("wave_height", 0.0)
        )


    def find_route(self, start: GridPoint, goal: GridPoint) -> Optional[List[GridPoint]]:
        if not self.valid_point(start) or not self.valid_point(goal):
            raise ValueError("Invalid start or goal point.")
        if self.is_blocked(start) or self.is_blocked(goal):
            raise ValueError("Start or goal point is blocked.")

        open_set = []
        heapq.heappush(open_set, (self.heuristic(start, goal), 0.0, start))
        came_from = {}
        g_score = {start: 0.0}
        visited = set()

        while open_set:
            _, current_g, current = heapq.heappop(open_set)
            if current in visited: continue
            visited.add(current)
            if current == goal:
                return self.reconstruct_path(came_from, current)

            for neighbor in self.neighbors(current):
                if self.is_blocked(neighbor): continue
                movement = self.calculate_cell_cost(current, neighbor)
                if math.isinf(movement): continue

                tentative_g = current_g + movement
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self.heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor))
        return None

    @staticmethod
    def reconstruct_path(came_from, current) -> List[GridPoint]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path