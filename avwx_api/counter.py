"""
Michael duPont - michael@mdupont.com
avwx_api.counter - Usage counting for analytics
"""

# stdlib
from datetime import datetime

# library
from avwx import Station


async def increment_station(icao: str, request_type: str):
    """
    Increments a station counter
    """
    # from avwx_api import mdb

    # if mdb is None:
    #     return
    # date = datetime.utcnow().strftime(r"%Y-%m-%d")
    # await mdb.station_counter.update_one(
    #     {"_id": icao}, {"$inc": {f"{request_type}.{date}": 1}}, upsert=True
    # )
    return


async def from_params(params: "structs.Params", report_type: str):
    """
    Counts station based on param values
    """
    if hasattr(params, "station"):
        icao = params.station.icao
    elif hasattr(params, "location") and isinstance(params.location, Station):
        icao = params.location.icao
    else:
        return
    await increment_station(icao, report_type)
    return
