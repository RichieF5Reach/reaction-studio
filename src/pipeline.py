"""
REACTION STUDIO — Pipeline Engine
Handles: trending video discovery, script generation, TTS, video compose,
         auto-captions, filters, FX, and YouTube export.
Targets moviepy >= 2.0.
"""

import os
import json
import random
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import requests
from pathlib import Path

CONFIG_DIR  = Path.home() / ".reaction_studio"
TOKEN_PATH  = CONFIG_DIR / "token.json"
CONFIG_PATH = CONFIG_DIR / "config.json"

CONFIG_DIR.mkdir(exist_ok=True)

# Ensure src/ dir is on sys.path so sibling modules import correctly
_src_dir = str(Path(__file__).parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# ─────────────────────────────────────────────
#  STEP 1: Find trending video via yt-dlp
# ─────────────────────────────────────────────
def find_trending_video(niche: str, max_duration_sec: int = 1200) -> dict:
    """
    Try up to 3 different search queries to find a downloadable video.
    Falls back gracefully — never returns an empty result that kills the pipeline.
    """
    year = time.strftime("%Y")
    queries = [
        f"ytsearch10:{niche} viral {year}",
        f"ytsearch10:{niche} trending",
        f"ytsearch10:{niche} funny moments",
    ]

    for search_query in queries:
        cmd = [
            "yt-dlp", "--dump-json", "--no-download",
            "--match-filter", f"duration < {max_duration_sec}",
            "--no-playlist",
            search_query,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            lines = [l for l in result.stdout.strip().splitlines() if l.startswith("{")]
            # Try each result until we find one that looks downloadable
            for line in lines:
                try:
                    data = json.loads(line)
                    url  = data.get("webpage_url", "")
                    if not url:
                        continue
                    # Skip age-restricted / members-only quickly
                    age  = data.get("age_limit", 0) or 0
                    avail = data.get("availability", "public")
                    if age > 17 or avail not in ("public", "unlisted", None, ""):
                        continue
                    return {
                        "url":       url,
                        "title":     data.get("title", "Unknown"),
                        "duration":  data.get("duration", 0),
                        "thumbnail": data.get("thumbnail", ""),
                        "uploader":  data.get("uploader", ""),
                    }
                except Exception:
                    continue
        except Exception as e:
            print(f"[find_trending_video] query '{search_query}': {e}")

    # Hard fallback — a long-form public domain video (NASA ISS tour, ~25min)
    # Using a video with substantial duration so the reaction pipeline
    # has enough content to work with (crashout markers, captions, etc.)
    print("[find_trending_video] All queries failed — using fallback video")
    return {
        "url":       "https://www.youtube.com/watch?v=Bp3LkFHmCME",
        "title":     "NASA ISS Tour (public domain, ~25 minutes)",
        "duration":  1500,
        "thumbnail": "",
        "uploader":  "NASA",
    }


# ─────────────────────────────────────────────
#  STEP 2: Generate reaction script via Ollama
# ─────────────────────────────────────────────
def generate_script(video_title: str, niche: str,
                    energy: str, style_hint: str) -> str:
    energy_desc = {
        "Chill":    "relaxed, observational, occasional dry humor",
        "Mid":      "conversational, moderate energy, relatable commentary",
        "High":     "loud, expressive, frequent exclamations, hype moments",
        "UNHINGED": "completely unfiltered, screaming in caps, chaotic takes, "
                    "multiple interruptions, drops everything at big moments",
    }.get(energy, "high energy")

    system_prompt = textwrap.dedent(f"""
        You are writing a YouTube reaction video script.
        Style: {style_hint}
        Energy: {energy_desc}
        Niche: {niche}

        Format:
        [MM:SS] REACTION_LINE
        Add [CRASHOUT] on the same line for big moments
        Add [PAUSE] on the same line where you pause the clip

        Write ~40 reaction segments spread over a 15-20 minute video.
    """).strip()

    payload = {
        "model":  "llama3",
        "prompt": f"{system_prompt}\n\nWrite a full reaction script for: \"{video_title}\"",
        "stream": False,
    }
    try:
        # (10, 300): 10s to connect (fast-fail if Ollama not running),
        #            300s for the model to finish generating
        r = requests.post("http://localhost:11434/api/generate",
                          json=payload, timeout=(10, 300))
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            if text:
                return text
    except Exception as e:
        print(f"[generate_script] Ollama error: {e}")

    # Fallback script — always produces something
    return "\n".join([
        f"[0:00] okay chat we're watching this — {video_title}",
        "[0:30] wait what [CRASHOUT]",
        "[1:00] nah bro said that with his whole chest [PAUSE]",
        "[2:00] I cannot believe this is real",
        "[3:00] WE ARE SO BACK [CRASHOUT]",
        "[4:00] chat are you seeing this right now",
        "[5:00] okay I need a moment [PAUSE]",
        "[6:00] this is genuinely insane",
        "[7:00] bro really said that [CRASHOUT]",
        "[8:00] I'm not okay",
    ])


# ─────────────────────────────────────────────
#  STEP 3: Text-to-Speech via Piper
# ─────────────────────────────────────────────
def synthesize_voice(script: str, voice_model_path: str, output_path: str) -> bool:
    """
    Synthesize voice using Piper TTS. Returns True on success.
    Safe to call even if Piper is not installed — returns False gracefully.
    """
    lines = [
        l.split("]")[-1].strip()
        for l in script.splitlines()
        if l.strip() and "[CRASHOUT]" not in l and "[PAUSE]" not in l
    ]
    if not lines:
        return False

    segment_files = []
    # TemporaryDirectory auto-cleans on exit — no more temp dir leaks
    _tmp_ctx = tempfile.TemporaryDirectory(prefix="reaction_tts_")
    tmp_dir  = Path(_tmp_ctx.name)

    # Determine piper binary
    # Use the supplied path only if it's a real .onnx file that actually exists
    piper_cmd = (
        voice_model_path
        if (voice_model_path
            and voice_model_path.endswith(".onnx")
            and os.path.isfile(voice_model_path))
        else None
    )
    model_arg = piper_cmd or "en_US-lessac-medium"
    if voice_model_path and voice_model_path.endswith(".onnx") and not piper_cmd:
        print(f"[synthesize_voice] .onnx model not found: {voice_model_path!r} — "
              "falling back to en_US-lessac-medium")

    for i, line in enumerate(lines[:60]):
        seg_path = tmp_dir / f"seg_{i:03d}.wav"
        cmd = ["piper", "--model", model_arg, "--output-file", str(seg_path)]
        try:
            r = subprocess.run(cmd, input=line, capture_output=True,
                               text=True, timeout=30)
            if seg_path.exists() and seg_path.stat().st_size > 0:
                segment_files.append(str(seg_path))
        except FileNotFoundError:
            print("[synthesize_voice] piper not found — skipping TTS")
            return False
        except Exception as e:
            print(f"[synthesize_voice] segment {i}: {e}")

    if not segment_files:
        print("[synthesize_voice] No segments produced.")
        _tmp_ctx.cleanup()
        return False

    list_file = tmp_dir / "concat.txt"
    list_file.write_text("\n".join(f"file '{f}'" for f in segment_files))
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_file), "-acodec", "pcm_s16le", output_path],
            capture_output=True, timeout=300)
        success = result.returncode == 0 and os.path.exists(output_path)
        if not success:
            print(f"[synthesize_voice] ffmpeg failed: {result.stderr.decode()[:300]}")
        _tmp_ctx.cleanup()
        return success
    except Exception as e:
        print(f"[synthesize_voice] ffmpeg: {e}")
        _tmp_ctx.cleanup()
        return False


