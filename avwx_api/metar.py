"""Custom Metar class with provider check cooldown"""

from datetime import UTC, datetime, timedelta

from avwx import Metar as _Metar

from avwx_api import app

# Time to check a station again if the default provider fails
SECOND_CHANCE_TIMES: dict[str, datetime] = {}
DEFAULT_COOLDOWN = timedelta(minutes=5)


class Metar(_Metar):
    """avwx.Metar class with custom provider check"""

    @property
    def _should_check_default(self) -> bool:
        """Add a cooldown period to default provider check."""
        if not (self.code and super()._should_check_default) or self.code not in app.noaa_stations:
            return False
        now = datetime.now(UTC)
        try:
            last_check = SECOND_CHANCE_TIMES[self.code]
        except KeyError:
            should_check = True
        else:
            should_check = now > last_check
        if should_check:
            SECOND_CHANCE_TIMES[self.code] = now + DEFAULT_COOLDOWN
        return should_check
