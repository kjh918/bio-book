from dash import html, dcc, Input, Output, State, dash_table
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
            if not isinstance(config, dict): return {}
            
            # 최상단에 'facility_mapping' 키가 있다면 그 안쪽 데이터를 반환
            return config.get('facility_mapping', config) 
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
            dbc.Col([
                html.Div([
                    html.H5("⏳ 현재 진행 중인 프로젝트 (접수일 기준)", className="fw-bold mb-3 text-danger"),
                    dash_table.DataTable(
                        id="table-ongoing-projects",
                        columns=[
                            {"name": "접수일", "id": "date"},
                            {"name": "Order ID", "id": "order_id"},
                            {"name": "의뢰 기관", "id": "facility_name"},
                            {"name": "분석 항목", "id": "item"},
                            {"name": "샘플 수", "id": "sample_count"}, # 🚀 샘플 이름 대신 수량으로 변경!
                            {"name": "진행 상태", "id": "status"},
                        ],
                        style_table={'overflowX': 'auto', 'maxHeight': '300px', 'overflowY': 'auto'},
                        style_cell={'textAlign': 'center', 'padding': '10px', 'fontSize': '14px'},
                        style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                        style_data_conditional=[
                            {'if': {'row_index': 'odd'}, 'backgroundColor': '#fcfcfc'}
                        ],
                        sort_action="native", 
                        page_size=10 # 프로젝트 단위로 묶였으니 10개씩만 보여줘도 충분합니다.
                    )
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm mb-4")
            ], width=12),
        ]),
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
    print(facility_map)

    # -----------------------------------------------------
    # 1. 필터 옵션 동적 생성 (🚀 100% DB 스키마 직결 - JSON 제거)
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
            # DB 컬럼에서 고유값(distinct)만 순식간에 뽑아옵니다.
            years = [int(r[0]) for r in db.query(NGSTracking.reception_year).distinct().all() if r[0] is not None]
            orgs_raw = [str(r[0]) for r in db.query(NGSTracking.order_facility).distinct().all() if r[0] is not None]
            items = [str(r[0]) for r in db.query(NGSTracking.analysis_type).distinct().all() if r[0] is not None]
            
            years.sort(reverse=True)
            orgs_raw.sort()
            items.sort()
            
            # 기관 코드(C01) -> YAML 이름(젠큐릭스) 번역
            org_options = []
            for code in orgs_raw:
                info = facility_map.get(code)
                
                # yaml에 등록된 코드인 경우
                if isinstance(info, dict):
                    fac_name = info.get('facility', '')
                    team_name = info.get('team', '')
                    # 둘 다 있으면 "기관 - 팀", 하나만 있으면 하나만 표시
                    if fac_name and team_name:
                        label_name = f"{fac_name} - {team_name}"
                    else:
                        label_name = f"{fac_name}{team_name}"
                    display_label = f"{label_name} ({code})"
                # yaml에 없는 코드(예: C24)인 경우 코드 그대로 표시
                else:
                    display_label = code
                    
                org_options.append({"label": display_label, "value": code})

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
    # 3. 데이터 연산 및 그래프 업데이트
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("card-total", "children"),
         Output("card-ongoing", "children"),
         Output("table-ongoing-projects", "data"), # 🚀 Output 추가!
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
            # 🚀 테이블에 표시하기 위해 order_id와 sample_name도 같이 가져옵니다!
            query = db.query(
                NGSTracking.reception_date.label("date"),
                NGSTracking.order_facility.label("facility"),
                NGSTracking.analysis_type.label("item"),
                NGSTracking.order_id.label("order_id"),       # 추가
                NGSTracking.sample_name.label("sample_name"), # 추가
                NGSTracking.excel_data.label("excel_data")
            )
            
            if year: query = query.filter(NGSTracking.reception_year == year)
            if org: query = query.filter(NGSTracking.order_facility == org)
            if item: query = query.filter(NGSTracking.analysis_type == item)
            
            results = query.all()
            if not results: 
                return "0건", "0건", [], {}, {}, {} # 빈 리스트 추가
            
            data = []
            for r in results:
                status_val = r.excel_data.get('진행사항', '접수 대기') if r.excel_data else '접수 대기'
                data.append({
                    'date': r.date,
                    'order_id': r.order_id,
                    'sample_name': r.sample_name,
                    'facility': r.facility,
                    'item': r.item,
                    'status': status_val
                })
                
            df = pd.DataFrame(data)

            # YAML 번역 함수 내장
            facility_map = load_facility_mapping()
            def get_facility_label(code):
                info = facility_map.get(code)
                if isinstance(info, dict):
                    fac = info.get('facility', '')
                    team = info.get('team', '')
                    return f"{fac} - {team}" if fac and team else f"{fac}{team}"
                return code if code else "미분류"

            df['facility_name'] = df['facility'].apply(get_facility_label)

            # --- 1. 요약 지표 ---
            total_cnt = f"{len(df):,}"
            ongoing_cnt = f"{len(df[~df['status'].str.contains('완료', na=False)]):,}"

            # --- 🚀 2. 진행 중인 프로젝트 데이터 추출 (새로 추가됨) ---
            ongoing_df = df[~df['status'].str.contains('완료', na=False)].copy()
            
            if not ongoing_df.empty:
                # Order ID를 기준으로 데이터를 하나로 뭉칩니다.
                project_df = ongoing_df.groupby('order_id').agg({
                    'date': 'first',                # 접수일은 첫 번째 값
                    'facility_name': 'first',       # 기관명도 첫 번째 값
                    'item': 'first',                # 분석 항목(Sequencing type)
                    'sample_name': 'count',         # 🚀 샘플 이름들을 세어서 '수량'으로 변환!
                    'status': lambda x: ' / '.join(sorted(set(x))) # 상태가 섞여있을 경우 합쳐서 표시
                }).reset_index()

                # 컬럼 이름을 데이터테이블에 맞게 변경
                project_df.rename(columns={'sample_name': 'sample_count'}, inplace=True)

                # 접수일(date) 기준 오름차순(오래된 것부터) 정렬
                project_df = project_df.sort_values(by='date', ascending=True, na_position='last')
                
                # 테이블용 데이터로 변환
                table_data = project_df[['date', 'order_id', 'facility_name', 'item', 'sample_count', 'status']].to_dict('records')
            else:
                table_data = []

            # --- 3. 기존 그래프 생성 (Pie, Bar, Line) ---
            item_counts = df['item'].value_counts().reset_index(name='count')
            fig_pie = px.pie(item_counts, values='count', names='item', hole=0.5, template='plotly_white', color_discrete_sequence=px.colors.qualitative.Safe) if not item_counts.empty else {}
            
            org_counts = df['facility_name'].value_counts().reset_index(name='count').head(10)
            fig_bar = px.bar(org_counts, x='count', y='facility_name', orientation='h', text='count', template='plotly_white', color='count', color_continuous_scale='Blues') if not org_counts.empty else {}
            if fig_bar: fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=20))

            df['year_month'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m')
            trend_df = df.groupby('year_month').size().reset_index(name='count').dropna().sort_values('year_month')
            fig_line = px.area(trend_df, x='year_month', y='count', labels={'year_month': '접수월', 'count': '시료수'}, template='plotly_white', line_shape='spline') if not trend_df.empty else {}
            if fig_line: 
                fig_line.update_traces(line_color='#3498db', fillcolor='rgba(52, 152, 219, 0.2)', mode='lines+markers')
                fig_line.update_layout(xaxis=dict(tickangle=-45))
            
            # 리턴 값에 table_data 추가!
            return total_cnt, ongoing_cnt, table_data, fig_pie, fig_bar, fig_line

        finally:
            db.close()
            
def create_summary_dashboard(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_dashboard_layout)
    app = lims.get_app() 
    register_dashboard_callbacks(app)
    return app