# ─────────────────────────────────────────────
#  STEP 4: Download source video
# ─────────────────────────────────────────────
def download_video(url: str, output_dir: str) -> str:
    """
    Download video via yt-dlp. Returns path to downloaded file or "" on failure.
    Tries two format strings to maximise compatibility.
    """
    if not url:
        return ""

    output_template = os.path.join(output_dir, "source.%(ext)s")

    # Try best merged mp4 first, fall back to best single-file
    format_attempts = [
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "best[height<=720]/best",
    ]

    for fmt in format_attempts:
        cmd = [
            "yt-dlp",
            "--format", fmt,
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", output_template,
            url,
        ]
        try:
            result = subprocess.run(cmd, timeout=600, capture_output=True, text=True)
            if result.returncode == 0:
                # Prefer mp4 > mkv > webm > any other — deterministic
                candidates = [
                    os.path.join(output_dir, f)
                    for f in os.listdir(output_dir)
                    if f.startswith("source.") and not f.endswith(".part")
                    and os.path.getsize(os.path.join(output_dir, f)) > 10_000
                ]
                _pref = {".mp4": 0, ".mkv": 1, ".webm": 2}
                candidates.sort(
                    key=lambda p: _pref.get(os.path.splitext(p)[1], 99))
                if candidates:
                    return candidates[0]
            else:
                _last_err = result.stderr[:300].strip()
                print(f"[download_video] fmt='{fmt}' failed: {_last_err}")
        except Exception as e:
            _last_err = str(e)
            print(f"[download_video] {e}")

    # Return a descriptive error string so callers can surface it to the user
    return f"ERROR: {_last_err}" if '_last_err' in dir() else "ERROR: download failed"


