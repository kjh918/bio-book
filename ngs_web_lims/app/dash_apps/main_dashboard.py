import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from datetime import datetime
from app.core.database import SessionLocal
from app.models.schema import NGSTracking
from app.dash_apps.shared_ui import create_navbar

def create_summary_dashboard(requests_pathname_prefix: str):
    app = dash.Dash(
        __name__,
        requests_pathname_prefix=requests_pathname_prefix,
        external_stylesheets=[dbc.themes.FLATLY]
    )

    app.layout = html.Div([
        create_navbar(),
        dbc.Container([
            html.H2("📊 NGS 서비스 의뢰 통계", className="text-center my-4 fw-bold"),
            
            # --- 상단 요약 카드 ---
            dbc.Row([
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H4("총 의뢰 건수", className="card-title text-muted"),
                        html.H2(id="total-count", className="fw-bold text-primary")
                    ])
                ], className="text-center shadow-sm"), width=4),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H4("올해 의뢰 건수", className="card-title text-muted"),
                        html.H2(id="year-count", className="fw-bold text-success")
                    ])
                ], className="text-center shadow-sm"), width=4),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H4("이번 달 접수", className="card-title text-muted"),
                        html.H2(id="month-count", className="fw-bold text-info")
                    ])
                ], className="text-center shadow-sm"), width=4),
            ], className="mb-4"),

            # --- 중앙 그래프 영역 ---
            dbc.Row([
                # 1. 연도별 의뢰 추이 (선 그래프)
                dbc.Col([
                    html.Div([
                        html.H5("📅 연도별 의뢰 추이", className="fw-bold mb-3"),
                        dcc.Graph(id="year-trend-graph")
                    ], className="p-3 bg-white border rounded shadow-sm")
                ], width=6),
                
                # 2. 올해 월별 현황 (막대 그래프 + 필터)
                dbc.Col([
                    html.Div([
                        html.H5("📈 올해 월별 상세 현황", className="fw-bold mb-3"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("분석 대상 선택:"),
                                dcc.Dropdown(
                                    id="filter-type",
                                    options=[
                                        {"label": "의뢰 기관별", "value": "Order Facility"},
                                        {"label": "분석 종류별", "value": "Analysis Type"}
                                    ],
                                    value="Order Facility",
                                    clearable=False
                                )
                            ])
                        ], className="mb-3"),
                        dcc.Graph(id="month-bar-graph")
                    ], className="p-3 bg-white border rounded shadow-sm")
                ], width=6),
            ]),
            
            dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0) # 1분마다 갱신
        ], fluid=True)
    ])

    @app.callback(
        [Output("total-count", "children"),
         Output("year-count", "children"),
         Output("month-count", "children"),
         Output("year-trend-graph", "figure"),
         Output("month-bar-graph", "figure")],
        [Input("filter-type", "value"),
         Input("interval-component", "n_intervals")]
    )
    def update_dashboard(filter_col, n):
        db = SessionLocal()
        try:
            # 1. 데이터 불러오기
            query = db.query(NGSTracking).all()
            if not query:
                return "0", "0", "0", px.scatter(title="데이터 없음"), px.scatter(title="데이터 없음")

            # excel_data(JSON) 내의 모든 정보를 Pandas DataFrame으로 변환
            df = pd.DataFrame([q.excel_data for q in query])
            
            # 날짜 전처리 (Reception Date 또는 Created At 기준)
            # 접수 번호 ACC-260408 에서 날짜 추출 가능
            df['date'] = pd.to_datetime(df['Registration ID'].str.split('-').str[1], format='%y%m%d')
            df['year'] = df['date'].dt.year
            df['month'] = df['date'].dt.month
            
            now = datetime.now()
            this_year = now.year
            this_month = now.month

            # 2. 요약 지표 계산
            total = len(df)
            y_total = len(df[df['year'] == this_year])
            m_total = len(df[(df['year'] == this_year) & (df['month'] == this_month)])

            # 3. 연도별 그래프 (Line)
            year_df = df.groupby('year').size().reset_index(name='count')
            fig_year = px.line(year_df, x='year', y='count', markers=True, 
                               labels={'year': '연도', 'count': '건수'},
                               template='plotly_white')

            # 4. 올해 월별 그래프 (Bar)
            current_year_df = df[df['year'] == this_year].copy()
            # 1월~12월 모든 달이 나오도록 카테고리 설정
            current_year_df['month_name'] = current_year_df['month'].apply(lambda x: f"{x}월")
            
            # 선택한 필터(의뢰기관 or 분석종류)에 따른 집계
            # 컬럼명이 정확하지 않을 경우를 대비해 처리
            target_col = filter_col if filter_col in df.columns else 'Order Facility'
            
            fig_month = px.bar(
                current_year_df, 
                x='month_name', 
                color=target_col,
                category_orders={"month_name": [f"{i}월" for i in range(1, 13)]},
                labels={'month_name': '월', 'count': '건수', target_col: '구분'},
                template='plotly_white',
                barmode='group'
            )

            return f"{total:,}건", f"{y_total:,}건", f"{m_total:,}건", fig_year, fig_month

        finally:
            db.close()

    return app