"""
Michael duPont - michael@mdupont.com
avwx_api.api.pirep - PIREP API endpoints
"""

from avwx_api import app
from avwx_api.api import Report, Parse

_key_remv = ["direction"]


@app.route("/api/pirep/<station>")
class Pirep(Report):
    report_type = "pirep"
    # example = 'pirep'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_remv = _key_remv


@app.route("/api/parse/pirep")
class PirepParse(Parse):
    report_type = "pirep"
    # example = 'pirep'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_remv = _key_remv
