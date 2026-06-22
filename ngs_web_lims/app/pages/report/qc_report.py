from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from datetime import datetime
import os
import base64
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR

# 🚀 공통 레이아웃 함수 가져오기
from app.pages.report.base import create_shared_report_layout

def get_qc_report_layout():
    # QC 전용 템플릿 옵션
    qc_templates = [
        {"label": "TSO500 QC 레포트 (DNA/RNA 통합)", "value": "sample_qc_gmc_tso_report"},
        {"label": "기본 DNA QC 레포트", "value": "sample_qc_dna_report"},
        {"label": "기본 RNA QC 레포트", "value": "sample_qc_rna_report"}
    ]
    return create_shared_report_layout(prefix="qc", title="QC Report 작성 대상", template_options=qc_templates)


def prepare_qc_jinja_data(selected_rows, img_contents):
    mapped_samples = []
    for r in selected_rows:
        dna_qc = str(r.get('dna_qc', r.get('sample_qc', r.get('current_status', 'PASS')))).strip().upper()
        rna_qc = str(r.get('rna_qc', r.get('sample_qc', r.get('current_status', 'PASS')))).strip().upper()
        
        sample_data = {
            'Sample Name': r.get('sample_name', r.get('sample_id', '')),
            'DNA_QC': dna_qc, 'RNA_QC': rna_qc,
            'DNA_Conc': r.get('dna_concentration', r.get('concentration', '-')),
            'DNA_Vol': r.get('dna_volume', r.get('volume', '15.0')),
            'DNA_Total': r.get('dna_total_amount', r.get('total_amount', '-')),
            'Purity': r.get('purity', '-'),
            'RNA_Conc': r.get('rna_concentration', '-'),
            'RNA_Vol': r.get('rna_volume', '35.0'),
            'RNA_Total': r.get('rna_total_amount', '-'),
            'DV200': r.get('dv200', '-'),
            'Comment': r.get('issue_comment', '')
        }
        mapped_samples.append(sample_data)

    pass_count = sum(1 for r in mapped_samples if r['DNA_QC'] == 'PASS')
    fail_count = sum(1 for r in mapped_samples if r['DNA_QC'] == 'FAIL')
    hold_count = sum(1 for r in mapped_samples if r['DNA_QC'] == 'HOLD')
    
    images = img_contents if isinstance(img_contents, list) else [img_contents] if img_contents else []
    return mapped_samples, pass_count, fail_count, hold_count, images


