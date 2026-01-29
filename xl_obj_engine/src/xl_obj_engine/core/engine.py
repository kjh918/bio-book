# src/xl_obj_engine/core/engine.py

import openpyxl
from openpyxl.utils import range_boundaries, get_column_letter
from openpyxl.styles import Font, Alignment, Border, Side
from .models import WorkbookModel, SheetModel, CellModel, StyleModel, BorderModel, BorderSideModel, MergedCellModel

class ExcelObjectEngine:
    @staticmethod
    def read_to_model(file_path: str) -> WorkbookModel:
        wb = openpyxl.load_workbook(file_path, data_only=False)
        sheet_models = []
        
        for ws in wb.worksheets:
            # 1. 병합 셀 분석
            merged_list = []
            for m_range in ws.merged_cells.ranges:
                min_col, min_row, max_col, max_row = range_boundaries(str(m_range))
                cells = [f"{get_column_letter(c)}{r}" for r in range(min_row, max_row+1) for c in range(min_col, max_col+1)]
                merged_list.append(MergedCellModel(
                    range_string=str(m_range), 
                    master_coordinate=f"{get_column_letter(min_col)}{min_row}", 
                    cells_in_range=cells
                ))

            # 2. 셀 데이터 로드 (에러 방지를 위해 최소한의 스타일만)
            cell_dict = {}
            for row in ws.iter_rows():
                for cell in row:
                    cell_dict[cell.coordinate] = CellModel(
                        coordinate=cell.coordinate, 
                        value=cell.value
                    )

            # 3. [FIXED] 행 높이 및 열 너비 수집 로직 수정
            row_heights = {}
            for r, rd in ws.row_dimensions.items():
                if rd.height is not None:
                    try:
                        # 키값을 반드시 int로 캐스팅하여 StyleProxy 유입 방지
                        row_heights[int(r)] = float(rd.height)
                    except (ValueError, TypeError):
                        continue

            col_widths = {}
            for c, cd in ws.column_dimensions.items():
                if cd.width is not None:
                    try:
                        # 키값을 반드시 str(A, B, C...)로 캐스팅
                        col_widths[str(c)] = float(cd.width)
                    except (ValueError, TypeError):
                        continue

            sheet_models.append(SheetModel(
                sheet_name=ws.title,
                cells=cell_dict,
                merged_cells=merged_list,
                row_heights=row_heights,
                col_widths=col_widths
            ))
            
        return WorkbookModel(sheets=sheet_models)

    @staticmethod
    def export_from_model(model: WorkbookModel, output_path: str):
        new_wb = openpyxl.Workbook()
        new_wb.remove(new_wb.active)
        
        for s_model in model.sheets:
            ws = new_wb.create_sheet(title=s_model.sheet_name)
            
            # 차원 설정
            for r, h in s_model.row_heights.items(): 
                ws.row_dimensions[int(r)].height = h
            for c, w in s_model.col_widths.items(): 
                ws.column_dimensions[str(c)].width = w

            # 데이터 주입
            for coord, c_model in s_model.cells.items():
                ws[coord].value = c_model.value
            
            # 병합 실행
            for m_obj in s_model.merged_cells:
                try:
                    ws.merge_cells(m_obj.range_string)
                except:
                    continue
                    
        new_wb.save(output_path)