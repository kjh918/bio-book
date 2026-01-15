from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .spec import load_spec
from .generator import generate_manual


def _run_quarto_render(out_dir: Path) -> None:
    cmd = ["quarto", "render", str(out_dir)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"[qmanual] quarto render failed\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="qmanual")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_init = sub.add_parser("init", help="Generate a Quarto manual project from spec YAML.")
    ap_init.add_argument("--spec", required=True, type=Path)
    ap_init.add_argument("--out", required=True, type=Path)
    ap_init.add_argument("--overwrite", action="store_true")

    ap_render = sub.add_parser("render", help="Run `quarto render` on generated project.")
    ap_render.add_argument("--out", required=True, type=Path)

    args = ap.parse_args()

    if args.cmd == "init":
        spec = load_spec(args.spec)
        generate_manual(spec=spec, out_dir=args.out, overwrite=args.overwrite)
        print(f"[qmanual] generated: {args.out}")
    elif args.cmd == "render":
        _run_quarto_render(args.out)
        print(f"[qmanual] rendered: {args.out} -> (check _site/)")
