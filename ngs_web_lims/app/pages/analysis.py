from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
import subprocess # 🚀 로컬 스크립트 실행용
import datetime

from app.core.database import SessionLocal
from app.models._schema import Sample
from app.pages.base import LimsDashApp

def create_analysis_view_layout():
    return html.Div([
        html.H3("💻 생물정보학(BI) 분석 파이프라인", className="fw-bold text-secondary mb-4"),
        
        dbc.Row([
            # 🛠️ 1. 분석 설정 및 실행 패널 (좌측)
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("1. 파이프라인 설정", className="fw-bold mb-0")),
                    dbc.CardBody([
                        html.Label("파이프라인 종류", className="fw-bold text-primary small"),
                        dbc.Select(id="analysis-type-select", options=[
                            {"label": "DNA Somatic Variant Calling", "value": "dna_somatic"},
                            {"label": "RNA Expression & Fusion", "value": "rna_fusion"},
                            {"label": "Methylation Profiling", "value": "meth_profile"}
                        ], value="dna_somatic", className="mb-3"),
                        
                        html.Label("파이프라인 버전 (Version)", className="fw-bold text-primary small"),
                        dbc.Select(id="analysis-version-select", options=[
                            {"label": "v2.1.0 (최신/안정)", "value": "v2.1.0"},
                            {"label": "v2.0.5 (이전 안정화)", "value": "v2.0.5"},
                            {"label": "v3.0.0-beta (테스트용)", "value": "v3.0.0-beta"}
                        ], value="v2.1.0", className="mb-4"),
                        
                        html.Label("분석 결과 저장 기본 경로", className="fw-bold text-muted small"),
                        dbc.Input(id="analysis-outdir-input", value="/storage/data/analysis_results/", readonly=True, className="mb-4 bg-light"),
                        
                        html.Hr(),
                        
                        dbc.Button([DashIconify(icon="carbon:play-filled", className="me-2"), "🚀 선택 샘플 분석 스크립트 구동"], 
                                   id="btn-run-analysis", color="success", className="w-100 fw-bold py-2 shadow-sm")
                    ])
                ], className="border-0 shadow-sm rounded-4 h-100")
            ], xs=12, lg=3),
            
            # 📊 2. 대상 샘플 목록 Grid (우측)
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("2. 분석 대기 샘플 목록", className="fw-bold mb-0")),
                    dbc.CardBody([
                        dag.AgGrid(
                            id="analysis-ag-grid",
                            columnDefs=[
                                {"headerName": "선택", "field": "sample_id", "pinned": "left", "width": 120, "checkboxSelection": True, "headerCheckboxSelection": True},
                                {"headerName": "Order ID", "field": "order_id", "width": 140},
                                {"headerName": "패널", "field": "target_panel", "width": 100},
                                {"headerName": "현재 상태", "field": "current_status", "width": 120},
                                {"headerName": "FASTQ 경로 (예상)", "field": "fastq_path", "width": 250},
                            ],
                            rowData=[],
                            defaultColDef={"sortable": True, "filter": True, "resizable": True},
                            dashGridOptions={"rowSelection": "multiple", "suppressRowClickSelection": True},
                            style={"height": "350px", "width": "100%"},
                            className="ag-theme-alpine"
                        )
                    ], className="p-3")
                ], className="border-0 shadow-sm rounded-4 h-100")
            ], xs=12, lg=9)
        ], className="mb-4"),
        
        # 📝 3. 실행 로그 콘솔
        dbc.Card([
            dbc.CardHeader(html.H5("🖥️ 스크립트 실행 로그 (Console Output)", className="fw-bold mb-0")),
            dbc.CardBody([
                html.Pre(id="analysis-console-log", children="대기 중...\n", 
                         style={"backgroundColor": "#1e1e1e", "color": "#00ff00", "padding": "15px", "borderRadius": "8px", "minHeight": "200px", "overflowY": "auto", "fontFamily": "monospace"})
            ])
        ], className="border-0 shadow-sm rounded-4")
        
    ], className="pb-5", style={"padding": "20px"})


