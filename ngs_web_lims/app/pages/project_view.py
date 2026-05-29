from dash import html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from app.core.database import SessionLocal
from app.models._schema import Order, Sample
from app.pages.base import LimsDashApp
from app.ui.shared_ui import create_project_summary_card # 기존 카드 생성 함수 활용
from dash_iconify import DashIconify

def create_project_view_layout():
    return html.Div([
        # 🚀 1. 모던 페이지 헤더
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:folder-open", className="me-2 text-dark"), "Project View"]),
                #html.P("의뢰된 프로젝트의 목록을 조회하고 개별 샘플 상세 상태를 확인합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header"),
        
        # 🚀 2. 프로젝트 리스트와 상세 정보 영역 (플로팅 카드 레이아웃)
        dbc.Row([
            # 좌측: 주문 목록 카드
            dbc.Col([
                html.Div([
                    html.H5([DashIconify(icon="carbon:list", className="me-2"), "주문 목록"], className="fw-bold mb-3 text-dark"),
                    dag.AgGrid(
                        id='project-list-grid',
                        columnDefs=[
                            {"headerName": "접수일", "field": "reception_date", "width": 110},
                            {"headerName": "Order ID", "field": "order_id", "width": 150},
                            {"headerName": "수량", "field": "sample_count", "width": 70}
                        ],
                        rowData=[],
                        defaultColDef={"sortable": True, "filter": True, "resizable": True},
                        dashGridOptions={
                            "rowSelection": "single",
                            "rowHeight": 40
                        },
                        style={"height": "600px", "width": "100%"},
                        className="ag-theme-alpine border-0 shadow-sm rounded-3"
                    )
                ], className="p-4 bg-white border border-light rounded-4 shadow-sm h-100")
            ], width=4),

            # 우측: 상세 정보 뷰
            dbc.Col([
                html.Div(id='project-detail-container', children=[
                    html.Div([
                        DashIconify(icon="carbon:cursor-1", width=50, className="text-muted mb-3"),
                        html.Div("좌측 목록에서 프로젝트를 선택하시면 상세 정보가 표시됩니다.", className="text-muted fs-6")
                    ], className="d-flex flex-column align-items-center justify-content-center text-center", style={"height": "600px"})
                ], className="p-4 bg-white border border-light rounded-4 shadow-sm h-100")
            ], width=8),
        ], className="g-4")
    ], className="pb-4")

def register_project_callbacks(dash_app):
    @dash_app.callback(
        Output('project-list-grid', 'rowData'),
        Input('project-list-grid', 'id')
    )
    def load_order_list(_):
        db = SessionLocal()
        try:
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

    @dash_app.callback(
        Output('project-detail-container', 'children'),
        Input('project-list-grid', 'selectedRows')
    )
    def display_project_details(selected_rows):
        if not selected_rows:
            return html.Div([
                DashIconify(icon="carbon:cursor-1", width=50, className="text-muted mb-3"),
                html.Div("좌측 목록에서 프로젝트를 선택하시면 상세 정보가 표시됩니다.", className="text-muted fs-6")
            ], className="d-flex flex-column align-items-center justify-content-center text-center", style={"height": "600px"})

        selected_row = selected_rows[0]
        order_id = selected_row.get("order_id")

        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if not order: return html.Div("데이터를 찾을 수 없습니다.")

            cols = ["sample_id", "sample_name", "target_panel", "current_status", "issue_comment"]
            
            detail_table = dag.AgGrid(
                columnDefs=[{"headerName": c.replace("_", " ").title(), "field": c} for c in cols],
                rowData=[{c: getattr(s, c, "") for c in cols} for s in order.samples],
                defaultColDef={"sortable": True, "filter": True, "resizable": True},
                style={"height": "350px", "width": "100%"},
                className="ag-theme-alpine border-0 shadow-sm rounded-3"
            )
            
            return html.Div([
                create_project_summary_card(order, len(order.samples)),
                html.Div([
                    html.H5([DashIconify(icon="carbon:data-table", className="me-2"), "샘플 상세 목록"], className="fw-bold mb-3"),
                    detail_table
                ], className="mt-4")
            ])
        finally:
            db.close()

def create_project_view_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_project_view_layout)
    app = lims.get_app() 
    register_project_callbacks(app)
    return app