from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Optional

from .block_gradients import find_best_block_match, get_block_category
from .categories import categorize_block
from .strict_rules import is_safe_replacement_strict, get_block_strict_category


# Core 1.16.5 blocks used as extra safety for keep-as-is logic.
# Final decision still checks target_blocks set first.
BLOCKS_IN_1_16_5 = {
    "stone", "granite", "diorite", "andesite", "cobblestone",
    "grass_block", "dirt", "coarse_dirt", "podzol", "mycelium",
    "oak_log", "spruce_log", "birch_log", "jungle_log", "acacia_log", "dark_oak_log",
    "oak_planks", "spruce_planks", "birch_planks", "jungle_planks", "acacia_planks", "dark_oak_planks",
    "oak_leaves", "spruce_leaves", "birch_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves",
    "vine", "weeping_vines", "twisting_vines",
    "water", "lava", "air", "cave_air", "void_air",
}


COLORLESS_BLOCK_MAPPINGS = {
    "cherry_leaves": "birch_leaves",
    "azalea_leaves": "oak_leaves",
    "flowering_azalea_leaves": "oak_leaves",
    "mangrove_leaves": "jungle_leaves",
    "cave_vines": "vine",
    "cave_vines_plant": "vine",
    "glow_lichen": "vine",
    "hanging_roots": "vine",
    "big_dripleaf": "lily_pad",
    "small_dripleaf": "vine",
    "big_dripleaf_stem": "oak_fence",
    "small_dripleaf_stem": "oak_fence",
    "spore_blossom": "vine",
    "moss_carpet": "green_carpet",
    "moss_block": "grass_block",
    "azalea": "oak_sapling",
    "flowering_azalea": "oak_sapling",
    "short_grass": "grass",
    "tall_grass": "tall_grass",
    "fern": "fern",
    "large_fern": "large_fern",
}

EXACT_BLOCK_MAPPINGS = {
    "amethyst_block": "minecraft:purple_wool",
    "budding_amethyst": "minecraft:purple_wool",
    "amethyst_cluster": "minecraft:purple_stained_glass",
    "small_amethyst_bud": "minecraft:purple_stained_glass",
    "medium_amethyst_bud": "minecraft:purple_stained_glass",
    "large_amethyst_bud": "minecraft:purple_stained_glass",
    "pointed_dripstone": "minecraft:oak_fence",
    "dripstone_block": "minecraft:stone",
    "pink_petals": "minecraft:pink_tulip",
    "bamboo_block": "minecraft:oak_log",
    "stripped_bamboo_block": "minecraft:stripped_oak_log",
    "bamboo_mosaic": "minecraft:oak_planks",
    "bamboo_planks": "minecraft:oak_planks",
    "bamboo_slab": "minecraft:oak_slab",
    "bamboo_stairs": "minecraft:oak_stairs",
    "bamboo_fence": "minecraft:oak_fence",
    "bamboo_fence_gate": "minecraft:oak_fence_gate",
    "bamboo_trapdoor": "minecraft:oak_trapdoor",
    "bamboo_door": "minecraft:oak_door",
    "bamboo_pressure_plate": "minecraft:oak_pressure_plate",
    "bamboo_button": "minecraft:oak_button",
    "mangrove_propagule": "minecraft:oak_sapling",
    "potted_mangrove_propagule": "minecraft:potted_oak_sapling",
    "potted_flowering_azalea_bush": "minecraft:potted_azalea_bush",
    "potted_azalea_bush": "minecraft:potted_fern",
}

PREFER_FAMILIES = {"concrete", "wool"}
DISCOURAGED_FAMILIES = {"terracotta"}

COLOR_TOKEN_MAP = {
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
}


SMALL_MODEL_BLOCKS = {
    "bamboo", "bamboo_sapling", "torch", "wall_torch", "redstone_torch",
    "soul_torch", "flower_pot", "lever", "button", "rail", "powered_rail",
    "detector_rail", "activator_rail", "tripwire_hook", "string",
    "scaffolding", "lantern", "soul_lantern",
}


def _normalize_block_name(name: str) -> str:
    base = name.split("[", 1)[0]
    if ":" in base:
        return base
    return f"minecraft:{base}"


