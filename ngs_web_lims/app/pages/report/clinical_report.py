from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from datetime import datetime
import os
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp

# 🚀 공통 레이아웃 함수 가져오기
from app.pages.report.base import create_shared_report_layout

def get_clinical_report_layout():
    clinical_templates = [
        {"label": "TSO500 Clinical Report", "value": "gmc_tso_clinical_report"},
        {"label": "cbNIPT Clinical Report", "value": "cbnipt_clinical_report"},
    ]
    return create_shared_report_layout(prefix="clinical", title="Clinical Report 작성 대상", template_options=clinical_templates)


def register_clinical_callbacks(dash_app):
    
    # 1. 배치 목록 업데이트
    @dash_app.callback(
        [Output("clinical-batch-select", "options"), Output("clinical-batch-select", "value")],
        Input("clinical-batch-select", "id") # 더미 트리거
    )
    def update_clinical_batch(_):
        db = SessionLocal()
        try:
            samples = db.query(Sample.sample_id).all()
            batches = sorted(list({f"{s_id[0].split('-')[0]}-{s_id[0].split('-')[1]}-{s_id[0].split('-')[2]}" for s_id in samples if s_id[0] and s_id[0].count("-") >= 2}), reverse=True)
            return [{"label": "전체 보기", "value": "ALL"}] + [{"label": f"📦 배치: {b}", "value": b} for b in batches], "ALL"
        finally: db.close()

    # 2. Grid 렌더링
    @dash_app.callback(
        Output("clinical-grid-container", "children"),
        Input("clinical-batch-select", "value")
    )
    def update_clinical_grid(selected_batch):
        config = REPORT_SCHEMA_CONFIG.get("Clinical Report", {"columns": []})
        columnDefs = [
            {"headerName": "선택", "field": "order_id", "pinned": "left", "width": 80, "checkboxSelection": True, "headerCheckboxSelection": True},
            {"headerName": "Order ID", "field": "order_id", "width": 150},
            {"headerName": "Patient ID", "field": "sample_id", "width": 160},
            {"headerName": "패널", "field": "target_panel", "width": 120},
            {"headerName": "현재 상태", "field": "current_status", "width": 120},
        ]
        columnDefs.extend([{"headerName": col["name"], "field": col["id"], "width": 130} for col in config["columns"]])
        
        db = SessionLocal()
        try:
            query = db.query(Sample)
            if selected_batch and selected_batch != "ALL": query = query.filter(Sample.sample_id.like(f"{selected_batch}-%"))
            samples = query.all()
            data = []
            for s in samples:
                row = {
                    "sample_id": s.sample_id, "order_id": s.order_id, 
                    "target_panel": s.target_panel, "current_status": s.current_status
                }
                for col in config["columns"]:
                    col_id = col["id"]
                    val = getattr(s, col_id, "")
                    if not val and s.panel_metadata: val = s.panel_metadata.get(col_id, "")
                    row[col_id] = val
                data.append(row)
                
            grid = LimsDashApp.create_standard_aggrid(id="clinical-ag-grid", columnDefs=columnDefs, height="400px")
            grid.dashGridOptions["rowSelection"] = "multiple"
            grid.rowData = data
            return grid
        finally: db.close()
        
    # 3. 토글 로직 (Clinical은 향후 로직 개발을 위해 UI만 열어둡니다)
    @dash_app.callback(
        Output("clinical-builder-section", "style"),
        Input("clinical-btn-open-settings", "n_clicks"), prevent_initial_call=True
    )
    def toggle_clinical_settings(n_clicks):
        return {"display": "block"} if n_clicks else {"display": "none"}