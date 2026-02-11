import json
import pathlib
import zipfile

import requests

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
PRISMARINE_BLOCKS_URL = "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/{version}/blocks.json"


def fetch_version_manifest(session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    response = session.get(MANIFEST_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def resolve_version_info(version: str, manifest: dict) -> dict:
    for entry in manifest.get("versions", []):
        if entry.get("id") == version:
            return entry
    raise ValueError(f"Version {version} not found in manifest")


def fetch_version_json(version_info: dict, session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    response = session.get(version_info["url"], timeout=30)
    response.raise_for_status()
    return response.json()


def _download_jar(version_json: dict, kind: str, destination: pathlib.Path, session: requests.Session | None = None) -> pathlib.Path:
    session = session or requests.Session()
    info = version_json.get("downloads", {}).get(kind)
    if not info:
        raise ValueError(f"{kind.capitalize()} jar download info not available for this version")

    destination.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(info["url"], timeout=120)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def download_server_jar(version_json: dict, destination: pathlib.Path, session: requests.Session | None = None) -> pathlib.Path:
    return _download_jar(version_json, "server", destination, session=session)


def download_client_jar(version_json: dict, destination: pathlib.Path, session: requests.Session | None = None) -> pathlib.Path:
    return _download_jar(version_json, "client", destination, session=session)


def extract_reports(server_jar: pathlib.Path, output_dir: pathlib.Path) -> list[pathlib.Path]:
    extracted = []
    with zipfile.ZipFile(server_jar) as jar:
        for report_path in ("reports/blocks.json", "reports/registries.json"):
            try:
                with jar.open(report_path) as report_file:
                    data = report_file.read()
                target_path = output_dir / pathlib.Path(report_path).name
                output_dir.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(data)
                extracted.append(target_path)
            except KeyError:
                continue
    return extracted


def _version_candidates(version: str) -> list[str]:
    candidates = [version]
    if version.count(".") == 2:
        candidates.append(version.rsplit(".", 1)[0])
    if version.count(".") == 1:
        candidates.append(f"{version}.0")
    return list(dict.fromkeys(candidates))


def _fetch_prismarine_blocks(version: str, session: requests.Session | None = None) -> dict[str, dict] | None:
    session = session or requests.Session()
    for candidate in _version_candidates(version):
        url = PRISMARINE_BLOCKS_URL.format(version=candidate)
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            continue
        payload = response.json()
        if not isinstance(payload, list):
            continue
        blocks = {}
        for entry in payload:
            name = entry.get("name")
            if not name:
                continue
            namespaced = name if ":" in name else f"minecraft:{name}"
            blocks[namespaced] = {
                "id": entry.get("id"),
                "displayName": entry.get("displayName"),
                "hardness": entry.get("hardness"),
                "transparent": entry.get("transparent"),
            }
        if blocks:
            return blocks
    return None


def _extract_block_names_from_server_tags(server_jar: pathlib.Path) -> set[str]:
    names: set[str] = set()
    with zipfile.ZipFile(server_jar) as jar:
        for path in jar.namelist():
            if not path.startswith("data/minecraft/tags/blocks/") or not path.endswith(".json"):
                continue
            try:
                payload = json.loads(jar.read(path).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            for value in payload.get("values", []):
                if isinstance(value, str) and ":" in value and not value.startswith("#"):
                    names.add(value)
    return names


def _extract_block_names_from_client_jar(client_jar: pathlib.Path) -> set[str]:
    names: set[str] = set()
    with zipfile.ZipFile(client_jar) as jar:
        for path in jar.namelist():
            prefix = "assets/minecraft/blockstates/"
            if not path.startswith(prefix) or not path.endswith(".json"):
                continue
            block = path[len(prefix) : -len(".json")]
            if block and "/" not in block:
                names.add(f"minecraft:{block}")
    return names


def _to_blocks_payload(names: set[str]) -> dict[str, dict]:
    payload: dict[str, dict] = {}
    for idx, name in enumerate(sorted(names)):
        payload[name] = {"id": idx}
    return payload


def _merge_block_payloads(*payloads: dict[str, dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for payload in payloads:
        for name, data in payload.items():
            if name not in merged:
                merged[name] = dict(data)
            else:
                merged[name].update(data)
    return merged


def _write_registry_files(output_dir: pathlib.Path, blocks: dict[str, dict], source: str) -> tuple[list[pathlib.Path], str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    blocks_path = output_dir / "blocks.json"
    registries_path = output_dir / "registries.json"
    blocks_path.write_text(json.dumps(blocks, indent=2), encoding="utf-8")
    if not registries_path.exists():
        registries_path.write_text("{}", encoding="utf-8")
    return [blocks_path, registries_path], source


def ensure_registry_reports(
    version: str,
    server_jar: pathlib.Path,
    output_dir: pathlib.Path,
    version_json: dict | None = None,
    session: requests.Session | None = None,
) -> tuple[list[pathlib.Path], str]:
    """Ensure blocks.json exists.

    Returns (paths, source).
    Sources: server_reports | server_tags_fallback | client_blockstates_fallback |
             prismarine_fallback | generated_fallback.
    """
    extracted = extract_reports(server_jar, output_dir)
    if extracted:
        return extracted, "server_reports"

    blocks_from_tags = _extract_block_names_from_server_tags(server_jar)
    tags_payload = _to_blocks_payload(blocks_from_tags) if blocks_from_tags else {}

    client_payload: dict[str, dict] = {}
    if version_json is not None:
        client_jar = output_dir / f"{version}.client.jar"
        try:
            if not client_jar.exists():
                download_client_jar(version_json, client_jar, session=session)
            client_names = _extract_block_names_from_client_jar(client_jar)
            if client_names:
                client_payload = _to_blocks_payload(client_names)
        except Exception:
            pass

    prismarine_payload = _fetch_prismarine_blocks(version, session=session) or {}

    merged = _merge_block_payloads(tags_payload, client_payload, prismarine_payload)
    if merged:
        sources = []
        if tags_payload:
            sources.append("server_tags")
        if client_payload:
            sources.append("client_blockstates")
        if prismarine_payload:
            sources.append("prismarine")
        return _write_registry_files(output_dir, merged, "+".join(sources) or "generated_fallback")

    raise FileNotFoundError(
        "No reports found in server jar and all fallback sources were unavailable."
    )




def _normalize_block_key(name: str) -> str:
    key = str(name).strip()
    if not key:
        return "minecraft:air"
    if key.startswith("#"):
        return key
    if ":" not in key:
        return f"minecraft:{key}"
    return key
def load_blocks_report(report_path: pathlib.Path) -> dict:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    payload = data["blocks"] if "blocks" in data else data
    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, dict] = {}
    for raw_name, info in payload.items():
        name = _normalize_block_key(raw_name)
        if name.startswith("#"):
            continue
        if isinstance(info, dict):
            normalized[name] = info
        else:
            normalized[name] = {"id": info}
    return normalized


def load_registry(report_dir: pathlib.Path) -> dict:
    blocks_path = report_dir / "blocks.json"
    if not blocks_path.exists():
        raise FileNotFoundError(f"Missing blocks.json in {report_dir}")
    return load_blocks_report(blocks_path)
