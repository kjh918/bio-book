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

import os
from pathlib import Path
from app.core.database import SessionLocal
from app.models._schema import Order, Sample, Analysis, ActionLog, STAGE_SCHEMA_CONFIG, ANALYSIS_SCHEMA_CONFIG
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
    "접수 대기":   {"border": "border-secondary", "text": "text-secondary"},
    "접수 완료":   {"border": "border-info",      "text": "text-info"},
    "QC 진행":     {"border": "border-warning",   "text": "text-warning"},
    "시퀀싱 진행": {"border": "border-primary",   "text": "text-primary"},
    "분석 진행":   {"border": "border-success",   "text": "text-success"},
    "정산 대기":   {"border": "border-dark",      "text": "text-dark"},
}

# ============================================================
# 필드 저장 위치 판별 헬퍼
#
# hasattr(Sample, col_id) 로 Sample 직접 컬럼 여부를 판별한다.
# True  → setattr(s, col_id, val)
# False → s.panel_metadata[col_id] = val
#
# 현재 스키마 기준 Sample 직접 컬럼에 해당하는 STAGE_SCHEMA_CONFIG 필드:
#   접수 대기 : sample_received, receiver_name, storage_location, visual_inspection
#   접수 완료 : initial_volume
#   나머지 전부 → panel_metadata
# ============================================================

def _read_field(s: Sample, col_id: str):
    """Sample 직접 컬럼 우선, 없으면 panel_metadata에서 읽는다."""
    if hasattr(Sample, col_id):
        return getattr(s, col_id, None)
    meta = s.panel_metadata or {}
    return meta.get(col_id)


