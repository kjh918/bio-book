from dash import html, dcc, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from datetime import datetime

from app.core.database import SessionLocal
from app.models.schema import NGSTracking
from app.pages.base import LimsDashApp 

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
                        html.Label("🏢 의뢰 기관 (의뢰사)", className="fw-bold small"),
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
                    html.H5("📅 월별 접수 및 진행 추이", className="fw-bold mb-3"),
                    dcc.Graph(id="graph-trend-line")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm")
            ], width=12),
        ]),
        
        dcc.Interval(id='dash-refresh', interval=300*1000, n_intervals=0) # 5분마다 갱신
    ], className="p-4")

def register_dashboard_callbacks(dash_app):
    
    # -----------------------------------------------------
    # 1. 필터 옵션 동적 생성 (DB 데이터 기준)
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
            query = db.query(NGSTracking).all()
            if not query: return [], [], []
            df = pd.DataFrame([q.excel_data for q in query])
            
            # 날짜 파싱
            clean_dates = df['Reception Date'].astype(str).str.split('.').str[0].str.strip()
            
            # 2. 'YYMMDD' 형식(%y%m%d)으로 먼저 해석 시도하고, 실패하면 일반 날짜 형식으로 2차 시도
            df['dt'] = pd.to_datetime(clean_dates, format='%y%m%d', errors='coerce').fillna(
                pd.to_datetime(clean_dates, errors='coerce')
            )
            
            df['year'] = df['dt'].dt.year
            years = sorted([y for y in df['year'].unique() if y > 0], reverse=True)
            orgs = sorted([str(o) for o in df['의뢰사'].unique() if pd.notna(o)])
            items = sorted([str(i) for i in df['Analysis Type'].unique() if pd.notna(i)])
            
            return [{"label": f"{y}년", "value": y} for y in years], \
                   [{"label": o, "value": o} for o in orgs], \
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
    # 3. 데이터 연산 및 그래프 업데이트 (메인 콜백)
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
            query = db.query(NGSTracking).all()
            if not query: return "0건", "0건", {}, {}, {}
            
            df = pd.DataFrame([q.excel_data for q in query]) 
            clean_dates = df['Reception Date'].astype(str).str.split('.').str[0].str.strip()
            
            # 2. 'YYMMDD' 형식(%y%m%d)으로 먼저 해석 시도하고, 실패하면 일반 날짜 형식으로 2차 시도
            df['dt'] = pd.to_datetime(clean_dates, format='%y%m%d', errors='coerce').fillna(
                pd.to_datetime(clean_dates, errors='coerce')
            )
            
            df['year'] = df['dt'].dt.year
            df['month_name'] = df['dt'].dt.strftime('%m월')
            print(df['year'])
            # 디버깅용 출력 (이제 NaN이 아니라 2026-04-03 등으로 예쁘게 찍힐 겁니다!)
            # print(df[['Reception Date', 'dt', 'year', 'month_name']])

            # --- 필터 적용 ---
            if year: df = df[df['year'] == year]
            if org: df = df[df['의뢰사'] == org]
            if item: df = df[df['Analysis Type'] == item]

            # 1. 카드 지표
            total_cnt = f"{len(df):,}"
            ongoing_cnt = f"{len(df[~df['진행사항'].str.contains('완료', na=False)]):,}"

            # 2. 의뢰 항목별 분포 (Pie)
            item_counts = df['Analysis Type'].value_counts().reset_index(name='count')
            fig_pie = px.pie(item_counts, values='count', names='Analysis Type', 
                             hole=0.5, template='plotly_white',
                             color_discrete_sequence=px.colors.qualitative.Safe)
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))

            # 3. 주요 의뢰 기관 순위 (Bar)
            org_counts = df['의뢰사'].value_counts().reset_index(name='count').head(10)
            fig_bar = px.bar(org_counts, x='count', y='의뢰사', orientation='h',
                             text='count', template='plotly_white',
                             color='count', color_continuous_scale='Blues')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=20))

            # 4. 월별 추이 (Line)
            trend_df = df.groupby(df['dt'].dt.strftime('%y-%m')).size().reset_index(name='count')
            trend_df = trend_df.sort_values('dt')
            fig_line = px.area(trend_df, x='dt', y='count', 
                               labels={'dt': '접수월', 'count': '시료수'},
                               template='plotly_white', line_shape='spline')
            fig_line.update_traces(line_color='#3498db', fillcolor='rgba(52, 152, 219, 0.2)')
            
            return total_cnt, ongoing_cnt, fig_pie, fig_bar, fig_line

        finally:
            db.close()

def create_summary_dashboard(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_dashboard_layout)
    app = lims.get_app() 
    register_dashboard_callbacks(app)
    return app