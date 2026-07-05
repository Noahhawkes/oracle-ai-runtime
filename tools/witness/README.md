# Witness Tools

Local-only witness pipeline built 2026-07-05 (Claude Code session, Noah.Physical
authority). All three tools are read-only against media; they never upload,
never mutate recordings, and label all derived text `STT_DERIVED` /
`INTERPRETED` candidate — never canon.

## obs_vocal_witness.py
Transcribes the live/finished OBS recording with faster-whisper (local CPU) and
injects a provenance-labeled `VOCAL_WITNESS` message into ORACLE's thread on
7781. Used for the 2026-07-05 vocal presence proof (first voice → ORACLE loop).
Note: ORACLE's intent router treats the literal phrase "can you hear me" as a
voice_request trigger (core/oracle_intent.py:80); the injector hyphenates it in
transit and records the verbatim text in the witness receipt.

## prompt_witness.py
Samples a frame from the live OBS recording every 60s, reads it with
qwen2.5vl:7b via local ollama, and logs every visible AI chat window (system,
latest user prompt, latest response) to
`C:\Oracle\state\prompt_witness\witness_log.jsonl` with frame sha256 receipts.
Stop flag: `C:\Oracle\state\prompt_witness\stop.flag`.

## obs_transcript_watcher.py
Ongoing daily transcript of all OBS recordings: catch-up pass over today's
files, then follows the active recording in ~2-minute increments. Output:
`C:\Oracle\state\transcripts\obs\YYYY-MM-DD_obs_transcript.md` with wall-clock
timestamps. Stop flag: `C:\Oracle\state\transcripts\obs\stop.flag`.

## Dependencies
`pip install faster-whisper` (installed 2026-07-05). The base.en model must be
fetched over IPv4 (Spectrum IPv6 to HuggingFace resets TLS):
`curl -4 -L -o model.bin https://huggingface.co/Systran/faster-whisper-base.en/resolve/main/model.bin`
(plus config.json, tokenizer.json, vocabulary.txt) into a local model dir, and
point `MODEL_DIR` at it. qwen2.5vl:7b comes from the existing ollama install.
