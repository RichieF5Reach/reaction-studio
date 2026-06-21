# Reaction Studio v4 — 100% Local, Yours Forever

**No subscriptions. No API keys. No cloud dependency. Runs on your machine permanently.**

---

## This app will NEVER stop working because:

- All source code is plain Python files — open them in Notepad if you want
- No license server, no activation, no "phone home" check
- No dependency on any paid service to function
- YouTube download/upload needs internet, but the app engine itself does not

---

## Install (Windows — one time)

```
Right-click install.ps1 → Run with PowerShell
```

That copies everything to `%LOCALAPPDATA%\ReactionStudio` and creates a Desktop shortcut.

## Run it forever without reinstalling

```
python C:\Users\YOU\AppData\Local\ReactionStudio\src\main.py
```

Or just double-click the Desktop shortcut. If the shortcut ever breaks, run that command directly — the files never move.

---

## What it does

1. **Finds trending videos** in your niche via yt-dlp (free, open source)
2. **Writes a reaction script** via Ollama running Llama 3 locally on your CPU/GPU
3. **Synthesizes a voice** via Piper TTS — local, offline voice synthesis
4. **Composes the video** with MoviePy — filters, captions, timing, picture-in-picture
5. **Adds crashout FX** — zoom punch, shake cam, bold caption pop-ups on hype moments
6. **Auto-uploads to YouTube** via Google OAuth (no API key — just sign in with your account)

---

## Requirements

| Thing | Where | Cost |
|---|---|---|
| Python 3.10+ | https://python.org/downloads | Free |
| Ollama | https://ollama.com then `ollama pull llama3` | Free |
| ffmpeg | https://ffmpeg.org/download.html | Free |
| 8GB RAM | — | — |

All pip packages install automatically during setup.

---

## Backup recommendation

Keep a copy of this ZIP on a USB drive or Google Drive. The installer is self-contained — you can reinstall on any Windows PC anytime, even with no internet, as long as Python is installed.

---

## If you need to reinstall pip packages manually

```
python -m pip install yt-dlp moviepy piper-tts openai-whisper google-auth google-auth-oauthlib google-api-python-client Pillow requests numpy
```

---

## Crashout FX

When the AI script marks a `[CRASHOUT]` moment:
- 1.15x zoom punch for 0.35 seconds
- Shake-cam effect for 0.5 seconds  
- Bold caption pops on screen ("WAIT WAIT WAIT", "bro is NOT moving different", etc.)

Toggle on/off in the Effects tab.

---

## Video Filters

None / Dramatic / VHS Glitch / Warm Sunset / Cold Blue / Black & White / High Contrast / Vignette / Oversaturated / Film Grain

---

## Caption Styles

Classic White / Bold Yellow / Black Bar / Meme Caps / Subtle Gray

Auto-generates `.srt` subtitle file alongside the video.

---

## Energy Levels

| Level | Vibe |
|---|---|
| Chill | Relaxed, observational, dry humor |
| Mid | Conversational, relatable |
| High | Loud, expressive, hype moments |
| UNHINGED | Full caps, chaos, screaming commentary |

---

## YouTube OAuth

No API key needed. Uses your personal Google account.
Token saved at `~/.reaction_studio/token.json` — yours forever.

---

## Source files

```
ReactionStudio/
  src/
    main.py       -- GUI app (tkinter, Windows installer style)
    pipeline.py   -- video pipeline (find, script, TTS, compose, upload)
    filters.py    -- video filters and crashout FX
    captions.py   -- auto-captions and SRT export
  install.ps1     -- one-time Windows installer
  README.md       -- this file
  HOW_TO_RUN_FOREVER.txt  -- created during install
```

---

*Built with: yt-dlp · Ollama · Piper TTS · MoviePy · Whisper · YouTube Data API v3*  
*All dependencies are free and open source.*
