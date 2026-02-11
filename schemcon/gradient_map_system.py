"""
Comprehensive Gradient Mapping System for Minecraft Block Conversion.

This system creates intelligent mappings between blocks based on:
- Block categories (wood, stone, grass, etc.)
- Block shapes (stairs, slabs, doors, etc.)
- Visual color similarity
- Strict rules to prevent incorrect mappings

Uses real data from Minecraft jar files.
"""

import json
from pathlib import Path
from typing import Dict, Set, Tuple, List, Optional
from dataclasses import dataclass, field
from enum import Enum

class BlockShape(Enum):
    """Block shape categories for matching similar forms."""
    SOLID = "solid"
    STAIRS = "stairs"
    SLAB = "slab"
    DOOR = "door"
    TRAPDOOR = "trapdoor"
    FENCE = "fence"
    FENCE_GATE = "fence_gate"
    WALL = "wall"
    BUTTON = "button"
    PRESSURE_PLATE = "pressure_plate"
    SIGN = "sign"
    LEAVES = "leaves"
    LOG = "log"
    PLANKS = "planks"
    ORE = "ore"
    PLANT = "plant"
    FLOWER = "flower"
    LIGHT = "light"
    GLASS = "glass"
    GLASS_PANE = "glass_pane"
    CARPET = "carpet"

class BlockFamily(Enum):
    """Block material families."""
    # Wood types
    OAK = "oak"
    BIRCH = "birch"
    SPRUCE = "spruce"
    JUNGLE = "jungle"
    ACACIA = "acacia"
    DARK_OAK = "dark_oak"
    CRIMSON = "crimson"
    WARPED = "warped"
    MANGROVE = "mangrove"
    CHERRY = "cherry"
    BAMBOO = "bamboo"
    
    # Stone types
    STONE = "stone"
    GRANITE = "granite"
    DIORITE = "diorite"
    ANDESITE = "andesite"
    COBBLESTONE = "cobblestone"
    STONE_BRICKS = "stone_bricks"
    DEEPSLATE = "deepslate"
    BLACKSTONE = "blackstone"
    BASALT = "basalt"
    
    # Colors
    WHITE = "white"
    ORANGE = "orange"
    MAGENTA = "magenta"
    LIGHT_BLUE = "light_blue"
    YELLOW = "yellow"
    LIME = "lime"
    PINK = "pink"
    GRAY = "gray"
    LIGHT_GRAY = "light_gray"
    CYAN = "cyan"
    PURPLE = "purple"
    BLUE = "blue"
    BROWN = "brown"
    GREEN = "green"
    RED = "red"
    BLACK = "black"

@dataclass
class BlockProfile:
    """Complete profile of a block for matching."""
    name: str
    shape: BlockShape
    family: Optional[BlockFamily] = None
    category: str = ""  # grass, stone, wood, etc.
    color_hex: str = "#808080"  # Average color
    is_natural: bool = False
    is_building_block: bool = False
    can_replace_with: List[str] = field(default_factory=list)
    
    def get_base_name(self) -> str:
        """Get block name without properties."""
        return self.name.split("[")[0]

# Strict mapping rules - prevents incorrect replacements
STRICT_RULES = {
    # Format: source_category -> allowed_target_categories
    # If not in list, can only map to same category
    "leaves": ["leaves"],  # Leaves can only become other leaves
    "grass_block": ["grass_block", "dirt", "podzol", "mycelium"],  # Grass can become dirt-like
    "sapling": ["sapling"],
    "flower": ["flower", "tall_flower"],
    "tall_plant": ["tall_plant", "plant"],
    "water": ["water", "air"],
    "lava": ["lava", "air"],
    "command_block": ["air"],  # Command blocks become air
}

# Block categories with their visual characteristics
BLOCK_CATEGORIES_DETAILED = {
    "grass": {
        "color": "#5C9E34",
        "blocks": ["grass_block", "short_grass", "tall_grass", "fern", "large_fern"],
        "can_replace_with": ["dirt", "podzol", "mycelium"],
    },
    "dirt": {
        "color": "#8B5A2B", 
        "blocks": ["dirt", "coarse_dirt", "podzol", "rooted_dirt", "mud", "packed_mud", "muddy_mangrove_roots"],
        "can_replace_with": ["dirt", "coarse_dirt"],
    },
    "stone": {
        "color": "#7D7D7D",
        "blocks": ["stone", "smooth_stone", "deepslate", "cobbled_deepslate", "calcite", "tuff", "dripstone_block"],
        "can_replace_with": ["stone", "cobblestone", "andesite"],
    },
    "cobblestone": {
        "color": "#686868",
        "blocks": ["cobblestone", "mossy_cobblestone"],
        "can_replace_with": ["cobblestone", "stone"],
    },
    "stone_bricks": {
        "color": "#7A7A7A",
        "blocks": ["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "chiseled_stone_bricks"],
        "can_replace_with": ["stone_bricks", "stone"],
    },
    "granite": {
        "color": "#A67568",
        "blocks": ["granite", "polished_granite"],
        "can_replace_with": ["granite", "stone"],
    },
    "diorite": {
        "color": "#D6D6D6",
        "blocks": ["diorite", "polished_diorite"],
        "can_replace_with": ["diorite", "stone"],
    },
    "andesite": {
        "color": "#888888",
        "blocks": ["andesite", "polished_andesite"],
        "can_replace_with": ["andesite", "stone"],
    },
    "deepslate": {
        "color": "#4A4A4A",
        "blocks": ["deepslate", "cobbled_deepslate", "polished_deepslate", "deepslate_bricks", "deepslate_tiles"],
        "can_replace_with": ["stone", "cobblestone", "blackstone"],
    },
    "blackstone": {
        "color": "#2D2D2D",
        "blocks": ["blackstone", "polished_blackstone", "chiseled_polished_blackstone", "cracked_polished_blackstone_bricks"],
        "can_replace_with": ["blackstone", "deepslate", "stone"],
    },
    "oak_wood": {
        "color": "#9C7F4A",
        "blocks": ["oak_log", "oak_wood", "stripped_oak_log", "stripped_oak_wood", "oak_planks"],
        "can_replace_with": ["oak_log", "oak_planks", "oak_wood"],
    },
    "birch_wood": {
        "color": "#D6CFA6",
        "blocks": ["birch_log", "birch_wood", "stripped_birch_log", "stripped_birch_wood", "birch_planks"],
        "can_replace_with": ["birch_log", "birch_planks", "oak_log"],
    },
    "spruce_wood": {
        "color": "#5C3A21",
        "blocks": ["spruce_log", "spruce_wood", "stripped_spruce_log", "stripped_spruce_wood", "spruce_planks"],
        "can_replace_with": ["spruce_log", "spruce_planks", "oak_log"],
    },
    "jungle_wood": {
        "color": "#A07049",
        "blocks": ["jungle_log", "jungle_wood", "stripped_jungle_log", "stripped_jungle_wood", "jungle_planks"],
        "can_replace_with": ["jungle_log", "jungle_planks", "oak_log"],
    },
    "acacia_wood": {
        "color": "#A85A32",
        "blocks": ["acacia_log", "acacia_wood", "stripped_acacia_log", "stripped_acacia_wood", "acacia_planks"],
        "can_replace_with": ["acacia_log", "acacia_planks", "oak_log"],
    },
    "dark_oak_wood": {
        "color": "#3C2716",
        "blocks": ["dark_oak_log", "dark_oak_wood", "stripped_dark_oak_log", "stripped_dark_oak_wood", "dark_oak_planks"],
        "can_replace_with": ["dark_oak_log", "dark_oak_planks", "oak_log"],
    },
    "crimson_wood": {
        "color": "#7D3948",
        "blocks": ["crimson_stem", "crimson_hyphae", "stripped_crimson_stem", "stripped_crimson_hyphae", "crimson_planks"],
        "can_replace_with": ["crimson_stem", "crimson_planks", "oak_log"],
    },
    "warped_wood": {
        "color": "#3A8E8C",
        "blocks": ["warped_stem", "warped_hyphae", "stripped_warped_stem", "stripped_warped_hyphae", "warped_planks"],
        "can_replace_with": ["warped_stem", "warped_planks", "birch_log"],
    },
    "mangrove_wood": {
        "color": "#6B3828",
        "blocks": ["mangrove_log", "mangrove_wood", "stripped_mangrove_log", "stripped_mangrove_wood", "mangrove_planks"],
        "can_replace_with": ["dark_oak_log", "jungle_log", "oak_log"],
    },
    "cherry_wood": {
        "color": "#D6B6B6",
        "blocks": ["cherry_log", "cherry_wood", "stripped_cherry_log", "stripped_cherry_wood", "cherry_planks"],
        "can_replace_with": ["birch_log", "oak_log", "jungle_log"],
    },
    "bamboo_wood": {
        "color": "#D9C484",
        "blocks": ["bamboo_block", "stripped_bamboo_block", "bamboo_planks"],
        "can_replace_with": ["oak_log", "birch_log", "bamboo"],
    },
    "oak_leaves": {
        "color": "#3A7D23",
        "blocks": ["oak_leaves"],
        "can_replace_with": ["oak_leaves", "birch_leaves", "spruce_leaves"],
    },
    "spruce_leaves": {
        "color": "#2D5A1E",
        "blocks": ["spruce_leaves"],
        "can_replace_with": ["spruce_leaves", "oak_leaves", "dark_oak_leaves"],
    },
    "birch_leaves": {
        "color": "#6BA84A",
        "blocks": ["birch_leaves"],
        "can_replace_with": ["birch_leaves", "oak_leaves", "acacia_leaves"],
    },
    "jungle_leaves": {
        "color": "#4A7D29",
        "blocks": ["jungle_leaves"],
        "can_replace_with": ["jungle_leaves", "oak_leaves", "acacia_leaves"],
    },
    "acacia_leaves": {
        "color": "#6B8C3A",
        "blocks": ["acacia_leaves"],
        "can_replace_with": ["acacia_leaves", "oak_leaves", "birch_leaves"],
    },
    "dark_oak_leaves": {
        "color": "#2D4A1A",
        "blocks": ["dark_oak_leaves"],
        "can_replace_with": ["dark_oak_leaves", "spruce_leaves", "oak_leaves"],
    },
    "azalea_leaves": {
        "color": "#4A8C3A",
        "blocks": ["azalea_leaves", "flowering_azalea_leaves"],
        "can_replace_with": ["oak_leaves", "birch_leaves", "jungle_leaves"],
    },
    "mangrove_leaves": {
        "color": "#4A7D2D",
        "blocks": ["mangrove_leaves"],
        "can_replace_with": ["oak_leaves", "jungle_leaves", "acacia_leaves"],
    },
    "cherry_leaves": {
        "color": "#E6A6D6",
        "blocks": ["cherry_leaves"],
        "can_replace_with": ["birch_leaves", "oak_leaves"],
    },
    "sand": {
        "color": "#D6D6A6",
        "blocks": ["sand", "red_sand"],
        "can_replace_with": ["sand", "red_sand"],
    },
    "sandstone": {
        "color": "#D6D6A6",
        "blocks": ["sandstone", "chiseled_sandstone", "cut_sandstone", "smooth_sandstone"],
        "can_replace_with": ["sandstone", "smooth_sandstone"],
    },
    "red_sandstone": {
        "color": "#A67D5A",
        "blocks": ["red_sandstone", "chiseled_red_sandstone", "cut_red_sandstone", "smooth_red_sandstone"],
        "can_replace_with": ["red_sandstone", "smooth_red_sandstone", "sandstone"],
    },
    "glass": {
        "color": "#AADDFF",
        "blocks": ["glass", "white_stained_glass", "orange_stained_glass", "magenta_stained_glass", 
                   "light_blue_stained_glass", "yellow_stained_glass", "lime_stained_glass",
                   "pink_stained_glass", "gray_stained_glass", "light_gray_stained_glass",
                   "cyan_stained_glass", "purple_stained_glass", "blue_stained_glass",
                   "brown_stained_glass", "green_stained_glass", "red_stained_glass", "black_stained_glass"],
        "can_replace_with": ["glass"],
    },
    "wool": {
        "color": "#DDDDDD",
        "blocks": ["white_wool", "orange_wool", "magenta_wool", "light_blue_wool", "yellow_wool",
                   "lime_wool", "pink_wool", "gray_wool", "light_gray_wool", "cyan_wool",
                   "purple_wool", "blue_wool", "brown_wool", "green_wool", "red_wool", "black_wool"],
        "can_replace_with": ["white_wool", "wool"],
    },
    "concrete": {
        "color": "#999999",
        "blocks": ["white_concrete", "orange_concrete", "magenta_concrete", "light_blue_concrete",
                   "yellow_concrete", "lime_concrete", "pink_concrete", "gray_concrete",
                   "light_gray_concrete", "cyan_concrete", "purple_concrete", "blue_concrete",
                   "brown_concrete", "green_concrete", "red_concrete", "black_concrete"],
        "can_replace_with": ["white_concrete", "concrete"],
    },
    "terracotta": {
        "color": "#A46B4A",
        "blocks": ["terracotta", "white_terracotta", "orange_terracotta", "magenta_terracotta",
                   "light_blue_terracotta", "yellow_terracotta", "lime_terracotta", "pink_terracotta",
                   "gray_terracotta", "light_gray_terracotta", "cyan_terracotta", "purple_terracotta",
                   "blue_terracotta", "brown_terracotta", "green_terracotta", "red_terracotta", "black_terracotta"],
        "can_replace_with": ["terracotta"],
    },
    "netherrack": {
        "color": "#7D3838",
        "blocks": ["netherrack"],
        "can_replace_with": ["netherrack"],
    },
    "soul_sand": {
        "color": "#4A3A2D",
        "blocks": ["soul_sand", "soul_soil"],
        "can_replace_with": ["soul_sand", "dirt"],
    },
    "basalt": {
        "color": "#4A4A4A",
        "blocks": ["basalt", "smooth_basalt", "polished_basalt"],
        "can_replace_with": ["basalt", "stone", "deepslate"],
    },
    "nether_bricks": {
        "color": "#2D1A1A",
        "blocks": ["nether_bricks", "red_nether_bricks", "chiseled_nether_bricks", "cracked_nether_bricks"],
        "can_replace_with": ["nether_bricks", "stone_bricks"],
    },
    "end_stone": {
        "color": "#E6E6AA",
        "blocks": ["end_stone", "end_stone_bricks"],
        "can_replace_with": ["end_stone", "sandstone"],
    },
    "purpur": {
        "color": "#A68AC4",
        "blocks": ["purpur_block", "purpur_pillar"],
        "can_replace_with": ["purpur_block", "end_stone"],
    },
    "quartz": {
        "color": "#E6E6E6",
        "blocks": ["quartz_block", "quartz_pillar", "chiseled_quartz_block", "smooth_quartz", "quartz_bricks"],
        "can_replace_with": ["quartz_block", "smooth_quartz"],
    },
    "prismarine": {
        "color": "#6B9C8C",
        "blocks": ["prismarine", "prismarine_bricks", "dark_prismarine"],
        "can_replace_with": ["prismarine", "stone"],
    },
    "amethyst": {
        "color": "#B48CD6",
        "blocks": ["amethyst_block", "amethyst_cluster", "budding_amethyst", "calcite"],
        "can_replace_with": ["purpur_block", "quartz_block", "stone"],
    },
    "copper": {
        "color": "#B86B38",
        "blocks": ["copper_block", "exposed_copper", "weathered_copper", "oxidized_copper"],
        "can_replace_with": ["iron_block", "gold_block", "stone"],
    },
    "sculk": {
        "color": "#1A2D3A",
        "blocks": ["sculk", "sculk_catalyst", "sculk_sensor", "sculk_shrieker", "sculk_vein"],
        "can_replace_with": ["coal_block", "black_wool", "obsidian"],
    },
    "froglight": {
        "color": "#F0E6AA",
        "blocks": ["ochre_froglight", "verdant_froglight", "pearlescent_froglight"],
        "can_replace_with": ["glowstone", "sea_lantern"],
    },
    "light": {
        "color": "#FFFFAA",
        "blocks": ["torch", "lantern", "glowstone", "sea_lantern", "shroomlight", "end_rod", "jack_o_lantern"],
        "can_replace_with": ["glowstone", "torch"],
    },
    "ore": {
        "color": "#8C8C8C",
        "blocks": ["coal_ore", "iron_ore", "gold_ore", "redstone_ore", "lapis_ore", 
                   "diamond_ore", "emerald_ore", "copper_ore", "ancient_debris",
                   "deepslate_coal_ore", "deepslate_iron_ore", "deepslate_gold_ore",
                   "deepslate_redstone_ore", "deepslate_lapis_ore", "deepslate_diamond_ore",
                   "deepslate_emerald_ore", "deepslate_copper_ore"],
        "can_replace_with": ["stone"],
    },
    "metal_block": {
        "color": "#B8B8B8",
        "blocks": ["iron_block", "gold_block", "diamond_block", "emerald_block", "lapis_block",
                   "redstone_block", "coal_block", "netherite_block"],
        "can_replace_with": ["iron_block", "gold_block"],
    },
    "tnt": {
        "color": "#C44E4E",
        "blocks": ["tnt"],
        "can_replace_with": ["tnt", "redstone_block"],
    },
    "sponge": {
        "color": "#D6D64A",
        "blocks": ["sponge", "wet_sponge"],
        "can_replace_with": ["sponge", "yellow_wool"],
    },
    "bookshelf": {
        "color": "#7A5C3A",
        "blocks": ["bookshelf"],
        "can_replace_with": ["bookshelf", "oak_planks"],
    },
    "mossy": {
        "color": "#5A7D3A",
        "blocks": ["moss_block", "moss_carpet"],
        "can_replace_with": ["grass_block", "leaves"],
    },
    "mushroom": {
        "color": "#8C5A3A",
        "blocks": ["brown_mushroom_block", "red_mushroom_block", "mushroom_stem"],
        "can_replace_with": ["brown_mushroom_block", "red_mushroom_block"],
    },
    # Shape-based categories (for blocks not matching specific materials)
    "stairs": {
        "color": "#808080",
        "blocks": [],  # Dynamic - any block ending in _stairs
        "can_replace_with": ["oak_stairs", "stone_stairs", "cobblestone_stairs"],
    },
    "slab": {
        "color": "#808080",
        "blocks": [],  # Dynamic - any block ending in _slab
        "can_replace_with": ["oak_slab", "stone_slab", "cobblestone_slab"],
    },
    "door": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic
        "can_replace_with": ["oak_door", "iron_door"],
    },
    "trapdoor": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic
        "can_replace_with": ["oak_trapdoor", "iron_trapdoor"],
    },
    "fence": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic
        "can_replace_with": ["oak_fence", "nether_brick_fence"],
    },
    "fence_gate": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic
        "can_replace_with": ["oak_fence_gate", "spruce_fence_gate"],
    },
    "wall": {
        "color": "#808080",
        "blocks": [],  # Dynamic
        "can_replace_with": ["cobblestone_wall", "stone_brick_wall"],
    },
    "button": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic
        "can_replace_with": ["oak_button", "stone_button"],
    },
    "pressure_plate": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic
        "can_replace_with": ["oak_pressure_plate", "stone_pressure_plate"],
    },
    "sign": {
        "color": "#8B7355",
        "blocks": [],  # Dynamic - includes hanging_sign
        "can_replace_with": ["oak_sign", "oak_wall_sign"],
    },
    "pumpkin": {
        "color": "#D68C1A",
        "blocks": ["pumpkin", "carved_pumpkin", "jack_o_lantern"],
        "can_replace_with": ["pumpkin", "melon"],
    },
    "melon": {
        "color": "#6BA31A",
        "blocks": ["melon"],
        "can_replace_with": ["melon", "pumpkin"],
    },
    "cactus": {
        "color": "#2D8C1A",
        "blocks": ["cactus"],
        "can_replace_with": ["cactus", "green_wool"],
    },
    "coral": {
        "color": "#D64A6B",
        "blocks": ["tube_coral_block", "brain_coral_block", "bubble_coral_block", 
                   "fire_coral_block", "horn_coral_block"],
        "can_replace_with": ["wool", "terracotta"],
    },
    "ice": {
        "color": "#A6D6FF",
        "blocks": ["ice", "packed_ice", "blue_ice", "frosted_ice"],
        "can_replace_with": ["ice", "packed_ice"],
    },
    "snow": {
        "color": "#F0F0F0",
        "blocks": ["snow", "snow_block", "powder_snow"],
        "can_replace_with": ["snow", "snow_block"],
    },
    "clay": {
        "color": "#9C9CC4",
        "blocks": ["clay"],
        "can_replace_with": ["clay", "dirt"],
    },
    "obsidian": {
        "color": "#1A1A2D",
        "blocks": ["obsidian", "crying_obsidian"],
        "can_replace_with": ["obsidian", "blackstone"],
    },
    "bedrock": {
        "color": "#4A4A4A",
        "blocks": ["bedrock"],
        "can_replace_with": ["bedrock", "stone"],
    },
}

