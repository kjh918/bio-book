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
from collections import defaultdict

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


# ============================================================
# 상수 정의
# ============================================================
STAGES = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"]
STATUS_IDX = {s: i for i, s in enumerate(STAGES)}

STATUS_THEME = {
    "접수 대기":  {"border": "border-secondary", "text": "text-secondary", "badge": "secondary", "bg": "#f1f5f9", "fg": "#475569"},
    "접수 완료":  {"border": "border-info",      "text": "text-info",      "badge": "info",      "bg": "#e0f2fe", "fg": "#0284c7"},
    "QC 진행":    {"border": "border-warning",   "text": "text-warning",   "badge": "warning",   "bg": "#fef3c7", "fg": "#d97706"},
    "시퀀싱 진행":{"border": "border-primary",   "text": "text-primary",   "badge": "primary",   "bg": "#e0e7ff", "fg": "#4f46e5"},
    "분석 진행":  {"border": "border-success",   "text": "text-success",   "badge": "success",   "bg": "#DFF5E1", "fg": "#18bc9c"},
    "정산 대기":  {"border": "border-dark",      "text": "text-dark",      "badge": "dark",      "bg": "#f3e8ff", "fg": "#9333ea"},
}


# ============================================================
# [1] 레이아웃
# ============================================================
def create_kanban_layout():

    def col_header(label, bg, fg):
        return html.Div(label, className="fw-bold text-center", style={
            "backgroundColor": bg, "color": fg,
            "fontSize": "0.9rem", "padding": "10px 6px",
            "borderRadius": "8px", "letterSpacing": "0.03em"
        })

    def col_body():
        return {
            "minHeight": "600px", "backgroundColor": "#f8fafc",
            "borderRadius": "8px", "border": "2px dashed #e2e8f0",
            "marginTop": "8px", "padding": "8px"
        }

    col_defs = [
        ("접수 대기",   "#f1f5f9", "#475569"),
        ("접수 완료",   "#e0f2fe", "#0284c7"),
        ("QC 진행",     "#fef3c7", "#d97706"),
        ("시퀀싱 진행", "#e0e7ff", "#4f46e5"),
        ("분석 진행",   "#DFF5E1", "#18bc9c"),
        ("정산 대기",   "#f3e8ff", "#9333ea"),
    ]

    return html.Div([
        # ── 헤더 ──────────────────────────────────────────────
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:flow", className="me-2 text-dark"), "WORKFLOW BOARD"],
                        className="fw-bold text-dark mb-0"),
            ]),
            # 필터 영역
            html.Div([
                dbc.Input(id="kanban-search-input", placeholder="Project / Order / 기관 검색…",
                          size="sm", style={"width": "260px"}, debounce=True),
                dbc.Select(id="kanban-panel-filter",
                           options=[{"label": "전체 패널", "value": "ALL"},
                                    {"label": "WES", "value": "WES"},
                                    {"label": "WGS", "value": "WGS"},
                                    {"label": "WTS", "value": "WTS"}],
                           value="ALL", size="sm", style={"width": "130px"}),
            ], className="d-flex gap-2 align-items-center")
        ], className="page-title-header d-flex justify-content-between align-items-center"),

        # ── 보드 ──────────────────────────────────────────────
        html.Div([
            dbc.Row([
                dbc.Col([
                    col_header(label, bg, fg),
                    html.Div(id=f"kanban-col-{i}", style=col_body())
                ], style={"minWidth": "300px"})
                for i, (label, bg, fg) in enumerate(col_defs)
            ], className="flex-nowrap g-3")
        ], style={"overflowX": "auto", "paddingBottom": "20px"}),

        # ── 숨겨진 스토어 ──────────────────────────────────────
        dcc.Store(id="current-modal-order-id"),
        dcc.Store(id="current-modal-stage"),
        dcc.Store(id="kanban-update-trigger", data=0),
        dcc.Store(id="drag-drop-store", data=None),
        dcc.Download(id="download-modal-excel"),
        html.Button(id="btn-hidden-drop", style={"display": "none"}),
        html.Div(id="dummy-js-output", style={"display": "none"}),

        # ── 토스트 ────────────────────────────────────────────
        html.Div(dbc.Toast(
            id="gatekeeper-toast", header="⚠️ 알림", is_open=False,
            dismissable=True, icon="danger",
            style={"position": "fixed", "top": 20, "right": 20, "width": 380, "zIndex": 9999}
        )),

        # ── 모달 ──────────────────────────────────────────────
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-detail-title", className="fw-bold",
                                           style={"color": "#1e293b"})),
            dbc.ModalBody([
                html.Div(id="modal-shared-card-container", className="mb-3"),

                # 샘플 분리(예외 처리) 안내 배너
                dbc.Alert([
                    DashIconify(icon="carbon:split", className="me-2"),
                    html.Strong("개별 샘플 분리: "),
                    "아래 표에서 특정 샘플의 '진행 상태'를 직접 변경하면 해당 샘플만 분리되어 독립 카드로 관리됩니다."
                ], color="info", className="py-2 mb-3 small"),

                # 툴바
                html.Div([
                    html.Div([
                        html.Strong([DashIconify(icon="carbon:edit", className="me-1"), "일괄 변경:"],
                                    className="text-secondary me-2", style={"fontSize": "0.85rem"}),
                        dbc.Select(id="bulk-col-select", options=[], placeholder="항목 선택…",
                                   style={"width": "160px"}, className="me-2 shadow-sm form-select-sm"),
                        dbc.Input(id="bulk-val-input", placeholder="입력값…",
                                  style={"width": "140px"}, className="me-2 shadow-sm form-control-sm"),
                        dbc.Button("적용", id="btn-bulk-apply", color="primary", size="sm",
                                   className="fw-bold shadow-sm rounded-3"),
                    ], className="d-flex align-items-center"),
                    html.Div([
                        dbc.Button([DashIconify(icon="carbon:download", className="me-1"), "엑셀 다운로드"],
                                   id="btn-export-excel", color="light", size="sm",
                                   className="me-2 fw-bold shadow-sm border rounded-3 text-secondary"),
                        dcc.Upload(
                            id="upload-overwrite-excel",
                            children=dbc.Button([DashIconify(icon="carbon:upload", className="me-1"), "엑셀 덮어쓰기"],
                                                color="white", size="sm",
                                                className="fw-bold shadow-sm border border-primary text-primary rounded-3"),
                            multiple=False, className="d-inline-block"
                        )
                    ], className="d-flex align-items-center")
                ], className="d-flex justify-content-between align-items-center p-3 mb-3 rounded-4 border",
                   style={"backgroundColor": "#f8fafc", "borderColor": "#e2e8f0"}),

                dag.AgGrid(
                    id="modal-datatable", rowData=[], columnDefs=[],
                    defaultColDef={"resizable": True, "sortable": True, "filter": True},
                    dashGridOptions={
                        "rowHeight": 45, "singleClickEdit": True,
                        "stopEditingWhenCellsLoseFocus": True,
                        "enterNavigatesVertically": False,
                        "enterNavigatesVerticallyAfterEdit": True,
                        "undoRedoCellEditing": True,
                        "undoRedoCellEditingLimit": 50,
                        # 분리된(예외) 샘플은 행 색상으로 강조
                        "getRowStyle": {
                            "function": "params.data.is_split ? {backgroundColor: '#fff7ed', fontStyle: 'italic'} : {}"
                        }
                    },
                    style={"height": "420px", "width": "100%"},
                    className="ag-theme-alpine border-0 shadow-sm rounded-3"
                )
            ], style={"maxHeight": "82vh", "overflowY": "auto"}),

            dbc.ModalFooter([
                html.Span("💡 저장 후 칸반 보드가 자동 갱신됩니다.",
                          className="text-muted small fw-bold me-auto"),
                dbc.Button([DashIconify(icon="carbon:save", className="me-1"), "변경사항 저장"],
                           id="btn-save-modal", color="primary",
                           className="fw-bold rounded-3 shadow-sm px-4")
            ], className="border-top-0 bg-light rounded-bottom-4")
        ],
            id="sample-detail-modal", size="xl", is_open=False, centered=True, backdrop="static",
            dialog_style={"maxWidth": "1450px", "width": "95%"},
            content_class_name="rounded-4 border-0 shadow-lg"
        ),
    ])


# ============================================================
# [2] 카드 생성 – Project 그룹 헤더 + Order 카드
# ============================================================

def _sample_status_bar(samples_in_order):
    """Order 안의 샘플들을 상태별로 집계해 미니 배지 바를 반환."""
    counts = defaultdict(int)
    for s in samples_in_order:
        counts[s.current_status] += 1

    badges = []
    for stage in STAGES:
        n = counts.get(stage, 0)
        if n:
            theme = STATUS_THEME.get(stage, {})
            badges.append(
                html.Span(f"{stage[:2]} {n}",
                          className=f"badge bg-{theme.get('badge', 'secondary')} me-1",
                          style={"fontSize": "0.7rem"})
            )
    # 보류/실패
    held = counts.get("보류/실패", 0) + counts.get("재실험", 0)
    if held:
        badges.append(html.Span(f"보류 {held}", className="badge bg-danger me-1",
                                style={"fontSize": "0.7rem"}))
    return html.Div(badges, className="mb-2")


def make_order_card(order_obj, status, samples_in_status, all_samples_in_order, is_split=False):
    """
    단일 Order 카드.
    is_split=True : 이 Order 안의 샘플들이 여러 단계에 흩어진 상태 → '분리됨' 배지 표시
    """
    action_rule = LimsRules.STAGE_ACTIONS.get(status, {"text": "다음 단계", "color": "info", "next": "완료"})
    btn_text, btn_color, next_stage = action_rule["text"], action_rule["color"], action_rule["next"]
    group_id = f"{order_obj.order_id}___{status}"
    theme = STATUS_THEME.get(status, {"border": "border-secondary", "text": "text-secondary"})

    has_issue = any(
        s.issue_comment and str(s.issue_comment).strip() not in ["", "None", "nan"]
        for s in samples_in_status
    )

    # 단계별 부가 정보
    stage_info = []
    if status == "접수 대기":
        received = sum(1 for s in samples_in_status
                       if str(getattr(s, "sample_received", "")).replace(" ", "") == "입고완료")
        stage_info.append(
            html.Small(f"📦 입고 완료 {received}/{len(samples_in_status)}건",
                       className=f"d-block {'text-success' if received == len(samples_in_status) else 'text-danger'} fw-bold mb-1")
        )
        stage_info.append(html.Small(f"🏢 {order_obj.facility} · {order_obj.client_team}",
                                     className="text-muted d-block"))
    elif status == "접수 완료":
        stage_info.append(html.Small(f"📅 접수일: {order_obj.reception_date}", className="text-muted d-block"))
    elif status == "QC 진행":
        passed = sum(1 for s in samples_in_status
                     if str(getattr(s, "sample_qc", "")).upper() == "PASS")
        stage_info.append(
            html.Small(f"🔬 QC PASS {passed}/{len(samples_in_status)}건",
                       className="d-block text-warning fw-bold mb-1")
        )
    elif status == "정산 대기":
        rev = (order_obj.sales_unit_price or 0) * len(samples_in_status)
        stage_info.append(
            html.Div(html.Small(f"💰 예상 매출: {rev:,}원", className="text-primary fw-bold"),
                     className="bg-light p-1 rounded border")
        )
    else:
        stage_info.append(html.Small(f"🏢 {order_obj.facility}", className="text-muted d-block"))

    return html.Div([
        dbc.Card([
            dbc.CardBody([
                # 제목 행
                html.Div([
                    html.H6(f"📦 {order_obj.order_id}",
                            className=f"fw-bold {theme['text']} mb-0",
                            style={"fontSize": "0.85rem"}),
                    html.Div([
                        html.Span(f"{len(samples_in_status)}건",
                                  className="badge bg-secondary me-1"),
                        html.Span("⚠️ 이슈", className="badge bg-danger me-1") if has_issue else None,
                        html.Span("🔀 분리됨", className="badge bg-warning text-dark") if is_split else None,
                    ])
                ], className="d-flex justify-content-between align-items-start mb-2"),

                # 전체 샘플 상태 미니 바 (Order 내 흩어진 현황)
                _sample_status_bar(all_samples_in_order),

                html.Div(stage_info, className="mb-3"),

                dbc.Button(btn_text,
                           id={"type": "btn-move-stage", "index": group_id, "next": next_stage},
                           color=btn_color, size="sm", className="w-100 mb-1 fw-bold"),
                dbc.Button("🔍 상세 / 개별 샘플 분리",
                           id={"type": "btn-open-modal", "order_id": order_obj.order_id, "stage": status},
                           color="link", size="sm", className="w-100 text-muted p-0 mt-1")
            ], className="p-3")
        ], className=f"shadow-sm border-start border-4 {theme['border']} rounded-3")
    ], draggable=True, id=f"drag-card-{group_id}",
       style={"cursor": "grab"}, className="mb-2")


def make_project_group(project_name, order_cards):
    """Project 이름을 헤더로 갖는 접이식 그룹 컨테이너."""
    safe_id = re.sub(r"[^a-zA-Z0-9가-힣_-]", "_", project_name)
    return html.Div([
        # 프로젝트 구분선 헤더
        html.Div([
            DashIconify(icon="carbon:folder", className="me-1 text-muted", width=14),
            html.Span(project_name, style={"fontSize": "0.75rem", "color": "#64748b",
                                           "fontWeight": "700", "letterSpacing": "0.06em",
                                           "textTransform": "uppercase"}),
            html.Hr(style={"flex": 1, "marginLeft": "8px", "borderColor": "#e2e8f0", "marginTop": "9px"})
        ], className="d-flex align-items-center mb-2 mt-1"),
        html.Div(order_cards)
    ], id=f"proj-group-{safe_id}", className="mb-1")


# ============================================================
# [3] 콜백
# ============================================================
def register_kanban_callbacks(dash_app):

    # ── 보드 렌더 ────────────────────────────────────────────
    @dash_app.callback(
        [Output(f"kanban-col-{i}", "children") for i in range(6)],
        [Input("kanban-update-trigger", "data"),
         Input("kanban-search-input", "value"),
         Input("kanban-panel-filter", "value")]
    )
    def render_kanban_board(trigger, search_kw, panel_filter):
        cols = [[] for _ in range(6)]
        db = SessionLocal()
        try:
            all_orders = db.query(Order).join(Sample).all()

            # ── 검색/필터 적용 ──
            kw = (search_kw or "").strip().lower()
            filtered_orders = []
            for o in all_orders:
                if kw and not any([
                    kw in (o.order_id or "").lower(),
                    kw in (o.facility or "").lower(),
                    kw in (o.client_team or "").lower(),
                    any(kw in (s.project_name or "").lower() for s in o.samples),
                ]):
                    continue
                if panel_filter and panel_filter != "ALL":
                    if not any(s.target_panel == panel_filter for s in o.samples):
                        continue
                filtered_orders.append(o)

            # ── 각 Order를 단계별로 분해 ──
            # 구조: {col_idx: {project_name: [card, ...]}}
            col_proj: list[dict[str, list]] = [defaultdict(list) for _ in range(6)]

            for o in filtered_orders:
                # 패널 필터 적용 후 샘플
                samples = [s for s in o.samples
                           if panel_filter == "ALL" or not panel_filter or s.target_panel == panel_filter]
                if not samples:
                    continue

                # 단계별 샘플 집계
                by_stage = defaultdict(list)
                for s in samples:
                    stage = s.current_status if s.current_status in STATUS_IDX else "접수 대기"
                    by_stage[stage].append(s)

                # Order 내 샘플이 여러 단계에 흩어졌는지 확인
                is_split = len(by_stage) > 1

                for stage, stage_samples in by_stage.items():
                    col_idx = STATUS_IDX[stage]
                    # project_name은 샘플 첫 번째 값 기준 (없으면 "Default")
                    proj = (stage_samples[0].project_name or "Default").strip()
                    card = make_order_card(o, stage, stage_samples, samples, is_split=is_split)
                    col_proj[col_idx][proj].append(card)

            # ── Project 그룹 헤더 씌워서 컬럼에 배치 ──
            for col_idx, proj_dict in enumerate(col_proj):
                if not proj_dict:
                    cols[col_idx] = [html.Div("빈 단계", className="text-center text-muted small mt-5")]
                    continue
                col_children = []
                for proj_name in sorted(proj_dict.keys()):
                    col_children.append(make_project_group(proj_name, proj_dict[proj_name]))
                cols[col_idx] = col_children

            return cols

        except Exception as e:
            print(f"Kanban Load Error: {e}")
            traceback.print_exc()
            return cols
        finally:
            db.close()

    # ── 모달 열기 / 닫기 ─────────────────────────────────────
    @dash_app.callback(
        [Output("sample-detail-modal", "is_open"),
         Output("modal-detail-title", "children"),
         Output("modal-shared-card-container", "children"),
         Output("modal-datatable", "rowData"),
         Output("modal-datatable", "columnDefs"),
         Output("current-modal-order-id", "data"),
         Output("current-modal-stage", "data"),
         Output("bulk-col-select", "options")],
        [Input({"type": "btn-open-modal", "order_id": ALL, "stage": ALL}, "n_clicks"),
         Input("btn-save-modal", "n_clicks")],
        [State("sample-detail-modal", "is_open"),
         State("current-modal-order-id", "data"),
         State("current-modal-stage", "data")],
        prevent_initial_call=True
    )
    def handle_modal(open_clicks, save_clicks, is_open, current_oid, current_stage):
        if not ctx.triggered:
            return [no_update] * 8
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        if tid == "btn-save-modal":
            return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update

        db = SessionLocal()
        try:
            oid, stage = current_oid, current_stage or "접수 대기"

            if "btn-open-modal" in tid:
                if all(c is None for c in open_clicks):
                    return [no_update] * 8
                btn_data = json.loads(tid)
                oid, stage = btn_data["order_id"], btn_data["stage"]

            if not oid:
                return [no_update] * 8
            order = db.query(Order).filter(Order.order_id == oid).first()
            if not order:
                return [no_update] * 8

            # 해당 단계 샘플만 표시
            samples = [s for s in order.samples if s.current_status == stage]
            stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})

            # 컬럼 정의
            columns = LimsDashApp.get_base_grid_columns(include_project=False)

            # 분리 여부 열 (읽기 전용 표시용)
            columns.append({
                "headerName": "🔀 분리 여부", "field": "is_split_label",
                "width": 100, "editable": False,
                "cellStyle": {
                    "styleConditions": [
                        {"condition": "params.value === '분리됨'",
                         "style": {"color": "#d97706", "fontWeight": "bold"}}
                    ]
                }
            })

            bulk_options = [{"label": col["name"], "value": col["id"]}
                            for col in stage_config["columns"] if col.get("editable", True)]

            for col in stage_config["columns"]:
                ag_col = {"headerName": col["name"], "field": col["id"],
                          "editable": col.get("editable", True)}
                if col.get("presentation") == "dropdown":
                    ag_col["cellEditor"] = "agSelectCellEditor"
                    if "options" in col:
                        ag_col["cellEditorParams"] = {"values": col["options"]}
                columns.append(ag_col)

            bulk_options.extend([
                {"label": "🔄 진행 상태 (개별 분리)", "value": "current_status"},
                {"label": "📝 특이사항/메모", "value": "issue_comment"}
            ])
            columns.extend([
                {"headerName": "진행 상태", "field": "current_status", "editable": True,
                 "width": 130,
                 "cellEditor": "agSelectCellEditor",
                 "cellEditorParams": {"values": STAGES + ["보류/실패", "재실험"]},
                 "cellStyle": {
                     "styleConditions": [
                         {"condition": f"params.value === '{stage}'",
                          "style": {"color": "#64748b"}},
                         {"condition": f"params.value !== '{stage}' && params.value !== ''",
                          "style": {"color": "#d97706", "fontWeight": "bold",
                                    "backgroundColor": "#fff7ed"}}
                     ]
                 }},
                {"headerName": "특이사항/메모", "field": "issue_comment", "editable": True,
                 "cellEditor": "agLargeTextCellEditor", "cellEditorPopup": True,
                 "cellEditorParams": {"maxLength": 1000, "rows": 6, "cols": 50},
                 "flex": 1, "minWidth": 220}
            ])

            # Order 전체 단계 집합 (분리 여부 판단용)
            all_stages_in_order = set(s.current_status for s in order.samples)
            is_split_order = len(all_stages_in_order) > 1

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
                    "is_split": is_split_order,
                    "is_split_label": "분리됨" if is_split_order else "통합",
                }
                for col in stage_config["columns"]:
                    col_id = col["id"]
                    if hasattr(s, col_id):
                        row_dict[col_id] = getattr(s, col_id) or ""
                    elif s.panel_metadata and col_id in s.panel_metadata:
                        row_dict[col_id] = s.panel_metadata[col_id]
                table_data.append(row_dict)

            shared_card = create_project_summary_card(order, len(samples))

            # 모달 타이틀: 분리 여부 표시
            title_extra = " 🔀 일부 샘플 분리 중" if is_split_order else ""
            title = f"📋 {oid} · {stage} ({len(samples)}건){title_extra}"

            return True, title, shared_card, table_data, columns, oid, stage, bulk_options

        finally:
            db.close()

    # ── 엑셀 다운로드 ────────────────────────────────────────
    @dash_app.callback(
        Output("download-modal-excel", "data"),
        Input("btn-export-excel", "n_clicks"),
        [State("modal-datatable", "rowData"),
         State("current-modal-order-id", "data"),
         State("current-modal-stage", "data")],
        prevent_initial_call=True
    )
    def export_excel(n_clicks, table_data, oid, stage):
        if not table_data:
            return no_update
        df = pd.DataFrame(table_data).drop(columns=["id", "is_split", "is_split_label"], errors="ignore")
        return dcc.send_data_frame(df.to_excel, f"{oid}_{stage}_데이터.xlsx", index=False)

    # ── 일괄 변경 & 엑셀 덮어쓰기 ───────────────────────────
    @dash_app.callback(
        Output("modal-datatable", "rowData", allow_duplicate=True),
        [Input("btn-bulk-apply", "n_clicks"),
         Input("upload-overwrite-excel", "contents")],
        [State("bulk-col-select", "value"),
         State("bulk-val-input", "value"),
         State("modal-datatable", "rowData")],
        prevent_initial_call=True
    )
    def bulk_and_overwrite(bulk_clicks, upload_contents, col, val, row_data):
        if not row_data:
            return no_update
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        if tid == "btn-bulk-apply":
            if not col or val is None:
                return no_update
            val_str = str(val).strip()
            return [{**row, col: val_str} for row in row_data]

        elif tid == "upload-overwrite-excel" and upload_contents:
            _, content_string = upload_contents.split(",")
            decoded = base64.b64decode(content_string)
            df_up = pd.read_excel(io.BytesIO(decoded))
            up_dict = df_up.to_dict("records")
            new_data = []
            for row in row_data:
                new_row = row.copy()
                match = next((u for u in up_dict
                              if str(u.get("sample_name")) == str(row.get("sample_name"))), None)
                if match:
                    for k, v in match.items():
                        if k in new_row and pd.notna(v) and k not in ["id", "sample_name", "target_panel"]:
                            new_row[k] = str(v).strip()
                new_data.append(new_row)
            return new_data

        return no_update

    # ── 저장 / 드래그&드롭 / 단계 이동 버튼 ────────────────
    @dash_app.callback(
        [Output("kanban-update-trigger", "data", allow_duplicate=True),
         Output("gatekeeper-toast", "is_open"),
         Output("gatekeeper-toast", "children")],
        [Input("drag-drop-store", "data"),
         Input({"type": "btn-move-stage", "index": ALL, "next": ALL}, "n_clicks"),
         Input("btn-save-modal", "n_clicks")],
        [State("modal-datatable", "rowData"),
         State("kanban-update-trigger", "data"),
         State("current-modal-stage", "data")],
        prevent_initial_call=True
    )
    def update_data(drag_data, btn_clicks, save_click, table_data, trig, modal_stage):
        if not ctx.triggered:
            return no_update, False, no_update

        trigger_val = ctx.triggered[0]["value"]
        if not trigger_val:
            return no_update, False, no_update

        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        db = SessionLocal()
        error_msgs = []
        try:
            upd = 0

            # ──────────────────────────────────────────────────
            # 1. 모달 저장 (개별 샘플 분리 포함)
            # ──────────────────────────────────────────────────
            if tid == "btn-save-modal" and table_data:
                stage = modal_stage or "접수 대기"
                stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})

                for row in table_data:
                    if not str(row.get("sample_name", "")).strip():
                        continue
                    s = db.query(Sample).filter(Sample.id == row.get("id")).first()
                    if not s:
                        continue

                    old_status = s.current_status
                    old_issue = s.issue_comment or ""
                    new_status = str(row.get("current_status", s.current_status)).strip()
                    new_issue = str(row.get("issue_comment", "")).strip("\t\r")

                    # ── 재실험 파생 ──
                    if "재실험" in new_status:
                        base_id = str(s.sample_id or "UNKNOWN")
                        m = re.search(r"-R(\d+)$", base_id)
                        new_s_id = (base_id[:m.start()] + f"-R{int(m.group(1)) + 1}"
                                    if m else base_id + "-R1")
                        new_s = Sample(
                            order_pk=s.order_pk, order_id=s.order_id, sample_id=new_s_id,
                            target_panel=s.target_panel, current_status="접수 대기",
                            sample_name=s.sample_name, cancer_type=s.cancer_type,
                            specimen=s.specimen, project_name=s.project_name,
                            pairing_info=s.pairing_info, outside_id_1=s.outside_id_1,
                            issue_comment=f"[{stage} 단계에서 재실험 요청됨 (원본: {base_id})]",
                            panel_metadata=s.panel_metadata
                        )
                        db.add(new_s)
                        s.current_status = "보류/실패"
                        s.issue_comment = f"[재실험 진행으로 인한 종료] {new_issue}"
                        db.add(ActionLog(sample_id=s.id, action_type="재실험 요청",
                                         previous_state=stage, new_state="보류/실패",
                                         details=f"새 샘플 {new_s_id} 파생됨"))
                        upd += 1
                        continue

                    # ── 필드 갱신 ──
                    has_field_change = False
                    for col in stage_config["columns"]:
                        c_id = col["id"]
                        if c_id not in row:
                            continue
                        val = row[c_id]
                        if isinstance(val, str):
                            val = val.strip()
                        if col.get("type") == "numeric":
                            try:
                                val = float(val) if str(val).strip() else None
                            except ValueError:
                                val = None
                        if hasattr(s, c_id):
                            if getattr(s, c_id) != val:
                                setattr(s, c_id, val)
                                has_field_change = True
                        else:
                            if s.panel_metadata is None:
                                s.panel_metadata = {}
                            if s.panel_metadata.get(c_id) != val:
                                s.panel_metadata[c_id] = val
                                has_field_change = True

                    if has_field_change:
                        if s.panel_metadata is not None:
                            s.panel_metadata = dict(s.panel_metadata)
                        db.add(ActionLog(sample_id=s.id, action_type="데이터 갱신",
                                         previous_state=old_status, new_state=old_status,
                                         details="상세 수정"))
                        upd += 1

                    # ── 역방향 이동 차단 ──
                    stages_order = STAGES + ["보류/실패"]
                    try:
                        old_idx = stages_order.index(old_status)
                        new_idx = stages_order.index(new_status)
                    except ValueError:
                        old_idx = new_idx = 0

                    if new_idx < old_idx and new_status != "보류/실패":
                        error_msgs.append(
                            f"🚫 [{s.sample_name}] 역방향 이동 불가 (현재: {old_status})")
                        new_status = old_status

                    # ── 단계 전진 조건(pass_value) 검증 ──
                    if new_status != old_status and new_status not in ["보류/실패", "재실험"]:
                        is_passed = True
                        for col in stage_config["columns"]:
                            db_val = str(
                                getattr(s, col["id"], "") if hasattr(s, col["id"])
                                else (s.panel_metadata.get(col["id"], "") if s.panel_metadata else "")
                            ).replace(" ", "")
                            target_val = str(col.get("pass_value", "")).replace(" ", "")
                            if col.get("required") and not db_val:
                                error_msgs.append(
                                    f"[{s.sample_name}] 필수 항목 '{col['name']}' 누락")
                                is_passed = False
                            if col.get("pass_value") and db_val != target_val:
                                error_msgs.append(
                                    f"📦 [{s.sample_name}] '{col['name']}'을 "
                                    f"'{col.get('pass_value')}'로 설정해야 이동 가능합니다.")
                                is_passed = False
                        if not is_passed:
                            new_status = old_status

                    if old_status != new_status:
                        s.current_status = new_status
                        action_label = ("개별 샘플 분리 이동" if new_status != stage
                                        else "상태 변경")
                        db.add(ActionLog(sample_id=s.id, action_type=action_label,
                                         previous_state=old_status, new_state=new_status,
                                         details="모달 저장"))
                        upd += 1

                    if old_issue != new_issue:
                        s.issue_comment = new_issue
                        db.add(ActionLog(sample_id=s.id, action_type="특이사항 갱신",
                                         previous_state=old_status, new_state=s.current_status,
                                         details=f"{old_issue or '없음'} → 변경됨"))
                        upd += 1

            # ──────────────────────────────────────────────────
            # 2. 칸반 버튼 / 드래그 (Order 단위 일괄 이동)
            # ──────────────────────────────────────────────────
            else:
                group_id, next_s = None, None
                if tid == "drag-drop-store" and drag_data:
                    group_id = drag_data["card_id"].replace("drag-card-", "")
                    next_s = drag_data["new_stage"]
                elif "btn-move-stage" in tid:
                    d = json.loads(tid)
                    group_id, next_s = d["index"], d["next"]

                if group_id:
                    oid, curr_s = group_id.split("___")
                    if curr_s == next_s:
                        return no_update, False, no_update

                    try:
                        curr_idx = STAGES.index(curr_s)
                        next_idx = STAGES.index(next_s)
                    except ValueError:
                        curr_idx = next_idx = 0

                    if next_idx < curr_idx:
                        error_msgs.append(f"🚫 역방향 이동 불가: [{curr_s}] → [{next_s}]")
                    else:
                        samples = (db.query(Sample).join(Order)
                                   .filter(Order.order_id == oid,
                                           Sample.current_status == curr_s).all())

                        for s in samples:
                            if curr_s == "접수 대기":
                                if str(getattr(s, "sample_received", "")).replace(" ", "") != "입고완료":
                                    error_msgs.append(
                                        f"📦 [{s.sample_name}] '입고 확인'을 '입고 완료'로 변경해주세요.")
                                if not getattr(s, "receiver_name", ""):
                                    error_msgs.append(
                                        f"👤 [{s.sample_name}] '입고 담당자' 이름이 누락되었습니다.")

                        if not error_msgs:
                            for s in samples:
                                old_status = s.current_status
                                s.current_status = next_s
                                db.add(ActionLog(
                                    sample_id=s.id, action_type="상태 변경 (Order 일괄)",
                                    previous_state=old_status, new_state=next_s,
                                    details="칸반 이동"))
                                upd += 1

            # ── 결과 처리 ──
            if error_msgs:
                db.rollback()
                toast_content = html.Div(
                    [html.P(msg, className="mb-1 text-danger fw-bold") for msg in error_msgs[:5]])
                return no_update, True, toast_content

            if upd > 0:
                db.commit()
                return (trig or 0) + 1, False, no_update

            return no_update, False, no_update

        finally:
            db.close()

    # ── 클라이언트사이드: 드래그 이벤트 바인딩 ──────────────
    dash_app.clientside_callback(
        """
        function(trigger) {
            setTimeout(function() {
                var cards = document.querySelectorAll('[draggable="true"]');
                cards.forEach(function(card) {
                    card.ondragstart = function(e) { e.dataTransfer.setData('text', card.id); };
                });
                var stages = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"];
                for (let i = 0; i <= 5; i++) {
                    let col = document.getElementById('kanban-col-' + i);
                    if (!col) continue;
                    col.ondragover = function(e) { e.preventDefault(); };
                    col.ondrop = function(e) {
                        e.preventDefault();
                        var id = e.dataTransfer.getData('text');
                        if (id) {
                            window.latestDropData = {
                                "card_id": id, "new_stage": stages[i], "ts": Date.now()
                            };
                            document.getElementById('btn-hidden-drop').click();
                        }
                    };
                }
            }, 800);
            return "";
        }
        """,
        Output("dummy-js-output", "children"),
        Input("kanban-update-trigger", "data")
    )

    dash_app.clientside_callback(
        "function(n){ return window.latestDropData || window.dash_clientside.no_update; }",
        Output("drag-drop-store", "data"),
        Input("btn-hidden-drop", "n_clicks")
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