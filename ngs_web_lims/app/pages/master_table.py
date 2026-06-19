from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from datetime import datetime
from sqlalchemy import desc

from app.core.database import SessionLocal
from app.models._schema import Sample, Order
from app.pages.base import LimsDashApp

# 🚀 [고정 컬럼 설정] LimsDashApp 표준 구조 계승 및 행 고정(Left Pinning)
base_columns = LimsDashApp.get_base_grid_columns(include_project=True)
for col in base_columns:
    if col["field"] in ["project_name", "sample_name", "target_panel"]:
        col["editable"] = True
        col["cellStyle"] = {"backgroundColor": "#fffbeb", "cursor": "text"} # 직접 수정 가능 (연노랑)
    else:
        col["editable"] = False # order_id, sample_id는 관계 무결성을 위해 편집 제한

# 🚀 [확장 컬럼 설정] Order 정보 및 모든 실험/정산 데이터 메타 필드
extended_columns = [
    {"headerName": "현재 상태 🚦", "field": "current_status", "presentation": "dropdown", "options": ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"]},
    
    # 🚀 [Order (의뢰 및 정산) 정보 추가]
    {"headerName": "의뢰 기관", "field": "facility", "width": 140},
    {"headerName": "소속 팀", "field": "client_team", "width": 120},
    {"headerName": "의뢰자 성명", "field": "client_name", "width": 120},
    {"headerName": "연락처", "field": "client_phone", "width": 140},
    {"headerName": "이메일", "field": "client_email", "width": 180},
    {"headerName": "매출 단가", "field": "sales_unit_price", "type": "numeric", "width": 120},

    # 🚀 [입고 및 기본 정보]
    {"headerName": "입고 확인", "field": "sample_received", "presentation": "dropdown", "options": ["대기중", "입고 완료"]},
    {"headerName": "입고 담당자", "field": "receiver_name"},
    {"headerName": "보관 위치", "field": "storage_location"},
    {"headerName": "암종(Cancer)", "field": "cancer_type"},
    {"headerName": "검체(Specimen)", "field": "specimen"},
    {"headerName": "페어링 정보", "field": "pairing_info"},
    {"headerName": "외부 ID", "field": "outside_id_1"},
    
    # 🚀 [DNA QC 메트릭]
    {"headerName": "DNA QC 결과", "field": "dna_qc", "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
    {"headerName": "DNA 농도(ng/uL)", "field": "dna_concentration", "type": "numeric"},
    {"headerName": "DNA 순도(260/280)", "field": "purity", "type": "numeric"},
    {"headerName": "DNA 용량(uL)", "field": "dna_volume", "type": "numeric"},
    {"headerName": "DNA 총량(μg)", "field": "dna_total_amount", "type": "numeric"},
    {"headerName": "DIN", "field": "din", "type": "numeric"},
    
    # 🚀 [RNA QC 메트릭]
    {"headerName": "RNA QC 결과", "field": "rna_qc", "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
    {"headerName": "RNA 농도(ng/uL)", "field": "rna_concentration", "type": "numeric"},
    {"headerName": "RNA 용량(uL)", "field": "rna_volume", "type": "numeric"},
    {"headerName": "RNA 총량(μg)", "field": "rna_total_amount", "type": "numeric"},
    {"headerName": "DV200 (%)", "field": "dv200", "type": "numeric"},
    {"headerName": "RIN", "field": "rin", "type": "numeric"},
    
    # 🚀 [시퀀싱 정보]
    {"headerName": "SEQ ID", "field": "seq_id"},
    {"headerName": "Depth/Output", "field": "depth_output"},
    {"headerName": "이슈 코멘트 💬", "field": "issue_comment", "width": 250}
]

# 확장 컬럼들도 편집 가능하도록 세팅 (배경색 적용 안 함, 일반 흰색 입력칸)
for col in extended_columns:
    col["editable"] = True

# 체크박스 다중 선택 기능을 첫 번째 고정 열인 'Project'에 추가합니다.
if base_columns:
    base_columns[0]["checkboxSelection"] = True
    base_columns[0]["headerCheckboxSelection"] = True
    base_columns[0]["width"] = 200

# 최종 컬럼 정의 리스트 통합
MASTER_COLUMN_DEFS = base_columns + extended_columns


def create_master_table_layout():
    return html.Div([
        # 데이터 리프레시용 내부 저장소 (Store)
        dcc.Store(id="master-table-refresh-trigger", data=0),

        # 페이지 헤더
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:table-split", className="me-2 text-dark"), "Master Data Management Board"]),
                html.P("LIMS 시스템의 전역 데이터를 조회하고, 엑셀처럼 일괄 수정하거나 선택한 데이터를 영구 삭제합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        # 상단 제어 바 (검색, 삭제, 저장 버튼)
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # 전역 통합 검색 엔진
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText(DashIconify(icon="carbon:search")),
                            dbc.Input(id="master-table-search", placeholder="Order ID, Sample ID, Patient ID, 기관 등 통합 검색...", className="rounded-end-3")
                        ], className="shadow-sm")
                    ], lg=4),
                    
                    # 실시간 팁
                    dbc.Col([
                        html.Div([
                            html.Span("💡 열 헤더의 필터 마크(≡)를 누르면 엑셀처럼 상세 필터링도 가능합니다.", className="text-muted small d-block")
                        ])
                    ], lg=4),
                    
                    # 데이터 액션 버튼 레이아웃
                    dbc.Col([
                        dbc.Row([
                            dbc.Col([
                                dbc.Button([DashIconify(icon="carbon:trash-can", className="me-2"), "선택 삭제"], 
                                           id="btn-delete-master-table", color="danger", outline=True, className="fw-bold shadow-sm w-100 rounded-3 py-2")
                            ], width=6, className="pe-1"),
                            dbc.Col([
                                dbc.Button([DashIconify(icon="carbon:save", className="me-2"), "💾 최종 저장"], 
                                           id="btn-save-master-table", color="primary", className="fw-bold shadow-sm w-100 rounded-3 py-2")
                            ], width=6, className="ps-1")
                        ])
                    ], lg=4)
                ], className="align-items-center"),
                html.Div(id="master-table-status-message", className="mt-3")
            ], className="py-3")
        ], className="border-0 shadow-sm rounded-4 mb-4"),

        # 영구 삭제 확인 알림 팝업 (안전장치)
        dcc.ConfirmDialog(
            id='confirm-delete-dialog',
            message='⚠️ 정말 선택한 샘플 데이터를 삭제하시겠습니까?\n\n연결된 모든 메타데이터(QC, 시퀀싱, 로그 등)가 영구적으로 삭제되며 절대 되돌릴 수 없습니다.'
        ),

        # 메인 마스터 그리드
        dbc.Card([
            dbc.CardBody([
                dag.AgGrid(
                    id="master-master-grid",
                    columnDefs=MASTER_COLUMN_DEFS,
                    rowData=[],  
                    defaultColDef={"sortable": True, "filter": True, "resizable": True},
                    dashGridOptions={
                        "rowSelection": "multiple",          
                        "suppressRowClickSelection": True,   
                    },
                    style={"height": "70vh", "width": "100%"},
                    className="ag-theme-alpine border-0"
                )
            ], className="p-0 rounded-4 overflow-hidden")
        ], className="border-0 shadow-sm rounded-4")
    ], className="pb-5", style={"padding": "20px"})


