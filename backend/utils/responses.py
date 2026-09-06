def build_data_response(
    data: list
) -> dict:

    stale_count = sum(
        1
        for item in data
        if item.get(
            "is_stale",
            False
        )
    )

    return {
        "status": "success",
        "count": len(data),
        "data": data,
        "system": {
            "fresh": stale_count == 0,
            "stale_count": stale_count
        }
    }