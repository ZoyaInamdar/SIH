from backend.routing.astar import AStarRouter

def create_test_grid():
    grid = []
    for row in range(10):
        grid_row = []
        for col in range(10):
            grid_row.append({"latitude": -60.0 + row * 0.1, "longitude": 70.0 + col * 0.1, "blocked": False, "sea_ice": 0.0, "wave_height": 0.0})
        grid.append(grid_row)
    return grid

def main():
    grid = create_test_grid()
    for row in range(3, 7):
        grid[row][5]["blocked"] = True

    router = AStarRouter(grid=grid)
    path = router.find_route(start=(0, 0), goal=(9, 9))

    if path is None:
        print("ERROR: A* could not find a route.")
        return
    print("SUCCESS: Route found.")

if __name__ == "__main__":
    main()