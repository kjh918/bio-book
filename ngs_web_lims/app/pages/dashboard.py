from dash import html, dcc, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from datetime import datetime

from app.core.database import SessionLocal
from app.models.schema import NGSTracking

# [경로 주의] 다이어트된 구조에 맞게 임포트 (app.ui.base 또는 app.pages.base 등 실제 위치에 맞게 수정)
from app.pages.base import LimsDashApp 

def create_dashboard_layout():
    """요청하신 4가지 지표에 집중한 대시보드 레이아웃"""
    return html.Div([
        html.H2("📊 NGS LIMS 통합 대시보드", className="text-center mb-4 fw-bold text-secondary"),
        
        # --- [1] 상단 요약 카드 (진행 중인 프로젝트 수 추가) ---
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("총 의뢰 시료", className="card-title text-muted fw-bold"),
                html.H3(id="total-count", className="fw-bold text-primary mb-0")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=3),
            
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("올해 접수 시료", className="card-title text-muted fw-bold"),
                html.H3(id="year-count", className="fw-bold text-success mb-0")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=3),
            
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("이번 달 접수 시료", className="card-title text-muted fw-bold"),
                html.H3(id="month-count", className="fw-bold text-info mb-0")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=3),
            
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("🚀 현재 진행 중인 프로젝트", className="card-title text-muted fw-bold"),
                html.H3(id="ongoing-project-count", className="fw-bold text-danger mb-0")
            ]), className="text-center shadow-sm border-0 rounded-4"), width=3),
        ], className="mb-4"),

        # --- [2] 중앙 영역: 진행 현황(파이) + 현재 진행 중인 프로젝트(테이블) ---
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("🧪 전체 시료 진행 현황", className="fw-bold mb-3"),
                    dcc.Graph(id="status-pie-graph")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm h-100")
            ], width=4),
            
            dbc.Col([
                html.Div([
                    html.H5("🚀 현재 진행 중인 프로젝트 (최근 접수순)", className="fw-bold mb-3"),
                    html.Div(id="ongoing-projects-table-container") # 콜백에서 테이블 렌더링
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm h-100")
            ], width=8),
        ], className="mb-4"),

        # --- [3] 하단 영역: 연도별 현황(선) + 월별 진행 현황(누적 막대) ---
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("📅 연도별 의뢰 현황", className="fw-bold mb-3"),
                    dcc.Graph(id="year-trend-graph")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm")
            ], width=5),
            
            dbc.Col([
                html.Div([
                    html.H5("📊 올해 월별 진행 현황", className="fw-bold mb-3"),
                    dcc.Graph(id="month-stacked-bar")
                ], className="p-3 bg-white border-0 rounded-4 shadow-sm")
            ], width=7),
        ]),
        
        dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0)
    ])