# ─────────────────────────────────────────────
#  Crashout caption lines
# ─────────────────────────────────────────────
CRASHOUT_LINES_SHORT = [
    "bro is NOT moving different",
    "WAIT WAIT WAIT",
    "no way",
    "I'm cooked.",
    "chat we need to talk",
    "THE AUDACITY",
    "I literally cannot",
]


# ─────────────────────────────────────────────
#  STEP 5: Compose reaction video  (moviepy 2.x)
# ─────────────────────────────────────────────
def compose_video(source_video: str, voice_audio: str,
                  script: str, crashout: bool, output_path: str,
                  video_filter: str = "None",
                  reaction_filter: str = "None",
                  caption_style: str = "Bold Yellow",
                  caption_mode: str = "Auto") -> bool:
    """
    Full reaction video compose pipeline.
    moviepy 2.x API:
      - Import from moviepy (not moviepy.editor)
      - TextClip: text=, font_size=, text_align=
      - Clip methods: with_start(), with_duration(), with_position(), with_audio()
      - Transforms: image_transform() and transform() (not fl_image / fl)
      - write_videofile: codec=, audio_codec= (same in 2.x, preset still works)
    """
    if not source_video or not os.path.exists(source_video):
        print(f"[compose_video] Source video not found: {source_video!r}")
        return False

    try:
        from moviepy import (
            VideoFileClip, AudioFileClip,
            CompositeVideoClip, TextClip,
        )
        from captions import (
            transcribe_with_whisper, captions_from_script,
            burn_captions, export_srt,
        )
        from filters import (
            apply_filter, apply_crashout_zoom, apply_shake,
        )

        source = VideoFileClip(source_video)

        # ── Voice audio ──────────────────────────────────────────────────
        has_voice = bool(voice_audio) and os.path.exists(voice_audio) and \
                    os.path.getsize(voice_audio) > 0
        voice = AudioFileClip(voice_audio) if has_voice else None

        # Preserve original source audio if no voice track
        original_audio = source.audio if not has_voice else None

        # ── Apply video filter ────────────────────────────────────────────
        source = apply_filter(source, video_filter)

        # ── Parse crashout timestamps ─────────────────────────────────────
        crashout_times = []
        for line in script.splitlines():
            if "[CRASHOUT]" in line:
                m = re.match(r"\[(\d+):(\d+)\]", line.strip())
                if m:
                    t = int(m.group(1)) * 60 + int(m.group(2))
                    crashout_times.append(t)

        # ── Crashout zoom + shake ─────────────────────────────────────────
        if crashout:
            for t in crashout_times[:8]:
                if t < source.duration - 1:
                    source = apply_crashout_zoom(source, start=float(t),
                                                 duration=0.35, zoom_factor=1.15)
                    source = apply_shake(source, start=float(t),
                                         duration=0.5, intensity=6)

        # ── Generate captions ─────────────────────────────────────────────
        caption_entries = []
        srt_path = output_path.replace(".mp4", ".srt")

        if caption_mode == "Auto":
            if has_voice:
                caption_entries = transcribe_with_whisper(voice_audio)
            if not caption_entries:
                caption_entries = captions_from_script(script)
        elif caption_mode == "Script":
            caption_entries = captions_from_script(script)
        # caption_mode == "None" -> leave caption_entries empty

        # ── Burn captions (safe — falls back if ImageMagick missing) ──────
        if caption_entries:
            export_srt(caption_entries, srt_path)
            try:
                source = burn_captions(source, caption_entries, caption_style)
            except Exception as cap_err:
                print(f"[compose_video] Caption rendering failed (continuing without): {cap_err}")

        # ── Crashout text pop-ups (safe) ───────────────────────────────────
        extra_clips = [source]
        if crashout:
            for t in crashout_times[:5]:
                if t < source.duration - 3:
                    try:
                        txt = (
                            TextClip(
                                text=random.choice(CRASHOUT_LINES_SHORT),
                                font_size=52,
                                color="yellow",
                                stroke_color="black",
                                stroke_width=4,
                                method="label",        # "label" works without ImageMagick
                                size=(int(source.w * 0.8), None),
                                text_align="center",
                            )
                            .with_position(("center", 0.12), relative=True)
                            .with_start(float(t))
                            .with_duration(1.8)
                        )
                        extra_clips.append(txt)
                    except Exception as txt_err:
                        print(f"[compose_video] Crashout text failed (skipping): {txt_err}")

        # ── Compose ───────────────────────────────────────────────────────
        final = CompositeVideoClip(extra_clips)

        # Attach audio: prefer reaction voice, fall back to original source audio
        # Trim voice to source duration so audio never runs past video end
        if voice is not None:
            voice_trimmed = voice.with_duration(
                min(voice.duration, source.duration))
            final = final.with_audio(voice_trimmed)
        elif original_audio is not None:
            final = final.with_audio(original_audio)

        # ── Write output ──────────────────────────────────────────────────
        _out_dir = os.path.dirname(os.path.abspath(output_path))
        if _out_dir:
            os.makedirs(_out_dir, exist_ok=True)
        final.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            logger=None,
        )
        # Close in dependency order: final (composite) first, then its sources
        try:
            final.close()
        except Exception:
            pass
        try:
            source.close()
        except Exception:
            pass
        if voice:
            try:
                voice.close()
            except Exception:
                pass

        return os.path.exists(output_path) and os.path.getsize(output_path) > 10_000

    except ImportError as e:
        print(f"[compose_video] Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"[compose_video] Error: {e}")
        import traceback; traceback.print_exc()
        return False



# ─────────────────────────────────────────────
#  YOUTUBE SCOPES
# ─────────────────────────────────────────────
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _validate_client_secrets(path: str) -> str:
    """
    Returns "" if file looks OK, or a human-readable error string.
    Catches the very common mistake of downloading a 'web' client instead
    of a 'Desktop app' client from Google Console.
    """
    import json as _json
    try:
        data = _json.loads(Path(path).read_text())
    except Exception as e:
        return f"Cannot read client_secrets.json: {e}"
    if "installed" not in data and "web" in data:
        return (
            "Your client_secrets.json is for a 'Web Application' — "
            "Reaction Studio needs a 'Desktop app' OAuth client.\n\n"
            "Fix: Go to console.cloud.google.com → Credentials → "
            "Edit your OAuth Client → change Application type to "
            "'Desktop app' → save → download again."
        )
    if "installed" not in data:
        return (
            "client_secrets.json format not recognised. "
            "Make sure you downloaded an OAuth 2.0 Client ID "
            "(Desktop app) from Google Console."
        )
    return ""


# ─────────────────────────────────────────────
#  OAUTH — check if already authenticated
# ─────────────────────────────────────────────
def is_authenticated() -> bool:
    """Return True if a valid (or refreshable) token exists."""
    if not TOKEN_PATH.exists():
        return False
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), YT_SCOPES)
        if creds and creds.valid:
            return True
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
            return True
    except Exception as e:
        print(f"[is_authenticated] {e}")
    return False


