"""
app/ui/components.py
====================
재사용 UI 컴포넌트 빌더. 상태 없음 — 순수 레이아웃 반환만.

제공:
    build_aggrid()              AG Grid 단독
    build_toolbar()             Grid 위 툴바 (bulk-edit / export / upload)
    build_aggrid_with_toolbar() 툴바 + Grid 묶음
    build_stat_card()           KPI 카드
    build_status_badge()        상태 뱃지
    build_action_modal()        범용 모달 (상세 편집용)
    build_confirm_modal()       확인 다이얼로그
    build_filter_bar()          상단 필터 바

ID 네이밍 컨벤션:
    컴포넌트별 id prefix 를 외부에서 주입받아 페이지 간 충돌 방지.
    예) prefix="sample" → grid id = "sample-grid"
"""

from dash import html, dcc
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify


# ─────────────────────────────────────────────────────
# AG Grid
# ─────────────────────────────────────────────────────
def build_aggrid(
    grid_id: str,
    column_defs: list,
    row_data: list | None = None,
    height: str = "500px",
    row_group: bool = False,
    extra_grid_options: dict | None = None,
    extra_col_def: dict | None = None,
) -> dag.AgGrid:
    """
    표준 AG Grid.

    Args:
        grid_id       : 컴포넌트 id
        column_defs   : ag-grid columnDefs
        row_data      : 초기 데이터 (None = 빈 배열, 콜백으로 채움)
        height        : CSS height 문자열
        row_group     : 프로젝트 그룹화 활성화 여부
        extra_grid_options : dashGridOptions 추가/오버라이드
        extra_col_def : defaultColDef 추가/오버라이드
    """
    default_col_def = {
        "resizable": True,
        "sortable": True,
        "filter": True,
        "editable": True,
        "minWidth": 100,
        **(extra_col_def or {}),
    }

    grid_options = {
        "rowHeight": 44,
        "headerHeight": 44,
        "singleClickEdit": True,
        "stopEditingWhenCellsLoseFocus": True,
        "undoRedoCellEditing": True,
        "undoRedoCellEditingLimit": 50,
        "enterNavigatesVertically": True,
        "animateRows": True,
    }
    if row_group:
        grid_options.update({
            "groupDefaultExpanded": 1,
            "autoGroupColumnDef": {
                "headerName": "Project",
                "minWidth": 240,
                "cellRendererParams": {"checkbox": True},
            },
        })
    if extra_grid_options:
        grid_options.update(extra_grid_options)

    return dag.AgGrid(
        id=grid_id,
        rowData=row_data or [],
        columnDefs=column_defs,
        defaultColDef=default_col_def,
        dashGridOptions=grid_options,
        style={"height": height, "width": "100%"},
        className="ag-theme-alpine border-0 shadow-sm rounded-3",
    )


# ─────────────────────────────────────────────────────
# Toolbar
# ─────────────────────────────────────────────────────
def build_toolbar(
    bulk_select_id: str,
    bulk_input_id: str,
    bulk_apply_id: str,
    export_id: str,
    upload_id: str,
    bulk_options: list | None = None,   # [{"label": ..., "value": ...}]
    show_bulk: bool = True,
    show_export: bool = True,
    show_upload: bool = True,
) -> html.Div:
    """
    AG Grid 위 툴바.
    bulk-edit / Excel 다운로드 / Excel 덮어쓰기 업로드.
    """
    left: list = []
    if show_bulk:
        left = [
            html.Span(
                [DashIconify(icon="carbon:edit", className="me-1"), "일괄 변경:"],
                className="text-secondary me-2 fw-semibold",
                style={"fontSize": "0.82rem"},
            ),
            dbc.Select(
                id=bulk_select_id,
                options=bulk_options or [],
                placeholder="항목 선택…",
                style={"width": "160px"},
                className="me-2 form-select-sm shadow-sm",
            ),
            dbc.Input(
                id=bulk_input_id,
                placeholder="입력값…",
                style={"width": "140px"},
                className="me-2 form-control-sm shadow-sm",
            ),
            dbc.Button(
                "적용",
                id=bulk_apply_id,
                color="primary",
                size="sm",
                className="fw-bold shadow-sm rounded-3",
            ),
        ]

    right: list = []
    if show_export:
        right.append(
            dbc.Button(
                [DashIconify(icon="carbon:download", className="me-1"), "Excel 다운로드"],
                id=export_id,
                color="light",
                size="sm",
                className="me-2 fw-semibold shadow-sm border rounded-3 text-secondary",
            )
        )
    if show_upload:
        right.append(
            dcc.Upload(
                id=upload_id,
                children=dbc.Button(
                    [DashIconify(icon="carbon:upload", className="me-1"), "Excel 업로드"],
                    color="white",
                    size="sm",
                    className="fw-semibold shadow-sm border border-primary text-primary rounded-3",
                ),
                multiple=False,
                className="d-inline-block",
            )
        )

    return html.Div(
        [
            html.Div(left,  className="d-flex align-items-center gap-1"),
            html.Div(right, className="d-flex align-items-center gap-1"),
        ],
        className="d-flex justify-content-between align-items-center p-3 mb-3 rounded-4 border",
        style={"backgroundColor": "#f8fafc", "borderColor": "#e2e8f0"},
    )


