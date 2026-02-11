"""
Block gradient mapping system for accurate cross-version conversion.
Uses color analysis and block categories for precise matching.
"""

from pathlib import Path
from typing import Dict, Set, Tuple, List, Optional
import json

# Block categories for organized mapping
BLOCK_CATEGORIES = {
    "wood_logs": [
        "oak_log", "birch_log", "spruce_log", "jungle_log", "acacia_log", "dark_oak_log",
        "cherry_log", "cherry_wood", "mangrove_log", "mangrove_wood", "crimson_stem", "warped_stem", "bamboo_block",
        "oak_wood", "birch_wood", "spruce_wood", "jungle_wood", "acacia_wood", "dark_oak_wood",
        "crimson_hyphae", "warped_hyphae",
        "stripped_oak_log", "stripped_birch_log", "stripped_spruce_log", "stripped_jungle_log", "stripped_acacia_log",
        "stripped_dark_oak_log", "stripped_cherry_log", "stripped_mangrove_log", "stripped_crimson_stem",
        "stripped_warped_stem", "stripped_oak_wood", "stripped_birch_wood", "stripped_spruce_wood",
        "stripped_jungle_wood", "stripped_acacia_wood", "stripped_dark_oak_wood", "stripped_cherry_wood",
        "stripped_mangrove_wood", "stripped_crimson_hyphae", "stripped_warped_hyphae"
    ],
    "wood_planks": [
        "oak_planks", "birch_planks", "spruce_planks", "jungle_planks", "acacia_planks", "dark_oak_planks",
        "cherry_planks", "mangrove_planks", "crimson_planks", "warped_planks", "bamboo_planks"
    ],
    "leaves": [
        "oak_leaves", "birch_leaves", "spruce_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves",
        "cherry_leaves", "mangrove_leaves", "azalea_leaves", "flowering_azalea_leaves"
    ],
    "stones": [
        "stone", "granite", "diorite", "andesite", "cobblestone", "mossy_cobblestone",
        "smooth_stone", "deepslate", "cobbled_deepslate", "polished_deepslate", "calcite", "tuff",
        "dripstone_block", "smooth_basalt", "basalt", "polished_basalt", "blackstone", "gilded_blackstone",
        "polished_blackstone", "chiseled_polished_blackstone", "cracked_polished_blackstone_bricks"
    ],
    "ores": [
        "coal_ore", "iron_ore", "gold_ore", "redstone_ore", "lapis_ore", "diamond_ore", "emerald_ore",
        "copper_ore", "ancient_debris", "deepslate_coal_ore", "deepslate_iron_ore", "deepslate_gold_ore",
        "deepslate_redstone_ore", "deepslate_lapis_ore", "deepslate_diamond_ore", "deepslate_emerald_ore",
        "deepslate_copper_ore"
    ],
    "dirts": [
        "dirt", "coarse_dirt", "podzol", "mycelium", "grass_block", "dirt_path", "rooted_dirt",
        "mud", "packed_mud", "muddy_mangrove_roots"
    ],
    "sands": [
        "sand", "red_sand", "sandstone", "red_sandstone", "chiseled_sandstone", "cut_sandstone",
        "smooth_sandstone", "chiseled_red_sandstone", "cut_red_sandstone", "smooth_red_sandstone"
    ],
    "concrete": [
        "white_concrete", "orange_concrete", "magenta_concrete", "light_blue_concrete", "yellow_concrete",
        "lime_concrete", "pink_concrete", "gray_concrete", "light_gray_concrete", "cyan_concrete",
        "purple_concrete", "blue_concrete", "brown_concrete", "green_concrete", "red_concrete", "black_concrete"
    ],
    "wool": [
        "white_wool", "orange_wool", "magenta_wool", "light_blue_wool", "yellow_wool", "lime_wool",
        "pink_wool", "gray_wool", "light_gray_wool", "cyan_wool", "purple_wool", "blue_wool",
        "brown_wool", "green_wool", "red_wool", "black_wool"
    ],
    "terracotta": [
        "terracotta", "white_terracotta", "orange_terracotta", "magenta_terracotta", "light_blue_terracotta",
        "yellow_terracotta", "lime_terracotta", "pink_terracotta", "gray_terracotta", "light_gray_terracotta",
        "cyan_terracotta", "purple_terracotta", "blue_terracotta", "brown_terracotta", "green_terracotta",
        "red_terracotta", "black_terracotta"
    ],
    "glass": [
        "glass", "white_stained_glass", "orange_stained_glass", "magenta_stained_glass", "light_blue_stained_glass",
        "yellow_stained_glass", "lime_stained_glass", "pink_stained_glass", "gray_stained_glass",
        "light_gray_stained_glass", "cyan_stained_glass", "purple_stained_glass", "blue_stained_glass",
        "brown_stained_glass", "green_stained_glass", "red_stained_glass", "black_stained_glass"
    ],
    "glass_panes": [
        "glass_pane", "white_stained_glass_pane", "orange_stained_glass_pane", "magenta_stained_glass_pane",
        "light_blue_stained_glass_pane", "yellow_stained_glass_pane", "lime_stained_glass_pane",
        "pink_stained_glass_pane", "gray_stained_glass_pane", "light_gray_stained_glass_pane",
        "cyan_stained_glass_pane", "purple_stained_glass_pane", "blue_stained_glass_pane",
        "brown_stained_glass_pane", "green_stained_glass_pane", "red_stained_glass_pane", "black_stained_glass_pane"
    ],
    "flowers_small": [
        "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip", "white_tulip", "pink_tulip",
        "oxeye_daisy", "cornflower", "lily_of_the_valley", "dandelion", "torchflower"
    ],
    "flowers_tall": [
        "sunflower", "lilac", "rose_bush", "peony", "tall_grass", "large_fern", "pitcher_plant"
    ],
    "mushrooms": [
        "brown_mushroom", "red_mushroom", "brown_mushroom_block", "red_mushroom_block", "mushroom_stem"
    ],
    "plants_small": [
        "grass", "fern", "dead_bush", "seagrass", "sea_pickle", "bamboo", "sugar_cane", "kelp"
    ],
    "plants_water": [
        "lily_pad", "small_dripleaf", "big_dripleaf", "seagrass", "tall_seagrass", "kelp", "kelp_plant"
    ],
    "nether": [
        "netherrack", "soul_sand", "soul_soil", "basalt", "smooth_basalt", "polished_basalt", "blackstone",
        "gilded_blackstone", "polished_blackstone", "chiseled_polished_blackstone", "cracked_polished_blackstone_bricks",
        "nether_bricks", "red_nether_bricks", "chiseled_nether_bricks", "cracked_nether_bricks", "nether_brick_fence",
        "nether_wart_block", "warped_wart_block", "ancient_debris", "shroomlight", "soul_fire", "nether_sprouts"
    ],
    "end": [
        "end_stone", "end_stone_bricks", "purpur_block", "purpur_pillar", "purpur_slab", "purpur_stairs"
    ],
    "quartz": [
        "quartz_block", "quartz_pillar", "chiseled_quartz_block", "quartz_bricks", "quartz_slab", "quartz_stairs",
        "smooth_quartz", "smooth_quartz_slab", "smooth_quartz_stairs"
    ],
    "prismarine": [
        "prismarine", "prismarine_bricks", "dark_prismarine", "prismarine_slab", "prismarine_stairs", "prismarine_wall"
    ],
    "redstone": [
        "redstone_block", "redstone_lamp", "redstone_torch", "redstone_wire", "repeater", "comparator",
        "piston", "sticky_piston", "observer", "hopper", "dropper", "dispenser", "note_block", "target",
        "lectern", "daylight_detector", "redstone_block"
    ],
    "storage": [
        "chest", "trapped_chest", "ender_chest", "barrel", "bookshelf", "shulker_box", "white_shulker_box",
        "orange_shulker_box", "magenta_shulker_box", "light_blue_shulker_box", "yellow_shulker_box",
        "lime_shulker_box", "pink_shulker_box", "gray_shulker_box", "light_gray_shulker_box",
        "cyan_shulker_box", "purple_shulker_box", "blue_shulker_box", "brown_shulker_box",
        "green_shulker_box", "red_shulker_box", "black_shulker_box"
    ],
    "ores_blocks": [
        "coal_block", "iron_block", "gold_block", "redstone_block", "lapis_block", "diamond_block",
        "emerald_block", "netherite_block", "copper_block", "exposed_copper", "weathered_copper",
        "oxidized_copper", "cut_copper", "exposed_cut_copper", "weathered_cut_copper", "oxidized_cut_copper"
    ],
    "amethyst": [
        "amethyst_block", "amethyst_cluster", "large_amethyst_bud", "medium_amethyst_bud", "small_amethyst_bud",
        "budding_amethyst", "calcite"
    ],
    "sculk": [
        "sculk", "sculk_catalyst", "sculk_shrieker", "sculk_sensor", "sculk_vein"
    ],
    "copper": [
        "copper_block", "exposed_copper", "weathered_copper", "oxidized_copper", "cut_copper",
        "exposed_cut_copper", "weathered_cut_copper", "oxidized_cut_copper"
    ],
    "copper_stairs": [
        "cut_copper_stairs", "exposed_cut_copper_stairs", "weathered_cut_copper_stairs", "oxidized_cut_copper_stairs"
    ],
    "copper_slabs": [
        "cut_copper_slab", "exposed_cut_copper_slab", "weathered_cut_copper_slab", "oxidized_cut_copper_slab"
    ],
    "fences": [
        "oak_fence", "birch_fence", "spruce_fence", "jungle_fence", "acacia_fence", "dark_oak_fence",
        "cherry_fence", "mangrove_fence", "crimson_fence", "warped_fence", "bamboo_fence", "nether_brick_fence"
    ],
    "fence_gates": [
        "oak_fence_gate", "birch_fence_gate", "spruce_fence_gate", "jungle_fence_gate", "acacia_fence_gate",
        "dark_oak_fence_gate", "cherry_fence_gate", "mangrove_fence_gate", "crimson_fence_gate",
        "warped_fence_gate", "bamboo_fence_gate"
    ],
    "walls": [
        "cobblestone_wall", "mossy_cobblestone_wall", "stone_brick_wall", "mossy_stone_brick_wall",
        "andesite_wall", "diorite_wall", "granite_wall", "sandstone_wall", "red_sandstone_wall",
        "brick_wall", "prismarine_wall", "nether_brick_wall", "red_nether_brick_wall",
        "end_stone_brick_wall", "blackstone_wall", "polished_blackstone_wall", "polished_blackstone_brick_wall",
        "cobbled_deepslate_wall", "polished_deepslate_wall", "deepslate_brick_wall", "deepslate_tile_wall"
    ],
    "trapdoors": [
        "oak_trapdoor", "birch_trapdoor", "spruce_trapdoor", "jungle_trapdoor", "acacia_trapdoor",
        "dark_oak_trapdoor", "cherry_trapdoor", "mangrove_trapdoor", "crimson_trapdoor", "warped_trapdoor",
        "bamboo_trapdoor", "iron_trapdoor"
    ],
    "doors": [
        "oak_door", "birch_door", "spruce_door", "jungle_door", "acacia_door", "dark_oak_door",
        "cherry_door", "mangrove_door", "crimson_door", "warped_door", "bamboo_door", "iron_door"
    ],
    "buttons": [
        "oak_button", "birch_button", "spruce_button", "jungle_button", "acacia_button", "dark_oak_button",
        "cherry_button", "mangrove_button", "crimson_button", "warped_button", "bamboo_button",
        "stone_button", "polished_blackstone_button"
    ],
    "pressure_plates": [
        "oak_pressure_plate", "birch_pressure_plate", "spruce_pressure_plate", "jungle_pressure_plate",
        "acacia_pressure_plate", "dark_oak_pressure_plate", "cherry_pressure_plate", "mangrove_pressure_plate",
        "crimson_pressure_plate", "warped_pressure_plate", "bamboo_pressure_plate", "stone_pressure_plate",
        "polished_blackstone_pressure_plate", "light_weighted_pressure_plate", "heavy_weighted_pressure_plate"
    ],
    "signs": [
        "oak_sign", "birch_sign", "spruce_sign", "jungle_sign", "acacia_sign", "dark_oak_sign",
        "cherry_sign", "mangrove_sign", "crimson_sign", "warped_sign", "bamboo_sign"
    ],
    "wall_signs": [
        "oak_wall_sign", "birch_wall_sign", "spruce_wall_sign", "jungle_wall_sign", "acacia_wall_sign",
        "dark_oak_wall_sign", "cherry_wall_sign", "mangrove_wall_sign", "crimson_wall_sign",
        "warped_wall_sign", "bamboo_wall_sign"
    ],
    "hanging_signs": [
        "oak_hanging_sign", "birch_hanging_sign", "spruce_hanging_sign", "jungle_hanging_sign",
        "acacia_hanging_sign", "dark_oak_hanging_sign", "cherry_hanging_sign", "mangrove_hanging_sign",
        "crimson_hanging_sign", "warped_hanging_sign", "bamboo_hanging_sign"
    ],
    "wall_hanging_signs": [
        "oak_wall_hanging_sign", "birch_wall_hanging_sign", "spruce_wall_hanging_sign", "jungle_wall_hanging_sign",
        "acacia_wall_hanging_sign", "dark_oak_wall_hanging_sign", "cherry_wall_hanging_sign",
        "mangrove_wall_hanging_sign", "crimson_wall_hanging_sign", "warped_wall_hanging_sign",
        "bamboo_wall_hanging_sign"
    ],
    "stairs": [
        "oak_stairs", "birch_stairs", "spruce_stairs", "jungle_stairs", "acacia_stairs", "dark_oak_stairs",
        "cherry_stairs", "mangrove_stairs", "crimson_stairs", "warped_stairs", "bamboo_stairs",
        "stone_stairs", "granite_stairs", "diorite_stairs", "andesite_stairs", "cobblestone_stairs",
        "mossy_cobblestone_stairs", "stone_brick_stairs", "mossy_stone_brick_stairs",
        "brick_stairs", "sandstone_stairs", "smooth_sandstone_stairs", "red_sandstone_stairs",
        "smooth_red_sandstone_stairs", "nether_brick_stairs", "red_nether_brick_stairs",
        "purpur_stairs", "quartz_stairs", "smooth_quartz_stairs", "prismarine_stairs",
        "prismarine_brick_stairs", "dark_prismarine_stairs", "blackstone_stairs",
        "polished_blackstone_stairs", "polished_blackstone_brick_stairs"
    ],
    "slabs": [
        "oak_slab", "birch_slab", "spruce_slab", "jungle_slab", "acacia_slab", "dark_oak_slab",
        "cherry_slab", "mangrove_slab", "crimson_slab", "warped_slab", "bamboo_slab",
        "stone_slab", "granite_slab", "diorite_slab", "andesite_slab", "cobblestone_slab",
        "mossy_cobblestone_slab", "stone_brick_slab", "mossy_stone_brick_slab",
        "brick_slab", "sandstone_slab", "smooth_sandstone_slab", "red_sandstone_slab",
        "smooth_red_sandstone_slab", "nether_brick_slab", "red_nether_brick_slab",
        "purpur_slab", "quartz_slab", "smooth_quartz_slab", "prismarine_slab",
        "prismarine_brick_slab", "dark_prismarine_slab", "blackstone_slab",
        "polished_blackstone_slab", "polished_blackstone_brick_slab"
    ],
    "light_sources": [
        "torch", "wall_torch", "redstone_torch", "redstone_wall_torch", "soul_torch", "soul_wall_torch",
        "lantern", "soul_lantern", "glowstone", "sea_lantern", "shroomlight", "end_rod",
        "redstone_lamp", "jack_o_lantern", "ochre_froglight", "verdant_froglight", "pearlescent_froglight",
        "candle", "white_candle", "orange_candle", "magenta_candle", "light_blue_candle",
        "yellow_candle", "lime_candle", "pink_candle", "gray_candle", "light_gray_candle",
        "cyan_candle", "purple_candle", "blue_candle", "brown_candle", "green_candle",
        "red_candle", "black_candle"
    ],
    "banners": [
        "white_banner", "orange_banner", "magenta_banner", "light_blue_banner", "yellow_banner",
        "lime_banner", "pink_banner", "gray_banner", "light_gray_banner", "cyan_banner",
        "purple_banner", "blue_banner", "brown_banner", "green_banner", "red_banner", "black_banner"
    ],
    "wall_banners": [
        "white_wall_banner", "orange_wall_banner", "magenta_wall_banner", "light_blue_wall_banner",
        "yellow_wall_banner", "lime_wall_banner", "pink_wall_banner", "gray_wall_banner",
        "light_gray_wall_banner", "cyan_wall_banner", "purple_wall_banner", "blue_wall_banner",
        "brown_wall_banner", "green_wall_banner", "red_wall_banner", "black_wall_banner"
    ],
    "carpets": [
        "white_carpet", "orange_carpet", "magenta_carpet", "light_blue_carpet", "yellow_carpet",
        "lime_carpet", "pink_carpet", "gray_carpet", "light_gray_carpet", "cyan_carpet",
        "purple_carpet", "blue_carpet", "brown_carpet", "green_carpet", "red_carpet", "black_carpet"
    ],
    "beds": [
        "white_bed", "orange_bed", "magenta_bed", "light_blue_bed", "yellow_bed", "lime_bed",
        "pink_bed", "gray_bed", "light_gray_bed", "cyan_bed", "purple_bed", "blue_bed",
        "brown_bed", "green_bed", "red_bed", "black_bed"
    ],
    "candles": [
        "candle", "white_candle", "orange_candle", "magenta_candle", "light_blue_candle",
        "yellow_candle", "lime_candle", "pink_candle", "gray_candle", "light_gray_candle",
        "cyan_candle", "purple_candle", "blue_candle", "brown_candle", "green_candle",
        "red_candle", "black_candle"
    ],
    "candle_cakes": [
        "candle_cake", "white_candle_cake", "orange_candle_cake", "magenta_candle_cake",
        "light_blue_candle_cake", "yellow_candle_cake", "lime_candle_cake", "pink_candle_cake",
        "gray_candle_cake", "light_gray_candle_cake", "cyan_candle_cake", "purple_candle_cake",
        "blue_candle_cake", "brown_candle_cake", "green_candle_cake", "red_candle_cake", "black_candle_cake"
    ],
    "coral": [
        "tube_coral", "brain_coral", "bubble_coral", "fire_coral", "horn_coral",
        "tube_coral_block", "brain_coral_block", "bubble_coral_block", "fire_coral_block", "horn_coral_block",
        "dead_tube_coral_block", "dead_brain_coral_block", "dead_bubble_coral_block", "dead_fire_coral_block", "dead_horn_coral_block"
    ],
    "coral_plants": [
        "tube_coral", "brain_coral", "bubble_coral", "fire_coral", "horn_coral",
        "dead_tube_coral", "dead_brain_coral", "dead_bubble_coral", "dead_fire_coral", "dead_horn_coral"
    ],
    "coral_fans": [
        "tube_coral_fan", "brain_coral_fan", "bubble_coral_fan", "fire_coral_fan", "horn_coral_fan",
        "dead_tube_coral_fan", "dead_brain_coral_fan", "dead_bubble_coral_fan", "dead_fire_coral_fan", "dead_horn_coral_fan"
    ],
    "coral_wall_fans": [
        "tube_coral_wall_fan", "brain_coral_wall_fan", "bubble_coral_wall_fan", "fire_coral_wall_fan", "horn_coral_wall_fan",
        "dead_tube_coral_wall_fan", "dead_brain_coral_wall_fan", "dead_bubble_coral_wall_fan", "dead_fire_coral_wall_fan", "dead_horn_coral_wall_fan"
    ]
}

