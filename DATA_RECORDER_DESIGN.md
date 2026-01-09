# Market Data Recorder Design Proposed

To support **Deterministic Replay** for migration verification, we propose a system that records all external data collected by the Trader into a file.

---

## 1. Recording Strategy (Recording Point)

Capture all **External Input (Side Effects)** that `trader.py` depends on. To achieve this, we will wrap or proxy key methods of `SchwabManager` (and `KoreaManager`).

**Target Methods (to be recorded):**
1.  `get_last_price(symbol)`: **[High Frequency]** Core input for the main loop.
2.  `get_positions(hash_value)`: Checked at market open/close.
3.  `get_positions_result(hash_value)`: For return calculation.
4.  `get_hashs()`: Determine account list.
5.  `get_cash(hash_value)`: Check available cash for buying.
6.  `get_account_result(hash_value)`: Check total asset value (for return calculation).
7.  `get_market_hours()`: Check market operating hours (True/False).
8.  `sell_etf_for_cash(...)`: Cash securing logic (Record result only to substitute internal logic replay).
9.  `place_*_order(...)`: **[Output]** Order result (Including `order.is_success`).

_※ `datetime.now()` used in `check_periodic_buy_date` is difficult to capture with the Recorder. During Replay, we should use tools like `freezegun` to freeze time or Mock time according to the Log's timestamp._

---

### 1.5. Metadata Header (Start of File)
Records execution environment info at the start of the file to check consistency during Replay.
**Operating Hours Note**: The system's start and end depend entirely on **Crontab** settings. The recorder opens when the process starts (`__init__`) and closes when the process ends (`atexit`).
**File Location**: Stored in the `/records` directory. Must be added to `.gitignore` to avoid committing to Git.
**Filename Convention**: `records/market_data_{market}_{YYYYMMDD}.jsonl`

### 1.5.1. Folder Structure Example
```text
auto-trading-helper/
├── library/
├── strategies/
├── trader.py
├── ...
└── records/                     <-- New Directory (Git Ignored)
    ├── market_data_schwab_20240109.jsonl
    ├── market_data_schwab_20240110.jsonl
    ├── market_data_korea_20240109.jsonl
    └── market_data_korea_20240110.jsonl
```

```json
{
  "meta": {
    "market": "schwab",
    "filename": "market_data_schwab_20240109.jsonl",
    "start_time": "2024-01-08T09:30:00",
    "trigger": "crontab", 
    "git_hash": "a1b2c3d...",
    "trader_version": "v1.0"
  }
}
```

---

## 2. Storage Format (JSONL)

Uses **Line-based JSON (JSONL)** format. It has fast write speeds, preserves data even if the process dies mid-way, and is easy to parse.

**Schema:**
```json
{
  "ts": 1704726000.123456,        // Unix Timestamp
  "method": "place_limit_buy_order",
  "args": ["hash123", "AAPL", 10, 150.0],
  "kwargs": {},
  "result": {"is_success": true, "order_id": 12345}, // Object Serialization
  "error": null
}
```

**Object Serialization Strategy:**
Objects returned by `place_*_order` (Response) may not be JSON serializable. Inside `recorder.record`, if `result` is an object with an `is_success` attribute, it is converted to a dict format like `{"is_success": result.is_success, ...}` before saving.

---

## 3. Data Volume Estimation (Based on Tomorrow's US Market)

**Assumption:**
- **Operating Hours**: Follows Crontab schedule (User defined).
    - _※ The recorder considers the period from `trader.py` execution by Crontab to termination as "one session"._
- **Active Rules**: Assumes 20 symbols.
- **Loop Cycle**: Rule processing 0.1s * 20 + `sleep(1)` = Approx. 3s/Cycle.
- **Total Cycles**: 23,400s (6.5h) / 3s = **7,800 Cycles**.

**1) `get_last_price` (Dominant Factor)**
- Call Count: 7,800 cycles * 20 symbols = **156,000 calls**.
- Size per Record: ~100 bytes (JSON overhead + data).
- Total Size: 156,000 * 100 bytes ≈ **15.6 MB**.

**2) Others (`get_positions`, `get_cash`, `market_hours`)**
- Call Count: Less than a few hundred (Occurs only at start/end/execution).
- Total Size: < 1 MB.

**👉 Conclusion: Daily log size is around 15~20 MB, posing no issue for disk capacity or I/O load.**

---

## 4. Implementation Plan (Code Injection)

Inject logic using the **Decorator Pattern** without significantly modifying `trader.py`.

### Step 1: Create `library/recorder.py` (Asynchronous Design)
**Core Goal**: Prevent the `Trader`'s Main Loop (Main Thread) from being delayed by even 1ms due to file I/O, or stopping due to save failures.

