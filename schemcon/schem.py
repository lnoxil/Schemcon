from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log2
from typing import Iterable

import nbtlib


CompoundLike = nbtlib.Compound


def _split_blockstate(value: str) -> tuple[str, str | None]:
    if "[" in value and value.endswith("]"):
        name, rest = value.split("[", 1)
        return name, rest[:-1]
    return value, None


def _state_from_litematic_entry(entry: CompoundLike) -> str:
    name = str(entry.get("Name", "minecraft:air"))
    props = entry.get("Properties")
    if props:
        parts = [f"{key}={str(val)}" for key, val in sorted(props.items())]
        return f"{name}[{','.join(parts)}]"
    return name


def _iter_compounds(node: object) -> Iterable[CompoundLike]:
    if isinstance(node, nbtlib.Compound):
        yield node
        for value in node.values():
            yield from _iter_compounds(value)
    elif isinstance(node, (nbtlib.List, list, tuple)):
        for value in node:
            yield from _iter_compounds(value)


def _find_named_compound(root: CompoundLike, key_name: str) -> tuple[CompoundLike, str, CompoundLike] | None:
    needle = key_name.lower()
    for compound in _iter_compounds(root):
        for key, value in compound.items():
            if key.lower() == needle and isinstance(value, nbtlib.Compound):
                return compound, key, value
    return None


def _iter_regions(root: CompoundLike) -> Iterable[CompoundLike]:
    for compound in _iter_compounds(root):
        regions = compound.get("Regions")
        if isinstance(regions, nbtlib.Compound):
            for region in regions.values():
                if isinstance(region, nbtlib.Compound):
                    yield region


def _to_u64(value: int) -> int:
    return value & ((1 << 64) - 1)


def _decode_packed_indices(data: list[int], count: int, bits: int) -> list[int]:
    if bits <= 0:
        return [0] * count
    mask = (1 << bits) - 1
    decoded: list[int] = []
    for i in range(count):
        bit_index = i * bits
        long_index = bit_index // 64
        start = bit_index % 64
        if long_index >= len(data):
            decoded.append(0)
            continue
        a = _to_u64(int(data[long_index]))
        value = (a >> start) & mask
        overflow = (start + bits) - 64
        if overflow > 0 and long_index + 1 < len(data):
            b = _to_u64(int(data[long_index + 1]))
            value |= (b & ((1 << overflow) - 1)) << (bits - overflow)
        decoded.append(value)
    return decoded


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    v = value & 0xFFFFFFFF
    while True:
        temp = v & 0x7F
        v >>= 7
        if v:
            out.append(temp | 0x80)
        else:
            out.append(temp)
            break
    return bytes(out)


def _index(x: int, y: int, z: int, sx: int, sz: int) -> int:
    return x + z * sx + y * sx * sz


def _region_box(region: CompoundLike) -> tuple[int, int, int, int, int, int]:
    pos = region.get("Position", nbtlib.Compound({"x": 0, "y": 0, "z": 0}))
    size = region.get("Size", nbtlib.Compound({"x": 1, "y": 1, "z": 1}))
    px, py, pz = int(pos.get("x", 0)), int(pos.get("y", 0)), int(pos.get("z", 0))
    sx, sy, sz = abs(int(size.get("x", 1))), abs(int(size.get("y", 1))), abs(int(size.get("z", 1)))
    return px, py, pz, sx, sy, sz


