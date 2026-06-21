"""
REACTION STUDIO — Video Filters Engine
Applies visual filters/effects to moviepy VideoClips.
All filters work on CPU — no GPU required.
Targets moviepy >= 2.0 (uses image_transform / transform, not fl_image / fl).
"""

import numpy as np
from PIL import Image, ImageEnhance

# ─────────────────────────────────────────────
#  Filter registry
# ─────────────────────────────────────────────
FILTERS = {
    "None":          None,
    "Dramatic":      "dramatic",
    "VHS Glitch":    "vhs",
    "Warm Sunset":   "warm",
    "Cold Blue":     "cold",
    "Black & White": "bw",
    "High Contrast": "contrast",
    "Vignette":      "vignette",
    "Oversaturated": "saturate",
    "Film Grain":    "grain",
}

FILTER_DESCRIPTIONS = {
    "None":          "No filter applied",
    "Dramatic":      "Boosted contrast + slight desaturation — cinematic look",
    "VHS Glitch":    "Horizontal scanlines + colour offset — retro chaos",
    "Warm Sunset":   "Warm orange tones — chill reaction vibe",
    "Cold Blue":     "Cool blue tones — midnight mood",
    "Black & White": "Full greyscale — serious/analytical vibe",
    "High Contrast": "Crushed blacks + blown highlights",
    "Vignette":      "Dark edges, bright center — focus effect",
    "Oversaturated": "Punchy, hyper-vivid colours",
    "Film Grain":    "Subtle noise overlay — indie/documentary feel",
}


def _u8(frame):
    """Safely cast any frame dtype to uint8 — moviepy 2.x ColorClip returns int64."""
    import numpy as _np
    return _np.asarray(frame, dtype=_np.uint8)


# ─────────────────────────────────────────────
#  Per-frame processors  (frame: np.ndarray HxWxC uint8)
# ─────────────────────────────────────────────
def _apply_dramatic(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    img = Image.fromarray(frame)
    img = ImageEnhance.Contrast(img).enhance(1.6)
    img = ImageEnhance.Color(img).enhance(0.75)
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    return np.array(img)


def _apply_vhs(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    img = np.array(frame, dtype=np.float32)
    h, w = img.shape[:2]
    img[::2, :, :] *= 0.75                                   # scanlines
    shift = max(1, w // 200)
    img[:, :, 0] = np.roll(img[:, :, 0], shift, axis=1)     # R shift right
    img[:, :, 2] = np.roll(img[:, :, 2], -shift, axis=1)    # B shift left
    img[:, :, 1] = np.clip(img[:, :, 1] * 1.05, 0, 255)     # green tint
    return np.clip(img, 0, 255).astype(np.uint8)


def _apply_warm(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    img = np.array(frame, dtype=np.float32)
    img[:, :, 0] = np.clip(img[:, :, 0] * 1.15, 0, 255)
    img[:, :, 1] = np.clip(img[:, :, 1] * 1.05, 0, 255)
    img[:, :, 2] = np.clip(img[:, :, 2] * 0.85, 0, 255)
    return img.astype(np.uint8)


def _apply_cold(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    img = np.array(frame, dtype=np.float32)
    img[:, :, 0] = np.clip(img[:, :, 0] * 0.85, 0, 255)
    img[:, :, 2] = np.clip(img[:, :, 2] * 1.20, 0, 255)
    return img.astype(np.uint8)


def _apply_bw(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    return np.array(Image.fromarray(frame).convert("L").convert("RGB"))


def _apply_contrast(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    img = np.array(frame, dtype=np.float32)
    img = (img - 50) * 1.4 + 50
    return np.clip(img, 0, 255).astype(np.uint8)


def _apply_vignette(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    h, w = frame.shape[:2]
    cx, cy = w / 2, h / 2
    y_idx, x_idx = np.ogrid[:h, :w]
    dist = np.sqrt(((x_idx - cx) / max(cx, 1)) ** 2 + ((y_idx - cy) / max(cy, 1)) ** 2)
    mask = np.clip(1.0 - dist * 0.7, 0.3, 1.0)[:, :, np.newaxis]
    return np.clip(frame * mask, 0, 255).astype(np.uint8)


def _apply_saturate(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    return np.array(ImageEnhance.Color(Image.fromarray(frame)).enhance(2.2))


def _apply_grain(frame: np.ndarray) -> np.ndarray:
    frame = _u8(frame)
    noise = np.random.randint(-18, 18, frame.shape, dtype=np.int16)
    return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)


_FILTER_FN = {
    "dramatic": _apply_dramatic,
    "vhs":      _apply_vhs,
    "warm":     _apply_warm,
    "cold":     _apply_cold,
    "bw":       _apply_bw,
    "contrast": _apply_contrast,
    "vignette": _apply_vignette,
    "saturate": _apply_saturate,
    "grain":    _apply_grain,
}


# ─────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────
def apply_filter(clip, filter_name: str):
    """
    Apply a named filter to a moviepy 2.x VideoClip.
    Uses image_transform() — the moviepy 2.x replacement for fl_image().
    """
    key = FILTERS.get(filter_name)
    if key is None:
        return clip
    fn = _FILTER_FN.get(key)
    if fn is None:
        return clip
    return clip.image_transform(fn)


def apply_reaction_cam_filter(clip, filter_name: str):
    return apply_filter(clip, filter_name)


def list_filters() -> list:
    return list(FILTERS.keys())


def filter_description(filter_name: str) -> str:
    return FILTER_DESCRIPTIONS.get(filter_name, "")


# ─────────────────────────────────────────────
#  Crashout zoom / shake  (moviepy 2.x: transform)
# ─────────────────────────────────────────────
def apply_crashout_zoom(clip, start: float, duration: float = 0.4,
                        zoom_factor: float = 1.15):
    """
    Quick zoom-punch at `start` seconds.
    moviepy 2.x: uses clip.transform(func) where func(get_frame, t) -> frame.
    """
    w, h = clip.size

    def zoom_frame(get_frame, t):
        frame = _u8(get_frame(t))
        if start <= t <= start + duration:
            progress = (t - start) / max(duration, 1e-6)
            z = 1.0 + 0.15 * np.sin(np.pi * progress)
            new_w, new_h = int(w * z), int(h * z)
            img = Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS)
            x0 = (new_w - w) // 2
            y0 = (new_h - h) // 2
            return np.array(img.crop((x0, y0, x0 + w, y0 + h)))
        return frame

    return clip.transform(zoom_frame)


def apply_shake(clip, start: float, duration: float = 0.6, intensity: int = 8):
    """
    Shake effect at `start` seconds.
    moviepy 2.x: uses clip.transform().
    """
    import random as _r
    w, h = clip.size

    def shake_frame(get_frame, t):
        frame = _u8(get_frame(t))
        if start <= t <= start + duration:
            dx = _r.randint(-intensity, intensity)
            dy = _r.randint(-intensity, intensity)
            img = Image.fromarray(frame)
            img = img.transform(img.size, Image.AFFINE, (1, 0, dx, 0, 1, dy))
            return np.array(img)
        return frame

    return clip.transform(shake_frame)
