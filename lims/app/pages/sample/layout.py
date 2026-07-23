"""
app/pages/sample/layout.py
============================
샘플 접수 페이지.
- 상단: 프로젝트 선택 드롭다운 + KPI
- 좌: 샘플 그리드
- 우: 샘플 등록/수정 사이드폼 (슬라이드인)
"""

from dash import html, dcc
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

from app.ui.components import build_stat_card, build_confirm_modal

P = "smp"


def build_layout():
    return html.Div([
        dcc.Store(id=f"{P}-selected"),
        dcc.Store(id=f"{P}-project-id"),
        dcc.Store(id=f"{P}-form-mode", data="new"),
        dcc.Download(id=f"{P}-download"),

        # ── 헤더 ─────────────────────────────────────
        html.Div([
            html.Div([
                DashIconify(icon="carbon:sample", width=26, color="#7c3aed", className="me-2"),
                html.H5("샘플 접수", className="fw-bold mb-0"),
            ], className="d-flex align-items-center"),
            html.Div([
                dbc.Button(
                    [DashIconify(icon="carbon:download", className="me-1"), "Excel"],
                    id=f"{P}-export", color="light", size="sm",
                    className="me-2 border rounded-3 fw-semibold shadow-sm text-secondary",
                ),
                dbc.Button(
                    [DashIconify(icon="carbon:add-alt", className="me-1"), "새 샘플"],
                    id=f"{P}-new-btn", color="primary", size="sm",
                    className="fw-bold rounded-3 shadow-sm",
                    disabled=True,          # 프로젝트 선택 전 비활성
                ),
            ], className="d-flex"),
        ], className="d-flex justify-content-between align-items-center mb-4"),

        # ── 프로젝트 선택 바 ──────────────────────────
        dbc.Card([
            dbc.CardBody(
                dbc.Row([
                    dbc.Col(html.Label("프로젝트 선택", className="fw-semibold text-secondary mb-0",
                                       style={"fontSize": "0.82rem", "lineHeight": "2"}), width="auto"),
                    dbc.Col(
                        dbc.Select(
                            id=f"{P}-project-select",
                            options=[],
                            placeholder="프로젝트를 선택하세요…",
                            className="form-select-sm shadow-sm",
                        ), md=4,
                    ),
                    dbc.Col(
                        html.Div(id=f"{P}-project-badge"),
                        className="d-flex align-items-center",
                    ),
                ], align="center", className="g-2"),
                className="py-2",
            ),
        ], className="mb-4 shadow-sm border-0 rounded-4", style={"backgroundColor": "#f0f6ff"}),

        # ── KPI ──────────────────────────────────────
        dbc.Row([
            dbc.Col(build_stat_card(f"{P}-kpi-total",    "전체 샘플",  icon="carbon:sample",          color="#7c3aed", bg="#f5f3ff"), md=3),
            dbc.Col(build_stat_card(f"{P}-kpi-received", "입고 완료",  icon="carbon:checkmark-filled", color="#16a34a", bg="#f0fdf4"), md=3),
            dbc.Col(build_stat_card(f"{P}-kpi-pending",  "대기중",     icon="carbon:time",             color="#d97706", bg="#fffbeb"), md=3),
            dbc.Col(build_stat_card(f"{P}-kpi-issue",    "이슈",       icon="carbon:warning",          color="#dc2626", bg="#fff1f2"), md=3),
        ], className="mb-4"),

        # ── 메인: 그리드 + 사이드폼 ──────────────────
        dbc.Row([
            dbc.Col(_grid_card(), id=f"{P}-grid-col", md=12),
            dbc.Col(_form_card(), id=f"{P}-form-col", md=4, style={"display": "none"}),
        ], className="g-3"),

        # ── 모달 / 토스트 ─────────────────────────────
        build_confirm_modal(
            modal_id=f"{P}-del-modal", title="샘플 삭제",
            message="선택한 샘플과 하위 Library 전체가 삭제됩니다. 계속하시겠습니까?",
            confirm_id=f"{P}-del-confirm", confirm_label="삭제", confirm_color="danger",
        ),
        dbc.Toast(id=f"{P}-toast", header="알림", is_open=False, dismissable=True, duration=3000,
                  style={"position": "fixed", "top": 70, "right": 20, "zIndex": 9999, "minWidth": "280px"}),

    ], className="p-4", style={"fontFamily": "Inter, sans-serif", "backgroundColor": "#f8fafc", "minHeight": "100vh"})


