from __future__ import annotations

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
