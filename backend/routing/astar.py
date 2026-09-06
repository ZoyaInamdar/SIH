import heapq
import math
from typing import List, Tuple, Optional


from .cost import (
    haversine_distance_km,
    movement_cost
)


GridPoint = Tuple[int, int]


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:

    return haversine_distance_km(
        lat1,
        lon1,
        lat2,
        lon2
    )


def point_inside_hazard(
    latitude: float,
    longitude: float,
    hazards: List[dict]
) -> bool:

    for hazard in hazards:

        hazard_lat = hazard["latitude"]
        hazard_lon = hazard["longitude"]

        radius_m = float(
            hazard.get("radius_m", 0)
        )

        distance_m = (
            haversine_distance_km(
                latitude,
                longitude,
                hazard_lat,
                hazard_lon
            ) * 1000
        )

        if distance_m <= radius_m:
            return True

    return False


class AStarRouter:

    def __init__(
        self,
        grid: List[List[dict]],
        hazards: Optional[List[dict]] = None
    ):

        if not grid:
            raise ValueError("Grid cannot be empty.")

        if not grid[0]:
            raise ValueError("Grid rows cannot be empty.")

        width = len(grid[0])

        for row in grid:

            if len(row) != width:
                raise ValueError(
                    "Grid must be rectangular."
                )

        self.grid = grid
        self.rows = len(grid)
        self.cols = width
        self.hazards = hazards or []

    def valid_point(
        self,
        point: GridPoint
    ) -> bool:

        row, col = point

        return (
            0 <= row < self.rows
            and 0 <= col < self.cols
        )

    def is_blocked(
        self,
        point: GridPoint
    ) -> bool:

        if not self.valid_point(point):
            return True

        row, col = point
        cell = self.grid[row][col]

        if cell.get("blocked", False):
            return True

        if cell.get("land", False):
            return True

        if point_inside_hazard(
            cell["latitude"],
            cell["longitude"],
            self.hazards
        ):
            return True

        return False

    def neighbors(
        self,
        point: GridPoint
    ) -> List[GridPoint]:

        row, col = point

        directions = [
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1)
        ]

        result = []

        for dr, dc in directions:

            neighbor = (
                row + dr,
                col + dc
            )

            if self.valid_point(neighbor):
                result.append(neighbor)

        return result

    def heuristic(
        self,
        point: GridPoint,
        goal: GridPoint
    ) -> float:

        row1, col1 = point
        row2, col2 = goal

        return math.sqrt(
            (row2 - row1) ** 2
            + (col2 - col1) ** 2
        )

    def calculate_cell_cost(
        self,
        current: GridPoint,
        neighbor: GridPoint,
        vessel_draft_m: float
    ) -> float:

        r1, c1 = current
        r2, c2 = neighbor

        current_cell = self.grid[r1][c1]
        next_cell = self.grid[r2][c2]

        distance_km = haversine_distance(
            current_cell["latitude"],
            current_cell["longitude"],
            next_cell["latitude"],
            next_cell["longitude"]
        )

        return movement_cost(
            distance_km=distance_km,
            sea_ice_concentration=next_cell.get(
                "sea_ice",
                0.0
            ),
            wave_height_m=next_cell.get(
                "wave_height",
                0.0
            ),
            water_depth_m=next_cell.get(
                "water_depth",
                1000.0
            ),
            vessel_draft_m=vessel_draft_m
        )

    def find_route(
        self,
        start: GridPoint,
        goal: GridPoint,
        vessel_draft_m: float = 6.0
    ) -> Optional[List[GridPoint]]:

        if not self.valid_point(start):
            raise ValueError("Invalid start point.")

        if not self.valid_point(goal):
            raise ValueError("Invalid goal point.")

        if self.is_blocked(start):
            raise ValueError(
                "Start point is blocked."
            )

        if self.is_blocked(goal):
            raise ValueError(
                "Destination point is blocked."
            )

        open_set = []

        heapq.heappush(
            open_set,
            (
                self.heuristic(start, goal),
                0.0,
                start
            )
        )

        came_from = {}

        g_score = {
            start: 0.0
        }

        visited = set()

        while open_set:

            _, current_g, current = heapq.heappop(
                open_set
            )

            if current in visited:
                continue

            visited.add(current)

            if current == goal:

                return self.reconstruct_path(
                    came_from,
                    current
                )

            for neighbor in self.neighbors(current):

                if self.is_blocked(neighbor):
                    continue

                movement = self.calculate_cell_cost(
                    current,
                    neighbor,
                    vessel_draft_m
                )

                if math.isinf(movement):
                    continue

                tentative_g = current_g + movement

                if tentative_g < g_score.get(
                    neighbor,
                    float("inf")
                ):

                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    f_score = (
                        tentative_g
                        + self.heuristic(
                            neighbor,
                            goal
                        )
                    )

                    heapq.heappush(
                        open_set,
                        (
                            f_score,
                            tentative_g,
                            neighbor
                        )
                    )

        return None

    @staticmethod
    def reconstruct_path(
        came_from,
        current
    ) -> List[GridPoint]:

        path = [current]

        while current in came_from:

            current = came_from[current]
            path.append(current)

        path.reverse()

        return path