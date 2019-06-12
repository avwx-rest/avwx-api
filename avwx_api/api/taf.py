"""
Michael duPont - michael@mdupont.com
avwx_api.api.taf - TAF API endpoints
"""

from avwx_api import app
from avwx_api.api import Report, LegacyReport, Parse, MultiReport

_key_repl = {"base": "altitude"}
_key_remv = ["top"]


@app.route("/api/taf/<station>")
class Taf(Report):

    report_type = "taf"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv


@app.route("/api/preview/taf/<station>")
class TafCopy(Taf):

    note = (
        "The new syntax can now be found at /api/taf. "
        "The preview endpoint will be available until July 1, 2019"
    )


@app.route("/api/legacy/taf/<station>")
class TafLegacy(LegacyReport):

    report_type = "taf"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_remv = _key_remv


@app.route("/api/parse/taf")
class TafParse(Parse):

    report_type = "taf"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv


@app.route("/api/multi/taf/<stations>")
class TafMulti(MultiReport):

    report_type = "taf"
    example = "multi_taf"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv
