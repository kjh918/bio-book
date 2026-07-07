from dash import html, dcc, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import base64
import io
import json
import traceback
from collections import defaultdict

from app.core.database import SessionLocal
from app.schema.objects import Order, Sample, ActionLog
from app.schema.workflow import workflow_manager
from app.pages.base import LimsDashApp
from app.ui.shared_ui import create_project_summary_card
from dash_iconify import DashIconify

# ============================================================
# 동적 테마 팔레트 (스테이지 인덱스에 따라 자동 배정)
# ============================================================
THEME_PALETTE = [
    {"bg": "#f1f5f9", "text_hex": "#475569", "border": "border-secondary", "text_class": "text-secondary"},
    {"bg": "#e0f2fe", "text_hex": "#0284c7", "border": "border-info", "text_class": "text-info"},
    {"bg": "#fef3c7", "text_hex": "#d97706", "border": "border-warning", "text_class": "text-warning"},
    {"bg": "#e0e7ff", "text_hex": "#4f46e5", "border": "border-primary", "text_class": "text-primary"},
    {"bg": "#DFF5E1", "text_hex": "#18bc9c", "border": "border-success", "text_class": "text-success"},
    {"bg": "#f3e8ff", "text_hex": "#9333ea", "border": "border-dark", "text_class": "text-dark"},
    {"bg": "#ffe4e6", "text_hex": "#e11d48", "border": "border-danger", "text_class": "text-danger"},
]

def get_theme(index: int, total: int) -> dict:
    """총 스테이지 개수에 맞춰 적절한 테마 색상을 분배하여 반환"""
    if total <= 1: return THEME_PALETTE[0]
    idx = int((index / (total - 1)) * (len(THEME_PALETTE) - 1))
    return THEME_PALETTE[idx]


# ============================================================
# 헬퍼 함수: 동적 데이터 Read/Write
# ============================================================
def _read_field(s: Sample, col_id: str):
    if hasattr(Sample, col_id): return getattr(s, col_id, None)
    return (s.panel_metadata or {}).get(col_id)

def _write_field(s: Sample, col_id: str, val, new_meta: dict) -> bool:
    if hasattr(Sample, col_id):
        if getattr(s, col_id, None) != val:
            setattr(s, col_id, val)
            return True
        return False
    else:
        if new_meta.get(col_id) != val:
            new_meta[col_id] = val
            return True
        return False


