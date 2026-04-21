from dash import html, dcc, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag # 🚀 기본 표 대신 최강의 AG Grid 도입!
import json
import traceback
from datetime import datetime

from app.core.database import SessionLocal
from app.models._schema import Order, Sample, ActionLog, STAGE_SCHEMA_CONFIG 
from app.pages.base import LimsDashApp

from app.core.rules import LimsRules
from app.ui.shared_ui import create_project_summary_card

# ==========================================
# [1] 화면 레이아웃
# ==========================================
# [1] 화면 레이아웃 정의 부분
def create_kanban_layout():
    return html.Div([
        # 🚀 1. 메인 타이틀 및 설명 (Toast를 여기서 제거)
        html.H3("🧬 NGS 통합 칸반 보드 (실물 입고 및 진행 관리)", className="fw-bold mb-4 text-secondary"),
        html.P("📦 [0. 접수 대기] 상태의 샘플은 실물 아이스박스가 도착했을 때 '입고 완료' 처리 후 다음 단계로 넘길 수 있습니다.", className="text-muted mb-4"),
        
        # 🚀 2. 칸반 보드 영역 (기존 코드 유지)
        html.Div([
            dbc.Row([
                dbc.Col([html.H5("📋 0. 접수 대기", className="fw-bold text-center text-dark bg-light border p-2 rounded shadow-sm"), html.Div(id="kanban-col-0", className="p-2 bg-white rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("📥 1. 접수 완료", className="fw-bold text-center text-white bg-info p-2 rounded shadow-sm"), html.Div(id="kanban-col-1", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("🧪 2. QC 진행", className="fw-bold text-center text-dark bg-warning p-2 rounded shadow-sm"), html.Div(id="kanban-col-2", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("🧬 3. 시퀀싱 진행", className="fw-bold text-center text-white bg-primary p-2 rounded shadow-sm"), html.Div(id="kanban-col-3", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("💻 4. 분석 진행", className="fw-bold text-center text-white bg-success p-2 rounded shadow-sm"), html.Div(id="kanban-col-4", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
                dbc.Col([html.H5("💸 5. 정산 대기", className="fw-bold text-center text-white bg-dark p-2 rounded shadow-sm"), html.Div(id="kanban-col-5", className="p-2 bg-light rounded border", style={"minHeight": "600px"})], style={"minWidth": "280px"}),
            ], className="flex-nowrap g-2") 
        ], style={"overflowX": "auto", "paddingBottom": "20px"}),
        
        dcc.Store(id="current-modal-order-id"),

        # 🚀 3. 상세정보 모달 (중앙 정렬 및 너비 설정 수정)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-detail-title", className="fw-bold")),
            dbc.ModalBody([
                html.Div(id="modal-shared-card-container", className="mb-3"),
                html.Div(
                    id="modal-merge-container", style={"display": "none"},
                    children=[
                        html.Div([
                            html.Strong("🔗 프로젝트 병합: ", className="text-dark me-2"),
                            dbc.Select(id="merge-target-select", options=[], placeholder="합칠 프로젝트 선택...", style={"width": "200px"}, className="me-2"),
                            dbc.Button("병합 실행", id="btn-execute-merge", color="warning", size="sm", className="fw-bold")
                        ], className="d-flex align-items-center p-2 mb-3 rounded", style={"backgroundColor": "#fff3cd", "border": "1px solid #ffe69c"})
                    ]
                ),
                dag.AgGrid(
                    id="modal-datatable",
                    rowData=[], columnDefs=[],
                    defaultColDef={"resizable": True, "sortable": True, "filter": True},
                    dashGridOptions={
                        "rowHeight": 45, 
                        "singleClickEdit": True, 
                        "stopEditingWhenCellsLoseFocus": True
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
        id="sample-detail-modal", 
        size="xl", 
        is_open=False, 
        centered=True, 
        backdrop="static",
        # 🚀 포인트: style에서 maxWidth를 제거하고 대신 dialog에 직접 스타일을 주거나,
        # 아래와 같이 flex로 중앙 정렬을 강제합니다.
        dialog_style={"maxWidth": "1400px", "width": "95%"}
        ),

        # 🚀 4. 알림창(Toast) 및 시스템 제어 도구 (레이아웃 맨 끝으로 이동)
        html.Div(
            dbc.Toast(
                id="gatekeeper-toast", header="⚠️ 알림",
                is_open=False, dismissable=True, icon="danger",
                style={"position": "fixed", "top": 20, "right": 20, "width": 350, "zIndex": 9999}
            )
        ),
        dcc.Store(id="kanban-update-trigger", data=0), 
        dcc.Store(id="drag-drop-store", data=None),
        html.Button(id="btn-hidden-drop", style={"display": "none"}), 
        html.Div(id="dummy-js-output", style={"display": "none"})

    ], style={"overflowX": "hidden", "position": "relative", "padding": "20px"}) # 🚀 전체 가로 스크롤 방지
# ==========================================
# [2] 카드 생성 함수
# ==========================================
def make_batch_card(order_obj, status, sample_count, has_issue):
    total_revenue = (order_obj.sales_unit_price or 0) * sample_count
    
    action_rule = LimsRules.STAGE_ACTIONS.get(status, {"text": "다음 단계", "color": "info", "next": "완료"})
    btn_text, btn_color, next_stage = action_rule["text"], action_rule["color"], action_rule["next"]
    group_id = f"{order_obj.order_id}___{status}"
    
    stage_specific_content = []
    if status == "접수 대기": stage_specific_content.extend([html.Small("⏳ 실물 샘플 입고 대기중", className="text-danger fw-bold d-block mb-1"), html.Small(f"🏢 기관: {order_obj.facility}", className="text-muted d-block")])
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
                    if s.current_status in ["완료", "보류/실패"]: continue
                    stat = s.current_status if s.current_status in status_idx else "접수 대기"
                    key = (o.order_id, stat)
                    if key not in groups: groups[key] = {"order": o, "count": 0, "has_issue": False}
                    groups[key]["count"] += 1
                    if s.issue_comment and str(s.issue_comment).strip() not in ["", "None", "nan"]: groups[key]["has_issue"] = True

            for (oid, stat), data in groups.items():
                cols[status_idx.get(stat, 0)].append(make_batch_card(data["order"], stat, data["count"], data["has_issue"]))
            return cols
        finally: db.close()

    # 🚀 AG Grid 컬럼 및 데이터 렌더링
    @dash_app.callback(
        [Output("sample-detail-modal", "is_open"), Output("modal-detail-title", "children"), Output("modal-shared-card-container", "children"),
         Output("modal-datatable", "rowData"), Output("modal-datatable", "columnDefs"),  # 🚀 rowData, columnDefs 로 변경
         Output("current-modal-order-id", "data"), Output("kanban-update-trigger", "data", allow_duplicate=True),
         Output("modal-merge-container", "style"), Output("merge-target-select", "options"), Output("merge-target-select", "value")],
        [Input({"type": "btn-open-modal", "order_id": ALL, "stage": ALL}, "n_clicks"), Input("btn-execute-merge", "n_clicks"), Input("btn-save-modal", "n_clicks")],
        [State("sample-detail-modal", "is_open"), State("current-modal-order-id", "data"), State("merge-target-select", "value"), State("kanban-update-trigger", "data")],
        prevent_initial_call=True
    )
    def handle_modal(open_clicks, merge_clicks, save_clicks, is_open, current_oid, merge_target, trig):
        if not ctx.triggered: return [no_update] * 10
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        if tid == "btn-save-modal": return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

        db = SessionLocal()
        merged = False
        try:
            oid = current_oid
            stage = "접수 대기"

            if "btn-open-modal" in tid:
                if all(c is None for c in open_clicks): return [no_update] * 10
                btn_data = json.loads(tid)
                oid, stage = btn_data["order_id"], btn_data["stage"]
            elif tid == "btn-execute-merge" and merge_target and merge_target != oid:
                target_order = db.query(Order).filter(Order.order_id == merge_target).first()
                current_order = db.query(Order).filter(Order.order_id == oid).first()
                if target_order and current_order:
                    for s in target_order.samples: s.order_id = current_order.id
                    db.delete(target_order)
                    db.commit()
                    merged = True

            if not oid: return [no_update] * 10
            order = db.query(Order).filter(Order.order_id == oid).first()
            if not order: return [no_update] * 10

            samples = [s for s in order.samples if s.current_status == stage]

            merge_style, merge_opts = {"display": "none"}, []
            if stage == "접수 대기":
                merge_style = {"display": "block"}
                other_orders = db.query(Order).filter(Order.order_id != oid).all()
                merge_opts = [{"label": o.order_id, "value": o.order_id} for o in other_orders if any(s.current_status == "접수 대기" for s in o.samples)]

            # 🚀 AG Grid용 컬럼 정의
            columns = [
                {"headerName": "Patient ID / Sample ID", "field": "sample_name", "editable": False, "width": 150},
                {"headerName": "패널", "field": "target_panel", "editable": False, "width": 100},
            ]

            stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})
            for col in stage_config["columns"]:
                ag_col = {"headerName": col["name"], "field": col["id"], "editable": col.get("editable", True)}
                
                # Dropdown 연결
                if col.get("presentation") == "dropdown":
                    ag_col["cellEditor"] = "agSelectCellEditor"
                    if col["id"] == "is_dropped": ag_col["cellEditorParams"] = {"values": ["유지", "제외"]}
                    elif col["id"] == "visual_inspection": ag_col["cellEditorParams"] = {"values": ["Pass", "Fail", "대기중"]}
                    elif col["id"] == "sample_received": ag_col["cellEditorParams"] = {"values": ["대기중", "입고 완료"]}
                    elif col["id"] == "extraction_status": ag_col["cellEditorParams"] = {"values": ["O", "X", "-"]}
                columns.append(ag_col)

            columns.extend([
                {"headerName": "진행 상태", "field": "current_status", "editable": True, "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "보류/실패"]}, "width": 120},
                {
                    "headerName": "특이사항/메모", 
                    "field": "issue_comment", 
                    "editable": True, 
                    # 🚀 이것이 진짜 Textarea 편집기를 띄우는 AG Grid의 마법입니다!
                    "cellEditor": "agLargeTextCellEditor", 
                    "cellEditorPopup": True, # 클릭 시 팝업 형태로 등장하여 자유롭게 다중 줄 입력 가능
                    "cellEditorParams": {"maxLength": 1000, "rows": 6, "cols": 50},
                    "flex": 1, # 남은 공간을 모두 채움
                    "minWidth": 250,
                    "suppressKeyboardEvent": {"function": "params.event.key === 'Enter'"}
                }
            ])

            table_data = []
            for s in samples:
                row_dict = {
                    "id": s.id, "sample_name": s.sample_name, "target_panel": s.target_panel,
                    "current_status": s.current_status, "issue_comment": s.issue_comment or "", "is_dropped": "유지"
                }
                for col in stage_config["columns"]:
                    col_id = col["id"]
                    if hasattr(s, col_id): row_dict[col_id] = getattr(s, col_id) or ""
                    elif s.panel_metadata and col_id in s.panel_metadata: row_dict[col_id] = s.panel_metadata[col_id]
                table_data.append(row_dict)

            shared_project_card = create_project_summary_card(order, len(samples))
            new_trig = (trig or 0) + 1 if merged else no_update

            return (
                True, f"📋 프로젝트 상세 ({stage})", shared_project_card,
                table_data, columns, # 🚀 rowData와 columnDefs 반환
                oid, new_trig, merge_style, merge_opts, None
            )
        finally: db.close()

    # 🚀 데이터 저장 (AG Grid rowData 수신)
    @dash_app.callback(
        [Output("kanban-update-trigger", "data", allow_duplicate=True), Output("gatekeeper-toast", "is_open"), Output("gatekeeper-toast", "children")],
        [Input("drag-drop-store", "data"), Input({"type": "btn-move-stage", "index": ALL, "next": ALL}, "n_clicks"), Input("btn-save-modal", "n_clicks")],
        [State("modal-datatable", "rowData"), State("kanban-update-trigger", "data"), State("modal-detail-title", "children")], # 🚀 rowData 받기
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
                    if s:
                        old_status, old_issue = s.current_status, s.issue_comment or ""
                        
                        if row.get("is_dropped") == "제외" and old_status != "보류/실패":
                            s.current_status = "보류/실패"
                            s.issue_comment = f"[접수 제외] {row.get('issue_comment', '')}"
                            db.add(ActionLog(sample_id=s.id, action_type="접수 제외", previous_state=old_status, new_state="보류/실패", details=s.issue_comment))
                            upd += 1; continue
                            
                        if s.current_status == stage and row.get("current_status") not in [stage, "보류/실패"]:
                            is_passed = True
                            for col in stage_config["columns"]:
                                val = str(row.get(col["id"], "")).strip()
                                if col.get("required") and not val:
                                    error_msgs.append(f"[{s.sample_name}] 필수 항목 '{col['name']}' 입력 누락."); is_passed = False
                                if col.get("pass_value") and val != col.get("pass_value"):
                                    error_msgs.append(f"[{s.sample_name}] '{col['name']}' 통과 실패."); is_passed = False
                            if not is_passed: continue 

                        meta_updated = False
                        for col in stage_config["columns"]:
                            c_id = col["id"]
                            if c_id in row:
                                val = row[c_id]
                                if col.get("type") == "numeric":
                                    try: val = float(val) if str(val).strip() else None
                                    except ValueError: val = None
                                
                                if hasattr(s, c_id): setattr(s, c_id, val)
                                else: 
                                    if s.panel_metadata is None: s.panel_metadata = {}
                                    s.panel_metadata[c_id] = val
                                    meta_updated = True
                        
                        if meta_updated: s.panel_metadata = dict(s.panel_metadata)

                        s.current_status = row.get("current_status", s.current_status)
                        s.issue_comment = row.get("issue_comment", "")
                        
                        if old_status != s.current_status:
                            db.add(ActionLog(sample_id=s.id, action_type="상태 변경", previous_state=old_status, new_state=s.current_status, details="모달창 상세 저장")); upd += 1
                        elif old_issue != s.issue_comment:
                            db.add(ActionLog(sample_id=s.id, action_type="특이사항 갱신", previous_state=old_status, new_state=s.current_status, details=f"메모 수정")); upd += 1

            else:
                group_id, next_s = (None, None)
                if tid == "drag-drop-store" and drag_data: group_id, next_s = drag_data["card_id"].replace("drag-card-", ""), drag_data["new_stage"]
                elif "btn-move-stage" in tid: d = json.loads(tid); group_id, next_s = d["index"], d["next"]

                if group_id:
                    oid, curr_s = group_id.split("___")
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
            }, 800); return "";
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