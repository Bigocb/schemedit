"""
Comprehensive Minecraft 1.21 block ID list used for autocomplete.
All IDs include the 'minecraft:' namespace prefix.
"""
from __future__ import annotations

# ── Colour palettes ────────────────────────────────────────────────────────────
_COLOURS = [
    "white", "orange", "magenta", "light_blue", "yellow", "lime",
    "pink", "gray", "light_gray", "cyan", "purple", "blue",
    "brown", "green", "red", "black",
]

_WOOD_TYPES = [
    "oak", "spruce", "birch", "jungle", "acacia", "dark_oak",
    "mangrove", "cherry", "pale_oak", "bamboo",
]
_NETHER_WOOD = ["crimson", "warped"]

# ── Builder ────────────────────────────────────────────────────────────────────

def _p(s: str) -> str:
    return f"minecraft:{s}"


def _wood_blocks(t: str) -> list[str]:
    if t == "bamboo":
        return [
            _p(f"bamboo_block"), _p(f"stripped_bamboo_block"),
            _p(f"bamboo_planks"), _p(f"bamboo_mosaic"),
            _p(f"bamboo_stairs"), _p(f"bamboo_mosaic_stairs"),
            _p(f"bamboo_slab"),   _p(f"bamboo_mosaic_slab"),
            _p(f"bamboo_fence"),  _p(f"bamboo_fence_gate"),
            _p(f"bamboo_door"),   _p(f"bamboo_trapdoor"),
            _p(f"bamboo_button"), _p(f"bamboo_pressure_plate"),
            _p(f"bamboo_sign"),   _p(f"bamboo_hanging_sign"),
        ]
    return [
        _p(f"{t}_log"),        _p(f"{t}_wood"),
        _p(f"stripped_{t}_log"), _p(f"stripped_{t}_wood"),
        _p(f"{t}_planks"),     _p(f"{t}_leaves"),
        _p(f"{t}_stairs"),     _p(f"{t}_slab"),
        _p(f"{t}_fence"),      _p(f"{t}_fence_gate"),
        _p(f"{t}_door"),       _p(f"{t}_trapdoor"),
        _p(f"{t}_button"),     _p(f"{t}_pressure_plate"),
        _p(f"{t}_sign"),       _p(f"{t}_wall_sign"),
        _p(f"{t}_hanging_sign"),
    ]


def _nether_wood(t: str) -> list[str]:
    return [
        _p(f"{t}_stem"),   _p(f"{t}_hyphae"),
        _p(f"stripped_{t}_stem"), _p(f"stripped_{t}_hyphae"),
        _p(f"{t}_planks"),
        _p(f"{t}_stairs"), _p(f"{t}_slab"),
        _p(f"{t}_fence"),  _p(f"{t}_fence_gate"),
        _p(f"{t}_door"),   _p(f"{t}_trapdoor"),
        _p(f"{t}_button"), _p(f"{t}_pressure_plate"),
        _p(f"{t}_sign"),
    ]


