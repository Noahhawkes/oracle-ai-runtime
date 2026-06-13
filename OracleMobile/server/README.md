# Private phone connection

## Recommended: Tailscale Serve

Keep ORACLE listening only on `127.0.0.1:7777`. Tailscale Serve acts as a private HTTPS reverse proxy available only to devices authenticated to Noah's tailnet.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_oracle_phone_access.ps1
```

The command uses:

```powershell
tailscale serve --bg localhost:7777
```

Copy the resulting `https://...ts.net` address into the app. The `--bg` configuration survives Tailscale and machine restarts until reset.

Disable it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\stop_oracle_phone_access.ps1
```

## Home Wi-Fi fallback

A LAN address such as `http://192.168.1.25:7777` requires ORACLE to listen beyond localhost and requires Windows Firewall configuration. That increases exposure and is not the default in this package. Use Tailscale instead.

## Do not do this

- Do not forward TCP 7777 through the home router.
- Do not run `tailscale funnel` for ORACLE.
- Do not place API keys or memory files inside the iPhone project.