def register_dashboard_callbacks(dash_app):
    """대시보드의 데이터 연산 및 그래프 생성 콜백"""
    @dash_app.callback(
        [Output("total-count", "children"), 
         Output("year-count", "children"), 
         Output("month-count", "children"),
         Output("ongoing-project-count", "children"),
         Output("status-pie-graph", "figure"), 
         Output("ongoing-projects-table-container", "children"),
         Output("year-trend-graph", "figure"), 
         Output("month-stacked-bar", "figure")],
        [Input("interval-component", "n_intervals")]
    )
    def update_dashboard(n):
        db = SessionLocal()
        try:
            query = db.query(NGSTracking).all()
            
            def empty_fig(title="데이터 없음"):
                return px.scatter(title=title, template='plotly_white')

            if not query:
                return "0건", "0건", "0건", "0건", empty_fig(), html.Div("진행 중인 프로젝트가 없습니다."), empty_fig(), empty_fig()

            df = pd.DataFrame([q.excel_data for q in query])
            
            # --- 1. 날짜 전처리 ---
            def parse_date(val):
                if not val or pd.isna(val): return pd.NaT
                val = str(val).strip()
                try:
                    if len(val) == 6 and val.isdigit(): return datetime.strptime(val, '%y%m%d')
                    return pd.to_datetime(val)
                except: return pd.NaT

            df['date'] = df['Reception Date'].apply(parse_date)
            # 날짜 없는 데이터는 오늘 날짜로 임시 대체 (에러 방지)
            df['date'] = df['date'].fillna(pd.Timestamp.today())
            
            df['year'] = df['date'].dt.year
            df['month'] = df['date'].dt.month
            df['month_name'] = df['month'].apply(lambda x: f"{x}월")
            df['진행사항'] = df.get('진행사항', pd.Series(['접수 대기']*len(df))).fillna('접수 대기')

            now = datetime.now()
            this_year, this_month = now.year, now.month

            # --- 2. 카드 요약 지표 ---
            total_cnt = len(df)
            y_cnt = len(df[df['year'] == this_year])
            m_cnt = len(df[(df['year'] == this_year) & (df['month'] == this_month)])

            # "완료"라는 단어가 포함되지 않은 항목을 '진행 중'으로 간주
            ongoing_df = df[~df['진행사항'].str.contains('완료', na=False)]
            ongoing_prj_cnt = ongoing_df['Order ID'].nunique() if 'Order ID' in df.columns else 0

            # --- 3. [지표 1] 진행 현황 (Pie Chart) ---
            status_counts = df['진행사항'].value_counts().reset_index(name='count')
            fig_pie = px.pie(
                status_counts, values='count', names='진행사항',
                hole=0.45, template='plotly_white',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))

            # --- 4. [지표 2] 현재 진행 중인 프로젝트 (DataTable) ---
            if ongoing_df.empty:
                ongoing_table = html.Div("🎉 현재 밀린(진행 중인) 프로젝트가 없습니다!", className="text-center text-success mt-5 fw-bold")
            else:
                # 프로젝트별로 그룹화하여 요약
                prj_summary = ongoing_df.groupby(['Reception Date', 'Order ID', '의뢰사']).agg(
                    시료수=('Sample Name', 'count'),
                    현재상태=('진행사항', lambda x: x.mode()[0] if not x.empty else '알 수 없음') # 가장 많이 차지하는 상태 표시
                ).reset_index()
                prj_summary = prj_summary.sort_values(by='Reception Date', ascending=False).head(8) # 최근 8개만 표시

                # [수정됨] 대시보드 카드 영역에 맞게 표 찌그러짐을 방지하고 너비를 100%로 폅니다.
                ongoing_table = LimsDashApp.create_standard_table(
                    id="ongoing-table",
                    columns=[{"name": c, "id": c} for c in prj_summary.columns],
                    data=prj_summary.to_dict('records'),
                    
                    # 1. 좁은 공간에서 표가 엇나가는 주범인 '틀 고정(fixed_columns)' 해제
                    fixed_columns={'headers': True, 'data': 0}, 
                    
                    # 2. 표 전체 너비를 100%로 꽉 채우고 불필요한 가로 스크롤 제거
                    style_table={
                        'height': '350px', 
                        'overflowY': 'auto', 
                        'overflowX': 'hidden', 
                        'width': '100%', 
                        'minWidth': '100%'
                    },
                    
                    # 3. 각 칸의 150px 강제 고정을 풀고 내용에 맞게 유동적으로 배분 (auto)
                    style_cell={
                        'fontSize': '14px', 
                        'padding': '12px', 
                        'textAlign': 'center',
                        'minWidth': '50px',
                        'width': 'auto',
                        'maxWidth': 'none',
                        'whiteSpace': 'normal', # 글자가 길면 예쁘게 줄바꿈
                        'backgroundColor': 'white'
                    },
                    
                    # 4. 헤더 여백 및 글꼴 크기 조정
                    style_header={
                        'backgroundColor': '#2C3E50',
                        'color': 'white',
                        'fontWeight': 'bold',
                        'fontSize': '14px',
                        'padding': '12px'
                    }
                )
            # --- 5. [지표 3] 연도별 의뢰 현황 (Line Chart) ---
            year_df = df.groupby('year').size().reset_index(name='count')
            fig_year = px.line(
                year_df, x='year', y='count', markers=True, 
                labels={'year': '연도', 'count': '시료 수'}, template='plotly_white'
            )
            fig_year.update_layout(xaxis=dict(tickmode='linear', dtick=1), margin=dict(t=20, b=20))

            # --- 6. [지표 4] 월별 진행 현황 (Stacked Bar Chart) ---
            curr_year_df = df[df['year'] == this_year]
            month_group = curr_year_df.groupby(['month_name', '진행사항']).size().reset_index(name='count')
            fig_month = px.bar(
                month_group, x='month_name', y='count', color='진행사항',
                category_orders={"month_name": [f"{i}월" for i in range(1, 13)]},
                labels={'month_name': '월', 'count': '시료 수'}, template='plotly_white', barmode='stack'
            )
            fig_month.update_layout(margin=dict(t=20, b=20), legend_title_text='상태')

            return (
                f"{total_cnt:,}건", f"{y_cnt:,}건", f"{m_cnt:,}건", f"{ongoing_prj_cnt:,}건",
                fig_pie, ongoing_table, fig_year, fig_month
            )

        finally:
            db.close()


def create_summary_dashboard(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_dashboard_layout)
    app = lims.get_app() 
    register_dashboard_callbacks(app)
    return app