**Architecture: Producer-Consumer Pattern**
*   **Main Thread (Producer)**: Only does `put()` to `Queue` and returns immediately (Cost ≈ 0).
*   **Background Thread (Consumer)**: A separate thread retrieves data from `Queue` and saves to file (Disk I/O).

```python
import json
import time
import functools
import threading
import queue
import atexit
import logging

class AsyncDataRecorder:
    def __init__(self, filename):
        self.queue = queue.Queue(maxsize=10000) # Prevent Memory Overflow
        self.stop_event = threading.Event()
        self.filename = filename
        self.logger = logging.getLogger("recorder")
        
        # Run as Daemon Thread (Requires separate handling to prevent forced kill on main process exit)
        self.worker_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.worker_thread.start()
        
        # Ensure file closes safely on program exit
        atexit.register(self.close)

    def record(self, method_name, args, kwargs, result=None, error=None):
        try:
            # Timestamp must record 'call time' accurately (not Queue processing time)
            entry = {
                "ts": time.time(),
                "method": method_name,
                "args": args,
                "kwargs": kwargs,
                "result": self._serialize(result),
                "error": str(error) if error else None
            }
            # Non-blocking: If queue is full, drop log rather than stopping main logic (block=False)
            self.queue.put_nowait(entry)
        except queue.Full:
            # Extreme case: Disk I/O too slow -> Queue full -> Drop log, prioritize trading
            self.logger.error("Recorder queue full! Dropping log entry.")
        except Exception as e:
            self.logger.error(f"Failed to enqueue log: {e}")

    def _serialize(self, obj):
        # Handle objects not serializable like Order object
        if hasattr(obj, 'is_success'):
             return {"is_success": obj.is_success, "raw": str(obj)}
        return obj

    def _write_loop(self):
        """Background Worker"""
        with open(self.filename, 'a', buffering=1, encoding='utf-8') as f:
            while not self.stop_event.is_set() or not self.queue.empty():
                try:
                    # 1s timeout to induce stop_event check
                    entry = self.queue.get(timeout=1)
                    f.write(json.dumps(entry, default=str) + "\n") # Handle datetime with default=str
                    self.queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"File Write Error: {e}")

    def close(self):
        """Graceful Shutdown"""
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5) # Wait max 5s then exit
```

### Step 2: Apply to `trader.py` (Class-Level Patching)
**Critical Change**: `TradingSystem` creates and caches separate Manager instances per user (`self.managers`). Patching a single instance has a fatal flaw of missing other users' trade logs.
Therefore, we **Patch the Class itself**, so all subsequently created instances are automatically recorded.

```python
# In trader.py startup (before TradingSystem init)
from library.schwab_manager import SchwabManager
from library.korea_manager import KoreaManager
from library.recorder import AsyncDataRecorder, recordable

# 1. Initialize Recorder
recorder = AsyncDataRecorder(f"records/market_data_{args.market}_{today}.jsonl")

# 2. Define Patching Logic
target_methods = [
    'get_last_price', 'get_positions', 'get_positions_result', 
    'get_hashs', 'get_cash', 'get_account_result', 
    'get_market_hours', 'sell_etf_for_cash',
    'place_limit_buy_order', 'place_limit_sell_order', 'place_market_sell_order'
]

# 3. Apply Patch to the Classes (Schwab & Korea)
for ManagerClass in [SchwabManager, KoreaManager]:
    for method_name in target_methods:
        if hasattr(ManagerClass, method_name):
            original_method = getattr(ManagerClass, method_name)
            # 'self' is handled inside the decorator for class method patching
            setattr(ManagerClass, method_name, recordable(recorder)(original_method))

# 4. Initialize System (All Managers created now are patched)
trading_system = TradingSystem(market_strategy)
```

---

## 6. Risk Assessment & Verification (Self-Review)

Potential risks identified during design and countermeasures.

| Risk Item | Impact | Mitigation Strategy |
|-----------|--------|---------------------|
| **Multi-User Data Loss** | High | Changed from `get_any_manager()` instance patch to `SchwabManager` **Class Patch** to cover all users. |
| **I/O Latency Block** | High | Introduced **Producer-Consumer (Queue)** pattern. Guarantees 0ms main thread latency. |
| **Worker Thread Crash** | Medium | Protected by `try-except` inside `_write_loop`. Even if crash occurs, trading continues (Log Loss Only). |
| **Serialization Fail** | Low | Defended by `json.dumps(..., default=str)` and `is_success` dict conversion logic. |
| **Module Import Timing** | Low | Patched at the top of `trader.py` to apply before `TradingSystem` initialization. |


---

## 5. Replay Strategy (For Verification)

For later verification, create a `MockManager` that finds and returns the **record matching timestamp and args from the JSONL file** instead of API requests.

This allows us to inject the **exact same market conditions** into the V2 bot to test logic.