# ============================================================
# [1] 레이아웃 (껍데기만 남기고 내부는 콜백으로 동적 생성)
# ============================================================
def create_kanban_layout():
    return html.Div([
        # ── 헤더 및 컨트롤러 ──
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:flow", className="me-2 text-dark"),
                         "DYNAMIC WORKFLOW BOARD"], className="fw-bold text-dark mb-0"),
            ]),
            html.Div([
                dbc.Input(id="kanban-search-input", placeholder="Project / Order / 기관 검색…", size="sm", style={"width": "260px"}, debounce=True),
                # 🚀 선택된 패널에 따라 Workflow 구조가 통째로 바뀝니다.
                dbc.Select(id="kanban-panel-filter",
                           options=[{"label": "전체(Standard)", "value": "ALL"},
                                    {"label": "WGS", "value": "WGS"},
                                    {"label": "WES", "value": "WES"},
                                    {"label": "WTS", "value": "WTS"},
                                    {"label": "TSO500", "value": "TSO500"}],
                           value="ALL", size="sm", style={"width": "130px"}),
            ], className="d-flex gap-2 align-items-center")
        ], className="page-title-header d-flex justify-content-between align-items-center mb-3"),

        # ── 보드 렌더링 영역 (동적 생성) ──
        html.Div(id="dynamic-board-container", style={"overflowX": "auto", "paddingBottom": "20px"}),

        # ── 숨겨진 스토어 ──
        dcc.Store(id="current-modal-order-id"),
        dcc.Store(id="current-modal-stage"),
        dcc.Store(id="current-modal-panel"), # 🚀 모달에서도 패널 정보를 알 수 있게 저장
        dcc.Store(id="kanban-update-trigger", data=0),
        dcc.Store(id="board-rendered-trigger", data=0), # JS 바인딩용
        dcc.Store(id="drag-drop-store", data=None),
        dcc.Store(id="modal-rowdata-synced", data=[]),
        dcc.Download(id="download-modal-excel"),
        html.Button(id="btn-hidden-drop", style={"display": "none"}),
        html.Div(id="dummy-js-output", style={"display": "none"}),

        # ── 토스트 & 모달 ──
        html.Div(dbc.Toast(id="gatekeeper-toast", header="⚠️ 알림", is_open=False, dismissable=True, icon="danger", style={"position": "fixed", "top": 20, "right": 20, "width": 380, "zIndex": 9999})),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-detail-title", className="fw-bold")),
            dbc.ModalBody([
                html.Div(id="modal-shared-card-container", className="mb-3"),
                html.Div([
                    html.Div([
                        html.Strong([DashIconify(icon="carbon:edit", className="me-1"), "일괄 변경:"], className="text-secondary me-2", style={"fontSize": "0.85rem"}),
                        dbc.Select(id="bulk-col-select", options=[], placeholder="항목 선택…", style={"width": "160px"}, className="me-2 shadow-sm form-select-sm"),
                        dbc.Input(id="bulk-val-input", placeholder="입력값…", style={"width": "140px"}, className="me-2 shadow-sm form-control-sm"),
                        dbc.Button("적용", id="btn-bulk-apply", color="primary", size="sm", className="fw-bold shadow-sm rounded-3"),
                    ], className="d-flex align-items-center"),
                    html.Div([
                        dbc.Button([DashIconify(icon="carbon:download", className="me-1"), "엑셀 다운로드"], id="btn-export-excel", color="light", size="sm", className="me-2 fw-bold shadow-sm border rounded-3 text-secondary"),
                        dcc.Upload(id="upload-overwrite-excel", children=dbc.Button([DashIconify(icon="carbon:upload", className="me-1"), "엑셀 덮어쓰기"], color="white", size="sm", className="fw-bold shadow-sm border border-primary text-primary rounded-3"), multiple=False, className="d-inline-block")
                    ], className="d-flex align-items-center")
                ], className="d-flex justify-content-between align-items-center p-3 mb-3 rounded-4 border", style={"backgroundColor": "#f8fafc", "borderColor": "#e2e8f0"}),
                dag.AgGrid(id="modal-datatable", rowData=[], columnDefs=[], defaultColDef={"resizable": True, "sortable": True, "filter": True}, dashGridOptions={"rowHeight": 45, "singleClickEdit": True, "stopEditingWhenCellsLoseFocus": True, "rowSelection": "multiple", "suppressRowClickSelection": True}, style={"height": "420px", "width": "100%"}, className="ag-theme-alpine border-0 shadow-sm rounded-3")
            ], style={"maxHeight": "82vh", "overflowY": "auto"}),
            dbc.ModalFooter([
                html.Span("💡 체크박스 선택 시 해당 검체만 다음 단계로 이동합니다.", className="text-primary small fw-bold me-auto"),
                dbc.Button([DashIconify(icon="carbon:save", className="me-1"), "변경사항 저장"], id="btn-save-modal", color="primary", className="fw-bold rounded-3 shadow-sm px-4")
            ], className="border-top-0 bg-light rounded-bottom-4")
        ], id="sample-detail-modal", size="xl", is_open=False, centered=True, backdrop="static", dialog_style={"maxWidth": "1450px", "width": "95%"}, content_class_name="rounded-4 border-0 shadow-lg"),
    ])


