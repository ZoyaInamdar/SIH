from backend.routing.astar import AStarRouter
from backend.routing.grid import create_ocean_grid


def main():

    print("=" * 50)
    print("ANTARCTIC ROUTING SYSTEM TEST")
    print("=" * 50)

    grid = create_ocean_grid(
        min_lat=-65.0,
        max_lat=-64.0,
        min_lon=-63.0,
        max_lon=-62.0,
        resolution=0.1
    )

    # Artificial test obstacle.
    # This is ONLY for testing the routing engine.
    for row in range(3, 7):

        if row < len(grid):

            middle = len(grid[row]) // 2

            grid[row][middle]["blocked"] = True

    router = AStarRouter(
        grid
    )

    start = (0, 0)

    goal = (
        len(grid) - 1,
        len(grid[0]) - 1
    )

    path = router.find_route(
        start,
        goal,
        vessel_draft_m=6.0
    )

    if path is None:

        print(
            "FAILURE: No route found."
        )

        return

    print(
        "SUCCESS: Route found."
    )

    print(
        f"Grid size: "
        f"{len(grid)} x {len(grid[0])}"
    )

    print(
        f"Route points: {len(path)}"
    )

    print(
        "Route:"
    )

    for point in path:

        print(
            f"  {point}"
        )

    blocked_used = any(
        grid[row][col]["blocked"]
        for row, col in path
    )

    if blocked_used:

        print(
            "FAILURE: Route crossed a blocked cell."
        )

        return

    print(
        "SUCCESS: Route avoided blocked cells."
    )

    print("=" * 50)
    print("ROUTING TEST PASSED")
    print("=" * 50)


if __name__ == "__main__":

    main()