from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from datetime import datetime
import os
import base64
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, Order, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR

def create_report_view_layout():
    return html.Div([
        # 🚀 페이지 헤더
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:document-report", className="me-2 text-dark"), "Report Management"], className="fw-bold text-dark"),
                html.P("QC 및 임상 보고서 양식을 설정하고 PDF로 발행합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        dbc.Tabs(id="report-tabs", active_tab="QC Report", children=[
            dbc.Tab(label="🔬 QC Report", tab_id="QC Report"),
            dbc.Tab(label="📋 Clinical Report", tab_id="Clinical Report"),
        ], className="nav-fill mb-4"),

        # 🚀 대기열 카드 (표준 AG Grid 적용)
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("📌 접수 배치(Batch) 필터", className="fw-bold small text-muted mb-1"),
                        dbc.Select(id="report-batch-select", options=[{"label": "전체 보기", "value": "ALL"}], value="ALL", className="shadow-sm rounded-3", style={"width": "250px"})
                    ], width="auto"),
                    dbc.Col(html.H5(id="report-grid-title", className="fw-bold m-0 mt-4 text-center"), align="center"),
                    dbc.Col([
                        dbc.Button([DashIconify(icon="carbon:settings-adjust", className="me-2"), "양식 설정"], 
                                   id="btn-open-settings", color="light", className="fw-bold shadow-sm border rounded-3 text-secondary mt-3")
                    ], width="auto", className="text-end")
                ], className="mb-4 d-flex justify-content-between"),
                
                # AG Grid 컨테이너
                html.Div(id="ag-grid-container") 
            ])
        ], className="border-0 shadow-sm rounded-4 mb-4"),
        
        # 🚀 보고서 빌더 영역
        html.Div(id="report-builder-section", style={"display": "none"}, children=[
            html.Hr(className="my-5 border-2 text-secondary"),
            
            dbc.Row([
                # 좌측: 입력 폼
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("1. 양식 및 첨부파일 설정", className="fw-bold mb-0")),
                        dbc.CardBody([
                            html.Label("적용할 레포트 템플릿", className="fw-bold text-primary"),
                            dcc.Dropdown(
                                id="report-template-select", 
                                options=[
                                    {"label": "기본 DNA QC 레포트", "value": "sample_qc_dna_report"},
                                    {"label": "기본 RNA QC 레포트", "value": "sample_qc_rna_report"},
                                    # 🚀 GMC TSO 레포트로 템플릿명 변경 적용
                                    {"label": "TSO500 QC 레포트 (DNA/RNA 통합)", "value": "sample_qc_gmc_tso_report"},
                                    {"label": "최종 분석 레포트", "value": "advanced_analysis"}
                                ], 
                                value="sample_qc_gmc_tso_report", 
                                clearable=False, 
                                className="mb-3"
                            ),
                            
                            html.Label("보고서 타이틀", className="fw-bold text-primary small"),
                            dbc.Input(id="report-title-input", placeholder="예: NGS 품질 검사 결과지", className="mb-3"),
                            
                            html.Label("총괄 책임자 서명", className="fw-bold text-primary small"),
                            dbc.Input(id="report-author-input", placeholder="책임자 이름 입력", className="mb-4"),
                            
                            html.Hr(),
                            
                            html.Label("📊 첨부 이미지 (다중 첨부 가능)", className="fw-bold text-primary mt-2"),
                            dcc.Upload(
                                id='upload-report-image', 
                                children=html.Div(['드래그 앤 드롭 또는 클릭하여 이미지 첨부']), 
                                style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '2px', 'borderStyle': 'dashed', 'borderColor': '#3498DB', 'borderRadius': '5px', 'textAlign': 'center', 'backgroundColor': '#f4f9fc', 'cursor': 'pointer'},
                                multiple=True
                            ),
                            html.Div(id="upload-image-preview", className="mt-2 text-muted small"),
                            
                            html.Hr(className="mt-4"),
                            dcc.Download(id="download-pdf-file"),
                            dbc.Button([DashIconify(icon="carbon:document-pdf", className="me-2"), "🖨️ 최종 PDF 생성 및 다운로드"], 
                                       id="btn-download-pdf", color="danger", className="w-100 fw-bold py-2 shadow-sm"),
                            html.Div(id="generate-report-message", className="mt-3 text-center")
                        ])
                    ], className="border-0 shadow-sm rounded-4 h-100")
                ], xs=12, lg=4),
                
                # 우측: Iframe 라이브 미리보기
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("2. A4 라이브 미리보기", className="fw-bold mb-0")),
                        dbc.CardBody([
                            html.Div(id="report-live-preview-container") 
                        ], className="bg-light p-0 rounded-bottom-4 overflow-hidden") 
                    ], className="border-0 shadow-sm rounded-4 h-100")
                ], xs=12, lg=8)
            ])
        ])
    ], className="pb-5", style={"padding": "20px"})


