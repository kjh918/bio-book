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

# ==========================================
# [1] 화면 레이아웃
# ==========================================
def create_kanban_layout():
    return html.Div([
        html.H3("🧬 NGS 통합 보드", className="fw-bold mb-4 text-secondary"),
        
        html.Div([
            dbc.Row([
                dbc.Col([html.H5("접수 대기", className="fw-bold text-center text-dark bg-light border p-2 rounded shadow-sm"), html.Div(id="kanban-col-0", className="p-2 bg-white rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("접수 완료", className="fw-bold text-center text-white bg-info p-2 rounded shadow-sm"), html.Div(id="kanban-col-1", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("QC", className="fw-bold text-center text-dark bg-warning p-2 rounded shadow-sm"), html.Div(id="kanban-col-2", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("시퀀싱", className="fw-bold text-center text-white bg-primary p-2 rounded shadow-sm"), html.Div(id="kanban-col-3", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("분석", className="fw-bold text-center text-white bg-success p-2 rounded shadow-sm"), html.Div(id="kanban-col-4", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("정산", className="fw-bold text-center text-white bg-dark p-2 rounded shadow-sm"), html.Div(id="kanban-col-5", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
            ], className="flex-nowrap g-2") 
        ], style={"overflowX": "auto", "paddingBottom": "20px"}),
        
        dcc.Store(id="current-modal-order-id"),
        dcc.Download(id="download-modal-excel"), # 엑셀 다운로드

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-detail-title", className="fw-bold")),
            dbc.ModalBody([
                html.Div(id="modal-shared-card-container", className="mb-3"),
                html.Div([
                    # 왼쪽: 기존 일괄 덮어쓰기 도우미
                    html.Div([
                        html.Strong("✨ 빠른 덮어쓰기:", className="text-success me-2"),
                        dbc.Select(
                            id="bulk-col-select", 
                            options=[], # 🚀 여기를 비웁니다!
                            placeholder="변경할 항목 선택...", 
                            style={"width": "180px"}, 
                            className="me-2 shadow-sm"
                        ),
                        dbc.Input(id="bulk-val-input", placeholder="입력값 (예: Pass...)", style={"width": "180px"}, className="me-2 shadow-sm"),
                        dbc.Button("적용", id="btn-bulk-apply", color="success", outline=True, size="sm", className="fw-bold shadow-sm"),
                    ], className="d-flex align-items-center"),
                    
                    # 오른쪽: 엑셀 다운로드 & 업로드 기반 표 덮어쓰기
                    html.Div([
                        dbc.Button("📥 현재 표 엑셀 다운로드", id="btn-export-excel", color="info", size="sm", className="me-2 fw-bold shadow-sm"),
                        dcc.Upload(
                            id="upload-overwrite-excel",
                            children=dbc.Button("📤 엑셀 업로드로 표 덮어쓰기", color="warning", size="sm", className="fw-bold shadow-sm"),
                            multiple=False, className="d-inline-block"
                        )
                    ], className="d-flex align-items-center")
                    
                ], className="d-flex justify-content-between align-items-center p-2 mb-3 rounded border", style={"backgroundColor": "#f8fffb", "borderColor": "#20c997"}),

                # 🚀 세련된 AG Grid 사용!
                dag.AgGrid(
                    id="modal-datatable",
                    rowData=[], columnDefs=[],
                    defaultColDef={"resizable": True, "sortable": True, "filter": True},
                    dashGridOptions={
                        "rowHeight": 45, 
                        "singleClickEdit": True, 
                        "stopEditingWhenCellsLoseFocus": True,
                        "enterNavigatesVertically": True,
                        "enterNavigatesVerticallyAfterEdit": True,
                        # 🚀 1차 방어: Ctrl+Z (실행 취소) 및 Ctrl+Y (다시 실행) 활성화!
                        "undoRedoCellEditing": True, 
                        "undoRedoCellEditingLimit": 50  # 최근 50번의 수정 기록을 기억함
                    },
                    style={"height": "400px", "width": "100%"},
                    className="ag-theme-alpine"
                )
            ], style={"maxHeight": "80vh", "overflowY": "auto"}),
            dbc.ModalFooter([
                html.Span("수정 후 저장을 누르시면 내용이 반영되며 활동 로그가 기록됩니다.", className="text-info small fw-bold me-auto"),
                dbc.Button("💾 변경사항 및 검수 저장", id="btn-save-modal", color="primary")
            ])
        ], 
        id="sample-detail-modal", size="xl", is_open=False, centered=True, backdrop="static",
        dialog_style={"maxWidth": "1400px", "width": "95%"}
        ),

        html.Div(dbc.Toast(id="gatekeeper-toast", header="⚠️ 알림", is_open=False, dismissable=True, icon="danger", style={"position": "fixed", "top": 20, "right": 20, "width": 350, "zIndex": 9999})),
        dcc.Store(id="kanban-update-trigger", data=0), 
        dcc.Store(id="drag-drop-store", data=None),
        html.Button(id="btn-hidden-drop", style={"display": "none"}), 
        html.Div(id="dummy-js-output", style={"display": "none"})

    ], style={"overflowX": "hidden", "position": "relative", "padding": "20px"})

# ==========================================
# [2] 카드 생성 함수
# ==========================================
def make_batch_card(order_obj, status, sample_count, has_issue):
    total_revenue = (order_obj.sales_unit_price or 0) * sample_count
    action_rule = LimsRules.STAGE_ACTIONS.get(status, {"text": "다음 단계", "color": "info", "next": "완료"})
    btn_text, btn_color, next_stage = action_rule["text"], action_rule["color"], action_rule["next"]
    group_id = f"{order_obj.order_id}___{status}"
    
    stage_specific_content = []
    if status == "접수 대기": stage_specific_content.extend([html.Small("⏳ 실물 샘플 입고 대기중", className="text-danger fw-bold d-block mb-1"), html.Small(f"🏢 기관: {order_obj.facility}-{order_obj.client_team}", className="text-muted d-block")])
    elif status == "접수 완료": stage_specific_content.extend([html.Small("✅ 추출 대기중", className="text-success fw-bold d-block mb-1"), html.Small(f"📅 접수일: {order_obj.reception_date}", className="text-muted d-block")])
    elif status == "QC 진행": stage_specific_content.extend([html.Small("🔬 DNA/RNA 추출 및 농도 측정", className="text-warning fw-bold d-block mb-1"), html.Small(f"🏢 기관: {order_obj.facility}", className="text-muted d-block")])
    elif status == "정산 대기": stage_specific_content.append(html.Div([html.Small(f"💰 예상 매출: {total_revenue:,}원", className="d-block text-primary fw-bold")], className="bg-light p-1 rounded border", style={"fontSize": "0.8rem"}))
    else: stage_specific_content.append(html.Small(f"🏢 기관: {order_obj.facility}", className="text-muted d-block"))

    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.H6(f"📦 {order_obj.order_id}", className="fw-bold text-primary mb-2"),
                html.P([html.Span(f"📊 {sample_count}건", className="badge bg-dark me-1"), html.Span("⚠️ 이슈", className="badge bg-danger ms-1") if has_issue else None], className="mb-2"),
                html.Div(stage_specific_content, className="mb-3"),
                dbc.Button(btn_text, id={"type": "btn-move-stage", "index": group_id, "next": next_stage}, color=btn_color, size="sm", className="w-100 mb-1 fw-bold"),
                dbc.Button("🔍 상세 및 입고/진행 확인", id={"type": "btn-open-modal", "order_id": order_obj.order_id, "stage": status}, color="link", size="sm", className="w-100 text-muted")
            ], className="p-3")
        ], className="shadow-sm border-start border-4 border-info h-100")
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
                    #if s.current_status in ["완료", "보류/실패", "재실험"]: continue
                    stat = s.current_status if s.current_status in status_idx else "접수 대기"
                    key = (o.order_id, stat)
                    if key not in groups: groups[key] = {"order": o, "count": 0, "has_issue": False}
                    groups[key]["count"] += 1
                    if s.issue_comment and str(s.issue_comment).strip() not in ["", "None", "nan"]: groups[key]["has_issue"] = True

            for (oid, stat), data in groups.items():
                cols[status_idx.get(stat, 0)].append(make_batch_card(data["order"], stat, data["count"], data["has_issue"]))
            return cols
        finally: db.close()

    # 모달 오픈 콜백 (AG Grid 용으로 columnDefs, rowData 반환)
    @dash_app.callback(
        [
            Output("sample-detail-modal", "is_open"), 
            Output("modal-detail-title", "children"), 
            Output("modal-shared-card-container", "children"),
            Output("modal-datatable", "rowData"), 
            Output("modal-datatable", "columnDefs"), 
            Output("current-modal-order-id", "data"),
            Output("bulk-col-select", "options") # 🚀 7번째 Output
        ],
        [Input({"type": "btn-open-modal", "order_id": ALL, "stage": ALL}, "n_clicks"), 
         Input("btn-save-modal", "n_clicks")],
        [State("sample-detail-modal", "is_open"), 
         State("current-modal-order-id", "data")],
        prevent_initial_call=True
    )
    def handle_modal(open_clicks, save_clicks, is_open, current_oid):
        # 🚀 1. 예외 처리 반환값도 모두 7개로 맞춰야 합니다. (* 7 로 변경)
        if not ctx.triggered: return [no_update] * 7
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        # 🚀 2. 저장 버튼 클릭 시에도 7개를 반환해야 합니다.
        if tid == "btn-save-modal": return False, no_update, no_update, no_update, no_update, no_update, no_update

        db = SessionLocal()
        try:
            oid = current_oid
            stage = "접수 대기"

            if "btn-open-modal" in tid:
                # 🚀 3. 예외 처리 반환값 7개로 수정
                if all(c is None for c in open_clicks): return [no_update] * 7
                btn_data = json.loads(tid)
                oid, stage = btn_data["order_id"], btn_data["stage"]

            # 🚀 4. 예외 처리 반환값 7개로 수정
            if not oid: return [no_update] * 7
            order = db.query(Order).filter(Order.order_id == oid).first()
            if not order: return [no_update] * 7

            samples = [s for s in order.samples if s.current_status == stage]

            # AG Grid 컬럼 설정
            columns = [
                {"headerName": "Regist ID", "field": "sample_id", "editable": False, "width": 150},
                {"headerName": "Patient ID / Sample ID", "field": "sample_name", "editable": False, "width": 150},
                {"headerName": "패널", "field": "target_panel", "editable": False, "width": 100},
            ]

            stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})
            
            # 동적 bulk_options 생성
            bulk_options = [
                {"label": col["name"], "value": col["id"]} 
                for col in stage_config["columns"] 
                if col.get("editable", True)
            ]
            
            for col in stage_config["columns"]:
                ag_col = {"headerName": col["name"], "field": col["id"], "editable": col.get("editable", True)}
                if col.get("presentation") == "dropdown": 
                    ag_col["cellEditor"] = "agSelectCellEditor"
                    # 이전에 알려드린 options 자동 연동 로직 적용 (스키마에 맞춤)
                    if "options" in col:
                        ag_col["cellEditorParams"] = {"values": col["options"]}
                    else:
                        # 하드코딩 백업
                        if col["id"] == "is_dropped": ag_col["cellEditorParams"] = {"values": ["유지", "제외"]}
                        elif col["id"] == "visual_inspection": ag_col["cellEditorParams"] = {"values": ["Pass", "Fail", "대기중"]}
                        elif col["id"] == "sample_received": ag_col["cellEditorParams"] = {"values": ["대기중", "입고 완료"]}
                        elif col["id"] == "extraction_status": ag_col["cellEditorParams"] = {"values": ["O", "X", "-"]}
                columns.append(ag_col)
                
            bulk_options.extend([
                {"label": "🔄 진행 상태", "value": "current_status"},
                {"label": "📝 특이사항/메모", "value": "issue_comment"}
            ])
            
            columns.extend([
                {"headerName": "진행 상태", "field": "current_status", "editable": True, "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "보류/실패","재실험"]}, "width": 120},
                {"headerName": "특이사항/메모", "field": "issue_comment", "editable": True, "cellEditor": "agLargeTextCellEditor", "cellEditorPopup": True, "cellEditorParams": {"maxLength": 1000, "rows": 6, "cols": 50}, "flex": 1, "minWidth": 250}
            ])

            table_data = []
            for s in samples:
                row_dict = {
                    "sample_id": s.sample_id, "id": s.id, "sample_name": s.sample_name, "target_panel": s.target_panel,
                    "current_status": s.current_status, "issue_comment": s.issue_comment or "", "is_dropped": "유지"
                }
                for col in stage_config["columns"]:
                    col_id = col["id"]
                    if hasattr(s, col_id): row_dict[col_id] = getattr(s, col_id) or ""
                    elif s.panel_metadata and col_id in s.panel_metadata: row_dict[col_id] = s.panel_metadata[col_id]
                table_data.append(row_dict)

            shared_project_card = create_project_summary_card(order, len(samples))
            
            # 🚀 5. 최종 반환값에 bulk_options 추가 (총 7개)
            return True, f"📋 프로젝트 상세 ({stage})", shared_project_card, table_data, columns, oid, bulk_options
            
        finally: db.close()
        
    # 🚀 엑셀 다운로드 (AG Grid의 rowData 참조)
    @dash_app.callback(
        Output("download-modal-excel", "data"),
        Input("btn-export-excel", "n_clicks"),
        [State("modal-datatable", "rowData"), State("current-modal-order-id", "data"), State("modal-detail-title", "children")],
        prevent_initial_call=True
    )
    def export_excel_table(n_clicks, table_data, oid, title):
        if not table_data: return no_update
        df = pd.DataFrame(table_data)
        stage = title.replace("📋 프로젝트 상세 (", "").replace(")", "") if title else "export"
        filename = f"{oid}_{stage}_데이터.xlsx"
        return dcc.send_data_frame(df.to_excel, filename, index=False)

    # 🚀 일괄 덮어쓰기 & 엑셀 업로드 (AG Grid의 rowData 갱신)
    @dash_app.callback(
        Output("modal-datatable", "rowData", allow_duplicate=True),
        [Input("btn-bulk-apply", "n_clicks"), Input("upload-overwrite-excel", "contents")],
        [State("bulk-col-select", "value"), State("bulk-val-input", "value"), State("modal-datatable", "rowData")],
        prevent_initial_call=True
    )
    def bulk_and_excel_overwrite(bulk_clicks, upload_contents, col, val, row_data):
        if not row_data: return no_update
        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        
        # --- 1. 화면 내 일괄 덮어쓰기 도우미 로직 ---
        if tid == "btn-bulk-apply":
            if not col or val is None: return no_update
            val_str = str(val).strip()
            
            if col == "sample_received" and val_str.replace(" ", "") in ["입고완료", "입고", "o", "y", "완료"]: val_str = "입고 완료"
            elif col == "visual_inspection" and val_str.lower() in ["pass", "p", "패스", "통과"]: val_str = "Pass"
            elif col == "visual_inspection" and val_str.lower() in ["fail", "f", "실패", "페일"]: val_str = "Fail"
                
            new_data = []
            for row in row_data:
                new_row = row.copy()
                new_row[col] = val_str
                new_data.append(new_row)
            return new_data
            
        # --- 2. 🚀 엑셀 업로드 덮어쓰기 로직 (오타 자동 교정 탑재!) ---
        elif tid == "upload-overwrite-excel" and upload_contents:
            content_type, content_string = upload_contents.split(',')
            decoded = base64.b64decode(content_string)
            df_upload = pd.read_excel(io.BytesIO(decoded))
            upload_dict = df_upload.to_dict('records')
            
            new_data = []
            for row in row_data:
                new_row = row.copy()
                # Patient ID나 Sample ID가 일치하는 행을 엑셀에서 찾음
                match = next((u for u in upload_dict if str(u.get("sample_name")) == str(row.get("sample_name"))), None)
                
                if match:
                    for k, v in match.items():
                        if k in new_row and pd.notna(v):
                            if k not in ["id", "sample_name", "target_panel"]:
                                val_str = str(v).strip() # 엑셀의 불필요한 띄어쓰기 제거
                                
                                # 🚀 엑셀에서 대충 적어도 AG Grid 드롭다운 규격에 맞게 찰떡 교정!
                                if k == "sample_received":
                                    if val_str.replace(" ", "") in ["입고완료", "입고", "o", "y", "완료"]: val_str = "입고 완료"
                                    elif val_str.replace(" ", "") in ["대기중", "대기", "x", "n", "미입고"]: val_str = "대기중"
                                    
                                elif k == "visual_inspection":
                                    if val_str.lower() in ["pass", "p", "패스", "통과"]: val_str = "Pass"
                                    elif val_str.lower() in ["fail", "f", "실패", "페일", "불량"]: val_str = "Fail"
                                    elif val_str.replace(" ", "") in ["대기중", "대기"]: val_str = "대기중"
                                    
                                elif k == "is_dropped":
                                    if "제외" in val_str or val_str.lower() in ["drop", "x"]: val_str = "제외"
                                    elif "유지" in val_str or val_str.lower() in ["keep", "o"]: val_str = "유지"
                                    
                                elif k == "extraction_status":
                                    if val_str.upper() in ["O", "0", "PASS", "완료", "y"]: val_str = "O"
                                    elif val_str.upper() in ["X", "FAIL", "실패", "n"]: val_str = "X"
                                
                                # 교정된 값을 표 데이터에 삽입
                                new_row[k] = val_str
                                
                new_data.append(new_row)
            return new_data        
        return no_update
    
    # 🚀 핵심: 데이터 저장, 재실험, 역주행 방지가 완벽히 통합된 철통 보안 콜백
    @dash_app.callback(
        [Output("kanban-update-trigger", "data", allow_duplicate=True), Output("gatekeeper-toast", "is_open"), Output("gatekeeper-toast", "children")],
        [Input("drag-drop-store", "data"), Input({"type": "btn-move-stage", "index": ALL, "next": ALL}, "n_clicks"), Input("btn-save-modal", "n_clicks")],
        [State("modal-datatable", "rowData"), State("kanban-update-trigger", "data"), State("modal-detail-title", "children")], 
        prevent_initial_call=True
    )
    def update_data(drag_data, btn_clicks, save_click, table_data, trig, title):
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
                    # 🚀 [1] 재실험 로직: 정확한 ID 파생 규칙 적용 (-R1, -R2...)
                    if "재실험" in new_status: 
                        # s.sample_id가 None일 경우를 대비해 기본값 설정
                        base_id = str(s.sample_id or "UNKNOWN")
                        
                        # 정규식: 마지막에 -R숫자가 있는지 확인
                        match = re.search(r'-R(\d+)$', base_id)
                        
                        if match:
                            # 이미 -R1이 있으면 숫자를 하나 올림 (ex: -R1 -> -R2)
                            new_r = int(match.group(1)) + 1
                            new_s_id = base_id[:match.start()] + f"-R{new_r}"
                        else:
                            # 없으면 -R1을 붙임 (ex: ACC-260422-03 -> ACC-260422-03-R1)
                            new_s_id = base_id + "-R1"
                            
                        # 새 샘플 생성
                        new_s = Sample(
                            order_id=s.order_id, 
                            sample_id=new_s_id, 
                            target_panel=s.target_panel,
                            current_status="접수 대기", 
                            sample_name=s.sample_name, 
                            cancer_type=s.cancer_type,
                            specimen=s.specimen, 
                            sample_group=s.sample_group, 
                            pairing_info=s.pairing_info,
                            outside_id_1=s.outside_id_1, 
                            issue_comment=f"[{stage} 단계에서 재실험 요청됨 (원본: {base_id})]",
                            panel_metadata=s.panel_metadata
                        )
                        db.add(new_s)
                        
                        # 기존 샘플 처리
                        s.current_status = "보류/실패"
                        s.issue_comment = f"[재실험 진행으로 인한 종료] {new_issue}"
                        db.add(ActionLog(sample_id=s.id, action_type="재실험 요청", previous_state=stage, new_state="보류/실패", details=f"새 샘플 {new_s_id} 파생됨"))
                        upd += 1
                        continue

                    # 🚀 [2] 모달창 내 역방향 이동 방어벽!
                    stages_order = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "보류/실패"]
                    try:
                        old_idx = stages_order.index(old_status)
                        new_idx = stages_order.index(new_status)
                    except ValueError:
                        old_idx, new_idx = 0, 0
                        
                    if new_idx < old_idx and new_status != "보류/실패":
                        error_msgs.append(f"🚫 [{s.sample_name}] 역방향 이동 불가: 모달창에서 이전 단계로 되돌릴 수 없습니다.")
                        continue

                    # 🚀 [3] 전진 이동 조건 엄격 검사
                    if new_status != old_status and new_status not in ["보류/실패", "재실험"]:
                        is_passed = True
                        for col in stage_config["columns"]:
                            val = str(row.get(col["id"], "")).strip()
                            if col.get("required") and not val:
                                error_msgs.append(f"[{s.sample_name}] 필수 항목 '{col['name']}' 입력 누락."); is_passed = False
                            if col.get("pass_value") and val != col.get("pass_value"):
                                error_msgs.append(f"[{s.sample_name}] '{col['name']}' 통과 실패."); is_passed = False
                        if not is_passed: continue 

                    # 🚀 [4] 일반 항목만 갱신해도 정상적으로 DB가 업데이트되도록 수정!
                    has_field_change = False
                    for col in stage_config["columns"]:
                        c_id = col["id"]
                        if c_id in row:
                            val = row[c_id]
                            if col.get("type") == "numeric":
                                try: val = float(val) if str(val).strip() else None
                                except ValueError: val = None
                            
                            if hasattr(s, c_id): 
                                if getattr(s, c_id) != val:
                                    setattr(s, c_id, val)
                                    has_field_change = True
                            else: 
                                if s.panel_metadata is None: s.panel_metadata = {}
                                if s.panel_metadata.get(c_id) != val:
                                    s.panel_metadata[c_id] = val
                                    has_field_change = True
                    
                    if has_field_change: 
                        if s.panel_metadata is not None:
                            s.panel_metadata = dict(s.panel_metadata)
                        db.add(ActionLog(sample_id=s.id, action_type="데이터 갱신", previous_state=old_status, new_state=old_status, details="상세 항목 수정"))
                        upd += 1 # 이 한 줄이 없어서 기존에는 데이터가 날아갔습니다!

                    # 상태 변경 및 특이사항 변경 커밋
                    if old_status != new_status:
                        s.current_status = new_status
                        db.add(ActionLog(sample_id=s.id, action_type="상태 변경", previous_state=old_status, new_state=new_status, details="모달창 상태 갱신"))
                        upd += 1
                        
                    # 🚀 2차 방어: 메모가 바뀌거나 지워졌을 때, 기존 내용을 로그에 확실하게 남김!
                    if old_issue != new_issue:
                        s.issue_comment = new_issue
                        
                        # 기존 메모가 비어있지 않았다면 내용 확보
                        safe_old_issue = old_issue if old_issue else "없음"
                        
                        db.add(ActionLog(
                            sample_id=s.id, 
                            action_type="특이사항 갱신", 
                            previous_state=old_status, 
                            new_state=s.current_status, 
                            # 👇 details 란에 기존 메모와 새 메모를 모두 기록합니다.
                            details=f"[기존 내용]: {safe_old_issue} ➡️ [변경/삭제됨]" 
                        ))
                        upd += 1

            else:
                # 🚀 칸반 보드 드래그 앤 드롭 및 버튼 이동 로직
                group_id, next_s = (None, None)
                if tid == "drag-drop-store" and drag_data: group_id, next_s = drag_data["card_id"].replace("drag-card-", ""), drag_data["new_stage"]
                elif "btn-move-stage" in tid: d = json.loads(tid); group_id, next_s = d["index"], d["next"]

                if group_id:
                    oid, curr_s = group_id.split("___")
                    
                    # 🚀 [5] 제자리 드롭 시 유령 업데이트 방지!
                    if curr_s == next_s:
                        return no_update, False, no_update
                        
                    stages_order = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"]
                    try: curr_idx, next_idx = stages_order.index(curr_s), stages_order.index(next_s)
                    except ValueError: curr_idx, next_idx = 0, 0
                    
                    if next_idx < curr_idx:
                        error_msgs.append(f"🚫 역방향 이동 불가: [{curr_s}] 단계의 카드를 [{next_s}] 단계로 되돌릴 수 없습니다.")
                    else:
                        samples = db.query(Sample).join(Order).filter(Order.order_id == oid, Sample.current_status == curr_s).all()
                        for s in samples:
                            if curr_s == "접수 대기" and next_s != "접수 대기":
                                if s.sample_received != "입고 완료" or not s.receiver_name:
                                    error_msgs.append(f"📦 상자 이동 거부: 실물 입고 확인 및 담당자 정보가 누락되었습니다."); break 
                            
                            old_status = s.current_status
                            s.current_status = next_s
                            db.add(ActionLog(sample_id=s.id, action_type="상태 변경 (일괄)", previous_state=old_status, new_state=next_s, details=f"칸반 이동")); upd += 1

            if error_msgs:
                db.rollback()
                toast_content = html.Div([html.P(msg, className="mb-1") for msg in error_msgs[:2]]) 
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