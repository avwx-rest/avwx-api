"""Forecast API endpoints."""

import avwx_api.handle.forecast as handle
from avwx_api import app
from avwx_api.api.base import Parse, Report

PLANS = ("pro", "enterprise")

GFS_HANDLERS = {"mav": handle.MavHandler(), "mex": handle.MexHandler()}
NBM_HANDLERS = {
    "nbh": handle.NbhHandler(),
    "nbs": handle.NbsHandler(),
    "nbe": handle.NbeHandler(),
    "nbx": handle.NbxHandler(),
}


@app.route("/api/gfs/<report_type>/<station>")
class GFS(Report):
    plan_types = PLANS
    handlers = GFS_HANDLERS


@app.route("/api/parse/gfs/<report_type>")
class GFSParse(Parse):
    plan_types = PLANS
    handlers = GFS_HANDLERS


@app.route("/api/nbm/<report_type>/<station>")
class NBM(Report):
    plan_types = PLANS
    handlers = NBM_HANDLERS


@app.route("/api/parse/nbm/<report_type>")
class NBMParse(Parse):
    plan_types = PLANS
    handlers = NBM_HANDLERS
