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

    # Hard fallback — a public domain / CC video that always works
    print("[find_trending_video] All queries failed — using fallback video")
    return {
        "url":       "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "title":     "Me at the zoo (first YouTube video ever)",
        "duration":  19,
        "thumbnail": "",
        "uploader":  "jawed",
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
        r = requests.post("http://localhost:11434/api/generate",
                          json=payload, timeout=300)
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
    tmp_dir = Path(tempfile.mkdtemp())

    # Determine piper binary
    piper_cmd = voice_model_path if (voice_model_path and
                                     os.path.isfile(voice_model_path) and
                                     voice_model_path.endswith(".onnx")) else None
    model_arg = piper_cmd or "en_US-lessac-medium"

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
        return success
    except Exception as e:
        print(f"[synthesize_voice] ffmpeg: {e}")
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
                for f in os.listdir(output_dir):
                    if f.startswith("source.") and not f.endswith(".part"):
                        full = os.path.join(output_dir, f)
                        if os.path.getsize(full) > 10_000:   # at least 10KB
                            return full
            else:
                print(f"[download_video] fmt='{fmt}' failed: {result.stderr[:200]}")
        except Exception as e:
            print(f"[download_video] {e}")

    return ""


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
        if voice is not None:
            final = final.with_audio(voice)
        elif original_audio is not None:
            final = final.with_audio(original_audio)

        # ── Write output ──────────────────────────────────────────────────
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            logger=None,
        )
        final.close()
        source.close()
        if voice:
            voice.close()

        return os.path.exists(output_path) and os.path.getsize(output_path) > 10_000

    except ImportError as e:
        print(f"[compose_video] Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"[compose_video] Error: {e}")
        import traceback; traceback.print_exc()
        return False


# ─────────────────────────────────────────────
#  STEP 6: Upload to YouTube
# ─────────────────────────────────────────────
def upload_to_youtube(video_path: str, title: str,
                      description: str = "", privacy: str = "public") -> str:
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        if not TOKEN_PATH.exists():
            return "ERROR: Not authenticated. Run OAuth flow first."

        creds   = Credentials.from_authorized_user_file(
            str(TOKEN_PATH),
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        youtube = build("youtube", "v3", credentials=creds)
        body    = {
            "snippet": {
                "title":       title[:100],
                "description": description,
                "tags":        ["reaction", "viral", "commentary"],
                "categoryId":  "22",
            },
            "status": {"privacyStatus": privacy},
        }
        media    = MediaFileUpload(video_path, mimetype="video/mp4",
                                   resumable=True, chunksize=1024 * 1024)
        request  = youtube.videos().insert(part="snippet,status",
                                           body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        return f"https://youtu.be/{response.get('id','')}"
    except Exception as e:
        return f"ERROR: {e}"


# ─────────────────────────────────────────────
#  OAUTH
# ─────────────────────────────────────────────
def run_oauth_flow(client_secrets_path: str) -> bool:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow  = InstalledAppFlow.from_client_secrets_file(
            client_secrets_path,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
        return True
    except Exception as e:
        print(f"[run_oauth_flow] {e}")
        return False
