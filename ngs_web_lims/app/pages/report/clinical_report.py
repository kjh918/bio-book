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

    # 2. Grid 렌더링 (🌟 틀고정 및 Base 공통 양식 완벽 적용 🌟)
    @dash_app.callback(
        Output("clinical-grid-container", "children"),
        Input("clinical-batch-select", "value")
    )
    def update_clinical_grid(selected_batch):
        config = REPORT_SCHEMA_CONFIG.get("Clinical Report", {"columns": []})
        
        # 🌟 LIMS 공통 베이스 컬럼 가져오기
        base_cols = LimsDashApp.get_base_grid_columns(include_project=True)
        if base_cols:
            # 첫 번째 열(프로젝트명)에 체크박스 및 틀고정(좌측) 적용
            base_cols[0]["checkboxSelection"] = True
            base_cols[0]["headerCheckboxSelection"] = True
            base_cols[0]["pinned"] = "left" 
            base_cols[0]["width"] = 140
            
            # 두 번째 열(Sample ID)도 스크롤 시 사라지지 않도록 틀고정!
            if len(base_cols) > 1:
                base_cols[1]["pinned"] = "left"
        
        # 베이스 컬럼 뒤에 상태 및 Clinical 전용 메타데이터 컬럼 이어 붙이기
        columnDefs = base_cols + [
            {"headerName": "현재 상태", "field": "current_status", "width": 120, "cellStyle": {"fontWeight": "bold", "color": "#198754"}},
            {"headerName": "분석 상태", "field": "analysis_status", "width": 120}
        ]
        columnDefs.extend([{"headerName": col["name"], "field": col["id"], "width": 130} for col in config["columns"]])
        
        db = SessionLocal()
        try:
            query = db.query(Sample)
            if selected_batch and selected_batch != "ALL": 
                query = query.filter(Sample.sample_id.like(f"{selected_batch}-%"))
            samples = query.all()
            
            data = []
            for s in samples:
                a_status = s.analysis.analysis_status if s.analysis else "대기중"
                # base_cols가 요구하는 매핑 데이터 통합
                row = {
                    "id": s.id, 
                    "project_name": s.project_name, 
                    "order_id": s.order_id,
                    "sample_id": s.sample_id, 
                    "sample_name": s.sample_name, 
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    "analysis_status": a_status
                }
                # 추가 메타데이터 파싱
                for col in config["columns"]:
                    col_id = col["id"]
                    val = getattr(s, col_id, "")
                    if not val and s.panel_metadata: val = s.panel_metadata.get(col_id, "")
                    row[col_id] = val
                data.append(row)
                
            # 높이를 모니터 해상도에 반응하도록 40vh로 변경
            grid = LimsDashApp.create_standard_aggrid(id="clinical-ag-grid", columnDefs=columnDefs, height="40vh")
            grid.dashGridOptions["rowSelection"] = "multiple"
            # 행을 클릭했을 때가 아니라 '체크박스'를 눌렀을 때만 선택되도록 설정 (실무 UI 최적화)
            grid.dashGridOptions["suppressRowClickSelection"] = True 
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