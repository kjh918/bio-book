from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from datetime import datetime
from sqlalchemy import desc

from app.core.database import SessionLocal
from app.models._schema import Sample, Order
from app.pages.base import LimsDashApp

from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from datetime import datetime
from sqlalchemy import desc, text  # 🚀 text 추가 필수!

from app.core.database import SessionLocal
from app.models._schema import Sample, Order
def get_initial_orders():
    """페이지 로드 시 즉시 Order(GCX) 목록을 렌더링"""
    db = SessionLocal()
    try:
        # 🚀 접수일(reception_date) 기준 최신순 정렬
        orders = db.query(Order).order_by(desc(Order.reception_date)).all()
        return [
            {
                "label": f"📦 {o.order_id} (샘플 {len(o.samples)}건)", 
                "value": o.order_id
            } for o in orders if o.order_id
        ]
    except Exception:
        return []
    finally:
        db.close()

def create_batch_modify_layout():
    initial_order_options = get_initial_orders()

    return html.Div([
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:calendar-tools", className="me-2 text-dark"), "Order & Date Modification"]),
                html.P("프로젝트(Order) 단위로 접수 일자를 변경하고, 새 일자에 맞는 GCX 및 ACC ID를 안전하게 재할당합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        dbc.Row([
            # 🚀 좌측: 설정 및 제어 패널
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🔄 변경 및 검증 설정", className="fw-bold mb-0"), className="bg-white border-0 pt-4 pb-0"),
                    dbc.CardBody([
                        # 🚀 1. Order 기준으로 완벽히 변경된 드롭다운
                        html.Label("1. 수정할 기존 오더 (Order) 선택", className="fw-bold small text-primary"),
                        dbc.Select(id="modify-source-order", options=initial_order_options, placeholder="오더 선택...", className="mb-4 shadow-sm rounded-3"),
                        
                        html.Label("2. 변경할 접수 일자", className="fw-bold small text-primary"),
                        dbc.Input(id="modify-target-date", type="date", className="mb-4 shadow-sm rounded-3"),
                        
                        html.Hr(className="my-3 text-muted"),
                        dbc.Button([DashIconify(icon="carbon:data-check", className="me-2"), "1차: ID 채번 및 검증"], 
                                   id="btn-preview-modify", color="info", outline=True, className="w-100 fw-bold mb-3 rounded-3 shadow-sm"),
                        
                        dbc.Button([DashIconify(icon="carbon:save", className="me-2"), "2차: 보드 내용 최종 저장"], 
                                   id="btn-apply-modify", color="danger", disabled=True, className="w-100 fw-bold rounded-3 shadow-sm"),
                        
                        html.Div(id="modify-status-message", className="mt-3 small text-center")
                    ])
                ], className="border-0 shadow-sm rounded-4 h-100")
            ], lg=3),

            # 🚀 우측: 데이터 검증 보드
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        html.Div([
                            html.H5("📋 일괄 수정 프로젝트 보드 (노란색 칸은 직접 수정 가능)", className="fw-bold mb-0 text-dark"),
                            dbc.Badge("대기중", id="validation-badge", color="secondary", className="ms-2 rounded-pill")
                        ], className="d-flex align-items-center"),
                        className="bg-white border-0 pt-4 pb-0"
                    ),
                    dbc.CardBody([
                        dag.AgGrid(
                            id="modify-preview-grid",
                            columnDefs=[
                                {"headerName": "검증 상태", "field": "validation_status", "width": 110, "pinned": "left",
                                 "cellStyle": {"styleConditions": [
                                     {"condition": "params.value == '✅ 정상'", "style": {"color": "#18bc9c", "fontWeight": "bold"}},
                                     {"condition": "params.value.includes('❌')", "style": {"color": "#dc3545", "fontWeight": "bold"}}
                                 ]}},
                                {"headerName": "기존 접수일", "field": "old_date", "width": 110, "pinned": "left"},
                                {"headerName": "🚀 변경 Order (GCX)", "field": "new_order_id", "width": 160, "pinned": "left", "cellStyle": {"backgroundColor": "#f0fdf4", "color": "#16a34a", "fontWeight": "bold"}},
                                {"headerName": "🚀 변경 Sample (ACC)", "field": "new_sample_id", "width": 180, "pinned": "left", "cellStyle": {"backgroundColor": "#f0fdf4", "color": "#16a34a", "fontWeight": "bold"}},
                                
                                {"headerName": "✏️ Patient ID (Name)", "field": "sample_name", "width": 160, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text", "border": "1px dashed #fbbf24"}},
                                {"headerName": "✏️ 검사 패널", "field": "target_panel", "width": 130, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                                {"headerName": "✏️ 암종(Cancer)", "field": "cancer_type", "width": 130, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                                {"headerName": "✏️ 검체(Specimen)", "field": "specimen", "width": 130, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                                {"headerName": "✏️ 프로젝트명", "field": "project_name", "width": 130, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                                {"headerName": "✏️ 페어링 정보", "field": "pairing_info", "width": 130, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                                {"headerName": "✏️ 외부 ID", "field": "outside_id_1", "width": 130, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                                {"headerName": "✏️ 이슈 코멘트", "field": "issue_comment", "width": 250, "editable": True, "cellStyle": {"backgroundColor": "#fffbeb", "cursor": "text"}},
                            ],
                            rowData=[],
                            defaultColDef={"sortable": True, "filter": True, "resizable": True},
                            dashGridOptions={"stopEditingWhenCellsLoseFocus": True},
                            style={"height": "500px", "width": "100%"},
                            className="ag-theme-alpine border-0 shadow-sm rounded-3"
                        )
                    ])
                ], className="border-0 shadow-sm rounded-4 h-100")
            ], lg=9)
        ], className="g-4")
    ], className="pb-5", style={"padding": "20px"})