# ============================================================
# [2] 동적 카드 생성기
# ============================================================
def make_order_card(order_obj, status, samples_in_status, panel_name, theme):
    group_id = f"{order_obj.order_id}___{status}"
    has_issue = any(s.issue_comment and str(s.issue_comment).strip() not in ["", "None", "nan"] for s in samples_in_status)
    
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.Div(order_obj.order_id, className=f"fw-bold {theme['text_class']} mb-1", style={"fontSize": "0.92rem", "wordBreak": "break-all"}),
                html.Div(f"{order_obj.facility}-{order_obj.client_team}: {order_obj.client_name or '-'}", className="text-muted mb-1", style={"fontSize": "0.78rem"}),
                html.Div(f"접수일: {order_obj.reception_date}", className="text-muted mb-2", style={"fontSize": "0.78rem"}),
                html.Div([
                    html.Span(f"{len(samples_in_status)}건", className="badge bg-secondary me-1"),
                    html.Span("⚠️ 이슈", className="badge bg-danger") if has_issue else None,
                ], className="mb-3"),
                # 🚀 모달 오픈 시 패널 정보도 함께 전달
                dbc.Button("상세보기", id={"type": "btn-open-modal", "order_id": order_obj.order_id, "stage": status, "panel": panel_name}, color="light", size="sm", className="w-100 fw-bold border text-secondary", style={"fontSize": "0.8rem"})
            ], className="p-3")
        ], className=f"shadow-sm border-start border-4 {theme['border']} rounded-3")
    ], draggable=True, id=f"drag-card-{group_id}", style={"cursor": "grab"}, className="mb-2")


