# Safe Self-Witness Telemetry

Status: implemented candidate
Canon status: raw_signal
Promotion status: not_promoted
Authority: Noah.Physical

`core/witness_telemetry.py` is a manual, local-only activity counter. It records which process has focus, active/idle state, aggregate keyboard activity, aggregate mouse clicks, and a SHA-256 hash of the window title. It never stores which keys were pressed.

It does not capture typed text, clipboard contents, passwords, URLs, camera frames, microphone audio, screenshots, or raw window titles by default.

## Manual use

```powershell
python core\witness_telemetry.py --duration 60
```

Output is limited to:

```text
C:\ORACLE.AI\sandbox\telemetry\
  session_<run>.jsonl
  summary_<run>.json
  receipt_<run>.json
```

The module is not imported by the server and has no boot integration.

## Window-title boundary

Default:

```text
TELEMETRY_STORE_WINDOW_TITLES=false
```

Only a hash is stored. Setting the variable to `true` is an explicit local opt-in to raw titles. Even with opt-in, no browser URL extraction occurs.

## Custody boundary

- Every summary is `raw_signal` and `not_promoted`.
- Receipts hash the session and summary files.
- Only `.json` and `.jsonl` outputs are permitted.
- Output paths are checked against the configured telemetry root.
- A run performs no network, GitHub, Drive, canon, or external action.

This telemetry is evidence about machine activity, not evidence of authorship, intent, identity, or consciousness.
