"""
gencurix_report.yaml_loader
==============================

Lets you describe an entire report as a YAML file instead of hand-building
`ReportData` in Python. See `examples/report_config.yaml` for a fully
worked example, and README.md for the schema reference.

Quick use:

    from gencurix_report.yaml_loader import build_from_yaml
    build_from_yaml("report_config.yaml", "output.pptx")

or, if you want the ReportData object instead of writing straight to disk:

    from gencurix_report.yaml_loader import load_report_data
    data = load_report_data("report_config.yaml")
"""

import csv
import datetime
import os
from typing import Optional

import yaml

from .builder import ReportBuilder
from .models import (
    ReportData, TitlePageData, ChapterItem, SummaryData, DividerData,
    SampleInfoData, ResultItem, ConclusionData, ContentBlock, TableData,
)

TOC_MAX_CHAPTERS = 4

# key-name -> section "type" is inferred by checking if the (lowercased)
# chapter key *starts with* one of these -- so "Introduction", "Introduction
# & Workflow", "intro" etc. all resolve to the same handler, while whatever
# the user actually wrote is kept verbatim as the TOC / divider display name.
_TYPE_PREFIXES = {
    "summary": "summary",
    "introduction": "introduction",
    "intro": "introduction",
    "results": "results",
    "result": "results",
    "conclusion": "conclusion",
}


# ---------------------------------------------------------------------------
# Table file loading (TSV / CSV)
# ---------------------------------------------------------------------------

def _load_table_file(path: str) -> TableData:
    ext = os.path.splitext(path)[1].lower()
    delimiter = "\t" if ext in (".tsv", ".txt") else ","
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return TableData(headers=[], rows=[])
    return TableData(headers=rows[0], rows=rows[1:])


# ---------------------------------------------------------------------------
# position/size -> ContentBlock helpers
# ---------------------------------------------------------------------------

def _as_pair(value):
    """Accepts [left, top] / [width, height] (2 values), or a redundant
    4-value [left, top, width, height] form (only the relevant half is used
    depending on whether this came from `position` or `size`). Returns a
    2-tuple or None."""
    if value is None:
        return None
    vals = list(value)
    if len(vals) >= 2:
        return (float(vals[0]), float(vals[1]))
    return None


def _content_block_from_node(node: dict) -> Optional[ContentBlock]:
    """node is a dict that may contain one of: image / table / bullets /
    paragraphs / text, each optionally with path/position/size (for
    image/table). Returns None if node is falsy or empty."""
    if not node:
        return None

    if "image" in node:
        img = node["image"]
        return ContentBlock(
            image_path=img["path"],
            position=_as_pair(img.get("position")),
            size=_as_pair(img.get("size")),
        )

    if "table" in node:
        tbl = node["table"]
        table_data = _load_table_file(tbl["path"])
        return ContentBlock(
            table=table_data,
            position=_as_pair(tbl.get("position")),
            size=_as_pair(tbl.get("size")),
        )

    if "bullets" in node:
        return ContentBlock(bullets=list(node["bullets"]))

    if "paragraphs" in node:
        return ContentBlock(paragraphs=list(node["paragraphs"]))

    if "text" in node:
        text = node["text"]
        if isinstance(text, list):
            return ContentBlock(paragraphs=list(text))
        if text:
            return ContentBlock(paragraphs=[str(text)])
        return None

    return None


def _find_key_ci(d: dict, *candidates):
    """Case-insensitive key lookup; returns (key, value) for the first match
    or (None, None)."""
    lower_map = {k.lower(): k for k in d.keys()}
    for cand in candidates:
        if cand.lower() in lower_map:
            k = lower_map[cand.lower()]
            return k, d[k]
    return None, None


def _infer_section_type(chapter_name: str) -> Optional[str]:
    lname = chapter_name.strip().lower()
    for prefix, kind in _TYPE_PREFIXES.items():
        if lname.startswith(prefix):
            return kind
    return None


