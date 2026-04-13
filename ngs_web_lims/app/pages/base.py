# app/pages/base.py
from dash import Dash, dash_table
import dash_bootstrap_components as dbc

# [수정됨] 우리가 이전에 만든 세련된 통합 레이아웃을 불러옵니다.
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
            # 우리가 만든 apply_modern_layout이 상단바와 배경/여백을 다 알아서 해줍니다!
            return apply_modern_layout(
                content_layout_func()
            )
            
        self.app.layout = serve_layout

    def get_app(self) -> Dash:
        return self.app

    @staticmethod
    def create_standard_table(id: str, columns: list, data: list, **kwargs):
        """NGS LIMS 전역에서 사용되는 반응형/표준화된 DataTable"""
        default_kwargs = {
            'page_action': 'none',
            'fixed_rows': {'headers': True},
            
            # [수정] 전역 4열 고정은 표가 깨지는 주범이므로 기본값에서 뺍니다. 
            # (틀고정이 필요한 엑셀 트래커 같은 곳에서는 kwargs로 따로 넘겨주면 됩니다)
            
            'style_table': {
                'overflowX': 'auto', 
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
                'fontSize': '13px',  # [수정] 헤더 폰트 크기 축소
                'padding': '8px'
            },
            'style_cell': {
                # [수정] 150px 강제 족쇄를 풀고, 주어진 화면 크기에 맞게 자동으로 배분되도록(Fit) 설정
                'minWidth': '80px', 
                'width': 'auto', 
                'maxWidth': 'none',
                
                'overflow': 'hidden', 
                'textOverflow': 'ellipsis',
                'textAlign': 'center', 
                'padding': '8px', # [수정] 패딩을 약간 줄여서 타이트하고 전문적으로 보이게 함
                'backgroundColor': 'white',
                'fontSize': '12px' # [수정] 본문 폰트 크기 축소 (데이터 밀집도 상승)
            },
            'style_data': {
                'whiteSpace': 'normal', 
                'height': 'auto', # [수정] 고정 높이를 풀고 내용물에 맞게 조정
                'lineHeight': '1.3'
            },
            'style_data_conditional': [
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'}, # 지브라 패턴
                {
                    'if': {'column_id': 'Registration ID'},
                    'fontWeight': 'bold', 'backgroundColor': '#f0f7ff'
                }
            ]
        }
        
        # 개별 페이지에서 특별히 넘겨준 옵션(kwargs)이 있다면 덮어씌웁니다. (예: 틀고정, 엑셀 다운로드 등)
        default_kwargs.update(kwargs)
        
        return dash_table.DataTable(
            id=id, columns=columns, data=data, **default_kwargs
        )