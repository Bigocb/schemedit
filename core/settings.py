"""
Application settings — persistent JSON storage.

Stored at ~/.config/schemedit/settings.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SETTINGS_PATH = Path.home() / ".config" / "schemedit" / "settings.json"

# Default values — used when the file doesn't exist or a key is missing
_DEFAULTS: dict[str, Any] = {
    "recent_files":       [],      # newest first; max length = max_recent
    "max_recent":         10,
    "fly_keys": {
        # Values are Qt key names as strings, e.g. "W", "Space", "Up"
        "forward":  "W",
        "backward": "S",
        "left":     "A",
        "right":    "D",
        "up":       "E",
        "down":     "Q",
        "reset":    "R",
    },
    "mouse_sensitivity":  0.20,    # degrees per pixel for right-drag look
    "move_speed":         10.0,    # blocks per second (3D fly speed)
    "show_hint_overlay":  True,    # hint label in 3D view
}

_data: dict[str, Any] = {}


# ── I/O ───────────────────────────────────────────────────────────────────────

def _load() -> None:
    global _data
    _data = {k: (dict(v) if isinstance(v, dict) else v) for k, v in _DEFAULTS.items()}
    if _SETTINGS_PATH.exists():
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
                saved: dict = json.load(fh)
            for key, val in saved.items():
                if key not in _data:
                    continue
                if isinstance(_data[key], dict) and isinstance(val, dict):
                    _data[key].update(val)   # merge dict sub-keys
                else:
                    _data[key] = val
        except Exception:
            pass   # corrupt file → stick with defaults


def save() -> None:
    """Persist current settings to disk."""
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(_data, fh, indent=2)
    except Exception:
        pass


# ── Accessors ─────────────────────────────────────────────────────────────────

def get(key: str, default: Any = None) -> Any:
    if not _data:
        _load()
    return _data.get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001  (shadowing built-in is fine here)
    if not _data:
        _load()
    _data[key] = value
    save()


# ── Fly-key helpers ───────────────────────────────────────────────────────────

def get_fly_keys() -> dict[str, str]:
    """Return current fly-key mapping.  Keys: forward/backward/left/right/up/down/reset."""
    if not _data:
        _load()
    result = dict(_DEFAULTS["fly_keys"])
    result.update(_data.get("fly_keys", {}))
    return result


def set_fly_keys(keys: dict[str, str]) -> None:
    if not _data:
        _load()
    _data["fly_keys"] = dict(keys)
    save()


# ── Recent-file helpers ───────────────────────────────────────────────────────

def add_recent_file(path: str) -> None:
    if not _data:
        _load()
    recent: list[str] = list(_data.get("recent_files", []))
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    _data["recent_files"] = recent[: _data.get("max_recent", 10)]
    save()


def get_recent_files() -> list[str]:
    if not _data:
        _load()
    return list(_data.get("recent_files", []))


def remove_recent_file(path: str) -> None:
    if not _data:
        _load()
    recent: list[str] = list(_data.get("recent_files", []))
    if path in recent:
        recent.remove(path)
    _data["recent_files"] = recent
    save()


# ── Mouse / speed helpers ─────────────────────────────────────────────────────

def mouse_sensitivity() -> float:
    return float(get("mouse_sensitivity", _DEFAULTS["mouse_sensitivity"]))


def set_mouse_sensitivity(v: float) -> None:
    set("mouse_sensitivity", float(v))


def move_speed() -> float:
    return float(get("move_speed", _DEFAULTS["move_speed"]))


def set_move_speed(v: float) -> None:
    set("move_speed", float(v))


# Load on import so callers don't need to call _load() explicitly
_load()
