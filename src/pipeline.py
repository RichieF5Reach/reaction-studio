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
    search_query = f"ytsearch5:{niche} viral 2026"
    cmd = [
        "yt-dlp", "--dump-json", "--no-download",
        "--match-filter", f"duration < {max_duration_sec}",
        search_query,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        lines = [l for l in result.stdout.strip().splitlines() if l.startswith("{")]
        if lines:
            data = json.loads(lines[0])
            return {
                "url":       data.get("webpage_url", ""),
                "title":     data.get("title", "Unknown"),
                "duration":  data.get("duration", 0),
                "thumbnail": data.get("thumbnail", ""),
                "uploader":  data.get("uploader", ""),
            }
    except Exception as e:
        print(f"[find_trending_video] {e}")
    return {"url": "", "title": "Not found", "duration": 0, "thumbnail": "", "uploader": ""}


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
            return r.json().get("response", "")
    except Exception as e:
        print(f"[generate_script] Ollama error: {e}")

    return "\n".join([
        f"[0:00] okay chat we're watching this — {video_title}",
        "[0:30] wait what [CRASHOUT]",
        "[1:00] nah bro said that with his whole chest [PAUSE]",
        "[2:00] I cannot believe this is real",
        "[3:00] WE ARE SO BACK [CRASHOUT]",
    ])


# ─────────────────────────────────────────────
#  STEP 3: Text-to-Speech via Piper
# ─────────────────────────────────────────────
def synthesize_voice(script: str, voice_model_path: str, output_path: str) -> bool:
    lines = [
        l.split("]")[-1].strip()
        for l in script.splitlines()
        if l.strip() and "[CRASHOUT]" not in l and "[PAUSE]" not in l
    ]
    segment_files = []
    tmp_dir = Path(tempfile.mkdtemp())

    for i, line in enumerate(lines[:60]):
        seg_path = tmp_dir / f"seg_{i:03d}.wav"
        cmd = [
            "piper",
            "--model",       voice_model_path or "en_US-lessac-medium",
            "--output-file", str(seg_path),
        ]
        try:
            subprocess.run(cmd, input=line, capture_output=True,
                           text=True, timeout=30)
            if seg_path.exists():
                segment_files.append(str(seg_path))
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
        return result.returncode == 0
    except Exception as e:
        print(f"[synthesize_voice] ffmpeg: {e}")
        return False


# ─────────────────────────────────────────────
#  STEP 4: Download source video
# ─────────────────────────────────────────────
def download_video(url: str, output_dir: str) -> str:
    output_template = os.path.join(output_dir, "source.%(ext)s")
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url,
    ]
    try:
        subprocess.run(cmd, timeout=600, check=True)
        for f in os.listdir(output_dir):
            if f.startswith("source."):
                return os.path.join(output_dir, f)
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
        voice  = AudioFileClip(voice_audio) if os.path.exists(voice_audio) else None

        # Apply video filter
        source = apply_filter(source, video_filter)

        # Parse crashout timestamps from script
        crashout_times = []
        for line in script.splitlines():
            if "[CRASHOUT]" in line:
                m = re.match(r"\[(\d+):(\d+)\]", line.strip())
                if m:
                    t = int(m.group(1)) * 60 + int(m.group(2))
                    crashout_times.append(t)

        # Apply crashout zoom + shake (moviepy 2.x: transform)
        if crashout:
            for t in crashout_times[:8]:
                if t < source.duration - 1:
                    source = apply_crashout_zoom(source, start=float(t),
                                                 duration=0.35, zoom_factor=1.15)
                    source = apply_shake(source, start=float(t),
                                         duration=0.5, intensity=6)

        # Generate captions
        caption_entries = []
        srt_path = output_path.replace(".mp4", ".srt")

        if caption_mode == "Auto":
            if voice_audio and os.path.exists(voice_audio):
                caption_entries = transcribe_with_whisper(voice_audio)
            if not caption_entries:
                caption_entries = captions_from_script(script)
        elif caption_mode == "Script":
            caption_entries = captions_from_script(script)

        # Burn captions (moviepy 2.x: with_start/with_duration/with_position)
        if caption_entries:
            export_srt(caption_entries, srt_path)
            source = burn_captions(source, caption_entries, caption_style)

        # Crashout text pop-ups
        extra_clips = [source]
        if crashout:
            for t in crashout_times[:5]:
                if t < source.duration - 3:
                    # moviepy 2.x TextClip API
                    txt = (
                        TextClip(
                            text=random.choice(CRASHOUT_LINES_SHORT),
                            font_size=52,
                            color="yellow",
                            stroke_color="black",
                            stroke_width=4,
                            method="caption",
                            size=(int(source.w * 0.8), None),
                            text_align="center",
                        )
                        .with_position(("center", 0.12), relative=True)
                        .with_start(float(t))
                        .with_duration(1.8)
                    )
                    extra_clips.append(txt)

        final = CompositeVideoClip(extra_clips)
        if voice:
            final = final.with_audio(voice)    # moviepy 2.x: with_audio not set_audio

        final.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            logger=None,
        )
        return True

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
