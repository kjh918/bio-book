from dash import html, dcc, Input, Output, State, no_update, ctx, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime
import base64
import io
import os
import traceback
from pathlib import Path

from app.pages.base import LimsDashApp  
from app.core.database import SessionLocal
from app.models._schema import Order, Sample
from app.core.mapping import FACILITY_MAPPING, get_full_mapping_for_panel

# 🚀 검사 선택값에 따른 엑셀 양식 파일명 매핑 사전
TEMPLATE_MAP = {
    "WGS": "wgs_request",
    "WES": "wes_request",
    "WTS": "wts_request",
    "TSO500": "tso_request",
    "dPCR": "dPCR_request"
}

# ==========================================
# [1] 화면 레이아웃
# ==========================================
def create_registration_layout():
    facility_opts = [{"label": f"[{code}] {data['facility']} ({data['team']})", "value": code} for code, data in FACILITY_MAPPING.items()]

    return html.Div([
        html.H3("📥 검사 의뢰서 신규 접수", className="fw-bold mb-4 text-secondary"),
        html.P("의뢰 기관과 검사 종류를 지정한 후 엑셀 의뢰서를 업로드해 주세요.", className="text-muted"),
        
        dbc.Card([
            dbc.CardBody([
                html.H5("1. 접수 기본 정보 설정 및 양식 다운로드", className="fw-bold text-primary mb-3"),
                dbc.Row([
                    dbc.Col([
                        html.Label("1-1. 의뢰 기관 (필수)", className="fw-bold text-danger small"),
                        dcc.Dropdown(id="reg-facility-select", options=facility_opts, placeholder="기관 코드 선택...", className="shadow-sm mb-2")
                    ], width=6),
                    dbc.Col([
                        html.Label("1-2. 검사 종류 (필수)", className="fw-bold text-danger small"),
                        dcc.Dropdown(id="reg-panel-select", options=[
                            {"label": "WGS", "value": "WGS"},
                            {"label": "WES", "value": "WES"},
                            {"label": "WTS", "value": "WTS"},
                            {"label": "TSO500", "value": "TSO500"},
                            {"label": "dPCR", "value": "dPCR"}
                        ], placeholder="검사 종류를 선택하면 아래에 양식이 나타납니다...", className="shadow-sm mb-2")
                    ], width=6)
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Button("📥 선택한 검사의 빈 양식 다운로드", id="btn-download-template", color="info", outline=True, className="w-100 fw-bold shadow-sm"),
                        dcc.Download(id="download-template-file")
                    ], width=12)
                ], className="mb-3 p-3 bg-light rounded border"),
                
                html.Div(id="template-preview-container", className="mb-4 p-3 bg-white border border-info rounded shadow-sm"),
                html.Hr(className="my-4 border-secondary"),

                html.H5("2. 작성된 의뢰서 업로드", className="fw-bold text-primary mb-3"),
                dcc.Upload(
                    id='upload-excel-data',
                    children=html.Div([
                        '📂 작성 완료된 의뢰서(Excel)를 여기에 ', html.B('드래그 앤 드롭', className="text-primary"), ' 하거나 ',
                        html.A('클릭하여 선택하세요.', className="text-decoration-underline text-primary fw-bold", style={'cursor': 'pointer'})
                    ]),
                    style={'width': '100%', 'height': '80px', 'lineHeight': '80px', 'borderWidth': '2px', 'borderStyle': 'dashed', 'borderColor': '#18BC9C', 'borderRadius': '10px', 'textAlign': 'center', 'marginBottom': '10px', 'backgroundColor': '#f8fffb'},
                    multiple=False
                ),
                html.Div(id="upload-filename-display", className="text-success fw-bold mb-3 small ms-1"),

                html.Div(id="parsed-data-container", style={"display": "none"}, children=[
                    html.H5("3. 추출된 데이터 확인", className="fw-bold text-primary mb-3 mt-4"),
                    dcc.Store(id="parsed-order-store"),
                    dbc.Alert(id="order-info-alert", color="success", className="shadow-sm py-2"),
                    dash_table.DataTable(
                        id="parsed-sample-table", columns=[], data=[],
                        style_table={'overflowX': 'auto', 'border': '1px solid #dee2e6'},
                        style_cell={'textAlign': 'center', 'padding': '10px', 'fontFamily': 'sans-serif', 'minWidth': '100px', 'whiteSpace': 'normal'},
                        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
                        page_size=10
                    ),
                    dbc.Button("🚀 추출된 데이터 LIMS에 최종 등록 (접수 대기)", id="btn-save-new", color="primary", size="lg", className="w-100 mt-4 fw-bold shadow-sm")
                ]),
                
                html.Div(id="save-new-message", className="mt-3")
            ])
        ], className="border-0 shadow-sm rounded-4")
    ])

