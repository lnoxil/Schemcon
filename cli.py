from __future__ import annotations

import argparse
import json
import pathlib

from .convert import build_mapping, build_smart_mapping, convert_schematic, convert_schematic_smart
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
    _paths, source = ensure_registry_reports(args.version, server_jar, output_dir, version_json=version_json)
    print(f"Saved registry data to {output_dir} (source: {source})")


def cmd_build_mapping(args: argparse.Namespace) -> None:
    source_registry = load_registry(pathlib.Path(args.source_dir))
    target_registry = load_registry(pathlib.Path(args.target_dir))
    source_blocks = set(source_registry.keys())
    target_blocks = set(target_registry.keys())
    
    # НОВОЕ: Используем умный маппинг, если запрошен
    if args.smart:
        mapping = build_smart_mapping(source_blocks, target_blocks)
        
        # Статистика
        total = len(mapping)
        changed = sum(1 for v in mapping.values() if v["changed"])
        high_conf = sum(1 for v in mapping.values() if v["changed"] and v["confidence"] >= 0.8)
        low_conf = sum(1 for v in mapping.values() if v["changed"] and v["confidence"] < 0.5)
        
        print(f"Smart mapping created:")
        print(f"  Total blocks: {total}")
        print(f"  Exact matches: {total - changed}")
        print(f"  Replaced: {changed}")
        print(f"  High confidence (≥80%): {high_conf}")
        print(f"  Low confidence (<50%): {low_conf}")
        
        if low_conf > 0:
            print(f"  ⚠️ WARNING: {low_conf} replacements have low confidence!")
    else:
        # Старый формат
        mapping_dict = build_mapping(source_blocks, target_blocks)
        mapping = {
            key: {"target": value, "reason": "legacy"}
            for key, value in mapping_dict.items()
        }
    
    pathlib.Path(args.output).write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Saved mapping to {args.output}")


def cmd_convert(args: argparse.Namespace) -> None:
    mapping_data = json.loads(pathlib.Path(args.mapping).read_text(encoding="utf-8"))
    
    # Определяем формат маппинга
    first_value = next(iter(mapping_data.values()))
    is_smart_mapping = isinstance(first_value, dict) and "confidence" in first_value
    
    if is_smart_mapping and not args.legacy:
        # НОВОЕ: Умная конвертация
        print("Using smart conversion with confidence analysis...")
        report = convert_schematic_smart(args.input, args.output, mapping_data)
        
        # Выводим статистику
        stats = report["statistics"]
        print(f"\nConversion completed:")
        print(f"  Total blocks: {stats['total_blocks']}")
        print(f"  Changed: {stats['changed']}")
        print(f"  Unchanged: {stats['unchanged']}")
        print(f"  Warnings: {stats['warnings']}")
        print(f"\nConfidence breakdown:")
        print(f"  Perfect (100%): {stats['perfect_matches']}")
        print(f"  High (80-99%): {stats['high_confidence']}")
        print(f"  Medium (50-79%): {stats['medium_confidence']}")
        print(f"  Low (30-49%): {stats['low_confidence']}")
        print(f"  Very Low (<30%): {stats['very_low_confidence']}")
        
        if stats['low_confidence'] + stats['very_low_confidence'] > 0:
            print(f"\n⚠️ WARNING: {stats['low_confidence'] + stats['very_low_confidence']} blocks replaced with low confidence!")
            print("  Check the detailed report for more information.")
    else:
        # Старая конвертация
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
        description="Smart Minecraft schematic converter with intelligent block mapping"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Fetch registry
    fetch = sub.add_parser("fetch-registry", help="Download server jar and extract reports")
    fetch.add_argument("version", help="Minecraft version (e.g., 1.20.1)")
    fetch.add_argument("--output-dir", default="data/versions", help="Output directory")
    fetch.set_defaults(func=cmd_fetch_registry)

    # Build mapping
    mapping = sub.add_parser("build-mapping", help="Build block mapping from two registry folders")
    mapping.add_argument("--source-dir", required=True, help="Source version registry directory")
    mapping.add_argument("--target-dir", required=True, help="Target version registry directory")
    mapping.add_argument("--output", required=True, help="Output mapping JSON file")
    mapping.add_argument(
        "--smart",
        action="store_true",
        help="Use smart mapping with confidence scoring (recommended)"
    )
    mapping.set_defaults(func=cmd_build_mapping)

    # Convert schematic
    convert = sub.add_parser("convert", help="Convert schematic using block mapping")
    convert.add_argument("--input", required=True, help="Input schematic file (.schem or .litematic)")
    convert.add_argument("--output", required=True, help="Output schematic file (.schem)")
    convert.add_argument("--mapping", required=True, help="Block mapping JSON file")
    convert.add_argument("--report", default="conversion_report.json", help="Detailed report output")
    convert.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy conversion (ignore confidence scores)"
    )
    convert.set_defaults(func=cmd_convert)

    # GUI
    gui = sub.add_parser("gui", help="Launch graphical user interface")
    gui.set_defaults(func=lambda _args: launch_gui())

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
