from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
import pandas as pd
from datetime import datetime
import os
import base64
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR # 환경에 맞게 경로 확인 필요

def create_report_view_layout():
    return html.Div([
        html.H3("📑 보고서(Report) 발행 및 관리", className="fw-bold text-secondary mb-4"),
        
        dbc.Tabs(id="report-tabs", active_tab="QC Report", children=[
            dbc.Tab(label="🔬 QC Report 대기열", tab_id="QC Report", className="pt-4"),
            dbc.Tab(label="📋 Clinical Report 대기열", tab_id="Clinical Report", className="pt-4"),
        ]),
        
        # --- 1. 대기열 Grid 영역 ---
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("📌 접수 배치(Batch) 필터", className="fw-bold small text-muted mb-1"),
                        dbc.Select(id="report-batch-select", options=[{"label": "전체 보기", "value": "ALL"}], value="ALL", className="shadow-sm", style={"width": "250px"})
                    ], width="auto"),
                    dbc.Col(html.H5(id="report-grid-title", className="fw-bold m-0 mt-4 text-center"), align="center"),
                    dbc.Col([
                        dbc.Button([DashIconify(icon="carbon:settings-adjust", className="me-2"), "보고서 양식 설정 열기"], 
                                   id="btn-open-settings", color="secondary", className="fw-bold mt-3")
                    ], width="auto", className="text-end")
                ], className="mb-3 d-flex justify-content-between"),
                
                dag.AgGrid(
                    id="report-ag-grid",
                    columnDefs=[], rowData=[],
                    defaultColDef={"sortable": True, "filter": True, "resizable": True},
                    dashGridOptions={"rowSelection": "multiple", "suppressRowClickSelection": True}, 
                    style={"height": "400px", "width": "100%"},
                    className="ag-theme-alpine"
                )
            ])
        ], className="border-0 shadow-sm rounded-4 mb-4"),
        
        # --- 2. 보고서 설정 및 미리보기 영역 ---
        html.Div(id="report-builder-section", style={"display": "none"}, children=[
            html.Hr(className="my-5 border-2 text-secondary"),
            
            dbc.Row([
                # 🛠️ 좌측: 템플릿 설정 및 이미지 첨부
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("1. 양식 및 첨부파일 설정", className="fw-bold mb-0")),
                        dbc.CardBody([
                            html.Label("적용할 레포트 템플릿", className="fw-bold text-primary"),
                            dcc.Dropdown(
                                id="report-template-select",
                                options=[
                                    {"label": "기본 DNA QC 레포트 (Standard)", "value": "sample_qc_dna_report"},
                                    {"label": "기본 RNA QC 레포트 (Standard)", "value": "sample_qc_rna_report"},
                                    {"label": "최종 분석 레포트 (Advanced)", "value": "advanced_analysis"}
                                ],
                                value="sample_qc_rna_report", clearable=False, className="mb-3"
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
                            html.Div(id="generate-report-message", className="mt-3")
                        ])
                    ], className="border-0 shadow-sm rounded-4 h-100")
                ], xs=12, lg=4),
                
                # 📄 우측: Iframe 라이브 미리보기
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("2. A4 라이브 미리보기", className="fw-bold mb-0")),
                        dbc.CardBody([
                            html.Div(id="report-live-preview-container") # 여기에 Iframe이 꽂힙니다.
                        ], className="bg-light p-0") # 패딩 제거하여 Iframe이 꽉 차게
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
            batches = sorted(list({f"{s_id.split('-')[0]}-{s_id.split('-')[1]}-{s_id.split('-')[2]}" for (s_id,) in samples if s_id and s_id.count("-") >= 2}), reverse=True)
            return [{"label": "전체 보기", "value": "ALL"}] + [{"label": f"📦 배치: {b}", "value": b} for b in batches], "ALL"
        finally: db.close()

    # 2. Grid 렌더링
    @dash_app.callback(
        [Output("report-ag-grid", "columnDefs"), Output("report-ag-grid", "rowData"), Output("report-grid-title", "children")],
        [Input("report-tabs", "active_tab"), Input("report-batch-select", "value")]
    )
    def update_grid(active_tab, selected_batch):
        if not active_tab: return no_update, no_update, ""
        config = REPORT_SCHEMA_CONFIG.get(active_tab, {"columns": []})
        columnDefs = [
            {"headerName": "선택", "field": "sample_id", "pinned": "left", "width": 100, "checkboxSelection": True, "headerCheckboxSelection": True},
            {"headerName": "Order ID", "field": "order_id", "width": 140},
            {"headerName": "패널", "field": "target_panel", "width": 100},
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
                # 🚀 중요: Sample에 연결된 Order 정보를 가져옵니다. (Relationship 필요)
                order_info = s.order 
                
                # 기본 샘플 정보 + 의뢰(Order) 메타 정보 결합
                row = {
                    "sample_id": s.sample_id,
                    "order_id": s.order_id,
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    # 리포트 미리보기에 필요한 데이터들 꽂아넣기 📌
                    "facility": order_info.facility if order_info else "-",
                    "client_team": order_info.client_team if order_info else "-",
                    "reception_date": str(order_info.reception_date) if order_info and order_info.reception_date else "-",
                }
                
                # 추가 스키마 컬럼 데이터 처리
                for col in config["columns"]:
                    col_id = col["id"]
                    if hasattr(s, col_id):
                        row[col_id] = getattr(s, col_id, "")
                    elif s.panel_metadata and col_id in s.panel_metadata:
                        row[col_id] = s.panel_metadata[col_id]
                    else:
                        row[col_id] = ""
                data.append(row)
                
            return columnDefs, data, f"{active_tab} 작성 대상"
        finally: db.close()

    # 💡 헬퍼 함수: Jinja2 렌더링용 데이터를 준비합니다.
    def prepare_jinja_data(selected_rows, img_contents):
        mapped_samples = [
            {
                'Sample Name': r.get('sample_name', r.get('sample_id', '')),
                'Sample QC': r.get('sample_qc', r.get('current_status', '')),
                'Conc.(ng/uL)': r.get('concentration', ''),
                'Purity': r.get('purity', ''),
                'Volume': r.get('volume', '62'),
                'Total Amount': r.get('total_amount', ''),
                'RIN': r.get('rin', ''),
                'DIN': r.get('din', ''),
                'DV200': r.get('dv200', '')
            } for r in selected_rows
        ]
        pass_count = sum(1 for r in mapped_samples if str(r.get('Sample QC', '')).upper() == 'PASS')
        fail_count = sum(1 for r in mapped_samples if str(r.get('Sample QC', '')).upper() == 'FAIL')
        hold_count = sum(1 for r in mapped_samples if str(r.get('Sample QC', '')).upper() == 'HOLD')
        
        # 이미지 리스트화 보장
        images = img_contents if isinstance(img_contents, list) else [img_contents] if img_contents else []
        
        return mapped_samples, pass_count, fail_count, hold_count, images

    # 🚀 3. 미리보기 (Iframe과 Jinja2만 사용)
    @dash_app.callback(
        [Output("report-builder-section", "style"),
         Output("report-live-preview-container", "children"),
         Output("upload-image-preview", "children")],
        [Input("btn-open-settings", "n_clicks"),
         Input("report-template-select", "value"),
         Input("report-title-input", "value"), # 템플릿에 {{ title }} 변수가 있다면 연결하세요
         Input("report-author-input", "value"), # 템플릿에 {{ author }} 변수가 있다면 연결하세요
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

            # Jinja2 환경 로드
            template_path = os.path.join(BASE_DIR, "app", "templates", "reports")
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template(f"{template_type}.html")

            # 로고 로드
            logo_path = os.path.join(template_path, "logo.png")
            logo_data_uri = ""
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_data_uri = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

            # 렌더링
            rendered_html = template.render(
                logo_path=logo_data_uri,
                order_id=first_row.get('order_id', '-'),
                report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=str(first_row.get("reception_date", "-"))[:10] if first_row.get("reception_date") else "-",
                customer_name=first_row.get("client_team", "-"),
                customer_organization=first_row.get("facility", "-"),
                customer_contact="-",
                arrival_date=str(first_row.get("reception_date", "-"))[:10] if first_row.get("reception_date") else "-",
                samples=mapped_samples,
                pass_count=pass_count, fail_count=fail_count, hold_count=hold_count,
                images=images
            )
            
            # 심플하게 Iframe 반환 (오류 났던 `rendered_html(0.7)` 제거)
            preview_ui = html.Iframe(
                srcDoc=rendered_html,
                style={"width": "100%", "height": "842px", "border": "none", "backgroundColor": "white"}
            )
            return {"display": "block"}, preview_ui, img_msg

        except Exception as e:
            return {"display": "block"}, html.Pre(f"렌더링 오류:\n{traceback.format_exc()}", style={"color":"red", "padding":"20px"}), img_msg

    # 🚀 4. 최종 PDF 다운로드
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
            
            logo_path = os.path.join(template_path, "logo.png")
            logo_data_uri = ""
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_data_uri = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
            
            html_out = template.render(
                logo_path=logo_data_uri,
                order_id=first_row.get('order_id', '-'),
                report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=str(first_row.get("reception_date", "-"))[:10] if first_row.get("reception_date") else "-",
                customer_name=first_row.get("client_team", "-"),
                customer_organization=first_row.get("facility", "-"),
                customer_contact="-",
                arrival_date=str(first_row.get("reception_date", "-"))[:10] if first_row.get("reception_date") else "-",
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