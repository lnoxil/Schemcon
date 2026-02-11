"""
Strict Replacement Rules - NO EXCEPTIONS!

These rules prevent illogical conversions like leaves->water
"""

from typing import Set, Dict, List, Tuple
from dataclasses import dataclass

# BLOCK TYPE HIERARCHY - what can replace what
# Format: source_category -> allowed_target_categories
STRICT_REPLACEMENT_RULES: Dict[str, Set[str]] = {
    # LEAVES - ONLY LEAVES!
    "leaves": {"leaves"},
    
    # WATER - ONLY WATER!
    "water": {"water"},
    "waterlogged": {"water", "air"},
    
    # LAVA - ONLY LAVA!
    "lava": {"lava"},
    
    # GRASS BLOCK - dirt-like only
    "grass_block": {"grass_block", "dirt", "podzol", "mycelium", "coarse_dirt"},
    
    # PLANTS - only plants
    "short_grass": {"short_grass", "tall_grass", "fern", "dead_bush"},
    "tall_grass": {"tall_grass", "large_fern", "short_grass"},
    "fern": {"fern", "dead_bush", "short_grass"},
    "flower": {"flower", "tall_flower", "short_grass"},
    
    # SAPLINGS - only saplings
    "sapling": {"sapling"},
    
    # WOOD - only wood variants
    "wood_log": {"wood_log", "wood_planks", "stripped_wood"},
    "wood_planks": {"wood_planks", "wood_log"},
    
    # STONE - only stone family
    "stone": {"stone", "cobblestone", "stone_bricks", "smooth_stone"},
    "cobblestone": {"cobblestone", "stone", "mossy_cobblestone"},
    "stone_bricks": {"stone_bricks", "stone", "cobblestone"},
    
    # DIRT - ground blocks
    "dirt": {"dirt", "coarse_dirt", "podzol"},
    
    # NETHER - hell dimension only
    "nether_block": {"nether_block", "netherrack", "nether_bricks"},
    "nether_plant": {"nether_plant", "nether_wart", "fungus"},
    
    # CORAL - coral or dead coral
    "coral": {"coral", "dead_coral"},
    "coral_block": {"coral_block", "dead_coral_block"},
    
    # BANNERS/FLAGS - only banners
    "banner": {"banner", "wall_banner"},
    "wall_banner": {"wall_banner", "banner"},
    
    # TORCHES - light sources
    "torch": {"torch", "wall_torch", "redstone_torch"},
    
    # LIQUIDS - strict!
    "liquid": {"liquid"},
}

# BLOCK CATEGORIES WITH THEIR TRAITS
@dataclass
class BlockCategory:
    name: str
    is_solid: bool
    is_liquid: bool
    is_plant: bool
    is_transparent: bool
    can_be_replaced_by: Set[str]
    
BLOCK_CATEGORIES: Dict[str, BlockCategory] = {
    # LEAVES
    "oak_leaves": BlockCategory("oak_leaves", True, False, True, True, {"leaves"}),
    "spruce_leaves": BlockCategory("spruce_leaves", True, False, True, True, {"leaves"}),
    "birch_leaves": BlockCategory("birch_leaves", True, False, True, True, {"leaves"}),
    "jungle_leaves": BlockCategory("jungle_leaves", True, False, True, True, {"leaves"}),
    "acacia_leaves": BlockCategory("acacia_leaves", True, False, True, True, {"leaves"}),
    "dark_oak_leaves": BlockCategory("dark_oak_leaves", True, False, True, True, {"leaves"}),
    "azalea_leaves": BlockCategory("azalea_leaves", True, False, True, True, {"leaves"}),
    "flowering_azalea_leaves": BlockCategory("flowering_azalea_leaves", True, False, True, True, {"leaves"}),
    "mangrove_leaves": BlockCategory("mangrove_leaves", True, False, True, True, {"leaves"}),
    "cherry_leaves": BlockCategory("cherry_leaves", True, False, True, True, {"leaves"}),
    "pale_oak_leaves": BlockCategory("pale_oak_leaves", True, False, True, True, {"leaves"}),
    
    # LIQUIDS
    "water": BlockCategory("water", False, True, False, True, {"water"}),
    "lava": BlockCategory("lava", False, True, False, False, {"lava"}),
    "bubble_column": BlockCategory("bubble_column", False, True, False, True, {"water"}),
    
    # GRASS
    "short_grass": BlockCategory("short_grass", False, False, True, True, {"short_grass", "tall_grass", "fern"}),
    "tall_grass": BlockCategory("tall_grass", False, False, True, True, {"tall_grass", "short_grass", "large_fern"}),
    "fern": BlockCategory("fern", False, False, True, True, {"fern", "dead_bush"}),
    "large_fern": BlockCategory("large_fern", False, False, True, True, {"large_fern", "tall_grass"}),
    "dead_bush": BlockCategory("dead_bush", False, False, True, True, {"dead_bush", "fern"}),
    
    # FLOWERS
    "dandelion": BlockCategory("dandelion", False, False, True, True, {"flower"}),
    "poppy": BlockCategory("poppy", False, False, True, True, {"flower"}),
    "blue_orchid": BlockCategory("blue_orchid", False, False, True, True, {"flower"}),
    "allium": BlockCategory("allium", False, False, True, True, {"flower"}),
    "azure_bluet": BlockCategory("azure_bluet", False, False, True, True, {"flower"}),
    "oxeye_daisy": BlockCategory("oxeye_daisy", False, False, True, True, {"flower"}),
    "cornflower": BlockCategory("cornflower", False, False, True, True, {"flower"}),
    "lily_of_the_valley": BlockCategory("lily_of_the_valley", False, False, True, True, {"flower"}),
    "sunflower": BlockCategory("sunflower", False, False, True, True, {"tall_flower"}),
    "lilac": BlockCategory("lilac", False, False, True, True, {"tall_flower"}),
    "rose_bush": BlockCategory("rose_bush", False, False, True, True, {"tall_flower"}),
    "peony": BlockCategory("peony", False, False, True, True, {"tall_flower"}),
    
    # SAPLINGS
    "oak_sapling": BlockCategory("oak_sapling", False, False, True, True, {"sapling"}),
    "spruce_sapling": BlockCategory("spruce_sapling", False, False, True, True, {"sapling"}),
    "birch_sapling": BlockCategory("birch_sapling", False, False, True, True, {"sapling"}),
    "jungle_sapling": BlockCategory("jungle_sapling", False, False, True, True, {"sapling"}),
    "acacia_sapling": BlockCategory("acacia_sapling", False, False, True, True, {"sapling"}),
    "dark_oak_sapling": BlockCategory("dark_oak_sapling", False, False, True, True, {"sapling"}),
    "mangrove_propagule": BlockCategory("mangrove_propagule", False, False, True, True, {"sapling"}),
    "cherry_sapling": BlockCategory("cherry_sapling", False, False, True, True, {"sapling"}),
    "pale_oak_sapling": BlockCategory("pale_oak_sapling", False, False, True, True, {"sapling"}),
    
    # BANNERS
    "white_banner": BlockCategory("white_banner", False, False, False, True, {"banner"}),
    "white_wall_banner": BlockCategory("white_wall_banner", False, False, False, True, {"wall_banner"}),
    # ... all other banner colors follow same pattern
}

