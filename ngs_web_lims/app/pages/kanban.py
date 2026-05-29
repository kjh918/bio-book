from dash import html, dcc, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import base64
import io
import json
import traceback
import re
from datetime import datetime

from app.core.database import SessionLocal
from app.models._schema import Order, Sample, ActionLog, STAGE_SCHEMA_CONFIG 
from app.core.mapping import FACILITY_MAPPING, get_full_mapping_for_panel
from app.pages.base import LimsDashApp

from app.core.rules import LimsRules
from app.ui.shared_ui import create_project_summary_card

from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify

def create_kanban_layout():
    # 🎨 칸반 컬럼 헤더 스타일 헬퍼 (모던 파스텔 톤)
    def col_header_style(bg_color, text_color):
        return {
            "backgroundColor": bg_color,
            "color": text_color,
            "fontSize": "0.95rem",
            "padding": "10px",
            "borderRadius": "8px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.02)"
        }

    # 🎨 칸반 드롭 영역(본문) 스타일 헬퍼
    def col_body_style():
        return {
            "minHeight": "600px",
            "backgroundColor": "#f8fafc", # 아주 연한 슬레이트 회색
            "borderRadius": "8px",
            "border": "2px dashed #e2e8f0", # 드롭 영역임을 암시하는 점선
            "marginTop": "8px",
            "padding": "10px"
        }

    return html.Div([
        # 🚀 1. 페이지 헤더 (style.css의 .page-title-header 적용)
        html.Div([
            html.Div([
                html.H2([
                    DashIconify(icon="carbon:flow", className="me-2 text-dark"), 
                    "WORKFLOW BOARD"
                ], className="fw-bold text-dark")
            ])
        ], className="page-title-header"),
        
        # 🚀 2. 칸반 보드 영역
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div("접수 대기", className="fw-bold text-center", style=col_header_style("#f1f5f9", "#475569")),
                    html.Div(id="kanban-col-0", style=col_body_style())
                ], style={"minWidth": "280px"}),
                
                dbc.Col([
                    html.Div("접수 완료", className="fw-bold text-center", style=col_header_style("#e0f2fe", "#0284c7")),
                    html.Div(id="kanban-col-1", style=col_body_style())
                ], style={"minWidth": "280px"}),
                
                dbc.Col([
                    html.Div("QC 진행", className="fw-bold text-center", style=col_header_style("#fef3c7", "#d97706")),
                    html.Div(id="kanban-col-2", style=col_body_style())
                ], style={"minWidth": "280px"}),
                
                dbc.Col([
                    html.Div("시퀀싱", className="fw-bold text-center", style=col_header_style("#e0e7ff", "#4f46e5")),
                    html.Div(id="kanban-col-3", style=col_body_style())
                ], style={"minWidth": "280px"}),
                
                dbc.Col([
                    html.Div("분석", className="fw-bold text-center", style=col_header_style("#DFF5E1", "#18bc9c")),
                    html.Div(id="kanban-col-4", style=col_body_style())
                ], style={"minWidth": "280px"}),
                
                dbc.Col([
                    html.Div("정산", className="fw-bold text-center", style=col_header_style("#f3e8ff", "#9333ea")),
                    html.Div(id="kanban-col-5", style=col_body_style())
                ], style={"minWidth": "280px"}),
            ], className="flex-nowrap g-3") 
        ], style={"overflowX": "auto", "paddingBottom": "20px"}),
        
        # 🚀 3. 숨겨진 기능용 스토어
        dcc.Store(id="current-modal-order-id"),
        dcc.Download(id="download-modal-excel"), 

        # 🚀 4. 모달(Modal) 팝업 디자인 개편
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-detail-title", className="fw-bold", style={"color": "#1e293b"})),
            dbc.ModalBody([
                html.Div(id="modal-shared-card-container", className="mb-3"),
                
                # 모달 내부 툴바 (둥근 테두리와 깔끔한 레이아웃)
                html.Div([
                    html.Div([
                        html.Strong([DashIconify(icon="carbon:edit", className="me-1"), "일괄 변경:"], className="text-secondary me-2", style={"fontSize": "0.85rem"}),
                        dbc.Select(id="bulk-col-select", options=[], placeholder="항목 선택...", style={"width": "150px"}, className="me-2 shadow-sm form-select-sm"),
                        dbc.Input(id="bulk-val-input", placeholder="입력값...", style={"width": "150px"}, className="me-2 shadow-sm form-control-sm"),
                        dbc.Button("적용", id="btn-bulk-apply", color="primary", size="sm", className="fw-bold shadow-sm rounded-3"),
                    ], className="d-flex align-items-center"),
                    
                    html.Div([
                        dbc.Button([DashIconify(icon="carbon:download", className="me-1"), "현재 표 엑셀 다운로드"], id="btn-export-excel", color="light", size="sm", className="me-2 fw-bold shadow-sm border rounded-3 text-secondary"),
                        dcc.Upload(
                            id="upload-overwrite-excel",
                            children=dbc.Button([DashIconify(icon="carbon:upload", className="me-1"), "엑셀 덮어쓰기"], color="white", size="sm", className="fw-bold shadow-sm border border-primary text-primary rounded-3"),
                            multiple=False, className="d-inline-block"
                        )
                    ], className="d-flex align-items-center")
                    
                ], className="d-flex justify-content-between align-items-center p-3 mb-3 rounded-4 border", style={"backgroundColor": "#f8fafc", "borderColor": "#e2e8f0"}),

                # 모달 내부 AG Grid
                dag.AgGrid(
                    id="modal-datatable",
                    rowData=[], 
                    columnDefs=[], 
                    defaultColDef={"resizable": True, "sortable": True, "filter": True},
                    dashGridOptions={
                        "rowHeight": 45, 
                        "singleClickEdit": True, 
                        "stopEditingWhenCellsLoseFocus": True,
                        "enterNavigatesVertically": True,
                        "enterNavigatesVerticallyAfterEdit": True,
                        "undoRedoCellEditing": True, 
                        "undoRedoCellEditingLimit": 50 
                    },
                    style={"height": "400px", "width": "100%"},
                    className="ag-theme-alpine border-0 shadow-sm rounded-3"
                )
            ], style={"maxHeight": "80vh", "overflowY": "auto"}),
            
            # 모달 푸터
            dbc.ModalFooter([
                html.Span("💡 수정 후 저장을 누르시면 변경사항이 반영되며 활동 로그가 기록됩니다.", className="text-muted small fw-bold me-auto"),
                dbc.Button([DashIconify(icon="carbon:save", className="me-1"), "변경사항 저장"], id="btn-save-modal", color="primary", className="fw-bold rounded-3 shadow-sm px-4")
            ], className="border-top-0 bg-light rounded-bottom-4")
        ], 
        id="sample-detail-modal", size="xl", is_open=False, centered=True, backdrop="static",
        dialog_style={"maxWidth": "1400px", "width": "95%"}, 
        # 🚀 [오류 수정] content_class -> content_class_name 으로 변경!
        content_class_name="rounded-4 border-0 shadow-lg" 
        ),

        html.Div(dbc.Toast(id="gatekeeper-toast", header="⚠️ 알림", is_open=False, dismissable=True, icon="danger", style={"position": "fixed", "top": 20, "right": 20, "width": 350, "zIndex": 9999})),
        dcc.Store(id="kanban-update-trigger", data=0), 
        dcc.Store(id="drag-drop-store", data=None),
        html.Button(id="btn-hidden-drop", style={"display": "none"}), 
        html.Div(id="dummy-js-output", style={"display": "none"})

    ])
