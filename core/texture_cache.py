"""
Block texture cache — downloads 16×16 PNGs from the minecraft-assets GitHub repo
and caches them locally as QPixmaps.

Source: https://github.com/InventivetalentDev/minecraft-assets/tree/1.21.11

URL pattern:
  https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.21.11/
    assets/minecraft/textures/block/<name>.png
"""
from __future__ import annotations
import threading
import urllib.request
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage

_BRANCH    = "1.21.11"
_REPO_BASE = (
    "https://raw.githubusercontent.com/InventivetalentDev/"
    f"minecraft-assets/{_BRANCH}/assets/minecraft/textures/block"
)
_CACHE_DIR = Path.home() / ".cache" / "schemedit" / "textures"

# Blocks that need a specific top-face texture (not just <block_name>.png)
_TOP_OVERRIDES: dict[str, str] = {
    "grass_block":              "grass_block_top",
    "mycelium":                 "mycelium_top",
    "podzol":                   "podzol_top",
    "dirt_path":                "dirt_path_top",
    "farmland":                 "farmland_moist",
    "sandstone":                "sandstone_top",
    "red_sandstone":            "red_sandstone_top",
    "chiseled_sandstone":       "sandstone_top",
    "smooth_sandstone":         "sandstone_top",
    "chiseled_red_sandstone":   "red_sandstone_top",
    "smooth_red_sandstone":     "red_sandstone_top",
    # Logs — top face
    "oak_log":                  "oak_log_top",
    "birch_log":                "birch_log_top",
    "spruce_log":               "spruce_log_top",
    "jungle_log":               "jungle_log_top",
    "acacia_log":               "acacia_log_top",
    "dark_oak_log":             "dark_oak_log_top",
    "mangrove_log":             "mangrove_log_top",
    "cherry_log":               "cherry_log_top",
    "pale_oak_log":             "pale_oak_log_top",
    # Stripped logs — top face
    "stripped_oak_log":         "stripped_oak_log_top",
    "stripped_birch_log":       "stripped_birch_log_top",
    "stripped_spruce_log":      "stripped_spruce_log_top",
    "stripped_jungle_log":      "stripped_jungle_log_top",
    "stripped_acacia_log":      "stripped_acacia_log_top",
    "stripped_dark_oak_log":    "stripped_dark_oak_log_top",
    "stripped_mangrove_log":    "stripped_mangrove_log_top",
    "stripped_cherry_log":      "stripped_cherry_log_top",
    "stripped_pale_oak_log":    "stripped_pale_oak_log_top",
    # Wood blocks (all-sided) — use the side log texture for the top
    "oak_wood":                 "oak_log",
    "birch_wood":               "birch_log",
    "spruce_wood":              "spruce_log",
    "jungle_wood":              "jungle_log",
    "acacia_wood":              "acacia_log",
    "dark_oak_wood":            "dark_oak_log",
    "mangrove_wood":            "mangrove_log",
    "cherry_wood":              "cherry_log",
    "pale_oak_wood":            "pale_oak_log",
    "stripped_oak_wood":        "stripped_oak_log",
    "stripped_birch_wood":      "stripped_birch_log",
    "stripped_spruce_wood":     "stripped_spruce_log",
    "stripped_jungle_wood":     "stripped_jungle_log",
    "stripped_acacia_wood":     "stripped_acacia_log",
    "stripped_dark_oak_wood":   "stripped_dark_oak_log",
    "stripped_mangrove_wood":   "stripped_mangrove_log",
    "stripped_cherry_wood":     "stripped_cherry_log",
    "stripped_pale_oak_wood":   "stripped_pale_oak_log",
}

_AIR_IDS: frozenset[str] = frozenset({
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
})


# ── Download manager ──────────────────────────────────────────────────────────
# Lives in the main thread; Qt auto-queues cross-thread signal delivery.

class _DownloadManager(QObject):
    """Signals emitted from worker threads — delivered to main thread by Qt."""
    batch_ready = pyqtSignal()   # fired when ≥1 new textures have landed


_manager = _DownloadManager()

# ── State ─────────────────────────────────────────────────────────────────────

_pixmap_cache: dict[str, QPixmap | None] = {}   # "<block_id>@<size>" → pixmap
_downloading:  set[str] = set()                  # block IDs in flight
_failed:       set[str] = set()                  # block IDs with no texture file


# ── Public API ────────────────────────────────────────────────────────────────

def get_pixmap(block_id: str, size: int = 16) -> QPixmap | None:
    """
    Return a QPixmap for the block's top face scaled to size×size, or None if
    not yet available.  Schedules a background download if the texture isn't on
    disk yet.  Call from the main thread only.
    """
    if block_id in _AIR_IDS or block_id in _failed:
        return None

    key = f"{block_id}@{size}"
    if key in _pixmap_cache:
        return _pixmap_cache[key]

    stem  = _texture_stem(block_id)
    local = _CACHE_DIR / f"{stem}.png"

    if local.exists():
        pix = _load_local(local, size)
        _pixmap_cache[key] = pix
        return pix

    _schedule_download(block_id, stem)
    return None


def prefetch(block_ids: list[str]) -> None:
    """
    Pre-download textures for a collection of block IDs (background, no-op if
    already cached on disk).  Call when a schematic is loaded so textures are
    warming up while the user is looking at the first layer.
    """
    for bid in sorted(set(block_ids)):
        if bid in _AIR_IDS or bid in _failed or bid in _downloading:
            continue
        stem  = _texture_stem(bid)
        local = _CACHE_DIR / f"{stem}.png"
        if not local.exists():
            _schedule_download(bid, stem)


# ── Internals ─────────────────────────────────────────────────────────────────

def _texture_stem(block_id: str) -> str:
    """Return the texture filename stem (no .png) for a block's top face."""
    name = block_id.removeprefix("minecraft:")
    return _TOP_OVERRIDES.get(name, name)


def _load_local(path: Path, size: int) -> QPixmap | None:
    img = QImage(str(path))
    if img.isNull():
        return None
    # FastTransformation = nearest-neighbour — preserves Minecraft pixel-art look
    return QPixmap.fromImage(img).scaled(
        size, size,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


def _schedule_download(block_id: str, stem: str) -> None:
    if block_id in _downloading:
        return
    _downloading.add(block_id)
    t = threading.Thread(
        target=_download_worker,
        args=(block_id, stem),
        daemon=True,
    )
    t.start()


def _download_worker(block_id: str, stem: str) -> None:
    """Runs in a background daemon thread."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        local = _CACHE_DIR / f"{stem}.png"
        url   = f"{_REPO_BASE}/{stem}.png"
        urllib.request.urlretrieve(url, str(local))
        _manager.batch_ready.emit()   # Qt queues this to the main thread
    except Exception:
        _failed.add(block_id)
    finally:
        _downloading.discard(block_id)
