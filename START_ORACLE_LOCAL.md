# How to Start ORACLE (Local Mode)

No coding required. Follow these steps once, then double-click forever.

---

## One-Time Setup

### 1. Install Ollama

Download and run the installer from:

**https://ollama.com/download/windows**

After installing, Ollama runs quietly in your system tray.

---

### 2. Pull the AI model

Open PowerShell or Command Prompt and run:

```
ollama pull qwen2.5:7b
```

This downloads ~4.7 GB. Do it once. You never need to do it again.

---

### 3. That's it for setup.

---

## Starting ORACLE Every Day

1. Make sure the **Ollama app is running** (look for it in the system tray).
   If it's not running, open it from the Start Menu.

2. Double-click **`oracle_local.bat`** in this folder.

3. A black window opens. Wait a few seconds.

4. You'll see the ORACLE banner and a `You:` prompt.

5. Start talking.

---

## Stopping ORACLE

Type `/quit` and press Enter.

Or close the window.

---

## If Something Goes Wrong

The window stays open and shows the error. Common causes:

| Error message | Fix |
|---|---|
| `Ollama not reachable` | Open the Ollama app from the Start Menu |
| `model not found` | Run `ollama pull qwen2.5:7b` in PowerShell |
| `python is not recognized` | Install Python from https://python.org (check "Add to PATH") |

---

## Quick Reference

| Task | How |
|---|---|
| Start ORACLE | Double-click `oracle_local.bat` |
| Stop ORACLE | Type `/quit` |
| Show memory | Type `/memory` |
| Show projects | Type `/projects` |
| Get help | Type `/help` |
