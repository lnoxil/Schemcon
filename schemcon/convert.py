from __future__ import annotations

from collections import Counter

from .matcher import pick_best_match
from .schem import load_schematic, save_schematic


def _split_blockstate(name: str) -> tuple[str, str | None]:
    if "[" in name and name.endswith("]"):
        block, rest = name.split("[", 1)
        return block, rest[:-1]
    return name, None


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
        return mapped_name
    return name


def _resolve_smart_target(name: str, mapping: dict[str, dict]) -> dict:
    direct = mapping.get(name)
    if isinstance(direct, dict):
        return direct

    base, _props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if isinstance(mapped_base, dict):
        return {
            "target": mapped_base.get("target", base),
            "reason": mapped_base.get("reason", "base_state_fallback"),
            "confidence": mapped_base.get("confidence", 0.0),
            "changed": mapped_base.get("target", base) != name,
        }

    return {
        "target": name,
        "reason": "unmapped",
        "confidence": 1.0,
        "changed": False,
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

        if existing is not None and existing != index:
            warnings.append(
                f"Collision for {name} -> {target}; keeping original name to preserve palette index {index}."
            )
            target = name

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

        if existing is not None and existing != index:
            warnings.append(
                {
                    "type": "collision",
                    "source": name,
                    "target": target,
                    "index": index,
                    "message": f"Collision: {name} -> {target} at index {index}",
                }
            )
            target = name
            mapping_info = {
                "target": name,
                "reason": "collision_fallback",
                "confidence": 0.0,
                "changed": False,
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
    for name in palette:
        mapped = _resolve_target(name, mapping)
        counter[mapped] += 1
        palette_mapping.append({"source": name, "target": mapped})

    return {
        "input": input_path,
        "output": output_path,
        "unique_blocks": len(palette),
        "warnings": warnings,
        "mapped_blocks": dict(counter),
        "palette_mapping": palette_mapping,
    }


def convert_schematic_smart(input_path: str, output_path: str, mapping: dict[str, dict]) -> dict:
    schematic = load_schematic(input_path)
    palette = schematic.palette

    new_palette, warnings, replacements = apply_smart_mapping_to_palette(palette, mapping)
    schematic.replace_palette(new_palette)
    save_schematic(schematic, output_path)

    changed_count = sum(1 for r in replacements if r["changed"])
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
    for r in replacements:
        target_counter[r["target"]] += 1

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
        "all_replacements": replacements,
    }
