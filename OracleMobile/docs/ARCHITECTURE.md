# Architecture

```text
ORACLE Mobile (iPhone)
        |
        | HTTPS inside Noah's Tailscale tailnet
        v
Tailscale Serve on Windows
        |
        | reverse proxy to 127.0.0.1:7777
        v
oracle_server.py
        |
        v
core/oracle.py -> Companion / Builder -> approved memory and tools
```

The phone is a client, not a second ORACLE brain. The canonical state remains on the Windows machine. This prevents an out-of-date mobile memory fork and keeps `Memory/`, `Context/`, local files, credentials, and execution authority off the iPhone.

The app consumes the existing transport contract and does not bypass SOV1/ORACLE validators or approval gates.
