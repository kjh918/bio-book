from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import yaml
import os

from app.core.database import SessionLocal
from app.models.schema import NGSTracking
from app.pages.base import LimsDashApp 
from app.core.config import BASE_DIR # 경로 설정을 위해 추가

# -----------------------------------------------------
# 🚀 0. 기관명(Facility) 매핑 사전 로드 함수
# -----------------------------------------------------
def load_facility_mapping():
    yaml_path = os.path.join(BASE_DIR, "config", "order_facility.yaml")
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            # yaml 파일 구조에 맞게 수정해주세요. (예: {'C01': '젠큐릭스', 'H01': '서울대병원'})
            # 만약 리스트 형태라면 딕셔너리로 변환하는 로직이 필요합니다.
            return config if isinstance(config, dict) else {}
    except Exception as e:
        print(f"⚠️ Facility 매핑 파일을 읽을 수 없습니다: {e}")
        return {}

def create_dashboard_layout():
    return html.Div([
        html.H2("📊 NGS LIMS 통합 분석 대시보드", className="text-center mb-4 fw-bold text-secondary"),
        
        # --- [1] 상단 검색 필터 바 (년도, 의뢰사, 의뢰항목) ---
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("📅 접수 년도", className="fw-bold small"),
                        dcc.Dropdown(id="filter-year", placeholder="전체 년도", clearable=True)
                    ], width=3),
                    dbc.Col([
                        html.Label("🏢 의뢰 기관 (그룹)", className="fw-bold small"),
                        dcc.Dropdown(id="filter-org", placeholder="전체 기관", clearable=True)
                    ], width=4),
                    dbc.Col([
                        html.Label("🧬 의뢰 항목 (Analysis Type)", className="fw-bold small"),
                        dcc.Dropdown(id="filter-item", placeholder="전체 항목", clearable=True)
                    ], width=3),
                    dbc.Col([
                        html.Label(" ", className="d-block"),
                        dbc.Button("🔄 초기화", id="btn-reset-filter", color="secondary", outline=True, className="w-100")
                    ], width=2),
                ])
            ])
        ], className="shadow-sm border-0 rounded-4 mb-4"),

        # --- [2] 요약 지표 카드 ---
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("필터된 총 시료", className="text-muted small"),
                html.H3(id="card-total", className="fw-bold text-primary mb-0")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=4),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("진행 중인 프로젝트", className="text-muted small"),
                html.H3(id="card-ongoing", className="fw-bold text-danger mb-0")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=4),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("평균 분석 소요(예상)", className="text-muted small"),
                html.H3(id="card-avg", className="fw-bold text-success mb-0", children="14일")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=4),
        ], className="mb-4"),

        # --- [3] 메인 그래프 영역 ---
        dbc.Row([
            # 좌측: 분석 항목별 비중
            dbc.Col([
                html.Div([
                    html.H5("🧬 의뢰 항목별 분포", className="fw-bold mb-3"),
                    dcc.Graph(id="graph-item-pie")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm h-100")
            ], width=4),
            
            # 우측: 의뢰 기관별 상위 순위
            dbc.Col([
                html.Div([
                    html.H5("🏢 주요 의뢰 기관 (TOP 10)", className="fw-bold mb-3"),
                    dcc.Graph(id="graph-org-bar")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm h-100")
            ], width=8),
        ], className="mb-4"),

        # --- [4] 하단 추이 영역 ---
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("📅 월별 접수 추이", className="fw-bold mb-3"),
                    dcc.Graph(id="graph-trend-line")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm")
            ], width=12),
        ]),
        
        dcc.Interval(id='dash-refresh', interval=300*1000, n_intervals=0) # 5분마다 갱신
    ], className="p-4")

