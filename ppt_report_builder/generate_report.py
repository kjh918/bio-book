#!/usr/bin/env python3
"""
generate_report.py
=====================

Standalone script: takes a YAML report config (see README.md /
examples/report_config.yaml for the schema) and writes a filled .pptx.

Usage:
    python generate_report.py report_config.yaml
    python generate_report.py report_config.yaml -o output.pptx
    python generate_report.py report_config.yaml -o output.pptx --template MyTemplate.pptx
    python generate_report.py report_config.yaml --dry-run

Exit codes:
    0  success
    1  bad arguments / file not found
    2  error while building the report (bad YAML, missing PNG/TSV, etc.)
"""

import argparse
import os
import sys
import traceback

# Allow running this script directly from the repo root without installing
# the package (adjust/remove this if you `pip install -e .` the package).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gencurix_report import ReportBuilder
from gencurix_report.yaml_loader import load_report_data


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="generate_report.py",
        description="Build a Gencurix .pptx report from a YAML config file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "config",
        help="Path to the YAML report config (e.g. report_config.yaml)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path to write the .pptx to. Defaults to "
             "<config filename without extension>.pptx in the current directory.",
    )
    parser.add_argument(
        "-t", "--template",
        default=None,
        help="Path to a .pptx template to use instead of the package's bundled "
             "Gencurix_PPT_Template.pptx. Must follow the same slide layout.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate the YAML (and check that every referenced "
             "PNG/TSV/CSV file exists) without writing a .pptx.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print a full traceback on error instead of a short message.",
    )
    return parser


def default_output_path(config_path: str) -> str:
    base = os.path.splitext(os.path.basename(config_path))[0]
    return f"{base}.pptx"


def validate_referenced_files(data) -> list:
    """Walk the parsed ReportData for any image_path / table-derived content
    and make sure the source files existed at parse time. (The YAML loader
    already reads TSV/CSV files eagerly, and PNG paths are checked here, so
    this mainly catches image paths that don't exist.)"""
    problems = []

    def _check_block(block, where):
        if block is not None and block.image_path and not os.path.isfile(block.image_path):
            problems.append(f"{where}: image not found: {block.image_path}")

    _check_block(data.workflow_content, "workflow_content")
    if data.sample_info is not None:
        _check_block(data.sample_info.content, "sample_info.content")
    for i, item in enumerate(data.results, start=1):
        _check_block(item.content, f"results[{i}] ('{item.title}')")
    if data.conclusion is not None:
        _check_block(data.conclusion.content_1, "conclusion.content_1")
        _check_block(data.conclusion.content_2, "conclusion.content_2")

    return problems


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not os.path.isfile(args.config):
        print(f"[ERROR] Config file not found: {args.config}", file=sys.stderr)
        return 1

    if args.template and not os.path.isfile(args.template):
        print(f"[ERROR] Template file not found: {args.template}", file=sys.stderr)
        return 1

    output_path = args.output or default_output_path(args.config)

    print(f"Reading config: {args.config}")
    try:
        data = load_report_data(args.config)
    except Exception as exc:
        print(f"[ERROR] Failed to parse YAML config: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 2

    problems = validate_referenced_files(data)
    if problems:
        print("[ERROR] Some referenced files are missing:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    n_results = len(data.results)
    print(f"  Title      : {data.title_page.title}")
    print(f"  Chapters   : {', '.join(c.name for c in data.chapters) or '(none)'}")
    print(f"  Results    : {n_results} item(s)")

    if args.dry_run:
        print("Dry run OK -- config is valid, no .pptx written.")
        return 0

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    try:
        builder = ReportBuilder(template_path=args.template)
        builder.build(data, output_path)
    except Exception as exc:
        print(f"[ERROR] Failed to build report: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 2

    print(f"Done -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
