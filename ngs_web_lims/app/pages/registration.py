from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime
import base64
import io

from app.pages.base import LimsDashApp  
from app.core.config import PAGES_CONFIG 
from app.core.database import SessionLocal
from app.models.schema import NGSTracking

# ==========================================
# [1] 화면 레이아웃
# ==========================================
def create_registration_layout():
    # --- 1. [신규 접수용] 테이블 구조 세팅 ---
    reg_columns = PAGES_CONFIG.get("registration", {}).get("columns", [])
    new_table_cols = []
    dropdown_config = {}
    
    for col in reg_columns:
        fmt = {"name": col["name"], "id": col["name"], "editable": True}
        if col.get("type") == "select": 
            fmt["presentation"] = "dropdown"
            dropdown_config[col["name"]] = {
                "options": [{"label": str(opt), "value": str(opt)} for opt in col.get("options", [])],
                "clearable": True
            }
        new_table_cols.append(fmt)
    
    empty_data = [{c["name"]: None for c in reg_columns} for _ in range(15)]

    # --- 2. 탭 1 컨텐츠 (다운로드 및 원본 백업 UI 적용) ---
    tab1_content = dbc.CardBody([
        
        # 1단계: 양식 선택 및 다운로드 영역
        html.H5("1. 검사 의뢰서 양식 선택", className="fw-bold text-primary mb-3"),
        dbc.Row([
            dbc.Col([
                html.Label("진행할 검사의 종류를 선택하세요", className="fw-bold text-secondary small"),
                dcc.Dropdown(
                    id="template-type-select",
                    options=[
                        {"label": "WES/WGS", "value": "wgs_request"},
                        {"label": "RNA", "value": "rna_request"},
                        {"label": "TSO", "value": "tso_resquest"}
                    ],
                    value="wgs_request",
                    clearable=False,
                    className="shadow-sm"
                )
            ], width=8),
            dbc.Col([
                html.Label("양식 다운로드", className="fw-bold text-white small"), # 줄맞춤용 투명 라벨
                dbc.Button("📥 선택한 양식 다운로드", id="btn-download-template", color="info", outline=True, className="w-100 fw-bold shadow-sm"),
                dcc.Download(id="download-template-file")
            ], width=4)
        ], className="mb-3 p-3 bg-light rounded border-top border-start border-end border-bottom-0"),
        
        # 선택된 양식 PDF 미리보기 화면 (뼈대 보여주기)
        html.Div(
            id="template-preview-container", 
            className="mb-4 p-3 bg-white border border-info rounded shadow-sm", 
            style={"minHeight": "150px", "borderWidth": "2px !important"}
        ),

        html.Hr(className="my-4 border-secondary"),

        # 2단계: 작성된 엑셀 업로드 영역
        html.H5("2. 작성된 의뢰서 업로드", className="fw-bold text-primary mb-3"),
        dcc.Upload(
            id='upload-excel-data',
            children=html.Div([
                '📂 다운로드하여 작성한 의뢰서(Excel)를 여기에 ', html.B('드래그 앤 드롭', className="text-primary"), ' 하거나 ',
                html.A('클릭하여 선택하세요.', className="text-decoration-underline text-primary fw-bold", style={'cursor': 'pointer'})
            ]),
            style={
                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '2px', 'borderStyle': 'dashed', 'borderColor': '#18BC9C',
                'borderRadius': '10px', 'textAlign': 'center', 'marginBottom': '10px',
                'backgroundColor': '#f8fffb'
            },
            multiple=False
        ),
        
        # 🚀 파일 이름 표시 영역
        html.Div(id="upload-filename-display", className="text-success fw-bold mb-3 small ms-1"),

        # 🚀 3단계: 데이터 미리보기 테이블 (주석 해제 완료!)
        LimsDashApp.create_standard_table(
            id="new-registration-table", 
            columns=new_table_cols, 
            data=empty_data,
            dropdown=dropdown_config,
            css=[
                {"selector": ".dash-spreadsheet td", "rule": "overflow: visible !important;"},
                {"selector": ".Select-menu-outer", "rule": "display: block !important; z-index: 9999 !important;"}
            ],
            style_table={'overflowX': 'auto', 'minWidth': '100%', 'minHeight': '450px'}
        ),
        
        # 저장 버튼
        dbc.Button("📥 신규 데이터 저장 및 원본 의뢰서 백업", id="btn-save-new", color="primary", className="w-100 mt-4 fw-bold py-2 shadow-sm"),
        html.Div(id="save-new-message", className="mt-3")
    ])

    # --- 3. 탭 2 컨텐츠 ---
    tab2_content = dbc.CardBody([
        html.P("1. 기존 프로젝트(Order ID)를 불러와 실험, 분석, 정산 결과를 덮어씁니다.", className="text-muted"),
        
        dbc.Row([
            dbc.Col([
                html.Label("대상 프로젝트 선택", className="fw-bold text-primary"),
                dcc.Dropdown(id="update-order-select", placeholder="Order ID 선택 (클릭)")
            ], width=6)
        ], className="mb-4 bg-light p-3 rounded border"),
        
        html.Label("2. 업데이트할 단계", className="fw-bold text-primary mb-2"),
        dbc.Tabs([
            dbc.Tab(label="📝 기본 정보", tab_id="registration"),
            dbc.Tab(label="🧪 실험/QC 결과", tab_id="wet_lab"),
            dbc.Tab(label="💻 분석/레포트", tab_id="dry_lab"),
            dbc.Tab(label="📦 정산/행정", tab_id="billing"),
        ], id="update-stage-select", active_tab="wet_lab", className="mb-3"),
        
        # 일괄 채우기 툴바
        html.Div([
            html.Span("⚡ 일괄 채우기: ", className="fw-bold text-warning me-3"),
            dcc.Dropdown(id="bulk-col-select", placeholder="컬럼 선택 (클릭)", style={"width": "230px"}, className="me-2"),
            dcc.Input(id="bulk-val-input", type="text", placeholder="값 입력 (예: O, X)", className="form-control me-2", style={"width": "200px"}),
            dbc.Button("적용", id="btn-bulk-fill", color="warning", className="fw-bold shadow-sm")
        ], className="mb-3 p-2 bg-light border rounded d-flex align-items-center"),
        
        html.Div(id="update-table-container", className="border-start border-end border-bottom p-3 bg-white"),
        
        dbc.Button("🔄 현재 단계 결과 저장 (덮어쓰기)", id="btn-save-update", color="success", className="w-100 mt-4 fw-bold py-2 shadow-sm"),
        html.Div(id="save-update-message", className="mt-3")
    ])

    # --- 4. 최종 레이아웃 ---
    return html.Div([
        html.H3("📥 데이터 등록 및 업데이트", className="fw-bold mb-4 text-secondary"),
        dbc.Tabs([
            dbc.Tab(dbc.Card(tab1_content, className="border-top-0 rounded-bottom-4 shadow-sm"), label="🆕 신규 시료 접수", tab_id="tab-new"),
            dbc.Tab(dbc.Card(tab2_content, className="border-top-0 rounded-bottom-4 shadow-sm"), label="🔄 단계별 결과 업데이트", tab_id="tab-update"),
        ], id="registration-tabs", active_tab="tab-new"),
        html.Div(id="dummy-trigger-reg", style={'display': 'none'})
    ])


