"""
app/pages/project/layout.py
============================
프로젝트 관리 페이지.
- 프로젝트 목록 그리드
- 우측 슬라이드인 폼 (신규/수정)
- 삭제 확인 모달
"""

from dash import html, dcc
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

from app.ui.components import build_stat_card, build_confirm_modal

P = "prj"


def build_layout():
    return html.Div([
        dcc.Store(id=f"{P}-selected"),
        dcc.Store(id=f"{P}-form-mode", data="new"),
        dcc.Download(id=f"{P}-download"),

        # ── 헤더 ─────────────────────────────────────
        html.Div([
            html.Div([
                DashIconify(icon="carbon:folder-add", width=26, color="#0d6efd", className="me-2"),
                html.H5("프로젝트 관리", className="fw-bold mb-0"),
            ], className="d-flex align-items-center"),
            html.Div([
                dbc.Button(
                    [DashIconify(icon="carbon:download", className="me-1"), "Excel"],
                    id=f"{P}-export", color="light", size="sm",
                    className="me-2 border rounded-3 fw-semibold shadow-sm text-secondary",
                ),
                dbc.Button(
                    [DashIconify(icon="carbon:add-alt", className="me-1"), "새 프로젝트"],
                    id=f"{P}-new-btn", color="primary", size="sm",
                    className="fw-bold rounded-3 shadow-sm",
                ),
            ], className="d-flex"),
        ], className="d-flex justify-content-between align-items-center mb-4"),

        # ── KPI ──────────────────────────────────────
        dbc.Row([
            dbc.Col(build_stat_card(f"{P}-kpi-total",   "전체 프로젝트", icon="carbon:folder"),                               md=3),
            dbc.Col(build_stat_card(f"{P}-kpi-active",  "진행중",        icon="carbon:in-progress",  color="#16a34a", bg="#f0fdf4"), md=3),
            dbc.Col(build_stat_card(f"{P}-kpi-done",    "완료",          icon="carbon:checkmark-outline", color="#6b7280", bg="#f1f5f9"), md=3),
            dbc.Col(build_stat_card(f"{P}-kpi-samples", "등록 샘플",     icon="carbon:sample",       color="#7c3aed", bg="#f5f3ff"), md=3),
        ], className="mb-4"),

        # ── 메인: 그리드 + 사이드폼 ──────────────────
        dbc.Row([
            dbc.Col(_grid_card(), id=f"{P}-grid-col", md=12),
            dbc.Col(_form_card(), id=f"{P}-form-col", md=4, style={"display": "none"}),
        ], id=f"{P}-main-row", className="g-3"),

        # ── 모달 / 토스트 ─────────────────────────────
        build_confirm_modal(
            modal_id=f"{P}-del-modal", title="프로젝트 삭제",
            message="하위 샘플 전체가 함께 삭제됩니다. 계속하시겠습니까?",
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
                html.Span("프로젝트 목록", className="fw-bold"),
                html.Div([
                    dbc.Input(id=f"{P}-search", placeholder="ID / 이름 / 기관…",
                              type="search", size="sm", style={"width": "200px"}, className="me-2 shadow-sm"),
                    dbc.Select(id=f"{P}-filter-status", value="",
                               options=[
                                   {"label": "전체",     "value": ""},
                                   {"label": "접수 완료","value": "접수 완료"},
                                   {"label": "진행중",   "value": "진행중"},
                                   {"label": "완료",     "value": "완료"},
                                   {"label": "취소",     "value": "취소"},
                               ],
                               style={"width": "110px"}, className="form-select-sm shadow-sm"),
                ], className="d-flex align-items-center gap-2"),
            ], className="d-flex justify-content-between align-items-center"),
            className="bg-white border-bottom py-2 px-3",
        ),
        dbc.CardBody([
            dag.AgGrid(
                id=f"{P}-grid",
                rowData=[],
                columnDefs=_project_cols(),
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
            _fg("프로젝트 종류 *", dbc.Select(id=f"{P}-f-code", options=[], placeholder="선택…", className="form-select-sm")),
            _fg("프로젝트명 *",    dbc.Input(id=f"{P}-f-name", placeholder="예) 2025 cbNIPT 1차", className="form-control-sm")),
            _fg("유형 *", dbc.RadioItems(id=f"{P}-f-type",
                options=[{"label": v, "value": v} for v in ["Clinical", "Research", "External"]],
                value="Clinical", inline=True, className="mt-1")),
            html.Hr(className="my-2"),
            html.P("의뢰처", className="fw-semibold text-secondary mb-2", style={"fontSize": "0.8rem"}),
            _fg("기관명 *",  dbc.Input(id=f"{P}-f-facility",  placeholder="서울대학교병원",   className="form-control-sm")),
            _fg("부서",      dbc.Input(id=f"{P}-f-team",      placeholder="산부인과",         className="form-control-sm")),
            _fg("담당자",    dbc.Input(id=f"{P}-f-cname",     placeholder="홍길동",            className="form-control-sm")),
            _fg("이메일",    dbc.Input(id=f"{P}-f-email",     placeholder="user@hospital.com", type="email", className="form-control-sm")),
            _fg("연락처",    dbc.Input(id=f"{P}-f-phone",     placeholder="010-0000-0000",     className="form-control-sm")),
            html.Hr(className="my-2"),
            html.P("일정 / 금액", className="fw-semibold text-secondary mb-2", style={"fontSize": "0.8rem"}),
            _fg("접수일 *", dcc.DatePickerSingle(id=f"{P}-f-rdate", display_format="YYYY-MM-DD", placeholder="YYYY-MM-DD", style={"width":"100%"})),
            _fg("마감일",   dcc.DatePickerSingle(id=f"{P}-f-ddate", display_format="YYYY-MM-DD", placeholder="YYYY-MM-DD", style={"width":"100%"})),
            _fg("단가(원)", dbc.Input(id=f"{P}-f-price", type="number", min=0, placeholder="0", className="form-control-sm")),
            html.Hr(className="my-2"),
            _fg("비고", dbc.Textarea(id=f"{P}-f-comment", placeholder="특이사항…", rows=2, className="form-control-sm")),
            html.Div([
                dbc.Button([DashIconify(icon="carbon:save", className="me-1"), "저장"],
                           id=f"{P}-form-save", color="primary",
                           className="fw-bold rounded-3 shadow-sm flex-grow-1 me-2"),
                dbc.Button("초기화", id=f"{P}-form-reset", color="light", className="rounded-3 border"),
            ], className="d-flex mt-2"),
            html.Div(id=f"{P}-form-fb", className="mt-2"),
        ], style={"overflowY": "auto", "maxHeight": "calc(100vh - 180px)"}),
    ], className="shadow-sm border-0 rounded-4")