# ─────────────────────────────────────────────
#  OAUTH — browser-based local server flow
# ─────────────────────────────────────────────
def run_oauth_flow(client_secrets_path: str) -> bool:
    """
    Run Google OAuth via a local redirect server.

    Key fixes vs previous version:
    - Validates the secrets file type FIRST with a clear error message.
    - Recreates the InstalledAppFlow fresh for each port attempt
      (reusing the same flow instance after failure is undefined behaviour).
    - Uses 'continue' not 'break' on non-OSError so all ports are tried.
    - Timeout and other non-port errors continue the loop, not abort it.
    """
    # Validate file before trying anything
    err = _validate_client_secrets(client_secrets_path)
    if err:
        print(f"[run_oauth_flow] {err}")
        raise ValueError(err)   # Re-raised so UI can show it to user

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "google-auth-oauthlib is not installed.\n"
            "Run: pip install google-auth-oauthlib")

    last_error = None
    for port in [8080, 8090, 8888, 9090, 0]:
        try:
            # Fresh flow instance per attempt — avoids stale internal state
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path, YT_SCOPES)
            creds = flow.run_local_server(
                port=port,
                open_browser=True,
                timeout_seconds=180,
                success_message=(
                    "Connected! Reaction Studio is now linked to YouTube. "
                    "You can close this tab."
                ),
            )
            TOKEN_PATH.write_text(creds.to_json())
            print(f"[run_oauth_flow] Success on port {port}. Token saved.")
            return True
        except OSError as e:
            # Port already in use — try next port
            print(f"[run_oauth_flow] Port {port} busy: {e}")
            last_error = e
            continue
        except Exception as e:
            # Timeout, user cancelled, network error, etc. — try next port
            print(f"[run_oauth_flow] Port {port} error ({type(e).__name__}): {e}")
            last_error = e
            continue   # ← was 'break' — this was the primary failure cause

    print(f"[run_oauth_flow] All ports failed. Last error: {last_error}")
    return False


