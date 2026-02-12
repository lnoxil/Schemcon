from __future__ import annotations

from collections import Counter
from math import ceil, log2
from pathlib import Path

import nbtlib

from .matcher import pick_best_match
from .schem import load_schematic, save_schematic
from .schem import _decode_packed_indices, _encode_packed_indices, _encode_varint, _normalize_blockstate_string
from .block_gradients import (
    get_block_category, get_block_gradient, find_best_block_match,
    is_block_available_in_version, COLOR_GRADIENTS, BLOCK_CATEGORIES
)


def _split_blockstate(name: str) -> tuple[str, str | None]:
    if "[" in name and name.endswith("]"):
        block, rest = name.split("[", 1)
        return block, rest[:-1]
    return name, None


def _as_base_blockstate(name: str) -> str:
    base, _props = _split_blockstate(name)
    return base




LEGACY_BLOCK_ALIASES = {
    "minecraft:grass": "minecraft:grass_block",
    "minecraft:grass_path": "minecraft:dirt_path",
    "minecraft:flowing_water": "minecraft:water",
    "minecraft:flowing_lava": "minecraft:lava",
    "minecraft:brick_block": "minecraft:bricks",
    "minecraft:melon_block": "minecraft:melon",
    "minecraft:standing_sign": "minecraft:oak_sign",
    "minecraft:wall_sign": "minecraft:oak_wall_sign",
    "minecraft:wall_banner": "minecraft:white_wall_banner",
    "minecraft:bed": "minecraft:red_bed",
    "minecraft:wooden_button": "minecraft:oak_button",
    "minecraft:double_fern": "minecraft:tall_grass",
    "minecraft:double_stone_slab2": "minecraft:smooth_stone_slab",
    "minecraft:red_sandstone_double_slab": "minecraft:red_sandstone_slab",
    "minecraft:quartz_double_slab": "minecraft:quartz_slab",
    "minecraft:acacia_double_slab": "minecraft:acacia_slab",
    "minecraft:dark_oak_double_slab": "minecraft:dark_oak_slab",
    "minecraft:cobblestone_double_slab": "minecraft:cobblestone_slab",
    "minecraft:brick_double_slab": "minecraft:brick_slab",
}

for _color in [
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
]:
    LEGACY_BLOCK_ALIASES[f"minecraft:{_color}_stained_hardened_clay"] = f"minecraft:{_color}_terracotta"


_ALLOWED_PROPS_BY_EXACT = {
    "minecraft:oak_button": {"face", "facing", "powered"},
    "minecraft:heavy_weighted_pressure_plate": {"power"},
    "minecraft:light_weighted_pressure_plate": {"power"},
    "minecraft:oak_wall_sign": {"facing", "waterlogged"},
    "minecraft:oak_sign": {"rotation", "waterlogged"},
    "minecraft:white_wall_banner": {"facing"},
    "minecraft:red_bed": {"facing", "occupied", "part"},
}

_ALLOWED_PROPS_BY_SUFFIX = {
    "_slab": {"type", "waterlogged"},
    "_stairs": {"facing", "half", "shape", "waterlogged"},
    "_button": {"face", "facing", "powered"},
    "_pressure_plate": {"power", "powered"},
    "_wall_sign": {"facing", "waterlogged"},
    "_sign": {"rotation", "waterlogged"},
    "_wall_banner": {"facing"},
    "_door": {"facing", "half", "hinge", "open", "powered"},
    "_trapdoor": {"facing", "half", "open", "powered", "waterlogged"},
    "_fence_gate": {"facing", "open", "in_wall", "powered"},
    "_fence": {"north", "south", "east", "west", "waterlogged"},
    "_wall": {"up", "north", "south", "east", "west", "waterlogged"},
    "_pane": {"north", "south", "east", "west", "waterlogged"},
}