# ==========================================
# [2] 콜백 로직
# ==========================================
def register_registration_callbacks(dash_app):
    
    @dash_app.callback(Output("template-preview-container", "children"), Input("reg-panel-select", "value"))
    def update_template_preview(panel_type):
        if not panel_type: return html.Div("👆 검사 종류(1-2)를 선택하시면 의뢰서 미리보기가 나타납니다.", className="text-muted small text-center py-2")
        template_name = TEMPLATE_MAP.get(panel_type, "wgs_request")
        excel_file_path = os.path.join(Path(__file__).parent.parent / "templates" / "requests", f"{template_name}.xlsx")
        if not os.path.exists(excel_file_path): return html.Div(f"⚠️ 양식 파일 없음: {template_name}.xlsx", className="text-danger small")
        try:
            df_raw = pd.read_excel(excel_file_path, header=None)
            header_idx = next((r for r in range(min(25, len(df_raw))) if "patientid" in "".join(df_raw.iloc[r].astype(str).tolist()).replace(" ", "").lower()), 15)
            df_preview = pd.read_excel(excel_file_path, header=header_idx).dropna(axis=1, how='all').head(5)
            df_preview.columns = [str(c) if not str(c).startswith('Unnamed') else '' for c in df_preview.columns]
            return html.Div([html.H6(f"[{panel_type}] 양식 미리보기", className="fw-bold text-primary mb-2"), dash_table.DataTable(columns=[{"name": str(i), "id": str(i)} for i in df_preview.columns if str(i)], data=df_preview.to_dict('records'), style_table={'overflowX': 'auto', 'border': '1px solid #dee2e6'}, style_cell={'textAlign': 'center', 'padding': '10px', 'fontSize': '12px'}, style_header={'backgroundColor': '#e9ecef', 'fontWeight': 'bold'})])
        except Exception as e: return html.Div(f"⚠️ 미리보기 오류: {e}", className="text-danger small")

    @dash_app.callback(
        Output("download-template-file", "data"), Input("btn-download-template", "n_clicks"), State("reg-panel-select", "value"), prevent_initial_call=True
    )
    def download_excel_template(n_clicks, panel_type):
        if not panel_type: return no_update
        file_name = f"{TEMPLATE_MAP.get(panel_type, 'wgs_request')}.xlsx"
        excel_file_path = os.path.join(Path(__file__).parent.parent / "templates" / "requests", file_name)
        return dcc.send_file(excel_file_path) if os.path.exists(excel_file_path) else dcc.send_data_frame(pd.DataFrame().to_excel, file_name, index=False)
    
    @dash_app.callback(
        [Output("parsed-data-container", "style"), Output("upload-filename-display", "children"), Output("order-info-alert", "children"), Output("parsed-sample-table", "columns"), Output("parsed-sample-table", "data")],
        Input("upload-excel-data", "contents"), [State("upload-excel-data", "filename"), State("reg-facility-select", "value"), State("reg-panel-select", "value")], prevent_initial_call=True
    )
    def parse_and_preview_excel(contents, filename, facility_code, panel_code):
        if not contents: return {"display": "none"}, "", "", [], []
        if not facility_code or not panel_code: return {"display": "none"}, dbc.Alert("🚨 업로드 전 1-1(기관)과 1-2(검사 종류)를 선택해주세요.", color="danger", className="py-2 mb-0"), "", [], []

        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            fac_info = FACILITY_MAPPING.get(facility_code, {"facility": "Unknown", "team": "Unknown"})
            
            df_raw = pd.read_excel(io.BytesIO(decoded), header=None)
            header_idx = next((r for r in range(5, min(25, len(df_raw))) if "patientid" in "".join(df_raw.iloc[r].astype(str).tolist()).replace(" ", "").lower()), 15)
            
            df_samples = pd.read_excel(io.BytesIO(decoded), header=header_idx).dropna(axis=1, how='all')
            df_samples.columns = [str(c) if not str(c).startswith('Unnamed') else f"col_{i}" for i, c in enumerate(df_samples.columns)]
            
            pid_col = next((col for col in df_samples.columns if "patient id" in col.lower() or "번호" in col.lower()), None)
            if pid_col:
                df_samples = df_samples.dropna(subset=[pid_col])
                df_samples = df_samples[df_samples[pid_col].astype(str).str.lower() != 'ex']
            
            # 🚀 [핵심 에러 픽스] 결측치(NaN)를 빈 문자열로 치환하여 JSON 통신 에러 방지
            df_samples = df_samples.fillna("")
            
            dynamic_cols = [{"name": c, "id": c} for c in df_samples.columns if "col_" not in c]
            table_data = df_samples.to_dict('records')
            
            alert_ui = html.Div([
                html.Strong("📂 타겟: "), html.Span(f"[{facility_code}] {fac_info['facility']} ({fac_info['team']}) / {panel_code}", className="me-3 text-primary"),
                html.Strong("📊 추출: "), html.Span(f"{len(table_data)}건")
            ])
            return {"display": "block"}, f"✅ {filename} 파싱 성공!", alert_ui, dynamic_cols, table_data
            
        except Exception as e:
            print(traceback.format_exc())
            return {"display": "none"}, dbc.Alert(f"🚨 파싱 오류: {e}", color="danger", className="py-2 mb-0"), "", [], []

    # 🚀 진짜 DB 저장 및 객체 생성 로직 (버튼 동작의 심장)
    # 🚀 진짜 DB 저장 및 객체 생성 로직 (버튼 동작의 심장)
    @dash_app.callback(
        Output("save-new-message", "children"),
        Input("btn-save-new", "n_clicks"),
        [State("parsed-sample-table", "data"), 
         State("reg-facility-select", "value"), 
         State("reg-panel-select", "value"),
         # 🚀 추가: 엑셀 원본 데이터를 다시 가져와서 상단 의뢰자 정보를 읽습니다.
         State("upload-excel-data", "contents")], 
        prevent_initial_call=True
    )
    def save_final_data_to_db(n_clicks, sample_data, facility_code, panel_code, excel_contents):
        if not n_clicks: return no_update
        if not sample_data or not facility_code or not panel_code or not excel_contents: 
            return dbc.Alert("⚠️ 필수 정보 누락 또는 파싱된 데이터가 없습니다.", color="warning")
        
        # 🚀 엑셀 헤더 유연성 엔진 (Fuzzy Match)
        def get_fuzzy_val(raw_dict, target_key):
            if target_key in raw_dict: return raw_dict[target_key]
            clean_target = str(target_key).lower().replace(" ", "").replace("\n", "")
            for k, v in raw_dict.items():
                if clean_target in str(k).lower().replace(" ", "").replace("\n", ""):
                    return v
            return None

        # =======================================================
        # 🚀 [추가] 의뢰자 정보 스마트 추출 로직
        # =======================================================
        client_facility, client_name, client_phone, client_email = "-", "-", "-", "-"
        try:
            import io
            import base64
            content_type, content_string = excel_contents.split(',')
            decoded = base64.b64decode(content_string)
            df_raw = pd.read_excel(io.BytesIO(decoded), header=None)
            
            for r in range(2, 12): 
                row_vals = df_raw.iloc[r].dropna().astype(str).str.strip().tolist()
                row_nospace = [x.replace(" ", "").lower() for x in row_vals]
                
                # 기관명 추출
                if "기관명" in row_nospace:
                    idx = row_nospace.index("기관명")
                    if idx + 1 < len(row_vals): client_facility = row_vals[idx + 1]
                    
                # 성명 & 연락처 추출
                if "실무자 성명" in row_nospace:
                    idx_name = row_nospace.index("실무자 성명")
                    if idx_name + 1 < len(row_vals): client_name = row_vals[idx_name + 1]
                    
                    if "연락처" in row_nospace:
                        idx_phone = row_nospace.index("연락처")
                        if idx_phone + 1 < len(row_vals): client_phone = row_vals[idx_phone + 1]
                        
                    # e-mail 추출 (성명 바로 다음 줄 스캔)
                    if r + 1 < len(df_raw):
                        next_row_vals = df_raw.iloc[r+1].dropna().astype(str).str.strip().tolist()
                        next_row_nospace = [x.replace(" ", "").lower() for x in next_row_vals]
                        
                        if "e-mail" in next_row_nospace or "email" in next_row_nospace:
                            idx_email = next_row_nospace.index("e-mail") if "e-mail" in next_row_nospace else next_row_nospace.index("email")
                            if idx_email + 1 < len(next_row_vals): client_email = next_row_vals[idx_email + 1]

            # 결측치 방어
            client_facility = client_facility if client_facility.lower() != 'nan' else "-"
            client_name = client_name if client_name.lower() != 'nan' else "-"
            client_phone = client_phone if client_phone.lower() != 'nan' else "-"
            client_email = client_email if client_email.lower() != 'nan' else "-"
        except Exception as e:
            print(f"⚠️ 의뢰자 정보 추출 실패: {e}") # 에러가 나더라도 샘플 저장은 되도록 pass 처리

        # =======================================================
        # DB 저장 파트
        # =======================================================
        db = SessionLocal()
        try:
            today_str = datetime.now().strftime("%y%m%d")
            fac_info = FACILITY_MAPPING.get(facility_code, {"facility": "Unknown", "team": "Unknown"})
            
            # 엑셀에서 뽑은 기관명이 있으면 우선 적용, 없으면 기본 FACILITY_MAPPING 적용
            final_facility = client_facility if client_facility != "-" else fac_info["facility"]
            
            total_orders_today = db.query(Order).filter(Order.order_id.like(f"%{today_str}%")).count()
            batch_seq = str(total_orders_today + 1).zfill(2) # "01", "02", "03"...

            new_order_id = f"GCX-{facility_code}-{today_str}-{batch_seq}"
            
            # 🚀 추출한 의뢰자 정보 모두 포함하여 Order 생성!
            new_order = Order(
                order_id=new_order_id, 
                facility=final_facility, 
                client_team=fac_info["team"],
                client_name=client_name,      # ✨ 새롭게 추출한 데이터
                client_email=client_email,    # ✨ 새롭게 추출한 데이터
                client_phone=client_phone,    # ✨ 새롭게 추출한 데이터
                reception_date=datetime.utcnow().date(), 
                sales_unit_price=0
            )
            db.add(new_order)
            db.flush()
            
            # 3. Sample 매핑 및 순차 번호 발급
            mapping_rule = get_full_mapping_for_panel(panel_code)
            success_count = 0 
            
            for raw_row in sample_data:
                base_data, extra_metadata = {}, {}
                for excel_col, map_info in mapping_rule.items():
                    val = get_fuzzy_val(raw_row, excel_col) 
                    clean_val = str(val).strip() if val is not None and str(val).strip() not in ["nan", "NaT", ""] else None
                    if map_info["is_extra"]: extra_metadata[map_info["db_col"]] = clean_val
                    else: base_data[map_info["db_col"]] = clean_val

                if not base_data.get("sample_name"): continue
                
                sample_seq = str(success_count + 1).zfill(3) 
                internal_sample_id = f"ACC-{today_str}-{batch_seq}-{sample_seq}"
                new_sample = Sample(
                    order_id=new_order.id, sample_id=internal_sample_id, target_panel=panel_code, current_status="접수 대기",
                    sample_name=base_data["sample_name"], cancer_type=base_data.get("cancer_type"), specimen=base_data.get("specimen"),
                    sample_group=base_data.get("sample_group"), pairing_info=base_data.get("pairing_info"), outside_id_1=base_data.get("outside_id_1"),
                    issue_comment=base_data.get("issue_comment"), panel_metadata=extra_metadata
                )
                db.add(new_sample)
                success_count += 1
                
            if success_count == 0:
                db.rollback()
                return dbc.Alert("🚨 엑셀에서 유효한 검체 정보(Patient ID)를 찾지 못했습니다. 매핑 양식을 확인해 주세요.", color="danger")

            db.commit() 
            return dbc.Alert(f"🎉 성공! 의뢰자[{client_name}]님의 샘플 총 {success_count}건 등록 완료. (칸반 보드를 확인하세요)", color="success")
            
        except Exception as e:
            db.rollback()
            print(traceback.format_exc())
            return dbc.Alert(f"🚨 DB 저장 오류: {e}", color="danger")
        finally: 
            db.close()

def create_registration_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_registration_layout)
    app = lims.get_app()
    register_registration_callbacks(app)
    return app