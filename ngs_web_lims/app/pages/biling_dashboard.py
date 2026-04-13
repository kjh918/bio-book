from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime

from app.pages.base import LimsDashApp  
from app.core.database import SessionLocal
from app.models.schema import NGSTracking

# ==========================================
# [1] 화면 레이아웃 (재무 대시보드)
# ==========================================
def create_billing_dashboard_layout():
    return dbc.Container([
        html.H3("💸 프로젝트별 매출/매입 정산 대시보드", className="fw-bold mb-4 text-secondary"),
        
        # 1. 상단 요약 카드 (KPI)
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("총 누적 매출액", className="text-muted mb-2"),
                    html.H2(id="kpi-total-revenue", children="₩ 0", className="fw-bold text-primary")
                ])
            ], className="shadow-sm border-start border-primary border-5")),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("총 누적 매입액", className="text-muted mb-2"),
                    html.H2(id="kpi-total-cost", children="₩ 0", className="fw-bold text-danger")
                ])
            ], className="shadow-sm border-start border-danger border-5")),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("총 예상 이익 (매출-매입)", className="text-muted mb-2"),
                    html.H2(id="kpi-total-profit", children="₩ 0", className="fw-bold text-success")
                ])
            ], className="shadow-sm border-start border-success border-5")),
        ], className="mb-4"),

        # 2. 컨트롤 패널 (새로고침 및 엑셀 다운로드)
        dbc.Row([
            dbc.Col([
                dbc.Button("🔄 데이터 새로고침", id="btn-refresh-billing", color="secondary", className="me-2 outline"),
                dbc.Button("📥 엑셀로 내보내기", id="btn-export-billing", color="success", className="fw-bold"),
                dcc.Download(id="download-billing-excel")
            ], width=12, className="text-end mb-2")
        ]),

        # 3. 정산 마스터 테이블
        dbc.Card([
            dbc.CardBody([
                html.Div(id="billing-table-container", className="mt-2", style={'minHeight': '500px'})
            ])
        ], className="shadow-sm rounded-4 border-0")

    ], fluid=True, className="py-4 bg-light min-vh-100")


# ==========================================
# [2] 콜백 로직 (Backend Data Aggregation)
# ==========================================
def register_billing_callbacks(dash_app):
    
    # -----------------------------------------------------
    # DB에서 데이터를 불러와 Order ID별로 병합(Group By)하는 메인 콜백
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("billing-table-container", "children"),
         Output("kpi-total-revenue", "children"),
         Output("kpi-total-cost", "children"),
         Output("kpi-total-profit", "children")],
        [Input("btn-refresh-billing", "n_clicks")] # 버튼을 누르거나 페이지 로드 시 실행
    )
    def update_billing_dashboard(n_clicks):
        db = SessionLocal()
        try:
            # 1. DB에서 모든 데이터 가져오기
            query = db.query(NGSTracking).all()
            if not query:
                return html.Div("데이터가 없습니다."), "₩ 0", "₩ 0", "₩ 0"
            
            # 2. Pandas DataFrame으로 변환
            raw_data = [q.excel_data for q in query if q.excel_data]
            df = pd.DataFrame(raw_data)
            
            # 3. 필수 컬럼이 없으면 빈 값으로 채우기 (에러 방지)
            cols_to_ensure = ['Order ID', '의뢰사', '매출 단가', '매입 단가', '견적서 발행', '세금계산서 발행일']
            for c in cols_to_ensure:
                if c not in df.columns:
                    df[c] = None

            # 4. 금액 컬럼을 숫자(Numeric)로 강제 변환 (문자열 방지)
            df['매출 단가'] = pd.to_numeric(df['매출 단가'], errors='coerce').fillna(0)
            df['매입 단가'] = pd.to_numeric(df['매입 단가'], errors='coerce').fillna(0)

            # 🚀 5. [핵심] Order ID 기준으로 그룹화(Group By) 하여 요약표 만들기
            summary_df = df.groupby('Order ID').agg(
                고객사=('의뢰사', 'first'),
                총샘플수=('Sample Name', 'count'),
                총매출액=('매출 단가', 'sum'),
                총매입액=('매입 단가', 'sum'),
                견적서발행=('견적서 발행', 'first'),
                계산서발행일=('세금계산서 발행일', 'first')
            ).reset_index()

            # 이익 계산
            summary_df['순이익'] = summary_df['총매출액'] - summary_df['총매입액']

            # KPI 카드용 전체 총합 계산
            total_rev = summary_df['총매출액'].sum()
            total_cost = summary_df['총매입액'].sum()
            total_profit = summary_df['순이익'].sum()

            # 6. 표에 보여주기 위해 금액에 콤마(,) 포매팅
            for col in ['총매출액', '총매입액', '순이익']:
                summary_df[col] = summary_df[col].apply(lambda x: f"₩ {int(x):,}")

            # 7. Dash DataTable로 변환
            display_cols = [{"name": col, "id": col} for col in summary_df.columns]
            
            from app.pages.base import LimsDashApp
            table = LimsDashApp.create_standard_table(
                id="billing-summary-table",
                columns=display_cols,
                data=summary_df.to_dict('records'),
                style_table={'overflowX': 'auto', 'minHeight': '500px'},
                # 금액 컬럼 우측 정렬
                style_cell_conditional=[
                    {'if': {'column_id': c}, 'textAlign': 'right', 'fontWeight': 'bold'} 
                    for c in ['총매출액', '총매입액', '순이익']
                ]
            )

            # KPI 카드 텍스트 포매팅
            kpi_rev_str = f"₩ {int(total_rev):,}"
            kpi_cost_str = f"₩ {int(total_cost):,}"
            kpi_profit_str = f"₩ {int(total_profit):,}"

            return table, kpi_rev_str, kpi_cost_str, kpi_profit_str

        finally:
            db.close()

    # -----------------------------------------------------
    # 엑셀 다운로드 콜백
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
        
        # 엑셀 파일로 바로 구워서 다운로드
        filename = f"Billing_Summary_{datetime.now().strftime('%y%m%d')}.xlsx"
        return dcc.send_data_frame(df.to_excel, filename, sheet_name="정산요약", index=False)

def create_billing_dashboard_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_billing_dashboard_layout)
    app = lims.get_app()
    register_billing_callbacks(app)
    return app