_BLOCKS_RAW: list[str] = [
    # ── Air ───────────────────────────────────────────────────────────────────
    "minecraft:air", "minecraft:cave_air", "minecraft:void_air",

    # ── Soil ──────────────────────────────────────────────────────────────────
    "minecraft:dirt", "minecraft:grass_block", "minecraft:coarse_dirt",
    "minecraft:podzol", "minecraft:mycelium", "minecraft:rooted_dirt",
    "minecraft:mud", "minecraft:muddy_mangrove_roots", "minecraft:farmland",
    "minecraft:dirt_path",

    # ── Sand / gravel ─────────────────────────────────────────────────────────
    "minecraft:sand", "minecraft:red_sand", "minecraft:gravel",
    "minecraft:suspicious_sand", "minecraft:suspicious_gravel",

    # ── Stone & derivatives ───────────────────────────────────────────────────
    "minecraft:stone", "minecraft:granite", "minecraft:polished_granite",
    "minecraft:diorite", "minecraft:polished_diorite",
    "minecraft:andesite", "minecraft:polished_andesite",
    "minecraft:cobblestone", "minecraft:mossy_cobblestone",
    "minecraft:stone_bricks", "minecraft:mossy_stone_bricks",
    "minecraft:cracked_stone_bricks", "minecraft:chiseled_stone_bricks",
    "minecraft:smooth_stone", "minecraft:infested_stone",
    # stairs / slabs / walls
    "minecraft:stone_stairs", "minecraft:stone_slab",
    "minecraft:cobblestone_stairs", "minecraft:cobblestone_slab",
    "minecraft:mossy_cobblestone_stairs", "minecraft:mossy_cobblestone_slab",
    "minecraft:stone_brick_stairs", "minecraft:stone_brick_slab",
    "minecraft:mossy_stone_brick_stairs", "minecraft:mossy_stone_brick_slab",
    "minecraft:andesite_stairs", "minecraft:andesite_slab",
    "minecraft:polished_andesite_stairs", "minecraft:polished_andesite_slab",
    "minecraft:diorite_stairs", "minecraft:diorite_slab",
    "minecraft:polished_diorite_stairs", "minecraft:polished_diorite_slab",
    "minecraft:granite_stairs", "minecraft:granite_slab",
    "minecraft:polished_granite_stairs", "minecraft:polished_granite_slab",
    "minecraft:cobblestone_wall", "minecraft:mossy_cobblestone_wall",
    "minecraft:stone_brick_wall", "minecraft:mossy_stone_brick_wall",
    "minecraft:andesite_wall", "minecraft:diorite_wall", "minecraft:granite_wall",
    "minecraft:stone_wall",
    # stone buttons/pressure plates
    "minecraft:stone_button", "minecraft:stone_pressure_plate",
    "minecraft:polished_blackstone_button", "minecraft:polished_blackstone_pressure_plate",
    "minecraft:heavy_weighted_pressure_plate", "minecraft:light_weighted_pressure_plate",

    # ── Bricks ────────────────────────────────────────────────────────────────
    "minecraft:bricks", "minecraft:brick_stairs", "minecraft:brick_slab",
    "minecraft:brick_wall",
    "minecraft:mud_bricks", "minecraft:mud_brick_stairs", "minecraft:mud_brick_slab",
    "minecraft:mud_brick_wall",

    # ── Sandstone ────────────────────────────────────────────────────────────
    "minecraft:sandstone", "minecraft:chiseled_sandstone",
    "minecraft:cut_sandstone", "minecraft:smooth_sandstone",
    "minecraft:sandstone_stairs", "minecraft:sandstone_slab",
    "minecraft:smooth_sandstone_stairs", "minecraft:smooth_sandstone_slab",
    "minecraft:cut_sandstone_slab", "minecraft:sandstone_wall",
    "minecraft:red_sandstone", "minecraft:chiseled_red_sandstone",
    "minecraft:cut_red_sandstone", "minecraft:smooth_red_sandstone",
    "minecraft:red_sandstone_stairs", "minecraft:red_sandstone_slab",
    "minecraft:smooth_red_sandstone_stairs", "minecraft:smooth_red_sandstone_slab",
    "minecraft:cut_red_sandstone_slab", "minecraft:red_sandstone_wall",

    # ── Deepslate ────────────────────────────────────────────────────────────
    "minecraft:deepslate", "minecraft:cobbled_deepslate",
    "minecraft:polished_deepslate", "minecraft:chiseled_deepslate",
    "minecraft:deepslate_bricks", "minecraft:cracked_deepslate_bricks",
    "minecraft:deepslate_tiles", "minecraft:cracked_deepslate_tiles",
    "minecraft:reinforced_deepslate",
    "minecraft:cobbled_deepslate_stairs", "minecraft:cobbled_deepslate_slab", "minecraft:cobbled_deepslate_wall",
    "minecraft:polished_deepslate_stairs", "minecraft:polished_deepslate_slab", "minecraft:polished_deepslate_wall",
    "minecraft:deepslate_brick_stairs", "minecraft:deepslate_brick_slab", "minecraft:deepslate_brick_wall",
    "minecraft:deepslate_tile_stairs", "minecraft:deepslate_tile_slab", "minecraft:deepslate_tile_wall",

    # ── Tuff ─────────────────────────────────────────────────────────────────
    "minecraft:tuff", "minecraft:chiseled_tuff", "minecraft:polished_tuff",
    "minecraft:tuff_bricks", "minecraft:chiseled_tuff_bricks",
    "minecraft:tuff_stairs", "minecraft:tuff_slab", "minecraft:tuff_wall",
    "minecraft:polished_tuff_stairs", "minecraft:polished_tuff_slab", "minecraft:polished_tuff_wall",
    "minecraft:tuff_brick_stairs", "minecraft:tuff_brick_slab", "minecraft:tuff_brick_wall",

    # ── Ores ─────────────────────────────────────────────────────────────────
    "minecraft:coal_ore", "minecraft:deepslate_coal_ore", "minecraft:coal_block",
    "minecraft:iron_ore", "minecraft:deepslate_iron_ore",
    "minecraft:iron_block", "minecraft:raw_iron_block",
    "minecraft:gold_ore", "minecraft:deepslate_gold_ore",
    "minecraft:gold_block", "minecraft:raw_gold_block",
    "minecraft:diamond_ore", "minecraft:deepslate_diamond_ore", "minecraft:diamond_block",
    "minecraft:emerald_ore", "minecraft:deepslate_emerald_ore", "minecraft:emerald_block",
    "minecraft:lapis_ore", "minecraft:deepslate_lapis_ore", "minecraft:lapis_block",
    "minecraft:redstone_ore", "minecraft:deepslate_redstone_ore", "minecraft:redstone_block",
    "minecraft:nether_gold_ore", "minecraft:nether_quartz_ore",
    "minecraft:ancient_debris", "minecraft:netherite_block",
    "minecraft:copper_ore", "minecraft:deepslate_copper_ore",
    "minecraft:raw_copper_block", "minecraft:raw_iron_block", "minecraft:raw_gold_block",

    # ── Copper ────────────────────────────────────────────────────────────────
    "minecraft:copper_block", "minecraft:exposed_copper",
    "minecraft:weathered_copper", "minecraft:oxidized_copper",
    "minecraft:waxed_copper_block", "minecraft:waxed_exposed_copper",
    "minecraft:waxed_weathered_copper", "minecraft:waxed_oxidized_copper",
    "minecraft:cut_copper", "minecraft:exposed_cut_copper",
    "minecraft:weathered_cut_copper", "minecraft:oxidized_cut_copper",
    "minecraft:waxed_cut_copper", "minecraft:waxed_exposed_cut_copper",
    "minecraft:waxed_weathered_cut_copper", "minecraft:waxed_oxidized_cut_copper",
    "minecraft:cut_copper_stairs", "minecraft:cut_copper_slab",
    "minecraft:exposed_cut_copper_stairs", "minecraft:exposed_cut_copper_slab",
    "minecraft:weathered_cut_copper_stairs", "minecraft:weathered_cut_copper_slab",
    "minecraft:oxidized_cut_copper_stairs", "minecraft:oxidized_cut_copper_slab",
    "minecraft:waxed_cut_copper_stairs", "minecraft:waxed_cut_copper_slab",
    "minecraft:waxed_exposed_cut_copper_stairs", "minecraft:waxed_exposed_cut_copper_slab",
    "minecraft:waxed_weathered_cut_copper_stairs", "minecraft:waxed_weathered_cut_copper_slab",
    "minecraft:waxed_oxidized_cut_copper_stairs", "minecraft:waxed_oxidized_cut_copper_slab",
    "minecraft:chiseled_copper", "minecraft:exposed_chiseled_copper",
    "minecraft:weathered_chiseled_copper", "minecraft:oxidized_chiseled_copper",
    "minecraft:waxed_chiseled_copper", "minecraft:waxed_exposed_chiseled_copper",
    "minecraft:waxed_weathered_chiseled_copper", "minecraft:waxed_oxidized_chiseled_copper",
    "minecraft:copper_grate", "minecraft:exposed_copper_grate",
    "minecraft:weathered_copper_grate", "minecraft:oxidized_copper_grate",
    "minecraft:waxed_copper_grate", "minecraft:waxed_exposed_copper_grate",
    "minecraft:waxed_weathered_copper_grate", "minecraft:waxed_oxidized_copper_grate",
    "minecraft:copper_bulb", "minecraft:exposed_copper_bulb",
    "minecraft:weathered_copper_bulb", "minecraft:oxidized_copper_bulb",
    "minecraft:waxed_copper_bulb", "minecraft:waxed_exposed_copper_bulb",
    "minecraft:waxed_weathered_copper_bulb", "minecraft:waxed_oxidized_copper_bulb",
    "minecraft:copper_door", "minecraft:exposed_copper_door",
    "minecraft:weathered_copper_door", "minecraft:oxidized_copper_door",
    "minecraft:waxed_copper_door", "minecraft:waxed_exposed_copper_door",
    "minecraft:waxed_weathered_copper_door", "minecraft:waxed_oxidized_copper_door",
    "minecraft:copper_trapdoor", "minecraft:exposed_copper_trapdoor",
    "minecraft:weathered_copper_trapdoor", "minecraft:oxidized_copper_trapdoor",
    "minecraft:waxed_copper_trapdoor", "minecraft:waxed_exposed_copper_trapdoor",
    "minecraft:waxed_weathered_copper_trapdoor", "minecraft:waxed_oxidized_copper_trapdoor",

    # ── Quartz ────────────────────────────────────────────────────────────────
    "minecraft:quartz_block", "minecraft:chiseled_quartz_block",
    "minecraft:quartz_pillar", "minecraft:smooth_quartz", "minecraft:quartz_bricks",
    "minecraft:quartz_stairs", "minecraft:quartz_slab",
    "minecraft:smooth_quartz_stairs", "minecraft:smooth_quartz_slab",

    # ── Prismarine ────────────────────────────────────────────────────────────
    "minecraft:prismarine", "minecraft:prismarine_bricks", "minecraft:dark_prismarine",
    "minecraft:sea_lantern",
    "minecraft:prismarine_stairs", "minecraft:prismarine_slab", "minecraft:prismarine_wall",
    "minecraft:prismarine_brick_stairs", "minecraft:prismarine_brick_slab",
    "minecraft:dark_prismarine_stairs", "minecraft:dark_prismarine_slab",

    # ── End ───────────────────────────────────────────────────────────────────
    "minecraft:end_stone", "minecraft:end_stone_bricks",
    "minecraft:purpur_block", "minecraft:purpur_pillar",
    "minecraft:end_portal_frame",
    "minecraft:end_stone_brick_stairs", "minecraft:end_stone_brick_slab",
    "minecraft:end_stone_brick_wall",
    "minecraft:purpur_stairs", "minecraft:purpur_slab",

    # ── Nether ────────────────────────────────────────────────────────────────
    "minecraft:netherrack", "minecraft:nether_bricks",
    "minecraft:red_nether_bricks", "minecraft:chiseled_nether_bricks",
    "minecraft:cracked_nether_bricks",
    "minecraft:nether_brick_fence",
    "minecraft:nether_brick_stairs", "minecraft:nether_brick_slab",
    "minecraft:nether_brick_wall",
    "minecraft:red_nether_brick_stairs", "minecraft:red_nether_brick_slab",
    "minecraft:red_nether_brick_wall",
    "minecraft:soul_sand", "minecraft:soul_soil",
    "minecraft:glowstone", "minecraft:obsidian", "minecraft:crying_obsidian",
    "minecraft:magma_block", "minecraft:shroomlight",
    "minecraft:basalt", "minecraft:polished_basalt", "minecraft:smooth_basalt",
    "minecraft:blackstone", "minecraft:gilded_blackstone",
    "minecraft:polished_blackstone", "minecraft:chiseled_polished_blackstone",
    "minecraft:polished_blackstone_bricks", "minecraft:cracked_polished_blackstone_bricks",
    "minecraft:blackstone_stairs", "minecraft:blackstone_slab", "minecraft:blackstone_wall",
    "minecraft:polished_blackstone_stairs", "minecraft:polished_blackstone_slab",
    "minecraft:polished_blackstone_wall",
    "minecraft:polished_blackstone_brick_stairs", "minecraft:polished_blackstone_brick_slab",
    "minecraft:polished_blackstone_brick_wall",
    "minecraft:nether_wart_block", "minecraft:warped_wart_block",
    "minecraft:crimson_nylium", "minecraft:warped_nylium",

    # ── Glass ─────────────────────────────────────────────────────────────────
    "minecraft:glass", "minecraft:glass_pane", "minecraft:tinted_glass",
    "minecraft:iron_bars",
] + [
    _p(f"{c}_stained_glass") for c in _COLOURS
] + [
    _p(f"{c}_stained_glass_pane") for c in _COLOURS
] + [

    # ── Wool ─────────────────────────────────────────────────────────────────
] + [_p(f"{c}_wool") for c in _COLOURS] + [

    # ── Carpet ───────────────────────────────────────────────────────────────
] + [_p(f"{c}_carpet") for c in _COLOURS] + [

    # ── Terracotta ───────────────────────────────────────────────────────────
    "minecraft:terracotta",
] + [_p(f"{c}_terracotta") for c in _COLOURS] + [
] + [_p(f"{c}_glazed_terracotta") for c in _COLOURS] + [

    # ── Concrete ─────────────────────────────────────────────────────────────
] + [_p(f"{c}_concrete") for c in _COLOURS] + [
] + [_p(f"{c}_concrete_powder") for c in _COLOURS] + [

    # ── Shulker boxes ────────────────────────────────────────────────────────
    "minecraft:shulker_box",
] + [_p(f"{c}_shulker_box") for c in _COLOURS] + [

    # ── Banners ──────────────────────────────────────────────────────────────
] + [_p(f"{c}_banner") for c in _COLOURS] + [
] + [_p(f"{c}_wall_banner") for c in _COLOURS] + [

    # ── Beds ─────────────────────────────────────────────────────────────────
] + [_p(f"{c}_bed") for c in _COLOURS] + [

    # ── Candles ──────────────────────────────────────────────────────────────
    "minecraft:candle",
] + [_p(f"{c}_candle") for c in _COLOURS] + [

] + [block for t in _WOOD_TYPES  for block in _wood_blocks(t)] + \
    [block for t in _NETHER_WOOD for block in _nether_wood(t)] + [

    # ── Snow / Ice ───────────────────────────────────────────────────────────
    "minecraft:snow", "minecraft:snow_block", "minecraft:powder_snow",
    "minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice",

    # ── Water / lava ─────────────────────────────────────────────────────────
    "minecraft:water", "minecraft:lava",

    # ── Functional blocks ────────────────────────────────────────────────────
    "minecraft:crafting_table", "minecraft:furnace",
    "minecraft:blast_furnace", "minecraft:smoker",
    "minecraft:chest", "minecraft:trapped_chest", "minecraft:ender_chest",
    "minecraft:barrel",
    "minecraft:bookshelf", "minecraft:chiseled_bookshelf", "minecraft:lectern",
    "minecraft:jukebox", "minecraft:note_block", "minecraft:tnt",
    "minecraft:dispenser", "minecraft:dropper", "minecraft:hopper",
    "minecraft:observer", "minecraft:piston", "minecraft:sticky_piston",
    "minecraft:beacon", "minecraft:enchanting_table",
    "minecraft:brewing_stand", "minecraft:cauldron",
    "minecraft:grindstone", "minecraft:stonecutter",
    "minecraft:cartography_table", "minecraft:fletching_table",
    "minecraft:smithing_table", "minecraft:loom", "minecraft:composter",
    "minecraft:crafter",

    # ── Redstone ─────────────────────────────────────────────────────────────
    "minecraft:redstone_lamp", "minecraft:redstone_torch",
    "minecraft:repeater", "minecraft:comparator", "minecraft:lever",
    "minecraft:daylight_detector", "minecraft:target",
    "minecraft:lightning_rod", "minecraft:tripwire_hook",

    # ── Lights ───────────────────────────────────────────────────────────────
    "minecraft:lantern", "minecraft:soul_lantern",
    "minecraft:campfire", "minecraft:soul_campfire",
    "minecraft:torch", "minecraft:soul_torch",
    "minecraft:sea_lantern", "minecraft:glowstone",
    "minecraft:ochre_froglight", "minecraft:verdant_froglight",
    "minecraft:pearlescent_froglight",

    # ── Metal / iron ─────────────────────────────────────────────────────────
    "minecraft:iron_block", "minecraft:iron_door", "minecraft:iron_trapdoor",
    "minecraft:iron_bars", "minecraft:chain",

    # ── Misc building ────────────────────────────────────────────────────────
    "minecraft:sponge", "minecraft:wet_sponge",
    "minecraft:hay_block", "minecraft:dried_kelp_block",
    "minecraft:slime_block", "minecraft:honey_block",
    "minecraft:honeycomb_block", "minecraft:bee_nest", "minecraft:beehive",
    "minecraft:bedrock",
    "minecraft:lodestone", "minecraft:respawn_anchor",

    # ── Amethyst / crystals ──────────────────────────────────────────────────
    "minecraft:amethyst_block", "minecraft:budding_amethyst",
    "minecraft:calcite", "minecraft:dripstone_block",

    # ── Mushroom blocks ──────────────────────────────────────────────────────
    "minecraft:brown_mushroom_block", "minecraft:red_mushroom_block",
    "minecraft:mushroom_stem",

    # ── Coral blocks ─────────────────────────────────────────────────────────
    "minecraft:tube_coral_block", "minecraft:brain_coral_block",
    "minecraft:bubble_coral_block", "minecraft:fire_coral_block",
    "minecraft:horn_coral_block",
    "minecraft:dead_tube_coral_block", "minecraft:dead_brain_coral_block",
    "minecraft:dead_bubble_coral_block", "minecraft:dead_fire_coral_block",
    "minecraft:dead_horn_coral_block",

    # ── Trial chambers (1.21) ─────────────────────────────────────────────────
    "minecraft:trial_spawner", "minecraft:vault", "minecraft:heavy_core",

    # ── Pale Garden (1.21.2) ─────────────────────────────────────────────────
    "minecraft:pale_moss_block", "minecraft:pale_moss_carpet",
    "minecraft:pale_hanging_moss",
    "minecraft:resin_block", "minecraft:resin_bricks",
    "minecraft:resin_brick_stairs", "minecraft:resin_brick_slab",
    "minecraft:resin_brick_wall", "minecraft:chiseled_resin_bricks",

    # ── Plants / decor (included so users can paint them) ────────────────────
    "minecraft:cactus", "minecraft:sugar_cane",
    "minecraft:pumpkin", "minecraft:carved_pumpkin", "minecraft:jack_o_lantern",
    "minecraft:melon",
    "minecraft:vine", "minecraft:lily_pad",
    "minecraft:flower_pot",
]

# De-duplicate, sort, expose as tuple
ALL_BLOCK_IDS: tuple[str, ...] = tuple(sorted(set(_BLOCKS_RAW)))
