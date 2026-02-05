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

class FillModel(BaseModel):
    """배경색 모델: theme 인덱스와 tint를 저장"""
    rgb: Optional[str] = "00000000"
    theme: Optional[int] = None
    tint: float = 0.0

class StyleModel(BaseModel):
    font: Dict[str, Any] = Field(default_factory=lambda: {
        "name": "Calibri", "size": 11, "bold": False, "italic": False, "color": "FF000000"
    })
    alignment: Dict[str, Any] = Field(default_factory=lambda: {
        "horizontal": None, "vertical": None, "wrap_text": False
    })
    border: BorderModel = Field(default_factory=BorderModel)
    fill: FillModel = Field(default_factory=FillModel)
    number_format: str = "General" 

class CellModel(BaseModel):
    coordinate: str
    value: Any = None
    style: StyleModel = Field(default_factory=StyleModel)

class MergedCellModel(BaseModel):
    range_string: str                
    master_coordinate: str           
    cells_in_range: List[str]        

class DimensionModel(BaseModel):
    value: float
    hidden: bool = False

class SheetModel(BaseModel):
    sheet_name: str
    cells: Dict[str, CellModel] = Field(default_factory=dict)
    merged_cells: List[MergedCellModel] = Field(default_factory=list)
    row_heights: Dict[int, DimensionModel] = Field(default_factory=dict)
    col_widths: Dict[str, DimensionModel] = Field(default_factory=dict)

class WorkbookModel(BaseModel):
    sheets: List[SheetModel] = Field(default_factory=list)