# ==========================================
# [2] 카드 생성 함수
# ==========================================
def make_batch_card(order_obj, status, sample_count, has_issue):
    total_revenue = (order_obj.sales_unit_price or 0) * sample_count
    action_rule = LimsRules.STAGE_ACTIONS.get(status, {"text": "다음 단계", "color": "info", "next": "완료"})
    btn_text, btn_color, next_stage = action_rule["text"], action_rule["color"], action_rule["next"]
    group_id = f"{order_obj.order_id}___{status}"
    
    # 🚀 상태별 테두리 색상 및 보조 색상 매핑
    STATUS_THEME = {
        "접수 대기": {"border": "border-secondary", "text": "text-secondary"},
        "접수 완료": {"border": "border-info", "text": "text-info"},
        "QC 진행": {"border": "border-warning", "text": "text-warning"},
        "시퀀싱": {"border": "border-primary", "text": "text-primary"},
        "분석": {"border": "border-success", "text": "text-success"},
        "정산": {"border": "border-dark", "text": "text-dark"}
    }
    theme = STATUS_THEME.get(status, {"border": "border-secondary", "text": "text-secondary"})
    
    stage_specific_content = []
    if status == "접수 대기": stage_specific_content.extend([html.Small("⏳ 실물 샘플 입고 대기중", className="text-danger fw-bold d-block mb-1"), html.Small(f"🏢 기관: {order_obj.facility}-{order_obj.client_team}", className="text-muted d-block")])
    elif status == "접수 완료": stage_specific_content.extend([html.Small("✅ 추출 대기중", className="text-success fw-bold d-block mb-1"), html.Small(f"📅 접수일: {order_obj.reception_date}", className="text-muted d-block")])
    elif status == "QC 진행": stage_specific_content.extend([html.Small("🔬 DNA/RNA 추출 및 농도 측정", className="text-warning fw-bold d-block mb-1"), html.Small(f"🏢 기관: {order_obj.facility}", className="text-muted d-block")])
    elif status == "정산 대기": stage_specific_content.append(html.Div([html.Small(f"💰 예상 매출: {total_revenue:,}원", className="d-block text-primary fw-bold")], className="bg-light p-1 rounded border", style={"fontSize": "0.8rem"}))
    else: stage_specific_content.append(html.Small(f"🏢 기관: {order_obj.facility}", className="text-muted d-block"))

    return html.Div([
        dbc.Card([
            dbc.CardBody([
                # 🚀 제목 색상도 상태 테마(theme['text'])를 따라가도록 변경
                html.H6(f"📦 {order_obj.order_id}", className=f"fw-bold {theme['text']} mb-2"),
                html.P([
                    html.Span(f"📊 {sample_count}건", className="badge bg-secondary me-1"), 
                    html.Span("⚠️ 이슈", className="badge bg-danger ms-1") if has_issue else None
                ], className="mb-2"),
                html.Div(stage_specific_content, className="mb-3"),
                dbc.Button(btn_text, id={"type": "btn-move-stage", "index": group_id, "next": next_stage}, color=btn_color, size="sm", className="w-100 mb-1 fw-bold"),
                dbc.Button("🔍 상세 및 입고/진행 확인", id={"type": "btn-open-modal", "order_id": order_obj.order_id, "stage": status}, color="link", size="sm", className="w-100 text-muted")
            ], className="p-3")
        # 🚀 [핵심] border-info 대신 status별로 유동적인 border 클래스 적용
        ], className=f"shadow-sm border-start border-4 {theme['border']} h-100 rounded-3") 
    ], draggable=True, id=f"drag-card-{group_id}", style={"cursor": "grab"}, className="mb-3")

