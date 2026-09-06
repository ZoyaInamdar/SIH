from backend.routing.astar import (
    AStarRouter
)


def create_test_grid():

    grid = []

    for row in range(10):

        grid_row = []

        for col in range(10):

            grid_row.append({

                "latitude":
                    -60.0 + row * 0.1,

                "longitude":
                    70.0 + col * 0.1,

                "blocked":
                    False,

                "sea_ice":
                    0.0,

                "wave_height":
                    0.0,

                "water_depth":
                    1000.0

            })

        grid.append(
            grid_row
        )

    return grid


def main():

    grid = create_test_grid()

    # --------------------------------------------------------
    # Create an artificial obstacle.
    #
    # A* should find a path around it.
    # --------------------------------------------------------

    for row in range(3, 7):

        grid[row][5][
            "blocked"
        ] = True

    router = AStarRouter(
        grid=grid
    )

    path = router.find_route(
        start=(0, 0),
        goal=(9, 9),
        vessel_draft_m=6.0
    )

    if path is None:

        print(
            "ERROR: A* could not find a route."
        )

        return

    print(
        "================================"
    )

    print(
        "A* ROUTING TEST"
    )

    print(
        "================================"
    )

    print(
        "SUCCESS: Route found."
    )

    print(
        "Number of grid points:",
        len(path)
    )

    print()

    print(
        "Route:"
    )

    for index, point in enumerate(
        path,
        start=1
    ):

        print(
            f"{index:02d}. {point}"
        )

    print()

    # --------------------------------------------------------
    # Verify that the route does not enter the
    # artificial blocked cells.
    # --------------------------------------------------------

    blocked_cells = {
        (row, 5)
        for row in range(3, 7)
    }

    collision = (
        set(path)
        &
        blocked_cells
    )

    if collision:

        print(
            "ERROR: Route entered blocked cells:"
        )

        print(
            collision
        )

        return

    print(
        "SUCCESS: Route avoided blocked cells."
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()