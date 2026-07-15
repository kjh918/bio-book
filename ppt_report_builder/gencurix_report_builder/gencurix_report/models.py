"""
gencurix_report.models
=======================

Plain-data input objects for the Gencurix report builder.

These are the ONLY objects a caller needs to construct. Fill them in with
your analysis results, hand the top-level `ReportData` object to
`gencurix_report.builder.ReportBuilder.build()`, and a filled .pptx comes out.

Every field below maps 1:1 onto a placeholder that already exists in
`Gencurix_PPT_Template.pptx`. See README.md for the full placeholder map.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


# ---------------------------------------------------------------------------
# Generic content block -- used for every free-form "body" area of a slide
# (the boxes that say [CONTENTS] / [TITLE] in the template).
# ---------------------------------------------------------------------------

@dataclass
class TableData:
    """Simple table: one header row + N data rows. All values are strings
    (format numbers yourself, e.g. f"{v:.2f}", before putting them in here)."""
    headers: List[str]
    rows: List[List[str]]


@dataclass
class ContentBlock:
    """One piece of slide content. Fill in exactly ONE "source" field; the
    builder checks them in this priority order:
    image_path > plot > table > dataframe > bullets > paragraphs.

    - bullets:     list[str]        -> rendered as a bulleted list
    - paragraphs:  list[str]        -> rendered as plain (non-bulleted) paragraphs
    - table:       TableData        -> rendered as a native PowerPoint table
    - dataframe:   pandas.DataFrame -> same as `table`, converted automatically
                                        (floats are formatted with sensible
                                        default precision)
    - image_path:  str              -> a PNG/JPG is placed into the content
                                        area (e.g. a chart you already saved)
    - plot:        matplotlib Figure/Axes -> rendered to PNG in-memory with a
                                        sensible default export style (white
                                        background, tight bbox, 200 dpi) and
                                        placed exactly like image_path -- no
                                        need to save a file yourself

    You normally won't build this dataclass by hand -- use the `Image()`,
    `Plot()`, or `Table()` helper functions below, which return a
    ContentBlock for you:

        ResultItem(title="...", content=Plot(fig))
        ResultItem(title="...", content=Table(dataframe=df))
        ResultItem(title="...", content=Image("chart.png"))

    position / size are OPTIONAL overrides (inches), only used for
    image_path / plot / table / dataframe. If omitted, the image/table is
    placed inside the template's existing placeholder box (auto-fit for
    images, same left/top/width for tables). Give both to pin an exact box
    instead:

        ContentBlock(image_path="chart.png", position=(1.0, 2.0), size=(6.0, 3.5))
    """
    bullets: Optional[List[str]] = None
    paragraphs: Optional[List[str]] = None
    table: Optional[TableData] = None
    image_path: Optional[str] = None
    plot: Optional[Any] = None        # a matplotlib Figure or Axes
    dataframe: Optional[Any] = None   # a pandas DataFrame
    plot_dpi: int = 200
    position: Optional[Union[tuple, list]] = None  # (left_in, top_in)
    size: Optional[Union[tuple, list]] = None       # (width_in, height_in)


# ---------------------------------------------------------------------------
# Convenience constructors -- the "Output object" API. Each one just builds
# a ContentBlock, but reads naturally at the call site and applies sensible
# defaults (export DPI, float formatting, etc.) so callers can hand over a
# live matplotlib figure or pandas DataFrame instead of pre-exporting to
# PNG/TSV themselves.
# ---------------------------------------------------------------------------

def Image(path: str, position=None, size=None) -> ContentBlock:
    """A PNG/JPG already saved to disk."""
    return ContentBlock(image_path=path, position=position, size=size)


def Plot(figure, position=None, size=None, dpi: int = 200) -> ContentBlock:
    """A live matplotlib Figure (or Axes -- its parent Figure is used).
    Rendered to PNG in-memory at build time with a default export style;
    you don't need to call fig.savefig() yourself."""
    return ContentBlock(plot=figure, position=position, size=size, plot_dpi=dpi)


def Table(dataframe=None, headers=None, rows=None, position=None, size=None) -> ContentBlock:
    """Either pass a pandas `dataframe=`, or plain `headers=`/`rows=` lists."""
    if dataframe is not None:
        return ContentBlock(dataframe=dataframe, position=position, size=size)
    return ContentBlock(table=TableData(headers=headers or [], rows=rows or []),
                         position=position, size=size)


# ---------------------------------------------------------------------------
# Page 1 (fixed) -- Color guide. Not user-editable; kept verbatim from the

# template on every generated deck, so there is no data object for it.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Page 2 -- Main / title page
# ---------------------------------------------------------------------------

@dataclass
class TitlePageData:
    title: str
    subtitle: str = ""
    writer: str = ""
    team: str = ""
    date: str = ""


# ---------------------------------------------------------------------------
# Page 3 -- Contents (Table of Contents). Up to 4 chapter entries (this is
# a hard limit of the template's TOC layout -- 4 quadrants).
# ---------------------------------------------------------------------------

@dataclass
class ChapterItem:
    name: str


# ---------------------------------------------------------------------------
# Page 4 -- Summary (4 quadrants: Purpose / Results / Conclusion / Further
# Study). Each quadrant takes a short bullet list.
# ---------------------------------------------------------------------------

@dataclass
class SummaryData:
    purpose: List[str] = field(default_factory=list)
    results: List[str] = field(default_factory=list)
    conclusion: List[str] = field(default_factory=list)
    further_study: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Chapter divider slides ("CHAPTER 01 / Introduction" full-bleed slides).
# The template ships exactly 3 divider slots; the builder assigns them in
# order to: (1) Introduction/Workflow/Sample block, (2) Results, (3) Conclusion.
# ---------------------------------------------------------------------------

@dataclass
class DividerData:
    number: str   # e.g. "01"
    name: str     # e.g. "Introduction"


# ---------------------------------------------------------------------------
# Introduction -> Workflow -> Sample/Data block
# ---------------------------------------------------------------------------

@dataclass
class SampleInfoData:
    content: ContentBlock


# ---------------------------------------------------------------------------
# Results (repeatable -- one slide per ResultItem; the builder duplicates
# the template's results slide automatically when there is more than one)
# ---------------------------------------------------------------------------

@dataclass
class ResultItem:
    title: str
    content: ContentBlock


# ---------------------------------------------------------------------------
# Conclusion
# ---------------------------------------------------------------------------

@dataclass
class ConclusionData:
    title: str
    content_1: ContentBlock
    content_2: Optional[ContentBlock] = None


# ---------------------------------------------------------------------------
# Top level container -- this is the single object you build and pass to
# ReportBuilder.build()
# ---------------------------------------------------------------------------

@dataclass
class ReportData:
    title_page: TitlePageData
    chapters: List[ChapterItem]                 # <= 4 items, drives the TOC
    summary: SummaryData
    divider_intro: DividerData
    workflow_content: Optional[ContentBlock] = None
    sample_info: Optional[SampleInfoData] = None
    divider_results: Optional[DividerData] = None
    results: List[ResultItem] = field(default_factory=list)
    divider_conclusion: Optional[DividerData] = None
    conclusion: Optional[ConclusionData] = None
