"""Custom Metar class with provider check cooldown"""

from datetime import UTC, datetime, timedelta

from avwx import Metar as _Metar

# Time to check a station again if the default provider fails
SECOND_CHANCE_TIMES: dict[str, datetime] = {}


class Metar(_Metar):
    """avwx.Metar class with custom provider check"""

    @property
    def _should_check_default(self) -> bool:
        """Add a cooldown period to default provider check."""
        if not (self.code and super()._should_check_default):
            return False
        try:
            last_check = SECOND_CHANCE_TIMES[self.code]
        except KeyError:
            return True
        now = datetime.now(UTC)
        should_check = now > last_check
        if should_check:
            SECOND_CHANCE_TIMES[self.code] = now + timedelta(minutes=5)
        return should_check