def _write_field(s: Sample, col_id: str, val, new_meta: dict) -> bool:
    """
    값을 저장하고 변경 여부(bool)를 반환한다.
    Sample 직접 컬럼이면 setattr, 아니면 new_meta dict에 기록한다.
    """
    if hasattr(Sample, col_id):
        old = getattr(s, col_id, None)
        if old != val:
            setattr(s, col_id, val)
            return True
        return False
    else:
        old = new_meta.get(col_id)
        if old != val:
            new_meta[col_id] = val
            return True
        return False


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
                html.H2([DashIconify(icon="carbon:flow", className="me-2 text-dark"),
                         "WORKFLOW BOARD"], className="fw-bold text-dark mb-0"),
            ]),
            html.Div([
                dbc.Input(id="kanban-search-input",
                          placeholder="Project / Order / 기관 검색…",
                          size="sm", style={"width": "260px"}, debounce=True),
                dbc.Select(id="kanban-panel-filter",
                           options=[{"label": "전체 패널", "value": "ALL"},
                                    {"label": "WES",       "value": "WES"},
                                    {"label": "WGS",       "value": "WGS"},
                                    {"label": "WTS",       "value": "WTS"}],
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
        # cellValueChanged echo-back → 저장 시점 rowData 동기화 보장
        dcc.Store(id="modal-rowdata-synced", data=[]),
        dcc.Download(id="download-modal-excel"),
        html.Button(id="btn-hidden-drop", style={"display": "none"}),
        html.Div(id="dummy-js-output", style={"display": "none"}),

        # ── 토스트 ────────────────────────────────────────────
        html.Div(dbc.Toast(
            id="gatekeeper-toast", header="⚠️ 알림", is_open=False,
            dismissable=True, icon="danger",
            style={"position": "fixed", "top": 20, "right": 20,
                   "width": 380, "zIndex": 9999}
        )),

        # ── 모달 ──────────────────────────────────────────────
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-detail-title", className="fw-bold",
                                           style={"color": "#1e293b"})),
            dbc.ModalBody([
                html.Div(id="modal-shared-card-container", className="mb-3"),

                # 툴바
                html.Div([
                    html.Div([
                        html.Strong([DashIconify(icon="carbon:edit", className="me-1"),
                                     "일괄 변경:"],
                                    className="text-secondary me-2",
                                    style={"fontSize": "0.85rem"}),
                        dbc.Select(id="bulk-col-select", options=[],
                                   placeholder="항목 선택…",
                                   style={"width": "160px"},
                                   className="me-2 shadow-sm form-select-sm"),
                        dbc.Input(id="bulk-val-input", placeholder="입력값…",
                                  style={"width": "140px"},
                                  className="me-2 shadow-sm form-control-sm"),
                        dbc.Button("적용", id="btn-bulk-apply", color="primary",
                                   size="sm", className="fw-bold shadow-sm rounded-3"),
                    ], className="d-flex align-items-center"),
                    html.Div([
                        dbc.Button([DashIconify(icon="carbon:download", className="me-1"),
                                    "엑셀 다운로드"],
                                   id="btn-export-excel", color="light", size="sm",
                                   className="me-2 fw-bold shadow-sm border rounded-3 text-secondary"),
                        dcc.Upload(
                            id="upload-overwrite-excel",
                            children=dbc.Button(
                                [DashIconify(icon="carbon:upload", className="me-1"),
                                 "엑셀 덮어쓰기"],
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
                        "rowHeight": 45,
                        "singleClickEdit": True,
                        "stopEditingWhenCellsLoseFocus": True,
                        # False: 팝업 에디터(agLargeTextCellEditor)에서
                        # 엔터가 줄바꿈 대신 셀 이동을 유발하는 것을 방지
                        "enterNavigatesVertically": False,
                        "enterNavigatesVerticallyAfterEdit": False,
                        "undoRedoCellEditing": True,
                        "undoRedoCellEditingLimit": 50,
                    },
                    style={"height": "420px", "width": "100%"},
                    className="ag-theme-alpine border-0 shadow-sm rounded-3"
                ),
            ], style={"maxHeight": "82vh", "overflowY": "auto"}),

            dbc.ModalFooter([
                html.Span("💡 저장 후 칸반 보드가 자동 갱신됩니다.",
                          className="text-muted small fw-bold me-auto"),
                dbc.Button([DashIconify(icon="carbon:save", className="me-1"),
                            "변경사항 저장"],
                           id="btn-save-modal", color="primary",
                           className="fw-bold rounded-3 shadow-sm px-4")
            ], className="border-top-0 bg-light rounded-bottom-4")
        ],
            id="sample-detail-modal", size="xl", is_open=False,
            centered=True, backdrop="static",
            dialog_style={"maxWidth": "1450px", "width": "95%"},
            content_class_name="rounded-4 border-0 shadow-lg"
        ),
    ])


# ============================================================
# [2] 카드 생성
# ============================================================
def make_order_card(order_obj, status, samples_in_status):
    group_id = f"{order_obj.order_id}___{status}"
    theme = STATUS_THEME.get(status,
                             {"border": "border-secondary", "text": "text-secondary"})
    has_issue = any(
        s.issue_comment and str(s.issue_comment).strip() not in ["", "None", "nan"]
        for s in samples_in_status
    )
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                # GCX 코드
                html.Div(
                    order_obj.order_id,
                    className=f"fw-bold {theme['text']} mb-1",
                    style={"fontSize": "0.92rem", "wordBreak": "break-all",
                           "lineHeight": "1.3"}
                ),
                # 기관·담당자
                html.Div(
                    f"{order_obj.facility}-{order_obj.client_team}: {order_obj.client_name or '-'}",
                    className="text-muted mb-1",
                    style={"fontSize": "0.78rem"}
                ),
                # 접수일
                html.Div(
                    f"접수일: {order_obj.reception_date}",
                    className="text-muted mb-2",
                    style={"fontSize": "0.78rem"}
                ),
                # 건수 + 이슈 배지
                html.Div([
                    html.Span(f"{len(samples_in_status)}건",
                              className="badge bg-secondary me-1"),
                    html.Span("⚠️ 이슈", className="badge bg-danger") if has_issue else None,
                ], className="mb-3"),

                dbc.Button("상세보기",
                           id={"type": "btn-open-modal",
                               "order_id": order_obj.order_id, "stage": status},
                           color="light", size="sm",
                           className="w-100 fw-bold border text-secondary",
                           style={"fontSize": "0.8rem"})
            ], className="p-3")
        ], className=f"shadow-sm border-start border-4 {theme['border']} rounded-3")
    ], draggable=True, id=f"drag-card-{group_id}",
       style={"cursor": "grab"}, className="mb-2")


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

            for o in filtered_orders:
                samples = [s for s in o.samples
                           if panel_filter == "ALL" or not panel_filter
                           or s.target_panel == panel_filter]
                if not samples:
                    continue
                by_stage = defaultdict(list)
                for s in samples:
                    stage = s.current_status if s.current_status in STATUS_IDX else "접수 대기"
                    by_stage[stage].append(s)
                for stage, stage_samples in by_stage.items():
                    cols[STATUS_IDX[stage]].append(
                        make_order_card(o, stage, stage_samples))

            for i in range(6):
                if not cols[i]:
                    cols[i] = [html.Div("빈 단계",
                                        className="text-center text-muted small mt-5")]
            return cols

        except Exception as e:
            print(f"Kanban Load Error: {e}")
            traceback.print_exc()
            return cols
        finally:
            db.close()

    # ── 모달 열기 / 닫기 ─────────────────────────────────────
    @dash_app.callback(
        [Output("sample-detail-modal",        "is_open"),
         Output("modal-detail-title",         "children"),
         Output("modal-shared-card-container","children"),
         Output("modal-datatable",            "rowData"),
         Output("modal-datatable",            "columnDefs"),
         Output("current-modal-order-id",     "data"),
         Output("current-modal-stage",        "data"),
         Output("bulk-col-select",            "options"),
         Output("modal-rowdata-synced",       "data", allow_duplicate=True)],
        [Input({"type": "btn-open-modal", "order_id": ALL, "stage": ALL}, "n_clicks"),
         Input("btn-save-modal", "n_clicks")],
        [State("sample-detail-modal",     "is_open"),
         State("current-modal-order-id",  "data"),
         State("current-modal-stage",     "data")],
        prevent_initial_call=True
    )
    def handle_modal(open_clicks, save_clicks, is_open, current_oid, current_stage):
        if not ctx.triggered:
            return [no_update] * 9
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        if tid == "btn-save-modal":
            return (False, no_update, no_update, no_update,
                    no_update, no_update, no_update, no_update, no_update)

        db = SessionLocal()
        try:
            
            oid   = current_oid
            stage = current_stage or "접수 대기"

            if "btn-open-modal" in tid:
                if all(c is None for c in open_clicks):
                    return [no_update] * 9
                btn_data  = json.loads(tid)
                oid, stage = btn_data["order_id"], btn_data["stage"]

            if not oid:
                return [no_update] * 9
            order = db.query(Order).filter(Order.order_id == oid).first()
            if not order:
                return [no_update] * 9

            samples      = [s for s in order.samples if s.current_status == stage]
            stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})

            # 컬럼 정의
            columns = LimsDashApp.get_base_grid_columns(include_project=False)

            bulk_options = [{"label": col["name"], "value": col["id"]}
                            for col in stage_config["columns"]
                            if col.get("editable", True)]

            for col in stage_config["columns"]:
                ag_col = {"headerName": col["name"], "field": col["id"],
                          "editable": col.get("editable", True)}
                if col.get("presentation") == "dropdown":
                    ag_col["cellEditor"] = "agSelectCellEditor"
                    if "options" in col:
                        ag_col["cellEditorParams"] = {"values": col["options"]}
                if col.get("type") == "numeric":
                    ag_col["type"] = "numericColumn"
                columns.append(ag_col)

            bulk_options.append({"label": "📝 특이사항/메모", "value": "issue_comment"})
            columns.extend([
                # 진행 상태: 읽기 전용 — 단계 이동은 드래그&드롭만
                {"headerName": "진행 상태", "field": "current_status",
                 "editable": False, "width": 110,
                 "cellStyle": {"color": "#64748b", "backgroundColor": "#f8fafc"}},
                {"headerName": "특이사항/메모", "field": "issue_comment",
                 "editable": True,
                 "cellEditor": "agLargeTextCellEditor", "cellEditorPopup": True,
                 "cellEditorParams": {"maxLength": 1000, "rows": 6, "cols": 50},
                 "flex": 1, "minWidth": 220}
            ])

            # rowData 구성 — _read_field 로 Sample직접/panel_metadata 자동 분기
            table_data = []
            for s in samples:
                row_dict = {
                    "id":             s.id,
                    "order_id":       s.order_id,
                    "sample_id":      s.sample_id,
                    "sample_name":    s.sample_name,
                    "target_panel":   s.target_panel,
                    "current_status": s.current_status,
                    "issue_comment":  s.issue_comment or "",
                }
                for col in stage_config["columns"]:
                    col_id = col["id"]
                    val = _read_field(s, col_id)
                    row_dict[col_id] = val if val is not None else ""
                table_data.append(row_dict)

            shared_card = create_project_summary_card(order, len(samples))
            title       = f"📋 {oid} · {stage} ({len(samples)}건)"
            

            return (True, title, shared_card,
                    table_data, columns, oid, stage, bulk_options,
                    table_data)  # ← modal-rowdata-synced 초기화
        finally:
            db.close()

    # ── 셀 편집 즉시 Store에 echo-back ───────────────────────
    # singleClickEdit 환경에서 셀 편집 직후 바로 저장 버튼을 누르면
    # State("rowData")에 최신값이 아직 반영 안 된 채로 콜백이 실행될 수 있다.
    # cellValueChanged 이벤트마다 전체 rowData를 Store에 저장해 타이밍 이슈 방지.
    @dash_app.callback(
        Output("modal-rowdata-synced", "data", allow_duplicate=True),
        Input("modal-datatable", "cellValueChanged"),
        State("modal-datatable", "rowData"),
        prevent_initial_call=True
    )
    def sync_rowdata_on_edit(_, row_data):
        return row_data if row_data is not None else no_update

    # ── 엑셀 다운로드 ────────────────────────────────────────
    @dash_app.callback(
        Output("download-modal-excel", "data"),
        Input("btn-export-excel", "n_clicks"),
        [State("modal-datatable",        "rowData"),
         State("current-modal-order-id", "data"),
         State("current-modal-stage",    "data")],
        prevent_initial_call=True
    )
    def export_excel(n_clicks, table_data, oid, stage):
        if not table_data:
            return no_update
        df = pd.DataFrame(table_data).drop(columns=["id"], errors="ignore")
        return dcc.send_data_frame(df.to_excel, f"{oid}_{stage}_데이터.xlsx", index=False)

    # ── 일괄 변경 & 엑셀 덮어쓰기 ───────────────────────────
    @dash_app.callback(
        Output("modal-datatable", "rowData", allow_duplicate=True),
        [Input("btn-bulk-apply",         "n_clicks"),
         Input("upload-overwrite-excel", "contents")],
        [State("bulk-col-select",   "value"),
         State("bulk-val-input",    "value"),
         State("modal-datatable",   "rowData")],
        prevent_initial_call=True
    )
    def bulk_and_overwrite(_, upload_contents, col, val, row_data):
        if not row_data:
            return no_update
        tid = ctx.triggered[0]["prop_id"].split(".")[0]

        if tid == "btn-bulk-apply":
            if not col or val is None:
                return no_update
            val_str = str(val).strip()
            return [{**row, col: val_str} for row in row_data]

        if tid == "upload-overwrite-excel" and upload_contents:
            _, content_string = upload_contents.split(",")
            decoded = base64.b64decode(content_string)
            df_up   = pd.read_excel(io.BytesIO(decoded))
            up_dict = df_up.to_dict("records")
            new_data = []
            for row in row_data:
                new_row = row.copy()
                match = next(
                    (u for u in up_dict
                     if str(u.get("sample_name")) == str(row.get("sample_name"))),
                    None)
                if match:
                    for k, v in match.items():
                        if (k in new_row and pd.notna(v)
                                and k not in ["id", "sample_name", "target_panel"]):
                            new_row[k] = str(v).strip()
                new_data.append(new_row)
            return new_data

        return no_update

    # ── 저장 / 드래그&드롭 ──────────────────────────────────
    @dash_app.callback(
        [Output("kanban-update-trigger", "data",      allow_duplicate=True),
         Output("gatekeeper-toast",      "is_open"),
         Output("gatekeeper-toast",      "children")],
        [Input("drag-drop-store",  "data"),
         Input({"type": "btn-move-stage", "index": ALL, "next": ALL}, "n_clicks"),
         Input("btn-save-modal",   "n_clicks")],
        [State("modal-datatable",        "rowData"),
         State("modal-rowdata-synced",   "data"),
         State("kanban-update-trigger",  "data"),
         State("current-modal-stage",    "data")],
        prevent_initial_call=True
    )
    def update_data(drag_data, btn_clicks, save_click,
                    grid_row_data, synced_row_data, trig, modal_stage):
        if not ctx.triggered:
            return no_update, False, no_update
        if not ctx.triggered[0]["value"]:
            return no_update, False, no_update

        # synced_row_data 우선 (편집 직후 저장 타이밍 이슈 방지)
        table_data = synced_row_data if synced_row_data else grid_row_data
        tid        = ctx.triggered[0]["prop_id"].split(".")[0]
        db         = SessionLocal()
        error_msgs = []

        try:
            upd = 0

            # ── 1. 모달 저장 (QC입력값/메모 갱신 — 단계 이동은 드래그&드롭 전용) ──
            if tid == "btn-save-modal" and table_data:
                stage        = modal_stage or "접수 대기"
                stage_config = STAGE_SCHEMA_CONFIG.get(stage, {"columns": []})

                for row in table_data:
                    if not str(row.get("sample_name", "")).strip():
                        continue
                    s = db.query(Sample).filter(Sample.id == row.get("id")).first()
                    if not s:
                        continue

                    old_status = s.current_status
                    old_issue  = s.issue_comment or ""
                    # 줄바꿈(\n) 보존 — 좌우 공백·탭·CR만 제거
                    new_issue  = str(row.get("issue_comment", "")).strip(" \t\r")

                    # panel_metadata 변경 감지를 위해 미리 복사
                    new_meta        = dict(s.panel_metadata) if s.panel_metadata else {}
                    has_field_change = False

                    for col in stage_config["columns"]:
                        c_id = col["id"]
                        if c_id not in row:
                            continue

                        val = row[c_id]

                        # 좌우 공백만 제거 (줄바꿈 보존)
                        if isinstance(val, str):
                            val = val.strip(" \t\r")
                        # 빈 문자열 → None 정규화
                        if val == "":
                            val = None
                        # numeric 타입 변환
                        if col.get("type") == "numeric" and val is not None:
                            try:
                                val = float(val)
                            except (ValueError, TypeError):
                                val = None

                        # _write_field: Sample직접 컬럼이면 setattr,
                        #               아니면 new_meta에 기록
                        if _write_field(s, c_id, val, new_meta):
                            has_field_change = True

                    if has_field_change:
                        # panel_metadata는 새 dict 할당해야 SQLAlchemy가 변경 감지
                        s.panel_metadata = new_meta
                        db.add(s)
                        db.add(ActionLog(
                            sample_id   = s.id,
                            action_type = "데이터 갱신",
                            previous_state = old_status,
                            new_state      = old_status,
                            details        = "상세 수정"))
                        upd += 1

                    if old_issue != new_issue:
                        s.issue_comment = new_issue
                        db.add(ActionLog(
                            sample_id   = s.id,
                            action_type = "특이사항 갱신",
                            previous_state = old_status,
                            new_state      = old_status,
                            details        = f"{old_issue or '없음'} → 변경됨"))
                        upd += 1

            # ── 2. 드래그&드롭 (Order 단위 일괄 단계 이동) ──────────
            else:
                group_id = next_s = None
                if tid == "drag-drop-store" and drag_data:
                    group_id = drag_data["card_id"].replace("drag-card-", "")
                    next_s   = drag_data["new_stage"]
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
                        error_msgs.append(
                            f"🚫 역방향 이동 불가: [{curr_s}] → [{next_s}]")
                    else:
                        samples = (db.query(Sample).join(Order)
                                   .filter(Order.order_id == oid,
                                           Sample.current_status == curr_s).all())

                        # 접수 대기 → 접수 완료 이동 시 게이트키퍼 검증
                        if curr_s == "접수 대기":
                            for s in samples:
                                recv = str(getattr(s, "sample_received", "")).replace(" ", "")
                                if recv != "입고완료":
                                    error_msgs.append(
                                        f"📦 [{s.sample_name}] '입고 확인'을 '입고 완료'로 변경해주세요.")
                                if not getattr(s, "receiver_name", ""):
                                    error_msgs.append(
                                        f"👤 [{s.sample_name}] '입고 담당자' 이름이 누락되었습니다.")

                        if not error_msgs:
                            for s in samples:
                                old_status      = s.current_status
                                s.current_status = next_s
                                db.add(ActionLog(
                                    sample_id      = s.id,
                                    action_type    = "상태 변경 (Order 일괄)",
                                    previous_state = old_status,
                                    new_state      = next_s,
                                    details        = "칸반 이동"))
                                upd += 1

            # ── 결과 처리 ──
            if error_msgs:
                db.rollback()
                return (no_update, True,
                        html.Div([html.P(m, className="mb-1 text-danger fw-bold")
                                  for m in error_msgs[:5]]))
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
                    card.ondragstart = function(e) {
                        e.dataTransfer.setData('text', card.id);
                    };
                });
                var stages = ["접수 대기","접수 완료","QC 진행",
                              "시퀀싱 진행","분석 진행","정산 대기"];
                for (let i = 0; i <= 5; i++) {
                    let col = document.getElementById('kanban-col-' + i);
                    if (!col) continue;
                    col.ondragover = function(e) { e.preventDefault(); };
                    col.ondrop = function(e) {
                        e.preventDefault();
                        var id = e.dataTransfer.getData('text');
                        if (id) {
                            window.latestDropData = {
                                card_id: id, new_stage: stages[i], ts: Date.now()
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