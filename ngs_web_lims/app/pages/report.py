from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime

from app.pages.base import LimsDashApp  
from app.core.database import SessionLocal
from app.models.schema import NGSTracking

# ==========================================
# [1] 화면 레이아웃
# ==========================================
def create_report_layout():
    return dbc.Container([
        html.H3("📄 레포트 자동 생성기", className="fw-bold mb-4 text-secondary"),
        
        dbc.Row([
            # 왼쪽 패널: 데이터 선택 및 옵션
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("1. 데이터 및 템플릿 선택", className="fw-bold mb-0")),
                    dbc.CardBody([
                        html.Label("대상 프로젝트 (Order ID)", className="fw-bold text-primary"),
                        dcc.Dropdown(id="report-order-select", placeholder="Order ID 선택", className="mb-3"),
                        
                        html.Label("적용할 레포트 템플릿", className="fw-bold text-primary mt-2"),
                        dcc.Dropdown(
                            id="report-template-select",
                            options=[
                                {"label": "기본 DNA QC 레포트 (Standard)", "value": "sample_qc_dna_report"},
                                {"label": "기본 RNA QC 레포트 (Standard)", "value": "sample_qc_rna_report"},
                                {"label": "최종 분석 레포트 (Advanced)", "value": "advanced_analysis"},
                                {"label": "내부 연구용 요약본", "value": "internal_summary"}
                            ],
                            value="sample_qc_rna_report", # 초기값을 존재하는 템플릿으로 변경
                            clearable=False,
                            className="mb-3"
                        ),
                        
                        html.Label("📊 첨부 이미지 (선택사항)", className="fw-bold text-primary mt-2"),
                        dcc.Upload(
                            id='upload-report-image',
                            children=html.Div(['드래그 앤 드롭 또는 ', html.A('클릭하여 이미지 첨부')]),
                            style={
                                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                                'borderWidth': '2px', 'borderStyle': 'dashed', 'borderColor': '#3498DB',
                                'borderRadius': '5px', 'textAlign': 'center', 'backgroundColor': '#f4f9fc'
                            },
                            multiple=True # 여러 장 첨부 가능
                        ),
                        html.Div(id="report-image-preview", className="mt-2 text-muted small"),
                        
                        html.Hr(),
                        
                        # 🚀 다운로드 트리거를 위한 숨겨진 컴포넌트
                        dcc.Download(id="download-report-file"),
                        
                        dbc.Button(
                            "🖨️ 레포트 생성 및 다운로드", 
                            id="btn-generate-report", 
                            color="danger", 
                            className="w-100 fw-bold py-2 shadow-sm"
                        ),
                        html.Div(id="generate-report-message", className="mt-3")
                    ])
                ], className="shadow-sm border-top-0 rounded-bottom-4")
            ], width=4),
            
            # 오른쪽 패널: 포함될 샘플 데이터 미리보기
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("2. 포함될 데이터 미리보기", className="fw-bold mb-0")),
                    dbc.CardBody([
                        html.P("레포트에 인쇄될 샘플들의 최종 데이터입니다.", className="text-muted"),
                        html.Div(id="report-preview-table-container", className="border rounded p-2 bg-light", style={'minHeight': '300px'})
                    ])
                ], className="shadow-sm border-top-0 rounded-bottom-4 h-100")
            ], width=8)
        ])
    ], fluid=True, className="py-4")

