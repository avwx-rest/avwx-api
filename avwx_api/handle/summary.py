"""Handle airport summary requests."""

import asyncio as aio
from contextlib import suppress
from http import HTTPStatus

import avwx

from avwx_api.handle.base import ERRORS, ReportHandler
from avwx_api.station_manager import station_data_for
from avwx_api.structs import DataStatus, ParseConfig

_METAR_KEYS = ("time", "flight_rules", "wx_codes", "visibility")
_TAF_KEYS = ("start_time", "end_time", "flight_rules")


def clip_timestamps(data: dict) -> dict:
    """Replace timestamps with just datetime"""
    for key, value in data.items():
        with suppress(KeyError, TypeError):
            data[key] = value["dt"]
    return data


def is_ceiling(cloud: dict) -> bool:
    """Returns True is the cloud dict is a valid ceiling"""
    return cloud["base"] and cloud["type"] in {"OVC", "BKN", "VV"}


def get_ceiling(clouds: list[dict]) -> dict | None:
    """Get the cloud ceiling. Identical to parsing.core but with a dict"""
    return next((cloud for cloud in clouds if is_ceiling(cloud)), None)


def metar_summary(metar: dict | None) -> dict:
    """Extract summary fields from a METAR dict"""
    metar = metar or {}
    data = {key: metar.get(key) for key in _METAR_KEYS}
    data["ceiling"] = get_ceiling(metar.get("clouds", []))
    return clip_timestamps(data)


def taf_period(period: dict) -> dict:
    """Extract summary fields from a TAF time period dict"""
    return clip_timestamps({key: period.get(key) for key in _TAF_KEYS})


def taf_summary(taf: dict | None) -> dict:
    """Extract summary fields from a TAF dict"""
    taf = taf or {}
    data = {
        "time": taf.get("time"),
        "forecast": [taf_period(period) for period in taf.get("forecast", [])],
    }
    return clip_timestamps(data)


def make_summary(metar: dict | None, taf: dict | None) -> dict:
    """Generate a summary response from desired report types"""
    return {
        "metar": metar_summary(metar),
        "taf": taf_summary(taf),
    }


class SummaryHandler(ReportHandler):
    report_type = "summary"

    async def fetch_report(
        self,
        station: avwx.Station,
        config: ParseConfig,
    ) -> DataStatus:
        """Returns summary data for aiven station and options
        Also returns the appropriate HTTP response code

        Cache report data is available for use, but summaries themselves are not cached
        """
        if not station.sends_reports:
            return {"error": ERRORS[6].format(station.storage_code)}, HTTPStatus.NO_CONTENT
        # Create summary from METAR and TAF reports
        (metar, *_), (taf, *_) = await aio.gather(
            self._station_cache_or_fetch(station, report_type="metar", parser=avwx.Metar),
            self._station_cache_or_fetch(station, report_type="taf", parser=avwx.Taf),
        )
        data = make_summary(metar.get("data"), taf.get("data"))
        # Create response
        resp = {"meta": self.make_meta()}
        if cache_time := metar.get("timestamp"):
            resp["meta"]["cache-timestamp"] = cache_time
        # Format the return data
        resp |= self._format_report(data, config)
        # Add station info if requested
        if station and config.station:
            resp["info"] = await station_data_for(station, config) or {}
        return resp, HTTPStatus.OK
