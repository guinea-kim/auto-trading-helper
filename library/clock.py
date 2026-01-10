from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

class Clock:
    def now(self, tz: Optional[ZoneInfo] = None) -> datetime:
        """Returns the current time, optionally in a specific timezone."""
        return datetime.now(tz)

class MockClock(Clock):
    def __init__(self, fixed_time: datetime):
        self._time = fixed_time
        
    def now(self, tz: Optional[ZoneInfo] = None) -> datetime:
        # If tz is requested, convert the internal mocked time to that tz
        if tz:
            # simple trick: if self._time is naive, assume it's local system time (or just attach tz)
            # but usually in tests we will initialize MockClock with a timezone-aware datetime
            if self._time.tzinfo is None:
                 return self._time.replace(tzinfo=tz) 
            return self._time.astimezone(tz)
        return self._time
        
    def set_time(self, new_time: datetime):
        self._time = new_time
        
    def advance_seconds(self, seconds: int):
        self._time += timedelta(seconds=seconds)