def register_analysis_callbacks(dash_app):
    
    # 1. '시퀀싱 진행' 또는 '분석 진행' 단계의 샘플만 불러오기
    @dash_app.callback(
        Output("analysis-ag-grid", "rowData"),
        Input("analysis-type-select", "value") # 탭 열리거나 타입 바뀔 때 갱신
    )
    def load_ready_samples(_):
        db = SessionLocal()
        try:
            # 실무에서는 시퀀싱이 끝난 샘플들만 가져옵니다.
            samples = db.query(Sample).filter(Sample.current_status.in_(["시퀀싱 진행", "분석 진행", "접수 완료"])).all()
            data = []
            for s in samples:
                data.append({
                    "sample_id": s.sample_id,
                    "order_id": s.order_id,
                    "target_panel": s.target_panel,
                    "current_status": s.current_status,
                    # 시퀀싱 장비에서 FASTQ가 떨어지는 기본 규칙 경로를 가상으로 표시
                    "fastq_path": f"/storage/data/raw_fastq/{s.sample_id}_R1.fastq.gz" 
                })
            return data
        finally: db.close()

    # 🚀 2. [핵심] 실제 로컬 분석 스크립트 실행 콜백
    @dash_app.callback(
        Output("analysis-console-log", "children"),
        Input("btn-run-analysis", "n_clicks"),
        [State("analysis-ag-grid", "selectedRows"),
         State("analysis-type-select", "value"),
         State("analysis-version-select", "value"),
         State("analysis-outdir-input", "value")],
        prevent_initial_call=True
    )
    def run_local_script(n_clicks, selected_rows, pipe_type, pipe_version, outdir):
        if not selected_rows:
            return "⚠️ 선택된 샘플이 없습니다. 표에서 분석할 샘플을 체크해주세요."
        
        log_output = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 파이프라인 구동 시작...\n"
        log_output += f" - 설정 파이프라인: {pipe_type} ({pipe_version})\n"
        log_output += f" - 타겟 샘플 수: {len(selected_rows)}건\n"
        log_output += "-" * 50 + "\n"

        db = SessionLocal()
        try:
            for row in selected_rows:
                sample_id = row['sample_id']
                fastq_r1 = row['fastq_path']
                fastq_r2 = fastq_r1.replace("_R1", "_R2") # 쌍으로 가정
                sample_outdir = f"{outdir}{sample_id}/"
                
                # ========================================================
                # 🚀 여기에 연구원님의 실제 BASH 스크립트 명령어를 구성하세요!
                # ========================================================
                # 예시 명령어: python run_pipeline.py -s ACC-240426-01-001 -v v2.1.0 -o /output/dir
                cmd_list = [
                    "echo", # ⚠️ 실제 사용 시 "echo"를 지우고 파이썬이나 bash 경로를 넣으세요! (예: "bash")
                    "/storage/scripts/run_ngs_pipeline.sh",
                    "--sample", sample_id,
                    "--type", pipe_type,
                    "--version", pipe_version,
                    "--r1", fastq_r1,
                    "--r2", fastq_r2,
                    "--outdir", sample_outdir
                ]
                
                # 명령어 조합된 텍스트
                cmd_str = " ".join(cmd_list)
                log_output += f"▶ [{sample_id}] 실행 명령어: {cmd_str}\n"

                try:
                    # 🚀 Python의 subprocess를 이용해 터미널 명령어 직접 실행!
                    # (실제 분석은 오래 걸리므로, 실무에서는 nohup이나 sbatch를 이용해 백그라운드로 던집니다)
                    result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        log_output += f"  [성공] Job 제출 완료.\n"
                        # DB의 상태를 '분석 진행'으로 업데이트 해줍니다.
                        target_sample = db.query(Sample).filter(Sample.sample_id == sample_id).first()
                        if target_sample:
                            target_sample.current_status = "분석 진행"
                    else:
                        log_output += f"  [실패] 에러 내용: {result.stderr}\n"

                except Exception as e:
                    log_output += f"  [시스템 오류] 스크립트 실행 실패: {e}\n"

            db.commit() # DB 상태 변경 확정
            log_output += "-" * 50 + "\n"
            log_output += f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모든 작업 큐 전송 완료. LIMS 상태가 '분석 진행'으로 변경되었습니다.\n"
            
            return log_output
            
        except Exception as e:
            db.rollback()
            return f"서버 내부 오류 발생: {e}"
        finally: db.close()

def create_analysis_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_analysis_view_layout)
    app = lims.get_app() 
    register_analysis_callbacks(app)
    return app