def build_aggrid_with_toolbar(
    grid_id: str,
    column_defs: list,
    row_data: list | None = None,
    height: str = "460px",
    bulk_select_id: str | None = None,
    bulk_input_id: str | None = None,
    bulk_apply_id: str | None = None,
    export_id: str | None = None,
    upload_id: str | None = None,
    bulk_options: list | None = None,
    show_bulk: bool = True,
    show_export: bool = True,
    show_upload: bool = True,
    row_group: bool = False,
    extra_grid_options: dict | None = None,
) -> html.Div:
    """툴바 + AG Grid 묶음 컴포넌트."""
    prefix = grid_id
    return html.Div([
        build_toolbar(
            bulk_select_id=bulk_select_id or f"{prefix}-bulk-col",
            bulk_input_id=bulk_input_id   or f"{prefix}-bulk-val",
            bulk_apply_id=bulk_apply_id   or f"{prefix}-bulk-apply",
            export_id=export_id           or f"{prefix}-export",
            upload_id=upload_id           or f"{prefix}-upload",
            bulk_options=bulk_options,
            show_bulk=show_bulk,
            show_export=show_export,
            show_upload=show_upload,
        ),
        build_aggrid(
            grid_id=grid_id,
            column_defs=column_defs,
            row_data=row_data,
            height=height,
            row_group=row_group,
            extra_grid_options=extra_grid_options,
        ),
    ])


# ─────────────────────────────────────────────────────
# KPI 카드
# ─────────────────────────────────────────────────────
def build_stat_card(
    card_id: str,
    label: str,
    value: str | int = "—",
    icon: str = "carbon:chart-line",
    color: str = "#0d6efd",
    bg: str = "#f0f6ff",
) -> dbc.Card:
    """
    대시보드 상단 KPI 카드.

    사용 예:
        build_stat_card("card-total", "전체 샘플", 0, icon="carbon:document")
    """
    return dbc.Card(
        dbc.CardBody([
            html.Div([
                DashIconify(icon=icon, width=28, color=color, className="me-2"),
                html.Span(label, className="text-secondary fw-semibold", style={"fontSize": "0.85rem"}),
            ], className="d-flex align-items-center mb-2"),
            html.H4(value, id=card_id, className="fw-bold mb-0", style={"color": color}),
        ]),
        className="shadow-sm border-0 rounded-4",
        style={"backgroundColor": bg},
    )


# ─────────────────────────────────────────────────────
# 상태 뱃지
# ─────────────────────────────────────────────────────
_STATUS_COLOR: dict[str, str] = {
    "접수 완료":   "primary",
    "진행중":      "info",
    "완료":        "success",
    "보류":        "warning",
    "취소":        "danger",
    "PASS":        "success",
    "FAIL":        "danger",
    "HOLD":        "warning",
    "RE-RUN":      "secondary",
    "PENDING":     "light",
}

def build_status_badge(status: str) -> dbc.Badge:
    color = _STATUS_COLOR.get(status, "secondary")
    return dbc.Badge(status, color=color, className="rounded-pill px-2 py-1")


# ─────────────────────────────────────────────────────
# 범용 모달 (상세 편집 / 단계 진행)
# ─────────────────────────────────────────────────────
def build_action_modal(
    modal_id: str,
    title: str = "상세 정보",
    body_id: str | None = None,
    save_id: str | None = None,
    size: str = "xl",
) -> dbc.Modal:
    """
    Stage별 상세 편집 모달.
    body는 콜백에서 동적으로 채움 (body_id 로 타깃).
    """
    body_id = body_id or f"{modal_id}-body"
    save_id = save_id or f"{modal_id}-save"

    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle(title), close_button=True),
            dbc.ModalBody(html.Div(id=body_id)),
            dbc.ModalFooter([
                dbc.Button(
                    [DashIconify(icon="carbon:save", className="me-1"), "저장"],
                    id=save_id,
                    color="primary",
                    className="fw-bold rounded-3",
                ),
                dbc.Button("닫기", id=f"{modal_id}-close", color="light", className="rounded-3"),
            ]),
        ],
        id=modal_id,
        size=size,
        is_open=False,
        backdrop="static",
        scrollable=True,
    )


