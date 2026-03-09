from __future__ import annotations

import argparse
import json
import pathlib

from .convert import build_mapping, build_smart_mapping, convert_schematic, convert_schematic_smart
from .gradient import build_gradient_map, save_gradient_map
from .gui import launch_gui
from .registry import (
    download_server_jar,
    ensure_registry_reports,
    fetch_version_json,
    fetch_version_manifest,
    load_registry,
    resolve_version_info,
)


def cmd_fetch_registry(args: argparse.Namespace) -> None:
    manifest = fetch_version_manifest()
    info = resolve_version_info(args.version, manifest)
    version_json = fetch_version_json(info)
    output_dir = pathlib.Path(args.output_dir) / args.version
    server_jar = output_dir / f"{args.version}.jar"
    download_server_jar(version_json, server_jar)
    _paths, source = ensure_registry_reports(args.version, server_jar, output_dir, version_json=version_json)
    print(f"Saved registry data to {output_dir} (source: {source})")


def cmd_build_mapping(args: argparse.Namespace) -> None:
    source_registry = load_registry(pathlib.Path(args.source_dir))
    target_registry = load_registry(pathlib.Path(args.target_dir))
    source_blocks = set(source_registry.keys())
    target_blocks = set(target_registry.keys())
    gradient_map = None

    source_dir = pathlib.Path(args.source_dir)
    target_dir = pathlib.Path(args.target_dir)
    source_ver = source_dir.name
    target_ver = target_dir.name
    source_client = source_dir / f"{source_ver}.client.jar"
    target_client = target_dir / f"{target_ver}.client.jar"
    if source_client.exists() and target_client.exists():
        source_grad = build_gradient_map(source_client, source_blocks)
        target_grad = build_gradient_map(target_client, target_blocks)
        gradient_map = {**source_grad, **target_grad}
        gradients_dir = pathlib.Path("data/gradients")
        save_gradient_map(gradients_dir / f"{source_ver}.json", source_grad)
        save_gradient_map(gradients_dir / f"{target_ver}.json", target_grad)
        print(f"Texture gradients built: {len(source_grad)} source, {len(target_grad)} target")

    if args.smart:
        mapping = build_smart_mapping(source_blocks, target_blocks, gradient_map=gradient_map)

        total = len(mapping)
        changed = sum(1 for v in mapping.values() if v["changed"])
        high_conf = sum(1 for v in mapping.values() if v["changed"] and v["confidence"] >= 0.8)
        low_conf = sum(1 for v in mapping.values() if v["changed"] and v["confidence"] < 0.3)

        print("Smart mapping created:")
        print(f"  Total blocks: {total}")
        print(f"  Exact matches: {total - changed}")
        print(f"  Replaced: {changed}")
        print(f"  High confidence (≥80%): {high_conf}")
        print(f"  Very low confidence (<30%): {low_conf}")

        if low_conf > 0:
            print(f"  ⚠️ WARNING: {low_conf} replacements have low confidence!")
    else:
        mapping_dict = build_mapping(source_blocks, target_blocks, gradient_map=gradient_map)
        mapping = {key: {"target": value, "reason": "legacy"} for key, value in mapping_dict.items()}

    pathlib.Path(args.output).write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Saved mapping to {args.output}")


def cmd_convert(args: argparse.Namespace) -> None:
    mapping_data = json.loads(pathlib.Path(args.mapping).read_text(encoding="utf-8"))

    first_value = next(iter(mapping_data.values())) if mapping_data else ""
    is_smart_mapping = isinstance(first_value, dict) and "confidence" in first_value

    if is_smart_mapping and not args.legacy:
        print("Using smart conversion with confidence analysis...")
        report = convert_schematic_smart(args.input, args.output, mapping_data)

        stats = report["statistics"]
        print("\nConversion completed:")
        print(f"  Total blocks: {stats['total_blocks']}")
        print(f"  Changed: {stats['changed']}")
        print(f"  Unchanged: {stats['unchanged']}")
        print(f"  Warnings: {stats['warnings']}")
        print("\nConfidence breakdown:")
        print(f"  Perfect (100%): {stats['perfect_matches']}")
        print(f"  High (80-99%): {stats['high_confidence']}")
        print(f"  Medium (50-79%): {stats['medium_confidence']}")
        print(f"  Low (30-49%): {stats['low_confidence']}")
        print(f"  Very Low (<30%): {stats['very_low_confidence']}")

        low_total = stats["low_confidence"] + stats["very_low_confidence"]
        if low_total > 0:
            print(f"\n⚠️ WARNING: {low_total} blocks replaced with low confidence!")
            print("  Check the detailed report for more information.")
    else:
        print("Using legacy conversion...")
        flat_mapping = {
            key: value["target"] if isinstance(value, dict) else value
            for key, value in mapping_data.items()
        }
        report = convert_schematic(args.input, args.output, flat_mapping)

    pathlib.Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved converted schematic to {args.output}")
    print(f"Saved detailed report to {args.report}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schemcon",
        description="Smart Minecraft schematic converter with intelligent block mapping",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-registry", help="Download server jar and extract reports")
    fetch.add_argument("version", help="Minecraft version (e.g., 1.20.1)")
    fetch.add_argument("--output-dir", default="data/versions", help="Output directory")
    fetch.set_defaults(func=cmd_fetch_registry)

    mapping = sub.add_parser("build-mapping", help="Build block mapping from two registry folders")
    mapping.add_argument("--source-dir", required=True, help="Source version registry directory")
    mapping.add_argument("--target-dir", required=True, help="Target version registry directory")
    mapping.add_argument("--output", required=True, help="Output mapping JSON file")
    mapping.add_argument(
        "--smart",
        action="store_true",
        help="Use smart mapping with confidence scoring (recommended)",
    )
    mapping.set_defaults(func=cmd_build_mapping)

    convert = sub.add_parser("convert", help="Convert schematic using block mapping")
    convert.add_argument("--input", required=True, help="Input schematic file (.schem or .litematic)")
    convert.add_argument("--output", required=True, help="Output schematic file (.schem)")
    convert.add_argument("--mapping", required=True, help="Block mapping JSON file")
    convert.add_argument("--report", default="conversion_report.json", help="Detailed report output")
    convert.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy conversion (ignore confidence scores)",
    )
    convert.set_defaults(func=cmd_convert)

    gui = sub.add_parser("gui", help="Launch graphical user interface")
    gui.set_defaults(func=lambda _args: launch_gui())

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
