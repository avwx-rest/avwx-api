"""Tests METAR serving capabilities of the API."""

import pytest
from quart import Response

from avwx_api import app

CLIENT = app.test_client()
URL = "/api/{}/{}"

REPORT_TYPES = ("metar", "taf")


async def _fetch(report_type: str, target: str = "KJFK") -> Response:
    resp = await CLIENT.get(URL.format(report_type, target))
    assert resp.status_code == 200
    return resp


@pytest.mark.asyncio
@pytest.mark.parametrize("report_type", REPORT_TYPES)
async def test_fetch(report_type: str):
    """Tests basic report fetch"""
    resp = await _fetch(report_type)
    data = await resp.json
    print(data)
    assert "station" in data
    assert data["station"] == "KJFK"


@pytest.mark.asyncio
@pytest.mark.parametrize("report_type", REPORT_TYPES)
async def test_coords(report_type: str):
    """Tests report coord lookup

    Make sure GN_USER is set in the env or the test will fail
    """
    resp = await _fetch(report_type, target="28.4293,-81.3089")
    data = await resp.json
    print(data)
    assert "station" in data
    assert data["station"] == "KMCO"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("report_type", "report"),
    zip(
        REPORT_TYPES,
        (
            "KJFK 192351Z 11006KT 10SM BKN055 BKN080 21/19 A3005",
            "PHKO 181735Z 1818/1918 VRB03KT P6SM FEW035",
        ),
        strict=False,
    ),
)
async def test_parse(report_type: str, report: str):
    """Tests report parsing endpoint"""
    resp = await CLIENT.post(URL.format("parse", report_type), data=report)
    assert resp.status_code == 200
    data = await resp.json
    print(data)
    assert "station" in data
    assert data["station"] == report[:4]
    assert data["raw"] == report