def _canonicalize_blockstate_name(value: str) -> str:
    base, props = _split_blockstate(value)
    canonical_base = LEGACY_BLOCK_ALIASES.get(base, base)
    if not props:
        return canonical_base

    parsed_props: dict[str, str] = {}
    for item in props.split(","):
        if "=" not in item:
            continue
        key, raw_val = item.split("=", 1)
        parsed_props[key.strip()] = raw_val.strip()

    allowed = _ALLOWED_PROPS_BY_EXACT.get(canonical_base)
    if allowed is None:
        for suffix, suffix_allowed in _ALLOWED_PROPS_BY_SUFFIX.items():
            if canonical_base.endswith(suffix):
                allowed = suffix_allowed
                break

    # If we don't have explicit rules for this block type,
    # preserve its state instead of dropping potentially valid properties
    # (e.g. fences, gates, walls, panes and other directional blocks).
    if allowed is None:
        return f"{canonical_base}[{props}]"

    filtered = {k: v for k, v in parsed_props.items() if k in allowed}

    # Legacy double slabs should become modern slabs with type=double.
    if base.endswith("_double_slab") or base.endswith("_double_slab2") or "double_slab" in base:
        filtered["type"] = "double"

    # Legacy booleans on plates/buttons are represented differently between versions.
    if canonical_base.endswith("_pressure_plate") and "powered" in filtered and "power" not in filtered:
        filtered["power"] = "15" if filtered["powered"] == "true" else "0"
        filtered.pop("powered", None)

    # Keep deterministic property order to avoid palette bloat.
    if not filtered:
        return canonical_base
    props_str = ",".join(f"{k}={filtered[k]}" for k in sorted(filtered))
    return f"{canonical_base}[{props_str}]"


def _sanitize_mapped_target(target: str, allowed_targets: set[str] | None = None) -> str:
    normalized = _canonicalize_blockstate_name(_normalize_blockstate_string(target))
    base = _as_base_blockstate(normalized)

    if allowed_targets is None:
        return normalized

    # Registry-based allow-lists may contain legacy ids; compare on canonicalized forms too.
    canonical_allowed: set[str] = set()
    canonical_allowed_bases: set[str] = set()
    for raw in allowed_targets:
        canon = _canonicalize_blockstate_name(_normalize_blockstate_string(raw))
        canonical_allowed.add(canon)
        canonical_allowed_bases.add(_as_base_blockstate(canon))

    # Registry-based allow-lists generally contain only base block ids.
    # If base exists in target version, keep full blockstate properties.
    if normalized in allowed_targets or normalized in canonical_allowed:
        return normalized
    if base in allowed_targets or base in canonical_allowed_bases:
        return normalized
    return "minecraft:air"
def _decode_varint_block_data(data: bytes, expected_count: int) -> list[int]:
    values: list[int] = []
    value = 0
    shift = 0
    for byte in data:
        unsigned = byte & 0xFF
        value |= (unsigned & 0x7F) << shift
        if (unsigned & 0x80) == 0:
            values.append(value)
            if len(values) >= expected_count:
                break
            value = 0
            shift = 0
        else:
            shift += 7
            if shift > 35:
                values.append(0)
                value = 0
                shift = 0

    if len(values) < expected_count:
        values.extend([0] * (expected_count - len(values)))

    return values


