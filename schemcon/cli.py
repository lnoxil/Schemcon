from __future__ import annotations

import argparse
import json
import pathlib

from .convert import build_mapping, convert_schematic
from .gui import launch_gui
from .matcher import pick_best_match
from .registry import (
    fetch_version_json,
    fetch_version_manifest,
    load_registry,
    download_server_jar,
    ensure_registry_reports,
    resolve_version_info,
)


def cmd_fetch_registry(args: argparse.Namespace) -> None:
    manifest = fetch_version_manifest()
    info = resolve_version_info(args.version, manifest)
    version_json = fetch_version_json(info)
    output_dir = pathlib.Path(args.output_dir) / args.version
    server_jar = output_dir / f"{args.version}.jar"
    download_server_jar(version_json, server_jar)
    _paths, source = ensure_registry_reports(args.version, server_jar, output_dir)
    print(f"Saved registry data to {output_dir} (source: {source})")


def cmd_build_mapping(args: argparse.Namespace) -> None:
    source_registry = load_registry(pathlib.Path(args.source_dir))
    target_registry = load_registry(pathlib.Path(args.target_dir))
    source_blocks = set(source_registry.keys())
    target_blocks = set(target_registry.keys())
    mapping = {}
    for block in sorted(source_blocks):
        result = pick_best_match(block, target_blocks)
        mapping[block] = {"target": result.target, "reason": result.reason}
    pathlib.Path(args.output).write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Saved mapping to {args.output}")


def cmd_convert(args: argparse.Namespace) -> None:
    mapping = json.loads(pathlib.Path(args.mapping).read_text(encoding="utf-8"))
    flat_mapping = {key: value["target"] if isinstance(value, dict) else value for key, value in mapping.items()}
    report = convert_schematic(args.input, args.output, flat_mapping)
    pathlib.Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved converted schematic to {args.output}")
    print(f"Saved report to {args.report}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="schemcon")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-registry", help="Download server jar and extract reports")
    fetch.add_argument("version")
    fetch.add_argument("--output-dir", default="data/versions")
    fetch.set_defaults(func=cmd_fetch_registry)

    mapping = sub.add_parser("build-mapping", help="Build mapping from two registry folders")
    mapping.add_argument("--source-dir", required=True)
    mapping.add_argument("--target-dir", required=True)
    mapping.add_argument("--output", required=True)
    mapping.set_defaults(func=cmd_build_mapping)

    convert = sub.add_parser("convert", help="Convert schematic by updating palette")
    convert.add_argument("--input", required=True)
    convert.add_argument("--output", required=True)
    convert.add_argument("--mapping", required=True)
    convert.add_argument("--report", default="conversion_report.json")
    convert.set_defaults(func=cmd_convert)

    gui = sub.add_parser("gui", help="Launch GUI")
    gui.set_defaults(func=lambda _args: launch_gui())

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
