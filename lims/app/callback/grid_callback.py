"""
app/callbacks/grid_callbacks.py
================================
AG Grid 공통 콜백 등록 함수.

제공:
    register_grid_callbacks(app, **ids)
        - bulk edit  : 선택 컬럼에 일괄 값 적용
        - excel 다운로드  : grid rowData → xlsx
        - excel 업로드   : xlsx → grid rowData 덮어쓰기

호출 방법 (페이지 callbacks.py 에서):
    from app.callbacks.grid_callbacks import register_grid_callbacks

    def register_callbacks(app):
        register_grid_callbacks(
            app,
            grid_id       = "sample-grid",
            bulk_select_id= "sample-bulk-col",
            bulk_input_id = "sample-bulk-val",
            bulk_apply_id = "sample-bulk-apply",
            export_id     = "sample-export",
            upload_id     = "sample-upload",
        )
        # 페이지 고유 콜백 추가 ...
"""

import base64
import io
from typing import Any

import pandas as pd
from dash import Input, Output, State, callback_context, no_update, dcc
from dash.exceptions import PreventUpdate


def register_grid_callbacks(app, **ids):
    """
    ids 키:
        grid_id, bulk_select_id, bulk_input_id, bulk_apply_id,
        export_id, upload_id
    """
    grid_id        = ids.get("grid_id")
    bulk_select_id = ids.get("bulk_select_id") or f"{grid_id}-bulk-col"
    bulk_input_id  = ids.get("bulk_input_id")  or f"{grid_id}-bulk-val"
    bulk_apply_id  = ids.get("bulk_apply_id")  or f"{grid_id}-bulk-apply"
    export_id      = ids.get("export_id")      or f"{grid_id}-export"
    upload_id      = ids.get("upload_id")      or f"{grid_id}-upload"

    if not grid_id:
        raise ValueError("grid_id 는 필수입니다.")

    # ── bulk edit ──────────────────────────────────────
    @app.callback(
        Output(grid_id, "rowData", allow_duplicate=True),
        Input(bulk_apply_id, "n_clicks"),
        State(bulk_select_id, "value"),
        State(bulk_input_id,  "value"),
        State(grid_id,        "rowData"),
        State(grid_id,        "selectedRows"),
        prevent_initial_call=True,
    )
    def apply_bulk_edit(n_clicks, col, value, row_data, selected):
        if not n_clicks or not col or value is None:
            raise PreventUpdate

        target_ids = {r.get("sample_id") for r in (selected or [])}
        updated = []
        for row in (row_data or []):
            if not target_ids or row.get("sample_id") in target_ids:
                row = {**row, col: value}
            updated.append(row)
        return updated

    # ── Excel 다운로드 ─────────────────────────────────
    @app.callback(
        Output(f"{grid_id}-download", "data"),
        Input(export_id, "n_clicks"),
        State(grid_id, "rowData"),
        prevent_initial_call=True,
    )
    def export_excel(n_clicks, row_data):
        if not n_clicks or not row_data:
            raise PreventUpdate

        df  = pd.DataFrame(row_data)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
        buf.seek(0)
        return dcc.send_bytes(buf.read(), filename="export.xlsx")

    # ── Excel 업로드 (덮어쓰기) ───────────────────────
    @app.callback(
        Output(grid_id, "rowData", allow_duplicate=True),
        Input(upload_id, "contents"),
        State(upload_id, "filename"),
        prevent_initial_call=True,
    )
    def import_excel(contents, filename):
        if not contents:
            raise PreventUpdate
        if not (filename or "").endswith((".xlsx", ".xls")):
            raise PreventUpdate

        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        df = pd.read_excel(io.BytesIO(decoded))
        return df.to_dict("records")