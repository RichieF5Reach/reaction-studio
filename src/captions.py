"""
REACTION STUDIO — Auto Caption Engine
Generates timed subtitles from voice audio using whisper (local, no API).
Falls back to script-derived captions if whisper is unavailable.
Targets moviepy >= 2.0.
"""

from typing import List, Tuple
import os
import re
import subprocess
import tempfile
from pathlib import Path


# ─────────────────────────────────────────────
#  SRT helpers
# ─────────────────────────────────────────────
def _seconds_to_srt_time(s: float) -> str:
    h   = int(s // 3600)
    m   = int((s % 3600) // 60)
    sec = int(s % 60)
    ms  = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _build_srt(entries: List[Tuple[float, float, str]]) -> str:
    lines = []
    for i, (start, end, text) in enumerate(entries, 1):
        lines.append(str(i))
        lines.append(f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}")
        lines.append(text.strip())
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  METHOD A: whisper transcription
# ─────────────────────────────────────────────
def transcribe_with_whisper(audio_path: str,
                            whisper_bin: str = "whisper",
                            model: str = "base") -> List[Tuple[float, float, str]]:
    """
    Run local whisper on voice audio.
    Returns [] safely if audio_path is invalid or whisper is not installed.
    """
    # Guard: skip if audio path is empty or file doesn't exist
    if not audio_path or not os.path.exists(audio_path):
        return []
    if os.path.getsize(audio_path) == 0:
        return []

    tmp_dir  = Path(tempfile.mkdtemp())
    out_base = str(tmp_dir / "out")

    # Try whisper.cpp binary
    cmd_cpp = [
        whisper_bin, "-m", f"models/ggml-{model}.bin",
        "-f", audio_path, "--output-srt", "-of", out_base,
    ]
    try:
        result = subprocess.run(cmd_cpp, capture_output=True, timeout=300)
        srt_path = out_base + ".srt"
        if result.returncode == 0 and os.path.exists(srt_path):
            return _parse_srt_file(srt_path)
    except Exception:
        pass

    # Try openai-whisper Python package
    try:
        import whisper as ow
        mdl    = ow.load_model(model)
        result = mdl.transcribe(audio_path, word_timestamps=False)
        return [
            (seg["start"], seg["end"], seg["text"])
            for seg in result.get("segments", [])
        ]
    except Exception as e:
        print(f"[transcribe_with_whisper] whisper unavailable: {e}")

    return []


def _parse_srt_file(srt_path: str) -> List[Tuple[float, float, str]]:
    entries = []
    try:
        text   = Path(srt_path).read_text(encoding="utf-8")
        blocks = re.split(r"\n\n+", text.strip())
        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
            ts_match = re.match(
                r"(\d+:\d+:\d+[,\.]\d+)\s*-->\s*(\d+:\d+:\d+[,\.]\d+)", lines[1])
            if not ts_match:
                continue
            start = _srt_time_to_seconds(ts_match.group(1))
            end   = _srt_time_to_seconds(ts_match.group(2))
            entries.append((start, end, " ".join(lines[2:])))
    except Exception as e:
        print(f"[_parse_srt_file] {e}")
    return entries


def _srt_time_to_seconds(ts: str) -> float:
    ts    = ts.replace(",", ".")
    parts = ts.split(":")
    try:
        if len(parts) == 3:          # HH:MM:SS.mmm (normal SRT)
            h, m, sf = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + sf
        elif len(parts) == 2:        # MM:SS (truncated)
            m, sf = int(parts[0]), float(parts[1])
            return m * 60 + sf
        elif len(parts) == 1:        # bare seconds
            return float(parts[0])
        else:
            print(f"[_srt_time_to_seconds] unexpected format: {ts!r}")
            return 0.0
    except (ValueError, IndexError) as e:
        print(f"[_srt_time_to_seconds] parse error for {ts!r}: {e}")
        return 0.0


# ─────────────────────────────────────────────
#  METHOD B: Script-derived captions (fallback)
# ─────────────────────────────────────────────
def captions_from_script(script: str,
                         words_per_second: float = 2.8) -> List[Tuple[float, float, str]]:
    """
    Build timed captions from reaction script [MM:SS] markers.
    """
    entries = []
    lines = [
        l for l in script.splitlines()
        if l.strip() and "[CRASHOUT]" not in l and "[PAUSE]" not in l
    ]
    for line in lines:
        m = re.match(r"\[(\d+):(\d+)\]\s*(.*)", line.strip())
        if not m:
            continue
        mins, secs, text = m.groups()
        start    = int(mins) * 60 + int(secs)
        words    = text.split()
        if not words:
            continue
        duration = max(1.5, len(words) / words_per_second)
        end      = start + duration
        chunk_size = 8
        for j in range(0, len(words), chunk_size):
            chunk   = " ".join(words[j:j + chunk_size])
            frac_s  = j / max(len(words), 1)
            frac_e  = (j + chunk_size) / max(len(words), 1)
            entries.append((start + frac_s * duration,
                            min(start + frac_e * duration, end),
                            chunk))
    return entries


# ─────────────────────────────────────────────
#  CAPTION STYLES
# ─────────────────────────────────────────────
CAPTION_STYLES = {
    "Classic White": {
        "color":        "white",
        "stroke_color": "black",
        "stroke_width": 2,
        "font_size":    40,
        "bg_color":     None,
        "position":     ("center", 0.85),
    },
    "Bold Yellow": {
        "color":        "yellow",
        "stroke_color": "black",
        "stroke_width": 3,
        "font_size":    44,
        "bg_color":     None,
        "position":     ("center", 0.85),
    },
    "Black Bar": {
        "color":        "white",
        "stroke_color": "black",
        "stroke_width": 1,
        "font_size":    36,
        "bg_color":     "black",
        "position":     ("center", 0.88),
    },
    "Meme Caps": {
        "color":        "white",
        "stroke_color": "black",
        "stroke_width": 4,
        "font_size":    52,
        "bg_color":     None,
        "position":     ("center", 0.80),
    },
    "Subtle Gray": {
        "color":        "#dddddd",
        "stroke_color": "#333333",
        "stroke_width": 1,
        "font_size":    32,
        "bg_color":     None,
        "position":     ("center", 0.90),
    },
}


# ─────────────────────────────────────────────
#  BURN captions onto clip  (moviepy 2.x API)
# ─────────────────────────────────────────────
def burn_captions(video_clip, entries: List[Tuple[float, float, str]],
                  style_name: str = "Bold Yellow"):
    """
    Overlay caption TextClips onto a moviepy 2.x VideoClip.
    Uses method="label" (Pillow-based) — works without ImageMagick.
    """
    from moviepy import TextClip, CompositeVideoClip

    style = CAPTION_STYLES.get(style_name, CAPTION_STYLES["Bold Yellow"])
    clips = [video_clip]
    W     = video_clip.w

    for start, end, text in entries:
        if start >= video_clip.duration:
            continue
        end = min(end, video_clip.duration)
        dur = max(end - start, 0.1)
        if not text.strip():
            continue

        try:
            kwargs = dict(
                text=text,
                font_size=style["font_size"],
                color=style["color"],
                stroke_color=style["stroke_color"],
                stroke_width=style["stroke_width"],
                method="label",          # Pillow-based — no ImageMagick needed
                size=(int(W * 0.9), None),
                text_align="center",
            )
            if style.get("bg_color"):
                kwargs["bg_color"] = style["bg_color"]

            txt_clip = (
                TextClip(**kwargs)
                .with_position(style["position"], relative=True)
                .with_start(start)
                .with_duration(dur)
            )
            clips.append(txt_clip)
        except Exception as e:
            print(f"[burn_captions] Skipping caption '{text[:30]}': {e}")
            continue

    return CompositeVideoClip(clips)


# ─────────────────────────────────────────────
#  EXPORT .srt
# ─────────────────────────────────────────────
def export_srt(entries: List[Tuple[float, float, str]], output_path: str) -> bool:
    try:
        Path(output_path).write_text(_build_srt(entries), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[export_srt] {e}")
        return False
