"""
REACTION STUDIO - Main Application
Reaction video generator with local AI, TTS, auto-captions, filters, and YouTube upload
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import subprocess
import sys
import os
import time
import random

# ── Ensure src/ is on sys.path so pipeline/captions/filters import correctly ──
import sys as _sys, os as _os
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
BG       = "#0f0f0f"
BG2      = "#1a1a1a"
BG3      = "#222222"
ACCENT   = "#7c3aed"
ACCENT2  = "#a855f7"
TEXT     = "#f5f5f5"
TEXT_DIM = "#888888"
GREEN    = "#22c55e"
RED      = "#ef4444"
YELLOW   = "#eab308"
CYAN     = "#22d3ee"
BORDER   = "#2a2a2a"

FONT_BIG   = ("Segoe UI", 22, "bold")
FONT_MED   = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_CODE  = ("Consolas", 9)

CRASHOUT_LINES = [
    "bro is NOT moving different 💀",
    "WAIT WAIT WAIT hold on—",
    "no way this actually happened",
    "I'm cooked. I'm actually cooked.",
    "chat we need to talk about this",
    "okay but WHY though",
    "this man really said that with his whole chest",
    "I literally cannot 😭",
    "the AUDACITY",
    "plot twist nobody asked for",
    "we're so back / it's so over (simultaneously)",
    "bro thought he ate 💀",
]

NICHES = [
    "Gaming Fails & Clips",
    "Tech Controversies",
    "Internet Drama",
    "Sports Highlights",
    "Music Reactions",
    "Viral Moments",
    "Podcast Clips",
    "Finance / Crypto News",
]

DEPENDENCIES = [
    ("yt-dlp",          "pip install yt-dlp"),
    ("moviepy",         "pip install moviepy"),
    ("piper-tts",       "pip install piper-tts"),
    ("openai-whisper",  "pip install openai-whisper"),
    ("ollama (local)",  "ollama pull llama3"),
    ("ffmpeg",          "system package"),
    ("google-auth",     "pip install google-auth google-auth-oauthlib google-api-python-client"),
    ("Pillow",          "pip install Pillow"),
    ("requests",        "pip install requests"),
]

# Keep in sync with filters.py FILTERS dict
FILTER_OPTIONS = [
    "None",
    "Dramatic",
    "VHS Glitch",
    "Warm Sunset",
    "Cold Blue",
    "Black & White",
    "High Contrast",
    "Vignette",
    "Oversaturated",
    "Film Grain",
]

FILTER_DESCRIPTIONS = {
    "None":          "No filter",
    "Dramatic":      "Boosted contrast + slight desaturation",
    "VHS Glitch":    "Scanlines + colour channel offset",
    "Warm Sunset":   "Warm orange tones",
    "Cold Blue":     "Cool blue tones",
    "Black & White": "Full greyscale",
    "High Contrast": "Crushed blacks + blown highlights",
    "Vignette":      "Dark edges, bright center",
    "Oversaturated": "Hyper-vivid colours",
    "Film Grain":    "Subtle noise overlay",
}

CAPTION_STYLES = [
    "Bold Yellow",
    "Classic White",
    "Black Bar",
    "Meme Caps",
    "Subtle Gray",
]

CAPTION_MODES = [
    ("Auto (Whisper)",   "Auto"),
    ("From Script",      "Script"),
    ("Off",              "Off"),
]


# ═══════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════
class ReactionStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reaction Studio  ·  v1.0")
        self.geometry("980x680")
        self.resizable(True, True)
        self.configure(bg=BG)

        self.current_page     = None
        self.setup_done       = tk.BooleanVar(value=False)
        self.niche_var        = tk.StringVar(value=NICHES[0])
        self.voice_path       = tk.StringVar(value="")
        self.yt_auth_done     = tk.BooleanVar(value=False)
        self.video_filter_var = tk.StringVar(value="None")
        self.react_filter_var = tk.StringVar(value="None")
        self.caption_mode_var = tk.StringVar(value="Auto")
        self.caption_style_var= tk.StringVar(value="Bold Yellow")
        self.log_lines        = []

        try:
            self._style()
            self._build_nav()
            self._build_pages()
            self.show_page("setup")
            self._tick_crashout()
        except Exception as _e:
            import traceback as _tb
            _msg = _tb.format_exc()
            _log = os.path.join(os.path.expanduser("~"), "Desktop", "ReactionStudio_error.txt")
            try:
                with open(_log, "w") as _f:
                    _f.write(_msg)
            except Exception:
                pass
            messagebox.showerror(
                "Startup Error",
                f"Reaction Studio failed to initialise:\n\n{str(_e)}\n\n"
                f"Full traceback saved to:\n{_log}"
            )
            raise

    # ── thread-safe GUI helper ────────────────
    def _ui(self, fn):
        self.after(0, fn)

    # ── styling ──────────────────────────────
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame",       background=BG)
        s.configure("TLabel",       background=BG, foreground=TEXT, font=FONT_MED)
        s.configure("TButton",      background=ACCENT, foreground=TEXT,
                    font=("Segoe UI", 11, "bold"), borderwidth=0, focusthickness=0)
        s.map("TButton",
              background=[("active", ACCENT2), ("pressed", "#6d28d9")])
        s.configure("TProgressbar", troughcolor=BG2, background=ACCENT, thickness=6)
        s.configure("Card.TFrame",  background=BG2)
        s.configure("TCombobox",    background=BG2, foreground=TEXT,
                    fieldbackground=BG2, selectbackground=ACCENT,
                    selectforeground=TEXT)
        s.map("TCombobox",
              fieldbackground=[("readonly", BG2)],
              foreground=[("readonly", TEXT)])

    # ── sidebar nav ──────────────────────────
    def _build_nav(self):
        self.nav = tk.Frame(self, bg=BG2, width=210)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        tk.Label(self.nav, text="⚡ REACTION\nSTUDIO",
                 bg=BG2, fg=ACCENT2,
                 font=("Segoe UI", 14, "bold"),
                 justify="center").pack(pady=(24, 8))

        tk.Frame(self.nav, bg=BORDER, height=1).pack(fill="x", padx=16, pady=8)

        self.nav_buttons = {}
        pages = [
            ("setup",    "⚙️  Setup"),
            ("niche",    "🎯  Niche"),
            ("voice",    "🎙️  Voice"),
            ("effects",  "🎨  Filters & Captions"),
            ("generate", "🎬  Generate"),
            ("upload",   "🚀  Upload"),
            ("log",      "📋  Log"),
        ]
        for key, label in pages:
            btn = tk.Button(self.nav, text=label, bg=BG2, fg=TEXT_DIM,
                            font=("Segoe UI", 11), anchor="w",
                            bd=0, relief="flat", padx=20, pady=8,
                            activebackground=BG, activeforeground=TEXT,
                            cursor="hand2",
                            command=lambda k=key: self.show_page(k))
            btn.pack(fill="x")
            self.nav_buttons[key] = btn

        tk.Frame(self.nav, bg=BORDER, height=1).pack(fill="x", padx=16, pady=8)

        self.crashout_label = tk.Label(self.nav, text="", bg=BG2, fg=ACCENT,
                                       font=("Segoe UI", 8, "italic"),
                                       wraplength=190, justify="center")
        self.crashout_label.pack(padx=12, pady=8)

    # ── pages container ──────────────────────
    def _build_pages(self):
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(side="right", fill="both", expand=True)

        self.pages = {}
        self.pages["setup"]    = self._page_setup()
        self.pages["niche"]    = self._page_niche()
        self.pages["voice"]    = self._page_voice()
        self.pages["effects"]  = self._page_effects()
        self.pages["generate"] = self._page_generate()
        self.pages["upload"]   = self._page_upload()
        self.pages["log"]      = self._page_log()

    def show_page(self, key):
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.nav_buttons[self.current_page].config(bg=BG2, fg=TEXT_DIM)
        self.current_page = key
        self.pages[key].pack(fill="both", expand=True)
        self.nav_buttons[key].config(bg=BG, fg=TEXT)

    def _tick_crashout(self):
        line = random.choice(CRASHOUT_LINES)
        self.crashout_label.config(text=f'"{line}"')
        self.after(4500, self._tick_crashout)

    # ════════════════════════════════════════
    #  PAGE: SETUP
    # ════════════════════════════════════════
    def _page_setup(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="System Setup", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))
        tk.Label(frame, text="Install required dependencies to run Reaction Studio locally.",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", padx=32, pady=(0, 16))

        dep_frame = tk.Frame(frame, bg=BG2)
        dep_frame.pack(fill="x", padx=32, pady=4)

        self.dep_labels = {}
        for name, cmd in DEPENDENCIES:
            row = tk.Frame(dep_frame, bg=BG2)
            row.pack(fill="x", padx=16, pady=3)
            dot = tk.Label(row, text="○", bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 13))
            dot.pack(side="left")
            tk.Label(row, text=f"  {name}", bg=BG2, fg=TEXT,
                     font=FONT_MED, width=22, anchor="w").pack(side="left")
            tk.Label(row, text=cmd, bg=BG2, fg=TEXT_DIM, font=FONT_CODE).pack(side="left")
            self.dep_labels[name] = dot

        self.setup_progress = ttk.Progressbar(frame, length=580, mode="determinate")
        self.setup_progress.pack(padx=32, pady=14)

        self.setup_status = tk.Label(frame, text="Ready to install.",
                                     bg=BG, fg=TEXT_DIM, font=FONT_SMALL)
        self.setup_status.pack(anchor="w", padx=32)

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(anchor="w", padx=32, pady=16)
        ttk.Button(btn_row, text="  ▶  Install Everything",
                   command=self._run_setup).pack(side="left", ipadx=12, ipady=6)
        ttk.Button(btn_row, text="  ✓  Skip (already installed)",
                   command=lambda: [self.setup_done.set(True),
                                    self._mark_all_deps_ok(),
                                    self.show_page("niche")]
                   ).pack(side="left", padx=12, ipadx=12, ipady=6)

        return frame

    def _mark_all_deps_ok(self):
        for name, _ in DEPENDENCIES:
            self.dep_labels[name].config(text="●", fg=GREEN)
        self.setup_progress["value"] = 100
        self.setup_status.config(text="All dependencies ready ✓", fg=GREEN)

    def _run_setup(self):
        threading.Thread(target=self._setup_worker, daemon=True).start()

    def _setup_worker(self):
        # FIX: keyed dict instead of index-based list — safe regardless of order
        pip_deps = {
            "yt-dlp":          "yt-dlp",
            "moviepy":         "moviepy",
            "piper-tts":       "piper-tts",
            "openai-whisper":  "openai-whisper",
            "google-auth":     "google-auth google-auth-oauthlib google-api-python-client",
            "Pillow":          "Pillow",
            "requests":        "requests",
        }
        total = len(DEPENDENCIES)

        for i, (dep_name, _) in enumerate(DEPENDENCIES):
            self._ui(lambda t=dep_name: self.setup_status.config(
                text=f"Installing {t}..."))
            time.sleep(0.3)

            if dep_name == "ollama (local)":
                ok = self._check_ollama()
            elif dep_name == "ffmpeg":
                ok = self._check_ffmpeg()
            else:
                pkg = pip_deps.get(dep_name, dep_name)
                try:
                    # Large packages (piper-tts, openai-whisper) can be 500MB+
                    # Use 600s timeout so slow connections don't false-fail
                    _big_pkgs = {"piper-tts", "openai-whisper", "moviepy"}
                    _timeout  = 600 if any(p in pkg for p in _big_pkgs) else 180
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install"] + pkg.split() + ["-q"],
                        capture_output=True, timeout=_timeout)
                    ok = result.returncode == 0
                except Exception:
                    ok = False

            color  = GREEN if ok else RED
            symbol = "●"   if ok else "✗"
            pct    = int((i + 1) / total * 100)
            self._ui(lambda s=symbol, c=color, d=dep_name, p=pct: (
                self.dep_labels[d].config(text=s, fg=c),
                self.setup_progress.config(value=p),
            ))

        self._ui(lambda: (
            self.setup_done.set(True),
            self.setup_status.config(
                text="Setup complete! Head to Niche to continue.", fg=GREEN),
        ))
        self._log("Setup complete.")

    def _check_ollama(self):
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def _check_ffmpeg(self):
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    # ════════════════════════════════════════
    #  PAGE: NICHE
    # ════════════════════════════════════════
    def _page_niche(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="Target Niche", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))
        tk.Label(frame,
                 text="Pick your lane. The AI finds trending videos and writes reactions in that space.",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", padx=32, pady=(0, 20))

        niche_frame = tk.Frame(frame, bg=BG2)
        niche_frame.pack(fill="x", padx=32, pady=4)

        self.niche_btns = {}
        for i, n in enumerate(NICHES):
            row, col = divmod(i, 2)
            btn = tk.Button(niche_frame, text=n, bg=BG2, fg=TEXT_DIM,
                            font=("Segoe UI", 11), bd=1, relief="solid",
                            padx=20, pady=12, cursor="hand2",
                            command=lambda x=n: self._select_niche(x))
            btn.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
            niche_frame.columnconfigure(col, weight=1)
            self.niche_btns[n] = btn

        tk.Label(frame, text="Or type a custom niche:", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=32, pady=(16, 4))

        custom_row = tk.Frame(frame, bg=BG)
        custom_row.pack(anchor="w", padx=32, pady=4)
        self.custom_niche_entry = tk.Entry(custom_row, bg=BG2, fg=TEXT,
                                           insertbackground=TEXT,
                                           font=FONT_MED, width=32, bd=0)
        self.custom_niche_entry.pack(side="left", ipady=8, padx=(0, 8))
        ttk.Button(custom_row, text="Set",
                   command=lambda: self._select_niche(
                       self.custom_niche_entry.get() or self.niche_var.get()
                   )).pack(side="left")

        self.niche_confirm = tk.Label(frame, text="", bg=BG, fg=GREEN, font=FONT_MED)
        self.niche_confirm.pack(anchor="w", padx=32, pady=8)

        ttk.Button(frame, text="Next — Voice Setup",
                   command=lambda: self.show_page("voice")
                   ).pack(anchor="w", padx=32, pady=16, ipadx=12, ipady=6)

        return frame

    def _select_niche(self, niche):
        self.niche_var.set(niche)
        for n, btn in self.niche_btns.items():
            btn.config(bg=ACCENT if n == niche else BG2,
                       fg=TEXT   if n == niche else TEXT_DIM)
        self.niche_confirm.config(text=f"Niche set: {niche}")
        self._log(f"Niche selected: {niche}")

    # ════════════════════════════════════════
    #  PAGE: VOICE
    # ════════════════════════════════════════
    def _page_voice(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="Voice Setup", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))
        tk.Label(frame,
                 text="Record a 30-60s clip of yourself talking. Piper TTS clones your cadence.",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", padx=32, pady=(0, 20))

        pick_row = tk.Frame(frame, bg=BG)
        pick_row.pack(anchor="w", padx=32, pady=4)
        ttk.Button(pick_row, text="Browse Voice Sample (.wav / .mp3)",
                   command=self._pick_voice).pack(side="left", ipadx=10, ipady=6)
        self.voice_label = tk.Label(pick_row, text="  No file selected",
                                    bg=BG, fg=TEXT_DIM, font=FONT_SMALL)
        self.voice_label.pack(side="left", padx=12)

        tk.Label(frame, text="Reaction Energy Level:", bg=BG, fg=TEXT,
                 font=FONT_MED).pack(anchor="w", padx=32, pady=(20, 4))

        self.energy_var = tk.StringVar(value="High")
        energy_frame = tk.Frame(frame, bg=BG)
        energy_frame.pack(anchor="w", padx=32)
        for level in ["Chill", "Mid", "High", "UNHINGED"]:
            tk.Radiobutton(energy_frame, text=level,
                           variable=self.energy_var, value=level,
                           bg=BG, fg=TEXT, selectcolor=ACCENT,
                           activebackground=BG,
                           font=("Segoe UI", 11)).pack(side="left", padx=12)

        tk.Label(frame, text="Crashout Animations:", bg=BG, fg=TEXT,
                 font=FONT_MED).pack(anchor="w", padx=32, pady=(20, 4))
        self.crashout_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame,
                       text="Enable random zoom / shake / text-pop on reaction moments",
                       variable=self.crashout_var,
                       bg=BG, fg=TEXT, selectcolor=ACCENT,
                       activebackground=BG,
                       font=("Segoe UI", 11)).pack(anchor="w", padx=32)

        tk.Label(frame, text="Script Style Hint:", bg=BG, fg=TEXT,
                 font=FONT_MED).pack(anchor="w", padx=32, pady=(20, 4))
        self.style_entry = tk.Text(frame, bg=BG2, fg=TEXT,
                                   insertbackground=TEXT,
                                   font=FONT_MED, height=3, width=60,
                                   bd=0, relief="flat")
        self.style_entry.insert("1.0",
            "Loud, unfiltered, uses slang, calls out BS immediately, "
            "drops quotes mid-reaction, short punchy sentences")
        self.style_entry.pack(anchor="w", padx=32, pady=4)

        ttk.Button(frame, text="Next — Filters & Captions",
                   command=lambda: self.show_page("effects")
                   ).pack(anchor="w", padx=32, pady=20, ipadx=12, ipady=6)

        return frame

    def _pick_voice(self):
        path = filedialog.askopenfilename(
            title="Select Voice Sample",
            filetypes=[("Audio", "*.wav *.mp3 *.ogg *.flac"), ("All", "*.*")])
        if path:
            self.voice_path.set(path)
            self.voice_label.config(text=f"  {os.path.basename(path)}", fg=GREEN)
            self._log(f"Voice sample set: {path}")

    # ════════════════════════════════════════
    #  PAGE: FILTERS & CAPTIONS  (NEW)
    # ════════════════════════════════════════
    def _page_effects(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="Filters & Captions", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))
        tk.Label(frame,
                 text="Choose visual filters for the video and configure auto-caption style.",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", padx=32, pady=(0, 20))

        # ── Video filter ──────────────────────────────────────────────────
        section = self._section(frame, "🎨  Video Filter")

        vf_row = tk.Frame(section, bg=BG2)
        vf_row.pack(fill="x", padx=16, pady=(4, 8))

        tk.Label(vf_row, text="Source video filter:", bg=BG2, fg=TEXT,
                 font=FONT_MED, width=22, anchor="w").pack(side="left")

        self.vf_combo = ttk.Combobox(vf_row, textvariable=self.video_filter_var,
                                     values=FILTER_OPTIONS, state="readonly", width=20)
        self.vf_combo.pack(side="left", padx=8)
        self.vf_combo.bind("<<ComboboxSelected>>", self._on_vf_change)

        self.vf_desc = tk.Label(vf_row, text="No filter", bg=BG2, fg=CYAN,
                                font=FONT_SMALL, width=36, anchor="w")
        self.vf_desc.pack(side="left", padx=8)

        # Reaction cam filter (separate control)
        rf_row = tk.Frame(section, bg=BG2)
        rf_row.pack(fill="x", padx=16, pady=(0, 12))

        tk.Label(rf_row, text="Reaction cam filter:", bg=BG2, fg=TEXT,
                 font=FONT_MED, width=22, anchor="w").pack(side="left")

        self.rf_combo = ttk.Combobox(rf_row, textvariable=self.react_filter_var,
                                     values=FILTER_OPTIONS, state="readonly", width=20)
        self.rf_combo.pack(side="left", padx=8)
        self.rf_combo.bind("<<ComboboxSelected>>", self._on_rf_change)

        self.rf_desc = tk.Label(rf_row, text="No filter", bg=BG2, fg=CYAN,
                                font=FONT_SMALL, width=36, anchor="w")
        self.rf_desc.pack(side="left", padx=8)

        # ── Filter preview swatch grid ─────────────────────────────────────
        tk.Label(frame, text="Quick pick:", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=32, pady=(8, 4))

        swatch_frame = tk.Frame(frame, bg=BG)
        swatch_frame.pack(anchor="w", padx=32, pady=4)

        swatch_colors = {
            "None":          "#444444",
            "Dramatic":      "#1a0a2e",
            "VHS Glitch":    "#003300",
            "Warm Sunset":   "#5c2d00",
            "Cold Blue":     "#001a4d",
            "Black & White": "#303030",
            "High Contrast": "#000000",
            "Vignette":      "#1a1a2e",
            "Oversaturated": "#4a0080",
            "Film Grain":    "#2a2a1a",
        }
        for i, fname in enumerate(FILTER_OPTIONS):
            col = i % 5
            row = i // 5
            color = swatch_colors.get(fname, "#333333")
            cell = tk.Frame(swatch_frame, bg=color, width=90, height=52,
                            cursor="hand2", bd=1, relief="solid")
            cell.grid(row=row, column=col, padx=4, pady=4)
            cell.pack_propagate(False)
            tk.Label(cell, text=fname, bg=color, fg=TEXT,
                     font=("Segoe UI", 8), wraplength=82,
                     justify="center").pack(expand=True)
            cell.bind("<Button-1>",
                      lambda e, f=fname: (
                          self.video_filter_var.set(f),
                          self._on_vf_change(None)))

        # ── Auto Captions ─────────────────────────────────────────────────
        section2 = self._section(frame, "💬  Auto Captions")

        # Caption mode
        mode_row = tk.Frame(section2, bg=BG2)
        mode_row.pack(fill="x", padx=16, pady=(4, 8))

        tk.Label(mode_row, text="Caption mode:", bg=BG2, fg=TEXT,
                 font=FONT_MED, width=16, anchor="w").pack(side="left")

        for label, val in CAPTION_MODES:
            tk.Radiobutton(mode_row, text=label,
                           variable=self.caption_mode_var, value=val,
                           bg=BG2, fg=TEXT, selectcolor=ACCENT,
                           activebackground=BG2,
                           font=("Segoe UI", 11)).pack(side="left", padx=10)

        # Caption style
        style_row = tk.Frame(section2, bg=BG2)
        style_row.pack(fill="x", padx=16, pady=(0, 12))

        tk.Label(style_row, text="Caption style:", bg=BG2, fg=TEXT,
                 font=FONT_MED, width=16, anchor="w").pack(side="left")

        self.cs_combo = ttk.Combobox(style_row, textvariable=self.caption_style_var,
                                     values=CAPTION_STYLES, state="readonly", width=20)
        self.cs_combo.pack(side="left", padx=8)

        # Caption style preview swatches
        tk.Label(frame, text="Caption style preview:", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=32, pady=(8, 4))

        preview_frame = tk.Frame(frame, bg=BG)
        preview_frame.pack(anchor="w", padx=32, pady=(0, 8))

        style_previews = {
            "Bold Yellow":   ("#000000", "yellow",   4, 44),
            "Classic White": ("#000000", "white",    2, 40),
            "Black Bar":     ("#000000", "white",    1, 36),
            "Meme Caps":     ("#000000", "white",    4, 52),
            "Subtle Gray":   ("#111111", "#dddddd",  1, 32),
        }
        for i, sname in enumerate(CAPTION_STYLES):
            bg_c, fg_c, _, fsize = style_previews.get(sname, ("#000", "#fff", 2, 36))
            cell = tk.Frame(preview_frame, bg=bg_c, width=140, height=52,
                            cursor="hand2", bd=1, relief="solid")
            cell.grid(row=0, column=i, padx=4)
            cell.pack_propagate(False)
            tk.Label(cell, text=sname, bg=bg_c, fg=fg_c,
                     font=("Segoe UI", 9, "bold"),
                     wraplength=130, justify="center").pack(expand=True)
            cell.bind("<Button-1>",
                      lambda e, s=sname: (
                          self.caption_style_var.set(s),
                          self.cs_combo.set(s)))

        # Whisper info box
        info = tk.Frame(frame, bg="#1a1a2e", bd=0)
        info.pack(fill="x", padx=32, pady=(8, 4))
        tk.Label(info,
                 text="ℹ️  Auto (Whisper): uses local openai-whisper to transcribe your voice audio "
                      "into timed subtitles. No internet needed. Falls back to Script mode if "
                      "whisper is not installed.",
                 bg="#1a1a2e", fg=CYAN, font=FONT_SMALL,
                 wraplength=680, justify="left").pack(padx=16, pady=10, anchor="w")

        ttk.Button(frame, text="Next — Generate Video",
                   command=lambda: self.show_page("generate")
                   ).pack(anchor="w", padx=32, pady=16, ipadx=12, ipady=6)

        return frame

    def _section(self, parent, title: str) -> tk.Frame:
        """Render a titled card section and return its inner frame."""
        outer = tk.Frame(parent, bg=BG2, bd=0)
        outer.pack(fill="x", padx=32, pady=(0, 8))
        tk.Label(outer, text=title, bg=BG2, fg=ACCENT2,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(10, 4))
        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(0, 4))
        return outer

    def _on_vf_change(self, _event):
        fname = self.video_filter_var.get()
        desc  = FILTER_DESCRIPTIONS.get(fname, "")
        self.vf_desc.config(text=desc)
        self._log(f"Video filter: {fname}")

    def _on_rf_change(self, _event):
        fname = self.react_filter_var.get()
        desc  = FILTER_DESCRIPTIONS.get(fname, "")
        self.rf_desc.config(text=desc)
        self._log(f"Reaction cam filter: {fname}")

    # ════════════════════════════════════════
    #  PAGE: GENERATE
    # ════════════════════════════════════════
    def _page_generate(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="Generate Reaction", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))
        tk.Label(frame,
                 text="Pipeline: Find  →  Script  →  TTS  →  Captions  →  Filter  →  FX  →  Export",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", padx=32, pady=(0, 16))

        # Settings summary row
        self.gen_summary = tk.Label(frame, text="", bg=BG, fg=CYAN, font=FONT_SMALL)
        self.gen_summary.pack(anchor="w", padx=32, pady=(0, 8))

        self.pipeline_frame = tk.Frame(frame, bg=BG2)
        self.pipeline_frame.pack(fill="x", padx=32, pady=4)

        pipeline_steps = [
            ("🔍", "Find trending video",              "find"),
            ("🤖", "Generate reaction script",         "script"),
            ("🎙️", "Synthesize voice (Piper)",          "tts"),
            ("📥", "Download source video",            "captions"),  # step key "captions" kept for compat
            ("🎨", "Apply video filter",               "filter"),
            ("💥", "Add crashout animations",          "fx"),
            ("🎞️", "Export final MP4 + .srt",          "export"),
        ]
        self.step_labels = {}
        for emoji, label, key in pipeline_steps:
            row = tk.Frame(self.pipeline_frame, bg=BG2)
            row.pack(fill="x", padx=16, pady=4)
            status = tk.Label(row, text="○", bg=BG2, fg=TEXT_DIM,
                              font=("Segoe UI", 14), width=2)
            status.pack(side="left")
            tk.Label(row, text=f"  {emoji}  {label}", bg=BG2, fg=TEXT,
                     font=FONT_MED).pack(side="left")
            bar = ttk.Progressbar(row, length=180, mode="determinate")
            bar.pack(side="right", padx=8)
            self.step_labels[key] = (status, bar)

        self.gen_progress = ttk.Progressbar(frame, length=580, mode="determinate")
        self.gen_progress.pack(padx=32, pady=10)

        self.gen_status = tk.Label(frame, text="Ready.", bg=BG, fg=TEXT_DIM, font=FONT_SMALL)
        self.gen_status.pack(anchor="w", padx=32)

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(anchor="w", padx=32, pady=14)
        self.gen_btn = ttk.Button(btn_row, text="  ⚡  Generate Now",
                                  command=self._start_generate)
        self.gen_btn.pack(side="left", ipadx=14, ipady=8)

        self.gen_output_label = tk.Label(frame, text="", bg=BG, fg=GREEN, font=FONT_MED)
        self.gen_output_label.pack(anchor="w", padx=32, pady=4)

        return frame

    def _start_generate(self):
        # Snapshot ALL GUI vars here (main thread) before spawning worker.
        # This is the ONLY safe place to read tkinter widgets.
        niche  = self.niche_var.get()
        voice  = self.voice_path.get()
        energy = self.energy_var.get() if hasattr(self, 'energy_var') else 'High'
        style  = (self.style_entry.get('1.0', 'end').strip()
                  if hasattr(self, 'style_entry') else '')
        crash  = (self.crashout_var.get()
                  if hasattr(self, 'crashout_var') else True)
        vf     = self.video_filter_var.get()
        cs     = self.caption_style_var.get()
        cm     = self.caption_mode_var.get()

        self._gen_settings = {
            'niche': niche, 'voice': voice, 'energy': energy,
            'style': style, 'crashout': crash,
            'vf': vf, 'cs': cs, 'cm': cm,
            'auto_upload':  self.auto_upload_var.get() if hasattr(self, 'auto_upload_var') else False,
            'yt_auth_done': self.yt_auth_done.get()    if hasattr(self, 'yt_auth_done')    else False,
        }

        summary = (f"Niche: {niche}  |  Filter: {vf}  |  "
                   f"Captions: {cm}  |  Style: {cs}")
        self.gen_summary.config(text=summary)

        self.gen_btn.config(state="disabled")
        for key, (status, bar) in self.step_labels.items():
            status.config(text="○", fg=TEXT_DIM)
            bar["value"] = 0
        self.gen_progress["value"] = 0
        self.gen_output_label.config(text="")
        threading.Thread(target=self._generate_worker, daemon=True).start()

    def _generate_worker(self):
        """
        Real pipeline worker — runs every step in order:
          find -> script -> tts -> captions -> filter -> fx -> export
        Updates the step progress bars and status labels via _ui() (thread-safe).
        """
        import importlib, tempfile, os as _os

        try:
            import pipeline as P
        except ImportError as e:
            self._ui(lambda: self.gen_status.config(
                text=f"Import error: {e}", fg=RED))
            self._ui(lambda: self.gen_btn.config(state="normal"))
            return

        steps_order = ["find", "script", "tts", "captions", "filter", "fx", "export"]
        step_names  = {
            "find":     "Finding trending video",
            "script":   "Writing reaction script",
            "tts":      "Synthesizing voice",
            "captions": "Downloading source video",
            "filter":   "Applying video filter",
            "fx":       "Adding crashout FX",
            "export":   "Exporting MP4 + SRT",
        }
        total = len(steps_order)

        def _step_start(key):
            lbl, _ = self.step_labels[key]
            self._ui(lambda l=lbl: l.config(text="▶", fg=YELLOW))

        def _step_progress(key, pct, idx):
            _, bar = self.step_labels[key]
            name = step_names[key]
            self._ui(lambda p=pct, s=name, n=idx, b=bar: (
                b.config(value=p),
                self.gen_status.config(
                    text=f"Step {n+1}/{total}: {s} ({p}%)...", fg=TEXT_DIM),
            ))

        def _step_done(key, overall_pct):
            lbl, _ = self.step_labels[key]
            self._ui(lambda l=lbl, p=overall_pct: (
                l.config(text="●", fg=GREEN),
                self.gen_progress.config(value=p),
            ))

        def _step_error(key, msg):
            lbl, _ = self.step_labels[key]
            self._ui(lambda l=lbl, m=msg: (
                l.config(text="✗", fg=RED),
                self.gen_status.config(text=f"Error: {m[:80]}", fg=RED),
            ))

        # Read pre-snapshotted settings (set on main thread in _start_generate).
        # Never read tkinter widgets directly from a background thread.
        _s       = getattr(self, '_gen_settings', {})
        niche    = _s.get('niche',   'General')
        voice    = _s.get('voice',   '')
        energy   = _s.get('energy',  'High')
        style    = _s.get('style',   '')
        crashout = _s.get('crashout', True)
        vf       = _s.get('vf',      'None')
        cs       = _s.get('cs',      'Bold Yellow')
        cm       = _s.get('cm',      'Auto')

        tmp_dir = tempfile.mkdtemp(prefix="reaction_studio_")
        output_path = _os.path.join(_os.path.expanduser("~"), "Desktop",
                                    "reaction_output.mp4")

        video_info = {}
        script     = ""
        src_video  = ""
        voice_wav  = ""

        # ── STEP 1: find ─────────────────────────────────────────────────
        _step_start("find")
        _step_progress("find", 0, 0)
        try:
            video_info = P.find_trending_video(niche)
            _step_progress("find", 100, 0)
            self._log(f"Found: {video_info.get('title','(unknown)')}")
        except Exception as e:
            _step_error("find", str(e))
            self._log(f"[find] error: {e}")
            video_info = {"title": f"Viral {niche} Moment", "url": ""}
        _step_done("find", int(1/total*100))

        # ── STEP 2: script ───────────────────────────────────────────────
        _step_start("script")
        _step_progress("script", 0, 1)
        try:
            script = P.generate_script(
                video_info.get("title", "viral video"),
                niche, energy, style)
            _step_progress("script", 100, 1)
            self._log(f"Script generated ({len(script)} chars)")
        except Exception as e:
            _step_error("script", str(e))
            self._log(f"[script] error: {e}")
            script = f"[0:00] okay chat we're watching this\n[0:30] wait what [CRASHOUT]\n[1:00] bro no way"
        _step_done("script", int(2/total*100))

        # ── STEP 3: tts ──────────────────────────────────────────────────
        _step_start("tts")
        _step_progress("tts", 0, 2)
        voice_wav = _os.path.join(tmp_dir, "voice.wav")
        try:
            ok_tts = P.synthesize_voice(script, voice, voice_wav)
            if ok_tts:
                _step_progress("tts", 100, 2)
                self._log("Voice synthesized OK")
            else:
                self._log("[tts] piper not available — continuing without voice")
                voice_wav = ""
        except Exception as e:
            self._log(f"[tts] error: {e}")
            voice_wav = ""
        _step_done("tts", int(3/total*100))

        # ── STEP 4: download source video ────────────────────────────────
        # We call it "captions" in the UI but this step downloads the video
        _step_start("captions")
        _step_progress("captions", 0, 3)
        if video_info.get("url"):
            try:
                src_video = P.download_video(video_info["url"], tmp_dir)
                if src_video and src_video.startswith("ERROR:"):
                    # download_video returned a descriptive error
                    self._log(f"[download] failed: {src_video}")
                    _step_error("captions", src_video[7:60])
                    src_video = ""
                else:
                    _step_progress("captions", 100, 3)
                    self._log(f"Video downloaded: {src_video}")
            except Exception as e:
                self._log(f"[download] error: {e}")
                src_video = ""
        else:
            self._log("[download] no URL — skipping download")
        _step_done("captions", int(4/total*100))

        # ── STEP 5: filter + FX label (compose handles all of this) ──────
        _step_start("filter")
        _step_progress("filter", 50, 4)
        _step_done("filter", int(5/total*100))

        _step_start("fx")
        _step_progress("fx", 50, 5)
        _step_done("fx", int(6/total*100))

        # ── STEP 6: compose + export ─────────────────────────────────────
        _step_start("export")
        _step_progress("export", 0, 6)
        self._log("Composing video...")

        compose_ok = False
        if src_video and _os.path.exists(src_video):
            try:
                compose_ok = P.compose_video(
                    source_video=src_video,
                    voice_audio=voice_wav,
                    script=script,
                    crashout=crashout,
                    output_path=output_path,
                    video_filter=vf,
                    caption_style=cs,
                    caption_mode=cm,
                )
                _step_progress("export", 100, 6)
            except Exception as e:
                _step_error("export", str(e))
                self._log(f"[compose] error: {e}")
        else:
            self._log("[compose] no source video — skipping full compose")
            compose_ok = False

        _step_done("export", 100)

        # ── Final ─────────────────────────────────────────────────────────
        srt_path = output_path.replace(".mp4", ".srt")
        if compose_ok:
            output_msg = f"✓ Video: {output_path}\n✓ Captions: {srt_path}"
            self._log("Generation complete!")
        else:
            output_msg = "⚠ Generation finished with warnings — check the log"
            self._log("Generation finished with warnings.")

        self.last_output_path = output_path  # stored for auto-upload

        self._ui(lambda m=output_msg: (
            self.gen_output_label.config(text=m),
            self.gen_status.config(text="Done!", fg=GREEN),
            self.gen_btn.config(state="normal"),
        ))

        # Auto-upload if enabled and auth done
        if _s.get('auto_upload') and _s.get('yt_auth_done') and compose_ok:
            self._log("Auto-upload triggered...")
            threading.Thread(target=self._upload_worker, daemon=True).start()
        else:
            self._ui(lambda: self.after(1600, lambda: self.show_page("upload")))

    # ════════════════════════════════════════
    #  PAGE: UPLOAD
    # ════════════════════════════════════════
    def _page_upload(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="YouTube Upload", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))
        tk.Label(frame,
                 text="Connect once — uploads go live automatically.",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", padx=32, pady=(0, 16))

        auth_frame = tk.Frame(frame, bg=BG2)
        auth_frame.pack(fill="x", padx=32, pady=4)

        self.auth_dot = tk.Label(auth_frame, text="○", bg=BG2, fg=TEXT_DIM,
                                 font=("Segoe UI", 18))
        self.auth_dot.pack(side="left", padx=16, pady=12)
        self.auth_status_lbl = tk.Label(auth_frame, text="Not connected",
                                        bg=BG2, fg=TEXT_DIM, font=FONT_MED)
        self.auth_status_lbl.pack(side="left")
        ttk.Button(auth_frame, text="Connect YouTube",
                   command=self._connect_google
                   ).pack(side="right", padx=12, pady=8, ipadx=8, ipady=4)

        help_frame = tk.Frame(frame, bg=BG3)
        help_frame.pack(fill="x", padx=32, pady=(0, 8))
        tk.Label(help_frame,
                 text=(
                     "i  Requires a free Google API key.\n"
                     "   1. console.cloud.google.com\n"
                     "   2. New project -> Enable 'YouTube Data API v3'\n"
                     "   3. Credentials -> OAuth 2.0 Client ID (Desktop app) -> Download JSON\n"
                     "   4. Save as:  C:\\Users\\YOU\\.reaction_studio\\client_secrets.json"
                 ),
                 bg=BG3, fg=TEXT_DIM, font=("Consolas", 9),
                 justify="left").pack(anchor="w", padx=16, pady=10)

        tk.Label(frame, text="Title Template:", bg=BG, fg=TEXT,
                 font=FONT_MED).pack(anchor="w", padx=32, pady=(12, 4))
        self.title_entry = tk.Entry(frame, bg=BG2, fg=TEXT,
                                    insertbackground=TEXT,
                                    font=FONT_MED, width=52, bd=0)
        self.title_entry.insert(0, "I Reacted to This and Broke (you won't believe this)")
        self.title_entry.pack(anchor="w", padx=32, ipady=8)

        tk.Label(frame, text="Privacy:", bg=BG, fg=TEXT,
                 font=FONT_MED).pack(anchor="w", padx=32, pady=(12, 4))
        self.privacy_var = tk.StringVar(value="public")
        priv_row = tk.Frame(frame, bg=BG)
        priv_row.pack(anchor="w", padx=32)
        for p in ["public", "unlisted", "private"]:
            tk.Radiobutton(priv_row, text=p.capitalize(),
                           variable=self.privacy_var, value=p,
                           bg=BG, fg=TEXT, selectcolor=ACCENT,
                           activebackground=BG,
                           font=("Segoe UI", 11)).pack(side="left", padx=10)

        self.auto_upload_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame,
                       text="Auto-upload every new video as soon as it finishes generating",
                       variable=self.auto_upload_var,
                       bg=BG, fg=TEXT, selectcolor=ACCENT,
                       activebackground=BG,
                       font=("Segoe UI", 11)).pack(anchor="w", padx=32, pady=8)

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(anchor="w", padx=32, pady=12)
        ttk.Button(btn_row, text="  Upload Now",
                   command=self._upload_now
                   ).pack(side="left", ipadx=14, ipady=8)
        ttk.Button(btn_row, text="  Select Different File",
                   command=self._pick_upload_file
                   ).pack(side="left", padx=12, ipadx=10, ipady=8)

        self.upload_status = tk.Label(frame, text="", bg=BG, fg=GREEN, font=FONT_MED)
        self.upload_status.pack(anchor="w", padx=32, pady=8)

        # Restore auth state from saved token on launch
        self.after(500, self._restore_auth_state)

        return frame

    def _restore_auth_state(self):
        """
        Check for a saved token on startup. Runs is_authenticated() in a
        background thread so a token refresh (network call) never blocks the GUI.
        """
        def _check():
            try:
                import pipeline as P
                ok = P.is_authenticated()
            except Exception:
                ok = False
            if ok:
                self._ui(lambda: (
                    self.auth_dot.config(text="●", fg=GREEN),
                    self.auth_status_lbl.config(text="Connected", fg=GREEN),
                    self.yt_auth_done.set(True),
                ))
            # If not ok, leave the default 'Not connected' state as-is
        import threading as _th
        _th.Thread(target=_check, daemon=True).start()

    def _connect_google(self):
        """Run Google OAuth. Falls back to manual code flow if browser redirect fails."""
        import threading as _th

        secrets_path = os.path.join(
            os.path.expanduser("~"), ".reaction_studio", "client_secrets.json")

        if not os.path.exists(secrets_path):
            messagebox.showinfo(
                "Setup Required",
                "To connect YouTube:\n\n"
                "1. Go to console.cloud.google.com\n"
                "2. New project -> Enable 'YouTube Data API v3'\n"
                "3. Credentials -> OAuth 2.0 Client ID (Desktop) -> Download JSON\n"
                "4. Rename to client_secrets.json and save here:\n\n"
                f"   {secrets_path}\n\n"
                "Then click Connect YouTube again.")
            return

        self._ui(lambda: (
            self.auth_dot.config(text="o", fg=YELLOW),
            self.auth_status_lbl.config(text="Connecting...", fg=YELLOW),
        ))
        self._log("Starting Google OAuth flow...")

        def _oauth_thread():
            try:
                import pipeline as P
                ok = P.run_oauth_flow(secrets_path)
                if ok:
                    self._ui(lambda: (
                        self.auth_dot.config(text="●", fg=GREEN),
                        self.auth_status_lbl.config(text="Connected", fg=GREEN),
                        self.yt_auth_done.set(True),
                    ))
                    self._log("Google OAuth complete.")
                else:
                    self._log("Browser redirect failed — offering manual flow...")
                    self._ui(lambda: self._offer_manual_oauth(secrets_path))
            except ValueError as ve:
                # Wrong client type (web vs desktop), bad JSON, etc — show clear dialog
                self._log(f"OAuth setup error: {ve}")
                self._ui(lambda m=str(ve): (
                    self.auth_dot.config(text="x", fg=RED),
                    self.auth_status_lbl.config(text="Setup error — see dialog", fg=RED),
                    messagebox.showerror("YouTube Setup Error", m),
                ))
            except ImportError as ie:
                self._log(f"Missing package: {ie}")
                self._ui(lambda m=str(ie): (
                    self.auth_dot.config(text="x", fg=RED),
                    self.auth_status_lbl.config(text="Missing package", fg=RED),
                    messagebox.showerror("Missing Package", m),
                ))
            except Exception as e:
                self._log(f"OAuth error: {e}")
                self._ui(lambda err=str(e): (
                    self.auth_dot.config(text="x", fg=RED),
                    self.auth_status_lbl.config(text=f"Error: {err[:50]}", fg=RED),
                ))

        _th.Thread(target=_oauth_thread, daemon=True).start()

    def _offer_manual_oauth(self, secrets_path):
        """
        Fallback auth window — uses a local loopback server (port 8765) instead
        of the old OOB flow which Google killed in 2023.
        The user opens the URL in their browser; we wait for the redirect callback.
        """
        try:
            import pipeline as P
            result = P.run_oauth_flow_manual(secrets_path)
        except Exception as e:
            messagebox.showerror("OAuth Error", str(e))
            self._ui(lambda: (
                self.auth_dot.config(text="x", fg=RED),
                self.auth_status_lbl.config(text="Failed", fg=RED),
            ))
            return

        if result.get("status") == "error":
            msg = result.get("message", "Unknown error")
            messagebox.showerror("OAuth Error", msg)
            self._ui(lambda: (
                self.auth_dot.config(text="x", fg=RED),
                self.auth_status_lbl.config(text=msg[:50], fg=RED),
            ))
            return

        # Build the "waiting" window
        auth_url = result.get("url", "")
        win = tk.Toplevel(self)
        win.title("Connect YouTube Account")
        win.configure(bg=BG)
        win.geometry("660x420")
        win.resizable(False, False)

        tk.Label(win, text="Step 1 — Open this URL in your browser:",
                 bg=BG, fg=TEXT, font=FONT_MED).pack(anchor="w", padx=20, pady=(20, 4))

        url_box = tk.Text(win, bg=BG2, fg=ACCENT2, font=("Consolas", 9),
                          height=4, wrap="char", bd=0)
        url_box.insert("1.0", auth_url)
        url_box.config(state="disabled")
        url_box.pack(fill="x", padx=20, pady=4)

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(anchor="w", padx=20, pady=4)
        ttk.Button(btn_row, text="Copy URL",
                   command=lambda: (win.clipboard_clear(),
                                    win.clipboard_append(auth_url))
                   ).pack(side="left", ipadx=8, ipady=4)

        import webbrowser as _wb
        ttk.Button(btn_row, text="Open in Browser",
                   command=lambda: _wb.open(auth_url)
                   ).pack(side="left", padx=8, ipadx=8, ipady=4)

        tk.Label(win,
                 text=(
                     "Step 2 — Sign in with Google and allow access.\n"
                     "You'll be redirected to http://localhost:8765/ — "
                     "this page is served by Reaction Studio on your PC.\n"
                     "The app will connect automatically when you complete the flow."
                 ),
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 10),
                 justify="left", wraplength=620
                 ).pack(anchor="w", padx=20, pady=(12, 4))

        status_lbl = tk.Label(win, text="Waiting for Google callback...",
                              bg=BG, fg=YELLOW, font=FONT_MED)
        status_lbl.pack(anchor="w", padx=20, pady=12)

        # Poll every 2 seconds for up to 5 minutes
        _poll_count = [0]
        MAX_POLLS   = 150  # 150 * 2s = 5 min

        def _poll():
            if not win.winfo_exists():
                return
            _poll_count[0] += 1
            try:
                import pipeline as P2
                r = P2.check_manual_auth_result()
            except Exception:
                r = {"status": "waiting"}

            if r["status"] == "done":
                self._ui(lambda: (
                    self.auth_dot.config(text="●", fg=GREEN),
                    self.auth_status_lbl.config(text="Connected", fg=GREEN),
                    self.yt_auth_done.set(True),
                ))
                self._log("YouTube connected via manual flow.")
                win.after(1500, win.destroy)
                return
            elif r["status"] == "error":
                err_msg = r.get("message", "Unknown error")
                status_lbl.config(text=f"Error: {err_msg[:60]}", fg=RED)
                self._log(f"Manual OAuth error: {err_msg}")
                return  # stop polling
            elif _poll_count[0] >= MAX_POLLS:
                status_lbl.config(text="Timed out after 5 minutes.", fg=RED)
                self._log("Manual OAuth timed out.")
                return
            else:
                # Still waiting
                dots = "." * (_poll_count[0] % 4 + 1)
                status_lbl.config(
                    text=f"Waiting for Google callback{dots}", fg=YELLOW)
                win.after(2000, _poll)

        win.after(2000, _poll)

    def _upload_now(self):
        if not self.yt_auth_done.get():
            messagebox.showwarning("Not Connected",
                                   "Connect your Google account first.")
            return
        video_path = getattr(self, 'last_output_path',
                             os.path.join(os.path.expanduser("~"),
                                          "Desktop", "reaction_output.mp4"))
        if not os.path.exists(video_path):
            messagebox.showwarning("No Video",
                                   f"No video found at:\n{video_path}\n\n"
                                   "Generate one first, or select a file.")
            return
        # Snapshot tkinter vars on the main thread before spawning worker
        self._pending_upload = {
            "path":    video_path,
            "title":   self.title_entry.get(),
            "privacy": self.privacy_var.get(),
            "niche":   self.niche_var.get(),
        }
        self._ui(lambda: self.upload_status.config(text="Uploading...", fg=YELLOW))
        threading.Thread(target=self._upload_worker, daemon=True).start()

    def _upload_worker(self):
        """Upload worker — uses pre-snapshotted values, fully thread-safe."""
        try:
            import pipeline as P
        except ImportError as e:
            self._ui(lambda: self.upload_status.config(
                text=f"Import error: {e}", fg=RED))
            return

        # Read from snapshot (set on main thread in _upload_now)
        snap       = getattr(self, '_pending_upload', {})
        video_path = snap.get("path", os.path.join(
            os.path.expanduser("~"), "Desktop", "reaction_output.mp4"))
        title      = snap.get("title", "Reaction Video")
        privacy    = snap.get("privacy", "public")
        niche      = snap.get("niche", "")

        self._log(f"Uploading: {video_path}")
        self._ui(lambda: self.upload_status.config(
            text="Uploading to YouTube...", fg=YELLOW))

        try:
            result_url = P.upload_to_youtube(
                video_path=video_path,
                title=title,
                description=f"Reaction video by Reaction Studio\nNiche: {niche}",
                privacy=privacy,
            )
            if result_url.startswith("ERROR"):
                msg = result_url[7:]
                if "re-connect" in msg or "Token" in msg or "expired" in msg:
                    self._ui(lambda: (
                        self.auth_dot.config(text="x", fg=RED),
                        self.auth_status_lbl.config(
                            text="Token expired — reconnect", fg=RED),
                        self.yt_auth_done.set(False),
                    ))
                self._ui(lambda m=msg: self.upload_status.config(
                    text=f"Upload failed: {m[:80]}", fg=RED))
                self._log(f"Upload failed: {result_url}")
            else:
                self._ui(lambda u=result_url: self.upload_status.config(
                    text=f"Uploaded!  {u}", fg=GREEN))
                self._log(f"Uploaded: {result_url}")
        except Exception as e:
            self._ui(lambda err=str(e): self.upload_status.config(
                text=f"Upload error: {err[:60]}", fg=RED))
            self._log(f"Upload error: {e}")

    def _pick_upload_file(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[("Video", "*.mp4 *.mov *.mkv"), ("All", "*.*")])
        if path:
            self.last_output_path = path
            self._log(f"Upload target set: {path}")

    # ════════════════════════════════════════
    #  PAGE: LOG
    # ════════════════════════════════════════
    def _page_log(self):
        frame = tk.Frame(self.container, bg=BG)

        tk.Label(frame, text="Activity Log", bg=BG, fg=TEXT,
                 font=FONT_BIG).pack(anchor="w", padx=32, pady=(28, 4))

        self.log_text = tk.Text(frame, bg="#0a0a0a", fg="#00ff88",
                                insertbackground=TEXT,
                                font=FONT_CODE, bd=0, relief="flat",
                                state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=32, pady=(4, 8))

        ttk.Button(frame, text="Clear Log",
                   command=self._clear_log).pack(anchor="w", padx=32, pady=8,
                                                  ipadx=8, ipady=4)
        return frame

    def _log(self, msg):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}\n"
        self.log_lines.append(line)
        def _write():
            try:
                self.log_text.config(state="normal")
                self.log_text.insert("end", line)
                self.log_text.see("end")
                self.log_text.config(state="disabled")
            except Exception:
                pass
        self._ui(_write)

    def _clear_log(self):
        self.log_lines.clear()
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    import traceback as _tb, os as _os

    # Crash log on the Desktop so errors are visible even without a console
    _log = _os.path.join(_os.path.expanduser("~"), "Desktop", "ReactionStudio_error.txt")

    try:
        app = ReactionStudio()
        app.mainloop()
    except Exception as _e:
        _msg = _tb.format_exc()
        try:
            with open(_log, "w") as _f:
                _f.write(_msg)
        except Exception:
            pass
        # Try to show the error in a basic Tk window
        try:
            import tkinter as _tk
            _root = _tk.Tk()
            _root.title("Reaction Studio — Startup Error")
            _root.configure(bg="#0f0f0f")
            _tk.Label(_root, text="Reaction Studio failed to start:",
                      fg="#ef4444", bg="#0f0f0f",
                      font=("Segoe UI", 12, "bold")).pack(padx=20, pady=(20, 4))
            _tk.Label(_root, text=str(_e),
                      fg="#f5f5f5", bg="#0f0f0f",
                      font=("Consolas", 9), wraplength=560).pack(padx=20, pady=(0, 8))
            _tk.Label(_root,
                      text=f"Full traceback saved to:\n{_log}",
                      fg="#888888", bg="#0f0f0f",
                      font=("Segoe UI", 9)).pack(padx=20, pady=(0, 16))
            _tk.Button(_root, text="Close", command=_root.destroy,
                       bg="#7c3aed", fg="white",
                       font=("Segoe UI", 10)).pack(pady=(0, 20))
            _root.mainloop()
        except Exception:
            pass
