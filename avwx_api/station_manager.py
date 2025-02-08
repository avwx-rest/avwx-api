"""
Manages station data sourcing
"""


import asyncio as aio
from dataclasses import asdict
from os import environ
from socket import gaierror
from typing import Optional

import httpcore
import httpx
import rollbar
from avwx import Station
from avwx.exceptions import SourceError
from avwx_api_core.token import Token
from avwx_api_core.util.handler import mongo_handler

from avwx_api import app
from avwx_api.structs import ParseConfig

TABLE = "awdata"
AVIOWIKI_URL = "https://api.aviowiki.com/airports/{}"
ENDPOINTS = [
    "",  # airport data
    "/runways/all",  # runways
]
API_KEY = environ.get("AVIOWIKI_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


TIMEOUT_ERRORS = (
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpcore.ReadTimeout,
    httpcore.WriteTimeout,
    httpcore.PoolTimeout,
)
CONNECTION_ERRORS = (gaierror, httpcore.ConnectError, httpx.ConnectError)
NETWORK_ERRORS = (
    httpcore.ReadError,
    httpcore.NetworkError,
    httpcore.RemoteProtocolError,
)


async def aid_for_code(code: str) -> Optional[str]:
    """Returns the AvioWiki ID for a station ident"""
    if app.mdb is None:
        return
    search = app.mdb.avio.aids.find_one({"_id": code})
    return data.get("aid") if (data := await mongo_handler(search)) else None


async def _call(
    client: httpx.AsyncClient, endpoint: str, aid: str, retries: int = 3
) -> Optional[dict]:
    url = (AVIOWIKI_URL + endpoint).format(aid)
    try:
        for _ in range(retries):
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                if "error" not in data:
                    return data
            # Skip retries if remote server error
            if resp.status_code >= 500:
                raise SourceError(f"aviowiki server returned {resp.status_code}")
        return None
    except TIMEOUT_ERRORS as timeout_error:
        raise TimeoutError("Timeout from aviowiki server") from timeout_error
    except CONNECTION_ERRORS as connect_error:
        raise ConnectionError("Unable to connect to aviowiki server") from connect_error
    except NETWORK_ERRORS as network_error:
        raise ConnectionError(
            "Unable to read data from aviowiki server"
        ) from network_error


async def fetch_from_aviowiki(code: str) -> Optional[dict]:
    """Fetch airport data from AvioWiki servers"""
    aid = await aid_for_code(code)
    async with httpx.AsyncClient(timeout=10) as client:
        coros = [_call(client, e, aid) for e in ENDPOINTS]
        data, runways = await aio.gather(*coros)
    if isinstance(data, dict):
        data["runways"] = runways
    return data


async def get_aviowiki_data(code: str) -> Optional[dict]:
    """Fetch aviowiki data"""
    if data := await app.cache.get(TABLE, code):
        del data["_id"]
        return data
    data = await fetch_from_aviowiki(code)
    if data:
        await app.cache.update(TABLE, code, data)
    return data


def _use_aviowiki_data(config: Optional[ParseConfig], token: Optional[Token]) -> bool:
    if not API_KEY or app.mdb is None:
        return False
    if config and config.aviowiki_data:
        return True
    return bool(token and ParseConfig.use_aviowiki_data(token))


async def station_data_for(
    station: Station,
    config: Optional[ParseConfig] = None,
    token: Optional[Token] = None,
) -> Optional[dict]:
    """Returns airport data dict from station or another source"""
    if _use_aviowiki_data(config, token):
        data = await get_aviowiki_data(station.storage_code)
        if data is None:
            text = f"{station.icao}-{station.gps}-{station.local}"
            rollbar.report_message(text, "info")
        return data
    return asdict(station)
