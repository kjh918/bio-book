#!/bin/bash

# 1. 디렉토리 생성
PROJECT_NAME="xl_obj_engine"
mkdir -p $PROJECT_NAME/src/$PROJECT_NAME/core
mkdir -p $PROJECT_NAME/data
mkdir -p $PROJECT_NAME/output

cd $PROJECT_NAME

# 2. requirements.txt 작성
cat <<EOF > requirements.txt
openpyxl
pydantic
EOF

# 3. 모델 정의 (models.py)
cat <<EOF > src/$PROJECT_NAME/core/models.py
from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional

class BorderSideModel(BaseModel):
    style: Optional[str] = None
    color: Optional[str] = None

class BorderModel(BaseModel):
    left: BorderSideModel = Field(default_factory=BorderSideModel)
    right: BorderSideModel = Field(default_factory=BorderSideModel)
    top: BorderSideModel = Field(default_factory=BorderSideModel)
    bottom: BorderSideModel = Field(default_factory=BorderSideModel)

class StyleModel(BaseModel):
    font: Dict[str, Any] = {}
    alignment: Dict[str, Any] = {}
    border: BorderModel = Field(default_factory=BorderModel)
    number_format: str = "General"

class CellModel(BaseModel):
    coordinate: str
    value: Any = None
    style: StyleModel = Field(default_factory=StyleModel)

class SheetModel(BaseModel):
    sheet_name: str
    cells: Dict[str, CellModel]
    merged_cells: List[str] = []
    row_heights: Dict[int, float] = Field(default_factory=dict)
    col_widths: Dict[str, float] = Field(default_factory=dict)

class WorkbookModel(BaseModel):
    sheets: List[SheetModel]
EOF

# 4. 엔진 정의 (engine.py)
cat <<EOF > src/$PROJECT_NAME/core/engine.py
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
from .models import WorkbookModel, SheetModel, CellModel, StyleModel, BorderModel, BorderSideModel

class ExcelObjectEngine:
    @staticmethod
    def read_to_model(file_path: str) -> WorkbookModel:
        wb = openpyxl.load_workbook(file_path)
        sheet_models = []
        for ws in wb.worksheets:
            cell_dict = {}
            for row in ws.iter_rows():
                for cell in row:
                    border = BorderModel(
                        left=BorderSideModel(style=cell.border.left.style),
                        right=BorderSideModel(style=cell.border.right.style),
                        top=BorderSideModel(style=cell.border.top.style),
                        bottom=BorderSideModel(style=cell.border.bottom.style)
                    )
                    style = StyleModel(
                        font={"name": cell.font.name, "bold": cell.font.bold, "size": cell.font.size},
                        alignment={"horizontal": cell.alignment.horizontal, "vertical": cell.alignment.vertical},
                        border=border,
                        number_format=cell.number_format
                    )
                    cell_dict[cell.coordinate] = CellModel(coordinate=cell.coordinate, value=cell.value, style=style)
            
            row_heights = {r: ws.row_dimensions[r].height for r in ws.row_dimensions if ws.row_dimensions[r].height}
            col_widths = {c: ws.column_dimensions[c].width for c in ws.column_dimensions if ws.column_dimensions[c].width}
            merged = [str(m_range) for m_range in ws.merged_cells.ranges]
            
            sheet_models.append(SheetModel(
                sheet_name=ws.title, cells=cell_dict, merged_cells=merged,
                row_heights=row_heights, col_widths=col_widths
            ))
        return WorkbookModel(sheets=sheet_models)

    @staticmethod
    def export_from_model(model: WorkbookModel, output_path: str):
        new_wb = openpyxl.Workbook()
        new_wb.remove(new_wb.active)
        for s_model in model.sheets:
            ws = new_wb.create_sheet(title=s_model.sheet_name)
            for r, h in s_model.row_heights.items(): ws.row_dimensions[r].height = h
            for c, w in s_model.col_widths.items(): ws.column_dimensions[c].width = w
            for coord, c_model in s_model.cells.items():
                cell = ws[coord]
                cell.value = c_model.value
                b = c_model.style.border
                cell.border = Border(
                    left=Side(style=b.left.style), right=Side(style=b.right.style),
                    top=Side(style=b.top.style), bottom=Side(style=b.bottom.style)
                )
                cell.font = Font(**c_model.style.font)
                cell.alignment = Alignment(**c_model.style.alignment)
            for m_range in s_model.merged_cells: ws.merge_cells(m_range)
        new_wb.save(output_path)
EOF

# 5. 실행 예제 (main.py)
cat <<EOF > main.py
import json
from src.$PROJECT_NAME.core.engine import ExcelObjectEngine

# 1. 기존 엑셀 읽기 (객체화)
model = ExcelObjectEngine.read_to_model("data/input_template.xlsx")

# 2. JSON으로 변환 및 확인
json_str = model.model_dump_json(indent=2)
with open("output/report_structure.json", "w") as f:
    f.write(json_str)

# 3. 객체 데이터 수정 (비즈니스 로직)
# 예: 첫 번째 시트의 A1 셀 값 변경
model.sheets[0].cells["A1"].value = "UPDATED REPORT"

# 4. 새로운 엑셀로 내보내기 (서식/병합/크기 유지)
ExcelObjectEngine.export_from_model(model, "output/final_report.xlsx")
print("Process Complete: Check 'output' directory.")
EOF

# 6. 샘플 엑셀 생성 스크립트 (setup_sample.py)
cat <<EOF > setup_sample.py
import openpyxl
from openpyxl.styles import Border, Side, Alignment, Font

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Analysis_Report"

# 레이아웃 설정
ws.column_dimensions['A'].width = 30
ws.row_dimensions[1].height = 30

# 병합 및 테두리
ws.merge_cells("A1:C1")
cell = ws["A1"]
cell.value = "BIOINFORMATICS PIPELINE RESULT"
cell.font = Font(bold=True, size=14)
cell.alignment = Alignment(horizontal="center", vertical="center")
thin = Side(style='thin')
cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)

wb.save("data/input_template.xlsx")
print("Sample template created in 'data/'")
EOF

echo "Build complete. Running setup..."
python3 setup_sample.py
echo "Setup finished. You can now run 'python3 main.py'"