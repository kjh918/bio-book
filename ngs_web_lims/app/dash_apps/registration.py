import dash
from dash import html, dcc, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
from app.core.database import SessionLocal
from app.models.schema import NGSTracking
from app.dash_apps.shared_ui import create_navbar

# [이미지 기준 컬럼 순서] - 사용자가 입력할 수 있는 필드들
# 시스템 자동 생성 필드(Registration ID, Sample ID, SEQ ID 등)는 리스트에서 제외
INPUT_COLUMNS = [
    "GMC/GCX", "Order Facility", "Reception Date", "Order ID", "Order No", 
    "Sample Name", "Cancer Type", "Specimen", "추출 진행", "Sample Type", 
    "Analysis Type", "Depth/Output", "Conc.(ng/uL)", "Sample QC", "검사진행 여부", 
    "특이사항", "Outside ID 1", "Outside ID 2", "진행사항", "매출", "의뢰사", "의뢰인", 
    "sample QC report date", "seq QC report date", "Quotation ID", "단가", 
    "견적서 발행", "Dead Line", "standard report date 01", "standard report date 02", 
    "advanced report date 01", "advanced report date 02", "거래명세서 발행일", 
    "문서번호", "세금계산서 발행일", "매입", "단가(매입)", "품의서(지출) 작성일", 
    "품의 문서번호", "거래명세서/세금계산서 발행일", "지출결의 문서번호"
]

def create_registration_app(requests_pathname_prefix: str):
    app = dash.Dash(
        __name__,
        requests_pathname_prefix=requests_pathname_prefix,
        external_stylesheets=[dbc.themes.FLATLY]
    )

    app.layout = html.Div([
        create_navbar(),
        dbc.Container([
            html.Div([
                html.H3("📥 New NGS Sample Registration", className="fw-bold text-primary"),
                html.Hr(),
                html.P("이미지 순서와 동일한 엑셀 데이터를 복사(Ctrl+C)하여 첫 번째 셀에 붙여넣기(Ctrl+V) 하세요.", className="text-muted"),
            ], className="mb-4"),

            # 입력 테이블
            dash_table.DataTable(
                id='reg-table',
                columns=[{"name": i, "id": i, "editable": True} for i in INPUT_COLUMNS],
                data=[{c: "" for c in INPUT_COLUMNS} for _ in range(50)], # 넉넉히 50행
                editable=True,
                row_deletable=True,
                include_headers_on_copy_paste=True,
                style_table={'overflowX': 'auto', 'height': '600px', 'border': '1px solid #dee2e6'},
                style_cell={
                    'minWidth': '120px', 'width': '150px', 'maxWidth': '200px',
                    'textAlign': 'center', 'fontSize': '12px', 'padding': '5px'
                },
                style_header={
                    'backgroundColor': '#2C3E50', 'color': 'white', 'fontWeight': 'bold',
                    'border': '1px solid #34495E'
                },
                style_data={'backgroundColor': 'white', 'border': '1px solid #eee'}
            ),

            html.Div([
                dbc.Button("💾 접수 및 ID 자동 생성", id="btn-save", color="success", size="lg", className="px-5 shadow"),
                dcc.Loading(id="loading-save", children=[html.Div(id="save-status", className="mt-3")], type="circle")
            ], className="d-grid gap-2 d-md-flex justify-content-md-end mt-4 mb-5")
            
        ], fluid=True)
    ])

    @app.callback(
        Output("save-status", "children"),
        Input("btn-save", "n_clicks"),
        State("reg-table", "data"),
        prevent_initial_call=True
    )
    @app.callback(
        Output("save-status", "children"),
        Input("btn-save", "n_clicks"),
        State("reg-table", "data"),
        prevent_initial_call=True
    )
    def save_data(n_clicks, table_data):
        if not any(row.get("Sample Name") for row in table_data):
            return dbc.Alert("입력된 유효한 샘플 데이터가 없습니다.", color="warning")

        db = SessionLocal()
        try:
            today_prefix = datetime.now().strftime("%y%m%d") # 예: 260408
            
            # [핵심 추가] 오늘 생성된 가장 높은 번호 찾기
            # registration_id 가 'ACC-260408-XXX' 인 데이터 중 가장 큰 값 검색
            last_entry = db.query(NGSTracking).filter(
                NGSTracking.registration_id.like(f"ACC-{today_prefix}-%")
            ).order_by(NGSTracking.registration_id.desc()).first()
            
            # 마지막 번호 추출 (없으면 0부터 시작)
            if last_entry:
                last_num = int(last_entry.registration_id.split("-")[-1])
            else:
                last_num = 0

            saved_count = 0
            for i, row in enumerate(table_data):
                if not row.get("Sample Name"): continue

                # 기존 번호에 현재 순번(i+1)을 더함
                current_num = last_num + saved_count + 1
                reg_id = f"ACC-{today_prefix}-{current_num:03d}"
                seq_id = f"{reg_id}_S1" 
                
                # ... (나머지 ID 생성 및 저장 로직 동일)
                order_id = row.get("Order ID", "UNKNOWN")
                sample_name = row.get("Sample Name", "NONAME")
                sample_id = f"{order_id}_{sample_name}"

                full_json = {**row, "Registration ID": reg_id, "Sample ID": sample_id, "SEQ ID": seq_id}

                new_entry = NGSTracking(
                    registration_id=reg_id,
                    order_id=order_id,
                    sample_name=sample_name,
                    seq_id=seq_id,
                    excel_data=full_json
                )
                db.add(new_entry)
                saved_count += 1
            
            db.commit()
            return dbc.Alert(f"✅ 성공: {saved_count}건 등록 완료 (접수번호 시작: {last_num + 1})", color="success")
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"❌ 오류: {str(e)}", color="danger")
        finally:
            db.close()

    return app