from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime

from app.pages.base import LimsDashApp  
from app.core.database import SessionLocal
from app.models.schema import NGSTracking

# ==========================================
# [1] 화면 레이아웃
# ==========================================
def create_billing_dashboard_layout():
    return dbc.Container([
        html.H3("💸 의뢰처별 매출/매입 정산 대시보드", className="fw-bold mb-4 text-secondary"),
        
        # 🚀 1. 상단 필터 바 (연도 선택)
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("📅 조회 연도 선택", className="fw-bold small"),
                        dcc.Dropdown(id="billing-year-filter", placeholder="전체 연도", clearable=True)
                    ], width=3),
                    dbc.Col([
                        html.Div(id="filter-info-text", className="text-muted small mt-4")
                    ], width=9, className="text-end")
                ])
            ])
        ], className="shadow-sm border-0 rounded-4 mb-4"),

        # 2. 상단 요약 카드 (KPI)
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("선택 기간 매출액", className="text-muted mb-2"),
                    html.H2(id="kpi-total-revenue", children="₩ 0", className="fw-bold text-primary")
                ])
            ], className="shadow-sm border-start border-primary border-5")),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("선택 기간 매입액", className="text-muted mb-2"),
                    html.H2(id="kpi-total-cost", children="₩ 0", className="fw-bold text-danger")
                ])
            ], className="shadow-sm border-start border-danger border-5")),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("예상 순이익", className="text-muted mb-2"),
                    html.H2(id="kpi-total-profit", children="₩ 0", className="fw-bold text-success")
                ])
            ], className="shadow-sm border-start border-success border-5")),
        ], className="mb-4"),

        # 3. 컨트롤 패널
        dbc.Row([
            dbc.Col([
                dbc.Button("🔄 데이터 새로고침", id="btn-refresh-billing", color="secondary", className="me-2 outline"),
                dbc.Button("📥 엑셀로 내보내기", id="btn-export-billing", color="success", className="fw-bold"),
                dcc.Download(id="download-billing-excel")
            ], width=12, className="text-end mb-2")
        ]),

        # 4. 정산 마스터 테이블
        dbc.Card([
            dbc.CardBody([
                html.Div(id="billing-table-container", className="mt-2", style={'minHeight': '500px'})
            ])
        ], className="shadow-sm rounded-4 border-0")

    ], fluid=True, className="py-4 bg-light min-vh-100")


# ==========================================
# [2] 콜백 로직
# ==========================================
def register_billing_callbacks(dash_app):
    
    # -----------------------------------------------------
    # 1. 페이지 로드 시 연도 필터 옵션 채우기
    # -----------------------------------------------------
    @dash_app.callback(
        Output("billing-year-filter", "options"),
        Input("btn-refresh-billing", "n_clicks")
    )
    def update_year_options(n):
        db = SessionLocal()
        try:
            query = db.query(NGSTracking).all()
            if not query: return []
            
            df = pd.DataFrame([q.excel_data for q in query if q.excel_data])
            # 날짜 파싱 (YYMMDD -> datetime)
            df['dt'] = pd.to_datetime(df['Reception Date'].astype(str).str.split('.').str[0], format='%y%m%d', errors='coerce')
            years = sorted(df['dt'].dt.year.dropna().unique(), reverse=True)
            
            return [{"label": f"{int(y)}년", "value": int(y)} for y in years]
        finally:
            db.close()

    # -----------------------------------------------------
    # 2. 메인 대시보드 업데이트 (연도 필터 및 의뢰처 그룹화 적용)
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("billing-table-container", "children"),
         Output("kpi-total-revenue", "children"),
         Output("kpi-total-cost", "children"),
         Output("kpi-total-profit", "children"),
         Output("filter-info-text", "children")],
        [Input("btn-refresh-billing", "n_clicks"),
         Input("billing-year-filter", "value")]
    )
    def update_billing_dashboard(n_clicks, selected_year):
        db = SessionLocal()
        try:
            query = db.query(NGSTracking).all()
            if not query:
                return html.Div("데이터가 없습니다."), "₩ 0", "₩ 0", "₩ 0", ""
            
            raw_data = [q.excel_data for q in query if q.excel_data]
            df = pd.DataFrame(raw_data)
            
            # 날짜 및 숫자 전처리
            df['dt'] = pd.to_datetime(df['Reception Date'].astype(str).str.split('.').str[0], format='%y%m%d', errors='coerce')
            df['매출 단가'] = pd.to_numeric(df['매출 단가'], errors='coerce').fillna(0)
            df['매입 단가'] = pd.to_numeric(df['매입 단가'], errors='coerce').fillna(0)
            
            # 🚀 연도 필터 적용
            if selected_year:
                df = df[df['dt'].dt.year == selected_year]
                info_text = f"조회 기준: {selected_year}년 전체"
            else:
                info_text = "조회 기준: 전체 기간"

            if df.empty:
                return html.Div("해당 기간에 데이터가 없습니다."), "₩ 0", "₩ 0", "₩ 0", info_text

            # 🚀 [핵심] Order Facility(의뢰처) 기준으로 그룹화
            # 의뢰처별로 프로젝트 수, 샘플 수, 금액 합계를 집계합니다.
            summary_df = df.groupby('Order Facility').agg(
                의뢰처그룹=('Order Facility', 'first'),
                고객사명=('의뢰사', 'first'),
                진행프로젝트수=('Order ID', 'nunique'),
                총샘플수=('Sample Name', 'count'),
                총매출액=('매출 단가', 'sum'),
                총매입액=('매입 단가', 'sum')
            ).reset_index()
            
            summary_df['순이익'] = summary_df['총매출액'] - summary_df['총매입액']
            
            # KPI 카드용 계산
            total_rev = summary_df['총매출액'].sum()
            total_cost = summary_df['총매입액'].sum()
            total_profit = summary_df['순이익'].sum()

            # 포매팅
            for col in ['총매출액', '총매입액', '순이익']:
                summary_df[col] = summary_df[col].apply(lambda x: f"₩ {int(x):,}")

            # 테이블 생성
            display_cols = [{"name": col, "id": col} for col in summary_df.columns]
            
            from app.pages.base import LimsDashApp
            table = LimsDashApp.create_standard_table(
                id="billing-summary-table",
                columns=display_cols,
                data=summary_df.to_dict('records'),
                style_table={'overflowX': 'auto', 'minHeight': '500px'},
                style_cell_conditional=[
                    {'if': {'column_id': c}, 'textAlign': 'right', 'fontWeight': 'bold'} 
                    for c in ['총매출액', '총매입액', '순이익']
                ]
            )

            return table, f"₩ {int(total_rev):,}", f"₩ {int(total_cost):,}", f"₩ {int(total_profit):,}", info_text

        finally:
            db.close()

    # -----------------------------------------------------
    # 3. 엑셀 다운로드 (필터링된 상태 그대로)
    # -----------------------------------------------------
    @dash_app.callback(
        Output("download-billing-excel", "data"),
        Input("btn-export-billing", "n_clicks"),
        State("billing-summary-table", "data"),
        prevent_initial_call=True
    )
    def export_to_excel(n_clicks, table_data):
        if not table_data: return no_update
        df = pd.DataFrame(table_data)
        filename = f"Billing_By_Facility_{datetime.now().strftime('%y%m%d')}.xlsx"
        return dcc.send_data_frame(df.to_excel, filename, index=False)

def create_billing_dashboard_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_billing_dashboard_layout)
    app = lims.get_app()
    register_billing_callbacks(app)
    return app