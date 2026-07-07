import os

from dash import Dash, dash_table, html, dcc  # 수정: html, dcc 추가
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify  # 신규: 공통 툴바 icon 사용

# 우리가 만든 세련된 통합 레이아웃(상단 네비게이션바 포함)을 불러옵니다.
from app.ui.shared_ui import apply_modern_layout


class LimsDashApp:
    def __init__(self, name: str, pathname_prefix: str):
        # 🚀 [수정] FLATLY처럼 자기주장이 강한 테마 대신,
        # 순정 BOOTSTRAP을 사용하여 우리가 만든 style.css가 100% 완벽하게 적용되도록 변경!
        self.app = Dash(
            name,
            requests_pathname_prefix=pathname_prefix,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
        )

    def set_content(self, content_layout_func):
        """
        각 페이지별 고유 컨텐츠를 받아
        공통 모던 레이아웃(Top Navbar 포함) 안에 조립해주는 메서드
        """
        def serve_layout():
            # apply_modern_layout이 상단바와 배경/여백을 알아서 처리합니다.
            return apply_modern_layout(content_layout_func())

        self.app.layout = serve_layout

    def get_app(self) -> Dash:
        return self.app

    # ========================================================
    # 🚀 1. 전역 공통 컬럼 관리 (왼쪽 5대 핵심 컬럼 명칭 정립)
    # ========================================================
    @staticmethod
    def get_base_grid_columns(include_project=True):
        base_columns = []

        if include_project:
            base_columns.append({
                "headerName": "Project",
                "field": "project_name",
                "width": 150,
                "rowGroup": True,
                "hide": True,
                "pinned": "left",
            })

        base_columns.extend([
            {
                "headerName": "접수 ID (Order ID)",
                "field": "order_id",
                "width": 180,
                "pinned": "left",
                "editable": False,
                # 🚀 짙은 회색 대신, 모던하고 깔끔한 연파랑/라이트그레이 배경으로 통일
                "cellStyle": {
                    "fontWeight": "bold",
                    "backgroundColor": "#f8fafc",
                },
            },
            {
                "headerName": "샘플 ID (ACC ID)",
                "field": "sample_id",
                "width": 180,
                "pinned": "left",
                "editable": False,
                "cellStyle": {
                    "fontWeight": "bold",
                    "color": "#0d6efd",
                    "backgroundColor": "#f8fafc",
                },
            },
            {
                "headerName": "환자 ID (Patient ID)",
                "field": "sample_name",
                "width": 180,
                "pinned": "left",
                "editable": False,
                "cellStyle": {
                    "fontWeight": "bold",
                    "backgroundColor": "#fffbeb",
                },
            },
            {
                "headerName": "검사 종류",
                "field": "target_panel",
                "width": 120,
                "pinned": "left",
                "editable": False,
                "cellStyle": {
                    "backgroundColor": "#f1f5f9",
                    "textAlign": "center",
                },
            },
        ])

        return base_columns

    # ========================================================
    # 🚀 2. 표준 DataTable (모던 SaaS 테마 적용)
    # ========================================================
    @staticmethod
    def create_standard_table(id: str, columns: list, data: list, **kwargs):
        """NGS LIMS 전역에서 사용되는 반응형/표준화된 기본 DataTable"""
        default_kwargs = {
            "page_action": "none",
            "fixed_rows": {"headers": True},
            "fixed_columns": {"headers": True, "data": 4},
            "style_table": {
                "overflowX": "auto",
                "overflowY": "auto",
                "minWidth": "100%",
                "width": "100%",
                "maxHeight": "70vh",
                "border": "1px solid #e2e8f0",
                "borderRadius": "8px",
            },
            "style_header": {
                "backgroundColor": "#f8fafc",
                "color": "#475569",
                "fontWeight": "700",
                "textAlign": "center",
                "height": "45px",
                "fontSize": "13px",
                "padding": "10px",
                "border": "1px solid #e2e8f0",
            },
            "style_cell": {
                "minWidth": "120px",
                "width": "auto",
                "maxWidth": "none",
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "textAlign": "center",
                "padding": "10px",
                "backgroundColor": "#ffffff",
                "color": "#1e293b",
                "fontSize": "13px",
                "border": "1px solid #e2e8f0",
            },
            "style_data": {
                "whiteSpace": "normal",
                "height": "auto",
                "lineHeight": "1.5",
            },
            "style_data_conditional": [
                {
                    "if": {"row_index": "odd"},
                    "backgroundColor": "#fcfcfc",
                },
            ],
        }

        default_kwargs.update(kwargs)

        return dash_table.DataTable(
            id=id,
            columns=columns,
            data=data,
            **default_kwargs,
        )

    # ========================================================
    # 🚀 3. 표준 AG Grid (공통 그룹화 및 반응형 최적화)
    # ========================================================
    @staticmethod
    def create_standard_aggrid(
        id: str,
        columnDefs: list = None,
        height: str = "400px",
        rowData: list = None,  # 수정: rowData 외부 주입 가능
        **kwargs,
    ):
        final_columns = columnDefs if columnDefs else []

        grid_kwargs = {
            "id": id,
            "rowData": rowData if rowData is not None else [],  # 수정
            "columnDefs": final_columns,
            "defaultColDef": {
                "resizable": True,
                "sortable": True,
                "filter": True,
                "editable": True,
                "minWidth": 120,
            },
            "dashGridOptions": {
                "rowHeight": 45,
                "singleClickEdit": True,
                "stopEditingWhenCellsLoseFocus": True,
                "undoRedoCellEditing": True,
                "undoRedoCellEditingLimit": 50,
                "enterNavigatesVertically": True,

                "animateRows": True,
                "groupDefaultExpanded": 2,
                "autoGroupColumnDef": {
                    "headerName": "Project / 검사 종류 / 접수 계층 트리",
                    "minWidth": 320,
                    "cellRendererParams": {
                        "checkbox": True,
                    },
                },
            },
            "style": {"height": height, "width": "100%"},
            # 🚀 AG Grid도 부드러운 테마와 둥근 모서리 적용
            "className": "ag-theme-alpine border-0 shadow-sm rounded-3",
        }

        grid_kwargs.update(kwargs)

        return dag.AgGrid(**grid_kwargs)

    # ========================================================
    # 🚀 4. AG Grid 공통 툴바
    # ========================================================
    @staticmethod
    def create_aggrid_toolbar(
        bulk_select_id: str = "bulk-col-select",
        bulk_input_id: str = "bulk-val-input",
        bulk_apply_button_id: str = "btn-bulk-apply",
        export_button_id: str = "btn-export-excel",
        upload_id: str = "upload-overwrite-excel",
        show_bulk: bool = True,
        show_export: bool = True,
        show_upload: bool = True,
        title: str = "일괄 변경:",
    ):
        """
        신규:
            AG Grid 위에서 공통으로 사용하는 툴바 생성.

        포함 기능:
            - 일괄 변경 컬럼 선택
            - 일괄 변경 값 입력
            - 적용 버튼
            - 엑셀 다운로드 버튼
            - 엑셀 덮어쓰기 업로드 버튼

        주의:
            실제 callback은 각 페이지에서 기존처럼 구현.
            여기서는 UI 컴포넌트만 공통화.
        """

        left_items = []

        if show_bulk:
            left_items = [
                html.Strong(
                    [
                        DashIconify(icon="carbon:edit", className="me-1"),
                        title,
                    ],
                    className="text-secondary me-2",
                    style={"fontSize": "0.85rem"},
                ),
                dbc.Select(
                    id=bulk_select_id,
                    options=[],
                    placeholder="항목 선택…",
                    style={"width": "160px"},
                    className="me-2 shadow-sm form-select-sm",
                ),
                dbc.Input(
                    id=bulk_input_id,
                    placeholder="입력값…",
                    style={"width": "140px"},
                    className="me-2 shadow-sm form-control-sm",
                ),
                dbc.Button(
                    "적용",
                    id=bulk_apply_button_id,
                    color="primary",
                    size="sm",
                    className="fw-bold shadow-sm rounded-3",
                ),
            ]

        right_items = []

        if show_export:
            right_items.append(
                dbc.Button(
                    [
                        DashIconify(icon="carbon:download", className="me-1"),
                        "엑셀 다운로드",
                    ],
                    id=export_button_id,
                    color="light",
                    size="sm",
                    className="me-2 fw-bold shadow-sm border rounded-3 text-secondary",
                )
            )

        if show_upload:
            right_items.append(
                dcc.Upload(
                    id=upload_id,
                    children=dbc.Button(
                        [
                            DashIconify(icon="carbon:upload", className="me-1"),
                            "엑셀 덮어쓰기",
                        ],
                        color="white",
                        size="sm",
                        className=(
                            "fw-bold shadow-sm border border-primary "
                            "text-primary rounded-3"
                        ),
                    ),
                    multiple=False,
                    className="d-inline-block",
                )
            )

        return html.Div(
            [
                html.Div(
                    left_items,
                    className="d-flex align-items-center",
                ),
                html.Div(
                    right_items,
                    className="d-flex align-items-center",
                ),
            ],
            className=(
                "d-flex justify-content-between align-items-center "
                "p-3 mb-3 rounded-4 border"
            ),
            style={
                "backgroundColor": "#f8fafc",
                "borderColor": "#e2e8f0",
            },
        )

    # ========================================================
    # 🚀 5. AG Grid + 공통 툴바 묶음
    # ========================================================
    @staticmethod
    def create_aggrid_with_toolbar(
        grid_id: str,
        columnDefs: list = None,
        rowData: list = None,
        height: str = "420px",
        bulk_select_id: str = "bulk-col-select",
        bulk_input_id: str = "bulk-val-input",
        bulk_apply_button_id: str = "btn-bulk-apply",
        export_button_id: str = "btn-export-excel",
        upload_id: str = "upload-overwrite-excel",
        show_bulk: bool = True,
        show_export: bool = True,
        show_upload: bool = True,
        toolbar_title: str = "일괄 변경:",
        grid_kwargs: dict = None,
    ):
        """
        신규:
            공통 toolbar + AG Grid를 한 번에 생성.

        사용 예:
            LimsDashApp.create_aggrid_with_toolbar(
                grid_id="modal-datatable",
                height="420px",
            )
        """

        grid_kwargs = grid_kwargs or {}

        return html.Div([
            LimsDashApp.create_aggrid_toolbar(
                bulk_select_id=bulk_select_id,
                bulk_input_id=bulk_input_id,
                bulk_apply_button_id=bulk_apply_button_id,
                export_button_id=export_button_id,
                upload_id=upload_id,
                show_bulk=show_bulk,
                show_export=show_export,
                show_upload=show_upload,
                title=toolbar_title,
            ),
            LimsDashApp.create_standard_aggrid(
                id=grid_id,
                columnDefs=columnDefs,
                rowData=rowData,
                height=height,
                **grid_kwargs,
            ),
        ])