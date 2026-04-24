from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
import datetime
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample
from app.pages.base import LimsDashApp

def create_data_registry_layout():
    return html.Div([
        html.H3("🗄️ Raw Data (FASTQ) 매핑 및 등록", className="fw-bold text-secondary mb-4"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("1. 시퀀싱 완료 검체 데이터 매핑", className="fw-bold mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.P("시퀀싱이 완료된 검체에 서버의 FASTQ 파일 경로를 매핑하여 분석 파이프라인으로 이관합니다.", className="text-muted mb-0")
                    ], width="auto"),
                    dbc.Col([
                        dbc.Button([DashIconify(icon="carbon:magic-wand", className="me-2"), "📂 서버 기본 경로 자동 매핑"], 
                                   id="btn-auto-map-fastq", color="info", className="fw-bold text-white me-2 shadow-sm"),
                        dbc.Button([DashIconify(icon="carbon:save", className="me-2"), "💾 데이터 등록 및 분석 이관"], 
                                   id="btn-save-registry", color="success", className="fw-bold shadow-sm")
                    ], width="auto", className="text-end")
                ], className="mb-3 d-flex justify-content-between align-items-center"),
                
                # 🚀 매핑용 Grid (경로 컬럼은 직접 텍스트 수정이 가능하도록 editable=True 설정)
                dag.AgGrid(
                    id="registry-ag-grid",
                    columnDefs=[
                        {"headerName": "선택", "field": "sample_id", "pinned": "left", "width": 80, "checkboxSelection": True, "headerCheckboxSelection": True},
                        {"headerName": "Order ID", "field": "order_id", "width": 140, "editable": False},
                        {"headerName": "패널", "field": "target_panel", "width": 100, "editable": False},
                        {"headerName": "상태", "field": "current_status", "width": 120, "editable": False},
                        
                        # ✏️ FASTQ 경로는 연구원이 엑셀처럼 직접 수정 가능!
                        {"headerName": "R1 FASTQ 경로", "field": "fastq_r1", "width": 300, "editable": True, 
                         "cellStyle": {"backgroundColor": "#f8f9fa", "border": "1px dashed #ccc"}},
                        {"headerName": "R2 FASTQ 경로", "field": "fastq_r2", "width": 300, "editable": True,
                         "cellStyle": {"backgroundColor": "#f8f9fa", "border": "1px dashed #ccc"}},
                    ],
                    rowData=[],
                    defaultColDef={"sortable": True, "filter": True, "resizable": True},
                    dashGridOptions={
                        "rowSelection": "multiple", 
                        "suppressRowClickSelection": True,
                        "stopEditingWhenCellsLoseFocus": True # 편집 후 클릭 밖으로 하면 자동 저장
                    },
                    style={"height": "450px", "width": "100%"},
                    className="ag-theme-alpine"
                ),
                
                html.Div(id="registry-save-msg", className="mt-3")
            ])
        ], className="border-0 shadow-sm rounded-4 mb-4")
        
    ], className="pb-5", style={"padding": "20px"})


def register_registry_callbacks(dash_app):
    
    # 1. 초기 데이터 로드 (시퀀싱 진행/완료 상태인 샘플만)
    @dash_app.callback(
        Output("registry-ag-grid", "rowData"),
        Input("registry-ag-grid", "id") # 더미 트리거 (페이지 로드 시)
    )
    def load_sequencing_samples(_):
        db = SessionLocal()
        try:
            samples = db.query(Sample).filter(Sample.current_status.in_(["시퀀싱 진행", "시퀀싱 완료"])).all()
            data = []
            for s in samples:
                meta = s.panel_metadata or {}
                data.append({
                    "sample_id": s.sample_id,
                    "order_id": s.order_id,
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    "fastq_r1": meta.get("fastq_r1", ""), # 이미 매핑된게 있으면 불러오기
                    "fastq_r2": meta.get("fastq_r2", "")
                })
            return data
        finally: db.close()

    # 2. 📂 자동 매핑 로직 (버튼 누르면 서버의 기본 룰셋에 따라 경로 자동 기입)
    @dash_app.callback(
        Output("registry-ag-grid", "rowData", allow_duplicate=True),
        Input("btn-auto-map-fastq", "n_clicks"),
        State("registry-ag-grid", "rowData"),
        prevent_initial_call=True
    )
    def auto_map_paths(n_clicks, row_data):
        if not n_clicks or not row_data: return no_update
        
        # 가상의 서버 기본 저장 경로 규칙 (예: /storage/data/raw_data/YYYYMM/...)
        current_yymm = datetime.datetime.now().strftime("%y%m")
        base_path = f"/storage/data/raw_data/{current_yymm}/"
        
        updated_data = []
        for row in row_data:
            sid = row["sample_id"]
            # 이미 값이 있으면 덮어쓰지 않고, 비어있을 때만 자동 채움
            if not row.get("fastq_r1"):
                row["fastq_r1"] = f"{base_path}{sid}_R1.fastq.gz"
            if not row.get("fastq_r2"):
                row["fastq_r2"] = f"{base_path}{sid}_R2.fastq.gz"
            updated_data.append(row)
            
        return updated_data

    # 3. 💾 매핑 결과 DB 저장 및 상태 이관
    @dash_app.callback(
        Output("registry-save-msg", "children"),
        Input("btn-save-registry", "n_clicks"),
        [State("registry-ag-grid", "selectedRows"),
         State("registry-ag-grid", "rowData")],
        prevent_initial_call=True
    )
    def save_data_registration(n_clicks, selected_rows, all_rows):
        if not n_clicks: return no_update
        if not selected_rows: 
            return dbc.Alert("⚠️ 이관할 검체를 체크박스로 선택해주세요.", color="warning")

        # 사용자가 수정한 표 전체 데이터(all_rows) 중, '체크된 항목'의 데이터만 추출
        selected_ids = [r["sample_id"] for r in selected_rows]
        target_data = [r for r in all_rows if r["sample_id"] in selected_ids]

        db = SessionLocal()
        try:
            success_cnt = 0
            for data in target_data:
                # 1. 경로가 비어있는지 확인
                r1, r2 = data.get("fastq_r1", "").strip(), data.get("fastq_r2", "").strip()
                if not r1 or not r2:
                    continue # 경로가 없으면 이관 스킵
                
                # 2. DB 업데이트
                sample = db.query(Sample).filter(Sample.sample_id == data["sample_id"]).first()
                if sample:
                    meta = sample.panel_metadata or {}
                    meta["fastq_r1"] = r1
                    meta["fastq_r2"] = r2
                    
                    # SQLAlchemy JSON 업데이트 감지 트리거
                    sample.panel_metadata = meta.copy() 
                    
                    # 🚀 핵심: 상태를 "분석 대기"로 변경!
                    sample.current_status = "분석 대기"
                    success_cnt += 1
                    
            if success_cnt == 0:
                return dbc.Alert("⚠️ 저장 실패: 선택한 검체들의 FASTQ 경로가 비어있습니다. 경로를 입력해주세요.", color="danger")

            db.commit()
            return dbc.Alert(f"🎉 매핑 완료! {success_cnt}건의 데이터가 등록되어 '분석 대기' 상태로 이관되었습니다.", color="success")
            
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"🚨 시스템 오류: {e}\n{traceback.format_exc()}", color="danger")
        finally: db.close()

def create_data_registry_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_data_registry_layout)
    app = lims.get_app() 
    register_registry_callbacks(app)
    return app