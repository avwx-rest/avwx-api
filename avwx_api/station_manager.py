"""Manages station data sourcing."""

import asyncio as aio
from dataclasses import asdict
from os import environ
from socket import gaierror

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


async def aid_for_code(code: str) -> str | None:
    """Returns the AvioWiki ID for a station ident"""
    if app.mdb is None:
        return None
    search = app.mdb.avio.aids.find_one({"_id": code})
    return data.get("aid") if (data := await mongo_handler(search)) else None


async def _call(client: httpx.AsyncClient, endpoint: str, aid: str, retries: int = 3) -> dict | None:
    url = (AVIOWIKI_URL + endpoint).format(aid)
    try:
        for _ in range(retries):
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data: dict = resp.json()
                if "error" not in data:
                    return data
            # Skip retries if remote server error
            if resp.status_code >= 500:
                msg = f"aviowiki server returned {resp.status_code}"
                raise SourceError(msg)
    except TIMEOUT_ERRORS as timeout_error:
        msg = "Timeout from aviowiki server"
        raise TimeoutError(msg) from timeout_error
    except CONNECTION_ERRORS as connect_error:
        msg = "Unable to connect to aviowiki server"
        raise ConnectionError(msg) from connect_error
    except NETWORK_ERRORS as network_error:
        msg = "Unable to read data from aviowiki server"
        raise ConnectionError(msg) from network_error
    return None


async def fetch_from_aviowiki(code: str) -> dict | None:
    """Fetch airport data from AvioWiki servers"""
    aid = await aid_for_code(code)
    if aid is None:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        coros = [_call(client, e, aid) for e in ENDPOINTS]
        data, runways = await aio.gather(*coros)
    if isinstance(data, dict):
        data["runways"] = runways
    return data


async def get_aviowiki_data(code: str) -> dict | None:
    """Fetch aviowiki data"""
    if data := await app.cache.get(TABLE, code):
        del data["_id"]
        return data
    data = await fetch_from_aviowiki(code)
    if data:
        await app.cache.update(TABLE, code, data)
    return data


def _use_aviowiki_data(config: ParseConfig | None, token: Token | None) -> bool:
    if not API_KEY or app.mdb is None:
        return False
    if config and config.aviowiki_data:
        return True
    return bool(token and ParseConfig.use_aviowiki_data(token))


async def station_data_for(
    station: Station,
    config: ParseConfig | None = None,
    token: Token | None = None,
) -> dict | None:
    """Returns airport data dict from station or another source"""
    if _use_aviowiki_data(config, token):
        data = await get_aviowiki_data(station.storage_code)
        if data is None:
            text = f"{station.icao}-{station.gps}-{station.local}"
            rollbar.report_message(text, "info")
        return data
    return asdict(station)