# ─────────────────────────────────────────────────────
def _grid_card():
    return dbc.Card([
        dbc.CardHeader(
            html.Div([
                html.Span("샘플 목록", className="fw-bold"),
                html.Div([
                    dbc.Input(id=f"{P}-search", placeholder="ID / 이름 검색…",
                              type="search", size="sm", style={"width": "180px"}, className="me-2 shadow-sm"),
                    dbc.Select(id=f"{P}-filter-received", value="",
                               options=[
                                   {"label": "전체",       "value": ""},
                                   {"label": "입고 완료",  "value": "입고 완료"},
                                   {"label": "대기중",     "value": "대기중"},
                               ],
                               style={"width": "110px"}, className="form-select-sm shadow-sm me-2"),
                    dbc.Select(id=f"{P}-filter-progress", value="",
                               options=[
                                   {"label": "전체", "value": ""},
                                   {"label": "진행", "value": "진행"},
                                   {"label": "보류", "value": "보류"},
                                   {"label": "취소", "value": "취소"},
                               ],
                               style={"width": "90px"}, className="form-select-sm shadow-sm"),
                ], className="d-flex align-items-center gap-2"),
            ], className="d-flex justify-content-between align-items-center"),
            className="bg-white border-bottom py-2 px-3",
        ),
        dbc.CardBody([
            dag.AgGrid(
                id=f"{P}-grid",
                rowData=[],
                columnDefs=_sample_cols(),
                defaultColDef={"resizable": True, "sortable": True, "filter": True,
                               "editable": False, "minWidth": 100},
                dashGridOptions={"rowHeight": 44, "headerHeight": 44,
                                 "rowSelection": "single", "animateRows": True},
                style={"height": "500px", "width": "100%"},
                className="ag-theme-alpine border-0",
            ),
            html.Div([
                dbc.Button([DashIconify(icon="carbon:edit", className="me-1"), "수정"],
                           id=f"{P}-edit-btn", color="light", size="sm",
                           className="border rounded-3 shadow-sm me-2", disabled=True),
                dbc.Button([DashIconify(icon="carbon:trash-can", className="me-1"), "삭제"],
                           id=f"{P}-del-btn", color="danger", size="sm", outline=True,
                           className="rounded-3 shadow-sm", disabled=True),
            ], className="d-flex mt-3"),
        ]),
    ], className="shadow-sm border-0 rounded-4")


