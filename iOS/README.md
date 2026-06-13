# ORACLE.AI for iOS

A native SwiftUI shell for Noah Hawkes' private ORACLE resident-intelligence server.

## What this first build does

- Opens the ORACLE dashboard inside a native iPhone app.
- Lets Noah change the server address without rebuilding the app.
- Shows online, checking, and offline connection state.
- Supports local-network HTTP access and private Tailscale addresses.
- Includes reload, back/forward gestures, inline media, and a branded app icon.

## Build and install

1. Copy this folder to a Mac.
2. Open `ORACLEAI.xcodeproj` in Xcode.
3. Select the `ORACLEAI` target, then `Signing & Capabilities`.
4. Choose your Apple account/team and change the bundle identifier if needed.
5. Connect the iPhone, select it as the run destination, and press Run.
6. In the app settings, enter the Windows computer address, for example `192.168.1.100:7777`.

The Windows ORACLE server must listen on `0.0.0.0`, not only `127.0.0.1`. Windows Firewall must allow TCP port 7777 on private networks.

## Important

`localhost:7777` on an iPhone points to the iPhone, not the Windows computer. For remote access, use Tailscale or another authenticated private tunnel. Do not forward port 7777 directly through the router.

## Next production pass

The next pass should replace the web wrapper with authenticated native chat, voice streaming, push notifications, biometric unlock, durable session handling, and a formally versioned ORACLE API.