def register_qc_callbacks(dash_app):
    
    # 1. 배치 목록 업데이트
    @dash_app.callback(
        [Output("qc-batch-select", "options"), Output("qc-batch-select", "value")],
        Input("qc-batch-select", "id") # 더미 트리거
    )
    def update_qc_batch(_):
        db = SessionLocal()
        try:
            samples = db.query(Sample.sample_id).all()
            batches = sorted(list({f"{s_id[0].split('-')[0]}-{s_id[0].split('-')[1]}-{s_id[0].split('-')[2]}" for s_id in samples if s_id[0] and s_id[0].count("-") >= 2}), reverse=True)
            return [{"label": "전체 보기", "value": "ALL"}] + [{"label": f"📦 배치: {b}", "value": b} for b in batches], "ALL"
        finally: db.close()

    # 2. Grid 렌더링
    @dash_app.callback(
        Output("qc-grid-container", "children"),
        Input("qc-batch-select", "value")
    )
    def update_qc_grid(selected_batch):
        config = REPORT_SCHEMA_CONFIG.get("QC Report", {"columns": []})
        
        # 🚀 1. 베이스 고정 컬럼 불러오기 (Kanban 방식)
        base_columns = LimsDashApp.get_base_grid_columns(include_project=False)
        
        # 첫 번째 열(Order ID)에 다중 체크박스 추가
        if base_columns:
            base_columns[0]["checkboxSelection"] = True
            base_columns[0]["headerCheckboxSelection"] = True
            base_columns[0]["width"] = 150

        # 상태 표시 컬럼 추가 (읽기 전용, 핀 고정)
        base_columns.append({
            "headerName": "현재 상태", "field": "current_status", 
            "pinned": "left", "editable": False, "width": 110,
            "cellStyle": {"color": "#64748b", "backgroundColor": "#f8fafc"}
        })

        # 🚀 2. 스키마 기반 동적 컬럼 생성 (Dropdown, Numeric 자동 인식)
        dynamic_columns = []
        for col in config["columns"]:
            ag_col = {
                "headerName": col["name"], 
                "field": col["id"], 
                "editable": col.get("editable", False), 
                "width": 130
            }
            
            # 드롭다운(선택) 옵션 렌더링
            if col.get("presentation") == "dropdown":
                ag_col["cellEditor"] = "agSelectCellEditor"
                if "options" in col:
                    ag_col["cellEditorParams"] = {"values": col["options"]}
                    
            # 숫자 필터 렌더링
            if col.get("type") == "numeric":
                ag_col["filter"] = "agNumberColumnFilter"
                
            dynamic_columns.append(ag_col)
            
        # 최종 컬럼 통합
        columnDefs = base_columns + dynamic_columns

        # 🚀 3. 스마트 데이터 로딩
        db = SessionLocal()
        try:
            query = db.query(Sample)
            if selected_batch and selected_batch != "ALL": 
                query = query.filter(Sample.sample_id.like(f"{selected_batch}-%"))
            samples = query.all()
            
            data = []
            for s in samples:
                # 기본 정보
                row = {
                    "id": s.id,
                    "order_id": s.order_id, 
                    "sample_id": s.sample_id, 
                    "sample_name": s.sample_name,
                    "target_panel": s.target_panel, 
                    "current_status": s.current_status,
                }
                
                # 🌟 테이블 자동 순회 탐색 로직 (Sample -> Order -> WetLab -> Seq -> Analysis -> JSON)
                for col in config["columns"]:
                    col_id = col["id"]
                    val = None
                    
                    if hasattr(s, col_id): val = getattr(s, col_id)
                    elif s.order and hasattr(s.order, col_id): val = getattr(s.order, col_id)
                    elif s.wet_lab and hasattr(s.wet_lab, col_id): val = getattr(s.wet_lab, col_id)
                    elif s.sequencing and hasattr(s.sequencing, col_id): val = getattr(s.sequencing, col_id)
                    elif s.analysis and hasattr(s.analysis, col_id): val = getattr(s.analysis, col_id)
                    
                    if val is None and s.panel_metadata: 
                        val = s.panel_metadata.get(col_id, "")
                        
                    row[col_id] = val if val is not None else ""
                
                # 🌟 PDF 레포트 출력을 위한 Hidden(숨김) 필수 컬럼 주입
                # 화면 스키마에는 없더라도, Jinja2 템플릿이 요구하는 값은 DB에서 꺼내어 row에 숨겨 담아줍니다.
                if s.wet_lab:
                    hidden_keys = ["dna_volume", "dna_total_amount", "purity", "rna_volume", "rna_total_amount", "dv200", "rin"]
                    for hk in hidden_keys:
                        if hk not in row:
                            row[hk] = getattr(s.wet_lab, hk, "")
                            
                data.append(row)
                
            # 표준 Grid 팩토리 호출
            grid = LimsDashApp.create_standard_aggrid(id="qc-ag-grid", columnDefs=columnDefs, height="400px")
            grid.dashGridOptions["rowSelection"] = "multiple"
            grid.dashGridOptions["suppressRowClickSelection"] = True
            grid.rowData = data
            return grid
            
        finally: 
            db.close()

    # 3. 라이브 미리보기 렌더링
    @dash_app.callback(
        [Output("qc-builder-section", "style"), Output("qc-live-preview-container", "children"), Output("qc-upload-preview", "children")],
        [Input("qc-btn-open-settings", "n_clicks"), Input("qc-template-select", "value"), Input("qc-title-input", "value"), 
         Input("qc-author-input", "value"), Input("qc-upload-image", "contents"), Input("qc-upload-image", "filename")],
        [State("qc-ag-grid", "selectedRows")], prevent_initial_call=True
    )
    def update_qc_preview(btn_click, template_type, title, author, img_contents, img_names, selected_rows):
        if not selected_rows: return {"display": "none"}, "", ""
        img_msg = f"📎 첨부됨: {', '.join(img_names)}" if img_names else "첨부된 이미지가 없습니다."
        try:
            from jinja2 import Environment, FileSystemLoader
            mapped_samples, pass_count, fail_count, hold_count, images = prepare_qc_jinja_data(selected_rows, img_contents)
            first_row = selected_rows[0]

            template_path = os.path.join(BASE_DIR, "app", "templates", "reports")
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template(f"{template_type}.html")

            logo_filename = "gmc_logo.png" if "gmc" in template_type.lower() else "logo.png"
            logo_path = os.path.join(template_path, logo_filename)
            logo_data_uri = f"data:image/png;base64,{base64.b64encode(open(logo_path, 'rb').read()).decode('utf-8')}" if os.path.exists(logo_path) else ""

            rendered_html = template.render(
                logo_path=logo_data_uri, order_id=first_row.get('order_id', '-'), report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=first_row.get("reception_date", "-"), customer_name=first_row.get("client_name", "-"),
                customer_organization=first_row.get("client_team", "-"), customer_contact="-",
                arrival_date=first_row.get("reception_date", "-"), samples=mapped_samples,
                pass_count=pass_count, fail_count=fail_count, hold_count=hold_count, images=images
            )
            return {"display": "block"}, html.Iframe(srcDoc=rendered_html, style={"width": "100%", "height": "842px", "border": "none"}), img_msg
        except Exception as e:
            return {"display": "block"}, html.Pre(f"오류:\n{traceback.format_exc()}", style={"color":"red"}), img_msg

    # 4. 최종 PDF 생성 (WeasyPrint)
    @dash_app.callback(
        [Output("qc-download-pdf-file", "data"), Output("qc-generate-message", "children")],
        Input("qc-btn-download-pdf", "n_clicks"),
        [State("qc-ag-grid", "selectedRows"), State("qc-template-select", "value"), State("qc-upload-image", "contents")], prevent_initial_call=True
    )
    def download_qc_pdf(n_clicks, selected_rows, template_type, image_contents):
        if not selected_rows: return no_update, dbc.Alert("선택된 샘플이 없습니다.", color="warning")
        import weasyprint
        from jinja2 import Environment, FileSystemLoader
        try:
            mapped_samples, pass_count, fail_count, hold_count, images = prepare_qc_jinja_data(selected_rows, image_contents)
            first_row = selected_rows[0]
            template_path = os.path.join(BASE_DIR, "app", "templates", "reports")
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template(f"{template_type}.html") 
            
            logo_filename = "gmc_logo.png" if "gmc" in template_type.lower() else "logo.png"
            logo_path = os.path.join(template_path, logo_filename)
            logo_data_uri = f"data:image/png;base64,{base64.b64encode(open(logo_path, 'rb').read()).decode('utf-8')}" if os.path.exists(logo_path) else ""
            
            html_out = template.render(
                logo_path=logo_data_uri, order_id=first_row.get('order_id', '-'), report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=first_row.get("reception_date", "-"), customer_name=first_row.get("client_team", "-"),
                customer_organization=first_row.get("client_team", "-"), customer_contact="-",
                arrival_date=first_row.get("reception_date", "-"), samples=mapped_samples, 
                pass_count=pass_count, fail_count=fail_count, hold_count=hold_count, images=images
            )
            pdf_bytes = weasyprint.HTML(string=html_out).write_pdf()
            filename = f"QC_Report_{first_row.get('order_id', 'QC')}_{datetime.now().strftime('%y%m%d')}.pdf"
            return dcc.send_bytes(pdf_bytes, filename), dbc.Alert("✅ PDF 다운로드 완료!", color="success")
        except Exception as e:
            return no_update, dbc.Alert(f"❌ PDF 생성 오류: {e}", color="danger")