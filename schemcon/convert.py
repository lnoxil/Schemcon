from __future__ import annotations

from collections import Counter
from pathlib import Path

from .matcher import pick_best_match
from .schem import load_schematic, save_schematic


SAFE_COLLISION_STATES = (
    "minecraft:stone",
    "minecraft:dirt",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:spruce_planks",
    "minecraft:birch_planks",
    "minecraft:jungle_planks",
    "minecraft:acacia_planks",
    "minecraft:dark_oak_planks",
    "minecraft:sand",
    "minecraft:red_sand",
    "minecraft:glass",
    "minecraft:gravel",
    "minecraft:netherrack",
    "minecraft:andesite",
    "minecraft:diorite",
    "minecraft:granite",
    "minecraft:deepslate",
    "minecraft:calcite",
    "minecraft:smooth_stone",
    "minecraft:terracotta",
    "minecraft:white_wool",
    "minecraft:gray_wool",
    "minecraft:light_gray_wool",
    "minecraft:black_wool",
)


def _candidate_targets_from_mapping(mapping: dict[str, str] | dict[str, dict]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for value in mapping.values():
        raw = value.get("target") if isinstance(value, dict) else value
        if not isinstance(raw, str) or not raw:
            continue
        normalized = raw if "[" in raw else _as_base_blockstate(raw)
        if normalized == "minecraft:air" or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(normalized)
    return candidates


def _pick_safe_collision_target(
    used_targets: dict[str, int],
    _palette_name: str,
    index: int,
    extra_candidates: list[str] | None = None,
) -> str:
    if extra_candidates:
        for candidate in extra_candidates:
            existing = used_targets.get(candidate)
            if existing is None or existing == index:
                return candidate

    for candidate in SAFE_COLLISION_STATES:
        existing = used_targets.get(candidate)
        if existing is None or existing == index:
            return candidate

    # Last resort: keep air only if absolutely no safe free target remains.
    return "minecraft:air"


def _split_blockstate(name: str) -> tuple[str, str | None]:
    if "[" in name and name.endswith("]"):
        block, rest = name.split("[", 1)
        return block, rest[:-1]
    return name, None


def _as_base_blockstate(name: str) -> str:
    base, _props = _split_blockstate(name)
    return base


def _resolve_target(name: str, mapping: dict[str, str]) -> str:
    direct = mapping.get(name)
    if direct:
        return direct
    base, _props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if mapped_base:
        mapped_name, mapped_props = _split_blockstate(mapped_base)
        if mapped_props:
            return mapped_base
        # FAWE can return null block states when legacy/newer properties are kept on
        # a base-only mapping (e.g. old property names that no longer exist). If the
        # mapping does not explicitly define a full blockstate, always emit only the
        # target base block id.
        return _as_base_blockstate(mapped_name)
    return "minecraft:air"


def _resolve_smart_target(name: str, mapping: dict[str, dict]) -> dict:
    direct = mapping.get(name)
    if isinstance(direct, dict):
        return direct

    base, _props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if isinstance(mapped_base, dict):
        mapped_target = str(mapped_base.get("target", base))
        mapped_name, mapped_props = _split_blockstate(mapped_target)
        if not mapped_props:
            mapped_target = _as_base_blockstate(mapped_name)
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


def apply_mapping_to_palette(palette: dict[str, int], mapping: dict[str, str]) -> tuple[dict[str, int], list[str]]:
    new_palette = {}
    warnings = []
    used_targets = {}
    collision_candidates = _candidate_targets_from_mapping(mapping)

    air_index = palette.get("minecraft:air")
    if air_index is not None:
        # Preserve air ID so fallback collisions never rewrite air to solid blocks.
        used_targets["minecraft:air"] = air_index
        new_palette["minecraft:air"] = air_index

    for name, index in palette.items():
        if name == "minecraft:air":
            continue
        target = _resolve_target(name, mapping)
        was_unmapped_to_air = target == "minecraft:air" and name != "minecraft:air"
        if target == "minecraft:air" and air_index is not None and air_index != index:
            target = _pick_safe_collision_target(used_targets, name, index, collision_candidates)
        existing = used_targets.get(target)

        if was_unmapped_to_air:
            warnings.append(f"Unmapped block {name}; replaced with {target} for FAWE safety.")

        if existing is not None and existing != index:
            fallback = _pick_safe_collision_target(used_targets, name, index, collision_candidates)
            if fallback != target:
                warnings.append(
                    f"Collision for {name} -> {target}; replaced with {fallback} to keep palette ids valid for FAWE."
                )
            target = fallback

        new_palette[target] = index
        used_targets[target] = index

    return new_palette, warnings


def apply_smart_mapping_to_palette(
    palette: dict[str, int],
    mapping: dict[str, dict],
) -> tuple[dict[str, int], list[dict], list[dict]]:
    new_palette = {}
    warnings = []
    replacements = []
    used_targets = {}
    collision_candidates = _candidate_targets_from_mapping(mapping)

    air_index = palette.get("minecraft:air")
    if air_index is not None:
        used_targets["minecraft:air"] = air_index
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
        mapping_info = _resolve_smart_target(name, mapping)

        target = mapping_info["target"]
        was_unmapped_to_air = target == "minecraft:air" and name != "minecraft:air"
        if target == "minecraft:air" and air_index is not None and air_index != index:
            target = _pick_safe_collision_target(used_targets, name, index, collision_candidates)
            mapping_info = {
                "target": target,
                "reason": "air_slot_preserved",
                "confidence": 0.0,
                "changed": name != target,
            }
        existing = used_targets.get(target)

        if was_unmapped_to_air:
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

        if existing is not None and existing != index:
            fallback = _pick_safe_collision_target(used_targets, name, index, collision_candidates)
            if fallback != target:
                warnings.append(
                    {
                        "type": "collision",
                        "source": name,
                        "target": target,
                        "index": index,
                        "message": f"Collision: {name} -> {target} at index {index}; replaced with {fallback} for FAWE safety.",
                    }
                )
            target = fallback
            mapping_info = {
                "target": target,
                "reason": "collision_fallback",
                "confidence": 0.0,
                "changed": name != target,
            }

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
        used_targets[target] = index

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


def convert_schematic(input_path: str, output_path: str, mapping: dict[str, str]) -> dict:
    schematic = load_schematic(input_path)
    palette = schematic.palette
    new_palette, warnings = apply_mapping_to_palette(palette, mapping)
    schematic.replace_palette(new_palette)
    save_schematic(schematic, output_path)

    counter = Counter()
    palette_mapping = []
    unchanged = 0
    for name in palette:
        mapped = _resolve_target(name, mapping)
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


def convert_schematic_smart(input_path: str, output_path: str, mapping: dict[str, dict]) -> dict:
    schematic = load_schematic(input_path)
    palette = schematic.palette

    new_palette, warnings, replacements = apply_smart_mapping_to_palette(palette, mapping)
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
