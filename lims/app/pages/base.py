import os
from dash import Dash, dash_table
import dash_ag_grid as dag
import dash_bootstrap_components as dbc

# 우리가 만든 세련된 통합 레이아웃(상단 네비게이션바 포함)을 불러옵니다.
from app.ui.shared_ui import apply_modern_layout 

class LimsDashApp:
    def __init__(self, name: str, pathname_prefix: str):
        # 🚀 [수정] FLATLY처럼 자기주장이 강한 테마 대신, 
        # 순정 BOOTSTRAP을 사용하여 우리가 만든 style.css가 100% 완벽하게 적용되도록 변경!
        self.app = Dash(
            name, 
            requests_pathname_prefix=pathname_prefix, 
            external_stylesheets=[dbc.themes.BOOTSTRAP] 
        )

    def set_content(self, content_layout_func):
        """
        각 페이지별 고유 컨텐츠를 받아 
        공통 모던 레이아웃(Top Navbar 포함) 안에 조립해주는 메서드
        """
        def serve_layout():
            # apply_modern_layout이 상단바와 배경/여백을 알아서 처리합니다.
            return apply_modern_layout(content_layout_func())
            
        self.app.layout = serve_layout

    def get_app(self) -> Dash:
        return self.app

    # ========================================================
    # 🚀 1. 전역 공통 컬럼 관리 (왼쪽 5대 핵심 컬럼 명칭 정립)
    # ========================================================
    @staticmethod
    def get_base_grid_columns(include_project=True):
        base_columns = []
        
        if include_project:
            base_columns.append({
                "headerName": "Project", 
                "field": "project_name", 
                "width": 150, 
                "rowGroup": True,      
                "hide": True,          
                "pinned": "left"       
            })
            
        base_columns.extend([
            {
                "headerName": "접수 ID (Order ID)", 
                "field": "order_id", 
                "width": 180, 
                "pinned": "left",      
                "editable": False, 
                # 🚀 짙은 회색 대신, 모던하고 깔끔한 연파랑/라이트그레이 배경으로 통일
                "cellStyle": {"fontWeight": "bold", "backgroundColor": "#f8fafc"} 
            },
             
            {
                "headerName": "샘플 ID (ACC ID)", 
                "field": "sample_id", 
                "width": 180, 
                "pinned": "left",      
                "editable": False, 
                "cellStyle": {"fontWeight": "bold", "color": "#0d6efd", "backgroundColor": "#f8fafc"}
            },

            {
                "headerName": "환자 ID (Patient ID)", 
                "field": "sample_name",  
                "width": 180, 
                "pinned": "left",      
                "editable": False, 
                "cellStyle": {"fontWeight": "bold", "backgroundColor": "#fffbeb"} # 아주 연한 노란색(하이라이트)
            },
            
            {
                "headerName": "검사 종류", 
                "field": "target_panel", 
                "width": 120, 
                "pinned": "left",      
                "editable": False,
                "cellStyle": {"backgroundColor": "#f1f5f9", "textAlign": "center"}
            }
        ])
        
        return base_columns

    # ========================================================
    # 🚀 2. 표준 DataTable (모던 SaaS 테마 적용)
    # ========================================================
    @staticmethod
    def create_standard_table(id: str, columns: list, data: list, **kwargs):
        """NGS LIMS 전역에서 사용되는 반응형/표준화된 기본 DataTable"""
        default_kwargs = {
            'page_action': 'none',
            'fixed_rows': {'headers': True},
            'fixed_columns': {'headers': True, 'data': 4}, 
            'style_table': {
                'overflowX': 'auto',  
                'overflowY': 'auto', 
                'minWidth': '100%', 
                'width': '100%', 
                'maxHeight': '70vh',
                'border': '1px solid #e2e8f0', # 표 전체 얇은 테두리
                'borderRadius': '8px' # 표 모서리 둥글게
            },
            # 🚀 [핵심 수정] 시커먼 남색(#2C3E50) 제거 -> 세련된 라이트 그레이 헤더
            'style_header': {
                'backgroundColor': '#f8fafc', 
                'color': '#475569', # 슬레이트 그레이 텍스트
                'fontWeight': '700', 
                'textAlign': 'center', 
                'height': '45px',
                'fontSize': '13px',  
                'padding': '10px',
                'border': '1px solid #e2e8f0'
            },
            # 🚀 셀 스타일도 화사하게 변경
            'style_cell': {
                'minWidth': '120px', 
                'width': 'auto', 
                'maxWidth': 'none',
                'overflow': 'hidden', 
                'textOverflow': 'ellipsis',
                'textAlign': 'center', 
                'padding': '10px', 
                'backgroundColor': '#ffffff',
                'color': '#1e293b', # 너무 새까맣지 않은 진회색 텍스트
                'fontSize': '13px',
                'border': '1px solid #e2e8f0'
            },
            'style_data': {
                'whiteSpace': 'normal', 
                'height': 'auto', 
                'lineHeight': '1.5'
            },
            'style_data_conditional': [
                # 홀수 줄에 아주 연한 회색을 주어 가독성 향상
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#fcfcfc'} 
            ]
        }
        
        default_kwargs.update(kwargs)
        return dash_table.DataTable(id=id, columns=columns, data=data, **default_kwargs)
    
    # ========================================================
    # 🚀 3. 표준 AG Grid (공통 그룹화 및 반응형 최적화)
    # ========================================================
    @staticmethod
    def create_standard_aggrid(id: str, columnDefs: list = None, height: str = "400px", **kwargs):
        final_columns = columnDefs if columnDefs else []

        grid_kwargs = {
            "id": id,
            "rowData": [], 
            "columnDefs": final_columns,
            "defaultColDef": {
                "resizable": True, 
                "sortable": True, 
                "filter": True,
                "editable": True, 
                "minWidth": 120  
            },
            "dashGridOptions": {
                "rowHeight": 45,
                "singleClickEdit": True,              
                "stopEditingWhenCellsLoseFocus": True, 
                "undoRedoCellEditing": True,           
                "undoRedoCellEditingLimit": 50,
                "enterNavigatesVertically": True,      
                
                "animateRows": True,                  
                "groupDefaultExpanded": 2,            
                "autoGroupColumnDef": {
                    "headerName": "Project / 검사 종류 / 접수 계층 트리",
                    "minWidth": 320,
                    "cellRendererParams": {
                        "checkbox": True              
                    }
                }
            },
            "style": {"height": height, "width": "100%"},
            # 🚀 AG Grid도 부드러운 테마와 둥근 모서리 적용
            "className": "ag-theme-alpine border-0 shadow-sm rounded-3" 
        }
        
        grid_kwargs.update(kwargs)
        return dag.AgGrid(**grid_kwargs)