import os
import yaml
import subprocess
import datetime
from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample
from app.pages.base import LimsDashApp

def load_registry_config():
    config_path = os.path.join(os.getcwd(), "app", "config", "config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get("data_registry", {})
    except Exception as e:
        print(f"⚠️ Config 로드 실패 (기본값 사용): {e}")
        return {
            "default_base_path": "/storage/data/raw_data",
            "seq_providers": ["Macrogen", "Theragen", "Novogene"],
            "default_project": "Default_Project"
        }

def create_data_registry_layout():
    reg_config = load_registry_config()
    providers = reg_config.get("seq_providers", ["Unknown"])

    return html.Div([
        html.H3("🗄️ Raw Data 등록 및 다운로드 관리", className="fw-bold text-secondary mb-4"),
        
        # ---------------------------------------------------------
        # 1. 데이터 매핑 및 Grid 영역
        # ---------------------------------------------------------
        dbc.Card([
            dbc.CardHeader(
                dbc.Row([
                    dbc.Col(html.H5("1. 패널별 데이터 매핑 및 셋업", className="fw-bold mb-0 text-primary"), align="center"),
                    dbc.Col([
                        # 🚀 다운로드 실행 버튼 추가!
                        dbc.Button([DashIconify(icon="carbon:cloud-download", className="me-2"), "⬇️ 선택 샘플 데이터 다운로드"], 
                                   id="btn-run-download", color="warning", className="fw-bold me-2 shadow-sm"),
                        dbc.Button([DashIconify(icon="carbon:folder-details", className="me-2"), "📂 기본 경로 자동 생성"], 
                                   id="btn-auto-map-fastq", color="info", className="fw-bold text-white me-2 shadow-sm"),
                        dbc.Button([DashIconify(icon="carbon:save", className="me-2"), "💾 분석 이관 저장"], 
                                   id="btn-save-registry", color="success", className="fw-bold shadow-sm")
                    ], width="auto", className="text-end")
                ], className="d-flex justify-content-between align-items-center")
            ),
            dbc.CardBody([
                html.P("URL 링크가 입력된 샘플을 선택하고 '데이터 다운로드'를 누르면 백그라운드에서 Wget 스크립트가 실행됩니다.", className="text-muted mb-3"),
                
                dbc.Tabs(
                    id="panel-tabs",
                    active_tab="ALL",
                    children=[
                        dbc.Tab(label="🧬 전체보기", tab_id="ALL", labelClassName="fw-bold"),
                        dbc.Tab(label="WES", tab_id="WES", labelClassName="fw-bold text-primary"),
                        dbc.Tab(label="WGS", tab_id="WGS", labelClassName="fw-bold text-success"),
                        dbc.Tab(label="WTS", tab_id="WTS", labelClassName="fw-bold text-warning"),
                        dbc.Tab(label="기타(TSO/dPCR)", tab_id="ETC", labelClassName="fw-bold text-secondary"),
                    ],
                    className="mb-3"
                ),
                
                dag.AgGrid(
                    id="registry-ag-grid",
                    columnDefs= LimsDashApp.get_base_grid_columns(include_project=True) + [
                        {"headerName": "상태", "field": "current_status", "width": 110, "editable": False},
                        
                        {"headerName": "해독 업체", "field": "seq_provider", "width": 150, "editable": True, 
                         "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": providers},
                         "cellStyle": {"backgroundColor": "#fff3cd"}},
                        # 🚀 핵심 URL 입력란
                        {"headerName": "다운로드 링크 (URL)", "field": "download_link", "width": 250, "editable": True, "cellStyle": {"backgroundColor": "#fff3cd"}},
                        
                        {"headerName": "R1 로컬 경로", "field": "fastq_r1", "width": 250, "editable": True, "cellStyle": {"backgroundColor": "#f8f9fa", "border": "1px dashed #ccc"}},
                        {"headerName": "R1 MD5", "field": "md5_r1", "width": 120, "editable": True, "cellStyle": {"backgroundColor": "#f8f9fa"}},
                        {"headerName": "R2 로컬 경로", "field": "fastq_r2", "width": 250, "editable": True, "cellStyle": {"backgroundColor": "#f8f9fa", "border": "1px dashed #ccc"}},
                        {"headerName": "R2 MD5", "field": "md5_r2", "width": 120, "editable": True, "cellStyle": {"backgroundColor": "#f8f9fa"}},
                    ],
                    rowData=[],
                    defaultColDef={"sortable": True, "filter": True, "resizable": True},
                    dashGridOptions={
                        "rowSelection": "multiple", 
                        "suppressRowClickSelection": True,
                        "stopEditingWhenCellsLoseFocus": True,
                        "animateRows": True,
                        "groupDefaultExpanded": 1, 
                        "autoGroupColumnDef": {
                            "headerName": "프로젝트 / 접수 폴더",
                            "minWidth": 250,
                            "cellRendererParams": {"checkbox": True}
                        }
                    },
                    style={"height": "400px", "width": "100%"},
                    className="ag-theme-alpine"
                ),
                
                html.Div(id="registry-save-msg", className="mt-3")
            ])
        ], className="border-0 shadow-sm rounded-4 mb-4"),

        # ---------------------------------------------------------
        # 2. 다운로드 진행 상태 콘솔 모니터 (신규 추가!)
        # ---------------------------------------------------------
        dbc.Card([
            dbc.CardHeader(html.H5("🖥️ Wget 다운로드 실시간 로그 (Console Output)", className="fw-bold mb-0 text-white"), className="bg-dark"),
            dbc.CardBody([
                html.Pre(id="download-console-log", children="대기 중...\n[선택 샘플 다운로드 실행]을 클릭하면 로그 스트리밍이 시작됩니다.", 
                         style={"backgroundColor": "#1e1e1e", "color": "#00ff00", "padding": "15px", "borderRadius": "8px", "minHeight": "250px", "maxHeight": "350px", "overflowY": "auto", "fontFamily": "monospace"}),
                # 🚀 핵심: 2초마다 로그 파일을 읽어오는 백그라운드 타이머
                dcc.Interval(id="download-log-interval", interval=2000, n_intervals=0, disabled=True) 
            ], className="bg-dark")
        ], className="border-0 shadow-sm rounded-4")
        
    ], className="pb-5", style={"padding": "20px"})


