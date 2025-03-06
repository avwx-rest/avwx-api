"""Non-API views."""

# pylint: disable=W0702

from quart import Response, redirect
from werkzeug.wrappers import Response as WerkzeugResponse

from avwx_api import app

# Static Web Pages


@app.route("/")
@app.route("/home")
def home() -> WerkzeugResponse:
    """Returns static home page"""
    return redirect("https://info.avwx.rest")


@app.route("/ping")
def ping() -> Response:
    """Send empty 200 ping response"""
    return Response(None, 200)


# API Routing Errors


@app.route("/api")
async def no_report() -> Response:
    """Returns no report msg"""
    return Response('{"error": "No report type given"}', 400, mimetype="application/json")


@app.route("/api/metar")
@app.route("/api/taf")
async def no_station() -> Response:
    """Returns no station msg"""
    return Response('{"error": "No station given"}', 400, mimetype="application/json")