def register_dashboard_callbacks(dash_app):
    
    facility_map = load_facility_mapping()

    # -----------------------------------------------------
    # 1. 필터 옵션 동적 생성 (🚀 DB 스키마 활용)
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("filter-year", "options"),
         Output("filter-org", "options"),
         Output("filter-item", "options")],
        [Input("dash-refresh", "n_intervals")]
    )
    def update_filter_options(n):
        db = SessionLocal()
        try:
            # DB 컬럼을 직접 활용하므로 pandas 파싱이 필요 없어 매우 빠릅니다!
            years = [r[0] for r in db.query(NGSTracking.reception_year).distinct().all() if r[0] is not None]
            orgs_raw = [r[0] for r in db.query(NGSTracking.order_facility).distinct().all() if r[0] is not None]
            items = [r[0] for r in db.query(NGSTracking.analysis_type).distinct().all() if r[0] is not None]
            
            years.sort(reverse=True)
            items.sort()
            
            # 기관 코드(C01)를 yaml에 정의된 예쁜 이름(젠큐릭스)으로 번역하여 옵션에 담습니다.
            org_options = []
            for code in orgs_raw:
                label_name = facility_map.get(code, code) # 매핑이 없으면 코드 그대로 표시
                org_options.append({"label": f"{label_name} ({code})", "value": code})

            return [{"label": f"{y}년", "value": y} for y in years], \
                   org_options, \
                   [{"label": i, "value": i} for i in items]
        finally:
            db.close()

    # -----------------------------------------------------
    # 2. 필터 초기화 버튼
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("filter-year", "value"),
         Output("filter-org", "value"),
         Output("filter-item", "value")],
        [Input("btn-reset-filter", "n_clicks")],
        prevent_initial_call=True
    )
    def reset_filters(n):
        return None, None, None

    # -----------------------------------------------------
    # 3. 데이터 연산 및 그래프 업데이트 (🚀 메모리 최적화 초고속 버전)
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("card-total", "children"),
         Output("card-ongoing", "children"),
         Output("graph-item-pie", "figure"),
         Output("graph-org-bar", "figure"),
         Output("graph-trend-line", "figure")],
        [Input("filter-year", "value"),
         Input("filter-org", "value"),
         Input("filter-item", "value"),
         Input("dash-refresh", "n_intervals")]
    )
    def update_graphs(year, org, item, n):
        db = SessionLocal()
        try:
            # 🚀 [핵심 튜닝] NGSTracking 덩어리 전체가 아니라, '필요한 컬럼 4개'만 깃털처럼 가볍게 가져옵니다!
            # 무거운 excel_data(JSON)는 아예 건드리지도 않습니다.
            query = db.query(
                NGSTracking.reception_date.label("date"),
                NGSTracking.order_facility.label("facility"),
                NGSTracking.analysis_type.label("item"),
                NGSTracking.status.label("status")
            )
            
            # 필터 조건 적용
            if year: query = query.filter(NGSTracking.reception_year == year)
            if org: query = query.filter(NGSTracking.order_facility == org)
            if item: query = query.filter(NGSTracking.analysis_type == item)
            
            # DB에서 데이터를 List of Tuples 형태로 순식간에 가져옴
            results = query.all()
            
            if not results: 
                return "0건", "0건", {}, {}, {}
            
            # 🚀 for문 돌릴 필요 없이, 가져온 결과를 바로 Pandas DataFrame으로 꽂아 넣습니다!
            df = pd.DataFrame(results)

            # 1. 카드 지표
            total_cnt = f"{len(df):,}"
            
            # 진행사항 컬럼에서 결측치를 안전하게 비우고, '완료'가 안 들어간 것을 진행 중으로 카운트
            ongoing_cnt = f"{len(df[~df['status'].fillna('').str.contains('완료')]):,}"

            # 2. 의뢰 항목별 분포 (Pie)
            item_counts = df['item'].value_counts().reset_index(name='count')
            fig_pie = px.pie(item_counts, values='count', names='item', 
                             hole=0.5, template='plotly_white',
                             color_discrete_sequence=px.colors.qualitative.Safe)
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))

            # 3. 주요 의뢰 기관 순위 (Bar) - YAML 번역 적용
            org_counts = df['facility'].value_counts().reset_index(name='count').head(10)
            facility_map = load_facility_mapping()
            org_counts['facility_name'] = org_counts['facility'].map(lambda x: facility_map.get(x, x))
            
            fig_bar = px.bar(org_counts, x='count', y='facility_name', orientation='h',
                             text='count', template='plotly_white',
                             color='count', color_continuous_scale='Blues')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=20))

            # 4. 월별 추이 (Line)
            df['year_month'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m')
            trend_df = df.groupby('year_month').size().reset_index(name='count').dropna().sort_values('year_month')
            
            fig_line = px.area(trend_df, x='year_month', y='count', 
                               labels={'year_month': '접수월', 'count': '시료수'},
                               template='plotly_white', line_shape='spline')
            fig_line.update_traces(line_color='#3498db', fillcolor='rgba(52, 152, 219, 0.2)', mode='lines+markers')
            fig_line.update_layout(xaxis=dict(tickangle=-45))
            
            return total_cnt, ongoing_cnt, fig_pie, fig_bar, fig_line

        finally:
            db.close()

def create_summary_dashboard(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_dashboard_layout)
    app = lims.get_app() 
    register_dashboard_callbacks(app)
    return app