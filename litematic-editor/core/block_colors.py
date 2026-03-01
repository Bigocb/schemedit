"""
Shared block colour data for both the 2D layer view and the 3D mesh builder.

block_rgb(block_id)  → (r, g, b) as 0-255 ints   — used by mesh_builder
block_qcolor(block_id) → QColor                   — used by layer_view
"""
from __future__ import annotations

_COLOR_MAP: dict[str, tuple[int, int, int]] = {
    "minecraft:air":               (0,   0,   0),
    "minecraft:cave_air":          (0,   0,   0),
    "minecraft:void_air":          (0,   0,   0),
    "minecraft:stone":             (128, 128, 128),
    "minecraft:granite":           (167, 107,  82),
    "minecraft:polished_granite":  (180, 120,  90),
    "minecraft:diorite":           (195, 195, 195),
    "minecraft:andesite":          (140, 140, 140),
    "minecraft:grass_block":       ( 89, 145,  63),
    "minecraft:dirt":              (134,  96,  67),
    "minecraft:coarse_dirt":       (120,  82,  55),
    "minecraft:cobblestone":       (110, 110, 110),
    "minecraft:oak_planks":        (197, 163, 102),
    "minecraft:spruce_planks":     (120,  86,  48),
    "minecraft:birch_planks":      (216, 206, 160),
    "minecraft:jungle_planks":     (160, 115,  72),
    "minecraft:acacia_planks":     (168,  90,  50),
    "minecraft:dark_oak_planks":   ( 66,  43,  20),
    "minecraft:oak_log":           (101,  77,  41),
    "minecraft:spruce_log":        ( 72,  55,  30),
    "minecraft:birch_log":         (216, 206, 160),
    "minecraft:jungle_log":        (148, 108,  57),
    "minecraft:acacia_log":        (168,  90,  50),
    "minecraft:dark_oak_log":      ( 60,  40,  14),
    "minecraft:oak_leaves":        ( 61, 102,  35),
    "minecraft:spruce_leaves":     ( 44,  75,  35),
    "minecraft:birch_leaves":      ( 90, 132,  44),
    "minecraft:jungle_leaves":     ( 40,  93,  24),
    "minecraft:acacia_leaves":     ( 76, 115,  24),
    "minecraft:dark_oak_leaves":   ( 43,  78,  14),
    "minecraft:sand":              (218, 210, 158),
    "minecraft:red_sand":          (189,  93,  38),
    "minecraft:gravel":            (161, 154, 148),
    "minecraft:gold_ore":          (144, 138,  78),
    "minecraft:iron_ore":          (136, 118, 107),
    "minecraft:coal_ore":          ( 85,  85,  85),
    "minecraft:gold_block":        (249, 236,  77),
    "minecraft:iron_block":        (220, 220, 220),
    "minecraft:diamond_block":     ( 99, 219, 213),
    "minecraft:emerald_block":     ( 42, 178,  81),
    "minecraft:glass":             (196, 225, 238),
    "minecraft:water":             ( 63, 118, 228),
    "minecraft:lava":              (228, 102,  18),
    "minecraft:obsidian":          ( 20,  13,  35),
    "minecraft:snow":              (240, 245, 255),
    "minecraft:ice":               (162, 200, 237),
    "minecraft:packed_ice":        (142, 188, 228),
    "minecraft:blue_ice":          ( 96, 167, 230),
    "minecraft:netherrack":        (135,  54,  54),
    "minecraft:nether_bricks":     ( 95,  28,  28),
    "minecraft:soul_sand":         ( 84,  66,  52),
    "minecraft:glowstone":         (225, 186, 104),
    "minecraft:end_stone":         (219, 220, 169),
    "minecraft:purpur_block":      (167, 118, 167),
    "minecraft:white_concrete":    (207, 213, 214),
    "minecraft:orange_concrete":   (224, 101,  20),
    "minecraft:magenta_concrete":  (170,  48, 159),
    "minecraft:light_blue_concrete":( 36, 137, 199),
    "minecraft:yellow_concrete":   (240, 175,  21),
    "minecraft:lime_concrete":     ( 94, 168,  24),
    "minecraft:pink_concrete":     (213, 101, 142),
    "minecraft:gray_concrete":     ( 55,  58,  62),
    "minecraft:light_gray_concrete":(125, 125, 115),
    "minecraft:cyan_concrete":     ( 21, 119, 136),
    "minecraft:purple_concrete":   (100,  32, 156),
    "minecraft:blue_concrete":     ( 45,  47, 143),
    "minecraft:brown_concrete":    ( 96,  60,  32),
    "minecraft:green_concrete":    ( 73,  91,  36),
    "minecraft:red_concrete":      (142,  32,  32),
    "minecraft:black_concrete":    (  8,  10,  15),
    "minecraft:bricks":            (151,  96,  83),
    "minecraft:stone_bricks":      (118, 118, 118),
    "minecraft:mossy_stone_bricks":(104, 118,  87),
    "minecraft:cracked_stone_bricks":(100,100,100),
    "minecraft:chiseled_stone_bricks":(130,130,130),
}

AIR_IDS: frozenset[str] = frozenset({
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
})


def _fallback_rgb(block_id: str) -> tuple[int, int, int]:
    """Deterministic colour for unmapped blocks, avoiding very dark values."""
    h = abs(hash(block_id))
    r = max((h & 0xFF0000) >> 16, 80)
    g = max((h & 0x00FF00) >> 8,  80)
    b = max((h & 0x0000FF),        80)
    return r, g, b


def block_rgb(block_id: str) -> tuple[int, int, int]:
    """Return (r, g, b) 0-255 for a block ID. Air returns (0, 0, 0)."""
    if block_id in AIR_IDS:
        return (0, 0, 0)
    return _COLOR_MAP.get(block_id) or _fallback_rgb(block_id)


def block_qcolor(block_id: str):
    """Return a PyQt6 QColor for a block ID (imports Qt lazily)."""
    from PyQt6.QtGui import QColor
    if block_id in AIR_IDS:
        return QColor(0, 0, 0, 0)
    r, g, b = block_rgb(block_id)
    return QColor(r, g, b)