def _rebuild_root_palette_blockdata(
    schematic,
    targets_by_old_index: dict[int, str],
) -> bool:
    root = schematic.root
    
    # Check for nested Sponge v1 structure
    if "Schematic" in root and "Blocks" in root["Schematic"]:
        return _rebuild_nested_palette_blockdata(schematic, targets_by_old_index)
    
    palette_tag = root.get("Palette")
    block_data = root.get("BlockData")
    if not isinstance(palette_tag, nbtlib.Compound) or block_data is None:
        return False

    width = int(root.get("Width", 0))
    height = int(root.get("Height", 0))
    length = int(root.get("Length", 0))
    volume = width * height * length
    if volume <= 0:
        return False

    version = int(root.get("Version", 2))
    old_palette_size = max(1, len(palette_tag))
    if version >= 3:
        bits = max(2, ceil(log2(old_palette_size)))
        decoded = _decode_packed_indices(list(block_data), volume, bits)
    else:
        decoded = _decode_varint_block_data(bytes(block_data), volume)

    new_palette: dict[str, int] = {"minecraft:air": 0}
    remapped: list[int] = []
    for old_index in decoded:
        target = targets_by_old_index.get(old_index, "minecraft:air")
        if target not in new_palette:
            new_palette[target] = len(new_palette)
        remapped.append(new_palette[target])

    if version >= 3:
        bits_per_entry = max(2, ceil(log2(max(1, len(new_palette)))))
        encoded = _encode_packed_indices(remapped, bits_per_entry)
    else:
        raw = bytearray()
        for idx in remapped:
            raw.extend(_encode_varint(idx))
        encoded = bytes(raw)

    root["Palette"] = nbtlib.Compound({name: nbtlib.Int(idx) for name, idx in new_palette.items()})
    root["PaletteMax"] = nbtlib.Int(len(new_palette))
    root["BlockData"] = nbtlib.ByteArray(list(encoded))
    return True


def _rebuild_nested_palette_blockdata(
    schematic,
    targets_by_old_index: dict[int, str],
) -> bool:
    """Rebuild palette and block data for nested Sponge v1 format (Schematic.Blocks)."""
    root = schematic.root
    
    if "Schematic" not in root or "Blocks" not in root["Schematic"]:
        return False
    
    inner = root["Schematic"]
    blocks = inner["Blocks"]
    
    if "Palette" not in blocks or "Data" not in blocks:
        return False
    
    palette_tag = blocks["Palette"]
    block_data = blocks["Data"]
    
    if not isinstance(palette_tag, nbtlib.Compound) or block_data is None:
        return False

    width = int(inner.get("Width", 0))
    height = int(inner.get("Height", 0))
    length = int(inner.get("Length", 0))
    volume = width * height * length
    if volume <= 0:
        return False

    # Sponge v1 uses varint encoding
    decoded = _decode_varint_block_data(bytes(block_data), volume)

    new_palette: dict[str, int] = {"minecraft:air": 0}
    remapped: list[int] = []
    for old_index in decoded:
        target = targets_by_old_index.get(old_index, "minecraft:air")
        if target not in new_palette:
            new_palette[target] = len(new_palette)
        remapped.append(new_palette[target])

    # Encode back to varint
    raw = bytearray()
    for idx in remapped:
        raw.extend(_encode_varint(idx))
    encoded = bytes(raw)

    # Update blocks section
    blocks["Palette"] = nbtlib.Compound({name: nbtlib.Int(idx) for name, idx in new_palette.items()})
    blocks["PaletteMax"] = nbtlib.Int(len(new_palette))
    blocks["Data"] = nbtlib.ByteArray(list(encoded))
    return True


def _resolve_target(name: str, mapping: dict[str, str], allowed_targets: set[str] | None = None) -> str:
    direct = mapping.get(name)
    if direct:
        direct_name, direct_props = _split_blockstate(direct)
        if direct_props:
            return _sanitize_mapped_target(direct, allowed_targets)
        # Most generated mappings are base-id only; preserve orientation/shape
        # from source blockstate when possible.
        with_props = _apply_source_properties(name, _as_base_blockstate(direct_name))
        return _sanitize_mapped_target(with_props, allowed_targets)
    base, _props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if mapped_base:
        mapped_name, mapped_props = _split_blockstate(mapped_base)
        if mapped_props:
            return _sanitize_mapped_target(mapped_base, allowed_targets)
        # If mapping only specifies target base id, preserve important geometric
        # properties from source (stairs/slabs/doors/...)
        # to avoid rotated/wrong-shape replacements after downgrade.
        with_props = _apply_source_properties(name, _as_base_blockstate(mapped_name))
        return _sanitize_mapped_target(with_props, allowed_targets)
    
    # Fallback: try to find similar block in allowed_targets
    if allowed_targets:
        fallback = _find_similar_block(name, allowed_targets)
        if fallback:
            # Apply properties from source to fallback
            return _apply_source_properties(name, fallback)
    
    return "minecraft:air"