def _as_key(name: str) -> str:
    return _normalize_block_name(name).replace("minecraft:", "")


def _block_exists_in_target(source_name: str, target_blocks: Set[str]) -> bool:
    source_base = _normalize_block_name(source_name)
    source_clean = _as_key(source_base)

    if source_base in target_blocks or source_clean in target_blocks:
        return True

    # Extra 1.16.5 safety fallback for partially loaded registries.
    if source_clean in BLOCKS_IN_1_16_5:
        for target in target_blocks:
            if _as_key(target) == source_clean:
                return True
    return False


def _get_colorless_replacement(source_name: str) -> Optional[str]:
    source_clean = _as_key(source_name)
    replacement = COLORLESS_BLOCK_MAPPINGS.get(source_clean)
    if replacement:
        return f"minecraft:{replacement}"
    return None


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5


def _strict_category_compatible(source_name: str, candidate_name: str) -> bool:
    """Hard category guardrails (leaves/water/banners/liquids)."""
    source_strict_cat = get_block_strict_category(source_name)
    target_strict_cat = get_block_strict_category(candidate_name)

    if source_strict_cat == "leaves" and target_strict_cat != "leaves":
        return False
    if source_strict_cat == "water" and target_strict_cat != "water":
        return False
    if source_strict_cat in {"banner", "wall_banner"} and target_strict_cat not in {"banner", "wall_banner"}:
        return False

    # Prevent non-special blocks from turning into leaves/water/banners.
    if source_strict_cat not in {"leaves", "water"} and target_strict_cat in {"leaves", "water"}:
        return False
    if source_strict_cat not in {"banner", "wall_banner"} and target_strict_cat in {"banner", "wall_banner"}:
        return False

    return True




def _family_group(family: str) -> str:
    if family in {"log", "planks"}:
        return "wood"
    if family in {"grass", "vine", "roots", "flower", "sapling", "azalea", "plant", "lichen", "bamboo", "leaves"}:
        return "plant"
    if family in {"stone", "ore", "brick", "deepslate", "tuff", "sand", "gravel", "dirt"}:
        return "mineral"
    if family in {"mushroom"}:
        return "plant"
    return family


def _air_if_missing_for_decorative(source_name: str, target_blocks: Set[str]) -> Optional[str]:
    """Allow air only for truly hard decorative cases (candles for now)."""
    src = _as_key(source_name)
    if "candle" in src or "candle_cake" in src:
        if "minecraft:air" in target_blocks or "air" in target_blocks:
            return "minecraft:air"
    return None


def _family_compatible(source_family: str, candidate_family: str) -> bool:
    src_group = _family_group(source_family)
    cand_group = _family_group(candidate_family)
    if src_group == "generic" or cand_group == "generic":
        return True
    return src_group == cand_group



SMALL_MODEL_TOKENS = {
    "bamboo",
    "sapling",
    "torch",
    "button",
    "rail",
    "lever",
    "candle",
    "vine",
    "vines",
    "lichen",
    "flower",
}


def _is_small_model(traits) -> bool:
    return any(token in traits.tokens for token in SMALL_MODEL_TOKENS)


def _special_plant_compatible(source_base: str, candidate_base: str) -> bool:
    src = source_base.replace("minecraft:", "")
    tgt = candidate_base.replace("minecraft:", "")

    # Cave vines should not become nether vines.
    if "cave_vines" in src and ("weeping_vines" in tgt or "twisting_vines" in tgt):
        return False
    if "glow_lichen" in src and "weeping_vines" in tgt:
        return False
    return True