# ==========================================
# [2] 콜백 로직 (Backend)
# ==========================================
def register_registration_callbacks(dash_app):
    
    # -----------------------------------------------------
    # 🚀 (신규) 1. 선택한 양식에 따라 PDF 미리보기 Iframe 띄우기
    # -----------------------------------------------------
    @dash_app.callback(
        Output("template-preview-container", "children"),
        Input("template-type-select", "value")
    )
    def update_template_preview(template_type):
        if template_type == "wgs_request":
            preview_title = "📄 [WES/WGS 검사 의뢰서] 실제 양식 미리보기"
            pdf_path = "/assets/wgs_request.pdf" 
        elif template_type == "rna_request":
            preview_title = "📄 [RNA 검사 의뢰서] 실제 양식 미리보기"
            pdf_path = "/assets/rna_request.pdf"
        elif template_type == "tso_resquest":
            preview_title = "📄 [TSO 검사 의뢰서] 실제 양식 미리보기"
            pdf_path = "/assets/tso_request.pdf"
        else:
            return html.Div()

        return html.Div([
            html.H6(preview_title, className="fw-bold text-info mb-2"),
            html.P("※ 다운로드 버튼을 누르면 이 양식의 엑셀(.xlsx) 원본 파일이 다운로드 됩니다.", className="text-muted small mb-2"),
            html.Iframe(
                src=pdf_path,
                style={"width": "100%", "height": "500px", "border": "1px solid #dee2e6", "borderRadius": "5px"}
            )
        ])

    # -----------------------------------------------------
    # 🚀 (신규) 2. 양식 파일 다운로드 버튼 로직
    # -----------------------------------------------------
    @dash_app.callback(
        Output("download-template-file", "data"),
        Input("btn-download-template", "n_clicks"),
        State("template-type-select", "value"),
        prevent_initial_call=True
    )
    def download_excel_template(n_clicks, template_type):
        # 임시 엑셀 생성 다운로드 (차후 dcc.send_file 로 실제 서버 엑셀 다운로드를 연결하시면 됩니다)
        if template_type == "wgs_request":
            df_dummy = pd.DataFrame({"Patient ID/ Sample ID": [], "Tumor Type": []})
            filename = "WES_WGS_의뢰서_양식.xlsx"
        elif template_type == "rna_request":
            df_dummy = pd.DataFrame({"Sample ID": [], "Cancer Type": []})
            filename = "RNA_의뢰서_양식.xlsx"
        else:
            df_dummy = pd.DataFrame({"Sample ID": [], "Specimen": []})
            filename = "TSO_의뢰서_양식.xlsx"
            
        return dcc.send_data_frame(df_dummy.to_excel, filename, index=False)

    # -----------------------------------------------------
    # 🚀 (신규) 3. 업로드된 파일명 화면에 표시
    # -----------------------------------------------------
    @dash_app.callback(
        Output("upload-filename-display", "children"),
        Input("upload-excel-data", "filename")
    )
    def display_uploaded_filename(filename):
        if filename:
            return f"✅ 정상적으로 파일이 업로드 되었습니다 : {filename}"
        return ""

    # -----------------------------------------------------
    # 🚀 (수정) 4. 엑셀 파서 (빈칸 제거 및 헤더 탐색)
    # -----------------------------------------------------
    @dash_app.callback(
        Output("new-registration-table", "data"),
        Input("upload-excel-data", "contents"),
        State("upload-excel-data", "filename"),
        State("new-registration-table", "data"),
        prevent_initial_call=True
    )
    def update_table_from_excel(contents, filename, current_data):
        if not contents: return no_update
        
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        try:
            if 'xls' in filename:
                # 1. 헤더 없이 임시로 읽어서 표가 시작되는 줄(행)을 찾습니다.
                df_raw = pd.read_excel(io.BytesIO(decoded), header=None)
                header_idx = 0
                
                for r in range(min(20, len(df_raw))):
                    row_vals = df_raw.iloc[r].astype(str).tolist()
                    # 'Tumor Type' 이나 'Sample ID' 가 있는 행을 헤더(표의 시작)로 인식
                    if any("Tumor Type" in val or "Sample ID" in val for val in row_vals):
                        header_idx = r
                        break
                
                # 2. 찾은 헤더 위치부터 엑셀을 제대로 다시 읽습니다.
                df = pd.read_excel(io.BytesIO(decoded), skiprows=header_idx)
                
                # 3. 예시 데이터('ex') 행과 완전히 빈 행을 삭제합니다.
                if '번호' in df.columns:
                    df = df[df['번호'].astype(str).str.lower() != 'ex']
                df = df.dropna(how='all')
                
                # 🚀 4. 고객 엑셀 컬럼 이름을 DB 컬럼 이름으로 번역!
                rename_map = {
                    "Patient ID/ Sample ID": "Sample Name",
                    "Patient ID/Sample ID": "Sample Name",
                    "Tumor Type": "Cancer Type",
                    "Specimen Type": "Specimen",
                    "Extraction 필요 유무": "추출 진행"
                }
                df = df.rename(columns=rename_map)

            elif 'csv' in filename:
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
                df = df.dropna(how='all')
            else:
                return current_data

            # 5. 날짜 형식 깔끔하게 변환
            for col in df.select_dtypes(include=['datetime64', 'datetimetz']).columns:
                df[col] = df[col].dt.strftime('%Y-%m-%d')

            return df.to_dict('records')
            
        except Exception as e:
            print(f"엑셀 읽기 오류: {e}")
            return current_data


    # -----------------------------------------------------
    # (탭 1) 신규 시료 저장 로직 (기존 유지)
    # -----------------------------------------------------
    @dash_app.callback(
        Output("save-new-message", "children"),
        Input("btn-save-new", "n_clicks"),
        State("new-registration-table", "data"),
        prevent_initial_call=True
    )
    def save_new_samples(n_clicks, table_data):
        if not n_clicks or not table_data: return ""
        df = pd.DataFrame(table_data)
        
        required_fields = ['Order ID', 'Sample Name']
        for field in required_fields:
            if field not in df.columns or df[field].astype(str).str.strip().eq("").all():
                return dbc.Alert(f"❌ 접수 실패: 필수 항목인 [{field}] 컬럼이 비어 있습니다.", color="danger")
                
        df = df[df['Sample Name'].astype(str).str.strip() != ""]
        if df.empty: return dbc.Alert("저장할 데이터가 없습니다.", color="warning")

        all_columns = [
            "Registration ID", "GMC/GCX", "Order Facility", "Reception Date", "Order ID", 
            "Order No", "Sample Name", "Sample ID", "Cancer Type", "Specimen", "추출 진행", 
            "Sample Type", "Analysis Type", "Depth/Output", "Conc.(ng/uL)", "Sample QC", 
            "검사진행 여부", "특이사항", "SEQ ID", "Outside ID 1", "Outside ID 2", "진행사항", 
            "매출", "의뢰사", "의뢰인", "sample QC report date", "seq QC report date", 
            "Quotation ID", "매출 단가", "견적서 발행", "Dead Line", "standard report date 01", 
            "standard report date 02", "advanced report date 01", "advanced report date 02", 
            "거래명세서 발행일", "문서번호", "세금계산서 발행일", "매입", "매입 단가", 
            "품의서(지출) 작성일", "품의 문서번호", "거래명세서/세금계산서 발행일", "지출결의 문서번호"
        ]
        
        db = SessionLocal()
        try:
            saved_count = 0
            today_str = datetime.now().strftime("%y%m%d")
            today_existing_count = db.query(NGSTracking).filter(
                NGSTracking.registration_id.like(f"ACC-{today_str}-%")
            ).count()
            
            for idx, row in df.iterrows():
                merged_data = {col: None for col in all_columns}
                merged_data.update(row.dropna().to_dict())
                
                order_id = merged_data.get('Order ID')
                sample_name = merged_data.get('Sample Name')
                facility = merged_data.get('Order Facility', '')
                
                if facility == "C01":
                    existing_note = str(merged_data.get('특이사항', '')).replace('None', '').strip()
                    merged_data['특이사항'] = f"[내부연구용] {existing_note}".strip()
                    merged_data['매출'] = "-"
                    merged_data['매입'] = "-"
                    merged_data['견적서 발행'] = "-"

                new_seq_num = today_existing_count + idx + 1
                reg_id = f"ACC-{today_str}-{str(new_seq_num).zfill(3)}"
                sample_id = f"{order_id}_{sample_name}"
                seq_id = f"{reg_id}_R1"
                
                merged_data["Registration ID"] = reg_id
                merged_data["Sample ID"] = sample_id
                merged_data["SEQ ID"] = seq_id
                
                if not merged_data.get("진행사항"): merged_data["진행사항"] = "접수 대기"
                
                new_entry = NGSTracking(
                    registration_id=reg_id, order_id=order_id, sample_name=sample_name,
                    seq_id=seq_id, excel_data=merged_data
                )
                db.add(new_entry)
                saved_count += 1
                
            db.commit()
            return dbc.Alert(f"✅ {saved_count}건 신규 접수 완료!", color="success")
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"데이터베이스 저장 오류: {e}", color="danger")
        finally:
            db.close()

    # -----------------------------------------------------
    # (탭 2) - 1: Order ID 드롭다운 목록
    # -----------------------------------------------------
    @dash_app.callback(
        Output("update-order-select", "options"),
        Input("dummy-trigger-reg", "id")
    )
    def load_order_ids(_):
        db = SessionLocal()
        try:
            orders = db.query(NGSTracking.order_id).distinct().all()
            return [{"label": o[0], "value": o[0]} for o in orders if o[0]]
        finally:
            db.close()

    # -----------------------------------------------------
    # (탭 2) - 2: 탭 변경 시 일괄 채우기 목록 자동 동기화
    # -----------------------------------------------------
    @dash_app.callback(
        [Output("bulk-col-select", "options"),
         Output("bulk-col-select", "value")],
        Input("update-stage-select", "active_tab")
    )
    def update_bulk_dropdown(stage):
        target_columns = PAGES_CONFIG.get(stage, {}).get("columns", [])
        options = [{"label": col["name"], "value": col["name"]} for col in target_columns]
        return options, None

    # -----------------------------------------------------
    # (탭 2) - 3: 단계별 테이블 렌더링
    # -----------------------------------------------------
    @dash_app.callback(
        Output("update-table-container", "children"),
        [Input("update-order-select", "value"), Input("update-stage-select", "active_tab")]
    )
    def render_update_table(order_id, stage):
        if not order_id: 
            return html.Div("👆 업데이트할 프로젝트(Order ID)를 선택해주세요.", className="text-muted mt-3 text-center")
        
        target_columns = PAGES_CONFIG.get(stage, {}).get("columns", [])
        
        if not target_columns:
            return dbc.Alert(f"⚠️ '{stage}' 단계 설정이 pages.yaml에 없습니다.", color="danger", className="mt-3")

        display_cols = [{"name": "Sample Name", "id": "Sample Name", "editable": False}]
        dropdown_config = {}

        for col in target_columns:
            fmt = {"name": col["name"], "id": col["name"], "editable": True}
            
            if col.get("type") == "select":
                fmt["presentation"] = "dropdown"
                dropdown_config[col["name"]] = {
                    "options": [{"label": str(opt), "value": str(opt)} for opt in col.get("options", [])],
                    "clearable": True
                }
            elif col.get("type") == "datetime":
                fmt["type"] = "datetime"
                
            display_cols.append(fmt)

        db = SessionLocal()
        try:
            query = db.query(NGSTracking).filter(NGSTracking.order_id == order_id).all()
            if not query: return html.Div("데이터가 없습니다.")
            
            datetime_cols = [c["name"] for c in target_columns if c.get("type") == "datetime"]
            
            db_data = []
            for q in query:
                row_data = q.excel_data.copy() if q.excel_data else {}
                
                for d_col in datetime_cols:
                    val = row_data.get(d_col)
                    if val and str(val).strip() not in ["None", "NaT", ""]:
                        row_data[d_col] = str(val)[:10] 
                        
                db_data.append(row_data)
            
            return LimsDashApp.create_standard_table(
                id="stage-update-table", 
                columns=display_cols, 
                data=db_data,
                dropdown=dropdown_config,
                fixed_columns={'headers': True, 'data': 1},
                css=[
                    {"selector": ".dash-spreadsheet td", "rule": "overflow: visible !important;"},
                    {"selector": ".Select-menu-outer", "rule": "display: block !important; z-index: 9999 !important;"}
                ],
                style_table={'minWidth': '100%', 'overflowX': 'auto', 'minHeight': '400px', 'overflowY': 'auto'},
                style_cell={'minWidth': '130px', 'textAlign': 'center', 'padding': '10px'}
            )
        finally:
            db.close()

    # -----------------------------------------------------
    # (탭 2) - 4: 일괄 채우기 적용 버튼
    # -----------------------------------------------------
    @dash_app.callback(
        Output("stage-update-table", "data"),
        Input("btn-bulk-fill", "n_clicks"),
        State("bulk-col-select", "value"),
        State("bulk-val-input", "value"),
        State("stage-update-table", "data"),
        prevent_initial_call=True
    )
    def apply_bulk_fill(n_clicks, target_col, target_val, current_data):
        if not n_clicks or not target_col or not current_data:
            return no_update
        fill_val = target_val if target_val else ""
        for row in current_data:
            row[target_col] = fill_val
        return current_data

    # -----------------------------------------------------
    # (탭 2) - 5: 결과 덮어쓰기 저장
    # -----------------------------------------------------
    @dash_app.callback(
        Output("save-update-message", "children"),
        Input("btn-save-update", "n_clicks"),
        State("update-order-select", "value"),
        State("stage-update-table", "data"),
        prevent_initial_call=True
    )
    def save_updated_samples(n_clicks, order_id, table_data):
        if not n_clicks or not order_id or not table_data: return ""
        db = SessionLocal()
        try:
            updated_count = 0
            for row in table_data:
                sample_name = row.get("Sample Name")
                if not sample_name: continue
                record = db.query(NGSTracking).filter(
                    NGSTracking.order_id == order_id, NGSTracking.sample_name == sample_name
                ).first()
                
                if record:
                    current_data = record.excel_data.copy() if record.excel_data else {}
                    current_data.update(row)
                    record.excel_data = current_data
                    updated_count += 1
                    
            db.commit()
            return dbc.Alert(f"✅ {updated_count}건 성공적으로 덮어쓰기 되었습니다!", color="success")
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"업데이트 오류: {e}", color="danger")
        finally:
            db.close()

def create_registration_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_registration_layout)
    app = lims.get_app()
    register_registration_callbacks(app)
    return app