# utils/sound.py
# Sound Effects Utility for SmartRetail POS
# Uses afplay on macOS (zero dependencies) with background thread for non-blocking playback.

from __future__ import annotations
import os
import threading
import subprocess

_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")

_SOUND_FILES = {
    "beep_success": os.path.join(_SOUNDS_DIR, "beep_success.wav"),
    "beep_error":   os.path.join(_SOUNDS_DIR, "beep_error.wav"),
}


def play_sound(name: str) -> None:
    """
    Play a named sound asynchronously (non-blocking).
    Uses macOS afplay for zero-latency output.
    Falls back to tkinter bell() if file not found.

    Names: 'beep_success', 'beep_error'
    """
    path = _SOUND_FILES.get(name)
    if path and os.path.exists(path):
        threading.Thread(target=_afplay, args=(path,), daemon=True).start()
    else:
        _tk_bell()


def _afplay(path: str) -> None:
    """Play WAV file using afplay (macOS built-in, zero install needed)."""
    try:
        subprocess.run(["afplay", path], check=False, timeout=3)
    except Exception:
        _tk_bell()


def _tk_bell() -> None:
    """Fallback: system bell via tkinter."""
    try:
        import tkinter as tk
        root = tk._default_root  # type: ignore
        if root:
            root.bell()
    except Exception:
        pass


# Convenience shortcuts
def beep_success() -> None:
    """Play the supermarket-style success beep (high pitched tick)."""
    play_sound("beep_success")


def beep_error() -> None:
    """Play the error beep (low tone, for not-found or invalid scan)."""
    play_sound("beep_error")