def _find_similar_block(source: str, allowed_targets: set[str]) -> str | None:
    """Find a similar block in allowed_targets using category and color-based matching."""
    # Use the gradient-based matching system from block_gradients
    return find_best_block_match(source, allowed_targets)


def _facing_to_rotation(facing: str) -> str:
    # Minecraft sign rotation values for cardinal directions.
    mapping = {
        "south": "0",
        "west": "4",
        "north": "8",
        "east": "12",
    }
    return mapping.get(facing, "8")


def _apply_source_properties(source: str, target: str) -> str:
    """Copy relevant properties from source block to target block, with smart defaults."""
    source_base, source_props_str = _split_blockstate(source)
    target_base, target_props_str = _split_blockstate(target)

    # Parse source properties
    source_props = {}
    if source_props_str:
        for item in source_props_str.split(","):
            if "=" in item:
                key, val = item.split("=", 1)
                source_props[key.strip()] = val.strip()

    # Build result properties based on block type
    result_props = {}

    # Stairs-specific properties
    if "stairs" in target_base:
        if "half" in source_props:
            result_props["half"] = source_props["half"]
        else:
            result_props["half"] = "bottom"
        if "facing" in source_props:
            result_props["facing"] = source_props["facing"]
        else:
            result_props["facing"] = "north"
        if "shape" in source_props:
            result_props["shape"] = source_props["shape"]
        else:
            result_props["shape"] = "straight"
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    # Slab-specific properties
    elif "slab" in target_base:
        if "type" in source_props:
            result_props["type"] = source_props["type"]
        else:
            result_props["type"] = "bottom"
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    # Sign-specific properties (important for correct orientation when replacing trapdoors/hatches etc.)
    elif target_base.endswith("_wall_sign"):
        if "facing" in source_props:
            result_props["facing"] = source_props["facing"]
        elif "rotation" in source_props:
            try:
                rot = int(source_props["rotation"]) % 16
                if rot in {0, 1, 15}:
                    result_props["facing"] = "south"
                elif rot in {2, 3, 4, 5}:
                    result_props["facing"] = "west"
                elif rot in {6, 7, 8, 9}:
                    result_props["facing"] = "north"
                else:
                    result_props["facing"] = "east"
            except ValueError:
                result_props["facing"] = "north"
        else:
            result_props["facing"] = "north"
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    elif target_base.endswith("_sign"):
        if "rotation" in source_props:
            result_props["rotation"] = source_props["rotation"]
        elif "facing" in source_props:
            result_props["rotation"] = _facing_to_rotation(source_props["facing"])
        else:
            result_props["rotation"] = "8"
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    # Door-specific properties
    elif "door" in target_base and "trapdoor" not in target_base:
        if "facing" in source_props:
            result_props["facing"] = source_props["facing"]
        else:
            result_props["facing"] = "north"
        if "half" in source_props:
            result_props["half"] = source_props["half"]
        else:
            result_props["half"] = "lower"
        if "hinge" in source_props:
            result_props["hinge"] = source_props["hinge"]
        else:
            result_props["hinge"] = "left"
        if "open" in source_props:
            result_props["open"] = source_props["open"]
        else:
            result_props["open"] = "false"

    # Trapdoor-specific properties
    elif "trapdoor" in target_base:
        if "facing" in source_props:
            result_props["facing"] = source_props["facing"]
        else:
            result_props["facing"] = "north"
        if "half" in source_props:
            result_props["half"] = source_props["half"]
        else:
            result_props["half"] = "bottom"
        if "open" in source_props:
            result_props["open"] = source_props["open"]
        else:
            result_props["open"] = "false"

    # Fence gate-specific properties
    elif "fence_gate" in target_base:
        if "facing" in source_props:
            result_props["facing"] = source_props["facing"]
        else:
            result_props["facing"] = "north"
        if "open" in source_props:
            result_props["open"] = source_props["open"]
        else:
            result_props["open"] = "false"
        if "in_wall" in source_props:
            result_props["in_wall"] = source_props["in_wall"]
        else:
            result_props["in_wall"] = "false"
        if "powered" in source_props:
            result_props["powered"] = source_props["powered"]

    # Fence-specific connection properties
    elif target_base.endswith("_fence"):
        for side in ("north", "south", "east", "west"):
            if side in source_props:
                result_props[side] = source_props[side]
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    # Wall-specific connection properties
    elif target_base.endswith("_wall"):
        for key in ("up", "north", "south", "east", "west"):
            if key in source_props:
                result_props[key] = source_props[key]
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    # Glass pane/iron bars style connection properties
    elif target_base.endswith("_pane") or target_base.endswith("iron_bars"):
        for side in ("north", "south", "east", "west"):
            if side in source_props:
                result_props[side] = source_props[side]
        if "waterlogged" in source_props:
            result_props["waterlogged"] = source_props["waterlogged"]

    # Button/pressure plate properties
    elif "button" in target_base or "pressure_plate" in target_base:
        if "powered" in source_props:
            result_props["powered"] = source_props["powered"]
        else:
            result_props["powered"] = "false"
        if "button" in target_base and "face" in source_props:
            result_props["face"] = source_props["face"]
        elif "button" in target_base:
            result_props["face"] = "wall"
        if "facing" in source_props:
            result_props["facing"] = source_props["facing"]
        else:
            result_props["facing"] = "north"

    if result_props:
        props_str = ",".join(f"{k}={v}" for k, v in result_props.items())
        return f"{target_base}[{props_str}]"

    return target


