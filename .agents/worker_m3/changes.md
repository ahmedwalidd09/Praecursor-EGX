# Changes Document - Milestone 3 (worker_m3)

## Summary of Changes

### 1. Pytest Configuration & Network Isolation Guard (`tests/conftest.py`)
- Created `tests/conftest.py` to establish global test configuration and network isolation.
- Added `sys.path` management to ensure `tests/` and `src/` are automatically available on Python's module search path during test execution.
- Implemented an `autouse=True` fixture `block_network_access(monkeypatch)` that monkeypatches `socket.socket.connect`.
- Any attempt by any test to connect to external hosts or APIs raises a `RuntimeError` explaining that external network connections are disabled to prevent API credit burn and external dependencies. Loopback/localhost connections remain allowed.

### 2. Network Isolation Guard Verification Test (`tests/test_network_isolation.py`)
- Created `tests/test_network_isolation.py` containing `test_network_isolation_guard_blocks_outbound_sockets()`.
- Explicitly verifies that attempting an external socket connection (`8.8.8.8:80`) raises `RuntimeError` as enforced by `block_network_access`.

### 3. Test Suite Fixes for 100% Pass Rate (`tests/e2e/test_tier4_scenarios.py` & `tests/test_scheduled_task.py`)
- **`tests/e2e/test_tier4_scenarios.py`**: Updated line 45 `INSERT INTO source_prices` to specify explicit column names matching the 11-column `source_prices` table schema in `SignalHistoryStore`, fixing a `sqlite3.OperationalError` (8 values for 11 columns).
- **`tests/test_scheduled_task.py`**: Updated `run_pipeline` test calls to include `force=True`, ensuring tests execute pipeline stages deterministically regardless of the day of the week `pytest` is executed on (e.g. weekends/Fridays).

---

## Test Results

1. **Network Guard Verification**:
   - `pytest tests/test_network_isolation.py`
   - **Result**: 1 passed (100% success rate)

2. **Scheduling E2E Tests**:
   - `pytest tests/e2e/test_r1_scheduling.py`
   - **Result**: 14 passed in 11.06s (100% success rate)

3. **Historical Archive E2E Tests**:
   - `pytest tests/e2e/test_r3_historical_archive.py`
   - **Result**: 10 passed in 27.03s (100% success rate)

4. **Combined R1 & R3 E2E Tests**:
   - `pytest tests/e2e/test_r1_scheduling.py tests/e2e/test_r3_historical_archive.py`
   - **Result**: 24 passed in 46.60s (100% success rate)

5. **Full Test Suite (`pytest tests`)**:
   - `pytest tests`
   - **Result**: 89 passed in 224.67s (100% success rate, 0 failures)
