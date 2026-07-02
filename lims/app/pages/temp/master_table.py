from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from datetime import datetime
from sqlalchemy import desc

from app.core.database import SessionLocal
# 🚀 필수 모델들 및 스키마 설정(STAGE_SCHEMA_CONFIG) 불러오기
from app.models._schema import Sample, Order, WetLabQC, Sequencing, Analysis, ActionLog, STAGE_SCHEMA_CONFIG
from sqlalchemy.orm.attributes import flag_modified
from app.pages.base import LimsDashApp

# =========================================================
# 🚀 1. 동적 컬럼 자동 생성 (Dynamic Column Generation)
# =========================================================

# [A] 기본 고정 컬럼 (프로젝트 및 샘플 식별자)
base_columns = LimsDashApp.get_base_grid_columns(include_project=True)
for col in base_columns:
    if col["field"] in ["project_name", "sample_name", "target_panel"]:
        col["editable"] = True
        col["cellStyle"] = {"backgroundColor": "#fffbeb", "cursor": "text"} # 직접 수정 가능 (연노랑)
    else:
        col["editable"] = False 

# 체크박스 다중 선택 기능을 첫 번째 고정 열에 추가
if base_columns:
    base_columns[0]["checkboxSelection"] = True
    base_columns[0]["headerCheckboxSelection"] = True
    base_columns[0]["width"] = 200

# [B] 수동 확장 컬럼 (상태 및 Order 전용)
order_columns = [
    {"headerName": "현재 상태 🚦", "field": "current_status", "editable": True, "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"]}},
    {"headerName": "의뢰 기관", "field": "facility", "width": 140, "editable": True},
    {"headerName": "소속 팀", "field": "client_team", "width": 120, "editable": True},
    {"headerName": "의뢰자 성명", "field": "client_name", "width": 120, "editable": True},
    {"headerName": "연락처", "field": "client_phone", "width": 140, "editable": True},
    {"headerName": "이메일", "field": "client_email", "width": 180, "editable": True},
]

# [C] 🌟 STAGE_SCHEMA_CONFIG 에서 동적 컬럼 긁어오기
dynamic_columns = []
DYNAMIC_FIELD_IDS = [] # 데이터 매핑에 사용할 ID 리스트
FIELD_TYPES = {}       # 저장 시 형변환(float 등)을 위한 타입 저장소

for stage, config in STAGE_SCHEMA_CONFIG.items():
    for col in config["columns"]:
        col_id = col["id"]
        
        # 중복 방지
        if col_id in DYNAMIC_FIELD_IDS: continue
        
        DYNAMIC_FIELD_IDS.append(col_id)
        FIELD_TYPES[col_id] = col.get("type", "text")
        
        ag_col = {
            "headerName": col["name"],
            "field": col_id,
            "editable": col.get("editable", True),
            "width": 130
        }
        
        if col.get("type") == "numeric":
            ag_col["filter"] = "agNumberColumnFilter"
        
        if col.get("presentation") == "dropdown":
            ag_col["cellEditor"] = "agSelectCellEditor"
            if "options" in col:
                ag_col["cellEditorParams"] = {"values": col["options"]}
                
        dynamic_columns.append(ag_col)

# 최종 마스터 컬럼 통합
MASTER_COLUMN_DEFS = base_columns + order_columns + dynamic_columns


# =========================================================
# 🚀 2. 레이아웃
# =========================================================
def create_master_table_layout():
    return html.Div([
        dcc.Store(id="master-table-refresh-trigger", data=0),

        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:table-split", className="me-2 text-dark"), "Master Data Management Board"]),
                html.P("LIMS 시스템의 전역 데이터를 조회하고, 엑셀처럼 일괄 수정하거나 선택한 데이터를 영구 삭제합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText(DashIconify(icon="carbon:search")),
                            dbc.Input(id="master-table-search", placeholder="Order ID, Sample ID, Patient ID, 기관 등 통합 검색...", className="rounded-end-3")
                        ], className="shadow-sm")
                    ], lg=4),
                    
                    dbc.Col([
                        html.Div([
                            html.Span("💡 열 헤더의 필터 마크(≡)를 누르면 엑셀처럼 상세 필터링도 가능합니다.", className="text-muted small d-block")
                        ])
                    ], lg=4),
                    
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

        dcc.ConfirmDialog(
            id='confirm-delete-dialog',
            message='⚠️ 정말 선택한 샘플 데이터를 삭제하시겠습니까?\n\n연결된 모든 메타데이터(QC, 시퀀싱, 로그 등)가 영구적으로 삭제되며 절대 되돌릴 수 없습니다.'
        ),

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


