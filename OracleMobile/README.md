# ORACLE Mobile

Native iPhone access for Noah's private ORACLE.AI runtime.

## What is implemented

- Native SwiftUI chat interface
- Streaming SSE responses from ORACLE's current `/chat` route
- Companion and Builder mode control
- Server conversation history
- New conversation / clear history
- Microphone dictation with Apple Speech
- Spoken ORACLE replies with AVSpeechSynthesizer
- Tailscale HTTPS or home-LAN connection configuration
- Optional Bearer token stored in the iOS Keychain
- No ORACLE memory database copied to the phone

## Requirements

- iPhone running iOS 17 or later
- A Mac with Xcode to compile and install the native app
- ORACLE running on the Windows PC at `127.0.0.1:7777`
- Tailscale on the PC and iPhone, recommended

See `START_HERE.md` for the installation path and `server/README.md` for the private network connection.

## Security position

Keep `oracle_server.py` on localhost. Use Tailscale Serve to publish it only inside Noah's tailnet. Never forward router port 7777. Never use Tailscale Funnel for ORACLE.

## Build status

The source tree, property list, assets, and Xcode project were generated and structurally validated in this package. The final iOS compilation and signing step requires Xcode on macOS; it cannot be honestly completed on a Windows or Linux host.