# ============================================================
# [3] 통합 콜백
# ============================================================
def register_kanban_callbacks(dash_app):

    # ── 1. 스키마 기반 동적 보드 렌더링 ──
    @dash_app.callback(
        [Output("dynamic-board-container", "children"), Output("board-rendered-trigger", "data")],
        [Input("kanban-update-trigger", "data"),
         Input("kanban-search-input", "value"),
         Input("kanban-panel-filter", "value")]
    )
    def render_dynamic_board(trigger, search_kw, panel_filter):
        db = SessionLocal()
        try:
            # 🚀 1. WorkflowManager에서 해당 패널의 스테이지 구조를 가져옴
            stage_names = workflow_manager.get_stage_names(panel_filter)
            total_stages = len(stage_names)
            
            # 스테이지별 컨테이너 초기화
            stage_cols_data = {s_name: [] for s_name in stage_names}

            # 2. DB 필터링
            all_orders = db.query(Order).join(Sample).all()
            kw = (search_kw or "").strip().lower()

            for o in all_orders:
                if kw and not any([kw in (o.order_id or "").lower(), kw in (o.facility or "").lower(), kw in (o.client_team or "").lower(), any(kw in (s.project_name or "").lower() for s in o.samples)]):
                    continue
                
                # 타겟 패널 샘플만 추출
                samples = [s for s in o.samples if panel_filter == "ALL" or not panel_filter or s.target_panel == panel_filter]
                if not samples: continue
                
                by_stage = defaultdict(list)
                for s in samples:
                    by_stage[s.current_status].append(s)
                
                # 🚀 3. 동적 테마 배정 및 카드 삽입
                for stage_name, stage_samples in by_stage.items():
                    if stage_name in stage_cols_data:
                        idx = stage_names.index(stage_name)
                        theme = get_theme(idx, total_stages)
                        card = make_order_card(o, stage_name, stage_samples, panel_filter or "ALL", theme)
                        stage_cols_data[stage_name].append(card)

            # 🚀 4. 동적 UI Layout 조립
            board_columns = []
            for i, s_name in enumerate(stage_names):
                theme = get_theme(i, total_stages)
                
                # 빈 컬럼 처리
                col_content = stage_cols_data[s_name] if stage_cols_data[s_name] else [html.Div("빈 단계", className="text-center text-muted small mt-5")]
                
                # 컬럼 헤더 및 바디 
                header = html.Div(s_name, className="fw-bold text-center", style={"backgroundColor": theme["bg"], "color": theme["text_hex"], "fontSize": "0.9rem", "padding": "10px 6px", "borderRadius": "8px", "letterSpacing": "0.03em"})
                body = html.Div(col_content, className="kanban-drop-zone", **{"data-stage-name": s_name}, style={"minHeight": "600px", "backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "2px dashed #e2e8f0", "marginTop": "8px", "padding": "8px"})
                
                board_columns.append(dbc.Col([header, body], style={"minWidth": "300px"}))

            final_layout = dbc.Row(board_columns, className="flex-nowrap g-3")
            
            # JS 트리거 값 변경하여 드래그앤드롭 이벤트 리바인딩
            return final_layout, (trigger or 0) + 1 
            
        finally:
            db.close()

    # ── 2. 스키마 기반 모달 동적 생성 ──
    @dash_app.callback(
        [Output("sample-detail-modal", "is_open"), Output("modal-detail-title", "children"), Output("modal-shared-card-container","children"),
         Output("modal-datatable", "rowData"), Output("modal-datatable", "columnDefs"), Output("current-modal-order-id", "data"),
         Output("current-modal-stage", "data"), Output("current-modal-panel", "data"), Output("bulk-col-select", "options"),
         Output("modal-rowdata-synced", "data", allow_duplicate=True), Output("modal-datatable", "selectedRows")],
        [Input({"type": "btn-open-modal", "order_id": ALL, "stage": ALL, "panel": ALL}, "n_clicks"), Input("btn-save-modal", "n_clicks")],
        [State("sample-detail-modal", "is_open"), State("current-modal-order-id", "data"), State("current-modal-stage", "data"), State("current-modal-panel", "data")],
        prevent_initial_call=True
    )
    def handle_modal(open_clicks, save_clicks, is_open, current_oid, current_stage, current_panel):
        if not ctx.triggered: return [no_update] * 11
        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        if tid == "btn-save-modal": return (False,) + (no_update,) * 10

        db = SessionLocal()
        try:
            oid, stage, panel = current_oid, current_stage, current_panel

            if "btn-open-modal" in tid:
                if all(c is None for c in open_clicks): return [no_update] * 11
                btn_data  = json.loads(tid)
                oid, stage, panel = btn_data["order_id"], btn_data["stage"], btn_data["panel"]

            if not oid: return [no_update] * 11
            order = db.query(Order).filter(Order.order_id == oid).first()
            if not order: return [no_update] * 11

            samples = [s for s in order.samples if s.current_status == stage and (panel == "ALL" or s.target_panel == panel)]
            
            # 🚀 Schema Config 로드
            stage_config = workflow_manager.get_stage_config(panel, stage)

            columns = LimsDashApp.get_base_grid_columns(include_project=False)
            if columns:
                columns[0]["checkboxSelection"] = True
                columns[0]["headerCheckboxSelection"] = True

            bulk_options = [{"label": col["name"], "value": col["id"]} for col in stage_config["columns"] if col.get("editable", True)]

            for col in stage_config["columns"]:
                ag_col = {"headerName": col["name"], "field": col["id"], "editable": col.get("editable", True)}
                if col.get("presentation") == "dropdown":
                    ag_col["cellEditor"] = "agSelectCellEditor"
                    if "options" in col: ag_col["cellEditorParams"] = {"values": col["options"]}
                if col.get("type") == "numeric": ag_col["type"] = "numericColumn"
                columns.append(ag_col)

            bulk_options.append({"label": "📝 특이사항/메모", "value": "issue_comment"})
            columns.extend([
                {"headerName": "진행 상태", "field": "current_status", "editable": False, "width": 110, "cellStyle": {"color": "#64748b", "backgroundColor": "#f8fafc"}},
                {"headerName": "특이사항/메모", "field": "issue_comment", "editable": True, "cellEditor": "agLargeTextCellEditor", "cellEditorPopup": True, "cellEditorParams": {"maxLength": 1000, "rows": 6, "cols": 50}, "flex": 1, "minWidth": 220}
            ])

            table_data = []
            for s in samples:
                row_dict = {"id": s.id, "order_id": s.order_id, "sample_id": s.sample_id, "sample_name": s.sample_name, "target_panel": s.target_panel, "current_status": s.current_status, "issue_comment": s.issue_comment or ""}
                for col in stage_config["columns"]:
                    val = _read_field(s, col["id"])
                    row_dict[col["id"]] = val if val is not None else ""
                table_data.append(row_dict)

            title = f"📋 {oid} · {stage} ({len(samples)}건)"
            return (True, title, create_project_summary_card(order, len(samples)), table_data, columns, oid, stage, panel, bulk_options, table_data, [])
        finally: db.close()

    # ── 3. 동기화 및 엑셀 다운로드 (공통 유지) ──
    @dash_app.callback(Output("modal-rowdata-synced", "data", allow_duplicate=True), Input("modal-datatable", "cellValueChanged"), State("modal-datatable", "rowData"), prevent_initial_call=True)
    def sync_rowdata(_, row_data): return row_data if row_data else no_update

    @dash_app.callback(Output("download-modal-excel", "data"), Input("btn-export-excel", "n_clicks"), [State("modal-datatable", "rowData"), State("current-modal-order-id", "data"), State("current-modal-stage", "data")], prevent_initial_call=True)
    def export_excel(n, data, oid, stage):
        if data: return dcc.send_data_frame(pd.DataFrame(data).drop(columns=["id"], errors="ignore").to_excel, f"{oid}_{stage}.xlsx", index=False)
        return no_update

    @dash_app.callback(Output("modal-datatable", "rowData", allow_duplicate=True), [Input("btn-bulk-apply", "n_clicks"), Input("upload-overwrite-excel", "contents")], [State("bulk-col-select", "value"), State("bulk-val-input", "value"), State("modal-datatable", "rowData")], prevent_initial_call=True)
    def bulk_apply(btn, contents, col, val, rows):
        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        if tid == "btn-bulk-apply" and col and val is not None: return [{**r, col: str(val).strip()} for r in rows]
        if tid == "upload-overwrite-excel" and contents:
            up_dict = pd.read_excel(io.BytesIO(base64.b64decode(contents.split(",")[1]))).to_dict("records")
            return [{**r, **{k: str(v).strip() for k, v in next((u for u in up_dict if str(u.get("sample_name")) == str(r.get("sample_name"))), {}).items() if k in r and pd.notna(v) and k not in ["id", "sample_name", "target_panel"]}} for r in rows]
        return no_update

    # ── 4. 스키마 기반 저장 및 이동 (부분이동/전체이동) ──
    @dash_app.callback(
        [Output("kanban-update-trigger", "data", allow_duplicate=True), Output("gatekeeper-toast", "is_open"), Output("gatekeeper-toast", "children")],
        [Input("drag-drop-store", "data"), Input("btn-save-modal", "n_clicks")],
        [State("modal-datatable", "rowData"), State("modal-rowdata-synced", "data"), State("kanban-update-trigger", "data"), 
         State("current-modal-stage", "data"), State("current-modal-panel", "data"), State("modal-datatable", "selectedRows")],
        prevent_initial_call=True
    )
    def update_data(drag_data, save_click, grid_data, sync_data, trig, m_stage, m_panel, selected_rows):
        if not ctx.triggered or not ctx.triggered[0]["value"]: return no_update, False, no_update
        tid, db, errs, upd = ctx.triggered[0]["prop_id"].split(".")[0], SessionLocal(), [], 0

        try:
            # ── [A] 모달 저장 (부분이동) ──
            if tid == "btn-save-modal":
                stage_config = workflow_manager.get_stage_config(m_panel, m_stage)
                next_stage = workflow_manager.get_next_stage_name(m_panel, m_stage) # 🚀 Schema 기반 자동 계산
                sel_ids = [str(r.get("id")) for r in (selected_rows or []) if r.get("id")]
                
                for row in (sync_data or grid_data or []):
                    s = db.query(Sample).filter(Sample.id == row.get("id")).first()
                    if not s: continue

                    new_meta, is_changed = dict(s.panel_metadata or {}), False
                    for col in stage_config["columns"]:
                        c_id = col["id"]
                        if c_id not in row: continue
                        val = str(row[c_id]).strip() if isinstance(row[c_id], str) else row[c_id]
                        val = float(val) if col.get("type") == "numeric" and val else val if val != "" else None
                        if _write_field(s, c_id, val, new_meta): is_changed = True

                    st_changed = False
                    if str(s.id) in sel_ids and s.current_status == m_stage and s.current_status != next_stage:
                        if m_stage == "접수 대기": # 하드 게이트키퍼 (임시 유지)
                            if str(getattr(s, "sample_received", "")).replace(" ","") != "입고완료": errs.append(f"📦 [{s.sample_name}] 입고 완료 상태여야 합니다.")
                            if not getattr(s, "receiver_name", ""): errs.append(f"👤 [{s.sample_name}] 입고 담당자가 필요합니다.")
                        if not errs:
                            s.current_status = next_stage
                            st_changed = True

                    if is_changed or st_changed:
                        s.panel_metadata = new_meta
                        db.add(ActionLog(sample_id=s.id, action_type="상태 변경" if st_changed else "데이터 갱신", previous_state=m_stage, new_state=next_stage if st_changed else m_stage, details="모달 처리"))
                        db.add(s); upd += 1
                        
                    n_issue = str(row.get("issue_comment", "")).strip()
                    if (s.issue_comment or "") != n_issue:
                        s.issue_comment = n_issue
                        db.add(ActionLog(sample_id=s.id, action_type="특이사항 갱신", previous_state=m_stage, new_state=m_stage, details="이슈 수정"))
                        db.add(s); upd += 1

            # ── [B] 드래그&드롭 저장 (일괄이동) ──
            elif tid == "drag-drop-store" and drag_data:
                oid, curr_s = drag_data["card_id"].replace("drag-card-", "").split("___")
                next_s = drag_data["new_stage"]
                
                # 🚀 Schema 기반 역방향 검증
                if workflow_manager.is_backward_move("ALL", curr_s, next_s):
                    errs.append(f"🚫 역방향 이동 불가: [{curr_s}] → [{next_s}]")
                else:
                    samples = db.query(Sample).join(Order).filter(Order.order_id == oid, Sample.current_status == curr_s).all()
                    if curr_s == "접수 대기":
                        for s in samples:
                            if str(getattr(s, "sample_received", "")).replace(" ","") != "입고완료": errs.append(f"📦 [{s.sample_name}] 입고 확인 필요")
                    if not errs:
                        for s in samples:
                            s.current_status = next_s
                            db.add(ActionLog(sample_id=s.id, action_type="상태 변경", previous_state=curr_s, new_state=next_s, details="칸반 D&D"))
                            db.add(s)
                        upd += 1

            if errs:
                db.rollback()
                return no_update, True, html.Div([html.P(m, className="mb-1 text-danger fw-bold") for m in errs[:5]])
            if upd > 0:
                db.commit()
                return (trig or 0) + 1, False, no_update
            return no_update, False, no_update
        finally: db.close()

    # ── 5. 동적 클라이언트사이드 스크립트 (완전 범용화) ──
    # 🚀 data-stage-name 속성을 읽어오도록 수정하여 JS 내부에 배열 하드코딩 완전 제거
    dash_app.clientside_callback(
        """
        function(trigger) {
            setTimeout(function() {
                var cards = document.querySelectorAll('[draggable="true"]');
                cards.forEach(function(card) {
                    card.ondragstart = function(e) { e.dataTransfer.setData('text', card.id); };
                });
                
                var dropZones = document.querySelectorAll('.kanban-drop-zone');
                dropZones.forEach(function(col) {
                    col.ondragover = function(e) { e.preventDefault(); };
                    col.ondrop = function(e) {
                        e.preventDefault();
                        var id = e.dataTransfer.getData('text');
                        var targetStage = col.getAttribute('data-stage-name'); // 🚀 태그에서 스테이지 이름 추출
                        if (id && targetStage) {
                            window.latestDropData = { card_id: id, new_stage: targetStage, ts: Date.now() };
                            document.getElementById('btn-hidden-drop').click();
                        }
                    };
                });
            }, 800); // UI 렌더링 대기
            return "";
        }
        """,
        Output("dummy-js-output", "children"),
        Input("board-rendered-trigger", "data") # 🚀 보드 렌더링 완료 시점에 발동
    )

    dash_app.clientside_callback(
        "function(n){ return window.latestDropData || window.dash_clientside.no_update; }",
        Output("drag-drop-store", "data"), Input("btn-hidden-drop", "n_clicks")
    )


# ============================================================
# [4] 앱 팩토리
# ============================================================
def create_kanban_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_kanban_layout)
    app = lims.get_app()
    register_kanban_callbacks(app)
    return app