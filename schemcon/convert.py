from __future__ import annotations

from collections import Counter

from .matcher import pick_best_match
from .schem import load_schematic, save_schematic


def build_mapping(source_blocks: set[str], target_blocks: set[str]) -> dict[str, str]:
    mapping = {}
    for block in sorted(source_blocks):
        result = pick_best_match(block, target_blocks)
        mapping[block] = result.target
    return mapping


def apply_mapping_to_palette(palette: dict[str, int], mapping: dict[str, str]) -> tuple[dict[str, int], list[str]]:
    new_palette = {}
    warnings = []
    used_targets = {}
    for name, index in palette.items():
        target = mapping.get(name, name)
        existing = used_targets.get(target)
        if existing is not None and existing != index:
            warnings.append(
                f"Collision for {name} -> {target}; keeping original name to preserve palette index {index}."
            )
            target = name
        new_palette[target] = index
        used_targets[target] = index
    return new_palette, warnings


def convert_schematic(input_path: str, output_path: str, mapping: dict[str, str]) -> dict:
    schematic = load_schematic(input_path)
    palette = schematic.palette
    new_palette, warnings = apply_mapping_to_palette(palette, mapping)
    schematic.replace_palette(new_palette)
    save_schematic(schematic, output_path)

    counter = Counter()
    for name in palette:
        counter[mapping.get(name, name)] += 1

    return {
        "input": input_path,
        "output": output_path,
        "unique_blocks": len(palette),
        "warnings": warnings,
        "mapped_blocks": dict(counter),
    }