def register_master_table_callbacks(dash_app):

    # 🚀 [콜백 1] 데이터 실시간 로딩 (Order 데이터 포함)
    @dash_app.callback(
        Output("master-master-grid", "rowData"),
        [Input("master-table-search", "value"),
         Input("master-table-refresh-trigger", "data")]
    )
    def update_grid_rows(search_value, refresh_count):
        db = SessionLocal()
        try:
            query = db.query(Sample).order_by(desc(Sample.created_at))
            samples = query.all()
            
            kw = (search_value or "").strip().lower()
            data = []
            
            for s in samples:
                if kw and not any([
                    kw in (s.order_id or "").lower(),
                    kw in (s.sample_id or "").lower(),
                    kw in (s.sample_name or "").lower(),
                    kw in (s.project_name or "").lower(),
                    kw in (s.order.facility or "").lower() if s.order else False,
                    kw in (s.order.client_name or "").lower() if s.order else False
                ]):
                    continue

                row = {
                    "id": s.id, 
                    "project_name": s.project_name,
                    "order_id": s.order_id,
                    "sample_id": s.sample_id,
                    "sample_name": s.sample_name,
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    
                    # 🚀 Order(의뢰) 데이터 연동
                    "facility": s.order.facility if s.order else "-",
                    "client_team": s.order.client_team if s.order else "-",
                    "client_name": s.order.client_name if s.order else "-",
                    "client_phone": s.order.client_phone if s.order else "-",
                    "client_email": s.order.client_email if s.order else "-",
                    "sales_unit_price": s.order.sales_unit_price if s.order else 0,

                    "sample_received": s.sample_received,
                    "receiver_name": s.receiver_name,
                    "storage_location": s.storage_location,
                    "cancer_type": s.cancer_type,
                    "specimen": s.specimen,
                    "pairing_info": s.pairing_info,
                    "outside_id_1": s.outside_id_1,
                    "issue_comment": s.issue_comment or "",
                    
                    "dna_qc": s.wet_lab.dna_qc if s.wet_lab else "PENDING",
                    "dna_concentration": s.wet_lab.dna_concentration if s.wet_lab and s.wet_lab.dna_concentration is not None else "",
                    "purity": s.wet_lab.purity if s.wet_lab and s.wet_lab.purity is not None else "",
                    "dna_volume": s.wet_lab.dna_volume if s.wet_lab and s.wet_lab.dna_volume is not None else "",
                    "dna_total_amount": s.wet_lab.dna_total_amount if s.wet_lab and s.wet_lab.dna_total_amount is not None else "",
                    "din": s.wet_lab.din if s.wet_lab and s.wet_lab.din is not None else "",
                    
                    "rna_qc": s.wet_lab.rna_qc if s.wet_lab else "PENDING",
                    "rna_concentration": s.wet_lab.rna_concentration if s.wet_lab and s.wet_lab.rna_concentration is not None else "",
                    "rna_volume": s.wet_lab.rna_volume if s.wet_lab and s.wet_lab.rna_volume is not None else "",
                    "rna_total_amount": s.wet_lab.rna_total_amount if s.wet_lab and s.wet_lab.rna_total_amount is not None else "",
                    "dv200": s.wet_lab.dv200 if s.wet_lab and s.wet_lab.dv200 is not None else "",
                    "rin": s.wet_lab.rin if s.wet_lab and s.wet_lab.rin is not None else "",
                    
                    "seq_id": s.sequencing.seq_id if s.sequencing else "",
                    "depth_output": s.sequencing.depth_output if s.sequencing else ""
                }
                data.append(row)
            return data
        finally:
            db.close()

    # 🚀 [콜백 2] DB 일괄 저장 (Order 데이터 포함)
    @dash_app.callback(
        Output("master-table-status-message", "children", allow_duplicate=True),
        Input("btn-save-master-table", "n_clicks"),
        State("master-master-grid", "rowData"),
        prevent_initial_call=True
    )
    def save_master_table_data(n_clicks, row_data):
        if not row_data: return no_update

        db = SessionLocal()
        try:
            for row in row_data:
                sample = db.query(Sample).filter(Sample.id == row.get("id")).first()
                if sample:
                    # Sample 정보 업데이트
                    sample.project_name = row.get("project_name")
                    sample.sample_name = row.get("sample_name")
                    sample.target_panel = row.get("target_panel")
                    sample.current_status = row.get("current_status")
                    sample.sample_received = row.get("sample_received")
                    sample.receiver_name = row.get("receiver_name")
                    sample.storage_location = row.get("storage_location")
                    sample.cancer_type = row.get("cancer_type")
                    sample.specimen = row.get("specimen")
                    sample.pairing_info = row.get("pairing_info")
                    sample.outside_id_1 = row.get("outside_id_1")
                    sample.issue_comment = row.get("issue_comment")

                    # 🚀 Order 정보 동기화 업데이트
                    if sample.order:
                        sample.order.facility = row.get("facility")
                        sample.order.client_team = row.get("client_team")
                        sample.order.client_name = row.get("client_name")
                        sample.order.client_phone = row.get("client_phone")
                        sample.order.client_email = row.get("client_email")
                        sample.order.sales_unit_price = float(row.get("sales_unit_price")) if row.get("sales_unit_price") not in ["", None] else 0

                    if sample.wet_lab:
                        sample.wet_lab.dna_qc = row.get("dna_qc")
                        sample.wet_lab.dna_concentration = float(row["dna_concentration"]) if row.get("dna_concentration") not in ["", None] else None
                        sample.wet_lab.purity = float(row["purity"]) if row.get("purity") not in ["", None] else None
                        sample.wet_lab.dna_volume = float(row["dna_volume"]) if row.get("dna_volume") not in ["", None] else None
                        sample.wet_lab.dna_total_amount = float(row["dna_total_amount"]) if row.get("dna_total_amount") not in ["", None] else None
                        sample.wet_lab.din = float(row["din"]) if row.get("din") not in ["", None] else None
                        
                        sample.wet_lab.rna_qc = row.get("rna_qc")
                        sample.wet_lab.rna_concentration = float(row["rna_concentration"]) if row.get("rna_concentration") not in ["", None] else None
                        sample.wet_lab.rna_volume = float(row["rna_volume"]) if row.get("rna_volume") not in ["", None] else None
                        sample.wet_lab.rna_total_amount = float(row["rna_total_amount"]) if row.get("rna_total_amount") not in ["", None] else None
                        sample.wet_lab.dv200 = float(row["dv200"]) if row.get("dv200") not in ["", None] else None
                        sample.wet_lab.rin = float(row["rin"]) if row.get("rin") not in ["", None] else None

                    if sample.sequencing:
                        sample.sequencing.seq_id = row.get("seq_id")
                        sample.sequencing.depth_output = row.get("depth_output")

            db.commit()
            return dbc.Alert("🎉 전역 보드의 모든 수정사항이 데이터베이스에 실시간 반영되었습니다!", color="success", className="shadow-sm rounded-3")
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"❌ 데이터 저장 실패: {str(e)}", color="danger", className="shadow-sm rounded-3")
        finally:
            db.close()


    # 🚀 [콜백 3] 삭제 버튼 작동 시 안전 팝업
    @dash_app.callback(
        Output('confirm-delete-dialog', 'displayed'),
        Input('btn-delete-master-table', 'n_clicks'),
        State('master-master-grid', 'selectedRows'),
        prevent_initial_call=True
    )
    def display_confirm(n_clicks, selected_rows):
        if n_clicks and selected_rows:
            return True
        return False


    # 🚀 [콜백 4] 안전 팝업 확인 시 삭제 로직
    @dash_app.callback(
        [Output("master-table-status-message", "children", allow_duplicate=True),
         Output("master-table-refresh-trigger", "data")],
        Input('confirm-delete-dialog', 'submit_n_clicks'),
        [State('master-master-grid', 'selectedRows'), State("master-table-refresh-trigger", "data")],
        prevent_initial_call=True
    )
    def execute_delete(submit_n_clicks, selected_rows, current_refresh):
        if not submit_n_clicks or not selected_rows:
            return no_update, no_update
        
        db = SessionLocal()
        try:
            orders_to_check = set()
            deleted_count = 0
            
            for row in selected_rows:
                sample = db.query(Sample).filter(Sample.id == row.get("id")).first()
                if sample:
                    if sample.order:
                        orders_to_check.add(sample.order)
                    
                    if sample.wet_lab: db.delete(sample.wet_lab)
                    if sample.sequencing: db.delete(sample.sequencing)
                    if sample.analysis: db.delete(sample.analysis)
                    if sample.logs:
                        for log in sample.logs: db.delete(log)
                    
                    db.delete(sample)
                    deleted_count += 1
            
            db.flush()
            
            for order in orders_to_check:
                if order and not order.samples:
                    db.delete(order)

            db.commit()
            
            return dbc.Alert(f"🗑️ 총 {deleted_count}건의 샘플 및 연관 로그들이 데이터베이스에서 안전하게 제거되었습니다.", color="success"), current_refresh + 1
            
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"❌ 데이터 삭제 오류: {str(e)}", color="danger"), no_update
        finally:
            db.close()
            
def create_master_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_master_table_layout)
    app = lims.get_app()
    register_master_table_callbacks(app)
    return app