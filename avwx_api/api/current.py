"""
Current report API endpoints
"""

# pylint: disable=missing-class-docstring,too-many-ancestors


from contextlib import suppress
from typing import Optional

from avwx.structs import Coord
from avwx_api_core.token import Token
from quart import Response
from quart_openapi.cors import crossdomain
from shapely.geometry import Point, Polygon

import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import (
    HEADERS,
    Base,
    MultiReport,
    Parse,
    Report,
    parse_params,
    token_check,
)
from avwx_api.handle.notam import NotamHandler
from avwx_api.handle.summary import SummaryHandler

MT_REPL = {"base": "altitude"}
MT_REMV = ("top",)


## METAR


@app.route("/api/metar/<station>")
class MetarFetch(Report):
    report_type = "metar"
    handler = handle.MetarHandler
    key_repl = MT_REPL
    key_remv = MT_REMV


@app.route("/api/parse/metar")
class MetarParse(Parse):
    report_type = "metar"
    handler = handle.MetarHandler
    key_repl = MT_REPL
    key_remv = MT_REMV


@app.route("/api/multi/metar/<stations>")
class MetarMulti(MultiReport):
    report_type = "metar"
    handler = handle.MetarHandler
    example = "multi_metar"
    key_repl = MT_REPL
    key_remv = MT_REMV


## TAF


@app.route("/api/taf/<station>")
class TafFetch(Report):
    report_type = "taf"
    handler = handle.TafHandler
    key_repl = MT_REPL
    key_remv = MT_REMV


@app.route("/api/parse/taf")
class TafParse(Parse):
    report_type = "taf"
    handler = handle.TafHandler
    key_repl = MT_REPL
    key_remv = MT_REMV


@app.route("/api/multi/taf/<stations>")
class TafMulti(MultiReport):
    report_type = "taf"
    handler = handle.TafHandler
    example = "multi_taf"
    key_repl = MT_REPL
    key_remv = MT_REMV


## PIREP


@app.route("/api/pirep/<location>")
class PirepFetch(Report):
    report_type = "pirep"
    loc_param = "location"
    plan_types = ("pro", "enterprise")
    struct = structs.ReportLocation
    validator = validate.report_location
    handler = handle.PirepHandler
    key_remv = ("direction",)


@app.route("/api/parse/pirep")
class PirepParse(Parse):
    report_type = "pirep"
    plan_types = ("pro", "enterprise")
    handler = handle.PirepHandler
    key_remv = ("direction",)


## AIRMET SIGMET


@app.route("/api/airsigmet")
class AirSigFetch(Report):
    report_type = "airsigmet"
    plan_types = ("pro", "enterprise")
    struct = structs.CachedReport
    validator = validate.global_report
    handler = handle.AirSigHandler


@app.route("/api/parse/airsigmet")
class AirSigParse(Parse):
    report_type = "airsigmet"
    plan_types = ("pro", "enterprise")
    struct = structs.ReportGiven
    validator = validate.report_given
    handler = handle.AirSigHandler


@app.route("/api/airsigmet/<location>")
class AirSigContains(Base):
    """Returns AirSigmets that contains a location"""

    validator = validate.airsig_contains
    struct = structs.AirSigContains
    loc_param = "location"
    example = "airsig_contains"
    plan_types = ("pro", "enterprise")

    @staticmethod
    def _filter_contains(point: Point, reports: list[dict]) -> list[dict]:
        """Filters report list that contain a coordinate point"""
        ret = []
        for report in reports:
            for period in ("observation", "forecast"):
                with suppress(TypeError):
                    coords = report[period]["coords"]
                    if len(coords) < 3:
                        continue
                    poly = Polygon((c["lat"], c["lon"]) for c in coords)
                    if poly.contains(point):
                        ret.append(report)
                        break
        return ret

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
        """Returns reports along a flight path"""
        config = structs.ParseConfig.from_params(params, token)
        data, code = await handle.AirSigHandler().fetch_reports(config)
        if code != 200:
            return self.make_response(data, params, code)
        if isinstance(params.location, Coord):
            coord = params.location
        else:
            coord = params.location.coord
        resp = {
            "meta": handle.MetarHandler().make_meta(),
            "point": coord,
            "reports": self._filter_contains(coord.point, data["reports"]),
        }
        return self.make_response(resp, params)


## NOTAM


@app.route("/api/notam/<location>")
class NotamFetch(Report):
    report_type = "notam"
    loc_param = "location"
    plan_types = ("enterprise",)
    struct = structs.NotamLocation
    validator = validate.notam_location
    handler = NotamHandler
    key_remv = ("remarks",)


@app.route("/api/parse/notam")
class NotamParse(Parse):
    report_type = "notam"
    loc_param = "location"
    plan_types = ("enterprise",)
    handler = NotamHandler
    key_remv = ("remarks",)


## Summary


@app.route("/api/summary/<station>")
class StationSummary(Report):
    report_type = "summary"
    handler = SummaryHandler
    key_repl = MT_REPL
    key_remv = MT_REMV


@app.route("/api/multi/summary/<stations>")
class StationSummaryMulti(MultiReport):
    report_type = "summary"
    plan_types = ("pro", "enterprise")
    handler = SummaryHandler
    example = "multi_summary"
    key_repl = MT_REPL
    key_remv = MT_REMV