def register_registry_callbacks(dash_app):
    
    # 1. 초기 데이터 로드 & 탭 필터링 
    @dash_app.callback(
        Output("registry-ag-grid", "rowData"),
        [Input("registry-ag-grid", "id"), Input("panel-tabs", "active_tab")] 
    )
    def load_sequencing_samples(_, active_tab):
        db = SessionLocal()
        reg_config = load_registry_config()
        default_proj = reg_config.get("default_project", "Default_Project")
        try:
            target_statuses = ["시퀀싱 완료", "해독 완료", "분석 대기", "분석 진행"]
            all_samples = db.query(Sample).filter(Sample.current_status.in_(target_statuses)).all()
            
            if active_tab == "ETC": filtered_samples = [s for s in all_samples if s.target_panel not in ["WES", "WGS", "WTS"]]
            elif active_tab != "ALL": filtered_samples = [s for s in all_samples if s.target_panel == active_tab]
            else: filtered_samples = all_samples
            
            data = []
            for s in filtered_samples:
                meta = s.panel_metadata or {}
                data.append({
                    "sample_id": s.sample_id,
                    "sample_name": s.sample_name, 
                    "order_id": s.order_id,
                    "project_name": s.project_name if s.project_name else default_proj, 
                    "current_status": s.current_status,
                    "target_panel": s.target_panel if s.target_panel else "WES", 
                    "seq_provider": meta.get("seq_provider", ""),
                    "download_link": meta.get("download_link", ""),
                    "fastq_r1": meta.get("fastq_r1", ""),
                    "md5_r1": meta.get("md5_r1", ""),
                    "fastq_r2": meta.get("fastq_r2", ""),
                    "md5_r2": meta.get("md5_r2", "")
                })
            return data
        finally: db.close()

    # 2. 경로 자동 생성
    @dash_app.callback(
        Output("registry-ag-grid", "rowData", allow_duplicate=True),
        Input("btn-auto-map-fastq", "n_clicks"), State("registry-ag-grid", "rowData"), prevent_initial_call=True
    )
    def auto_map_paths(n_clicks, row_data):
        if not n_clicks or not row_data: return no_update
        reg_config = load_registry_config()
        base_path = reg_config.get("default_base_path", "/storage/data/raw_data")
        updated_data = []
        for row in row_data:
            if not row.get("sample_id"): updated_data.append(row); continue
            sid = row["sample_id"]
            proj = row.get("project_name", "Default")
            panel = row.get("target_panel", "WES")
            target_dir = f"{base_path}/{proj}/{panel}/"
            if not row.get("fastq_r1"): row["fastq_r1"] = f"{target_dir}{sid}_R1.fastq.gz"
            if not row.get("fastq_r2"): row["fastq_r2"] = f"{target_dir}{sid}_R2.fastq.gz"
            updated_data.append(row)
        return updated_data

    # 🚀 3. 데이터 다운로드 Bash 스크립트 생성 및 백그라운드 실행
    @dash_app.callback(
        [Output("registry-save-msg", "children", allow_duplicate=True),
         Output("download-log-interval", "disabled")], # 스크립트 시작 시 타이머 활성화
        Input("btn-run-download", "n_clicks"),
        State("registry-ag-grid", "selectedRows"),
        prevent_initial_call=True
    )
    def start_wget_downloads(n_clicks, selected_rows):
        if not selected_rows: 
            return dbc.Alert("⚠️ 다운로드할 검체를 체크박스로 선택해주세요.", color="warning"), True
        
        valid_rows = [r for r in selected_rows if r.get("sample_id") and r.get("download_link")]
        if not valid_rows:
            return dbc.Alert("⚠️ 선택된 샘플 중 '다운로드 링크(URL)'가 입력된 데이터가 없습니다.", color="danger"), True

        # 스크립트 및 로그 파일 경로 정의
        script_path = os.path.join(os.getcwd(), "run_wget_download.sh")
        log_path = os.path.join(os.getcwd(), "download_log.txt")

        try:
            # 1️⃣ Bash 스크립트(.sh) 파일 작성
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n\n")
                f.write(f"echo '=================================================='\n")
                f.write(f"echo '🚀 LIMS Wget Download Job Started: $(date)'\n")
                f.write(f"echo '=================================================='\n\n")
                
                for row in valid_rows:
                    sid = row["sample_id"]
                    link = row["download_link"].strip()
                    r1_path = row.get("fastq_r1", f"./{sid}_R1.fastq.gz")
                    
                    target_dir = os.path.dirname(r1_path)
                    f.write(f"echo '[{sid}] 경로 준비: {target_dir}'\n")
                    f.write(f"mkdir -p '{target_dir}'\n")
                    
                    # wget 명령어 (이어받기 -c, 진행상황 로그 덤프)
                    f.write(f"echo '▶ Downloading {sid} data...'\n")
                    f.write(f"wget -c '{link}' -O '{r1_path}' 2>&1 | stdbuf -o0 awk '/[.] +[0-9]+%/ {{print $0}} ORS=\"\"' | awk '{{print $0; fflush();}}'\n")
                    f.write(f"echo '✅ [{sid}] Download Completed.'\n\n")
                
                f.write(f"echo '=================================================='\n")
                f.write(f"echo '🎉 All Download Jobs Finished: $(date)'\n")
                f.write(f"echo '=================================================='\n")

            os.chmod(script_path, 0o755)

            # 2️⃣ 백그라운드로 서브프로세스 실행 (UI 멈춤 방지!)
            with open(log_path, "w") as log_f:
                subprocess.Popen(["bash", script_path], stdout=log_f, stderr=subprocess.STDOUT)

            return dbc.Alert("🚀 백그라운드 다운로드 스크립트가 성공적으로 시작되었습니다. 하단 콘솔에서 진행 상황을 확인하세요.", color="info"), False # False = interval 타이머 켜기

        except Exception as e:
            return dbc.Alert(f"🚨 스크립트 실행 오류: {e}", color="danger"), True


    # 🚀 4. 실시간 로그 읽기 (Interval Polling)
    @dash_app.callback(
        Output("download-console-log", "children"),
        Input("download-log-interval", "n_intervals"),
        prevent_initial_call=True
    )
    def update_console_log(n):
        log_path = os.path.join(os.getcwd(), "download_log.txt")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    # 브라우저 과부하를 막기 위해 마지막 50줄만 가져와서 출력
                    lines = f.readlines()
                    if not lines: return "로그를 기다리는 중..."
                    return "".join(lines[-50:])
            except Exception:
                return "로그 파일을 읽는 중 일시적인 오류..."
        return "진행 중인 작업 또는 로그 파일이 없습니다."


    # 5. DB 저장 및 이관
    @dash_app.callback(
        Output("registry-save-msg", "children"),
        Input("btn-save-registry", "n_clicks"),
        [State("registry-ag-grid", "selectedRows"), State("registry-ag-grid", "rowData")],
        prevent_initial_call=True
    )
    def save_data_registration(n_clicks, selected_rows, all_rows):
        if not n_clicks: return no_update
        if not selected_rows: 
            return dbc.Alert("⚠️ 저장/이관할 검체를 체크박스로 선택해주세요.", color="warning")

        valid_selected_rows = [r for r in selected_rows if r.get("sample_id")]
        if not valid_selected_rows: return dbc.Alert("⚠️ 유효한 데이터가 없습니다.", color="warning")

        selected_ids = [r["sample_id"] for r in valid_selected_rows]
        target_data = [r for r in all_rows if r.get("sample_id") in selected_ids]

        db = SessionLocal()
        try:
            success_cnt = 0
            for data in target_data:
                sample = db.query(Sample).filter(Sample.sample_id == data["sample_id"]).first()
                if sample:
                    meta = sample.panel_metadata or {}
                    for k in ["seq_provider", "download_link", "fastq_r1", "md5_r1", "fastq_r2", "md5_r2"]:
                        meta[k] = data.get(k, "")
                    sample.panel_metadata = meta.copy() 
                    
                    if sample.current_status in ["시퀀싱 완료", "해독 완료"]: sample.current_status = "분석 대기"
                    success_cnt += 1

            db.commit()
            return dbc.Alert(f"🎉 성공! {success_cnt}건의 데이터 검증 내역 저장 및 분석 단계 이관이 완료되었습니다.", color="success")
            
        except Exception as e:
            db.rollback()
            return dbc.Alert(f"🚨 DB 저장 오류: {e}\n{traceback.format_exc()}", color="danger")
        finally: db.close()

def create_data_registry_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_data_registry_layout)
    app = lims.get_app() 
    register_registry_callbacks(app)
    return app