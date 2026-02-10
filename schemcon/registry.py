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


def download_server_jar(version_json: dict, destination: pathlib.Path, session: requests.Session | None = None) -> pathlib.Path:
    session = session or requests.Session()
    server_info = version_json.get("downloads", {}).get("server")
    if not server_info:
        raise ValueError("Server jar download info not available for this version")

    destination.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(server_info["url"], timeout=120)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


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


def ensure_registry_reports(
    version: str,
    server_jar: pathlib.Path,
    output_dir: pathlib.Path,
    session: requests.Session | None = None,
) -> tuple[list[pathlib.Path], str]:
    """Ensure blocks.json exists.

    Returns (paths, source) where source is 'server_reports' or 'prismarine_fallback'.
    """
    extracted = extract_reports(server_jar, output_dir)
    if extracted:
        return extracted, "server_reports"

    blocks = _fetch_prismarine_blocks(version, session=session)
    if not blocks:
        raise FileNotFoundError(
            "No reports found in server jar and fallback block source is unavailable for this version."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    blocks_path = output_dir / "blocks.json"
    registries_path = output_dir / "registries.json"
    blocks_path.write_text(json.dumps(blocks, indent=2), encoding="utf-8")
    if not registries_path.exists():
        registries_path.write_text("{}", encoding="utf-8")
    return [blocks_path, registries_path], "prismarine_fallback"


def load_blocks_report(report_path: pathlib.Path) -> dict:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if "blocks" in data:
        return data["blocks"]
    return data


def load_registry(report_dir: pathlib.Path) -> dict:
    blocks_path = report_dir / "blocks.json"
    if not blocks_path.exists():
        raise FileNotFoundError(f"Missing blocks.json in {report_dir}")
    return load_blocks_report(blocks_path)
