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

# ── Fallback stem map for blocks that have no own texture file ─────────────────
# When a block ID's stem doesn't exist on disk, map it to its base material.
# Covers stairs, slabs, walls, fences (nether brick), buttons, signs, and common
# functional blocks.  Keys are bare names (no 'minecraft:' prefix).
_FALLBACK_STEM: dict[str, str] = {
    # ── Stairs ────────────────────────────────────────────────────────────────
    "oak_stairs":                       "oak_planks",
    "spruce_stairs":                    "spruce_planks",
    "birch_stairs":                     "birch_planks",
    "jungle_stairs":                    "jungle_planks",
    "acacia_stairs":                    "acacia_planks",
    "dark_oak_stairs":                  "dark_oak_planks",
    "mangrove_stairs":                  "mangrove_planks",
    "cherry_stairs":                    "cherry_planks",
    "pale_oak_stairs":                  "pale_oak_planks",
    "bamboo_stairs":                    "bamboo_planks",
    "bamboo_mosaic_stairs":             "bamboo_mosaic",
    "crimson_stairs":                   "crimson_planks",
    "warped_stairs":                    "warped_planks",
    "stone_stairs":                     "stone",
    "cobblestone_stairs":               "cobblestone",
    "mossy_cobblestone_stairs":         "mossy_cobblestone",
    "stone_brick_stairs":               "stone_bricks",
    "mossy_stone_brick_stairs":         "mossy_stone_bricks",
    "andesite_stairs":                  "andesite",
    "polished_andesite_stairs":         "polished_andesite",
    "diorite_stairs":                   "diorite",
    "polished_diorite_stairs":          "polished_diorite",
    "granite_stairs":                   "granite",
    "polished_granite_stairs":          "polished_granite",
    "sandstone_stairs":                 "sandstone",
    "smooth_sandstone_stairs":          "sandstone_top",
    "cut_sandstone_stairs":             "cut_sandstone",
    "red_sandstone_stairs":             "red_sandstone",
    "smooth_red_sandstone_stairs":      "red_sandstone_top",
    "cut_red_sandstone_stairs":         "cut_red_sandstone",
    "brick_stairs":                     "bricks",
    "mud_brick_stairs":                 "mud_bricks",
    "nether_brick_stairs":              "nether_bricks",
    "red_nether_brick_stairs":          "red_nether_bricks",
    "quartz_stairs":                    "quartz_block_side",
    "smooth_quartz_stairs":             "quartz_block_bottom",
    "prismarine_stairs":                "prismarine",
    "prismarine_brick_stairs":          "prismarine_bricks",
    "dark_prismarine_stairs":           "dark_prismarine",
    "purpur_stairs":                    "purpur_block_side",
    "end_stone_brick_stairs":           "end_stone_bricks",
    "blackstone_stairs":                "blackstone",
    "polished_blackstone_stairs":       "polished_blackstone",
    "polished_blackstone_brick_stairs": "polished_blackstone_bricks",
    "deepslate_stairs":                 "deepslate",
    "cobbled_deepslate_stairs":         "cobbled_deepslate",
    "polished_deepslate_stairs":        "polished_deepslate",
    "deepslate_brick_stairs":           "deepslate_bricks",
    "deepslate_tile_stairs":            "deepslate_tiles",
    "tuff_stairs":                      "tuff",
    "polished_tuff_stairs":             "polished_tuff",
    "tuff_brick_stairs":                "tuff_bricks",
    "mud_brick_stairs":                 "mud_bricks",
    "cut_copper_stairs":                "cut_copper",
    "exposed_cut_copper_stairs":        "exposed_cut_copper",
    "weathered_cut_copper_stairs":      "weathered_cut_copper",
    "oxidized_cut_copper_stairs":       "oxidized_cut_copper",
    "waxed_cut_copper_stairs":          "cut_copper",
    "waxed_exposed_cut_copper_stairs":  "exposed_cut_copper",
    "waxed_weathered_cut_copper_stairs":"weathered_cut_copper",
    "waxed_oxidized_cut_copper_stairs": "oxidized_cut_copper",
    "resin_brick_stairs":               "resin_bricks",
    # ── Slabs ────────────────────────────────────────────────────────────────
    "oak_slab":                         "oak_planks",
    "spruce_slab":                      "spruce_planks",
    "birch_slab":                       "birch_planks",
    "jungle_slab":                      "jungle_planks",
    "acacia_slab":                      "acacia_planks",
    "dark_oak_slab":                    "dark_oak_planks",
    "mangrove_slab":                    "mangrove_planks",
    "cherry_slab":                      "cherry_planks",
    "pale_oak_slab":                    "pale_oak_planks",
    "bamboo_slab":                      "bamboo_planks",
    "bamboo_mosaic_slab":               "bamboo_mosaic",
    "crimson_slab":                     "crimson_planks",
    "warped_slab":                      "warped_planks",
    "petrified_oak_slab":               "oak_planks",
    "stone_slab":                       "stone",
    "smooth_stone_slab":                "smooth_stone",
    "cobblestone_slab":                 "cobblestone",
    "mossy_cobblestone_slab":           "mossy_cobblestone",
    "stone_brick_slab":                 "stone_bricks",
    "mossy_stone_brick_slab":           "mossy_stone_bricks",
    "andesite_slab":                    "andesite",
    "polished_andesite_slab":           "polished_andesite",
    "diorite_slab":                     "diorite",
    "polished_diorite_slab":            "polished_diorite",
    "granite_slab":                     "granite",
    "polished_granite_slab":            "polished_granite",
    "sandstone_slab":                   "sandstone",
    "smooth_sandstone_slab":            "sandstone_top",
    "cut_sandstone_slab":               "cut_sandstone",
    "red_sandstone_slab":               "red_sandstone",
    "smooth_red_sandstone_slab":        "red_sandstone_top",
    "cut_red_sandstone_slab":           "cut_red_sandstone",
    "brick_slab":                       "bricks",
    "mud_brick_slab":                   "mud_bricks",
    "nether_brick_slab":                "nether_bricks",
    "red_nether_brick_slab":            "red_nether_bricks",
    "quartz_slab":                      "quartz_block_side",
    "smooth_quartz_slab":               "quartz_block_bottom",
    "prismarine_slab":                  "prismarine",
    "prismarine_brick_slab":            "prismarine_bricks",
    "dark_prismarine_slab":             "dark_prismarine",
    "purpur_slab":                      "purpur_block_side",
    "end_stone_brick_slab":             "end_stone_bricks",
    "blackstone_slab":                  "blackstone",
    "polished_blackstone_slab":         "polished_blackstone",
    "polished_blackstone_brick_slab":   "polished_blackstone_bricks",
    "deepslate_slab":                   "deepslate",
    "cobbled_deepslate_slab":           "cobbled_deepslate",
    "polished_deepslate_slab":          "polished_deepslate",
    "deepslate_brick_slab":             "deepslate_bricks",
    "deepslate_tile_slab":              "deepslate_tiles",
    "tuff_slab":                        "tuff",
    "polished_tuff_slab":               "polished_tuff",
    "tuff_brick_slab":                  "tuff_bricks",
    "cut_copper_slab":                  "cut_copper",
    "exposed_cut_copper_slab":          "exposed_cut_copper",
    "weathered_cut_copper_slab":        "weathered_cut_copper",
    "oxidized_cut_copper_slab":         "oxidized_cut_copper",
    "waxed_cut_copper_slab":            "cut_copper",
    "waxed_exposed_cut_copper_slab":    "exposed_cut_copper",
    "waxed_weathered_cut_copper_slab":  "weathered_cut_copper",
    "waxed_oxidized_cut_copper_slab":   "oxidized_cut_copper",
    "resin_brick_slab":                 "resin_bricks",
    # ── Walls ────────────────────────────────────────────────────────────────
    "cobblestone_wall":                 "cobblestone",
    "mossy_cobblestone_wall":           "mossy_cobblestone",
    "stone_wall":                       "stone",
    "stone_brick_wall":                 "stone_bricks",
    "mossy_stone_brick_wall":           "mossy_stone_bricks",
    "andesite_wall":                    "andesite",
    "diorite_wall":                     "diorite",
    "granite_wall":                     "granite",
    "sandstone_wall":                   "sandstone",
    "red_sandstone_wall":               "red_sandstone",
    "brick_wall":                       "bricks",
    "mud_brick_wall":                   "mud_bricks",
    "nether_brick_wall":                "nether_bricks",
    "red_nether_brick_wall":            "red_nether_bricks",
    "prismarine_wall":                  "prismarine",
    "end_stone_brick_wall":             "end_stone_bricks",
    "blackstone_wall":                  "blackstone",
    "polished_blackstone_wall":         "polished_blackstone",
    "polished_blackstone_brick_wall":   "polished_blackstone_bricks",
    "deepslate_wall":                   "deepslate",
    "cobbled_deepslate_wall":           "cobbled_deepslate",
    "polished_deepslate_wall":          "polished_deepslate",
    "deepslate_brick_wall":             "deepslate_bricks",
    "deepslate_tile_wall":              "deepslate_tiles",
    "tuff_wall":                        "tuff",
    "polished_tuff_wall":               "polished_tuff",
    "tuff_brick_wall":                  "tuff_bricks",
    "resin_brick_wall":                 "resin_bricks",
    # ── Fences (nether — others have own texture files) ───────────────────────
    "nether_brick_fence":               "nether_bricks",
    # ── Buttons ──────────────────────────────────────────────────────────────
    "oak_button":                       "oak_planks",
    "spruce_button":                    "spruce_planks",
    "birch_button":                     "birch_planks",
    "jungle_button":                    "jungle_planks",
    "acacia_button":                    "acacia_planks",
    "dark_oak_button":                  "dark_oak_planks",
    "mangrove_button":                  "mangrove_planks",
    "cherry_button":                    "cherry_planks",
    "pale_oak_button":                  "pale_oak_planks",
    "bamboo_button":                    "bamboo_planks",
    "crimson_button":                   "crimson_planks",
    "warped_button":                    "warped_planks",
    "stone_button":                     "stone",
    "polished_blackstone_button":       "polished_blackstone",
    # ── Signs ────────────────────────────────────────────────────────────────
    "oak_sign":          "oak_planks",    "oak_wall_sign":     "oak_planks",
    "spruce_sign":       "spruce_planks", "spruce_wall_sign":  "spruce_planks",
    "birch_sign":        "birch_planks",  "birch_wall_sign":   "birch_planks",
    "jungle_sign":       "jungle_planks", "jungle_wall_sign":  "jungle_planks",
    "acacia_sign":       "acacia_planks", "acacia_wall_sign":  "acacia_planks",
    "dark_oak_sign":     "dark_oak_planks","dark_oak_wall_sign":"dark_oak_planks",
    "mangrove_sign":     "mangrove_planks","mangrove_wall_sign":"mangrove_planks",
    "cherry_sign":       "cherry_planks", "cherry_wall_sign":  "cherry_planks",
    "pale_oak_sign":     "pale_oak_planks","pale_oak_wall_sign":"pale_oak_planks",
    "bamboo_sign":       "bamboo_planks", "bamboo_wall_sign":  "bamboo_planks",
    "crimson_sign":      "crimson_planks","crimson_wall_sign": "crimson_planks",
    "warped_sign":       "warped_planks", "warped_wall_sign":  "warped_planks",
    "oak_hanging_sign":  "oak_planks",
    "spruce_hanging_sign":"spruce_planks",
    "birch_hanging_sign":"birch_planks",
    "jungle_hanging_sign":"jungle_planks",
    "acacia_hanging_sign":"acacia_planks",
    "dark_oak_hanging_sign":"dark_oak_planks",
    "mangrove_hanging_sign":"mangrove_planks",
    "cherry_hanging_sign":"cherry_planks",
    "pale_oak_hanging_sign":"pale_oak_planks",
    "bamboo_hanging_sign":"bamboo_planks",
    "crimson_hanging_sign":"crimson_planks",
    "warped_hanging_sign":"warped_planks",
    # ── Functional blocks ────────────────────────────────────────────────────
    "crafting_table":    "crafting_table_top",
    "furnace":           "furnace_top",
    "blast_furnace":     "blast_furnace_top",
    "smoker":            "smoker_top",
    "chest":             "oak_planks",
    "trapped_chest":     "oak_planks",
    "ender_chest":       "obsidian",
    "barrel":            "barrel_top",
    "piston":            "piston_top_normal",
    "sticky_piston":     "piston_top_sticky",
    "piston_head":       "piston_top_normal",
    "observer":          "observer_top",
    "dispenser":         "dispenser_front_horizontal",
    "dropper":           "dropper_front_horizontal",
    "hopper":            "hopper_outside",
    "tnt":               "tnt_side",
    "bookshelf":         "bookshelf",
    "jukebox":           "jukebox_top",
    "note_block":        "note_block",
    "beacon":            "beacon",
    "enchanting_table":  "enchanting_table_top",
    "cauldron":          "cauldron_side",
    "grindstone":        "grindstone_side",
    "stonecutter":       "stonecutter_top",
    "cartography_table": "cartography_table_top",
    "fletching_table":   "fletching_table_front",
    "smithing_table":    "smithing_table_top",
    "loom":              "loom_top",
    "composter":         "composter_top",
    "lectern":           "lectern_top",
    "glass_pane":        "glass",
    "iron_bars":         "iron_bars",
    "chain":             "chain",
    "lantern":           "lantern",
    "soul_lantern":      "soul_lantern",
    "campfire":          "campfire_log",
    "soul_campfire":     "soul_campfire_log",
    # Copper functional
    "copper_door":                      "copper_block",
    "exposed_copper_door":              "exposed_copper",
    "weathered_copper_door":            "weathered_copper",
    "oxidized_copper_door":             "oxidized_copper",
    "waxed_copper_door":                "copper_block",
    "waxed_exposed_copper_door":        "exposed_copper",
    "waxed_weathered_copper_door":      "weathered_copper",
    "waxed_oxidized_copper_door":       "oxidized_copper",
    "copper_trapdoor":                  "copper_block",
    "exposed_copper_trapdoor":          "exposed_copper",
    "weathered_copper_trapdoor":        "weathered_copper",
    "oxidized_copper_trapdoor":         "oxidized_copper",
    "waxed_copper_trapdoor":            "copper_block",
    "waxed_exposed_copper_trapdoor":    "exposed_copper",
    "waxed_weathered_copper_trapdoor":  "weathered_copper",
    "waxed_oxidized_copper_trapdoor":   "oxidized_copper",
}


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
    """Return the texture filename stem (no .png) for a block's top face.

    Resolution order:
      1. _TOP_OVERRIDES  — explicit top-face overrides (grass_block_top, etc.)
      2. exact name      — most blocks just use their own name
      3. _FALLBACK_STEM  — variant blocks (stairs, slabs, walls, …) → base material
    """
    name = block_id.removeprefix("minecraft:")
    if name in _TOP_OVERRIDES:
        return _TOP_OVERRIDES[name]
    if name in _FALLBACK_STEM:
        return _FALLBACK_STEM[name]
    return name


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
