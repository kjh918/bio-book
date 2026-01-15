#!/usr/bin/env python3
from pathlib import Path

DIRS = [
    "qmanual/src/qmanual/templates",
]

FILES = {
    "qmanual/pyproject.toml": """[project]
name = "qmanual"
version = "0.1.0"
description = "Generate Quarto manual scaffolds (website/book) from YAML spec."
requires-python = ">=3.10"
dependencies = [
  "pyyaml>=6.0",
  "jinja2>=3.1",
]

[project.scripts]
qmanual = "qmanual.cli:main"

[tool.setuptools.package-data]
qmanual = ["templates/*.j2"]
""",
    "qmanual/README.md": """# qmanual
Generate Quarto manual scaffolds from YAML spec.

## Usage
pip install -e .

qmanual init --spec manual_spec.yml --out manual_site
qmanual render --out manual_site
""",
    "qmanual/src/qmanual/__init__.py": "__all__ = []\n",
    "qmanual/src/qmanual/spec.py": """from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class PageItem:
    path: str
    title: str


@dataclass(frozen=True)
class PageSection:
    section: str
    items: List[PageItem]


@dataclass(frozen=True)
class SiteSpec:
    title: str = "Manual"
    theme: str = "cosmo"
    app_link: Optional[str] = None
    sidebar_style: str = "docked"
    sidebar_search: bool = True
    collapse_level: int = 1


@dataclass(frozen=True)
class ManualSpec:
    site: SiteSpec
    pages: List[PageSection]


def load_spec(spec_path: Path) -> ManualSpec:
    raw: Dict[str, Any] = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    site_raw = raw.get("site", {}) or {}

    site = SiteSpec(
        title=site_raw.get("title", "Manual"),
        theme=site_raw.get("theme", "cosmo"),
        app_link=site_raw.get("app_link"),
        sidebar_style=(site_raw.get("sidebar", {}) or {}).get("style", "docked"),
        sidebar_search=bool((site_raw.get("sidebar", {}) or {}).get("search", True)),
        collapse_level=int((site_raw.get("sidebar", {}) or {}).get("collapse_level", 1)),
    )

    pages: List[PageSection] = []
    for sec in raw.get("pages", []) or []:
        items = [PageItem(path=i["path"], title=i["title"]) for i in (sec.get("items") or [])]
        pages.append(PageSection(section=sec.get("section", "Section"), items=items))

    return ManualSpec(site=site, pages=pages)
""",
    "qmanual/src/qmanual/generator.py": """from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .spec import ManualSpec


def _jinja_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )


def generate_manual(*, spec: ManualSpec, out_dir: Path, overwrite: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    env = _jinja_env(template_dir)

    yml_t = env.get_template("quarto_yml_website.j2")
    (out_dir / "_quarto.yml").write_text(yml_t.render(spec=spec), encoding="utf-8")

    idx_t = env.get_template("index_qmd.j2")
    idx_path = out_dir / "index.qmd"
    if overwrite or not idx_path.exists():
        idx_path.write_text(idx_t.render(spec=spec), encoding="utf-8")

    page_t = env.get_template("page_qmd.j2")
    for sec in spec.pages:
        for item in sec.items:
            p = out_dir / item.path
            p.parent.mkdir(parents=True, exist_ok=True)
            if (not overwrite) and p.exists():
                continue
            p.write_text(
                page_t.render(title=item.title, section=sec.section, path=item.path),
                encoding="utf-8",
            )
""",
    "qmanual/src/qmanual/cli.py": """from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .spec import load_spec
from .generator import generate_manual


def _run_quarto_render(out_dir: Path) -> None:
    cmd = ["quarto", "render", str(out_dir)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"[qmanual] quarto render failed\\nSTDOUT:\\n{p.stdout}\\nSTDERR:\\n{p.stderr}")


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
""",
    "qmanual/src/qmanual/templates/quarto_yml_website.j2": """project:
  type: website

website:
  title: "{{ spec.site.title }}"
  reader-mode: true
  page-navigation: true
  sidebar:
    style: {{ spec.site.sidebar_style }}
    search: {{ "true" if spec.site.sidebar_search else "false" }}
    collapse-level: {{ spec.site.collapse_level }}
    contents:
      - href: index.qmd
        text: Home
{% for sec in spec.pages %}
      - section: "{{ sec.section }}"
        contents:
{% for item in sec.items %}
          - href: {{ item.path }}
            text: "{{ item.title }}"
{% endfor %}
{% endfor %}
{% if spec.site.app_link %}
  navbar:
    right:
      - href: "{{ spec.site.app_link }}"
        text: "App"
{% endif %}

format:
  html:
    toc: true
    theme: {{ spec.site.theme }}
""",
    "qmanual/src/qmanual/templates/index_qmd.j2": """---
title: "{{ spec.site.title }}"
---

## Welcome

- 왼쪽 사이드바에서 문서를 탐색하세요.
""",
    "qmanual/src/qmanual/templates/page_qmd.j2": """---
title: "{{ title }}"
---

## {{ title }}

- Section: {{ section }}
- Source path: `{{ path }}`

### TODO
- 여기에 매뉴얼 내용을 작성하세요.
""",
    "manual_spec.yml": """site:
  title: "PCR Primer Manual"
  theme: "cosmo"
  app_link: "/"
  sidebar:
    style: "docked"
    search: true
    collapse_level: 1

pages:
  - section: "Getting started"
    items:
      - path: "getting-started/install.qmd"
        title: "Install"
      - path: "getting-started/quickstart.qmd"
        title: "Quickstart"
""",
}

def main() -> None:
    root = Path(".").resolve()
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)

    for rel, content in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    print("✅ created qmanual package scaffold")
    print("Next:")
    print("  python script.py  # (already ran if you see this)")
    print("  cd qmanual && pip install -e .")
    print("  qmanual init --spec ../manual_spec.yml --out ../manual_site")
    print("  cd ../manual_site && quarto preview")

if __name__ == "__main__":
    main()
