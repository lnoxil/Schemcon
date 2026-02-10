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
    base, props = _split_blockstate(name)
    mapped_base = mapping.get(base)
    if mapped_base:
        mapped_name, mapped_props = _split_blockstate(mapped_base)
        if mapped_name == base and props:
            return f"{mapped_name}[{props}]"
        if mapped_props:
            return mapped_base
        return mapped_name
    return name


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