def build_confirm_modal(
    modal_id: str,
    title: str = "확인",
    message: str = "계속하시겠습니까?",
    confirm_id: str | None = None,
    confirm_label: str = "확인",
    confirm_color: str = "danger",
) -> dbc.Modal:
    """삭제/상태 변경 등 확인 다이얼로그."""
    confirm_id = confirm_id or f"{modal_id}-confirm"
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle(title)),
            dbc.ModalBody(message),
            dbc.ModalFooter([
                dbc.Button(confirm_label, id=confirm_id, color=confirm_color, className="fw-bold rounded-3"),
                dbc.Button("취소", id=f"{modal_id}-cancel", color="light", className="rounded-3"),
            ]),
        ],
        id=modal_id,
        is_open=False,
        centered=True,
    )


# ─────────────────────────────────────────────────────
# 필터 바
# ─────────────────────────────────────────────────────
def build_filter_bar(
    project_filter_id: str = "filter-project",
    status_filter_id: str  = "filter-status",
    panel_filter_id: str   = "filter-panel",
    date_range_id: str     = "filter-date-range",
    search_id: str         = "filter-search",
    project_options: list  | None = None,
    status_options: list   | None = None,
    panel_options: list    | None = None,
    show_date: bool = True,
    show_search: bool = True,
) -> dbc.Card:
    """
    페이지 상단 필터 바. 드롭다운 + 날짜 범위 + 텍스트 검색.
    options는 콜백에서 동적으로도 채울 수 있음.
    """
    items = [
        dbc.Col(
            dbc.Select(
                id=project_filter_id,
                options=project_options or [],
                placeholder="Project…",
                className="form-select-sm shadow-sm",
            ),
            width="auto",
        ),
        dbc.Col(
            dbc.Select(
                id=status_filter_id,
                options=status_options or [],
                placeholder="Status…",
                className="form-select-sm shadow-sm",
            ),
            width="auto",
        ),
        dbc.Col(
            dbc.Select(
                id=panel_filter_id,
                options=panel_options or [],
                placeholder="Panel…",
                className="form-select-sm shadow-sm",
            ),
            width="auto",
        ),
    ]

    if show_date:
        items.append(
            dbc.Col(
                dcc.DatePickerRange(
                    id=date_range_id,
                    display_format="YYYY-MM-DD",
                    className="shadow-sm",
                    style={"fontSize": "0.82rem"},
                ),
                width="auto",
            )
        )

    if show_search:
        items.append(
            dbc.Col(
                dbc.Input(
                    id=search_id,
                    placeholder="검색 (ID / 이름)…",
                    type="search",
                    className="form-control-sm shadow-sm",
                    style={"width": "200px"},
                ),
                width="auto",
            )
        )

    return dbc.Card(
        dbc.CardBody(
            dbc.Row(items, className="g-2 align-items-center"),
        ),
        className="mb-3 border-0 shadow-sm rounded-4",
        style={"backgroundColor": "#f8fafc"},
    )


# ─────────────────────────────────────────────────────
# 기본 그리드 컬럼 정의 (Project-based ID 체계 반영)
# ─────────────────────────────────────────────────────
def base_id_columns(show_project: bool = True) -> list[dict]:
    """
    모든 그리드에 공통으로 들어가는 좌측 고정 ID 컬럼.

    Project-based ID 체계:
        project_id  : CBNIPT-202507-0001
        sample_id   : CBNIPT-202507-0001-S001
        library_id  : CBNIPT-202507-0001-S001-L001
    """
    cols = []

    if show_project:
        cols.append({
            "headerName": "Project",
            "field": "project_id",
            "width": 180,
            "pinned": "left",
            "editable": False,
            "rowGroup": True,
            "hide": True,
        })

    cols.extend([
        {
            "headerName": "Sample ID",
            "field": "sample_id",
            "width": 210,
            "pinned": "left",
            "editable": False,
            "cellStyle": {"fontWeight": "600", "color": "#0d6efd", "backgroundColor": "#f8fafc"},
        },
        {
            "headerName": "Library ID",
            "field": "library_id",
            "width": 240,
            "pinned": "left",
            "editable": False,
            "cellStyle": {"fontWeight": "600", "backgroundColor": "#f8fafc"},
        },
        {
            "headerName": "Sample Name",
            "field": "sample_name",
            "width": 160,
            "pinned": "left",
            "editable": False,
            "cellStyle": {"backgroundColor": "#fffbeb"},
        },
        {
            "headerName": "Panel",
            "field": "target_panel",
            "width": 110,
            "pinned": "left",
            "editable": False,
            "cellStyle": {"backgroundColor": "#f1f5f9", "textAlign": "center"},
        },
    ])

    return cols