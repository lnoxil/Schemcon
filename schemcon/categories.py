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
    "grass": "grass",
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
    "mushroom": "mushroom",
    "flowering": "plant",
    "roots": "plant",
    "crop": "plant",
    "bamboo": "plant",
    "seagrass": "plant",
    "kelp": "plant",
    "vine": "plant",
    "tall_grass": "plant",
    "short_grass": "plant",
    "grass": "plant",
    "fern": "plant",
    "azalea": "plant",
    "berry": "plant",
    "torchflower": "plant",
    "pitcher": "plant",
}

SPECIAL_CASES = {
    "air": "air",
    "cave_air": "air",
    "void_air": "air",
    "water": "fluid",
    "lava": "fluid",
}


@dataclass(frozen=True)
class BlockTraits:
    name: str
    base_name: str
    shape: str
    family: str
    color: tuple[int, int, int] | None
    tokens: set[str]


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
    return SPECIAL_CASES.get(name, "generic")


def categorize_block(name: str) -> BlockTraits:
    base_name = _normalize_name(name)
    tokens = set(base_name.split("_"))
    shape = _detect_shape(tokens, base_name)
    family = _detect_family(tokens, base_name)
    color = _detect_color(base_name)
    return BlockTraits(
        name=name,
        base_name=base_name,
        shape=shape,
        family=family,
        color=color,
        tokens=tokens,
    )
