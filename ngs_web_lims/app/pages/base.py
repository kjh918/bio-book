import os
from dash import Dash, dash_table
import dash_ag_grid as dag
import dash_bootstrap_components as dbc

# 우리가 만든 세련된 통합 레이아웃(상단 네비게이션바 포함)을 불러옵니다.
from app.ui.shared_ui import apply_modern_layout 

class LimsDashApp:
    def __init__(self, name: str, pathname_prefix: str):
        # 공통 Dash 앱 초기화 및 테마 일괄 적용
        self.app = Dash(
            name, 
            requests_pathname_prefix=pathname_prefix, 
            external_stylesheets=[dbc.themes.FLATLY]
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

    @staticmethod
    def create_standard_table(id: str, columns: list, data: list, **kwargs):
        """NGS LIMS 전역에서 사용되는 반응형/표준화된 DataTable"""
        default_kwargs = {
            'page_action': 'none',
            'fixed_rows': {'headers': True},
            'style_table': {
                'overflowX': 'auto',  # 🚀 가로 스크롤 생성 (화면 축소 시 찌그러짐 방지)
                'overflowY': 'auto', 
                'minWidth': '100%', 
                'width': '100%', 
                'maxHeight': '70vh'
            },
            'style_header': {
                'backgroundColor': '#2C3E50', 
                'color': 'white', 
                'fontWeight': 'bold', 
                'textAlign': 'center', 
                'height': '40px',
                'fontSize': '13px',  
                'padding': '8px'
            },
            'style_cell': {
                'minWidth': '100px', # 🚀 글자 겹침 방지: 최소 100px 보장
                'width': 'auto', 
                'maxWidth': 'none',
                'overflow': 'hidden', 
                'textOverflow': 'ellipsis',
                'textAlign': 'center', 
                'padding': '8px', 
                'backgroundColor': 'white',
                'fontSize': '12px' 
            },
            'style_data': {
                'whiteSpace': 'normal', 
                'height': 'auto', 
                'lineHeight': '1.3'
            },
            'style_data_conditional': [
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'}, 
                {
                    'if': {'column_id': 'Registration ID'},
                    'fontWeight': 'bold', 'backgroundColor': '#f0f7ff'
                }
            ]
        }
        
        # 개별 페이지에서 특별히 넘겨준 옵션이 있다면 덮어씌웁니다.
        default_kwargs.update(kwargs)
        return dash_table.DataTable(id=id, columns=columns, data=data, **default_kwargs)
    
    @staticmethod
    def create_standard_aggrid(id: str, height: str = "400px"):
        """NGS LIMS 전역에서 사용되는 반응형/표준화된 AgGrid"""
        return dag.AgGrid(
            id=id,
            rowData=[], 
            columnDefs=[],
            defaultColDef={
                "resizable": True, 
                "sortable": True, 
                "filter": True,
                "editable": True, 
                "minWidth": 120  # 🚀 화면이 줄어도 120px 이하로 찌그러지지 않고 스크롤 생성!
            },
            dashGridOptions={
                "rowHeight": 45,
                "singleClickEdit": True,
                "stopEditingWhenCellsLoseFocus": True,
                "undoRedoCellEditing": True, # [실행 취소] Ctrl+Z 탑재
                "undoRedoCellEditingLimit": 50,
                "enterNavigatesVertically": True
            },
            style={"height": height, "width": "100%"},
            className="ag-theme-alpine"
        )