def _resolve_smart_target(name: str, mapping: dict[str, dict], allowed_targets: set[str] | None = None) -> dict:
    direct = mapping.get(name)
    if isinstance(direct, dict):
        raw_target = str(direct.get("target", "minecraft:air"))
        target_base, target_props = _split_blockstate(raw_target)
        target_candidate = raw_target if target_props else _apply_source_properties(name, _as_base_blockstate(target_base))
        target = _sanitize_mapped_target(target_candidate, allowed_targets)
        return {
            "target": target,
            "reason": direct.get("reason", "direct"),
            "confidence": direct.get("confidence", 0.0),
            "changed": target != name,
        }

    base, _props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if isinstance(mapped_base, dict):
        mapped_target = str(mapped_base.get("target", base))
        mapped_name, mapped_props = _split_blockstate(mapped_target)
        if not mapped_props:
            mapped_target = _apply_source_properties(name, _as_base_blockstate(mapped_name))
        mapped_target = _sanitize_mapped_target(mapped_target, allowed_targets)
        return {
            "target": mapped_target,
            "reason": mapped_base.get("reason", "base_state_fallback"),
            "confidence": mapped_base.get("confidence", 0.0),
            "changed": mapped_target != name,
        }

    return {
        "target": "minecraft:air",
        "reason": "unmapped_to_air",
        "confidence": 0.0,
        "changed": name != "minecraft:air",
    }


