from __future__ import annotations

from dataclasses import dataclass

COLOR_KEYWORDS = {
    "white": (240, 240, 240),
    "light_gray": (180, 180, 180),
    "gray": (120, 120, 120),
    "black": (30, 30, 30),
    "red": (180, 40, 40),
    "orange": (210, 120, 40),
    "yellow": (210, 190, 40),
    "lime": (140, 190, 40),
    "green": (70, 140, 70),
    "cyan": (50, 170, 170),
    "light_blue": (80, 150, 210),
    "blue": (60, 90, 170),
    "purple": (120, 70, 160),
    "magenta": (190, 80, 170),
    "pink": (210, 140, 170),
    "brown": (110, 80, 50),
}

SHAPE_RULES = {
    "slab": "slab",
    "stairs": "stairs",
    "wall": "wall",
    "fence_gate": "fence_gate",
    "fence": "fence",
    "trapdoor": "trapdoor",
    "door": "door",
    "carpet": "carpet",
    "pane": "pane",
    "pressure_plate": "pressure_plate",
    "button": "button",
    "sign": "sign",
    "torch": "torch",
    "lantern": "lantern",
    "rail": "rail",
    "ladder": "ladder",
    "banner": "banner",
    "bed": "bed",
    "candle": "candle",
}

FAMILY_RULES = {
    "flower": "flower",
    "sapling": "sapling",
    "coral": "coral",
    "glass": "glass",
    "wool": "wool",
    "terracotta": "terracotta",
    "concrete": "concrete",
    "log": "log",
    "planks": "planks",
    "leaves": "leaves",
    "dirt": "dirt",
    "stone": "stone",
    "ore": "ore",
    "sand": "sand",
    "gravel": "gravel",
    "ice": "ice",
    "snow": "snow",
    "brick": "brick",
    "tuff": "tuff",
    "deepslate": "deepslate",
    "prismarine": "prismarine",
    "nether": "nether",
    "end": "end",
}

BLOCK_CATEGORIES = {
    "water": "liquid_water",
    "lava": "liquid_lava",
    "flowing_water": "liquid_water",
    "flowing_lava": "liquid_lava",
    "air": "air",
    "cave_air": "air",
    "void_air": "air",
    "grass": "grass_block",
    "grass_block": "grass_block",
    "short_grass": "grass_plant",
    "tall_grass": "tall_plant",
    "fern": "grass_plant",
    "large_fern": "tall_plant",
    "brown_mushroom": "mushroom_small",
    "red_mushroom": "mushroom_small",
    "brown_mushroom_block": "mushroom_block",
    "red_mushroom_block": "mushroom_block",
    "mushroom_stem": "mushroom_block",
    "dandelion": "flower_small",
    "poppy": "flower_small",
    "blue_orchid": "flower_small",
    "allium": "flower_small",
    "azure_bluet": "flower_small",
    "tulip": "flower_small",
    "oxeye_daisy": "flower_small",
    "cornflower": "flower_small",
    "lily_of_the_valley": "flower_small",
    "wither_rose": "flower_small",
    "sunflower": "flower_tall",
    "lilac": "flower_tall",
    "rose_bush": "flower_tall",
    "peony": "flower_tall",
    "oak_sapling": "sapling",
    "spruce_sapling": "sapling",
    "birch_sapling": "sapling",
    "jungle_sapling": "sapling",
    "acacia_sapling": "sapling",
    "dark_oak_sapling": "sapling",
    "cherry_sapling": "sapling",
    "mangrove_propagule": "sapling",
    "wheat": "crop",
    "carrots": "crop",
    "potatoes": "crop",
    "beetroots": "crop",
    "sweet_berry_bush": "crop",
    "torchflower_crop": "crop",
    "pitcher_crop": "crop",
    "seagrass": "water_plant",
    "tall_seagrass": "water_plant",
    "kelp": "water_plant",
    "kelp_plant": "water_plant",
    "vine": "vine",
    "weeping_vines": "vine",
    "twisting_vines": "vine",
    "cave_vines": "vine",
    "hanging_roots": "roots",
    "mangrove_roots": "roots",
    "bamboo": "bamboo",
    "bamboo_sapling": "bamboo",
}

BLOCK_PROPERTIES = {
    "solid": {
        "stone",
        "dirt",
        "grass_block",
        "cobblestone",
        "planks",
        "log",
        "wool",
        "concrete",
        "terracotta",
        "glass",
        "sand",
        "gravel",
        "ore",
        "brick",
    },
    "plant": {
        "grass_plant",
        "tall_plant",
        "flower_small",
        "flower_tall",
        "sapling",
        "crop",
        "water_plant",
        "vine",
        "roots",
        "bamboo",
        "mushroom_small",
    },
    "liquid": {
        "liquid_water",
        "liquid_lava",
    },
}


@dataclass(frozen=True)
class BlockTraits:
    name: str
    base_name: str
    shape: str
    family: str
    color: tuple[int, int, int] | None
    tokens: set[str]
    category: str
    block_type: str


def _detect_color(name: str) -> tuple[int, int, int] | None:
    for keyword, rgb in COLOR_KEYWORDS.items():
        if keyword in name:
            return rgb
    return None


def _normalize_name(name: str) -> str:
    if ":" in name:
        return name.split(":", 1)[1]
    return name


def _detect_shape(tokens: set[str], name: str) -> str:
    for needle, shape in SHAPE_RULES.items():
        if needle in name or needle in tokens:
            return shape
    return "full"


def _detect_family(tokens: set[str], name: str) -> str:
    for needle, family in FAMILY_RULES.items():
        if needle in name or needle in tokens:
            return family
    return "generic"


def _detect_category(base_name: str) -> str:
    if base_name in BLOCK_CATEGORIES:
        return BLOCK_CATEGORIES[base_name]

    for key, category in BLOCK_CATEGORIES.items():
        if key in base_name:
            return category

    return "generic"


def _detect_block_type(category: str, family: str) -> str:
    for block_type, categories in BLOCK_PROPERTIES.items():
        if category in categories:
            return block_type

    if family in {"flower", "sapling"}:
        return "plant"
    if family in {"glass", "wool", "concrete", "stone", "dirt"}:
        return "solid"

    return "solid"


def categorize_block(name: str) -> BlockTraits:
    base_name = _normalize_name(name)
    tokens = set(base_name.split("_"))
    shape = _detect_shape(tokens, base_name)
    family = _detect_family(tokens, base_name)
    color = _detect_color(base_name)
    category = _detect_category(base_name)
    block_type = _detect_block_type(category, family)

    return BlockTraits(
        name=name,
        base_name=base_name,
        shape=shape,
        family=family,
        color=color,
        tokens=tokens,
        category=category,
        block_type=block_type,
    )