def _project_cols():
    badge = {"function": """
        const c={'접수 완료':'#0d6efd','진행중':'#16a34a','완료':'#6b7280','취소':'#dc2626','보류':'#d97706'};
        const col=c[params.value]||'#6b7280';
        return params.value?`<span style="background:${col};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600">${params.value}</span>`:'';
    """}
    return [
        {"headerName": "Project ID",   "field": "project_id",     "width": 200, "pinned": "left",
         "cellStyle": {"fontWeight": "600", "color": "#0d6efd"}},
        {"headerName": "프로젝트명",    "field": "project_name",   "width": 220},
        {"headerName": "종류",          "field": "project_code",   "width": 110},
        {"headerName": "유형",          "field": "project_type",   "width": 100},
        {"headerName": "기관",          "field": "facility",       "width": 160},
        {"headerName": "담당자",        "field": "client_name",    "width": 100},
        {"headerName": "접수일",        "field": "reception_date", "width": 110},
        {"headerName": "마감일",        "field": "deadline",       "width": 110},
        {"headerName": "상태",          "field": "current_status", "width": 110,
         "cellRenderer": "markdown", "cellRendererParams": badge},
        {"headerName": "샘플 수",       "field": "_sample_count",  "width": 80,
         "cellStyle": {"textAlign": "center", "fontWeight": "600"}},
        {"headerName": "비고",          "field": "issue_comment",  "width": 200},
    ]


def _fg(label, component):
    return html.Div([
        html.Label(label, className="form-label fw-semibold text-secondary mb-1",
                   style={"fontSize": "0.79rem"}),
        component,
    ], className="mb-2")