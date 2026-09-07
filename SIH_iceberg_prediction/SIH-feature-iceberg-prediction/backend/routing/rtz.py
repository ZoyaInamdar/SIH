from datetime import datetime, timezone
from xml.etree.ElementTree import (
    Element,
    SubElement,
    tostring
)


def route_to_rtz(
    route_id: str,
    points: list,
    route_name: str = "Antarctic Safe Route"
) -> str:

    root = Element(
        "route",
        {
            "version": "1.1"
        }
    )

    route_info = SubElement(
        root,
        "routeInfo"
    )

    SubElement(
        route_info,
        "routeId"
    ).text = route_id

    SubElement(
        route_info,
        "routeName"
    ).text = route_name

    SubElement(
        route_info,
        "creationDate"
    ).text = datetime.now(
        timezone.utc
    ).isoformat()

    waypoints = SubElement(
        root,
        "waypoints"
    )

    for index, point in enumerate(points, start=1):

        waypoint = SubElement(
            waypoints,
            "waypoint",
            {
                "id": str(index)
            }
        )

        position = SubElement(
            waypoint,
            "position"
        )

        SubElement(
            position,
            "lat"
        ).text = str(
            point["latitude"]
        )

        SubElement(
            position,
            "lon"
        ).text = str(
            point["longitude"]
        )

    xml_bytes = tostring(
        root,
        encoding="utf-8",
        xml_declaration=True
    )

    return xml_bytes.decode("utf-8")