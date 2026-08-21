# Witness Tools

Local-only witness pipeline built 2026-07-05 (Claude Code session, Noah.Physical
authority). The tools are read-only against media; they never upload,
never mutate recordings, and label all derived text `STT_DERIVED` /
`INTERPRETED` candidate — never canon.

## obs_vocal_witness.py
Transcribes the live/finished OBS recording with faster-whisper (local CPU) and
injects a provenance-labeled `VOCAL_WITNESS` message into ORACLE's thread on
7781. Used for the 2026-07-05 vocal presence proof (first voice → ORACLE loop).
Note: ORACLE's intent router treats the literal phrase "can you hear me" as a
voice_request trigger (core/oracle_intent.py:80); the injector hyphenates it in
transit and records the verbatim text in the witness receipt.

## obs_media_metadata_witness.py
Reads filesystem, container, stream, QuickTime/MOV, and OBS-log metadata from
recordings. It does not decode or save frames and never creates screenshots.
It writes evidence to the single canonical source thread:
`C:\Oracle\state\threads\oracle_obs_media_thread_v1.jsonl`.
Stop flag: `C:\Oracle\state\media_metadata_witness\stop.flag`.

## obs_transcript_watcher.py
Ongoing daily transcript of all OBS recordings: catch-up pass over today's
files, then follows the active recording in ~2-minute increments. Output:
`C:\Oracle\state\transcripts\obs\YYYY-MM-DD_obs_transcript.md` with wall-clock
timestamps. Transcript evidence is also appended to the canonical source
thread above; Markdown is a derived human-readable view, not an independent
authority source. Stop flag: `C:\Oracle\state\transcripts\obs\stop.flag`.

## media_memory_bridge.py
Continuously indexes new canonical source-thread events into
`Memory\oracle_memory.db`. The JSONL thread remains authoritative; memory rows
are candidate search indexes carrying the original event ID and source path.
Stop flag: `C:\Oracle\state\media_memory_bridge\stop.flag`.

## Dependencies
`pip install faster-whisper` (installed 2026-07-05). The base.en model must be
fetched over IPv4 (Spectrum IPv6 to HuggingFace resets TLS):
`curl -4 -L -o model.bin https://huggingface.co/Systran/faster-whisper-base.en/resolve/main/model.bin`
(plus config.json, tokenizer.json, vocabulary.txt) into a local model dir, and
point `MODEL_DIR` at it. The metadata watcher requires PyAV and no vision model.