def _resolve_color(
    block_name: str,
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> tuple[int, int, int] | None:
    """Prefer sampled texture color, fallback to name-derived color keyword."""
    key = _as_key(block_name)
    if gradient_map:
        sampled = gradient_map.get(key) or gradient_map.get(f"minecraft:{key}")
        if sampled:
            return sampled

    # Fallback from color keyword in block id (e.g. red_wool, light_blue_glass)
    return categorize_block(block_name).color


def _extract_color_tokens(block_name: str) -> set[str]:
    key = _as_key(block_name)
    found: set[str] = set()
    for token in sorted(COLOR_TOKEN_MAP, key=len, reverse=True):
        if token in key:
            found.add(token)
    return found


def _color_token_penalty(source_name: str, candidate_name: str) -> float:
    src_colors = _extract_color_tokens(source_name)
    cand_colors = _extract_color_tokens(candidate_name)
    if not src_colors or not cand_colors:
        return 0.0
    if src_colors & cand_colors:
        return 1.2
    return -8.5


def _manual_override_match(source_name: str, target_blocks: Set[str]) -> Optional[str]:
    src = _as_key(source_name)
    for key in sorted(EXACT_BLOCK_MAPPINGS.keys(), key=len, reverse=True):
        replacement = EXACT_BLOCK_MAPPINGS[key]
        if key not in src:
            continue
        repl_clean = _as_key(replacement)
        if replacement in target_blocks or repl_clean in target_blocks:
            return replacement
    return None


def _special_soft_match(source_name: str, target_blocks: Set[str]) -> Optional[str]:
    src = _as_key(source_name)
    if src == "moss_carpet":
        for cand in ["minecraft:green_carpet", "minecraft:green_wool", "minecraft:mossy_cobblestone", "minecraft:grass"]:
            clean = _as_key(cand)
            if cand in target_blocks or clean in target_blocks:
                return cand
    return None


def _same_shape_candidates(source_name: str, target_blocks: Set[str]) -> list[str]:
    src_traits = categorize_block(source_name)
    out: list[str] = []
    for target in sorted(target_blocks):
        base = target.split("[", 1)[0]
        if categorize_block(base).shape == src_traits.shape:
            out.append(base)
    return out


def _shape_suffix(base_name: str) -> str:
    base = _as_key(base_name)
    for suffix in ("_stairs", "_slab", "_wall", "_fence", "_fence_gate", "_trapdoor", "_door"):
        if base.endswith(suffix):
            return suffix
    return ""


def _pick_copper_stage_match(source_name: str, target_blocks: Set[str]) -> Optional[str]:
    src = _as_key(source_name)
    if "copper" not in src:
        return None

    shape = _shape_suffix(source_name)
    # Keep oxidation hue logic: orange->warm, exposed->tan, weathered->teal, oxidized->green/blue.
    if "oxidized" in src:
        bases = ["warped", "dark_prismarine", "prismarine"]
    elif "weathered" in src:
        bases = ["prismarine", "dark_prismarine", "warped"]
    elif "exposed" in src:
        bases = ["cut_sandstone", "smooth_sandstone", "sandstone"]
    else:
        bases = ["cut_red_sandstone", "red_sandstone", "sandstone"]

    candidates: list[str] = []
    for block in target_blocks:
        base = _as_key(block)
        if "glazed_terracotta" in base:
            continue
        if shape and not base.endswith(shape):
            continue
        if any(k in base for k in bases):
            candidates.append(block.split("[", 1)[0])

    if not candidates:
        return None
    return sorted(set(candidates))[0]


def _pick_shape_safe_match(
    source_name: str,
    target_blocks: Set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> Optional[str]:
    """Strict fallback: keep shape/type/family first, then color."""
    source_traits = categorize_block(source_name)
    src_color = _resolve_color(source_name, gradient_map)

    best: tuple[float, str] | None = None

    source_color_tokens = _extract_color_tokens(source_name)

    for candidate in sorted(target_blocks):
        candidate_base = candidate.split("[", 1)[0]
        if _as_key(candidate_base) == "air":
            continue
        candidate_traits = categorize_block(candidate_base)

        # ULTRA STRICT SAFETY CHECKS
        if not _strict_category_compatible(source_name, candidate_base):
            continue

        # Use strict safety rules
        if not is_safe_replacement_strict(source_name, candidate_base):
            continue

        source_strict_cat = get_block_strict_category(source_name)
        target_strict_cat = get_block_strict_category(candidate_base)

        # Hard safety: do not map non-liquid blocks to liquids and vice versa.
        if source_traits.block_type == "liquid" and candidate_traits.block_type != "liquid":
            continue
        if source_traits.block_type != "liquid" and candidate_traits.block_type == "liquid":
            continue
        if source_traits.block_type == "solid" and candidate_traits.block_type == "plant":
            continue
        if source_traits.block_type == "plant" and candidate_traits.block_type == "solid":
            continue

        # Avoid silly substitutions across incompatible families (e.g. stone->bamboo).
        if not _family_compatible(source_traits.family, candidate_traits.family):
            continue

        if not _special_plant_compatible(source_name, candidate_base):
            continue

        # Do not replace full blocks with tiny decorative models.
        candidate_clean = _as_key(candidate_base)
        source_clean = _as_key(source_name)
        if source_traits.shape == "full" and (candidate_clean in SMALL_MODEL_BLOCKS or _is_small_model(candidate_traits)) and source_clean not in SMALL_MODEL_BLOCKS and not _is_small_model(source_traits):
            continue

        # Keep full blocks from becoming wood if source is mineral-like.
        if (
            source_traits.shape == "full"
            and source_traits.family in {"stone", "deepslate", "blackstone", "brick", "ore", "dirt", "amethyst"}
            and candidate_traits.family in {"log", "planks"}
        ):
            continue

        # Bamboo block is a full log-like block, never map to thin bamboo plant.
        if "bamboo_block" in source_clean and candidate_clean == "bamboo":
            continue

        # Shape is the most important rule for schematic geometry.
        if source_traits.shape != candidate_traits.shape:
            continue

        score = 0.0

        # Preserve broad material behavior.
        if source_traits.block_type == candidate_traits.block_type:
            score += 6.0
        else:
            score -= 5.0

        # Preserve families (wood, stone, leaves, etc.) where possible.
        if source_traits.family == candidate_traits.family:
            score += 3.5

        if candidate_traits.family in PREFER_FAMILIES:
            score += 1.8
        if candidate_traits.family in DISCOURAGED_FAMILIES or "glazed_terracotta" in candidate_clean:
            score -= 3.2

        # Penalize crossing broad groups (mineral/wood/plant).
        if _family_group(source_traits.family) != _family_group(candidate_traits.family):
            score -= 4.5

        # Preserve category if available.
        if source_traits.category == candidate_traits.category:
            score += 4.5

        # Keep strict categories together for sensitive blocks.
        if source_strict_cat == target_strict_cat:
            score += 3.0

        # Try to keep color tone: use sampled map, fallback to keyword color.
        cand_color = _resolve_color(candidate_base, gradient_map)
        if src_color and cand_color:
            dist = _color_distance(src_color, cand_color)
            # Strongly penalize large mismatches so blue doesn't become red/brown.
            score += max(-6.0, 6.5 - (dist / 28.0))

        score += _color_token_penalty(source_name, candidate_base)

        # Keep color families aligned when source has explicit color token.
        if source_color_tokens:
            cand_colors = _extract_color_tokens(candidate_base)
            if cand_colors and not (source_color_tokens & cand_colors):
                score -= 2.5

        # Token overlap helps with wood variants (oak/cherry/etc.) and similar naming.
        overlap = len(source_traits.tokens & candidate_traits.tokens)
        score += overlap * 0.7

        if best is None or score > best[0]:
            best = (score, candidate_base)

    return best[1] if best else None


def _is_risky_category(name: str) -> bool:
    traits = categorize_block(name)
    if traits.block_type == "liquid":
        return True
    return traits.family in {
        "flower",
        "sapling",
        "leaves",
        "grass",
        "mushroom",
        "vine",
        "roots",
        "bamboo",
    } or traits.category in {
        "grass_block",
        "grass_plant",
        "tall_plant",
        "flower_small",
        "flower_tall",
        "water_plant",
        "mushroom_small",
        "mushroom_block",
    }


def _pick_relaxed_safe_match(
    source_name: str,
    target_blocks: Set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> Optional[str]:
    """Fallback matcher that still enforces strict category guardrails."""
    source_traits = categorize_block(source_name)
    src_color = _resolve_color(source_name, gradient_map)

    best: tuple[float, str] | None = None

    for candidate in sorted(target_blocks):
        candidate_base = candidate.split("[", 1)[0]
        if _as_key(candidate_base) == "air":
            continue
        candidate_traits = categorize_block(candidate_base)

        if not _strict_category_compatible(source_name, candidate_base):
            continue
        if not is_safe_replacement_strict(source_name, candidate_base):
            continue

        if source_traits.block_type == "liquid" and candidate_traits.block_type != "liquid":
            continue
        if source_traits.block_type != "liquid" and candidate_traits.block_type == "liquid":
            continue
        if source_traits.block_type == "solid" and candidate_traits.block_type == "plant":
            continue
        if source_traits.block_type == "plant" and candidate_traits.block_type == "solid":
            continue
        if not _family_compatible(source_traits.family, candidate_traits.family):
            continue
        if not _special_plant_compatible(source_name, candidate_base):
            continue
        candidate_clean = _as_key(candidate_base)
        source_clean = _as_key(source_name)
        if source_traits.shape == "full" and (candidate_clean in SMALL_MODEL_BLOCKS or _is_small_model(candidate_traits)) and source_clean not in SMALL_MODEL_BLOCKS and not _is_small_model(source_traits):
            continue
        if (
            source_traits.shape == "full"
            and source_traits.family in {"stone", "deepslate", "blackstone", "brick", "ore", "dirt", "amethyst"}
            and candidate_traits.family in {"log", "planks"}
        ):
            continue
        if "bamboo_block" in source_clean and candidate_clean == "bamboo":
            continue
        if source_traits.shape != candidate_traits.shape:
            continue

        score = 0.0
        if source_traits.block_type == candidate_traits.block_type:
            score += 3.0
        if source_traits.family == candidate_traits.family:
            score += 2.0

        if candidate_traits.family in PREFER_FAMILIES:
            score += 1.2
        if candidate_traits.family in DISCOURAGED_FAMILIES or "glazed_terracotta" in candidate_clean:
            score -= 2.4
        if source_traits.category == candidate_traits.category:
            score += 2.5

        cand_color = _resolve_color(candidate_base, gradient_map)
        if src_color and cand_color:
            score += max(-5.0, 4.0 - (_color_distance(src_color, cand_color) / 35.0))

        score += _color_token_penalty(source_name, candidate_base)

        if best is None or score > best[0]:
            best = (score, candidate_base)

    return best[1] if best else None


@dataclass(frozen=True)
class MatchResult:
    source: str
    target: str
    reason: str
    confidence: float


def pick_best_match(
    source_name: str,
    target_blocks: Set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> MatchResult:
    """
    Find the best matching block using the gradient-based system.

    IMPORTANT: If a block exists in target version, keep it EXACTLY as-is!
    Only replace blocks that don't exist in the target version.
    """
    # Extract base block name (remove properties)
    source_base = source_name.split("[", 1)[0]

    # Handle special cases
    if source_base == "minecraft:air":
        return MatchResult(source=source_name, target="minecraft:air", reason="air_preserved", confidence=1.0)

    # Check for restricted/command blocks - convert to air
    if "command_block" in source_base:
        return MatchResult(source=source_name, target="minecraft:air", reason="restricted_removed", confidence=1.0)

    # CRITICAL: Check if block exists in target version
    if _block_exists_in_target(source_name, target_blocks):
        return MatchResult(source=source_name, target=source_name, reason="exists_in_target_1.16.5", confidence=1.0)

    # Invisible technical block: if target version has no `light`, prefer removing it.
    if _as_key(source_name) == "light":
        if "minecraft:air" in target_blocks or "air" in target_blocks:
            return MatchResult(source=source_name, target="minecraft:air", reason="light_removed", confidence=0.98)

    # Special handling for colorless/foliage-like blocks.
    manual_match = _manual_override_match(source_name, target_blocks)
    if manual_match:
        return MatchResult(source=source_name, target=manual_match, reason="manual_exact_mapping", confidence=0.97)

    soft_match = _special_soft_match(source_name, target_blocks)
    if soft_match:
        return MatchResult(source=source_name, target=soft_match, reason="special_soft_mapping", confidence=0.93)

    # Special handling for colorless/foliage-like blocks.
    colorless_replacement = _get_colorless_replacement(source_name)
    if colorless_replacement:
        # only use it when target version actually has this block
        repl_clean = _as_key(colorless_replacement)
        if colorless_replacement in target_blocks or repl_clean in target_blocks:
            return MatchResult(
                source=source_name,
                target=colorless_replacement,
                reason=f"colorless_mapping({_as_key(source_name)}->{repl_clean})",
                confidence=0.95,
            )

    # Copper stage-aware fallback first (prevents oxidized->orange regressions).
    copper_match = _pick_copper_stage_match(source_name, target_blocks)
    if copper_match:
        return MatchResult(source=source_name, target=copper_match, reason="copper_stage_match", confidence=0.88)

    # If exact/manual fallback failed, allow air only for selected decorative blocks.
    air_candidate = _air_if_missing_for_decorative(source_name, target_blocks)
    if air_candidate:
        return MatchResult(source=source_name, target=air_candidate, reason="decorative_to_air", confidence=0.65)

    # Block doesn't exist in target - need to find replacement
    best_match = _pick_shape_safe_match(source_name, target_blocks, gradient_map=gradient_map)
    if not best_match:
        best_match = _pick_relaxed_safe_match(source_name, target_blocks, gradient_map=gradient_map)
    if not best_match and not _is_risky_category(source_name):
        # Extra fallback only for non-risky blocks.
        candidate = find_best_block_match(source_name, target_blocks)
        if candidate:
            src_type = categorize_block(source_name).block_type
            cand_type = categorize_block(candidate).block_type
            cand_traits = categorize_block(candidate)
            src_traits = categorize_block(source_name)
            if (
                src_type == cand_type
                and _strict_category_compatible(source_name, candidate)
                and _family_compatible(src_traits.family, cand_traits.family)
                and _special_plant_compatible(source_name, candidate)
            ):
                src_color = _resolve_color(source_name, gradient_map)
                cand_color = _resolve_color(candidate, gradient_map)
                if src_color and cand_color and _color_distance(src_color, cand_color) > 110:
                    pass
                else:
                    best_match = candidate

    if best_match:
        # Calculate confidence based on category match
        source_cat = get_block_category(source_name)
        target_cat = get_block_category(best_match)

        if source_cat and target_cat and source_cat == target_cat:
            confidence = 0.9
            reason = f"category_match({source_cat})"
        elif source_cat and target_cat:
            confidence = 0.7
            reason = f"fallback_match({source_cat}->{target_cat})"
        else:
            confidence = 0.6
            reason = "color_match"

        return MatchResult(
            source=source_name,
            target=best_match,
            reason=reason,
            confidence=confidence,
        )

    # Last-resort: never drop arbitrary blocks to air.
    # Pick nearest by shape, then by strict compatibility + color distance.
    src_color = _resolve_color(source_name, gradient_map)
    fallback_best: tuple[float, str] | None = None
    for cand in _same_shape_candidates(source_name, target_blocks):
        if not _strict_category_compatible(source_name, cand):
            continue
        if not is_safe_replacement_strict(source_name, cand):
            continue
        cand_color = _resolve_color(cand, gradient_map)
        score = 0.0
        src_traits = categorize_block(source_name)
        cand_traits = categorize_block(cand)
        if src_traits.block_type == cand_traits.block_type:
            score += 2.0
        if _family_group(src_traits.family) == _family_group(cand_traits.family):
            score += 2.0
        score += _color_token_penalty(source_name, cand)
        if src_color and cand_color:
            score += max(-9.0, 7.0 - (_color_distance(src_color, cand_color) / 20.0))
        if fallback_best is None or score > fallback_best[0]:
            fallback_best = (score, cand)

    if fallback_best:
        return MatchResult(source=source_name, target=fallback_best[1], reason="last_resort_shape_color", confidence=0.45)

    # Absolute final fallback (still avoid air unless truly absent in target set)
    for cand in sorted(target_blocks):
        base = cand.split("[", 1)[0]
        if _as_key(base) != "air":
            return MatchResult(source=source_name, target=base, reason="last_resort_any_block", confidence=0.25)

    return MatchResult(source=source_name, target="minecraft:air", reason="no_match", confidence=0.0)