# Color gradients for similar materials
COLOR_GRADIENTS = {
    "wood_oak": ("#8B7355", "#6B4423", "#5D3A1A"),
    "wood_birch": ("#F5DEB3", "#DEB887", "#D2B48C"),
    "wood_spruce": ("#4A3728", "#3D2B1F", "#2F1F16"),
    "wood_jungle": ("#5C4033", "#4A3426", "#3D2B1F"),
    "wood_acacia": ("#8B4513", "#A0522D", "#CD853F"),
    "wood_dark_oak": ("#2F1F16", "#3D2B1F", "#1A110D"),
    "wood_cherry": ("#5C4033", "#8B7355", "#A0522D"),
    "wood_mangrove": ("#6B4423", "#8B4513", "#5D3A1A"),
    "wood_crimson": ("#8B0000", "#A0522D", "#CD5C5C"),
    "wood_warped": ("#2F4F4F", "#008B8B", "#20B2AA"),
    "stone_gray": ("#808080", "#696969", "#A9A9A9"),
    "stone_brown": ("#8B7355", "#A0522D", "#CD853F"),
    "stone_black": ("#2F2F2F", "#1C1C1C", "#000000"),
    "sand_yellow": ("#F4A460", "#DEB887", "#D2B48C"),
    "sand_red": ("#CD853F", "#A0522D", "#8B4513"),
    "dirt_brown": ("#8B4513", "#A0522D", "#CD853F"),
    "grass_green": ("#228B22", "#32CD32", "#006400"),
    "leaves_green": ("#228B22", "#006400", "#32CD32"),
    "leaves_pink": ("#FFB6C1", "#FF69B4", "#FFC0CB"),
    "water_blue": ("#4169E1", "#1E90FF", "#00BFFF"),
    "lava_orange": ("#FF4500", "#FF6347", "#FFD700"),
    "ice_blue": ("#ADD8E6", "#B0E0E6", "#E0FFFF"),
    "snow_white": ("#FFFAFA", "#F0F8FF", "#FFFFFF"),
    "wool_white": ("#FFFAFA", "#FFFFFF", "#F5F5F5"),
    "wool_orange": ("#FFA500", "#FF8C00", "#FFD700"),
    "wool_magenta": ("#FF00FF", "#DA70D6", "#DDA0DD"),
    "wool_light_blue": ("#ADD8E6", "#87CEEB", "#B0E0E6"),
    "wool_yellow": ("#FFFF00", "#FFD700", "#FFA500"),
    "wool_lime": ("#00FF00", "#32CD32", "#00FA9A"),
    "wool_pink": ("#FFB6C1", "#FF69B4", "#FFC0CB"),
    "wool_gray": ("#808080", "#696969", "#A9A9A9"),
    "wool_light_gray": ("#D3D3D3", "#C0C0C0", "#DCDCDC"),
    "wool_cyan": ("#00FFFF", "#00CED1", "#20B2AA"),
    "wool_purple": ("#800080", "#9370DB", "#BA55D3"),
    "wool_blue": ("#0000FF", "#4169E1", "#00008B"),
    "wool_brown": ("#8B4513", "#A0522D", "#CD853F"),
    "wool_green": ("#008000", "#228B22", "#006400"),
    "wool_red": ("#FF0000", "#DC143C", "#B22222"),
    "wool_black": ("#000000", "#2F2F2F", "#1C1C1C"),
    "concrete_white": ("#F5F5F5", "#FFFFFF", "#FFFAFA"),
    "concrete_orange": ("#FFA500", "#FF8C00", "#FFD700"),
    "concrete_magenta": ("#FF00FF", "#DA70D6", "#DDA0DD"),
    "concrete_light_blue": ("#87CEEB", "#ADD8E6", "#B0E0E6"),
    "concrete_yellow": ("#FFFF00", "#FFD700", "#FFA500"),
    "concrete_lime": ("#00FF00", "#32CD32", "#00FA9A"),
    "concrete_pink": ("#FF69B4", "#FFB6C1", "#FFC0CB"),
    "concrete_gray": ("#808080", "#696969", "#A9A9A9"),
    "concrete_light_gray": ("#D3D3D3", "#C0C0C0", "#DCDCDC"),
    "concrete_cyan": ("#00CED1", "#00FFFF", "#20B2AA"),
    "concrete_purple": ("#9370DB", "#800080", "#BA55D3"),
    "concrete_blue": ("#4169E1", "#0000FF", "#00008B"),
    "concrete_brown": ("#8B4513", "#A0522D", "#CD853F"),
    "concrete_green": ("#228B22", "#008000", "#006400"),
    "concrete_red": ("#DC143C", "#FF0000", "#B22222"),
    "concrete_black": ("#2F2F2F", "#000000", "#1C1C1C"),
    "terracotta_orange": ("#CD853F", "#D2691E", "#A0522D"),
    "terracotta_white": ("#F5DEB3", "#F5F5DC", "#FFF8DC"),
    "terracotta_light_gray": ("#D3D3D3", "#C0C0C0", "#A9A9A9"),
    "terracotta_brown": ("#8B4513", "#A0522D", "#CD853F"),
    "redstone_red": ("#FF0000", "#DC143C", "#B22222"),
    "gold_yellow": ("#FFD700", "#FFA500", "#FF8C00"),
    "iron_gray": ("#C0C0C0", "#A9A9A9", "#808080"),
    "diamond_cyan": ("#00CED1", "#40E0D0", "#00FFFF"),
    "emerald_green": ("#50C878", "#00FF7F", "#228B22"),
    "lapis_blue": ("#4169E1", "#0000FF", "#00008B"),
    "coal_black": ("#2F2F2F", "#1C1C1C", "#000000"),
    "quartz_white": ("#FFFAFA", "#F5F5F5", "#FFFFFF"),
    "purpur_pink": ("#DDA0DD", "#DA70D6", "#BA55D3"),
    "prismarine_cyan": ("#20B2AA", "#008B8B", "#00CED1"),
    "prismarine_dark": ("#2F4F4F", "#008B8B", "#20B2AA"),
    "nether_red": ("#8B0000", "#A0522D", "#CD5C5C"),
    "soul_fire_blue": ("#00BFFF", "#1E90FF", "#87CEEB"),
    "amethyst_purple": ("#9966CC", "#9370DB", "#BA55D3"),
    "copper_orange": ("#B87333", "#CD853F", "#D2691E"),
    "copper_green": ("#6B8E23", "#556B2F", "#808000"),
    "sculk_dark": ("#2F4F4F", "#1C1C1C", "#2F2F2F"),
    "froglight_green": ("#90EE90", "#98FB98", "#00FA9A"),
    "froglight_pearlescent": ("#FFB6C1", "#FFC0CB", "#FF69B4"),
    "froglight_verdant": ("#00FF7F", "#32CD32", "#228B22"),
}

