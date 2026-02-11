from __future__ import annotations

import json
import pathlib
import struct
import zlib
import zipfile


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _decode_png_rgb(data: bytes) -> tuple[int, int, int] | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None

    pos = 8
    width = height = 0
    bit_depth = color_type = None
    palette: list[tuple[int, int, int]] = []
    idat = bytearray()

    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filter, _interlace = struct.unpack(">IIBBBBB", chunk_data
            )
        elif chunk_type == b"PLTE":
            palette = [tuple(chunk_data[i : i + 3]) for i in range(0, len(chunk_data), 3)]
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width <= 0 or height <= 0 or bit_depth != 8 or color_type is None:
        return None

    channels = {2: 3, 3: 1, 6: 4}.get(color_type)
    if channels is None:
        return None

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(height * stride)

    src = 0
    for y in range(height):
        if src >= len(raw):
            return None
        flt = raw[src]
        src += 1
        row = bytearray(raw[src : src + stride])
        src += stride

        prev_row_start = (y - 1) * stride
        row_start = y * stride

        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = out[prev_row_start + x] if y > 0 else 0
            up_left = out[prev_row_start + x - channels] if (y > 0 and x >= channels) else 0
            val = row[x]

            if flt == 1:
                val = (val + left) & 0xFF
            elif flt == 2:
                val = (val + up) & 0xFF
            elif flt == 3:
                val = (val + ((left + up) // 2)) & 0xFF
            elif flt == 4:
                val = (val + _paeth(left, up, up_left)) & 0xFF

            out[row_start + x] = val

    total = [0, 0, 0]
    pixels = 0

    for y in range(height):
        row_start = y * stride
        for x in range(width):
            i = row_start + x * channels
            if color_type == 2:
                r, g, b = out[i], out[i + 1], out[i + 2]
            elif color_type == 6:
                r, g, b, a = out[i], out[i + 1], out[i + 2], out[i + 3]
                if a < 16:
                    continue
            else:  # color_type == 3
                idx = out[i]
                if idx >= len(palette):
                    continue
                r, g, b = palette[idx]
            total[0] += r
            total[1] += g
            total[2] += b
            pixels += 1

    if pixels == 0:
        return None
    return total[0] // pixels, total[1] // pixels, total[2] // pixels


def _texture_candidates(block_name: str) -> list[str]:
    base = block_name.split("[", 1)[0]
    if ":" in base:
        base = base.split(":", 1)[1]
    return [base, f"{base}_top", f"{base}_side", f"{base}_front"]


def build_gradient_map(client_jar: pathlib.Path, block_names: set[str]) -> dict[str, tuple[int, int, int]]:
    result: dict[str, tuple[int, int, int]] = {}
    if not client_jar.exists():
        return result

    with zipfile.ZipFile(client_jar) as jar:
        members = set(jar.namelist())
        for block_name in block_names:
            for candidate in _texture_candidates(block_name):
                member = f"assets/minecraft/textures/block/{candidate}.png"
                if member not in members:
                    continue
                try:
                    rgb = _decode_png_rgb(jar.read(member))
                except Exception:
                    rgb = None
                if rgb is not None:
                    result[block_name] = rgb
                    break
    return result




def list_local_versions(versions_root: pathlib.Path) -> list[str]:
    versions: list[str] = []
    if not versions_root.exists():
        return versions

    for child in sorted(versions_root.iterdir()):
        if not child.is_dir():
            continue
        blocks = child / "blocks.json"
        client = child / f"{child.name}.client.jar"
        if blocks.exists() and client.exists():
            versions.append(child.name)
    return versions


def refresh_gradient_maps_for_local_versions(
    versions_root: pathlib.Path,
    gradients_dir: pathlib.Path,
) -> dict[str, int]:
    """Build/refresh gradient maps for all local versions that have client jars.

    Returns mapping version -> number of blocks with sampled texture color.
    """
    stats: dict[str, int] = {}
    for version in list_local_versions(versions_root):
        version_dir = versions_root / version
        blocks_path = version_dir / "blocks.json"
        client_jar = version_dir / f"{version}.client.jar"
        if not blocks_path.exists() or not client_jar.exists():
            continue

        try:
            payload = json.loads(blocks_path.read_text(encoding="utf-8"))
            block_data = payload.get("blocks") if isinstance(payload, dict) else payload
            if isinstance(block_data, dict):
                block_names = set(block_data.keys())
            else:
                block_names = set()
        except Exception:
            block_names = set()

        if not block_names:
            continue

        gradient_map = build_gradient_map(client_jar, block_names)
        save_gradient_map(gradients_dir / f"{version}.json", gradient_map)
        stats[version] = len(gradient_map)

    return stats

def save_gradient_map(path: pathlib.Path, gradient_map: dict[str, tuple[int, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: list(v) for k, v in gradient_map.items()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_gradient_map(path: pathlib.Path) -> dict[str, tuple[int, int, int]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, tuple[int, int, int]] = {}
    for k, v in data.items():
        if isinstance(v, list) and len(v) == 3:
            out[k] = (int(v[0]), int(v[1]), int(v[2]))
    return out