# ==========================================
# [3] 콜백 로직
# ==========================================
def register_kanban_callbacks(dash_app):
    
    @dash_app.callback(
        [Output(f"kanban-col-{i}", "children") for i in range(0, 6)], Input("kanban-update-trigger", "data")
    )
    def render_kanban_board(trigger):
        cols = [[], [], [], [], [], []]
        status_idx = {"접수 대기": 0, "접수 완료": 1, "QC 진행": 2, "시퀀싱 진행": 3, "분석 진행": 4, "정산 대기": 5}
        db = SessionLocal()
        try:
            all_orders = db.query(Order).join(Sample).all()
            groups = {}
            for o in all_orders:
                for s in o.samples:
                    stat = s.current_status if s.current_status in status_idx else "접수 대기"
                    key = (o.order_id, stat)
                    if key not in groups: groups[key] = {"order": o, "count": 0, "has_issue": False}
                    groups[key]["count"] += 1
                    if s.issue_comment and str(s.issue_comment).strip() not in ["", "None", "nan"]: groups[key]["has_issue"] = True

            for (oid, stat), data in groups.items():
                cols[status_idx.get(stat, 0)].append(make_batch_card(data["order"], stat, data["count"], data["has_issue"]))
            return cols
        except Exception as e:
            print(f"Kanban Load Error: {e}")
            return cols
        finally: db.close()

    @dash_app.callback(
        [
            Output("sample-detail-modal", "is_open"), Output("modal-detail-title", "children"), Output("modal-shared-card-container", "children"),
            Output("modal-datatable", "rowData"), Output("modal-datatable", "columnDefs"), Output("current-modal-order-id", "data"), Output("bulk-col-select", "options") 
        ],
        [Input({"type": "btn-open-modal", "order_id": ALL, "stage": ALL}, "n_clicks"), Input("btn-save-modal", "n_clicks")],
        [State("sample-detail-modal", "is_open"), State("current-modal-order-id", "data")],
        prevent_initial_call=True
    )
    def handle_modal(open_clicks, save_clicks, is_open, current_oid):
        if not ctx.triggered: return [no_update] * 7
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        if tid == "btn-save-modal": return False, no_update, no_update, no_update, no_update, no_update, no_update

        db = SessionLocal()
        try:
            oid = current_oid
            stage = "접수 대기"

            if "btn-open-modal" in tid:
                if all(c is None for c in open_clicks): return [no_update] * 7
                btn_data = json.loads(tid)
                oid, stage = btn_data["order_id"], btn_data["stage"]

            if not oid: return [no_update] * 7
            order = db.query(Order).filter(Order.order_id == oid).first()
            if not order: return [no_update] * 7

            samples = [s for s in order.samples if s.current_status == stage]
            columns = LimsDashApp.get_base_grid_columns(include_project=False)
            stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})

            bulk_options = [{"label": col["name"], "value": col["id"]} for col in stage_config["columns"] if col.get("editable", True)]
            
            for col in stage_config["columns"]:
                ag_col = {"headerName": col["name"], "field": col["id"], "editable": col.get("editable", True)}
                if col.get("presentation") == "dropdown": 
                    ag_col["cellEditor"] = "agSelectCellEditor"
                    if "options" in col: ag_col["cellEditorParams"] = {"values": col["options"]}
                columns.append(ag_col)
                
            bulk_options.extend([{"label": "🔄 진행 상태", "value": "current_status"}, {"label": "📝 특이사항/메모", "value": "issue_comment"}])
            columns.extend([
                {"headerName": "진행 상태", "field": "current_status", "editable": True, "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "보류/실패","재실험"]}, "width": 120},
                {"headerName": "특이사항/메모", "field": "issue_comment", "editable": True, "cellEditor": "agLargeTextCellEditor", "cellEditorPopup": True, "cellEditorParams": {"maxLength": 1000, "rows": 6, "cols": 50}, "flex": 1, "minWidth": 250}
            ])

            table_data = []
            for s in samples:
                row_dict = {
                    "order_id": s.order_id, 
                    "sample_id": s.sample_id, 
                    "id": s.id, 
                    "sample_name": s.sample_name, 
                    "target_panel": s.target_panel,
                    "current_status": s.current_status, 
                    "issue_comment": s.issue_comment or "", 
                    "is_dropped": "유지"
                }
                for col in stage_config["columns"]:
                    col_id = col["id"]
                    if hasattr(s, col_id): row_dict[col_id] = getattr(s, col_id) or ""
                    elif s.panel_metadata and col_id in s.panel_metadata: row_dict[col_id] = s.panel_metadata[col_id]
                table_data.append(row_dict)
                
            shared_project_card = create_project_summary_card(order, len(samples))
            return True, f"📋 프로젝트 상세 ({stage})", shared_project_card, table_data, columns, oid, bulk_options
            
        finally: db.close()
        
    @dash_app.callback(
        Output("download-modal-excel", "data"), Input("btn-export-excel", "n_clicks"),
        [State("modal-datatable", "rowData"), State("current-modal-order-id", "data"), State("modal-detail-title", "children")], prevent_initial_call=True
    )
    def export_excel_table(n_clicks, table_data, oid, title):
        if not table_data: return no_update
        df = pd.DataFrame(table_data)
        stage = title.replace("📋 프로젝트 상세 (", "").replace(")", "") if title else "export"
        filename = f"{oid}_{stage}_데이터.xlsx"
        return dcc.send_data_frame(df.to_excel, filename, index=False)

    @dash_app.callback(
        Output("modal-datatable", "rowData", allow_duplicate=True),
        [Input("btn-bulk-apply", "n_clicks"), Input("upload-overwrite-excel", "contents")],
        [State("bulk-col-select", "value"), State("bulk-val-input", "value"), State("modal-datatable", "rowData")], prevent_initial_call=True
    )
    def bulk_and_excel_overwrite(bulk_clicks, upload_contents, col, val, row_data):
        if not row_data: return no_update
        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if tid == "btn-bulk-apply":
            if not col or val is None: return no_update
            val_str = str(val).strip()
            if col == "sample_received" and val_str.replace(" ", "") in ["입고완료", "입고", "o", "y", "완료"]: val_str = "입고 완료"
            elif col == "visual_inspection" and val_str.lower() in ["pass", "p", "패스", "통과"]: val_str = "Pass"
            elif col == "visual_inspection" and val_str.lower() in ["fail", "f", "실패", "페일"]: val_str = "Fail"
            
            new_data = [ {**row, col: val_str} for row in row_data ]
            return new_data
            
        elif tid == "upload-overwrite-excel" and upload_contents:
            content_type, content_string = upload_contents.split(',')
            decoded = base64.b64decode(content_string)
            df_upload = pd.read_excel(io.BytesIO(decoded))
            upload_dict = df_upload.to_dict('records')
            
            new_data = []
            for row in row_data:
                new_row = row.copy()
                match = next((u for u in upload_dict if str(u.get("sample_name")) == str(row.get("sample_name"))), None)
                if match:
                    for k, v in match.items():
                        if k in new_row and pd.notna(v) and k not in ["id", "sample_name", "target_panel"]:
                            val_str = str(v).strip()
                            if k == "sample_received":
                                if val_str.replace(" ", "") in ["입고완료", "입고", "o", "y", "완료"]: val_str = "입고 완료"
                                elif val_str.replace(" ", "") in ["대기중", "대기", "x", "n", "미입고"]: val_str = "대기중"
                            elif k == "visual_inspection":
                                if val_str.lower() in ["pass", "p", "패스", "통과"]: val_str = "Pass"
                                elif val_str.lower() in ["fail", "f", "실패", "페일", "불량"]: val_str = "Fail"
                            elif k == "extraction_status":
                                if val_str.upper() in ["O", "0", "PASS", "완료", "y"]: val_str = "O"
                                elif val_str.upper() in ["X", "FAIL", "실패", "n"]: val_str = "X"
                            new_row[k] = val_str
                new_data.append(new_row)
            return new_data        
        return no_update
    
    @dash_app.callback(
        [Output("kanban-update-trigger", "data", allow_duplicate=True), Output("gatekeeper-toast", "is_open"), Output("gatekeeper-toast", "children")],
        [Input("drag-drop-store", "data"), Input({"type": "btn-move-stage", "index": ALL, "next": ALL}, "n_clicks"), Input("btn-save-modal", "n_clicks")],
        [State("modal-datatable", "rowData"), State("kanban-update-trigger", "data"), State("modal-detail-title", "children")], prevent_initial_call=True
    )
    def update_data(drag_data, btn_clicks, save_click, table_data, trig, title):
        if not ctx.triggered: return no_update, False, no_update
        
        trigger_val = ctx.triggered[0]["value"]
        if not trigger_val: 
            return no_update, False, no_update

        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        db = SessionLocal()
        error_msgs = []
        try:
            upd = 0
            if tid == "btn-save-modal" and table_data:
                stage = title.replace("📋 프로젝트 상세 (", "").replace(")", "") if title else ""
                stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})
                
                for row in table_data:
                    s_name_val = str(row.get("sample_name", "")).strip()
                    if not s_name_val: continue 

                    s = db.query(Sample).filter(Sample.id == row.get("id")).first()
                    if not s: continue

                    old_status = s.current_status
                    old_issue = s.issue_comment or ""
                    new_status = str(row.get("current_status", s.current_status)).strip()
                    new_issue = str(row.get("issue_comment", "")).strip()
                    
                    if "재실험" in new_status: 
                        base_id = str(s.sample_id or "UNKNOWN")
                        match = re.search(r'-R(\d+)$', base_id)
                        new_s_id = base_id[:match.start()] + f"-R{int(match.group(1)) + 1}" if match else base_id + "-R1"
                            
                        new_s = Sample(
                            order_pk=s.order_pk, order_id=s.order_id, sample_id=new_s_id, target_panel=s.target_panel,
                            current_status="접수 대기", sample_name=s.sample_name, cancer_type=s.cancer_type,
                            specimen=s.specimen, project_name=s.project_name, pairing_info=s.pairing_info,
                            outside_id_1=s.outside_id_1, issue_comment=f"[{stage} 단계에서 재실험 요청됨 (원본: {base_id})]",
                            panel_metadata=s.panel_metadata
                        )
                        db.add(new_s)
                        
                        s.current_status = "보류/실패"
                        s.issue_comment = f"[재실험 진행으로 인한 종료] {new_issue}"
                        db.add(ActionLog(sample_id=s.id, action_type="재실험 요청", previous_state=stage, new_state="보류/실패", details=f"새 샘플 {new_s_id} 파생됨"))
                        upd += 1
                        continue

                    # 🚀 강제 타입 정리 및 데이터 업데이트 로직
                    has_field_change = False
                    for col in stage_config["columns"]:
                        c_id = col["id"]
                        if c_id in row:
                            val = row[c_id]
                            # 공백 제거 등 강력한 정제
                            if isinstance(val, str): val = val.strip()
                                
                            if col.get("type") == "numeric":
                                try: val = float(val) if str(val).strip() else None
                                except ValueError: val = None
                            
                            if hasattr(s, c_id): 
                                if getattr(s, c_id) != val:
                                    setattr(s, c_id, val); has_field_change = True
                            else: 
                                if s.panel_metadata is None: s.panel_metadata = {}
                                if s.panel_metadata.get(c_id) != val:
                                    s.panel_metadata[c_id] = val; has_field_change = True
                    
                    if has_field_change: 
                        if s.panel_metadata is not None: s.panel_metadata = dict(s.panel_metadata)
                        db.add(ActionLog(sample_id=s.id, action_type="데이터 갱신", previous_state=old_status, new_state=old_status, details="상세 수정"))
                        upd += 1

                    # 🚀 무결성 검증 (오타, 공백까지 철저하게 보정 후 비교)
                    stages_order = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "보류/실패"]
                    try: old_idx, new_idx = stages_order.index(old_status), stages_order.index(new_status)
                    except ValueError: old_idx, new_idx = 0, 0
                        
                    if new_idx < old_idx and new_status != "보류/실패":
                        error_msgs.append(f"🚫 [{s.sample_name}] 역방향 이동 불가 (상태는 기존으로 유지됩니다.)")
                        new_status = old_status

                    if new_status != old_status and new_status not in ["보류/실패", "재실험"]:
                        is_passed = True
                        for col in stage_config["columns"]:
                            db_val = str(getattr(s, col["id"], "") if hasattr(s, col["id"]) else (s.panel_metadata.get(col["id"], "") if s.panel_metadata else "")).replace(" ", "")
                            target_val = str(col.get("pass_value", "")).replace(" ", "")
                            
                            if col.get("required") and not db_val:
                                error_msgs.append(f"[{s.sample_name}] 필수 항목 '{col['name']}' 누락"); is_passed = False
                            if col.get("pass_value") and db_val != target_val:
                                error_msgs.append(f"📦 [{s.sample_name}] 다음 단계 이동 불가: '{col['name']}'을(를) 반드시 '{col.get('pass_value')}'(으)로 설정하세요."); is_passed = False
                        
                        if not is_passed: 
                            new_status = old_status 

                    if old_status != new_status:
                        s.current_status = new_status
                        db.add(ActionLog(sample_id=s.id, action_type="상태 변경", previous_state=old_status, new_state=new_status, details="모달창 갱신"))
                        upd += 1
                        
                    if old_issue != new_issue:
                        s.issue_comment = new_issue
                        db.add(ActionLog(sample_id=s.id, action_type="특이사항 갱신", previous_state=old_status, new_state=s.current_status, details=f"기존: {old_issue or '없음'} ➡️ 변경됨"))
                        upd += 1

            # ==========================================
            # 2. 칸반 [버튼 클릭] 또는 [드래그] 로직
            # ==========================================
            else:
                group_id, next_s = (None, None)
                if tid == "drag-drop-store" and drag_data: group_id, next_s = drag_data["card_id"].replace("drag-card-", ""), drag_data["new_stage"]
                elif "btn-move-stage" in tid: d = json.loads(tid); group_id, next_s = d["index"], d["next"]

                if group_id:
                    oid, curr_s = group_id.split("___")
                    if curr_s == next_s: return no_update, False, no_update
                        
                    stages_order = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"]
                    try: curr_idx, next_idx = stages_order.index(curr_s), stages_order.index(next_s)
                    except ValueError: curr_idx, next_idx = 0, 0
                    
                    if next_idx < curr_idx:
                        error_msgs.append(f"🚫 역방향 이동 불가: [{curr_s}] -> [{next_s}]")
                    else:
                        samples = db.query(Sample).join(Order).filter(Order.order_id == oid, Sample.current_status == curr_s).all()
                        
                        for s in samples:
                            if curr_s == "접수 대기" and next_s != "접수 대기":
                                if str(s.sample_received).replace(" ", "") != "입고완료":
                                    error_msgs.append(f"📦 [{s.sample_name}] '입고 확인'을 입고 완료로 변경해주세요.")
                                if not s.receiver_name or str(s.receiver_name).strip() == "":
                                    error_msgs.append(f"👤 [{s.sample_name}] '입고 담당자' 이름이 누락되었습니다.")
                        
                        if not error_msgs:
                            for s in samples:
                                old_status = s.current_status
                                s.current_status = next_s
                                db.add(ActionLog(sample_id=s.id, action_type="상태 변경 (일괄)", previous_state=old_status, new_state=next_s, details=f"칸반 이동"))
                                upd += 1

            if error_msgs:
                db.rollback()
                toast_content = html.Div([html.P(msg, className="mb-1 text-danger fw-bold") for msg in error_msgs[:5]]) 
                return no_update, True, toast_content
                
            if upd > 0: db.commit(); return (trig or 0) + 1, False, no_update
            return no_update, False, no_update
        finally: db.close()

    dash_app.clientside_callback(
        """
        function(trigger) {
            setTimeout(function() {
                var cards = document.querySelectorAll('[draggable="true"]');
                cards.forEach(function(card) { card.ondragstart = function(e) { e.dataTransfer.setData('text', card.id); }; });
                var stages = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"];
                for (let i = 0; i <= 5; i++) {
                    let col = document.getElementById('kanban-col-' + i);
                    if (!col) continue;
                    col.ondragover = function(e) { e.preventDefault(); };
                    col.ondrop = function(e) {
                        e.preventDefault();
                        var id = e.dataTransfer.getData('text');
                        if(id) {
                            window.latestDropData = {"card_id": id, "new_stage": stages[i], "ts": Date.now()};
                            document.getElementById('btn-hidden-drop').click();
                        }
                    };
                }
            }, 800); 
            return "";
        }
        """, Output("dummy-js-output", "children"), Input("kanban-update-trigger", "data")
    )
    
    dash_app.clientside_callback("function(n){ return window.latestDropData || window.dash_clientside.no_update; }", Output("drag-drop-store", "data"), Input("btn-hidden-drop", "n_clicks"))

def create_kanban_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_kanban_layout)
    app = lims.get_app() 
    register_kanban_callbacks(app)
    return app