# Mapping from block to its color gradient key
BLOCK_TO_GRADIENT = {}

# Build block to gradient mapping
for category, blocks in BLOCK_CATEGORIES.items():
    gradient_key = None
    
    # Determine gradient key based on category
    if category.startswith("wood_"):
        wood_type = category.replace("wood_", "")
        gradient_key = f"wood_{wood_type}"
    elif category == "stones":
        gradient_key = "stone_gray"
    elif category == "ores":
        gradient_key = "stone_gray"
    elif category == "dirts":
        gradient_key = "dirt_brown"
    elif category == "sands":
        gradient_key = "sand_yellow"
    elif category == "concrete":
        # Extract color from block name
        for color in ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", 
                      "gray", "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]:
            if color in category or any(color in b for b in blocks):
                gradient_key = f"concrete_{color}"
                break
    elif category == "wool":
        for color in ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", 
                      "gray", "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]:
            if color in category or any(color in b for b in blocks):
                gradient_key = f"wool_{color}"
                break
    elif category == "terracotta":
        if "orange" in category or any("orange" in b for b in blocks):
            gradient_key = "terracotta_orange"
        elif "white" in category:
            gradient_key = "terracotta_white"
        elif "light_gray" in category:
            gradient_key = "terracotta_light_gray"
        else:
            gradient_key = "terracotta_brown"
    elif category == "glass":
        gradient_key = "ice_blue"  # Default glass is clear/blue
    elif category == "glass_panes":
        gradient_key = "ice_blue"
    elif category == "leaves":
        # Check for cherry leaves
        if any("cherry" in b or "pink" in b for b in blocks):
            gradient_key = "leaves_pink"
        else:
            gradient_key = "leaves_green"
    elif category == "flowers_small" or category == "flowers_tall":
        gradient_key = "grass_green"
    elif category == "plants_small" or category == "plants_water":
        gradient_key = "grass_green"
    elif category == "mushrooms":
        gradient_key = "dirt_brown"
    elif category == "nether":
        gradient_key = "nether_red"
    elif category == "end":
        gradient_key = "purpur_pink"
    elif category == "quartz":
        gradient_key = "quartz_white"
    elif category == "prismarine":
        if "dark" in category:
            gradient_key = "prismarine_dark"
        else:
            gradient_key = "prismarine_cyan"
    elif category == "redstone":
        gradient_key = "redstone_red"
    elif category == "storage":
        gradient_key = "wood_oak"  # Default chests are oak-like
    elif category == "ores_blocks":
        if "coal" in category:
            gradient_key = "coal_black"
        elif "iron" in category:
            gradient_key = "iron_gray"
        elif "gold" in category:
            gradient_key = "gold_yellow"
        elif "redstone" in category:
            gradient_key = "redstone_red"
        elif "lapis" in category:
            gradient_key = "lapis_blue"
        elif "diamond" in category:
            gradient_key = "diamond_cyan"
        elif "emerald" in category:
            gradient_key = "emerald_green"
        elif "netherite" in category:
            gradient_key = "stone_black"
        elif "copper" in category:
            gradient_key = "copper_orange"
    elif category == "amethyst":
        gradient_key = "amethyst_purple"
    elif category == "sculk":
        gradient_key = "sculk_dark"
    elif category == "copper" or category.startswith("copper_"):
        gradient_key = "copper_orange"
    elif category.startswith("fences"):
        gradient_key = "wood_oak"
    elif category.startswith("fence_gates"):
        gradient_key = "wood_oak"
    elif category.startswith("walls"):
        gradient_key = "stone_gray"
    elif category.startswith("trapdoors"):
        gradient_key = "wood_oak"
    elif category.startswith("doors"):
        gradient_key = "wood_oak"
    elif category.startswith("buttons"):
        gradient_key = "wood_oak"
    elif category.startswith("pressure_plates"):
        gradient_key = "wood_oak"
    elif category.startswith("signs") or category.startswith("wall_signs"):
        gradient_key = "wood_oak"
    elif category.startswith("hanging_signs") or category.startswith("wall_hanging_signs"):
        gradient_key = "wood_oak"
    elif category.startswith("banners") or category.startswith("wall_banners"):
        gradient_key = "wool_white"
    elif category.startswith("carpets"):
        gradient_key = "wool_white"
    elif category.startswith("beds"):
        gradient_key = "wool_white"
    elif category.startswith("candles") or category.startswith("candle_cakes"):
        gradient_key = "wool_white"
    elif category.startswith("coral"):
        gradient_key = "water_blue"
    
    # Assign gradient to all blocks in category
    if gradient_key:
        for block in blocks:
            BLOCK_TO_GRADIENT[block] = gradient_key


