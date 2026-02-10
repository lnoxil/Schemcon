from __future__ import annotations

from collections import Counter
from pathlib import Path

from .matcher import pick_best_match
from .schem import load_schematic, save_schematic


SAFE_COLLISION_STATES = (
    "minecraft:air",
    "minecraft:stone",
    "minecraft:dirt",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:sand",
    "minecraft:glass",
    "minecraft:gravel",
    "minecraft:netherrack",
)


def _pick_safe_collision_target(used_targets: dict[str, int], palette_name: str, index: int) -> str:
    original_owner = used_targets.get(palette_name)
    if original_owner is None or original_owner == index:
        return palette_name
    for candidate in SAFE_COLLISION_STATES:
        existing = used_targets.get(candidate)
        if existing is None or existing == index:
            return candidate
    # Last resort: fallback to air and let root sanitization reindex safely.
    return "minecraft:air"


def _split_blockstate(name: str) -> tuple[str, str | None]:
    if "[" in name and name.endswith("]"):
        block, rest = name.split("[", 1)
        return block, rest[:-1]
    return name, None


def _resolve_target(name: str, mapping: dict[str, str]) -> str:
    direct = mapping.get(name)
    if direct:
        return direct
    base, props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if mapped_base:
        mapped_name, mapped_props = _split_blockstate(mapped_base)
        if mapped_props:
            return mapped_base
        # Keep original properties when block base does not change.
        # This avoids collapsing many valid blockstates into one palette key.
        if props and mapped_name == base:
            return name
        return mapped_name
    return "minecraft:air"


def _resolve_smart_target(name: str, mapping: dict[str, dict]) -> dict:
    direct = mapping.get(name)
    if isinstance(direct, dict):
        return direct

    base, props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if isinstance(mapped_base, dict):
        mapped_target = str(mapped_base.get("target", base))
        mapped_name, mapped_props = _split_blockstate(mapped_target)
        if props and not mapped_props and mapped_name == base:
            return {
                "target": name,
                "reason": "preserve_state_props",
                "confidence": mapped_base.get("confidence", 0.0),
                "changed": False,
            }
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


def build_mapping(source_blocks: set[str], target_blocks: set[str]) -> dict[str, str]:
    mapping = {}
    for block in sorted(source_blocks):
        result = pick_best_match(block, target_blocks)
        mapping[block] = result.target
    return mapping


def build_smart_mapping(source_blocks: set[str], target_blocks: set[str]) -> dict[str, dict]:
    mapping = {}
    for block in sorted(source_blocks):
        result = pick_best_match(block, target_blocks)
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

    for name, index in palette.items():
        target = _resolve_target(name, mapping)
        existing = used_targets.get(target)

        if target == "minecraft:air" and name != "minecraft:air":
            warnings.append(f"Unmapped block {name}; replaced with minecraft:air for FAWE safety.")

        if existing is not None and existing != index:
            fallback = _pick_safe_collision_target(used_targets, name, index)
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

    for name, index in palette.items():
        mapping_info = _resolve_smart_target(name, mapping)

        target = mapping_info["target"]
        existing = used_targets.get(target)

        if target == "minecraft:air" and name != "minecraft:air":
            warnings.append(
                {
                    "type": "unmapped_to_air",
                    "source": name,
                    "target": target,
                    "confidence": mapping_info.get("confidence", 0.0),
                    "reason": mapping_info.get("reason", "unmapped_to_air"),
                    "message": f"Unmapped block {name}; replaced with minecraft:air for FAWE safety.",
                }
            )

        if existing is not None and existing != index:
            fallback = _pick_safe_collision_target(used_targets, name, index)
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
