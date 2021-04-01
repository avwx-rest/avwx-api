"""
Methods to resolve flight paths in coordinates
"""

# stdlib
import json
import math
from pathlib import Path
from typing import Optional, Union

# module
from avwx import Station
from avwx.exceptions import BadStation
from avwx_api.structs import Coord

NAV_PATH = Path(__file__).parent.joinpath("data", "navaids.json")
NAVAIDS = json.load(NAV_PATH.open())

QCoord = Union[Coord, list[Coord]]


def _is_coord(coord: QCoord) -> bool:
    return coord and isinstance(coord[0], float)


def _is_list(coord: QCoord) -> bool:
    return coord and isinstance(coord[0], list)


def _distance(near: Coord, far: Coord) -> float:
    return math.sqrt((near[0] - far[0]) ** 2 + (near[1] - far[1]) ** 2)


def _closest(coord: QCoord, coords: list[Coord]) -> Coord:
    if _is_coord(coord):
        distances = [(_distance(coord, c), c) for c in coords]
    else:
        distances = [(_distance(c, _closest(c, coords)), c) for c in coord]
    distances.sort(key=lambda x: x[0])
    return distances[0][1]


def _best_coord(
    previous: Optional[QCoord],
    current: QCoord,
    up_next: Optional[Coord],
) -> Coord:
    """Determine the best coordinate based on surroundings
    At least one of these should be a list
    """
    if previous is None and up_next is None:
        if _is_list(current):
            raise Exception("Unable to determine best coordinate")
        return current
    # NOTE: add handling to determine best midpoint
    if up_next is None:
        up_next = previous
    if _is_list(up_next):
        return _closest(current, up_next)
    return _closest(up_next, current)


def to_coordinates(
    values: list[Union[Coord, str]], last_value: Optional[list[Coord]] = None
) -> list[Coord]:
    """Convert any known idents found in a flight path into coordinates"""
    if not values:
        return values
    coord = values[0]
    if isinstance(coord, str):
        try:
            station = Station.from_icao(coord)
            coord = (station.latitude, station.longitude)
        except BadStation:
            coords = NAVAIDS[coord]
            if len(coords) == 1:
                coord = coords[0]
            else:
                new_coords = to_coordinates(values[1:], coords)
                new_coord = new_coords[0] if new_coords else None
                coord = _best_coord(last_value, coords, new_coord)
                return [coord] + new_coords
    return [coord] + to_coordinates(values[1:], coord)
