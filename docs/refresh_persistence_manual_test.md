# Manual Refresh Persistence Test (browser level)

The data layer is proven by `tests/test_thread_persistence.py` (automated). This
checklist covers the browser/app level, which must be run against the live
canonical runtime (:7781). Do this on **:7781**, not the stale :7777 copy.

## Steps

1. Start the canonical runtime: double-click the Desktop **ORACLE** icon
   (or `oracle_desktop.bat`). Confirm Operator Home shows :7781 ONLINE.
2. Open `http://127.0.0.1:7781/`.
3. Send a test message: `persistence test one`.
4. **Refresh the browser (F5).**
   - PASS: `persistence test one` reappears (replayed from /api/history).
   - FAIL: the message area is blank.
5. Send a second message: `persistence test two`.
6. **Fully close the browser, then reopen** `http://127.0.0.1:7781/`.
   - PASS: both messages are present, in order.
7. (Optional) Stop and restart the runtime, reopen the page.
   - PASS: the thread is still recoverable from Memory/oracle_memory.db.

## Expected result

All messages survive refresh, browser close, and runtime restart, because every
turn is written to `Memory/oracle_memory.db` and `/api/history` replays the
durable thread on load (`restoreHistory()` in `ui/index.html`).

## If it FAILS

You are almost certainly on the stale :7777 Google Drive copy (which predates the
durable-history fix), not :7781. Re-run the Desktop ORACLE launcher and use the
:7781 link it gives you. See TP_017 / TP_031.
