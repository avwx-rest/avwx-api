"""
Current report API endpoints
"""

# pylint: disable=missing-class-docstring,too-many-ancestors

import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import Report, Parse, MultiReport


## METAR


@app.route("/api/metar/<station>")
class MetarFetch(Report):
    report_type = "metar"
    handler = handle.MetarHandler
    _key_repl = {"base": "altitude"}
    _key_remv = ("top",)


@app.route("/api/parse/metar")
class MetarParse(Parse):
    report_type = "metar"
    handler = handle.MetarHandler
    _key_repl = {"base": "altitude"}
    _key_remv = ("top",)


@app.route("/api/multi/metar/<stations>")
class MetarMulti(MultiReport):
    report_type = "metar"
    handler = handle.MetarHandler
    example = "multi_metar"
    _key_repl = {"base": "altitude"}
    _key_remv = ("top",)


## TAF


@app.route("/api/taf/<station>")
class TafFetch(Report):
    report_type = "taf"
    handler = handle.TafHandler
    _key_repl = {"base": "altitude"}
    _key_remv = ("top",)


@app.route("/api/parse/taf")
class TafParse(Parse):
    report_type = "taf"
    handler = handle.TafHandler
    _key_repl = {"base": "altitude"}
    _key_remv = ("top",)


@app.route("/api/multi/taf/<stations>")
class TafMulti(MultiReport):
    report_type = "taf"
    handler = handle.TafHandler
    example = "multi_taf"
    _key_repl = {"base": "altitude"}
    _key_remv = ("top",)


## PIREP


@app.route("/api/pirep/<location>")
class PirepFetch(Report):
    report_type = "pirep"
    loc_param = "location"
    plan_types = ("pro", "enterprise")
    struct = structs.ReportLocation
    validator = validate.report_location
    handler = handle.PirepHandler
    _key_remv = ("direction",)


@app.route("/api/parse/pirep")
class PirepParse(Parse):
    report_type = "pirep"
    loc_param = "location"
    plan_types = ("pro", "enterprise")
    struct = structs.ReportLocation
    validator = validate.report_location
    handler = handle.PirepHandler
    _key_remv = ("direction",)
