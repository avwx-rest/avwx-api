"""
Michael duPont - michael@mdupont.com
avwx_api.views - Routes and views for the Quart application
"""

# pylint: disable=W0702


from quart import Response, jsonify, redirect

from avwx_api import app

# Static Web Pages


@app.route("/")
@app.route("/home")
def home() -> Response:
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
    return jsonify({"error": "No report type given"}), 400


@app.route("/api/metar")
@app.route("/api/taf")
async def no_station() -> Response:
    """Returns no station msg"""
    return jsonify({"error": "No station given"}), 400