# =========================================================
# 🚀 3. 콜백 (동적 데이터 매핑 및 저장)
# =========================================================
def register_master_table_callbacks(dash_app):

    # 🚀 [콜백 1] 데이터 동적 로딩
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

                # 기본 데이터 세팅
                row = {
                    "id": s.id, 
                    "project_name": s.project_name,
                    "order_id": s.order_id,
                    "sample_id": s.sample_id,
                    "sample_name": s.sample_name,
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    "facility": s.order.facility if s.order else "-",
                    "client_team": s.order.client_team if s.order else "-",
                    "client_name": s.order.client_name if s.order else "-",
                    "client_phone": s.order.client_phone if s.order else "-",
                    "client_email": s.order.client_email if s.order else "-",
                }
                
                # 🌟 동적 컬럼(STAGE_SCHEMA_CONFIG) 자동 추출 로직
                for col_id in DYNAMIC_FIELD_IDS:
                    val = None
                    # 각 DB 모델을 순회하며 값이 있는지 탐색
                    if hasattr(s, col_id): val = getattr(s, col_id)
                    elif s.order and hasattr(s.order, col_id): val = getattr(s.order, col_id)
                    elif s.wet_lab and hasattr(s.wet_lab, col_id): val = getattr(s.wet_lab, col_id)
                    elif s.sequencing and hasattr(s.sequencing, col_id): val = getattr(s.sequencing, col_id)
                    elif s.analysis and hasattr(s.analysis, col_id): val = getattr(s.analysis, col_id)
                    
                    # 그래도 없으면 JSON 메타데이터에서 탐색
                    if val is None and s.panel_metadata:
                        val = s.panel_metadata.get(col_id, "")
                        
                    row[col_id] = val if val is not None else ""

                data.append(row)
            return data
        finally:
            db.close()

    # 🚀 [콜백 2] DB 일괄 저장 (스마트 라우팅 및 타입 자동 변환)
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
                if not sample: continue

                # 1. 고정 정보 업데이트
                sample.project_name = row.get("project_name")
                sample.sample_name = row.get("sample_name")
                sample.target_panel = row.get("target_panel")
                sample.current_status = row.get("current_status")

                if sample.order:
                    sample.order.facility = row.get("facility")
                    sample.order.client_team = row.get("client_team")
                    sample.order.client_name = row.get("client_name")
                    sample.order.client_phone = row.get("client_phone")
                    sample.order.client_email = row.get("client_email")

                # 2. 껍데기 자동 생성 (Lazy Initialization)
                if not sample.wet_lab:
                    sample.wet_lab = WetLabQC(sample_id=sample.id)
                    db.add(sample.wet_lab)
                if not sample.sequencing:
                    sample.sequencing = Sequencing(sample_id=sample.id)
                    db.add(sample.sequencing)
                if not sample.analysis:
                    sample.analysis = Analysis(sample_id=sample.id)
                    db.add(sample.analysis)

                # 3. 🌟 동적 데이터 자동 배달 로직
                new_meta = dict(sample.panel_metadata) if sample.panel_metadata else {}
                has_meta_change = False

                for col_id in DYNAMIC_FIELD_IDS:
                    if col_id not in row: continue
                    
                    val = row[col_id]
                    if val == "": val = None
                    
                    # 숫자형으로 지정된 경우 float 변환 방어코드
                    if val is not None and FIELD_TYPES.get(col_id) == "numeric":
                        try: val = float(val)
                        except ValueError: val = None

                    # 알아서 제 위치 찾아가기
                    if hasattr(Sample, col_id) and col_id != "panel_metadata":
                        setattr(sample, col_id, val)
                    elif hasattr(Order, col_id) and sample.order:
                        setattr(sample.order, col_id, val)
                    elif hasattr(WetLabQC, col_id):
                        setattr(sample.wet_lab, col_id, val)
                    elif hasattr(Sequencing, col_id):
                        setattr(sample.sequencing, col_id, val)
                    elif hasattr(Analysis, col_id) and col_id not in ["analysis_results", "analysis_metadata"]:
                        setattr(sample.analysis, col_id, val)
                    else:
                        if new_meta.get(col_id) != val:
                            new_meta[col_id] = val
                            has_meta_change = True

                if has_meta_change:
                    sample.panel_metadata = new_meta
                    flag_modified(sample, "panel_metadata")

            db.commit()
            return dbc.Alert("🎉 전역 보드의 모든 수정사항이 데이터베이스에 완벽히 반영되었습니다!", color="success", className="shadow-sm rounded-3")
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"❌ 데이터 저장 실패: {str(e)}", color="danger", className="shadow-sm rounded-3")
        finally:
            db.close()


    # 🚀 [콜백 3, 4] 영구 삭제 로직 (기존 코드 유지)
    @dash_app.callback(
        Output('confirm-delete-dialog', 'displayed'),
        Input('btn-delete-master-table', 'n_clicks'),
        State('master-master-grid', 'selectedRows'),
        prevent_initial_call=True
    )
    def display_confirm(n_clicks, selected_rows):
        if n_clicks and selected_rows: return True
        return False

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