def _to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def load_report_data(yaml_path: str) -> ReportData:
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    main = cfg.get("main", {}) or {}
    title_page = TitlePageData(
        title=main.get("title", ""),
        subtitle=main.get("subtitle", ""),
        writer=main.get("writer", ""),
        team=main.get("team", ""),
        date=str(main.get("date") or datetime.date.today().isoformat()),
    )

    contents = ((cfg.get("slides") or {}).get("contents")) or []

    chapters = []
    summary = SummaryData()
    divider_intro = None
    workflow_content = None
    sample_info = None
    divider_results = None
    results = []
    divider_conclusion = None
    conclusion = None

    divider_counter = 0

    for entry in contents:
        if not isinstance(entry, dict) or not entry:
            continue
        chapter_name, section = next(iter(entry.items()))
        section = section or {}

        if len(chapters) >= TOC_MAX_CHAPTERS:
            raise ValueError(
                f"TOC layout supports at most {TOC_MAX_CHAPTERS} chapters; "
                f"'{chapter_name}' would be #{len(chapters) + 1}"
            )
        chapters.append(ChapterItem(name=chapter_name))

        kind = _infer_section_type(chapter_name)

        if kind == "summary":
            summary = SummaryData(
                purpose=_to_list(section.get("purpose")),
                results=_to_list(section.get("results")),
                conclusion=_to_list(section.get("conclusion")),
                further_study=_to_list(section.get("further_study")),
            )

        elif kind == "introduction":
            divider_counter += 1
            divider_intro = DividerData(number=f"{divider_counter:02d}", name=chapter_name)

            _, workflow_node = _find_key_ci(section, "workflow")
            if workflow_node:
                if "workflow_png" in workflow_node:
                    img = workflow_node["workflow_png"]
                    workflow_content = ContentBlock(
                        image_path=img["path"],
                        position=_as_pair(img.get("position")),
                        size=_as_pair(img.get("size")),
                    )
                elif "workflow_table" in workflow_node:
                    tbl = workflow_node["workflow_table"]
                    workflow_content = ContentBlock(
                        table=_load_table_file(tbl["path"]),
                        position=_as_pair(tbl.get("position")),
                        size=_as_pair(tbl.get("size")),
                    )
                else:
                    workflow_content = _content_block_from_node(workflow_node)

            _, sample_node = _find_key_ci(section, "Sample Information", "sample information", "sample_info")
            if sample_node:
                if "sample_info_table" in sample_node:
                    tbl = sample_node["sample_info_table"]
                    sample_info = SampleInfoData(content=ContentBlock(
                        table=_load_table_file(tbl["path"]),
                        position=_as_pair(tbl.get("position")),
                        size=_as_pair(tbl.get("size")),
                    ))
                elif "sample_info_png" in sample_node:
                    img = sample_node["sample_info_png"]
                    sample_info = SampleInfoData(content=ContentBlock(
                        image_path=img["path"],
                        position=_as_pair(img.get("position")),
                        size=_as_pair(img.get("size")),
                    ))
                else:
                    block = _content_block_from_node(sample_node)
                    if block:
                        sample_info = SampleInfoData(content=block)

        elif kind == "results":
            divider_counter += 1
            divider_results = DividerData(number=f"{divider_counter:02d}", name=chapter_name)

            for item in (section.get("items") or []):
                item_title = item.get("title", "")
                content = _content_block_from_node(item)
                results.append(ResultItem(title=item_title, content=content))

        elif kind == "conclusion":
            divider_counter += 1
            divider_conclusion = DividerData(number=f"{divider_counter:02d}", name=chapter_name)

            conc_title = section.get("title", chapter_name)

            _, conc_node = _find_key_ci(section, "Conclusion", "conclusion")
            content_1 = _content_block_from_node(conc_node) if conc_node else None

            _, further_node = _find_key_ci(section, "Further study", "further_study", "further study")
            content_2 = _content_block_from_node(further_node) if further_node else None

            conclusion = ConclusionData(title=conc_title, content_1=content_1, content_2=content_2)

        else:
            # Unrecognized section type -- it still shows up in the TOC
            # (added above), but no content slide is generated for it.
            pass

    return ReportData(
        title_page=title_page,
        chapters=chapters,
        summary=summary,
        divider_intro=divider_intro or DividerData(number="01", name="Introduction"),
        workflow_content=workflow_content,
        sample_info=sample_info,
        divider_results=divider_results,
        results=results,
        divider_conclusion=divider_conclusion,
        conclusion=conclusion,
    )


def build_from_yaml(yaml_path: str, output_path: str, template_path: str = None) -> str:
    """Parse `yaml_path` and write the filled deck to `output_path`."""
    data = load_report_data(yaml_path)
    return ReportBuilder(template_path=template_path).build(data, output_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m gencurix_report.yaml_loader <config.yaml> <output.pptx>")
        raise SystemExit(1)
    out = build_from_yaml(sys.argv[1], sys.argv[2])
    print("Wrote:", out)
