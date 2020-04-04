"""
GFS forecast API endpoints
"""

import avwx_api.handle.gfs as handle
from avwx_api import app
from avwx_api.api.base import Report, Parse


@app.route("/api/gfs/mav/<station>")
class Mav(Report):
    report_type = "mav"
    plan_types = ("pro", "enterprise")
    handler = handle.MavHandler


@app.route("/api/parse/gfs/mav")
class MavParse(Parse):
    report_type = "mav"
    plan_types = ("pro", "enterprise")
    handler = handle.MavHandler


@app.route("/api/gfs/mex/<station>")
class Mex(Report):
    report_type = "mex"
    plan_types = ("pro", "enterprise")
    handler = handle.MexHandler


@app.route("/api/parse/gfs/mex")
class MexParse(Parse):
    report_type = "mex"
    plan_types = ("pro", "enterprise")
    handler = handle.MexHandler