def get_block_category(block_name: str) -> Optional[str]:
    """Get the category of a block."""
    # Remove minecraft: prefix and properties
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    
    for category, blocks in BLOCK_CATEGORIES.items():
        if block_clean in blocks:
            return category
    return None


def get_block_gradient(block_name: str) -> Optional[str]:
    """Get the color gradient key for a block."""
    # Remove minecraft: prefix and properties
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    return BLOCK_TO_GRADIENT.get(block_clean)


def color_distance(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    """Calculate Euclidean distance between two RGB colors."""
    return sum((a - b) ** 2 for a, b in zip(color1, color2)) ** 0.5


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def find_closest_block_by_color(source_block: str, target_blocks: Set[str]) -> Optional[str]:
    """Find the closest matching block by color gradient."""
    source_gradient = get_block_gradient(source_block)
    if not source_gradient:
        return None
    
    source_colors = COLOR_GRADIENTS.get(source_gradient)
    if not source_colors:
        return None
    
    # Convert source colors to RGB
    source_rgbs = [hex_to_rgb(c) for c in source_colors]
    
    best_match = None
    best_score = float('inf')
    
    for target_block in target_blocks:
        target_gradient = get_block_gradient(target_block)
        if not target_gradient:
            continue
        
        target_colors = COLOR_GRADIENTS.get(target_gradient)
        if not target_colors:
            continue
        
        target_rgbs = [hex_to_rgb(c) for c in target_colors]
        
        # Calculate average color distance
        total_distance = 0
        count = 0
        for src_rgb in source_rgbs:
            for tgt_rgb in target_rgbs:
                total_distance += color_distance(src_rgb, tgt_rgb)
                count += 1
        
        avg_distance = total_distance / count if count > 0 else float('inf')
        
        if avg_distance < best_score:
            best_score = avg_distance
            best_match = target_block
    
    return best_match


def find_best_block_match(source_block: str, target_blocks: Set[str]) -> Optional[str]:
    """
    Find the best matching block using category-based matching with intelligent fallbacks.
    
    Strategy:
    1. Check if source category exists in targets
    2. If yes, return first match from that category
    3. If no, use fallback category mapping
    4. Apply color matching only when needed
    """
    # Clean block name
    source_clean = source_block.replace("minecraft:", "").split("[")[0]
    source_category = get_block_category(source_block)
    
    # Category fallback mappings (when target version doesn't have the same category)
    CATEGORY_FALLBACKS = {
        # New wood types -> oak wood
        "wood_logs": "wood_logs",  # Will find oak_log, etc.
        "wood_planks": "wood_planks",  # Will find oak_planks, etc.
        "stripped_wood_logs": "wood_logs",
        "stripped_wood_planks": "wood_planks",
        
        # New stones -> stone
        "stones": "stones",  # Will find stone, andesite, etc.
        "deepslate": "stones",
        
        # Sculk -> dark blocks
        "sculk": ("stones", "ores_blocks"),  # Prefer stone-like or dark blocks
        
        # Copper -> iron/gold blocks or stone
        "copper": "ores_blocks",
        "copper_stairs": "stairs",
        "copper_slabs": "slabs",
        
        # Froglights -> glowstone/lamp
        "froglight": ("light_sources", "ores_blocks"),
        
        # Amethyst -> quartz/purpur
        "amethyst": ("ores_blocks", "quartz"),
        
        # New leaves -> oak leaves
        "leaves": "leaves",
        
        # New flowers/plants -> grass/flowers
        "flowers_small": ("plants_small", "flowers_small"),
        "flowers_tall": ("plants_small", "flowers_tall"),
        "plants_small": "plants_small",
        "plants_water": "plants_water",
        
        # Concrete/wool/terracotta/glass -> same category (colors should match)
        "concrete": "concrete",
        "wool": "wool",
        "terracotta": "terracotta",
        "glass": "glass",
        "glass_panes": "glass_panes",
        
        # Ores -> ores or stone
        "ores": ("ores", "stones"),
        
        # Dirts -> dirts
        "dirts": "dirts",
        
        # Sands -> sands
        "sands": "sands",
        
        # Nether/End blocks -> similar
        "nether": "nether",
        "end": "end",
        "quartz": "quartz",
        "prismarine": "prismarine",
        
        # Building blocks
        "stairs": "stairs",
        "slabs": "slabs",
        "walls": "walls",
        "fences": "fences",
        "fence_gates": "fence_gates",
        
        # Functional blocks
        "doors": "doors",
        "trapdoors": "trapdoors",
        "buttons": "buttons",
        "pressure_plates": "pressure_plates",
        "signs": "signs",
        "redstone": "redstone",
        "storage": "storage",
        "ores_blocks": "ores_blocks",
        
        # Light sources
        "light_sources": "light_sources",
        
        # Misc
        "mushrooms": "mushrooms",
    }
    
    # Get fallback categories
    if source_category is None:
        fallback_categories = (None,)
    else:
        fallback_categories = CATEGORY_FALLBACKS.get(source_category, (source_category,))
        if not isinstance(fallback_categories, tuple):
            fallback_categories = (fallback_categories,)
    
    # Try each fallback category
    for fallback_cat in fallback_categories:
        # Find blocks in target set that match this category
        matching_blocks = []
        for target in target_blocks:
            target_cat = get_block_category(target)
            if target_cat == fallback_cat:
                matching_blocks.append(target)
        
        if matching_blocks:
            # Choose nearest by gradient color instead of random/first set order.
            source_gradient = get_block_gradient(source_block)
            if source_gradient and source_gradient in COLOR_GRADIENTS:
                source_rgbs = [hex_to_rgb(c) for c in COLOR_GRADIENTS[source_gradient]]

                def block_score(block: str) -> float:
                    target_gradient = get_block_gradient(block)
                    if not target_gradient or target_gradient not in COLOR_GRADIENTS:
                        return float("inf")
                    target_rgbs = [hex_to_rgb(c) for c in COLOR_GRADIENTS[target_gradient]]
                    total_distance = 0.0
                    count = 0
                    for src_rgb in source_rgbs:
                        for tgt_rgb in target_rgbs:
                            total_distance += color_distance(src_rgb, tgt_rgb)
                            count += 1
                    return total_distance / count if count else float("inf")

                matching_blocks.sort(key=lambda b: (block_score(b), b))
                return matching_blocks[0]

            # deterministic fallback
            return sorted(matching_blocks)[0]
    
    # Last resort: try color-based matching across all targets
    return find_closest_block_by_color(source_block, target_blocks)


# Version-specific block availability
VERSION_BLOCKS = {
    "1.16.5": {
        # Wood types available in 1.16.5
        "oak_log", "birch_log", "spruce_log", "jungle_log", "acacia_log", "dark_oak_log",
        "stripped_oak_log", "stripped_birch_log", "stripped_spruce_log", "stripped_jungle_log",
        "stripped_acacia_log", "stripped_dark_oak_log",
        "oak_wood", "birch_wood", "spruce_wood", "jungle_wood", "acacia_wood", "dark_oak_wood",
        "stripped_oak_wood", "stripped_birch_wood", "stripped_spruce_wood", "stripped_jungle_wood",
        "stripped_acacia_wood", "stripped_dark_oak_wood",
        
        # Planks
        "oak_planks", "birch_planks", "spruce_planks", "jungle_planks", "acacia_planks", "dark_oak_planks",
        
        # Leaves
        "oak_leaves", "birch_leaves", "spruce_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves",
        
        # Basic blocks
        "stone", "granite", "diorite", "andesite", "cobblestone", "mossy_cobblestone",
        "smooth_stone", "stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "chiseled_stone_bricks",
        
        # Nether
        "netherrack", "soul_sand", "soul_soil", "basalt", "smooth_basalt", "polished_basalt",
        "blackstone", "polished_blackstone", "chiseled_polished_blackstone",
        "nether_bricks", "red_nether_bricks", "chiseled_nether_bricks", "cracked_nether_bricks",
        
        # End
        "end_stone", "end_stone_bricks", "purpur_block", "purpur_pillar",
        
        # Ores
        "coal_ore", "iron_ore", "gold_ore", "redstone_ore", "lapis_ore", "diamond_ore", "emerald_ore",
        "nether_quartz_ore", "nether_gold_ore", "ancient_debris",
        
        # Ore blocks
        "coal_block", "iron_block", "gold_block", "redstone_block", "lapis_block", 
        "diamond_block", "emerald_block", "netherite_block", "quartz_block",
        
        # Dirt variants
        "dirt", "coarse_dirt", "podzol", "mycelium", "grass_block", "grass_path",
        
        # Sand
        "sand", "red_sand", "sandstone", "red_sandstone", "chiseled_sandstone", "cut_sandstone",
        "smooth_sandstone", "chiseled_red_sandstone", "cut_red_sandstone", "smooth_red_sandstone",
        
        # Prismarine
        "prismarine", "prismarine_bricks", "dark_prismarine",
        
        # Concrete and terracotta
        "terracotta", "white_concrete", "orange_concrete", "magenta_concrete", "light_blue_concrete",
        "yellow_concrete", "lime_concrete", "pink_concrete", "gray_concrete", "light_gray_concrete",
        "cyan_concrete", "purple_concrete", "blue_concrete", "brown_concrete", "green_concrete",
        "red_concrete", "black_concrete",
        "white_terracotta", "orange_terracotta", "magenta_terracotta", "light_blue_terracotta",
        "yellow_terracotta", "lime_terracotta", "pink_terracotta", "gray_terracotta",
        "light_gray_terracotta", "cyan_terracotta", "purple_terracotta", "blue_terracotta",
        "brown_terracotta", "green_terracotta", "red_terracotta", "black_terracotta",
        
        # Wool
        "white_wool", "orange_wool", "magenta_wool", "light_blue_wool", "yellow_wool",
        "lime_wool", "pink_wool", "gray_wool", "light_gray_wool", "cyan_wool",
        "purple_wool", "blue_wool", "brown_wool", "green_wool", "red_wool", "black_wool",
        
        # Glass
        "glass", "white_stained_glass", "orange_stained_glass", "magenta_stained_glass",
        "light_blue_stained_glass", "yellow_stained_glass", "lime_stained_glass",
        "pink_stained_glass", "gray_stained_glass", "light_gray_stained_glass",
        "cyan_stained_glass", "purple_stained_glass", "blue_stained_glass",
        "brown_stained_glass", "green_stained_glass", "red_stained_glass", "black_stained_glass",
        "glass_pane", "white_stained_glass_pane", "orange_stained_glass_pane",
        "magenta_stained_glass_pane", "light_blue_stained_glass_pane", "yellow_stained_glass_pane",
        "lime_stained_glass_pane", "pink_stained_glass_pane", "gray_stained_glass_pane",
        "light_gray_stained_glass_pane", "cyan_stained_glass_pane", "purple_stained_glass_pane",
        "blue_stained_glass_pane", "brown_stained_glass_pane", "green_stained_glass_pane",
        "red_stained_glass_pane", "black_stained_glass_pane",
        
        # Flowers and plants
        "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip",
        "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley", "dandelion",
        "sunflower", "lilac", "rose_bush", "peony", "tall_grass", "large_fern", "grass", "fern",
        "dead_bush", "bamboo", "sugar_cane", "lily_pad",
        
        # Mushrooms
        "brown_mushroom", "red_mushroom", "brown_mushroom_block", "red_mushroom_block", "mushroom_stem",
        
        # Fences and gates
        "oak_fence", "birch_fence", "spruce_fence", "jungle_fence", "acacia_fence", "dark_oak_fence",
        "nether_brick_fence",
        "oak_fence_gate", "birch_fence_gate", "spruce_fence_gate", "jungle_fence_gate",
        "acacia_fence_gate", "dark_oak_fence_gate",
        
        # Doors and trapdoors
        "oak_door", "birch_door", "spruce_door", "jungle_door", "acacia_door", "dark_oak_door", "iron_door",
        "oak_trapdoor", "birch_trapdoor", "spruce_trapdoor", "jungle_trapdoor",
        "acacia_trapdoor", "dark_oak_trapdoor", "iron_trapdoor",
        
        # Signs
        "oak_sign", "birch_sign", "spruce_sign", "jungle_sign", "acacia_sign", "dark_oak_sign",
        "oak_wall_sign", "birch_wall_sign", "spruce_wall_sign", "jungle_wall_sign",
        "acacia_wall_sign", "dark_oak_wall_sign",
        
        # Buttons and pressure plates
        "oak_button", "birch_button", "spruce_button", "jungle_button", "acacia_button", "dark_oak_button",
        "stone_button", "polished_blackstone_button",
        "oak_pressure_plate", "birch_pressure_plate", "spruce_pressure_plate", "jungle_pressure_plate",
        "acacia_pressure_plate", "dark_oak_pressure_plate", "stone_pressure_plate",
        "polished_blackstone_pressure_plate", "light_weighted_pressure_plate", "heavy_weighted_pressure_plate",
        
        # Stairs
        "oak_stairs", "birch_stairs", "spruce_stairs", "jungle_stairs", "acacia_stairs", "dark_oak_stairs",
        "stone_stairs", "granite_stairs", "diorite_stairs", "andesite_stairs", "cobblestone_stairs",
        "mossy_cobblestone_stairs", "stone_brick_stairs", "mossy_stone_brick_stairs",
        "brick_stairs", "sandstone_stairs", "smooth_sandstone_stairs", "red_sandstone_stairs",
        "smooth_red_sandstone_stairs", "nether_brick_stairs", "red_nether_brick_stairs",
        "purpur_stairs", "quartz_stairs", "smooth_quartz_stairs", "prismarine_stairs",
        "prismarine_brick_stairs", "dark_prismarine_stairs", "blackstone_stairs",
        "polished_blackstone_stairs", "polished_blackstone_brick_stairs",
        
        # Slabs
        "oak_slab", "birch_slab", "spruce_slab", "jungle_slab", "acacia_slab", "dark_oak_slab",
        "stone_slab", "granite_slab", "diorite_slab", "andesite_slab", "cobblestone_slab",
        "mossy_cobblestone_slab", "stone_brick_slab", "mossy_stone_brick_slab",
        "brick_slab", "sandstone_slab", "smooth_sandstone_slab", "red_sandstone_slab",
        "smooth_red_sandstone_slab", "nether_brick_slab", "red_nether_brick_slab",
        "purpur_slab", "quartz_slab", "smooth_quartz_slab", "prismarine_slab",
        "prismarine_brick_slab", "dark_prismarine_slab", "blackstone_slab",
        "polished_blackstone_slab", "polished_blackstone_brick_slab",
        
        # Walls
        "cobblestone_wall", "mossy_cobblestone_wall", "stone_brick_wall", "mossy_stone_brick_wall",
        "andesite_wall", "diorite_wall", "granite_wall", "sandstone_wall", "red_sandstone_wall",
        "brick_wall", "prismarine_wall", "nether_brick_wall", "red_nether_brick_wall",
        "end_stone_brick_wall", "blackstone_wall", "polished_blackstone_wall",
        "polished_blackstone_brick_wall",
        
        # Carpets
        "white_carpet", "orange_carpet", "magenta_carpet", "light_blue_carpet", "yellow_carpet",
        "lime_carpet", "pink_carpet", "gray_carpet", "light_gray_carpet", "cyan_carpet",
        "purple_carpet", "blue_carpet", "brown_carpet", "green_carpet", "red_carpet", "black_carpet",
        
        # Banners
        "white_banner", "orange_banner", "magenta_banner", "light_blue_banner", "yellow_banner",
        "lime_banner", "pink_banner", "gray_banner", "light_gray_banner", "cyan_banner",
        "purple_banner", "blue_banner", "brown_banner", "green_banner", "red_banner", "black_banner",
        "white_wall_banner", "orange_wall_banner", "magenta_wall_banner", "light_blue_wall_banner",
        "yellow_wall_banner", "lime_wall_banner", "pink_wall_banner", "gray_wall_banner",
        "light_gray_wall_banner", "cyan_wall_banner", "purple_wall_banner", "blue_wall_banner",
        "brown_wall_banner", "green_wall_banner", "red_wall_banner", "black_wall_banner",
        
        # Beds
        "white_bed", "orange_bed", "magenta_bed", "light_blue_bed", "yellow_bed", "lime_bed",
        "pink_bed", "gray_bed", "light_gray_bed", "cyan_bed", "purple_bed", "blue_bed",
        "brown_bed", "green_bed", "red_bed", "black_bed",
        
        # Coral
        "tube_coral", "brain_coral", "bubble_coral", "fire_coral", "horn_coral",
        "tube_coral_block", "brain_coral_block", "bubble_coral_block", "fire_coral_block", "horn_coral_block",
        "dead_tube_coral_block", "dead_brain_coral_block", "dead_bubble_coral_block",
        "dead_fire_coral_block", "dead_horn_coral_block",
        
        # Special
        "shulker_box", "white_shulker_box", "orange_shulker_box", "magenta_shulker_box",
        "light_blue_shulker_box", "yellow_shulker_box", "lime_shulker_box", "pink_shulker_box",
        "gray_shulker_box", "light_gray_shulker_box", "cyan_shulker_box", "purple_shulker_box",
        "blue_shulker_box", "brown_shulker_box", "green_shulker_box", "red_shulker_box", "black_shulker_box",
        
        # Redstone
        "redstone_wire", "redstone_torch", "redstone_wall_torch", "redstone_block",
        "repeater", "comparator", "piston", "sticky_piston", "observer", "hopper",
        "dropper", "dispenser", "note_block", "target", "lectern", "daylight_detector",
        
        # Storage
        "chest", "trapped_chest", "ender_chest", "barrel", "bookshelf",
        
        # Air
        "air", "cave_air", "void_air"
    }
}


def is_block_available_in_version(block: str, version: str) -> bool:
    """Check if a block is available in a specific Minecraft version."""
    if version not in VERSION_BLOCKS:
        return True  # Assume available if version not in database
    
    block_clean = block.replace("minecraft:", "").split("[")[0]
    return block_clean in VERSION_BLOCKS[version]


def get_available_blocks_for_version(blocks: Set[str], version: str) -> Set[str]:
    """Filter blocks to only those available in a specific version."""
    if version not in VERSION_BLOCKS:
        return blocks
    
    return {b for b in blocks if is_block_available_in_version(b, version)}


# Export for use in other modules
__all__ = [
    'BLOCK_CATEGORIES',
    'COLOR_GRADIENTS',
    'BLOCK_TO_GRADIENT',
    'get_block_category',
    'get_block_gradient',
    'find_best_block_match',
    'find_closest_block_by_color',
    'is_block_available_in_version',
    'get_available_blocks_for_version',
]