# ==========================================
# [2] 콜백 로직 (Backend)
# ==========================================
def register_report_callbacks(dash_app):
    
    # -----------------------------------------------------
    # 1. Order ID 목록 불러오기 (페이지 로드 시)
    # -----------------------------------------------------
    @dash_app.callback(
        Output("report-order-select", "options"),
        Input("report-order-select", "id") # 더미 트리거
    )
    def load_order_ids(_):
        db = SessionLocal()
        try:
            orders = db.query(NGSTracking.order_id).distinct().all()
            return [{"label": o[0], "value": o[0]} for o in orders if o[0]]
        finally:
            db.close()

    # -----------------------------------------------------
    # 2. 선택한 프로젝트의 데이터 미리보기 표 렌더링
    # -----------------------------------------------------
    @dash_app.callback(
        Output("report-preview-table-container", "children"),
        Input("report-order-select", "value")
    )
    def update_preview_table(order_id):
        if not order_id:
            return html.Div("👈 왼쪽에서 프로젝트를 선택해주세요.", className="text-center text-muted mt-5")
            
        db = SessionLocal()
        try:
            query = db.query(NGSTracking).filter(NGSTracking.order_id == order_id).all()
            if not query: return "데이터가 없습니다."
            
            db_data = [q.excel_data for q in query]
            
            # 미리보기용 핵심 컬럼만 추출
            preview_cols = ["Sample Name", "Sample Type", "Conc.(ng/uL)", "Sample QC", "Depth/Output"]
            display_cols = [{"name": col, "id": col} for col in preview_cols]
            
            from app.pages.base import LimsDashApp
            return LimsDashApp.create_standard_table(
                id="report-preview-table",
                columns=display_cols,
                data=db_data,
                style_table={'overflowX': 'auto', 'minHeight': '300px'}
            )
        finally:
            db.close()

    # -----------------------------------------------------
    # 3. 이미지 첨부 시 파일명 미리보기
    # -----------------------------------------------------
    @dash_app.callback(
        Output("report-image-preview", "children"),
        Input("upload-report-image", "filename")
    )
    def preview_images(filenames):
        if not filenames: return ""
        if isinstance(filenames, str): filenames = [filenames]
        return f"📎 첨부됨: {', '.join(filenames)}"

    # -----------------------------------------------------
    # 🚀 4. [핵심] 레포트 생성 및 다운로드 (Base64 로고 변환 적용)
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("download-report-file", "data"),
         Output("generate-report-message", "children")],
        Input("btn-generate-report", "n_clicks"),
        State("report-order-select", "value"),
        State("report-template-select", "value"),
        State("report-preview-table", "data"),      
        State("upload-report-image", "contents"),   
        prevent_initial_call=True
    )
    def generate_and_download_report(n_clicks, order_id, template_type, table_data, image_contents):
        if not n_clicks or not order_id or not table_data:
            return no_update, dbc.Alert("대상 프로젝트를 먼저 선택해주세요.", color="warning")

        import weasyprint
        from jinja2 import Environment, FileSystemLoader
        from datetime import datetime
        import os
        import base64
        from app.core.config import BASE_DIR

        try:
            # 1. Jinja2 템플릿 환경 설정 ('report' 폴더 안의 html 파일 로드)
            template_path = os.path.join(BASE_DIR, "app", "report")
            
            # Jinja2 환경에 절대 경로 주입
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template(f"{template_type}.html") 
            
            # 🚀 2. 로고 이미지를 읽어서 Base64 문자열로 인코딩 (절대 깨지지 않음)
            logo_file_path = "/storage/home/jhkim/scripts/bio-book/ngs_web_lims/app/report/logo.png"
            logo_data_uri = ""
            try:
                with open(logo_file_path, "rb") as img_file:
                    logo_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                    logo_data_uri = f"data:image/png;base64,{logo_b64}"
            except Exception as img_err:
                print(f"⚠️ 로고 이미지를 불러오지 못했습니다: {img_err}")
                # 로고가 없더라도 레포트 생성 자체는 계속 진행되도록 빈 문자열 유지
            
            # 3. 통계 변수 계산 (Pass, Hold, Fail 개수 세기)
            pass_count = sum(1 for row in table_data if str(row.get('Sample QC', '')).upper() == 'PASS')
            fail_count = sum(1 for row in table_data if str(row.get('Sample QC', '')).upper() == 'FAIL')
            hold_count = sum(1 for row in table_data if str(row.get('Sample QC', '')).upper() == 'HOLD')
            
            # DB 데이터 중 첫 번째 행을 기준으로 공통 정보(의뢰인, 날짜 등) 추출
            first_row = table_data[0] if table_data else {}
            
            # 4. HTML 템플릿에 데이터 밀어넣기
            html_out = template.render(
                logo_path=logo_data_uri, # 🚀 인코딩된 로고 데이터 전달
                order_id=order_id,
                report_date=datetime.now().strftime("%Y-%m-%d"),
                order_date=str(first_row.get("Reception Date", ""))[:10],
                customer_name=first_row.get("의뢰인", "-"),
                customer_organization=first_row.get("의뢰사", "-"),
                customer_contact="-", # 필요시 스키마에 추가
                arrival_date=str(first_row.get("Reception Date", ""))[:10],
                
                samples=table_data,
                pass_count=pass_count,
                fail_count=fail_count,
                hold_count=hold_count,
                images=image_contents if image_contents else []
            )
            
            # 5. WeasyPrint를 사용해 HTML을 PDF로 변환
            pdf_bytes = weasyprint.HTML(string=html_out).write_pdf()
            filename = f"QC_Report_{order_id}_{datetime.now().strftime('%y%m%d')}.pdf"
            
            # 6. 완성된 PDF 다운로드!
            return dcc.send_bytes(pdf_bytes, filename), dbc.Alert("✅ PDF 레포트 생성이 완료되었습니다!", color="success")
            
        except Exception as e:
            return no_update, dbc.Alert(f"❌ PDF 생성 중 오류 발생: {e}", color="danger")

def create_report_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_report_layout)
    app = lims.get_app()
    register_report_callbacks(app)
    return app