def build_mapping(
    source_blocks: set[str],
    target_blocks: set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> dict[str, str]:
    mapping = {}
    for block in sorted(source_blocks):
        result = pick_best_match(block, target_blocks, gradient_map=gradient_map)
        mapping[block] = result.target
    return mapping


def build_smart_mapping(
    source_blocks: set[str],
    target_blocks: set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> dict[str, dict]:
    mapping = {}
    for block in sorted(source_blocks):
        result = pick_best_match(block, target_blocks, gradient_map=gradient_map)
        mapping[block] = {
            "target": result.target,
            "reason": result.reason,
            "confidence": result.confidence,
            "changed": result.source != result.target,
        }
    return mapping


def apply_mapping_to_palette(
    palette: dict[str, int],
    mapping: dict[str, str],
    allowed_targets: set[str] | None = None,
) -> tuple[dict[str, int], list[str]]:
    new_palette = {}
    warnings = []
    air_index = palette.get("minecraft:air", 0)
    new_palette["minecraft:air"] = air_index

    for name, index in palette.items():
        if name == "minecraft:air":
            continue
        target = _resolve_target(name, mapping, allowed_targets)
        if target == "minecraft:air":
            warnings.append(f"Unmapped block {name}; replaced with {target} for FAWE safety.")
        new_palette[target] = index

    return new_palette, warnings


def apply_smart_mapping_to_palette(
    palette: dict[str, int],
    mapping: dict[str, dict],
    allowed_targets: set[str] | None = None,
) -> tuple[dict[str, int], list[dict], list[dict]]:
    new_palette = {}
    warnings = []
    replacements = []
    air_index = palette.get("minecraft:air", 0)
    new_palette["minecraft:air"] = air_index
    replacements.append(
        {
            "source": "minecraft:air",
            "target": "minecraft:air",
            "index": air_index,
            "reason": "air_preserved",
            "confidence": 1.0,
            "changed": False,
        }
    )

    for name, index in palette.items():
        if name == "minecraft:air":
            continue
        mapping_info = _resolve_smart_target(name, mapping, allowed_targets)

        target = mapping_info["target"]
        if target == "minecraft:air":
            warnings.append(
                {
                    "type": "unmapped_to_air",
                    "source": name,
                    "target": target,
                    "confidence": mapping_info.get("confidence", 0.0),
                    "reason": mapping_info.get("reason", "unmapped_to_air"),
                    "message": f"Unmapped block {name}; replaced with {target} for FAWE safety.",
                }
            )

        if mapping_info["changed"] and mapping_info["confidence"] < 0.5:
            warnings.append(
                {
                    "type": "low_confidence",
                    "source": name,
                    "target": target,
                    "confidence": mapping_info["confidence"],
                    "reason": mapping_info["reason"],
                    "message": f"Low confidence replacement: {name} -> {target} (confidence: {mapping_info['confidence']:.1%})",
                }
            )

        new_palette[target] = index

        replacements.append(
            {
                "source": name,
                "target": target,
                "index": index,
                "reason": mapping_info["reason"],
                "confidence": mapping_info["confidence"],
                "changed": mapping_info["changed"],
            }
        )

    return new_palette, warnings, replacements


def convert_schematic(
    input_path: str,
    output_path: str,
    mapping: dict[str, str],
    allowed_targets: set[str] | None = None,
) -> dict:
    schematic = load_schematic(input_path)
    palette = schematic.palette
    new_palette, warnings = apply_mapping_to_palette(palette, mapping, allowed_targets)
    targets_by_old_index = {
        int(index): _resolve_target(name, mapping, allowed_targets)
        for name, index in palette.items()
    }
    if not _rebuild_root_palette_blockdata(schematic, targets_by_old_index):
        schematic.replace_palette(new_palette)
    save_schematic(schematic, output_path)

    counter = Counter()
    palette_mapping = []
    unchanged = 0
    for name in palette:
        mapped = _resolve_target(name, mapping, allowed_targets)
        if mapped == name:
            unchanged += 1
            continue
        counter[mapped] += 1
        palette_mapping.append({"source": name, "target": mapped})

    input_size = Path(input_path).stat().st_size
    output_size = Path(output_path).stat().st_size

    def _gzip_magic(path: str) -> bool:
        try:
            with open(path, "rb") as handle:
                return handle.read(2) == b"\x1f\x8b"
        except OSError:
            return False

    return {
        "input": input_path,
        "output": output_path,
        "unique_blocks": len(palette),
        "unchanged_blocks": unchanged,
        "changed_blocks": len(palette_mapping),
        "warnings": warnings,
        "mapped_blocks": dict(counter),
        "palette_mapping": palette_mapping,
        "file_sizes": {
            "input_bytes": input_size,
            "output_bytes": output_size,
            "delta_bytes": output_size - input_size,
            "ratio": round((output_size / input_size), 4) if input_size else None,
            "input_is_gzipped": _gzip_magic(input_path),
            "output_is_gzipped": _gzip_magic(output_path),
        },
    }


def convert_schematic_smart(
    input_path: str,
    output_path: str,
    mapping: dict[str, dict],
    allowed_targets: set[str] | None = None,
) -> dict:
    schematic = load_schematic(input_path)
    palette = schematic.palette

    new_palette, warnings, replacements = apply_smart_mapping_to_palette(palette, mapping, allowed_targets)
    targets_by_old_index = {
        int(index): _resolve_smart_target(name, mapping, allowed_targets)["target"]
        for name, index in palette.items()
    }
    if not _rebuild_root_palette_blockdata(schematic, targets_by_old_index):
        schematic.replace_palette(new_palette)
    save_schematic(schematic, output_path)

    changed_replacements = [r for r in replacements if r["changed"]]
    changed_count = len(changed_replacements)
    unchanged_count = len(replacements) - changed_count

    confidence_groups = {
        "perfect": [],
        "high": [],
        "medium": [],
        "low": [],
        "very_low": [],
    }

    for r in replacements:
        if not r["changed"]:
            continue
        conf = r["confidence"]
        if conf >= 1.0:
            confidence_groups["perfect"].append(r)
        elif conf >= 0.8:
            confidence_groups["high"].append(r)
        elif conf >= 0.5:
            confidence_groups["medium"].append(r)
        elif conf >= 0.3:
            confidence_groups["low"].append(r)
        else:
            confidence_groups["very_low"].append(r)

    target_counter = Counter()
    for r in changed_replacements:
        target_counter[r["target"]] += 1

    input_size = Path(input_path).stat().st_size
    output_size = Path(output_path).stat().st_size

    def _gzip_magic(path: str) -> bool:
        try:
            with open(path, "rb") as handle:
                return handle.read(2) == b"\x1f\x8b"
        except OSError:
            return False

    return {
        "input": input_path,
        "output": output_path,
        "statistics": {
            "total_blocks": len(palette),
            "changed": changed_count,
            "unchanged": unchanged_count,
            "warnings": len(warnings),
            "perfect_matches": len(confidence_groups["perfect"]),
            "high_confidence": len(confidence_groups["high"]),
            "medium_confidence": len(confidence_groups["medium"]),
            "low_confidence": len(confidence_groups["low"]),
            "very_low_confidence": len(confidence_groups["very_low"]),
        },
        "confidence_breakdown": {
            level: [
                {
                    "source": r["source"],
                    "target": r["target"],
                    "confidence": r["confidence"],
                    "reason": r["reason"],
                }
                for r in items
            ]
            for level, items in confidence_groups.items()
        },
        "warnings": warnings,
        "top_replacements": [
            {"block": block, "count": count}
            for block, count in target_counter.most_common(20)
        ],
        "all_replacements": changed_replacements,
        "file_sizes": {
            "input_bytes": input_size,
            "output_bytes": output_size,
            "delta_bytes": output_size - input_size,
            "ratio": round((output_size / input_size), 4) if input_size else None,
            "input_is_gzipped": _gzip_magic(input_path),
            "output_is_gzipped": _gzip_magic(output_path),
        },
    }
