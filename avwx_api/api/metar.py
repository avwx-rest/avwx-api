"""
Michael duPont - michael@mdupont.com
avwx_api.api.metar - METAR API endpoints
"""

from avwx_api import app
from avwx_api.api import Report, Parse, MultiReport

_key_repl = {"base": "altitude"}
_key_remv = ["top"]


@app.route("/api/metar/<station>")
class Metar(Report):

    report_type = "metar"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv


@app.route("/api/parse/metar")
class MetarParse(Parse):

    report_type = "metar"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv


@app.route("/api/multi/metar/<stations>")
class MetarMulti(MultiReport):

    report_type = "metar"
    example = "multi_metar"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv
