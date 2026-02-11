"""
Strict Block Replacement System with Category-Specific Gradients

Rules:
1. Type MUST match (leaves→leaves, grass→grass, stone→stone)
2. Form SHOULD match (stairs→stairs, slab→slab)
3. Color similarity within same type
4. NEVER replace solids with liquids
5. NEVER cross major categories
"""

from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path

@dataclass 
class BlockType:
    """Block classification with strict replacement rules."""
    name: str
    color: str  # Hex color
    can_replace_with: List[str]  # Allowed target types
    is_solid: bool = True
    is_liquid: bool = False
    is_plant: bool = False
    forms: List[str] = field(default_factory=list)  # stairs, slab, etc.

# STRICT BLOCK TYPES - replacement only within these categories
BLOCK_TYPES = {
    # ORGANIC - Grass & Plants
    "short_grass": BlockType("short_grass", "#5C9E34", ["short_grass", "tall_grass", "fern"], is_plant=True),
    "tall_grass": BlockType("tall_grass", "#4A8C2A", ["tall_grass", "large_fern", "short_grass"], is_plant=True),
    "fern": BlockType("fern", "#4A7D23", ["fern", "dead_bush", "short_grass"], is_plant=True),
    "large_fern": BlockType("large_fern", "#4A7D23", ["large_fern", "tall_grass"], is_plant=True),
    "dead_bush": BlockType("dead_bush", "#8B7355", ["dead_bush", "fern"], is_plant=True),
    "sea_pickle": BlockType("sea_pickle", "#4A8C1A", ["sea_pickle"], is_plant=True),
    
    # FLOWERS - Decorative plants
    "flower_small": BlockType("flower_small", "#FFD700", 
        ["dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "oxeye_daisy", "cornflower", "lily_of_the_valley"], 
        is_plant=True),
    "flower_tall": BlockType("flower_tall", "#FF69B4",
        ["sunflower", "lilac", "rose_bush", "peony"],
        is_plant=True),
    "torchflower": BlockType("torchflower", "#FF8C00", ["torchflower", "redstone_torch", "torch"], is_plant=True),
    "pitcher_plant": BlockType("pitcher_plant", "#6B8C3A", ["pitcher_plant", "tall_grass", "large_fern"], is_plant=True),
    
    # LEAVES - Tree foliage (STRICT: only leaves!)
    "leaves_oak": BlockType("leaves_oak", "#3A7D23", ["oak_leaves", "birch_leaves", "spruce_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves"], is_plant=True),
    "leaves_spruce": BlockType("leaves_spruce", "#2D5A1E", ["spruce_leaves", "oak_leaves", "dark_oak_leaves"], is_plant=True),
    "leaves_birch": BlockType("leaves_birch", "#6BA84A", ["birch_leaves", "oak_leaves", "acacia_leaves"], is_plant=True),
    "leaves_jungle": BlockType("leaves_jungle", "#4A7D29", ["jungle_leaves", "oak_leaves", "acacia_leaves"], is_plant=True),
    "leaves_acacia": BlockType("leaves_acacia", "#6B8C3A", ["acacia_leaves", "oak_leaves", "birch_leaves"], is_plant=True),
    "leaves_dark_oak": BlockType("leaves_dark_oak", "#2D4A1A", ["dark_oak_leaves", "spruce_leaves", "oak_leaves"], is_plant=True),
    "leaves_azalea": BlockType("leaves_azalea", "#4A8C3A", ["oak_leaves", "birch_leaves", "jungle_leaves"], is_plant=True),
    "leaves_mangrove": BlockType("leaves_mangrove", "#4A7D2D", ["oak_leaves", "jungle_leaves", "acacia_leaves"], is_plant=True),
    "leaves_cherry": BlockType("leaves_cherry", "#E6A6D6", ["birch_leaves", "oak_leaves"], is_plant=True),
    "leaves_pale_oak": BlockType("leaves_pale_oak", "#C4D6A6", ["birch_leaves", "oak_leaves"], is_plant=True),
    
    # WOOD - Logs and wood blocks
    "wood_oak": BlockType("wood_oak", "#9C7F4A", ["oak_log", "oak_wood", "stripped_oak_log", "stripped_oak_wood", "oak_planks"]),
    "wood_birch": BlockType("wood_birch", "#D6CFA6", ["birch_log", "birch_wood", "birch_planks"]),
    "wood_spruce": BlockType("wood_spruce", "#5C3A21", ["spruce_log", "spruce_wood", "spruce_planks"]),
    "wood_jungle": BlockType("wood_jungle", "#A07049", ["jungle_log", "jungle_wood", "jungle_planks"]),
    "wood_acacia": BlockType("wood_acacia", "#A85A32", ["acacia_log", "acacia_wood", "acacia_planks"]),
    "wood_dark_oak": BlockType("wood_dark_oak", "#3C2716", ["dark_oak_log", "dark_oak_wood", "dark_oak_planks"]),
    "wood_crimson": BlockType("wood_crimson", "#7D3948", ["crimson_stem", "crimson_hyphae", "crimson_planks"]),
    "wood_warped": BlockType("wood_warped", "#3A8E8C", ["warped_stem", "warped_hyphae", "warped_planks"]),
    "wood_mangrove": BlockType("wood_mangrove", "#6B3828", ["dark_oak_log", "jungle_log", "oak_log"]),
    "wood_cherry": BlockType("wood_cherry", "#D6B6B6", ["birch_log", "oak_log", "jungle_log"]),
    "wood_bamboo": BlockType("wood_bamboo", "#D9C484", ["birch_log", "oak_log", "oak_planks"]),
    "wood_pale_oak": BlockType("wood_pale_oak", "#C4B6A6", ["birch_log", "oak_log"]),
    
    # STONE - Natural stone
    "stone": BlockType("stone", "#7D7D7D", ["stone", "smooth_stone"]),
    "stone_cobble": BlockType("stone_cobble", "#686868", ["cobblestone", "mossy_cobblestone"]),
    "stone_bricks": BlockType("stone_bricks", "#7A7A7A", ["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "chiseled_stone_bricks"]),
    "stone_granite": BlockType("stone_granite", "#A67568", ["granite", "polished_granite", "stone"]),
    "stone_diorite": BlockType("stone_diorite", "#D6D6D6", ["diorite", "polished_diorite", "stone"]),
    "stone_andesite": BlockType("stone_andesite", "#888888", ["andesite", "polished_andesite", "stone"]),
    "stone_deepslate": BlockType("stone_deepslate", "#4A4A4A", ["deepslate", "cobbled_deepslate", "polished_deepslate", "stone", "blackstone"]),
    "stone_blackstone": BlockType("stone_blackstone", "#2D2D2D", ["blackstone", "polished_blackstone", "stone", "deepslate"]),
    "stone_basalt": BlockType("stone_basalt", "#4A4A4A", ["basalt", "smooth_basalt", "polished_basalt", "stone", "deepslate"]),
    "stone_tuff": BlockType("stone_tuff", "#6B6B6B", ["tuff", "stone", "andesite"]),
    "stone_calcite": BlockType("stone_calcite", "#E6E6E6", ["calcite", "quartz_block", "smooth_stone"]),
    
    # DIRT - Ground blocks
    "dirt": BlockType("dirt", "#8B5A2B", ["dirt", "coarse_dirt"]),
    "grass_block": BlockType("grass_block", "#5C9E34", ["grass_block", "podzol", "mycelium"]),
    "podzol": BlockType("podzol", "#5C4A3A", ["podzol", "dirt", "coarse_dirt"]),
    "mycelium": BlockType("mycelium", "#6B5A7D", ["mycelium", "podzol", "dirt"]),
    "rooted_dirt": BlockType("rooted_dirt", "#8B5A2B", ["dirt", "coarse_dirt"]),
    "mud": BlockType("mud", "#4A3A2D", ["dirt", "coarse_dirt"]),
    "packed_mud": BlockType("packed_mud", "#8B6B4A", ["dirt", "coarse_dirt", "mud_bricks"]),
    "mud_bricks": BlockType("mud_bricks", "#9C7C5A", ["mud_bricks", "bricks", "dirt"]),
    
    # SAND - Desert blocks
    "sand": BlockType("sand", "#D6D6A6", ["sand", "red_sand"]),
    "sandstone": BlockType("sandstone", "#D6D6A6", ["sandstone", "smooth_sandstone", "cut_sandstone", "chiseled_sandstone"]),
    "red_sandstone": BlockType("red_sandstone", "#A67D5A", ["red_sandstone", "smooth_red_sandstone", "sandstone"]),
    
    # NETHER - Hell dimension blocks (STRICT: only nether blocks!)
    "netherrack": BlockType("netherrack", "#7D3838", ["netherrack", "magma_block", "nether_bricks"]),
    "nether_bricks": BlockType("nether_bricks", "#2D1A1A", ["nether_bricks", "red_nether_bricks", "netherrack"]),
    "soul_sand": BlockType("soul_sand", "#4A3A2D", ["soul_sand", "soul_soil", "dirt"]),
    "soul_soil": BlockType("soul_soil", "#4A3A2D", ["soul_soil", "soul_sand", "dirt"]),
    "nether_gold_ore": BlockType("nether_gold_ore", "#8C7C2A", ["nether_gold_ore", "gold_ore", "netherrack"]),
    "ancient_debris": BlockType("ancient_debris", "#4A3A2D", ["ancient_debris", "obsidian", "netherite_block"]),
    
    # NETHER PLANTS - Nether vegetation (STRICT: only nether plants!)
    "nether_wart": BlockType("nether_wart", "#8C1A1A", ["nether_wart", "red_mushroom", "brown_mushroom"], is_plant=True),
    "warped_wart": BlockType("warped_wart", "#1A4A4A", ["warped_wart", "warped_fungus", "crimson_fungus"], is_plant=True),
    "crimson_fungus": BlockType("crimson_fungus", "#8C1A1A", ["crimson_fungus", "red_mushroom", "brown_mushroom"], is_plant=True),
    "warped_fungus": BlockType("warped_fungus", "#1A6A6A", ["warped_fungus", "brown_mushroom", "crimson_fungus"], is_plant=True),
    "crimson_roots": BlockType("crimson_roots", "#8C1A1A", ["crimson_roots", "nether_sprouts", "warped_roots"], is_plant=True),
    "warped_roots": BlockType("warped_roots", "#1A6A6A", ["warped_roots", "crimson_roots", "nether_sprouts"], is_plant=True),
    "nether_sprouts": BlockType("nether_sprouts", "#1A8C1A", ["nether_sprouts", "warped_roots", "crimson_roots"], is_plant=True),
    "weeping_vines": BlockType("weeping_vines", "#8C1A1A", ["weeping_vines", "twisting_vines", "vine"], is_plant=True),
    "twisting_vines": BlockType("twisting_vines", "#1A6A8C", ["twisting_vines", "weeping_vines", "vine"], is_plant=True),
    "shroomlight": BlockType("shroomlight", "#F0E6AA", ["shroomlight", "glowstone", "jack_o_lantern"]),
    
    # MUSHROOMS - Fungal blocks
    "mushroom_red": BlockType("mushroom_red", "#C44E4E", ["red_mushroom", "brown_mushroom"], is_plant=True),
    "mushroom_brown": BlockType("mushroom_brown", "#8B5A3A", ["brown_mushroom", "red_mushroom"], is_plant=True),
    "mushroom_block_red": BlockType("mushroom_block_red", "#C44E4E", ["red_mushroom_block", "brown_mushroom_block"]),
    "mushroom_block_brown": BlockType("mushroom_block_brown", "#8B5A3A", ["brown_mushroom_block", "red_mushroom_block"]),
    
    # CORAL - Ocean plants (if no coral available → carpet!)
    "coral_tube": BlockType("coral_tube", "#4A6AD6", ["tube_coral", "tube_coral_fan", "blue_carpet", "light_blue_carpet"], is_plant=True),
    "coral_brain": BlockType("coral_brain", "#D64A8C", ["brain_coral", "brain_coral_fan", "pink_carpet", "magenta_carpet"], is_plant=True),
    "coral_bubble": BlockType("coral_bubble", "#8C4AD6", ["bubble_coral", "bubble_coral_fan", "purple_carpet", "magenta_carpet"], is_plant=True),
    "coral_fire": BlockType("coral_fire", "#D64A4A", ["fire_coral", "fire_coral_fan", "red_carpet", "orange_carpet"], is_plant=True),
    "coral_horn": BlockType("coral_horn", "#F0D64A", ["horn_coral", "horn_coral_fan", "yellow_carpet", "orange_carpet"], is_plant=True),
    "coral_block": BlockType("coral_block", "#4A6AD6", ["tube_coral_block", "brain_coral_block", "bubble_coral_block", "fire_coral_block", "horn_coral_block"]),
    
    # SEA PLANTS - Underwater vegetation
    "kelp": BlockType("kelp", "#2D8C1A", ["kelp", "kelp_plant", "seagrass", "tall_seagrass"], is_plant=True),
    "seagrass": BlockType("seagrass", "#2D8C1A", ["seagrass", "tall_seagrass", "kelp"], is_plant=True),
    "sea_pickle": BlockType("sea_pickle", "#4A8C1A", ["sea_pickle"], is_plant=True),
    
    # BAMBOO - Asian wood type
    "bamboo": BlockType("bamboo", "#6BA31A", ["bamboo", "sugar_cane", "cactus"], is_plant=True),
    "bamboo_shoot": BlockType("bamboo_shoot", "#8BC34A", ["bamboo_sapling", "oak_sapling", "birch_sapling"], is_plant=True),
    
    # VINES - Climbing plants
    "vine": BlockType("vine", "#2D5A1E", ["vine", "weeping_vines", "twisting_vines"], is_plant=True),
    "cave_vines": BlockType("cave_vines", "#4A8C1A", ["cave_vines", "cave_vines_plant", "vine"], is_plant=True),
    
    # CROPS - Farm plants
    "wheat": BlockType("wheat", "#D6C44A", ["wheat", "carrots", "potatoes", "beetroots"], is_plant=True),
    "melon": BlockType("melon", "#6BA31A", ["melon", "pumpkin"]),
    "pumpkin": BlockType("pumpkin", "#D68C1A", ["pumpkin", "melon", "carved_pumpkin", "jack_o_lantern"]),
    
    # DECORATIVE - Pretty blocks
    "amethyst": BlockType("amethyst", "#B48CD6", ["amethyst_block", "amethyst_cluster", "budding_amethyst", "purpur_block"]),
    "crystal": BlockType("crystal", "#E6D6FF", ["amethyst_cluster", "large_amethyst_bud", "medium_amethyst_bud", "small_amethyst_bud"]),
    
    # SCULK - Deep dark blocks
    "sculk": BlockType("sculk", "#1A2D3A", ["sculk", "coal_block", "black_wool", "obsidian"]),
    "sculk_catalyst": BlockType("sculk_catalyst", "#1A3A4A", ["sculk_catalyst", "coal_block", "sculk"]),
    "sculk_shrieker": BlockType("sculk_shrieker", "#1A2D3A", ["sculk_shrieker", "sculk", "coal_block"]),
    "sculk_sensor": BlockType("sculk_sensor", "#2D4A5A", ["sculk_sensor", "note_block", "observer"]),
    "sculk_vein": BlockType("sculk_vein", "#0D1A20", ["sculk_vein", "vine", "moss_carpet"], is_plant=True),
    
    # COPPER - Oxidizing metal
    "copper": BlockType("copper", "#B86B38", ["copper_block", "cut_copper", "iron_block", "gold_block"]),
    "copper_exposed": BlockType("copper_exposed", "#9C7C5A", ["exposed_copper", "exposed_cut_copper", "iron_block"]),
    "copper_weathered": BlockType("copper_weathered", "#6B8C6B", ["weathered_copper", "weathered_cut_copper", "iron_block"]),
    "copper_oxidized": BlockType("copper_oxidized", "#4A7D7D", ["oxidized_copper", "oxidized_cut_copper", "iron_block"]),
    
    # FROGLIGHT - New light sources
    "froglight_ochre": BlockType("froglight_ochre", "#F0E6AA", ["ochre_froglight", "glowstone", "jack_o_lantern"]),
    "froglight_verdant": BlockType("froglight_verdant", "#A6F0A6", ["verdant_froglight", "glowstone", "lime_carpet"]),
    "froglight_pearlescent": BlockType("froglight_pearlescent", "#F0D6E6", ["pearlescent_froglight", "glowstone", "pink_carpet"]),
    
    # CANDLES - Light sources
    "candle": BlockType("candle", "#F0E6C4", ["candle", "torch", "glowstone"]),
    
    # DRIPLEAF - Lily pad plants
    "dripleaf_small": BlockType("dripleaf_small", "#4A8C1A", ["small_dripleaf", "lily_pad", "big_dripleaf"], is_plant=True),
    "dripleaf_big": BlockType("dripleaf_big", "#4A8C1A", ["big_dripleaf", "lily_pad", "small_dripleaf"], is_plant=True),
    
    # MOSS - Soft green blocks
    "moss_block": BlockType("moss_block", "#5A7D3A", ["moss_block", "grass_block", "leaves"]),
    "moss_carpet": BlockType("moss_carpet", "#5A7D3A", ["moss_carpet", "grass", "carpet"], is_plant=True),
    
    # SPORE BLOSSOM - Ceiling flower
    "spore_blossom": BlockType("spore_blossom", "#E6A6D6", ["spore_blossom", "pink_petals", "peony"], is_plant=True),
    
    # PINK PETALS - Ground flowers
    "pink_petals": BlockType("pink_petals", "#F0A6D6", ["pink_petals", "pink_tulip", "peony"], is_plant=True),
    
    # HANGING ROOTS - Ceiling vines
    "hanging_roots": BlockType("hanging_roots", "#8B7355", ["hanging_roots", "vine", "weeping_vines"], is_plant=True),
    
    # POINTED DRIPSTONE - Stalactites
    "pointed_dripstone": BlockType("pointed_dripstone", "#8B8B8B", ["pointed_dripstone", "stone", "dripstone_block"]),
    "dripstone_block": BlockType("dripstone_block", "#9C9C9C", ["dripstone_block", "calcite", "stone"]),
    
    # POWDER SNOW - Soft snow
    "powder_snow": BlockType("powder_snow", "#F0F0F0", ["powder_snow", "snow", "snow_block"]),
    
    # AZALEA - Decorative bush
    "azalea": BlockType("azalea", "#6BA84A", ["azalea", "flowering_azalea", "oak_leaves", "jungle_leaves"], is_plant=True),
    "flowering_azalea": BlockType("flowering_azalea", "#F0A6E6", ["flowering_azalea", "azalea", "pink_petals"], is_plant=True),
    
    # CAVE PLANTS
    "glow_lichen": BlockType("glow_lichen", "#B4D67A", ["glow_lichen", "moss_carpet", "vine"], is_plant=True),
    
    # DECORATED POT - Ceramic
    "decorated_pot": BlockType("decorated_pot", "#B86B4A", ["decorated_pot", "flower_pot", "terracotta"]),
    
    # CHISELED BOOKSHELF
    "chiseled_bookshelf": BlockType("chiseled_bookshelf", "#9C7F4A", ["chiseled_bookshelf", "bookshelf", "oak_planks"]),
    
    # RESIN - New 1.21 blocks
    "resin": BlockType("resin", "#D6A64A", ["resin_block", "resin_bricks", "resin_clump", "honey_block"]),
    "resin_bricks": BlockType("resin_bricks", "#C4963A", ["resin_bricks", "chiseled_resin_bricks", "bricks"]),
    
    # PALE GARDEN - 1.21.2 blocks
    "pale_oak": BlockType("pale_oak", "#C4B6A6", ["pale_oak_log", "pale_oak_wood", "pale_oak_planks", "birch_log"]),
    "pale_leaves": BlockType("pale_leaves", "#C4D6A6", ["pale_oak_leaves", "birch_leaves", "oak_leaves"], is_plant=True),
    "pale_moss": BlockType("pale_moss", "#D6E6C4", ["pale_moss_block", "pale_hanging_moss", "moss_block"]),
    
    # CREAKING - 1.21.2 tree
    "creaking_heart": BlockType("creaking_heart", "#8B6B4A", ["creaking_heart", "pale_oak_log", "oak_log"]),
}

# LIQUIDS - Special handling (can't replace solids with these!)
LIQUID_BLOCKS = {
    "water": BlockType("water", "#3C44AA", ["water"], is_solid=False, is_liquid=True),
    "lava": BlockType("lava", "#FF6C00", ["lava"], is_solid=False, is_liquid=True),
}

# FORMS - Block shape variants
BLOCK_FORMS = ["stairs", "slab", "door", "trapdoor", "fence", "fence_gate", "wall", "button", "pressure_plate", "sign"]

def get_block_type(block_name: str) -> Optional[str]:
    """Get the block type category for a block."""
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    
    # Direct match
    for type_name, block_type in BLOCK_TYPES.items():
        if block_clean in block_type.can_replace_with:
            return type_name
    
    # Pattern matching
    if "leaves" in block_clean:
        for wood in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "azalea", "mangrove", "cherry", "pale_oak"]:
            if wood in block_clean:
                return f"leaves_{wood}"
        return "leaves_oak"
    
    if any(x in block_clean for x in ["_log", "_wood", "_stem", "_hyphae"]):
        for wood in ["oak", "birch", "spruce", "jungle", "acacia", "dark_oak", "crimson", "warped", "mangrove", "cherry", "bamboo", "pale_oak"]:
            if wood in block_clean:
                return f"wood_{wood}"
    
    if "_planks" in block_clean:
        for wood in ["oak", "birch", "spruce", "jungle", "acacia", "dark_oak", "crimson", "warped", "mangrove", "cherry", "bamboo", "pale_oak"]:
            if wood in block_clean:
                return f"wood_{wood}"
    
    if "grass" in block_clean and block_clean != "grass_block":
        return "short_grass"
    
    if "_coral" in block_clean:
        if "tube" in block_clean:
            return "coral_tube"
        elif "brain" in block_clean:
            return "coral_brain"
        elif "bubble" in block_clean:
            return "coral_bubble"
        elif "fire" in block_clean:
            return "coral_fire"
        elif "horn" in block_clean:
            return "coral_horn"
    
    if "sculk" in block_clean:
        if "catalyst" in block_clean:
            return "sculk_catalyst"
        elif "shrieker" in block_clean:
            return "sculk_shrieker"
        elif "sensor" in block_clean:
            return "sculk_sensor"
        elif "vein" in block_clean:
            return "sculk_vein"
        else:
            return "sculk"
    
    if "froglight" in block_clean:
        if "ochre" in block_clean:
            return "froglight_ochre"
        elif "verdant" in block_clean:
            return "froglight_verdant"
        elif "pearlescent" in block_clean:
            return "froglight_pearlescent"
    
    if "copper" in block_clean:
        if "oxidized" in block_clean:
            return "copper_oxidized"
        elif "weathered" in block_clean:
            return "copper_weathered"
        elif "exposed" in block_clean:
            return "copper_exposed"
        else:
            return "copper"
    
    return None

def get_replacement_for_block(block_name: str, target_version: str = "1.16.5") -> str:
    """Get best replacement for a block following strict type rules."""
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    block_type = get_block_type(block_name)
    
    if block_type and block_type in BLOCK_TYPES:
        type_info = BLOCK_TYPES[block_type]
        
        # Get form suffix if any
        form_suffix = ""
        for form in BLOCK_FORMS:
            if block_clean.endswith(f"_{form}"):
                form_suffix = f"_{form}"
                break
        
        # Find replacement with same form
        for replacement in type_info.can_replace_with:
            if form_suffix:
                # Try to find replacement with same form
                replacement_with_form = replacement + form_suffix
                if replacement_with_form.startswith("minecraft:"):
                    replacement_with_form = replacement_with_form[10:]
                return f"minecraft:{replacement_with_form}"
            else:
                if not replacement.startswith("minecraft:"):
                    replacement = f"minecraft:{replacement}"
                return replacement
    
    # Fallback: return air for unknown blocks
    return "minecraft:air"

def is_safe_replacement(source: str, target: str) -> bool:
    """Check if replacement follows safety rules."""
    source_type = get_block_type(source)
    target_type = get_block_type(target)
    
    if not source_type or not target_type:
        return True  # Allow if unknown
    
    source_info = BLOCK_TYPES.get(source_type)
    target_info = BLOCK_TYPES.get(target_type)
    
    if not source_info or not target_info:
        return True
    
    # NEVER: solid → liquid
    if source_info.is_solid and target_info.is_liquid:
        return False
    
    # NEVER: liquid → solid (unless intentional)
    if source_info.is_liquid and target_info.is_solid:
        return False
    
    # STRICT: leaves → only leaves
    if "leaves" in source_type and "leaves" not in target_type:
        return False
    
    # STRICT: nether plants → only nether plants
    if source_type.startswith("nether_") and not target_type.startswith("nether_"):
        return False
    
    # STRICT: coral → coral or carpet
    if source_type.startswith("coral_") and not (target_type.startswith("coral_") or target_type == "carpet"):
        return False
    
    return True

# Export
__all__ = ['BLOCK_TYPES', 'BLOCK_FORMS', 'get_block_type', 'get_replacement_for_block', 'is_safe_replacement']