def register_report_callbacks(dash_app):
    
    # 1. 배치 목록
    @dash_app.callback(
        [Output("report-batch-select", "options"), Output("report-batch-select", "value")],
        Input("report-tabs", "active_tab")
    )
    def update_batch_dropdown(_):
        db = SessionLocal()
        try:
            samples = db.query(Sample.sample_id).all()
            batches = sorted(list({f"{s_id[0].split('-')[0]}-{s_id[0].split('-')[1]}-{s_id[0].split('-')[2]}" for s_id in samples if s_id[0] and s_id[0].count("-") >= 2}), reverse=True)
            return [{"label": "전체 보기", "value": "ALL"}] + [{"label": f"📦 배치: {b}", "value": b} for b in batches], "ALL"
        finally: db.close()

    # 2. Grid 렌더링
    @dash_app.callback(
        [Output("ag-grid-container", "children"), Output("report-grid-title", "children")],
        [Input("report-tabs", "active_tab"), Input("report-batch-select", "value")]
    )
    def update_grid(active_tab, selected_batch):
        if not active_tab: return no_update, ""
        
        config = REPORT_SCHEMA_CONFIG.get(active_tab, {"columns": []})
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
                order_info = s.order 
                row = {
                    "sample_id": s.sample_id,
                    "order_id": s.order_id,
                    "sample_name": s.sample_name,
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    "facility": order_info.facility if order_info else "-",
                    "client_team": order_info.client_team if order_info else "-",
                    "reception_date": str(order_info.reception_date)[:10] if order_info and order_info.reception_date else "-",
                    "issue_comment": s.issue_comment or ""
                }
                
                for col in config["columns"]:
                    col_id = col["id"]
                    val = getattr(s, col_id, "")
                    if not val and s.panel_metadata:
                        val = s.panel_metadata.get(col_id, "")
                    row[col_id] = val
                data.append(row)
                
            grid = LimsDashApp.create_standard_aggrid(
                id="report-ag-grid",
                columnDefs=columnDefs,
                height="400px"
            )
            grid.dashGridOptions["rowSelection"] = "multiple"
            grid.dashGridOptions["suppressRowClickSelection"] = True
            grid.rowData = data
            
            return grid, f"{active_tab} 작성 대상"
        finally: db.close()

    # 3. Jinja2 데이터 준비 헬퍼 함수 
    def prepare_jinja_data(selected_rows, img_contents):
        mapped_samples = []
        for r in selected_rows:
            dna_qc = str(r.get('dna_qc', r.get('sample_qc', r.get('current_status', 'PASS')))).strip().upper()
            rna_qc = str(r.get('rna_qc', r.get('sample_qc', r.get('current_status', 'PASS')))).strip().upper()
            
            sample_data = {
                'Sample Name': r.get('sample_name', r.get('sample_id', '')),
                
                'DNA_QC': dna_qc,
                'RNA_QC': rna_qc,
                
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

    # 4. 미리보기 (Iframe 렌더링)
    @dash_app.callback(
        [Output("report-builder-section", "style"),
         Output("report-live-preview-container", "children"),
         Output("upload-image-preview", "children")],
        [Input("btn-open-settings", "n_clicks"),
         Input("report-template-select", "value"),
         Input("report-title-input", "value"), 
         Input("report-author-input", "value"), 
         Input("upload-report-image", "contents"),
         Input("upload-report-image", "filename")],
        [State("report-ag-grid", "selectedRows")],
        prevent_initial_call=True
    )
    def update_report_preview(btn_click, template_type, title, author, img_contents, img_names, selected_rows):
        if not selected_rows: return {"display": "none"}, "", ""
        img_msg = f"📎 첨부됨: {', '.join(img_names)}" if img_names else "첨부된 이미지가 없습니다."

        try:
            from jinja2 import Environment, FileSystemLoader
            
            mapped_samples, pass_count, fail_count, hold_count, images = prepare_jinja_data(selected_rows, img_contents)
            first_row = selected_rows[0]

            template_path = os.path.join(BASE_DIR, "app", "templates", "reports")
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template(f"{template_type}.html")

            # 🚀 "gmc"가 템플릿 이름에 포함되어 있으면 gmc_logo.png 사용, 아니면 logo.png 사용
            logo_filename = "gmc_logo.png" if "gmc" in template_type.lower() else "logo.png"
            logo_path = os.path.join(template_path, logo_filename)
            
            logo_data_uri = ""
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_data_uri = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

            rendered_html = template.render(
                logo_path=logo_data_uri,
                order_id=first_row.get('order_id', '-'),
                report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=first_row.get("reception_date", "-"),
                customer_name=first_row.get("client_name", "-"),
                customer_organization=first_row.get("facility", "-") + '-' + first_row.get("client_team", "-"),
                customer_contact="-",
                arrival_date=first_row.get("reception_date", "-"),
                samples=mapped_samples,
                pass_count=pass_count, fail_count=fail_count, hold_count=hold_count,
                images=images
            )
            
            preview_ui = html.Iframe(
                srcDoc=rendered_html,
                style={"width": "100%", "height": "842px", "border": "none", "backgroundColor": "white"}
            )
            return {"display": "block"}, preview_ui, img_msg

        except Exception as e:
            return {"display": "block"}, html.Pre(f"렌더링 오류:\n{traceback.format_exc()}", style={"color":"red", "padding":"20px"}), img_msg

    # 5. 최종 PDF 다운로드
    @dash_app.callback(
        [Output("download-pdf-file", "data"), Output("generate-report-message", "children")],
        Input("btn-download-pdf", "n_clicks"),
        [State("report-ag-grid", "selectedRows"), State("report-template-select", "value"), State("upload-report-image", "contents")],
        prevent_initial_call=True
    )
    def download_pdf(n_clicks, selected_rows, template_type, image_contents):
        if not selected_rows: return no_update, dbc.Alert("선택된 샘플이 없습니다.", color="warning")

        import weasyprint
        from jinja2 import Environment, FileSystemLoader

        try:
            mapped_samples, pass_count, fail_count, hold_count, images = prepare_jinja_data(selected_rows, image_contents)
            first_row = selected_rows[0]

            template_path = os.path.join(BASE_DIR, "app", "templates", "reports")
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template(f"{template_type}.html") 
            
            # 🚀 동일한 로고 동적 할당 로직 적용
            logo_filename = "gmc_logo.png" if "gmc" in template_type.lower() else "logo.png"
            logo_path = os.path.join(template_path, logo_filename)
            
            logo_data_uri = ""
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_data_uri = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
            
            html_out = template.render(
                logo_path=logo_data_uri,
                order_id=first_row.get('order_id', '-'),
                report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=first_row.get("reception_date", "-"),
                customer_name=first_row.get("client_team", "-"),
                customer_organization=first_row.get("client_team", "-"),
                customer_contact="-",
                arrival_date=first_row.get("reception_date", "-"),
                samples=mapped_samples, 
                pass_count=pass_count, fail_count=fail_count, hold_count=hold_count,
                images=images
            )
            
            pdf_bytes = weasyprint.HTML(string=html_out).write_pdf()
            filename = f"Report_{first_row.get('order_id', 'QC')}_{datetime.now().strftime('%y%m%d_%H%M')}.pdf"
            
            return dcc.send_bytes(pdf_bytes, filename), dbc.Alert("✅ PDF 다운로드가 완료되었습니다!", color="success")
            
        except Exception as e:
            return no_update, dbc.Alert(f"❌ PDF 생성 오류: {e}", color="danger")

def create_report_view_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_report_view_layout)
    app = lims.get_app() 
    register_report_callbacks(app)
    return app