# ORACLE Mobile — Start Here

This package is a native SwiftUI iPhone client for the ORACLE runtime already running on Noah's Windows PC.

It connects to the existing endpoints:

- `POST /chat` — Server-Sent Events response stream
- `GET /api/history`
- `GET /api/mode`
- `POST /api/clear`

The safest connection is **Tailscale Serve**. ORACLE remains bound to `127.0.0.1:7777`; Tailscale privately provides an HTTPS address to Noah's authenticated devices.

## Fast installation sequence

1. On the Windows ORACLE computer, start ORACLE normally at `http://localhost:7777`.
2. Install and sign in to Tailscale on Windows and the iPhone using the same tailnet.
3. On Windows PowerShell, run the included `server/start_oracle_phone_access.ps1`.
4. Copy the HTTPS address printed by Tailscale.
5. On a Mac, open `OracleMobile.xcodeproj` in Xcode.
6. Select the `OracleMobile` target, open **Signing & Capabilities**, and select Noah's Apple Account team.
7. Connect the iPhone to the Mac, select it as the run destination, and press **Run**.
8. On the iPhone, open ORACLE, go to **Settings**, paste the HTTPS address, and tap **Test connection**.

A free Apple Account can install the app for personal testing, but the provisioning profile expires after seven days. A paid Apple Developer membership avoids that weekly reinstall cycle and enables TestFlight distribution.
