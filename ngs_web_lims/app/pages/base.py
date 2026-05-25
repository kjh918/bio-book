# app/pages/base.py
import os
from dash import Dash, dash_table
import dash_ag_grid as dag
import dash_bootstrap_components as dbc

# 우리가 만든 세련된 통합 레이아웃(상단 네비게이션바 포함)을 불러옵니다.
from app.ui.shared_ui import apply_modern_layout 

class LimsDashApp:
    def __init__(self, name: str, pathname_prefix: str):
        # 공통 Dash 앱 초기화 및 테마 일괄 적용 (FLATLY 테마로 화사하게 설정)
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

    # ========================================================
    # 🚀 1. 전역 공통 컬럼 관리 (왼쪽 5대 핵심 컬럼 명칭 정립)
    # ========================================================
    @staticmethod
    def get_base_grid_columns(include_project=True):
        """
        NGS LIMS 전역에서 테이블 좌측에 완벽히 고정(Pinned)되는 필수 식별자 컬럼입니다.
        연구원님이 정해주신 3대 식별자(접수 ID, 샘플 ID, 환자 ID)의 명칭 구분을 명확히 반영했습니다.
        """
        base_columns = []
        
        # 📌 [고정 1] Project 컬럼
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
            # 📌 [고정 2] 접수 ID (Order ID)
            {
                "headerName": "접수 ID (Order ID)", # 🌟 명칭 수정
                "field": "order_id", 
                "width": 180, 
                "pinned": "left",      
                "editable": False, 
                "cellStyle": {"fontWeight": "bold", "backgroundColor": "#f8f9fa"}
            },
             
            # 📌 [고정 3] 샘플 ID (ACC ID)
            {
                "headerName": "샘플 ID (ACC ID)", # 🌟 명칭 수정
                "field": "sample_id", 
                "width": 180, 
                "pinned": "left",      
                "editable": False, 
                "cellStyle": {"fontWeight": "bold", "color": "#0d6efd", "backgroundColor": "#f8f9fa"}
            },

            # 📌 [고정 4] 환자 ID (Patient ID)
            {
                "headerName": "환자 ID (Patient ID)", # 🌟 명칭 수정
                "field": "sample_name",  
                "width": 180, 
                "pinned": "left",      
                "editable": False, 
                "cellStyle": {"fontWeight": "bold", "backgroundColor": "#fef9e7"} 
            },
            
            # 📌 [고정 5] 검사 종류 (패널)
            {
                "headerName": "검사 종류", 
                "field": "target_panel", 
                "width": 120, 
                "pinned": "left",      
                "editable": False,
                "cellStyle": {"backgroundColor": "#f1f3f5", "textAlign": "center"}
            }
        ])
        
        return base_columns
    # ========================================================
    # 🚀 2. 표준 DataTable (기본 테이블용 틀고정 탑재)
    # ========================================================
    @staticmethod
    def create_standard_table(id: str, columns: list, data: list, **kwargs):
        """NGS LIMS 전역에서 사용되는 반응형/표준화된 기본 DataTable"""
        default_kwargs = {
            'page_action': 'none',
            'fixed_rows': {'headers': True},
            # 📌 DataTable용 여러 개 틀고정: 왼쪽에서부터 3개 컬럼(Order ID, Sample ID, 검사 종류)을 고정
            'fixed_columns': {'headers': True, 'data': 4}, 
            'style_table': {
                'overflowX': 'auto',  # 가로 스크롤 생성 (화면 축소 시 찌그러짐 방지)
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
                'minWidth': '120px', # 📌 틀고정 기능을 쓸 때는 고정된 폭(minWidth) 지정이 필수입니다.
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
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'}
            ]
        }
        
        # 개별 페이지에서 특별히 넘겨준 옵션이 있다면 기본 옵션 위에 덮어씌웁니다.
        default_kwargs.update(kwargs)
        return dash_table.DataTable(id=id, columns=columns, data=data, **default_kwargs)
    
    # ========================================================
    # 🚀 3. 표준 AG Grid (공통 그룹화 및 반응형 최적화)
    # ========================================================
    @staticmethod
    def create_standard_aggrid(id: str, columnDefs: list = None, height: str = "400px", **kwargs):
        """
        NGS LIMS 전역에서 사용되는 가볍고 강력한 고기능 표준 AG Grid입니다.
        데이터 등록, 파이프라인 분석 이관 화면 등 대용량 데이터 시각화에 최적화되어 있습니다.
        """
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
                "minWidth": 120  # 화면이 극단적으로 줄어도 120px 이하로 찌그러지지 않고 세련되게 스크롤바 생성
            },
            "dashGridOptions": {
                "rowHeight": 45,
                "singleClickEdit": True,              # 더블클릭 대신 한 번만 클릭해도 엑셀처럼 즉시 수정 모드 진입
                "stopEditingWhenCellsLoseFocus": True, # 다른 셀을 클릭하면 수정 중이던 데이터가 자동으로 확정 및 저장됨
                "undoRedoCellEditing": True,           # ⌨️ 오타 시 되돌리기 기능 탑재 (Ctrl + Z 사용 가능)
                "undoRedoCellEditingLimit": 50,
                "enterNavigatesVertically": True,      # 엔터 키를 누르면 아랫방향 셀로 수직 이동
                
                # 📌 계층형 트리 구조(Row Grouping) 디자인 최적화 설정
                "animateRows": True,                  # 폴더 트리를 열고 닫을 때 부드러운 애니메이션 효과
                "groupDefaultExpanded": 2,            # 켬과 동시에 2차 레이어(Project 및 검사 종류)까지 시원하게 자동 펼침
                "autoGroupColumnDef": {
                    "headerName": "Project / 검사 종류 / 접수 계층 트리",
                    "minWidth": 320,
                    "cellRendererParams": {
                        "checkbox": True              # 부모 폴더를 체크하면 하위 샘플들이 자석처럼 일괄 자동 선택되는 기능
                    }
                }
            },
            "style": {"height": height, "width": "100%"},
            "className": "ag-theme-alpine"
        }
        
        # 외부 페이지 호출부에서 주입한 특수 파라미터가 있다면 덮어씁니다.
        grid_kwargs.update(kwargs)
        return dag.AgGrid(**grid_kwargs)