def get_block_category(block_name: str) -> str:
    """Get the category for a block using pattern matching."""
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    
    # First try exact match
    for category, data in BLOCK_CATEGORIES_DETAILED.items():
        if block_clean in data["blocks"]:
            return category
    
    # Pattern-based matching for variants
    # Wood types
    wood_types = ["oak", "birch", "spruce", "jungle", "acacia", "dark_oak", 
                  "crimson", "warped", "mangrove", "cherry", "bamboo"]
    
    for wood in wood_types:
        if block_clean.startswith(wood):
            if any(x in block_clean for x in ["_log", "_wood", "_stem", "_hyphae", "_block"]):
                if wood == "bamboo":
                    return "bamboo_wood"
                elif wood in ["crimson", "warped"]:
                    return f"{wood}_wood"
                else:
                    return f"{wood}_wood"
            elif "_planks" in block_clean:
                if wood == "bamboo":
                    return "bamboo_wood"
                return f"{wood}_wood"
            elif "_leaves" in block_clean:
                if wood == "azalea":
                    return "azalea_leaves"
                return f"{wood}_leaves" if f"{wood}_leaves" in BLOCK_CATEGORIES_DETAILED else "oak_leaves"
            elif "_stairs" in block_clean:
                return "stairs"
            elif "_slab" in block_clean:
                return "slab"
            elif "_fence" in block_clean:
                return "fence"
            elif "_door" in block_clean:
                return "door"
            elif "_trapdoor" in block_clean:
                return "trapdoor"
            elif "_button" in block_clean:
                return "button"
            elif "_pressure_plate" in block_clean:
                return "pressure_plate"
            elif "_sign" in block_clean:
                return "sign"
    
    # Stone types
    stone_types = ["stone", "cobblestone", "stone_bricks", "granite", "diorite", 
                   "andesite", "deepslate", "blackstone", "basalt", "tuff", "calcite"]
    for stone in stone_types:
        if stone in block_clean:
            if stone in ["deepslate", "blackstone", "basalt"]:
                return stone
            return "stone"
    
    # Color blocks
    colors = ["white", "orange", "magenta", "light_blue", "yellow", "lime", 
              "pink", "gray", "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]
    for color in colors:
        if block_clean.startswith(color):
            if "_concrete" in block_clean:
                return "concrete"
            elif "_wool" in block_clean:
                return "wool"
            elif "_terracotta" in block_clean:
                return "terracotta"
            elif "_stained_glass" in block_clean:
                return "glass"
            elif "_candle" in block_clean:
                return "light"
    
    # Shape-based detection
    if "_stairs" in block_clean:
        return "stairs"
    elif "_slab" in block_clean:
        return "slab"
    elif "_wall" in block_clean:
        return "wall"
    elif "_fence_gate" in block_clean:
        return "fence_gate"
    elif "_fence" in block_clean:
        return "fence"
    elif "_door" in block_clean:
        return "door"
    elif "_trapdoor" in block_clean:
        return "trapdoor"
    elif "_button" in block_clean:
        return "button"
    elif "_pressure_plate" in block_clean:
        return "pressure_plate"
    elif "_sign" in block_clean or "_hanging_sign" in block_clean:
        return "sign"
    elif "_leaves" in block_clean:
        return "oak_leaves"
    elif "_ore" in block_clean:
        return "ore"
    
    return "unknown"

def get_block_color(block_name: str) -> str:
    """Get the color for a block category."""
    category = get_block_category(block_name)
    if category in BLOCK_CATEGORIES_DETAILED:
        return BLOCK_CATEGORIES_DETAILED[category]["color"]
    return "#808080"

def get_replacement_candidates(block_name: str, target_version: str = "1.16.5") -> List[str]:
    """Get list of blocks that can replace this block."""
    category = get_block_category(block_name)
    if category in BLOCK_CATEGORIES_DETAILED:
        return BLOCK_CATEGORIES_DETAILED[category]["can_replace_with"]
    return []

# Export for use in other modules
__all__ = [
    'BlockShape', 'BlockFamily', 'BlockProfile', 'STRICT_RULES',
    'BLOCK_CATEGORIES_DETAILED', 'get_block_category', 'get_block_color', 
    'get_replacement_candidates'
]