# ─────────────────────────────────────────────
#  OAUTH — manual copy-paste fallback
#  NOTE: Google removed OOB ("urn:ietf:wg:oauth:2.0:oob") on Jan 31 2023.
#  The replacement is a loopback redirect with a custom port.
#  We run a minimal HTTP server on a fixed port and redirect there.
# ─────────────────────────────────────────────
def run_oauth_flow_manual(client_secrets_path: str) -> dict:
    """
    Starts a minimal loopback HTTP listener on port 8765, builds an
    auth URL the user opens in any browser, then waits up to 5 minutes
    for the redirect. Returns dict:
      {"status": "waiting", "url": "https://accounts.google.com/..."}
    on success (listener started), or
      {"status": "error", "message": "..."}
    on failure.

    The listener saves the token automatically when Google redirects back.
    Check is_authenticated() after ~5 min or listen for the callback.
    """
    err = _validate_client_secrets(client_secrets_path)
    if err:
        return {"status": "error", "message": err}

    import threading as _th
    import http.server as _hs
    import urllib.parse as _up

    MANUAL_PORT = 8765
    result_container = {"done": False, "error": None}

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_path, YT_SCOPES)

        redirect_uri = f"http://localhost:{MANUAL_PORT}/"
        flow.redirect_uri = redirect_uri
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
        )

        class _Handler(_hs.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed   = _up.urlparse(self.path)
                params   = _up.parse_qs(parsed.query)
                code_lst = params.get("code", [])
                err_lst  = params.get("error", [])

                if err_lst:
                    result_container["error"] = err_lst[0]
                    self._respond("Access denied — check Google Console settings.")
                elif code_lst:
                    try:
                        flow.fetch_token(code=code_lst[0])
                        TOKEN_PATH.write_text(flow.credentials.to_json())
                        result_container["done"] = True
                        self._respond(
                            "Connected! Reaction Studio is linked to YouTube. "
                            "You can close this tab.")
                    except Exception as ex:
                        result_container["error"] = str(ex)
                        self._respond(f"Token exchange failed: {ex}")
                else:
                    self._respond("Waiting for Google callback...")

                # Signal server to stop
                _th.Thread(target=self.server.shutdown, daemon=True).start()

            def _respond(self, msg):
                body = (
                    f"<html><body style='font-family:sans-serif;padding:40px;"
                    f"background:#111;color:#eee'>"
                    f"<h2>{msg}</h2></body></html>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass  # Suppress access logs

        server = _hs.HTTPServer(("127.0.0.1", MANUAL_PORT), _Handler)
        server.timeout = 300   # 5 minute timeout

        def _serve():
            try:
                server.handle_request()   # handles ONE request then stops
            except Exception as ex:
                result_container["error"] = str(ex)

        _th.Thread(target=_serve, daemon=True).start()
        _PENDING_MANUAL["flow"]      = flow
        _PENDING_MANUAL["container"] = result_container

        return {"status": "waiting", "url": auth_url}

    except Exception as e:
        return {"status": "error", "message": str(e)}


_PENDING_MANUAL: dict = {}


def check_manual_auth_result() -> dict:
    """
    Poll this after run_oauth_flow_manual() to see if the user completed auth.
    Returns: {"status": "done"} | {"status": "waiting"} | {"status": "error", "message": ...}
    """
    container = _PENDING_MANUAL.get("container", {})
    if container.get("done"):
        return {"status": "done"}
    if container.get("error"):
        return {"status": "error", "message": container["error"]}
    return {"status": "waiting"}


# Legacy — kept for backward compatibility but now unused
_PENDING_FLOWS: dict = {}


def exchange_oauth_code(client_secrets_path: str, code: str) -> bool:
    """Kept for backward compat — prefer run_oauth_flow_manual + check_manual_auth_result."""
    flow = _PENDING_FLOWS.get(client_secrets_path)
    if not flow:
        return False
    try:
        flow.fetch_token(code=code)
        TOKEN_PATH.write_text(flow.credentials.to_json())
        _PENDING_FLOWS.pop(client_secrets_path, None)
        return True
    except Exception as e:
        print(f"[exchange_oauth_code] {e}")
        return False


# ─────────────────────────────────────────────
#  STEP 6: Upload to YouTube
# ─────────────────────────────────────────────
def upload_to_youtube(video_path: str, title: str,
                      description: str = "", privacy: str = "public") -> str:
    """
    Upload video to YouTube. Auto-refreshes expired tokens.
    Returns the video URL on success, or "ERROR: ..." on failure.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        if not TOKEN_PATH.exists():
            return "ERROR: Not authenticated. Connect your Google account first."

        # Load and auto-refresh credentials
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), YT_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    TOKEN_PATH.write_text(creds.to_json())
                    print("[upload_to_youtube] Token refreshed.")
                except Exception as refresh_err:
                    return f"ERROR: Token expired and refresh failed: {refresh_err}. Please re-connect your Google account."
            else:
                return "ERROR: Token invalid. Please re-connect your Google account."

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title":       title[:100],
                "description": description,
                "tags":        ["reaction", "viral", "commentary", "reactionvideo"],
                "categoryId":  "22",
            },
            "status": {"privacyStatus": privacy},
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024,   # 5MB chunks — more reliable than 1MB
        )
        request  = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media)

        response = None
        _chunk_retries = 0
        while response is None:
            try:
                status, response = request.next_chunk()
                _chunk_retries = 0   # reset on success
                if status:
                    pct = int(status.progress() * 100)
                    print(f"[upload_to_youtube] {pct}%")
            except Exception as chunk_err:
                _chunk_retries += 1
                if _chunk_retries > 3:
                    raise RuntimeError(
                        f"Upload failed after 3 retries: {chunk_err}") from chunk_err
                print(f"[upload_to_youtube] chunk error (retry {_chunk_retries}/3): "
                      f"{chunk_err}")
                time.sleep(2 ** _chunk_retries)

        video_id = response.get("id", "")
        if not video_id:
            return f"ERROR: Upload succeeded but got no video ID. Response: {response}"
        return f"https://youtu.be/{video_id}"

    except Exception as e:
        return f"ERROR: {e}"
