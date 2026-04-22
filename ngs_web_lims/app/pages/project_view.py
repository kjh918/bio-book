from dash import html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from app.core.database import SessionLocal
from app.models._schema import Order, Sample
from app.pages.base import LimsDashApp
from app.ui.shared_ui import create_project_summary_card # 기존 카드 생성 함수 활용
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from app.core.database import SessionLocal
from app.models._schema import Order, Sample
from app.ui.shared_ui import create_project_summary_card # 기존 카드 생성 함수 재활용

def create_project_view_layout():
    return html.Div([
        html.H3("📂 프로젝트(의뢰) 상세 조회", className="fw-bold text-secondary mb-4"),
        
        dbc.Row([
            # --- 좌측: 최신 주문 목록 (4칸) ---
            dbc.Col([
                html.Div([
                    html.H5("📅 주문 목록", className="fw-bold mb-3"),
                    dag.AgGrid(
                        id='project-list-grid',
                        columnDefs=[
                            {"headerName": "접수일", "field": "reception_date", "width": 110},
                            {"headerName": "Order ID", "field": "order_id", "width": 160},
                            {"headerName": "시료 수", "field": "sample_count", "width": 80}
                        ],
                        rowData=[],
                        defaultColDef={"sortable": True, "filter": True, "resizable": True},
                        dashGridOptions={"rowSelection": "single"},
                        style={"height": "650px", "width": "100%"},
                        className="ag-theme-alpine"
                    )
                ], className="p-4 bg-white border-0 rounded-4 shadow-sm h-100")
            ], width=4),

            # --- 우측: 상세 정보 뷰 (8칸 - 모달 스타일) ---
            dbc.Col([
                html.Div(id='project-detail-container', children=[
                    html.Div("👈 좌측에서 주문을 선택하면 상세 정보가 표시됩니다.", 
                             className="text-muted text-center mt-5 fs-5")
                ], className="p-4 bg-white border-0 rounded-4 shadow-sm h-100", style={'minHeight': '650px'})
            ], width=8),
        ]),
    ], className="pb-4")

def register_project_callbacks(dash_app):
    
    # 1. 최신순으로 주문 목록 불러오기
    @dash_app.callback(
        Output('project-list-grid', 'rowData'),
        Input('project-list-grid', 'id')
    )
    def load_order_list(_):
        db = SessionLocal()
        try:
            # 🚀 접수일(reception_date) 기준 최신순 정렬
            orders = db.query(Order).order_by(Order.reception_date.desc()).all()
            return [
                {
                    "order_id": o.order_id, 
                    "reception_date": str(o.reception_date), 
                    "sample_count": len(o.samples)
                } for o in orders
            ]
        finally:
            db.close()

    # 2. 행 선택 시 상세 정보 표시 (모달과 동일한 UI 로직)
    # 2. [수정됨] 행 선택 시 우측 상세 정보 업데이트 (Input을 selectedRows로 변경)
    @dash_app.callback(
        Output('project-detail-container', 'children'),
        Input('project-list-grid', 'selectedRows')  # 🚀 핵심: selectionChanged 대신 selectedRows 사용
    )
    def display_project_details(selected_rows):
        # 🚀 디버깅용 로그 (터미널에 선택한 데이터가 찍히는지 꼭 확인하세요!)
        print(f"DEBUG: 선택된 행 정보: {selected_rows}")
        
        if not selected_rows:
            return html.Div("👈 좌측에서 주문을 선택하세요.", className="text-muted text-center mt-5 fs-5")

        # 🚀 선택된 데이터 가져오기 (단일 선택이므로 첫 번째 행)
        selected_row = selected_rows[0]
        order_id = selected_row.get("order_id")
        reception_date = selected_row.get("reception_date")

        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if not order: return html.Div("데이터를 찾을 수 없습니다.")

            # 상세 테이블 컬럼
            cols = ["sample_id", "sample_name", "target_panel", "current_status", "issue_comment"]
            
            detail_table = dag.AgGrid(
                columnDefs=[{"headerName": c.replace("_", " ").title(), "field": c} for c in cols],
                rowData=[{c: getattr(s, c, "") for c in cols} for s in order.samples],
                defaultColDef={"sortable": True, "filter": True, "resizable": True},
                style={"height": "400px", "width": "100%"},
                className="ag-theme-alpine"
            )
            
            return html.Div([
                create_project_summary_card(order, len(order.samples)),
                html.Hr(className="my-4"),
                html.H5("📋 해당 주문 시료 목록", className="fw-bold mb-3"),
                detail_table
            ])
        finally:
            db.close()



def create_project_view_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_project_view_layout)
    app = lims.get_app() 
    register_project_callbacks(app)
    return app