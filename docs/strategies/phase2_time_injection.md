# Phase 2 Strategy: Time Injection (Clock Pattern)

## 1. Goal
To mitigate the non-determinism caused by `datetime.now()`, enabling the testing of time-sensitive logic (e.g., periodic buying on Mondays, market close logic, end-of-month rebalancing) without waiting for the actual time.

## 2. Problem Statement
Currently, `trader.py` and its dependencies call `datetime.now()` directly in multiple places:
- **`trader.py`**: `check_periodic_buy_date`, `update_result`, Alert timestamps.
- **`schwab_manager.py`**: `get_market_hours` (Critical: uses `ZoneInfo("America/Los_Angeles")`).

This makes it impossible to automate tests for:
- "What happens during a leap year?"
- "What happens on the last day of the month?"
- "What happens if the script runs at 23:59:59?"
- "Logic that depends on Market Open/Close status" (since Manager checks real time).

## 3. Implementation Strategy

### 3.1 The `Clock` Interface (Timezone Aware)
Create a robust abstraction in `library/clock.py` that supports timezones, essential for our dual-market (KR/US) system.

```python
from datetime import datetime
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
            if self._time.tzinfo is None:
                 pass 
            return self._time.astimezone(tz)
        return self._time
        
    def set_time(self, new_time: datetime):
        self._time = new_time
        
    def advance_seconds(self, seconds: int):
        from datetime import timedelta
        self._time += timedelta(seconds=seconds)
```

### 3.2 Code Refactoring (Deep Injection)

The `clock` must be passed down from `TradingSystem` -> `MarketStrategy` -> `Manager`.

**1. Manager Refactoring:**
`SchwabManager` needs the clock to check market hours correctly during tests.

```python
# library/schwab_manager.py
class SchwabManager:
    def __init__(self, user_id: str, clock: Clock = None):
        self.clock = clock or Clock()
        # ...

    def get_market_hours(self):
        # REPLACE: now = datetime.now(ZoneInfo("America/Los_Angeles"))
        now = self.clock.now(ZoneInfo("America/Los_Angeles"))
        # ...
```

**2. Strategy Refactoring:**
Strategies act as factories for Managers.

```python
# strategies/schwab_strategy.py
class SchwabMarketStrategy(MarketStrategy):
    def __init__(self, clock=None):
        self.clock = clock or Clock()
        self.managers = {}

    def get_manager(self, user_id):
        if user_id not in self.managers:
            self.managers[user_id] = SchwabManager(user_id, clock=self.clock)
        return self.managers[user_id]
```

**3. TradingSystem Refactoring:**
The entry point.

```python
# trader.py
class TradingSystem:
    def __init__(self, market_strategy, clock=None):
        self.clock = clock or Clock()
        if hasattr(market_strategy, 'clock'): 
             market_strategy.clock = self.clock
        
        self.market_strategy = market_strategy
        # ...
        
    def check_periodic_buy_date(self, rule: dict) -> bool:
        # REPLACE: today = datetime.now()
        today = self.clock.now() 
        # ...
```

### 3.3 Areas to Refactor
Scan for all `datetime.now()` usages using `grep` and replace them with `self.clock.now()`.

- **Critical:** periodic buy logic in `trader.py`.
- **Critical:** `get_market_hours` in `schwab_manager.py`.
- **Reporting:** `update_result` date string generation.
- **Logging:** Timestamp generation (optional).

## 4. Verification Plan

### 4.1 Unit Tests (New Capability)
We can now write deterministic tests for both logic and market interaction.

#### 4.1.1 Market Boundary Tests (The "Ghost Day" Prevention)
Ensure precise handling of market open/close times.

| Case ID | Scenario | Mock Time (US/Eastern) | Expected Result | Note |
|:---:|:---|:---|:---:|:---|
| **MKT-01** | Pre-Market (1 sec before open) | 09:29:59 | `False` | Orders should NOT execute |
| **MKT-02** | Market Open (Exact) | 09:30:00 | `True` | Orders ACCEPTED |
| **MKT-03** | Intraday | 12:00:00 | `True` | Normal Operation |
| **MKT-04** | Market Close (Exact) | 16:00:00 | `False` | No new orders |
| **MKT-05** | After Hours | 16:00:01 | `False` | No new orders |
| **MKT-06** | Weekend (Saturday) | Sat 10:00:00 | `False` | User might run script manually |

#### 4.1.2 Calendar & Periodic Logic
Ensure `check_periodic_buy_date` works across weird calendar dates.

| Case ID | Scenario | Mock Date | Rule Logic | Expected |
|:---:|:---|:---|:---|:---:|
| **CAL-01** | Weekly Buy on Monday | 2024-01-01 (Mon) | `weekly` (0) | `True` |
| **CAL-02** | Weekly Buy on Monday (Fail) | 2024-01-02 (Tue) | `weekly` (0) | `False` |
| **CAL-03** | Monthly Buy (1st) | 2024-02-01 | `monthly` (1) | `True` |
| **CAL-04** | Monthly Buy (31st) - Feb | 2024-02-29 | `monthly` (31) | `False` |
| **CAL-05** | Leap Year Day (Feb 29) | 2024-02-29 | `monthly` (29) | `True` |
| **CAL-06** | End of Year Transition | 2023-12-31 | `monthly` (31) | `True` |

#### 4.1.3 Timezone & DST Transitions
Verify `ZoneInfo` handling during US Daylight Saving Time (DST) shifts.

*Note: US Market times shift relative to UTC, but stay fixed at 09:30 ET.*

| Case ID | Scenario | Mock UTC Time | Mock ET Time | Expected |
|:---:|:---|:---|:---|:---:|
| **DST-01** | Winter (Standard Time) | 14:30 UTC | 09:30 EST | `True` |
| **DST-02** | Summer (Daylight Time) | 13:30 UTC | 09:30 EDT | `True` |
| **DST-03** | Transition Day (Spring Forward) | *Variable* | 09:30 Local | `True` |

### 4.2 Code Example for Edge Cases

```python
def test_dst_market_open():
    """Verify market considers 9:30 AM local time, regardless of UTC shift"""
    
    # 1. Winter (Nov 2023) - UTC offset -5
    winter_open = datetime(2023, 11, 15, 9, 30, tzinfo=ZoneInfo("America/New_York"))
    clock = MockClock(winter_open)
    manager = SchwabManager("user", clock=clock)
    assert manager.get_market_hours() is True
    
    # 2. Summer (July 2024) - UTC offset -4
    summer_open = datetime(2024, 7, 15, 9, 30, tzinfo=ZoneInfo("America/New_York"))
    clock.set_time(summer_open)
    assert manager.get_market_hours() is True
```

## 5. Migration Steps
1. Create `library/clock.py` with `ZoneInfo` support.
2. Refactor `SchwabManager` and `KoreaManager` to accept `clock`.
3. Refactor `MarketStrategy` subclasses to accept and pass `clock`.
4. Refactor `TradingSystem` to accept and use `clock`.
5. Systematically replace `datetime.now()` in `trader.py` and `managers`.
6. Add `tests/test_clock_logic.py` implementing the catalog above.

## 6. Actual Implementation Details
- **`library/clock.py`**: Implemented `Clock` and `MockClock` with proper timezone support.
- **Dependency Injection**: Refactored `SchwabManager`, `KoreaManager`, `SchwabMarketStrategy`, `KoreaMarketStrategy`, and `TradingSystem` to accept a `clock` instance.
- **`trader.py`**: Replaced all critical `datetime.now()` calls with `self.clock.now()`.
- **Verification**: Added `tests/test_clock.py` to verify time mocking capabilities.

