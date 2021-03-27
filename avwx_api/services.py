"""
Custom report services
"""

# pylint: disable=too-few-public-methods

# library
from xmltodict import parse as parsexml

# module
from avwx.exceptions import InvalidRequest
from avwx.service.base import CallsHTTP
from avwx_api.structs import Coord


class FlightRouter(CallsHTTP):
    """Requests routing reports from NOAA ADDS"""

    url = "https://aviationweather.gov/adds/dataserver_current/httpparam"

    _valid_types = ("metar", "taf", "aircraftreport")
    _type_map = {"airep": "aircraftreport"}
    _targets = {"metar": "METAR", "taf": "TAF", "aircraftreport": "AircraftReport"}

    def _extract(self, report_type: str, text: str) -> list[str]:
        """Extracts the raw_report element from XML response"""
        resp = parsexml(text)
        try:
            data = resp["response"]["data"]
            if data["@num_results"] == "0":
                return ""
            reports = data[self._targets[report_type]]
        except KeyError as key_error:
            raise InvalidRequest(
                "Could not find report path in response"
            ) from key_error
        return [r["raw_text"] for r in reports]

    async def fetch(
        self, report_type: str, distance: float, route: list[Coord]
    ) -> list[str]:
        """Fetch reports from the service along a coordinate route"""
        report_type = self._type_map.get(report_type, report_type)
        if report_type not in self._valid_types:
            raise InvalidRequest(f"{report_type} is not a valid router report type")
        flight_path = ";".join(f"{lon},{lat}" for lat, lon in route)
        params = {
            "dataSource": report_type + "s",
            "requestType": "retrieve",
            "format": "xml",
            "flightPath": f"{distance};{flight_path}",
        }
        text = await self._call(self.url, params=params)
        return self._extract(report_type, text)
