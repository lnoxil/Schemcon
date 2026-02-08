import json
import pathlib
import zipfile

import requests

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"


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
    response = session.get(server_info["url"], timeout=60)
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
    if not extracted:
        raise FileNotFoundError("No reports found in server jar")
    return extracted


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
