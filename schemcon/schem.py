from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log2
import re
from typing import Iterable

import nbtlib


CompoundLike = nbtlib.Compound

_BLOCK_NAME_RE = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
_BLOCK_PROP_RE = re.compile(r"^[a-z0-9_./-]+$")
_SAFE_COLLISION_STATES = (
    "minecraft:air",
    "minecraft:stone",
    "minecraft:dirt",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:sand",
    "minecraft:glass",
    "minecraft:gravel",
    "minecraft:netherrack",
    "minecraft:water",
    "minecraft:lava",
)


def _normalize_block_name(name: str) -> str:
    candidate = (name or "minecraft:air").strip().lower()
    if not candidate:
        return "minecraft:air"
    if ":" not in candidate:
        candidate = f"minecraft:{candidate}"
    if not _BLOCK_NAME_RE.fullmatch(candidate):
        return "minecraft:air"
    return candidate


def _sanitize_properties(props: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in props.items():
        key_norm = key.strip().lower()
        val_norm = value.strip().lower()
        if not key_norm or not val_norm:
            continue
        if _BLOCK_PROP_RE.fullmatch(key_norm) and _BLOCK_PROP_RE.fullmatch(val_norm):
            cleaned[key_norm] = val_norm
    return cleaned


def _normalize_blockstate_string(value: str) -> str:
    base, props = _parse_blockstate(value)
    base = _normalize_block_name(base)
    props = _sanitize_properties(props)
    if props:
        parts = [f"{key}={val}" for key, val in sorted(props.items())]
        return f"{base}[{','.join(parts)}]"
    return base


def _pick_safe_collision_state(used_states: dict[str, int], index: int) -> str:
    for candidate in _SAFE_COLLISION_STATES:
        existing = used_states.get(candidate)
        if existing is None or existing == index:
            return candidate
    return "minecraft:air"


def _split_blockstate(value: str) -> tuple[str, str | None]:
    if "[" in value and value.endswith("]"):
        name, rest = value.split("[", 1)
        return name, rest[:-1]
    return value, None


def _get_compound_root(loaded: object) -> CompoundLike:
    """Handle nbtlib versions that return File or Compound from load()."""
    if isinstance(loaded, nbtlib.Compound):
        return loaded
    root = getattr(loaded, "root", None)
    if isinstance(root, nbtlib.Compound):
        return root
    if hasattr(loaded, "__getitem__"):
        for key in ("", "Schematic"):
            try:
                maybe = loaded[key]
                if isinstance(maybe, nbtlib.Compound):
                    return maybe
            except Exception:
                pass
    if hasattr(loaded, "items"):
        try:
            for _k, maybe in loaded.items():
                if isinstance(maybe, nbtlib.Compound):
                    return maybe
        except Exception:
            pass
    raise TypeError("Unsupported NBT root type from nbtlib.load")


def _state_from_litematic_entry(entry: CompoundLike) -> str:
    name = _normalize_block_name(str(entry.get("Name", "minecraft:air")))
    props = entry.get("Properties")
    if props:
        parsed = {str(key): str(val) for key, val in props.items()}
        cleaned = _sanitize_properties(parsed)
        if cleaned:
            parts = [f"{key}={val}" for key, val in sorted(cleaned.items())]
            return f"{name}[{','.join(parts)}]"
    return name


def _parse_blockstate(value: str) -> tuple[str, dict[str, str]]:
    base, props_raw = _split_blockstate(value)
    props: dict[str, str] = {}
    if props_raw:
        for item in props_raw.split(","):
            if "=" not in item:
                continue
            key, val = item.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key:
                props[key] = val
    return base, props


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


def _encode_packed_indices(indices: list[int], bits_per_entry: int) -> bytes:
    if bits_per_entry <= 0:
        return bytes()

    longs_needed = (len(indices) * bits_per_entry + 63) // 64
    longs = [0] * longs_needed
    mask = (1 << bits_per_entry) - 1

    for i, idx in enumerate(indices):
        value = idx & mask
        bit_index = i * bits_per_entry
        long_index = bit_index // 64
        start = bit_index % 64

        if long_index >= len(longs):
            continue
        longs[long_index] |= value << start

        overflow = (start + bits_per_entry) - 64
        if overflow > 0 and long_index + 1 < len(longs):
            longs[long_index + 1] |= value >> (bits_per_entry - overflow)

    result = bytearray()
    for long_val in longs:
        if long_val >= (1 << 63):
            long_val -= 1 << 64
        result.extend(long_val.to_bytes(8, byteorder="big", signed=True))
    return bytes(result)


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


def _decode_varint_stream(raw: bytes, expected_count: int) -> list[int]:
    values: list[int] = []
    idx = 0
    size = len(raw)
    while idx < size and len(values) < expected_count:
        shift = 0
        value = 0
        while True:
            if idx >= size:
                return values
            byte = raw[idx]
            idx += 1
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
            if shift > 35:
                return values
        values.append(value)
    return values


def _decode_block_ids(block_data: nbtlib.ByteArray, volume: int, palette_size: int) -> list[int]:
    raw = bytes((int(b) & 0xFF) for b in block_data)
    decoded = _decode_varint_stream(raw, volume)
    if len(decoded) == volume:
        return decoded

    # Fallback for packed-bit style payloads.
    if volume > 0 and len(raw) % 8 == 0 and palette_size > 0:
        longs: list[int] = []
        for i in range(0, len(raw), 8):
            chunk = raw[i : i + 8]
            signed = int.from_bytes(chunk, byteorder="big", signed=True)
            longs.append(signed)
        bits = max(2, ceil(log2(max(1, palette_size))))
        packed = _decode_packed_indices(longs, volume, bits)
        if len(packed) == volume:
            return packed

    return []


def _sanitize_root_palette_and_blockdata(root: nbtlib.Compound, palette_parent: nbtlib.Compound, palette_key: str) -> None:
    palette_obj = palette_parent.get(palette_key)
    block_data = root.get("BlockData")
    if not isinstance(palette_obj, nbtlib.Compound) or not isinstance(block_data, nbtlib.ByteArray):
        return

    width = int(root.get("Width", 0) or 0)
    height = int(root.get("Height", 0) or 0)
    length = int(root.get("Length", 0) or 0)
    volume = width * height * length
    if volume <= 0:
        return

    id_to_state: dict[int, str] = {}
    used_state: dict[str, int] = {}
    for raw_state, raw_id in palette_obj.items():
        # FAWE can fail with NPE when palette contains a syntactically valid state string
        # but with unsupported properties for the runtime server version.
        # For root Sponge palettes, prefer base block IDs only to guarantee resolvable states.
        raw_name, _raw_props = _parse_blockstate(str(raw_state))
        state = _normalize_block_name(raw_name)
        state_id = int(raw_id)
        if state_id < 0:
            continue

        if state_id in id_to_state and id_to_state[state_id] != state:
            state = _pick_safe_collision_state(used_state, state_id)

        owner = used_state.get(state)
        if owner is not None and owner != state_id:
            state = _pick_safe_collision_state(used_state, state_id)

        id_to_state[state_id] = state
        used_state[state] = state_id

    if not id_to_state:
        id_to_state = {0: "minecraft:air"}

    old_ids = sorted(id_to_state.keys())
    dense_map = {old_id: new_id for new_id, old_id in enumerate(old_ids)}

    decoded_ids = _decode_block_ids(block_data, volume, max(old_ids) + 1)
    if len(decoded_ids) != volume:
        # Hard fail-safe: keep schematic loadable in FAWE even when BlockData is corrupted
        # or encoded in an unsupported way. Better to lose blocks than crash loader with NPE.
        dense_palette = nbtlib.Compound({"minecraft:air": nbtlib.Int(0)})
        block_raw = bytearray()
        for _ in range(volume):
            block_raw.extend(_encode_varint(0))
        palette_parent[palette_key] = dense_palette
        root["BlockData"] = nbtlib.ByteArray(bytes(block_raw))
        root["PaletteMax"] = nbtlib.Int(1)
        root["Version"] = nbtlib.Int(2)
        return

    remapped_ids: list[int] = []
    for old_id in decoded_ids:
        if old_id in dense_map:
            remapped_ids.append(dense_map[old_id])
        else:
            remapped_ids.append(0)

    dense_palette = nbtlib.Compound()
    for old_id in old_ids:
        state = id_to_state[old_id]
        dense_palette[state] = nbtlib.Int(dense_map[old_id])

    block_raw = bytearray()
    for block_id in remapped_ids:
        block_raw.extend(_encode_varint(block_id))

    palette_parent[palette_key] = dense_palette
    root["BlockData"] = nbtlib.ByteArray(bytes(block_raw))
    root["PaletteMax"] = nbtlib.Int(len(dense_palette))
    # Force Sponge v2 payload style for maximum FAWE compatibility.
    root["Version"] = nbtlib.Int(2)


def _index(x: int, y: int, z: int, sx: int, sz: int) -> int:
    return x + z * sx + y * sx * sz


def _region_box(region: CompoundLike) -> tuple[int, int, int, int, int, int]:
    pos = region.get("Position", nbtlib.Compound({"x": 0, "y": 0, "z": 0}))
    size = region.get("Size", nbtlib.Compound({"x": 1, "y": 1, "z": 1}))
    px, py, pz = int(pos.get("x", 0)), int(pos.get("y", 0)), int(pos.get("z", 0))
    sx, sy, sz = abs(int(size.get("x", 1))), abs(int(size.get("y", 1))), abs(int(size.get("z", 1)))
    return px, py, pz, sx, sy, sz


def _active_regions(root: CompoundLike) -> list[tuple[CompoundLike, tuple[int, int, int, int, int, int]]]:
    active: list[tuple[CompoundLike, tuple[int, int, int, int, int, int]]] = []
    for region in _iter_regions(root):
        palette_list = region.get("BlockStatePalette")
        packed = region.get("BlockStates")
        if not palette_list or packed is None:
            continue
        box = _region_box(region)
        if box[3] <= 0 or box[4] <= 0 or box[5] <= 0:
            continue
        active.append((region, box))
    return active


def _build_sponge_from_regions(root: CompoundLike, sponge_version: int = 2) -> nbtlib.Compound | None:
    active = _active_regions(root)
    if not active:
        return None

    boxes = [box for _region, box in active]
    total_region_volume = sum(sx * sy * sz for _px, _py, _pz, sx, sy, sz in boxes)

    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    min_z = min(b[2] for b in boxes)
    max_x = max(b[0] + b[3] for b in boxes)
    max_y = max(b[1] + b[4] for b in boxes)
    max_z = max(b[2] + b[5] for b in boxes)
    width, height, length = max_x - min_x, max_y - min_y, max_z - min_z
    volume = width * height * length

    # Some FAWE/Litematic exports keep regions far apart in world coordinates,
    # which creates enormous sparse schematics. Repack regions when too sparse.
    repacked_sparse = False
    if total_region_volume > 0 and volume > total_region_volume * 2:
        repacked_sparse = True
        cursor_x = 0
        repacked: list[tuple[CompoundLike, tuple[int, int, int, int, int, int]]] = []
        max_h = 0
        max_l = 0
        for region, (_px, _py, _pz, sx, sy, sz) in active:
            repacked.append((region, (cursor_x, 0, 0, sx, sy, sz)))
            cursor_x += sx + 1
            max_h = max(max_h, sy)
            max_l = max(max_l, sz)
        active = repacked
        width = max(1, cursor_x - 1)
        height = max(1, max_h)
        length = max(1, max_l)
        volume = width * height * length
        min_x = 0
        min_y = 0
        min_z = 0

    if volume <= 0:
        return None

    global_palette: dict[str, int] = {"minecraft:air": 0}
    block_ids = [0] * volume

    for region, (px, py, pz, sx, sy, sz) in active:
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
                        state = _normalize_blockstate_string(local_states[p_idx])

                    if state not in global_palette:
                        global_palette[state] = len(global_palette)
                    if repacked_sparse:
                        offset_x, offset_y, offset_z = px, py, pz
                    else:
                        offset_x, offset_y, offset_z = px - min_x, py - min_y, pz - min_z
                    gi = _index(offset_x + x, offset_y + y, offset_z + z, width, length)
                    if 0 <= gi < volume:
                        block_ids[gi] = global_palette[state]

    palette_compound = nbtlib.Compound({name: nbtlib.Int(idx) for name, idx in global_palette.items()})

    if sponge_version == 3:
        bits_per_entry = max(2, ceil(log2(max(1, len(global_palette)))))
        block_data = _encode_packed_indices(block_ids, bits_per_entry)
    else:
        block_data_raw = bytearray()
        for idx in block_ids:
            block_data_raw.extend(_encode_varint(idx))
        block_data = bytes(block_data_raw)

    data_version = 2586
    for key in ("DataVersion", "MinecraftDataVersion", "MCDataVersion"):
        found_dv = root.get(key)
        if found_dv is not None:
            try:
                value = int(found_dv)
                if value > 0:
                    data_version = value
                    break
            except (TypeError, ValueError):
                continue

    result = nbtlib.Compound(
        {
            "Version": nbtlib.Int(3 if sponge_version == 3 else 2),
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
        }
    )


    if sponge_version == 2:
        result["Metadata"] = nbtlib.Compound({"Name": nbtlib.String(""), "Author": nbtlib.String("Schemcon")})

    return result


def export_fawe_compatible(path: str, sponge_version: int = 2) -> None:
    loaded = nbtlib.load(path)
    root = _get_compound_root(loaded)
    if _find_named_compound(root, "Palette") is not None and "BlockData" in root:
        return
    sponge = _build_sponge_from_regions(root, sponge_version=sponge_version)
    if sponge is None:
        return
    _save_nbt(path, sponge)


def _save_nbt(path: str, root: nbtlib.Compound) -> None:
    file_obj = nbtlib.File(root)
    try:
        file_obj.save(path, gzipped=True)
    except TypeError:
        file_obj.save(path)


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
            normalized: dict[str, int] = {}
            used_states: dict[str, int] = {}
            used_ids: dict[int, str] = {}
            for raw_name, raw_index in new_palette.items():
                safe_name = _normalize_blockstate_string(raw_name)
                safe_index = int(raw_index)
                # Keep palette IDs unique and always associated with a resolvable state.
                if safe_index in used_ids and used_ids[safe_index] != safe_name:
                    safe_name = _pick_safe_collision_state(used_states, safe_index)
                state_owner = used_states.get(safe_name)
                if state_owner is not None and state_owner != safe_index:
                    safe_name = _pick_safe_collision_state(used_states, safe_index)
                normalized[safe_name] = nbtlib.Int(safe_index)
                used_ids[safe_index] = safe_name
                used_states[safe_name] = safe_index

            parent[key] = nbtlib.Compound(normalized)
            if "PaletteMax" in self.root:
                self.root["PaletteMax"] = nbtlib.Int(len(parent[key]))
            _sanitize_root_palette_and_blockdata(self.root, parent, key)
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
                target_name, target_props = _parse_blockstate(_normalize_blockstate_string(target_state))
                if target_name != str(entry.get("Name", "minecraft:air")):
                    entry["Name"] = nbtlib.String(target_name)
                cleaned_props = _sanitize_properties(target_props)
                if cleaned_props:
                    entry["Properties"] = nbtlib.Compound(
                        {key: nbtlib.String(value) for key, value in sorted(cleaned_props.items())}
                    )
                elif "Properties" in entry:
                    del entry["Properties"]

        if region_found:
            return

        raise KeyError("Palette")


def load_schematic(path: str) -> Schematic:
    root = _get_compound_root(nbtlib.load(path))
    return Schematic(root=root)


def save_schematic(schematic: Schematic, path: str) -> None:
    _save_nbt(path, schematic.root)
