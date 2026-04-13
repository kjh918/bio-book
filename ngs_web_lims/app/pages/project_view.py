from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd

from app.core.database import SessionLocal
from app.models.schema import NGSTracking
from app.pages import LimsDashApp  # 새로 만든 베이스 앱 통로(__init__.py)

def create_project_view_layout():
    """순수하게 프로젝트 뷰의 레이아웃(UI)만 정의합니다."""
    return html.Div([
        html.H3("📂 프로젝트(의뢰) 상세 조회", className="fw-bold text-secondary mb-4"),
        
        dbc.Row([
            # --- 좌측: 프로젝트 리스트 (4칸) ---
            dbc.Col([
                html.Div([
                    html.H5("📅 프로젝트 목록", className="fw-bold mb-3"),
                    dcc.Loading(
                        # [변경됨] LimsDashApp의 표준 테이블 생성기 사용!
                        LimsDashApp.create_standard_table(
                            id='project-list-table',
                            columns=[
                                {"name": "접수일", "id": "Reception Date"},
                                {"name": "Order ID", "id": "Order ID"},
                                {"name": "시료 수", "id": "Sample Count"}
                            ],
                            data=[], # 초기엔 빈 값 (콜백에서 채움)
                            row_selectable="single", # 행 선택 기능 추가
                            sort_action="native",
                            filter_action="native",
                            # 좌측 사이드바용 좁은 표에 맞춰 너비 조정
                            style_cell={'minWidth': '80px', 'textAlign': 'center', 'padding': '10px'},
                            style_table={'height': '600px', 'overflowY': 'auto'}
                        )
                    )
                ], className="p-4 bg-white border-0 rounded-4 shadow-sm h-100")
            ], width=4),

            # --- 우측: 상세 정보 뷰 (8칸) ---
            dbc.Col([
                html.Div(id='project-detail-container', children=[
                    # 초기 화면 (선택 전)
                    html.Div(
                        "👈 좌측에서 프로젝트(Order ID)를 선택하면 상세 정보가 표시됩니다.", 
                        className="text-muted text-center mt-5 fs-5"
                    )
                ], className="p-4 bg-white border-0 rounded-4 shadow-sm h-100", style={'minHeight': '650px'})
            ], width=8),
        ]),
        
        # 페이지 로드 시 데이터를 불러오기 위한 더미 트리거
        html.Div(id='dummy-trigger', style={'display': 'none'})
        
    ], className="pb-5")


def register_project_callbacks(dash_app):
    """프로젝트 뷰와 관련된 모든 콜백을 등록합니다."""
    
    # 1. 페이지 로드 시 좌측 프로젝트 목록 업데이트
    @dash_app.callback(
        Output('project-list-table', 'data'),
        Input('dummy-trigger', 'children')
    )
    def load_project_list(_):
        db = SessionLocal()
        try:
            query = db.query(NGSTracking).all()
            if not query: return []

            df = pd.DataFrame([q.excel_data for q in query])
            
            # Order ID와 Reception Date를 기준으로 그룹화하여 시료 수(Sample Count) 계산
            grouped = df.groupby(['Reception Date', 'Order ID']).size().reset_index(name='Sample Count')
            
            # 최신 접수일이 위로 오도록 정렬
            grouped = grouped.sort_values(by='Reception Date', ascending=False)
            
            return grouped.to_dict('records')
        finally:
            db.close()

    # 2. 좌측 표에서 행 선택 시 우측 상세 정보 업데이트
    @dash_app.callback(
        Output('project-detail-container', 'children'),
        Input('project-list-table', 'derived_virtual_selected_rows'),
        State('project-list-table', 'derived_virtual_data')
    )
    def display_project_details(selected_rows, table_data):
        if not selected_rows or not table_data:
            return html.Div("👈 좌측에서 프로젝트(Order ID)를 선택하면 상세 정보가 표시됩니다.", className="text-muted text-center mt-5 fs-5")

        # 선택된 행의 Order ID 가져오기
        selected_idx = selected_rows[0]
        selected_order_id = table_data[selected_idx]['Order ID']
        reception_date = table_data[selected_idx]['Reception Date']

        db = SessionLocal()
        try:
            # 해당 Order ID를 가진 데이터만 필터링 (DB 스키마 구조에 맞춤)
            query = db.query(NGSTracking).filter(NGSTracking.order_id == selected_order_id).all()
            if not query: 
                return html.Div("데이터를 찾을 수 없습니다.")

            df = pd.DataFrame([q.excel_data for q in query])
            
            # 결측치 처리
            df['진행사항'] = df.get('진행사항', pd.Series(['상태 미지정']*len(df))).fillna('상태 미지정')

            # 상태별 카운트 요약
            status_counts = df['진행사항'].value_counts()
            status_badges = []
            for status, count in status_counts.items():
                status_badges.append(dbc.Badge(f"{status}: {count}건", color="info", className="me-2 fs-6 mb-2 rounded-pill"))

            # 표시할 주요 컬럼들만 추리기
            display_cols = ['Sample ID', 'Sample Name', 'Cancer Type', 'Specimen', 'Conc.(ng/uL)', '진행사항', 'Dead Line']
            existing_cols = [c for c in display_cols if c in df.columns]
            
            # [변경됨] 우측 상세 테이블 생성 시에도 표준 팩토리 사용
            detail_table = LimsDashApp.create_standard_table(
                id="project-detail-table",
                columns=[{"name": i, "id": i} for i in existing_cols],
                data=df.to_dict('records'),
                # 상태가 '완료'인 항목 시각적 강조 옵션 병합
                style_data_conditional=[
                    {'if': {'filter_query': '{진행사항} contains "완료"'}, 'backgroundColor': '#e8f8f5', 'color': '#117a65', 'fontWeight': 'bold'},
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'} # 기본 지브라 패턴 유지
                ]
            )
            
            # 우측 상세 화면 구성 반환
            return html.Div([
                # 프로젝트 헤더
                html.H4(f"의뢰 번호: {selected_order_id}", className="fw-bold text-primary mb-1"),
                html.P(f"접수일: {reception_date} | 총 시료 수: {len(df)}건", className="text-muted mb-4"),
                
                # 진행 상태 요약 뱃지
                html.Div(status_badges, className="mb-4"),
                html.Hr(className="mb-4 text-secondary"),
                
                # 시료 상세 테이블 (위에서 생성한 테이블 꽂기)
                html.H5("📋 개별 시료 상세 현황", className="fw-bold mb-3"),
                detail_table
            ])

        finally:
            db.close()


def create_project_view_app(requests_pathname_prefix: str):
    """베이스 앱을 초기화하고 레이아웃과 콜백을 조립하여 최종 앱을 반환합니다."""
    
    # 1. LimsDashApp 초기화 (FLATLY 테마 자동 적용)
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    
    # 2. 레이아웃 세팅 (Navbar 및 Container 래퍼 자동 적용)
    lims.set_content(create_project_view_layout)
    
    # 3. 콜백 등록
    app = lims.get_app()
    register_project_callbacks(app)
    
    return app