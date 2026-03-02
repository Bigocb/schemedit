"""
Texture atlas builder for the 3D voxel renderer.

Each unique block×face combination gets a 16×16 slot packed into a single
RGBA image that can be uploaded as one OpenGL texture.  Slots are filled with
real textures when available on disk, or solid-colour placeholders otherwise.
The UV layout is determined once at load time and never changes, so partial
texture availability (some downloaded, some not yet) is fine — placeholder
slots are simply overwritten when refresh_textures() is called later.

Face types recognised by uv_map:
    'top'   — +Y face  (grass top, log end, sandstone top, …)
    'side'  — ±X / ±Z faces
    'bottom'— –Y face  (currently same stem as 'side' for most blocks)
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from core.block_colors import block_rgb, AIR_IDS
from core import texture_cache as _tex
from core.texture_cache import _FALLBACK_STEM as _TEX_FALLBACK

TILE = 16   # pixels per atlas tile
COLS = 16   # tiles per atlas row → atlas width = COLS*TILE = 256 px

# ── Side-face texture overrides ───────────────────────────────────────────────
# For blocks whose side texture differs from the plain block name.
# (Top overrides are already in texture_cache._TOP_OVERRIDES)

_SIDE_OVERRIDES: dict[str, str] = {
    "grass_block":              "grass_block_side",
    "mycelium":                 "mycelium_side",
    "podzol":                   "podzol_side",
    "dirt_path":                "dirt_path_side",
    "farmland":                 "dirt",
    "farmland_moist":           "dirt",
    # Logs: side is the log texture itself (no _top suffix)
    "oak_log":                  "oak_log",
    "birch_log":                "birch_log",
    "spruce_log":               "spruce_log",
    "jungle_log":               "jungle_log",
    "acacia_log":               "acacia_log",
    "dark_oak_log":             "dark_oak_log",
    "mangrove_log":             "mangrove_log",
    "cherry_log":               "cherry_log",
    "pale_oak_log":             "pale_oak_log",
    "stripped_oak_log":         "stripped_oak_log",
    "stripped_birch_log":       "stripped_birch_log",
    "stripped_spruce_log":      "stripped_spruce_log",
    "stripped_jungle_log":      "stripped_jungle_log",
    "stripped_acacia_log":      "stripped_acacia_log",
    "stripped_dark_oak_log":    "stripped_dark_oak_log",
    "stripped_mangrove_log":    "stripped_mangrove_log",
    "stripped_cherry_log":      "stripped_cherry_log",
    "stripped_pale_oak_log":    "stripped_pale_oak_log",
    # Wood (all-sided variant)
    "oak_wood":                 "oak_log",
    "birch_wood":               "birch_log",
    "spruce_wood":              "spruce_log",
    "jungle_wood":              "jungle_log",
    "acacia_wood":              "acacia_log",
    "dark_oak_wood":            "dark_oak_log",
    "mangrove_wood":            "mangrove_log",
    "cherry_wood":              "cherry_log",
    "pale_oak_wood":            "pale_oak_log",
}

# Bottom-face overrides (grass = dirt underneath, etc.)
_BOTTOM_OVERRIDES: dict[str, str] = {
    "grass_block":  "dirt",
    "mycelium":     "dirt",
    "podzol":       "dirt",
}


def _side_stem(block_id: str) -> str:
    name = block_id.removeprefix("minecraft:")
    if name in _SIDE_OVERRIDES:
        return _SIDE_OVERRIDES[name]
    if name in _TEX_FALLBACK:
        return _TEX_FALLBACK[name]
    return name


def _bottom_stem(block_id: str) -> str:
    name = block_id.removeprefix("minecraft:")
    if name in _BOTTOM_OVERRIDES:
        return _BOTTOM_OVERRIDES[name]
    # Reuse side stem (handles stairs/slabs/walls automatically)
    return _side_stem(block_id)


def _load_tile(stem: str) -> np.ndarray | None:
    """Load a 16×16 RGBA tile from the disk cache.  Returns None if missing."""
    local = _tex._CACHE_DIR / f"{stem}.png"
    if not local.exists():
        return None
    img = QImage(str(local))
    if img.isNull():
        return None
    img = img.scaled(
        TILE, TILE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    ).convertToFormat(QImage.Format.Format_RGBA8888)
    arr = np.zeros((TILE, TILE, 4), dtype=np.uint8)
    for y in range(TILE):
        for x in range(TILE):
            px = img.pixel(x, y)            # QRgb = 0xAARRGGBB
            arr[y, x, 0] = (px >> 16) & 0xFF
            arr[y, x, 1] = (px >> 8)  & 0xFF
            arr[y, x, 2] =  px        & 0xFF
            arr[y, x, 3] = (px >> 24) & 0xFF
    return arr


def _color_tile(block_id: str) -> np.ndarray:
    """Generate a solid-colour 16×16 RGBA tile from the colour map."""
    r, g, b = block_rgb(block_id)
    tile = np.zeros((TILE, TILE, 4), dtype=np.uint8)
    tile[:, :] = [r, g, b, 255]
    return tile


# ── Atlas class ───────────────────────────────────────────────────────────────

class Atlas:
    """
    Manages a texture atlas for the 3D renderer.

    Usage:
        atlas = Atlas(unique_block_ids)
        rgba  = atlas.get_rgba()    # upload to GPU as RGBA texture
        uvmap = atlas.uv_map        # pass to mesh_builder.build_mesh()

        # After new textures download:
        if atlas.refresh_textures():
            re_upload_to_gpu(atlas.get_rgba())
    """

    def __init__(self, block_ids: list[str]):
        # Filter air, deduplicate, sort for deterministic layout
        unique = sorted(
            {bid for bid in block_ids if bid not in AIR_IDS}
        )

        # Collect all unique (stem, face_key) pairs needed
        # face_key: 'top' | 'side' | 'bottom'
        self._stem_slots: dict[str, int] = {}   # stem → slot index
        self._block_face_to_stem: dict[tuple[str, str], str] = {}

        stems_ordered: list[str] = []

        def _alloc(stem: str) -> int:
            if stem not in self._stem_slots:
                self._stem_slots[stem] = len(stems_ordered)
                stems_ordered.append(stem)
            return self._stem_slots[stem]

        for bid in unique:
            top_s    = _tex._texture_stem(bid)
            side_s   = _side_stem(bid)
            bottom_s = _bottom_stem(bid)
            _alloc(top_s)
            _alloc(side_s)
            _alloc(bottom_s)
            self._block_face_to_stem[(bid, 'top')]    = top_s
            self._block_face_to_stem[(bid, 'side')]   = side_s
            self._block_face_to_stem[(bid, 'bottom')] = bottom_s

        n = len(stems_ordered)
        rows = max(1, math.ceil(n / COLS))
        self._atlas_w = COLS * TILE
        self._atlas_h = rows * TILE
        self._rgba = np.zeros((self._atlas_h, self._atlas_w, 4), dtype=np.uint8)
        self._stems = stems_ordered      # index → stem
        self._has_real: set[str] = set() # stems that have real textures

        # Build UV map: block_id → dict of face → (u0,v0,u1,v1)
        self.uv_map: dict[str, dict[str, tuple[float, float, float, float]]] = {}
        for bid in unique:
            self.uv_map[bid] = {}
            for face in ('top', 'side', 'bottom'):
                stem = self._block_face_to_stem[(bid, face)]
                slot = self._stem_slots[stem]
                self.uv_map[bid][face] = self._slot_uvs(slot)

        self._fill_all()

    # ── public ───────────────────────────────────────────────────────────────

    def get_rgba(self) -> np.ndarray:
        """Return the current atlas pixel data as (H, W, 4) uint8."""
        return self._rgba

    def refresh_textures(self) -> bool:
        """
        Overwrite placeholder slots for which real textures are now on disk.
        Returns True if anything changed (caller should re-upload to GPU).
        """
        changed = False
        for stem, slot in self._stem_slots.items():
            if stem in self._has_real:
                continue
            tile = _load_tile(stem)
            if tile is not None:
                self._write_slot(slot, tile)
                self._has_real.add(stem)
                changed = True
        return changed

    @property
    def width(self) -> int:
        return self._atlas_w

    @property
    def height(self) -> int:
        return self._atlas_h

    # ── internals ────────────────────────────────────────────────────────────

    def _slot_uvs(self, slot: int) -> tuple[float, float, float, float]:
        col = slot % COLS
        row = slot // COLS
        u0 = (col * TILE)         / self._atlas_w
        v0 = (row * TILE)         / self._atlas_h
        u1 = (col * TILE + TILE)  / self._atlas_w
        v1 = (row * TILE + TILE)  / self._atlas_h
        return u0, v0, u1, v1

    def _write_slot(self, slot: int, tile: np.ndarray) -> None:
        col = slot % COLS
        row = slot // COLS
        x0  = col * TILE
        y0  = row * TILE
        self._rgba[y0:y0 + TILE, x0:x0 + TILE] = tile

    def _fill_all(self) -> None:
        for stem, slot in self._stem_slots.items():
            tile = _load_tile(stem)
            if tile is not None:
                self._has_real.add(stem)
            else:
                # Find a representative block_id for this stem's fallback colour
                # (just use the stem name prefixed with 'minecraft:')
                tile = _color_tile(f"minecraft:{stem}")
            self._write_slot(slot, tile)
