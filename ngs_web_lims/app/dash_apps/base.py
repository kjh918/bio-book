# app/dash_apps/base.py
from dash import Dash, dash_table
import dash_bootstrap_components as dbc
from app.dash_apps.shared_ui import create_navbar

class LimsDashApp:
    def __init__(self, name: str, pathname_prefix: str):
        # 1. 공통 Dash 앱 초기화 및 테마(FLATLY) 일괄 적용
        self.app = Dash(
            name, 
            requests_pathname_prefix=pathname_prefix, 
            external_stylesheets=[dbc.themes.FLATLY]
        )
        
    def set_content(self, content_layout_func):
        """
        각 페이지별 고유 컨텐츠(표, 그래프 등)를 받아 
        공통 Navbar와 배경 레이아웃 안에 조립(Mount)해주는 팩토리 메서드
        """
        def serve_layout():
            return dbc.Container([
                create_navbar(), # 공통 네비게이션 바
                
                # 개별 페이지 컨텐츠가 들어갈 자리
                dbc.Container(
                    content_layout_func(), 
                    className="p-4"
                )
            ], fluid=True, className="bg-light", style={"minHeight": "100vh", "padding": "0"})
            
        # Dash 앱 레이아웃에 최종 완성본 할당
        self.app.layout = serve_layout

    def get_app(self) -> Dash:
        """라우터에 마운트할 원본 Dash 객체 반환"""
        return self.app
    @staticmethod
    def create_standard_table(id: str, columns: list, data: list, **kwargs):
        """
        NGS LIMS 전역에서 사용되는 반응형/표준화된 DataTable을 반환합니다.
        추가 옵션(editable, dropdown 등)은 kwargs로 받아서 병합합니다.
        """
        # 1. 뭉개짐 방지 및 UI 공통 베이스 스타일 설정
        default_kwargs = {
            'page_action': 'none',
            'fixed_rows': {'headers': True},
            'fixed_columns': {'headers': True, 'data': 4}, 
            
            'style_table': {
                'overflowX': 'auto', 
                'minWidth': '100%',
                'overflowY': 'auto',
                'maxHeight': '70vh' 
            },
            'style_header': {
                'backgroundColor': '#2C3E50', 
                'color': 'white', 
                'fontWeight': 'bold',
                'textAlign': 'center',
                'height': '40px' # 헤더 높이 고정
            },
            'style_cell': {
                # 고정 너비를 주어야 틀어짐이 없습니다.
                'minWidth': '150px', 'width': '150px', 'maxWidth': '150px',
                'overflow': 'hidden',
                'textOverflow': 'ellipsis',
                'textAlign': 'center',
                'padding': '10px',
                'backgroundColor': 'white' # 기본 배경색을 지정해야 투명하게 겹치지 않음
            },
            'style_data': {
                'whiteSpace': 'normal',
                'height': '45px', # [중요] 행 높이를 auto가 아닌 고정값으로 지정
                'lineHeight': '1.2'
            },
            'style_data_conditional': [
                # 지브라 패턴 (배경색 지정 시 z-index가 중요)
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'},
                
                # [핵심] 시스템 고정 필드 강조용 스타일
                {
                    'if': {'column_id': 'Registration ID'},
                    'fontWeight': 'bold',
                    'backgroundColor': '#f0f7ff'
                }
            ]
        }

        # 2. 사용자가 호출 시 넘겨준 추가 속성(kwargs)을 기본 속성에 덮어쓰기
        default_kwargs.update(kwargs)

        # 3. 최종 완성된 Dash DataTable 반환
        return dash_table.DataTable(
            id=id,
            columns=columns,
            data=data,
            **default_kwargs
        )