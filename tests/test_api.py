"""
Tests shared and high-level attributes of the API
"""

import pytest
from avwx_api import app

REPORT_TYPES = ("metar", "taf", "pirep")


@pytest.mark.asyncio
async def test_cors():
    """
    Tests that CORS headers are available at the primary endpoints
    """
    client = app.test_client()
    for url in [f"/api/{report_type}/KJFK" for report_type in REPORT_TYPES]:
        resp = await client.get(url)
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
    for report_type, report in (
        ("metar", "KJFK 192351Z 11006KT 10SM BKN055 BKN080 21/19 A3005"),
        ("taf", "PHKO 181735Z 1818/1918 VRB03KT P6SM FEW035"),
    ):
        resp = await client.post(f"/api/parse/{report_type}", data=report)
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
