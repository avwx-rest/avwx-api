"""
Tests METAR serving capabilities of the API
"""

# library
import pytest
# module
from avwx_api import app

CLIENT = app.test_client()
URL = '/api/{}/{}'

REPORT_TYPES = ('metar', 'taf',)

@pytest.mark.asyncio
async def _fetch(rtype: str, target: str = 'KJFK', options: str = '') -> 'Response':
    resp = await CLIENT.get(URL.format(rtype, target))
    assert resp.status_code == 200
    return resp

@pytest.mark.asyncio
async def test_fetch():
    """
    Tests basic report fetch
    """
    for rtype in REPORT_TYPES:
        resp = await _fetch(rtype)
        data = await resp.json
        print(data)
        assert 'Station' in data
        assert data['Station'] == 'KJFK'

@pytest.mark.asyncio
async def test_coords():
    """
    Tests report coord lookup

    Make sure GN_USER is set in the env or the test will fail
    """
    for rtype in REPORT_TYPES:
        resp = await _fetch(rtype, target='28.4293,-81.3089')
        data = await resp.json
        print(data)
        assert 'Station' in data
        assert data['Station'] == 'KMCO'

@pytest.mark.asyncio
async def test_parse():
    """
    Tests report parsing endpoint
    """
    for rtype, report in (
        ('metar', 'KJFK 192351Z 11006KT 10SM BKN055 BKN080 21/19 A3005'),
        ('taf', 'PHKO 181735Z 1818/1918 VRB03KT P6SM FEW035'),
    ):
        resp = await CLIENT.post(URL.format(rtype, 'parse'), data=report)
        assert resp.status_code == 200
        data = await resp.json
        print(data)
        assert 'station' in data
        assert data['station'] == report[:4]
        assert data['raw'] == report
