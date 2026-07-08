"""
gencurix_report.fill_content
==============================

Dispatches a `ContentBlock` (from models.py) into a target shape, picking
the right rendering (bullets / plain paragraphs / table / image) based on
which field was set, and honoring an optional position/size override
(given in inches on the ContentBlock).
"""

from pptx.util import Inches

from .models import ContentBlock
from . import slide_utils as su


def _resolve_box(shape, block: ContentBlock):
    """Build an (left, top, width, height) EMU tuple from block.position /
    block.size, falling back to the target shape's own box for any part
    that wasn't specified. Returns None if neither was given at all (i.e.
    just use the shape's box outright)."""
    if block.position is None and block.size is None:
        return None

    left, top = (block.position if block.position is not None else (None, None))
    width, height = (block.size if block.size is not None else (None, None))

    left = Inches(left) if left is not None else shape.left
    top = Inches(top) if top is not None else shape.top
    width = Inches(width) if width is not None else shape.width
    height = Inches(height) if height is not None else shape.height
    return (left, top, width, height)


def apply_content_block(slide, shape, block: ContentBlock):
    """Fill `shape` (a [CONTENTS]-style placeholder) with `block`'s data.
    Priority when multiple fields are set: image_path > table > bullets >
    paragraphs. `block.position`/`block.size` (inches) optionally override
    where the image/table is placed; bullets/paragraphs always use the
    shape's own text box."""
    if block is None:
        return

    box = _resolve_box(shape, block)

    if block.image_path:
        su.fill_image(slide, shape, block.image_path, box=box)
    elif block.table:
        su.fill_table(slide, shape, block.table.headers, block.table.rows, box=box)
    elif block.bullets:
        su.fill_bullets(shape, block.bullets, bulleted=True)
    elif block.paragraphs:
        su.fill_bullets(shape, block.paragraphs, bulleted=False)
    # If nothing was set, leave the placeholder text as-is (caller's choice).