def get_block_strict_category(block_name: str) -> str:
    """Get strict category for a block."""
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    
    # Direct lookup
    if block_clean in BLOCK_CATEGORIES:
        cat = BLOCK_CATEGORIES[block_clean]
        if cat.is_liquid:
            return "liquid"
        elif "leaves" in block_clean:
            return "leaves"
        elif block_clean.endswith("_wall_banner"):
            return "wall_banner"
        elif block_clean.endswith("_banner"):
            return "banner"
    
    # Pattern matching
    if "leaves" in block_clean:
        return "leaves"
    elif block_clean in ["water", "flowing_water", "bubble_column", "kelp", "kelp_plant", "seagrass", "tall_seagrass"]:
        return "water"
    elif block_clean.endswith("_wall_banner"):
        return "wall_banner"
    elif block_clean.endswith("_banner"):
        return "banner"
    elif block_clean.endswith("_sapling") or block_clean == "mangrove_propagule":
        return "sapling"
    elif any(x in block_clean for x in ["grass", "fern", "dead_bush"]):
        return "short_grass"
    elif any(x in block_clean for x in ["dandelion", "poppy", "orchid", "allium", "bluet", "daisy", "cornflower", "lily"]):
        return "flower"
    elif any(x in block_clean for x in ["sunflower", "lilac", "rose_bush", "peony"]):
        return "tall_flower"
    elif any(x in block_clean for x in ["torchflower", "pitcher_plant"]):
        return "flower"
    
    return "unknown"

def is_safe_replacement_strict(source: str, target: str) -> bool:
    """STRICT safety check - NO EXCEPTIONS!"""
    source_cat = get_block_strict_category(source)
    target_cat = get_block_strict_category(target)
    
    # LEAVES can ONLY become LEAVES!
    if source_cat == "leaves" and target_cat != "leaves":
        return False
    
    # WATER can ONLY become WATER!
    if source_cat == "water" and target_cat != "water":
        return False
    
    # LIQUIDS cannot become SOLIDS
    source_traits = BLOCK_CATEGORIES.get(source.replace("minecraft:", "").split("[")[0])
    target_traits = BLOCK_CATEGORIES.get(target.replace("minecraft:", "").split("[")[0])
    
    if source_traits and target_traits:
        # Liquid -> Non-liquid = FORBIDDEN
        if source_traits.is_liquid and not target_traits.is_liquid:
            return False
        # Non-liquid -> Liquid = FORBIDDEN  
        if not source_traits.is_liquid and target_traits.is_liquid:
            return False
        
        # Solid block cannot become transparent plant (leaves exception above)
        if source_traits.is_solid and target_traits.is_plant and target_cat != "leaves":
            return False
    
    return True

# FORMS - block shapes
BLOCK_FORMS = ["stairs", "slab", "door", "trapdoor", "fence", "fence_gate", "wall", "button", "pressure_plate", "sign", "hanging_sign"]

def get_block_form(block_name: str) -> str:
    """Get the form/shape of a block."""
    block_clean = block_name.replace("minecraft:", "").split("[")[0]
    
    for form in BLOCK_FORMS:
        if f"_{form}" in block_clean:
            return form
    
    return "block"