def _build_sponge_from_regions(root: CompoundLike) -> nbtlib.Compound | None:
    regions = list(_iter_regions(root))
    if not regions:
        return None

    boxes = [_region_box(r) for r in regions]
    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    min_z = min(b[2] for b in boxes)
    max_x = max(b[0] + b[3] for b in boxes)
    max_y = max(b[1] + b[4] for b in boxes)
    max_z = max(b[2] + b[5] for b in boxes)
    width, height, length = max_x - min_x, max_y - min_y, max_z - min_z
    volume = width * height * length
    if volume <= 0:
        return None

    global_palette: dict[str, int] = {"minecraft:air": 0}
    block_ids = [0] * volume

    for region, (px, py, pz, sx, sy, sz) in zip(regions, boxes):
        palette_list = region.get("BlockStatePalette")
        packed = region.get("BlockStates")
        if not palette_list or packed is None:
            continue

        local_states = [_state_from_litematic_entry(entry) for entry in palette_list if isinstance(entry, nbtlib.Compound)]
        if not local_states:
            continue

        bits = max(2, ceil(log2(max(1, len(local_states)))))
        local_volume = sx * sy * sz
        decoded = _decode_packed_indices(list(packed), local_volume, bits)

        for y in range(sy):
            for z in range(sz):
                for x in range(sx):
                    i_local = _index(x, y, z, sx, sz)
                    if i_local >= len(decoded):
                        continue
                    p_idx = decoded[i_local]
                    if p_idx < 0 or p_idx >= len(local_states):
                        state = "minecraft:air"
                    else:
                        state = local_states[p_idx]

                    if state not in global_palette:
                        global_palette[state] = len(global_palette)
                    gi = _index((px - min_x) + x, (py - min_y) + y, (pz - min_z) + z, width, length)
                    if 0 <= gi < volume:
                        block_ids[gi] = global_palette[state]

    palette_compound = nbtlib.Compound({name: nbtlib.Int(idx) for name, idx in global_palette.items()})
    block_data = bytearray()
    for idx in block_ids:
        block_data.extend(_encode_varint(idx))

    data_version = 0
    found_dv = root.get("DataVersion")
    if found_dv is not None:
        data_version = int(found_dv)

    return nbtlib.Compound(
        {
            "Version": nbtlib.Int(2),
            "DataVersion": nbtlib.Int(data_version),
            "Width": nbtlib.Short(width),
            "Height": nbtlib.Short(height),
            "Length": nbtlib.Short(length),
            "Offset": nbtlib.IntArray([0, 0, 0]),
            "PaletteMax": nbtlib.Int(len(global_palette)),
            "Palette": palette_compound,
            "BlockData": nbtlib.ByteArray(block_data),
            "BlockEntities": nbtlib.List[nbtlib.Compound]([]),
            "Entities": nbtlib.List[nbtlib.Compound]([]),
            "Metadata": nbtlib.Compound({"Author": nbtlib.String("Schemcon")}),
        }
    )


def export_fawe_compatible(path: str) -> None:
    loaded = nbtlib.load(path)
    root = loaded.root
    if _find_named_compound(root, "Palette") is not None and "BlockData" in root:
        return
    sponge = _build_sponge_from_regions(root)
    if sponge is None:
        return
    nbtlib.File(sponge).save(path)


@dataclass
class Schematic:
    root: nbtlib.Compound

    @property
    def palette(self) -> dict[str, int]:
        found = _find_named_compound(self.root, "Palette")
        if found is not None:
            _parent, _key, palette = found
            return {str(name): int(index) for name, index in palette.items()}

        merged: dict[str, int] = {}
        idx = 0
        for region in _iter_regions(self.root):
            palette = region.get("BlockStatePalette")
            if not palette:
                continue
            for entry in palette:
                if not isinstance(entry, nbtlib.Compound):
                    continue
                state = _state_from_litematic_entry(entry)
                if state not in merged:
                    merged[state] = idx
                    idx += 1

        if merged:
            return merged

        raise KeyError("Palette")

    def replace_palette(self, new_palette: dict[str, int]) -> None:
        found = _find_named_compound(self.root, "Palette")
        if found is not None:
            parent, key, _palette = found
            parent[key] = nbtlib.Compound({name: nbtlib.Int(index) for name, index in new_palette.items()})
            return

        replacement = {old: new for old, new in new_palette.items()}
        region_found = False
        for region in _iter_regions(self.root):
            palette = region.get("BlockStatePalette")
            if not palette:
                continue
            region_found = True
            for entry in palette:
                if not isinstance(entry, nbtlib.Compound):
                    continue
                source_state = _state_from_litematic_entry(entry)
                target_state = replacement.get(source_state, source_state)
                target_name, _target_props = _split_blockstate(target_state)
                if target_name != str(entry.get("Name", "minecraft:air")):
                    entry["Name"] = nbtlib.String(target_name)

        if region_found:
            return

        raise KeyError("Palette")


def load_schematic(path: str) -> Schematic:
    root = nbtlib.load(path).root
    return Schematic(root=root)


def save_schematic(schematic: Schematic, path: str) -> None:
    nbtlib.File(schematic.root).save(path)