def _form_card():
    origin_opts  = [{"label": v, "value": v} for v in ["Blood","Tissue","FFPE","Urine","Plasma","Saliva","기타"]]
    pairing_opts = [{"label": v, "value": v} for v in ["N/A","Tumor","Normal","Paired"]]
    visual_opts  = [{"label": v, "value": v} for v in ["양호","불량","보류"]]
    recv_opts    = [{"label": v, "value": v} for v in ["대기중","입고 완료"]]
    prog_opts    = [{"label": v, "value": v} for v in ["진행","보류","취소"]]

    return dbc.Card([
        dbc.CardHeader(
            html.Div([
                html.Span(id=f"{P}-form-title", className="fw-bold"),
                dbc.Button(DashIconify(icon="carbon:close", width=16),
                           id=f"{P}-form-close", color="light", size="sm", className="border-0 p-1"),
            ], className="d-flex justify-content-between align-items-center"),
            className="bg-white border-bottom py-2 px-3",
        ),
        dbc.CardBody([
            # 선택 프로젝트 표시
            dbc.Alert(id=f"{P}-form-project-info", color="info",
                      className="py-2 rounded-3 mb-3", style={"fontSize": "0.82rem"}),

            _fg("샘플명 *",       dbc.Input(id=f"{P}-f-name",     placeholder="예) Patient_001",   className="form-control-sm")),
            _fg("검체 유래 *",    dbc.Select(id=f"{P}-f-origin",  options=origin_opts,             className="form-select-sm")),
            _fg("Pairing",        dbc.Select(id=f"{P}-f-pairing", options=pairing_opts, value="N/A", className="form-select-sm")),
            _fg("외부 ID",        dbc.Input(id=f"{P}-f-outside",  placeholder="의뢰처 자체 ID",    className="form-control-sm")),
            html.Hr(className="my-2"),
            html.P("입고 정보", className="fw-semibold text-secondary mb-2", style={"fontSize": "0.8rem"}),
            _fg("입고 확인 *",    dbc.Select(id=f"{P}-f-received", options=recv_opts, value="대기중", className="form-select-sm")),
            _fg("입고 담당자",    dbc.Input(id=f"{P}-f-receiver",  placeholder="홍길동",            className="form-control-sm")),
            _fg("육안 상태 *",    dbc.Select(id=f"{P}-f-visual",   options=visual_opts, value="양호", className="form-select-sm")),
            _fg("보관 위치",      dbc.Input(id=f"{P}-f-storage",   placeholder="-80℃ A-1-2",       className="form-control-sm")),
            _fg("초기 용량(mL)",  dbc.Input(id=f"{P}-f-volume",    type="number", min=0, placeholder="0.5", className="form-control-sm")),
            _fg("검사진행 여부 *",dbc.Select(id=f"{P}-f-progress", options=prog_opts, value="진행", className="form-select-sm")),
            html.Hr(className="my-2"),
            _fg("이슈/비고",      dbc.Textarea(id=f"{P}-f-comment", rows=2, placeholder="특이사항…", className="form-control-sm")),

            html.Div([
                dbc.Button([DashIconify(icon="carbon:save", className="me-1"), "저장"],
                           id=f"{P}-form-save", color="primary",
                           className="fw-bold rounded-3 shadow-sm flex-grow-1 me-2"),
                dbc.Button("초기화", id=f"{P}-form-reset", color="light", className="rounded-3 border"),
            ], className="d-flex mt-2"),
            html.Div(id=f"{P}-form-fb", className="mt-2"),
        ], style={"overflowY": "auto", "maxHeight": "calc(100vh - 180px)"}),
    ], className="shadow-sm border-0 rounded-4")


def _sample_cols():
    recv_badge = {"function": """
        const c={'입고 완료':'#16a34a','대기중':'#d97706'};
        const col=c[params.value]||'#6b7280';
        return params.value?`<span style="background:${col};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600">${params.value}</span>`:'';
    """}
    prog_badge = {"function": """
        const c={'진행':'#0d6efd','보류':'#d97706','취소':'#dc2626'};
        const col=c[params.value]||'#6b7280';
        return params.value?`<span style="background:${col};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600">${params.value}</span>`:'';
    """}
    return [
        {"headerName": "Sample ID",    "field": "sample_id",        "width": 240, "pinned": "left",
         "cellStyle": {"fontWeight": "600", "color": "#7c3aed"}},
        {"headerName": "샘플명",        "field": "sample_name",      "width": 150},
        {"headerName": "검체 유래",     "field": "origin",           "width": 110},
        {"headerName": "Pairing",       "field": "pairing_info",     "width": 100},
        {"headerName": "외부 ID",       "field": "outside_id",       "width": 130},
        {"headerName": "입고 확인",     "field": "sample_received",  "width": 120,
         "cellRenderer": "markdown", "cellRendererParams": recv_badge},
        {"headerName": "입고 담당자",   "field": "receiver_name",    "width": 110},
        {"headerName": "육안 상태",     "field": "visual_inspection","width": 100},
        {"headerName": "보관 위치",     "field": "storage_location", "width": 130},
        {"headerName": "초기 용량",     "field": "initial_volume",   "width": 100},
        {"headerName": "검사진행",      "field": "test_progress",    "width": 100,
         "cellRenderer": "markdown", "cellRendererParams": prog_badge},
        {"headerName": "이슈",          "field": "issue_comment",    "width": 200},
        {"headerName": "등록일",        "field": "created_at",       "width": 150, "editable": False},
    ]


def _fg(label, component):
    return html.Div([
        html.Label(label, className="form-label fw-semibold text-secondary mb-1",
                   style={"fontSize": "0.79rem"}),
        component,
    ], className="mb-2")