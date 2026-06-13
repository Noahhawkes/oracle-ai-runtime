# Device test checklist

1. ORACLE PC is awake and `http://127.0.0.1:7777/api/mode` responds.
2. Tailscale is connected on the Windows PC and iPhone.
3. Tailscale Serve status shows the ORACLE HTTPS address.
4. App **Test connection** reports Companion or Builder mode.
5. Text message streams token-by-token.
6. `/companion` changes the mode indicator.
7. `/builder` changes the mode indicator.
8. Microphone permission is requested only after tapping the microphone.
9. Spoken transcript appears in the composer.
10. ORACLE response is spoken when **Speak ORACLE replies** is enabled.
11. Clear conversation calls `/api/clear` and empties the screen.
12. With Tailscale disconnected, the app fails closed and shows Offline.
13. No router port forwarding exists for 7777.
