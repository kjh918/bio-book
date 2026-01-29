from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional

class BorderSideModel(BaseModel):
    style: Optional[str] = "none"
    color: Optional[str] = "00000000"

class BorderModel(BaseModel):
    left: BorderSideModel = Field(default_factory=BorderSideModel)
    right: BorderSideModel = Field(default_factory=BorderSideModel)
    top: BorderSideModel = Field(default_factory=BorderSideModel)
    bottom: BorderSideModel = Field(default_factory=BorderSideModel)

class StyleModel(BaseModel):
    font: Dict[str, Any] = Field(default_factory=lambda: {
        "name": "Calibri", "size": 11, "bold": False, "italic": False, "color": "FF000000"
    })
    alignment: Dict[str, Any] = Field(default_factory=lambda: {
        "horizontal": "general", "vertical": "bottom", "wrap_text": False
    })
    border: BorderModel = Field(default_factory=BorderModel)
    number_format: str = "General"

class CellModel(BaseModel):
    coordinate: str
    value: Any = None
    style: StyleModel = Field(default_factory=StyleModel)

class MergedCellModel(BaseModel):
    range_string: str
    master_coordinate: str
    cells_in_range: List[str]

class SheetModel(BaseModel):
    sheet_name: str
    cells: Dict[str, CellModel] = Field(default_factory=dict)
    merged_cells: List[MergedCellModel] = Field(default_factory=list)
    row_heights: Dict[int, float] = Field(default_factory=dict)
    col_widths: Dict[str, float] = Field(default_factory=dict)

class WorkbookModel(BaseModel):
    sheets: List[SheetModel] = Field(default_factory=list)