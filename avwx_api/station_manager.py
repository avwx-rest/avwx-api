"""
Manages station data sourcing
"""

from dataclasses import asdict
from typing import Optional

from avwx import Station
from avwx_api_core.token import Token
from avwx_api import app
from avwx_api.structs import ParseConfig


async def get_aviowiki_data(icao: str) -> dict:
    """Fetch aviowiki data"""
    return {"icao": icao, "aviowiki": True}


def _use_aviowiki_data(config: Optional[ParseConfig], token: Optional[Token]) -> bool:
    if config and config.aviowiki_data:
        return True
    if token and ParseConfig.use_aviowiki_data(token):
        return True
    return False


async def station_data_for(
    station: Station,
    config: Optional[ParseConfig] = None,
    token: Optional[Token] = None,
) -> dict:
    """Returns airport data dict from station or another source"""
    if _use_aviowiki_data(config, token):
        return await get_aviowiki_data(station.icao)
    return asdict(station)