def register_batch_modify_callbacks(dash_app):
    
    # 1. 미리보기: 선택된 '단일 Order'를 기반으로 새 ID 채번
    @dash_app.callback(
        [Output("modify-preview-grid", "rowData", allow_duplicate=True),
         Output("btn-apply-modify", "disabled", allow_duplicate=True),
         Output("validation-badge", "children"), Output("validation-badge", "color"),
         Output("modify-status-message", "children", allow_duplicate=True)],
        Input("btn-preview-modify", "n_clicks"),
        [State("modify-source-order", "value"), State("modify-target-date", "value")],
        prevent_initial_call=True
    )
    def preview_changes(n_clicks, old_order_id, target_date):
        if not old_order_id or not target_date:
            return [], True, "입력 누락", "warning", dbc.Alert("수정할 오더(Order)와 변경할 날짜를 모두 선택해주세요.", color="warning")

        db = SessionLocal()
        try:
            # 🚀 정확히 선택된 하나의 Order만 가져옵니다
            old_order = db.query(Order).filter(Order.order_id == old_order_id).first()
            if not old_order or not old_order.samples:
                return [], True, "데이터 없음", "danger", dbc.Alert("해당 오더에 속한 샘플이 없습니다.", color="danger")

            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            new_today_str = date_obj.strftime("%y%m%d")

            # 기존 GCX ID에서 기관코드 추출 (예: GCX-C12-260610-01 -> 'C12')
            parts = old_order_id.split('-')
            facility_code = parts[1] if len(parts) >= 2 else "00"

            # 해당 날짜의 총 오더 수 기반으로 새 배치 시퀀스 계산
            total_orders_today = db.query(Order).filter(Order.order_id.like(f"%{new_today_str}%")).count()
            batch_seq_str = str(total_orders_today + 1).zfill(2)

            new_order_id = f"GCX-{facility_code}-{new_today_str}-{batch_seq_str}"

            if db.query(Order).filter(Order.order_id == new_order_id).first():
                return [], True, "Order 충돌", "danger", dbc.Alert(f"생성될 Order ID({new_order_id})가 이미 존재합니다.", color="danger")

            preview_data = []
            has_error = False
            
            # 🚀 해당 Order 안의 샘플들만 루프 돌며 ID 재할당
            for idx, s in enumerate(old_order.samples):
                sample_seq = str(idx + 1).zfill(3)
                new_sample_id = f"ACC-{new_today_str}-{batch_seq_str}-{sample_seq}"
                
                is_dup = db.query(Sample).filter(Sample.sample_id == new_sample_id).first()
                status = "✅ 정상"
                if is_dup:
                    status = "❌ 충돌"
                    has_error = True

                preview_data.append({
                    "validation_status": status,
                    "old_order_id": old_order_id,
                    "old_sample_id": s.sample_id,
                    "old_date": str(old_order.reception_date)[:10] if old_order.reception_date else "-",
                    "new_order_id": new_order_id,
                    "new_sample_id": new_sample_id,
                    "new_date": target_date,
                    "sample_name": s.sample_name, 
                    "target_panel": s.target_panel,
                    "cancer_type": getattr(s, "cancer_type", ""),
                    "specimen": getattr(s, "specimen", ""),
                    "project_name": getattr(s, "project_name", ""),
                    "pairing_info": getattr(s, "pairing_info", ""),
                    "outside_id_1": getattr(s, "outside_id_1", ""),
                    "issue_comment": getattr(s, "issue_comment", "") or ""
                })

            if has_error:
                return preview_data, True, "충돌 발생", "danger", dbc.Alert("새로운 ACC ID가 기존 ID와 중복됩니다.", color="danger")
            
            return preview_data, False, "검증 완료", "success", dbc.Alert(f"새로운 오더({new_order_id}) 생성 준비 완료. 정보를 수정하고 저장하세요.", color="success")

        except Exception as e:
            return [], True, "오류", "danger", dbc.Alert(f"미리보기 오류: {str(e)}", color="danger")
        finally:
            db.close()

    # 2. 최종 DB 반영 후 UI 초기화 및 드롭다운 목록 새로고침
    @dash_app.callback(
        [Output("modify-status-message", "children", allow_duplicate=True),
         Output("modify-source-order", "options"), 
         Output("modify-source-order", "value"),   
         Output("modify-preview-grid", "rowData", allow_duplicate=True), 
         Output("btn-apply-modify", "disabled", allow_duplicate=True)], 
        Input("btn-apply-modify", "n_clicks"),
        [State("modify-preview-grid", "rowData"), State("modify-target-date", "value")],
        prevent_initial_call=True
    )
    def apply_changes(n_clicks, row_data, target_date):
        if not row_data: 
            return no_update, no_update, no_update, no_update, no_update
        
        db = SessionLocal()
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")

            # 🚀 단일 Order 복제 및 데이터 갱신
            old_order_id = row_data[0]["old_order_id"]
            new_order_id = row_data[0]["new_order_id"]
            
            old_order = db.query(Order).filter(Order.order_id == old_order_id).first()
            if not old_order: raise ValueError("기존 오더를 찾을 수 없습니다.")
            
            new_order = Order(
                order_id=new_order_id,
                reception_date=date_obj,
                facility=old_order.facility,
                client_team=old_order.client_team,
                client_name=getattr(old_order, 'client_name', None),
                client_email=getattr(old_order, 'client_email', None),
                client_phone=getattr(old_order, 'client_phone', None),
                sales_unit_price=getattr(old_order, 'sales_unit_price', 0)
            )
            db.add(new_order)
            db.flush() 

            for row in row_data:
                sample = db.query(Sample).filter(Sample.sample_id == row["old_sample_id"]).first()
                if sample:
                    if sample in old_order.samples:
                        old_order.samples.remove(sample)
                    new_order.samples.append(sample)

                    db.execute(
                        text("UPDATE action_logs SET sample_id = :new_id WHERE sample_id = :old_id"),
                        {"new_id": row["new_sample_id"], "old_id": row["old_sample_id"]}
                    )

                    sample.order_pk = new_order.id
                    sample.order_id = new_order_id
                    sample.sample_id = row["new_sample_id"]
                    
                    sample.sample_name = row.get("sample_name")
                    sample.target_panel = row.get("target_panel")
                    if hasattr(sample, 'cancer_type'): sample.cancer_type = row.get("cancer_type")
                    if hasattr(sample, 'specimen'): sample.specimen = row.get("specimen")
                    if hasattr(sample, 'project_name'): sample.project_name = row.get("project_name")
                    if hasattr(sample, 'pairing_info'): sample.pairing_info = row.get("pairing_info")
                    if hasattr(sample, 'outside_id_1'): sample.outside_id_1 = row.get("outside_id_1")
                    
                    old_date = row.get("old_date")
                    system_memo = f"[시스템] 오더/접수일 변경: {old_date} -> {target_date} (이전 ID: {row['old_sample_id']})"
                    user_comment = row.get("issue_comment", "")
                    user_comment = user_comment.strip() if user_comment else ""
                    
                    if user_comment:
                        if system_memo not in user_comment:
                            sample.issue_comment = f"{user_comment}\n{system_memo}"
                        else:
                            sample.issue_comment = user_comment
                    else:
                        sample.issue_comment = system_memo
            
            db.delete(old_order)
            db.commit()

            # 저장 완료 후 최신 오더 목록 다시 로드
            new_orders = db.query(Order).order_by(desc(Order.reception_date)).all()
            new_options = [
                {"label": f"📦 {o.order_id} (샘플 {len(o.samples)}건)", "value": o.order_id} 
                for o in new_orders if o.order_id
            ]

            return (
                dbc.Alert("✅ 성공적으로 오더 변경 및 저장이 완료되었습니다!", color="success"),
                new_options,
                None, 
                [], 
                True
            )
            
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"❌ DB 저장 실패: {str(e)}", color="danger"), no_update, no_update, no_update, no_update
        finally:
            db.close()

def create_batch_modify_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_batch_modify_layout)
    app = lims.get_app() 
    register_batch_modify_callbacks(app)
    return app