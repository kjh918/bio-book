from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from datetime import datetime
import pandas as pd
import io
import os
import base64
import traceback
import json

# 🚀 [MODIFIED] SSH 원격 접속을 위한 라이브러리 추가
import paramiko 

from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR
from app.pages.analysis.base import create_shared_analysis_layout

# ==========================================
# ⚙️ [MODIFIED] 원격 서버 설정 (환경변수 또는 Config 처리 권장)
# ==========================================
REMOTE_HOST = "192.168.0.39"
REMOTE_USER = "gmctso" # 실제 접속 계정으로 변경 필요
REMOTE_PW = "tso@gmc!!" # 실제 비밀번호 또는 Key 파일 경로로 변경 필요
REMOTE_BASE_DIR = "/data/ngs/nextseq550dx_output" # 39번 서버의 분석 결과 최상위 경로
REMOTE_SAVED_RESOURCES_DIR = "/data/tso/test/metadata"


from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from datetime import datetime
import pandas as pd
import io
import os
import base64
import traceback
import json

# 🚀 [MODIFIED] SSH 원격 접속 및 제어를 위한 라이브러리 추가
import paramiko 

from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR
from app.pages.analysis.base import create_shared_analysis_layout


def get_tso_setup_layout():
    # 기본 분석 셋업 레이아웃
    base_layout = create_shared_analysis_layout(
        prefix="tso-setup",
        title="TSO500 Analysis Run Setup",
        description="Illumina TSO500 패널의 DNA/RNA 통합 분석 셋업 및 SampleSheet 발행 화면입니다.",
        panel_options=[{"label": "🧬 TSO500", "value": "TSO500"}],
        pipeline_options=[{"label": "DNA/RNA Integrated", "value": "DNA/RNA 통합"}]
    )
    
    # 🚀 [MODIFIED] 분석 서버 원격 모니터링 카드 추가 (검색 후 선택 방식으로 변경)
    remote_sync_card = dbc.Card([
        dbc.CardHeader([
            html.H5("🌐 분석 서버(192.168.0.39) 데이터 동기화", className="mb-0 fw-bold text-info")
        ]),
        dbc.CardBody([
            html.P("39번 분석 서버를 검색하여 분석이 완료된(Results.json 생성됨) 폴더 목록을 불러오고, LIMS로 메타데이터를 수집합니다.", className="text-muted small"),
            dbc.Row([
                dbc.Col([
                    dbc.Button("🔍 1. 원격 서버 결과 폴더 검색", id="tso-setup-btn-remote-search", color="secondary", className="fw-bold shadow-sm w-100")
                ], width=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dcc.Dropdown(id="tso-setup-remote-dir-dropdown", multi=True, placeholder="검색 버튼을 눌러 분석 완료 폴더를 선택하세요...")
                ], width=8),
                dbc.Col([
                    dbc.Button("⬇️ 2. 선택 데이터 LIMS 수집", id="tso-setup-btn-remote-sync", color="info", className="fw-bold text-white shadow-sm w-100")
                ], width=4)
            ]),
            html.Div(id="tso-setup-remote-status-msg", className="mt-3")
        ])
    ], className="mt-4 shadow-sm border-0")

    return html.Div([remote_sync_card, base_layout])

# 🚀 2. TSO500 전용 콜백 등록 (Prefix: tso-setup)
def register_tso_setup_callbacks(dash_app):

    # [콜백 1] 템플릿 로드 + 대기 샘플 자동 Pre-fill
    @dash_app.callback(
        Output("tso-setup-download-template", "data"),
        Input("tso-setup-btn-download", "n_clicks"),
        State("tso-setup-panel-select", "value"),
        prevent_initial_call=True
    )
    def download_template(n_clicks, panel):
        if not n_clicks or not panel: return no_update
        
        headers = [
            "Sample_ID", "Case_ID", "Sex", "Tumor_Type", "Patient_Name", "Patient_ID", "Customer_name", 
            "Date_of_birth", "Diagnosis", "Medical_facility", "Medical_facility_ID", "Physician", "Pathologist", 
            "Date_of_order", "Specimen_name", "Specimen_type", "Specimen_state", "Specimen_Site", "Tumor_purity", 
            "Date_of_collection", "Extraction_type", "Panel_information", "Date_of_receipt", "Concentration", 
            "Sample_purity", "Library_size", "Sample_Plate", "Sample_Well", "Index_ID", "index", "index2", 
            "Sample_Type", "Pair_ID", "Tumor_Type", "Sex", "Sample_Project"
        ]
        
        try:
            df_export = pd.DataFrame(columns=headers)
            db = SessionLocal()
            samples = db.query(Sample).filter(Sample.target_panel == panel, Sample.current_status == "분석 진행").all()
            
            panel_full_name = "TruSight Oncology 500" if panel == "TSO500" else panel
            
            row_idx = 0
            for s in samples:
                a_status = s.analysis.analysis_status if s.analysis else "대기중"
                if a_status != "대기중": continue
                
                clean_case = s.sample_id.upper().replace("-DNA", "").replace("_DNA", "").replace("-RNA", "").replace("_RNA", "")
                is_rna = "-RNA" in s.sample_id.upper()
                n_type = "RNA" if is_rna else ("DNA" if "-DNA" in s.sample_id.upper() else getattr(s, 'nucleic_acid_type', 'DNA'))
                
                df_export.loc[row_idx, "Sample_ID"] = s.sample_id
                df_export.loc[row_idx, "Case_ID"] = clean_case
                df_export.loc[row_idx, "Patient_Name"] = s.sample_name
                df_export.loc[row_idx, "Patient_ID"] = s.sample_name
                df_export.loc[row_idx, "Specimen_type"] = s.specimen or ""
                df_export.loc[row_idx, "Extraction_type"] = n_type
                df_export.loc[row_idx, "Panel_information"] = panel_full_name
                
                df_export.loc[row_idx, "Sample_Type"] = n_type
                df_export.loc[row_idx, "Pair_ID"] = clean_case
                df_export.loc[row_idx, "Sample_Project"] = s.sample_id
                
                df_export.loc[row_idx, "Index_ID"] = "UP02" if is_rna else "UP01"
                df_export.loc[row_idx, "index"] = "AGGATAGG" if is_rna else "TCCGGAGA"
                df_export.loc[row_idx, "index2"] = "TCCGGAGA" if is_rna else "AGGATAGG"
                
                row_idx += 1
                
            if row_idx == 0:
                df_export.loc[0, "Sample_ID"] = f"대기중인_{panel}_샘플이_없습니다"
                
            filename = f"Template_Integrated_{panel}_{datetime.now().strftime('%y%m%d')}.csv"
            bom_csv_string = "\ufeff" + df_export.to_csv(index=False)
            return dcc.send_string(bom_csv_string, filename)
            
        except Exception as e:
            traceback.print_exc()
            return no_update
        finally:
            if 'db' in locals(): db.close()

    # [콜백 2] 업로드 파일 파싱 
    @dash_app.callback(
        [Output("tso-setup-uploaded-store", "data"),
         Output("tso-setup-upload-status", "children")],
        Input("tso-setup-upload-file", "contents"),
        State("tso-setup-upload-file", "filename"),
        prevent_initial_call=True
    )
    def handle_upload(contents, filename):
        if contents is None: return no_update, no_update
        
        try:
            _, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            if filename.endswith('.csv'): 
                try:
                    df = pd.read_csv(io.BytesIO(decoded), encoding='utf-8-sig')
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(decoded), encoding='cp949')
            else: 
                df = pd.read_excel(io.BytesIO(decoded))
            
            if 'Sample_ID' not in df.columns:
                return None, html.Span("❌ 파싱 실패: 'Sample_ID' 컬럼이 보이지 않습니다.", className="text-danger fw-bold")
            
            df = df.dropna(subset=['Sample_ID'])
            return df.to_dict("records"), html.Span(f"✅ '{filename}' 통합 파싱 성공 ({len(df)}개 샘플 로드됨)", className="text-success fw-bold")
        except Exception as e:
            traceback.print_exc()
            return None, html.Span(f"❌ 파일 해석 오류: {str(e)}", className="text-danger fw-bold")

    # [콜백 3] Grid 로드
    @dash_app.callback(
        Output("tso-setup-grid-container", "children"),
        [Input("tso-setup-panel-select", "value"),
         Input("tso-setup-execute-status", "children"),
         Input("tso-setup-remote-status-msg", "children")] # 🚀 [MODIFIED] 리모트 체크 완료 후 그리드 리프레시 트리거 추가
    )
    def load_pending_grid(panel, _, __):
        if not panel: return no_update
        
        base_cols = LimsDashApp.get_base_grid_columns(include_project=True)
        if base_cols:
            base_cols[0]["checkboxSelection"] = True
            base_cols[0]["headerCheckboxSelection"] = True
            base_cols[0]["width"] = 150
        
        columnDefs = base_cols + [
            {"headerName": "암종(Cancer)", "field": "cancer_type", "width": 130},
            {"headerName": "검체(Specimen)", "field": "specimen", "width": 130},
            {"headerName": "분석 상태", "field": "analysis_status", "width": 120, "cellStyle": {"fontWeight": "bold", "color": "#0d6efd"}}
        ]
        
        db = SessionLocal()
        try:
            # 분석 상태와 상관없이 분석 진행 스테이지에 있는 것들을 보여주거나 필요 시 조율 가능
            samples = db.query(Sample).filter(Sample.target_panel == panel, Sample.current_status == "분석 진행").all()
            data = []
            for s in samples:
                a_status = s.analysis.analysis_status if s.analysis else "대기중"
                data.append({
                    "id": s.id, "project_name": s.project_name, "order_id": s.order_id,
                    "sample_id": s.sample_id, "sample_name": s.sample_name, "target_panel": s.target_panel,
                    "cancer_type": s.cancer_type, "specimen": s.specimen, "analysis_status": a_status
                })
                
            grid = LimsDashApp.create_standard_aggrid(id="tso-setup-aggrid", columnDefs=columnDefs, height="35vh")
            grid.dashGridOptions["rowSelection"] = "multiple"
            grid.dashGridOptions["suppressRowClickSelection"] = True
            grid.rowData = data
            return grid
        finally: db.close()

    # [콜백 4] 매칭 실행 + SampleSheet & Metadata 동시 발행
    @dash_app.callback(
        [Output("tso-setup-execute-status", "children"),
         Output("tso-setup-download-samplesheet", "data"),
         Output("tso-setup-download-template", "data", allow_duplicate=True)], 
        Input("tso-setup-btn-execute", "n_clicks"),
        [State("tso-setup-aggrid", "selectedRows"),
         State("tso-setup-uploaded-store", "data"),
         State("tso-setup-panel-select", "value"),
         State("tso-setup-pipeline-select", "value"),
         State("tso-setup-remote-dir-dropdown", "value")],
        prevent_initial_call=True
    )
    def execute_analysis_setup(n_clicks, selected_rows, metadata_list, panel, pipeline, remote_selection):
        if not selected_rows: return dbc.Alert("⚠️ Grid에서 분석할 샘플을 먼저 선택해주세요.", color="warning"), no_update, no_update
        if not metadata_list: return dbc.Alert("⚠️ Step 2에서 메타데이터 파일을 먼저 업로드해주세요.", color="warning"), no_update, no_update
            
        def safe_get(meta, key, default):
            val = meta.get(key, default)
            if pd.isna(val) or str(val).strip().lower() == "nan": return default
            return val
        
        dir_name = remote_selection[0] if isinstance(remote_selection, list) else remote_selection
        
        db = SessionLocal()
        success_count = 0
        fail_msgs = []
        samplesheet_rows = []
        metadata_rows = [] 
        
        meta_headers = [
            "Sample_ID", "Case_ID", "Sex", "Tumor_Type", "Patient_Name", "Patient_ID", "Customer_name", 
            "Date_of_birth", "Diagnosis", "Medical_facility", "Medical_facility_ID", "Physician", "Pathologist", 
            "Date_of_order", "Specimen_name", "Specimen_type", "Specimen_state", "Specimen_Site", "Tumor_purity", 
            "Date_of_collection", "Extraction_type", "Panel_information", "Date_of_receipt", "Concentration", 
            "Sample_purity", "Library_size"
        ]

        try:
            for row in selected_rows:
                s_id = row["sample_id"]
                matching_meta = next((item for item in metadata_list if str(item.get("Sample_ID", "")).strip() == s_id), None)
                
                if not matching_meta:
                    fail_msgs.append(f"• [{s_id}] 업로드 파일에 데이터가 없습니다.")
                    continue
                    
                sample = db.query(Sample).filter(Sample.id == row["id"]).first()
                if not sample: continue
                
                if not sample.analysis:
                    sample.analysis = Analysis(sample_id=sample.id)
                    db.add(sample.analysis)
                
                sample.analysis.analysis_status = "분석 준비"
                sample.analysis.pipeline = pipeline
                
                results_json = sample.analysis.analysis_results or {}
                if isinstance(results_json, str): results_json = {}
                for excel_header, excel_val in matching_meta.items():
                    if excel_header == "Sample_ID" or pd.isna(excel_val): continue
                    results_json[excel_header.strip()] = str(excel_val) if not isinstance(excel_val, (int, float)) else excel_val
                sample.analysis.analysis_results = results_json
            
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(sample.analysis, "analysis_results")
                
                clean_case_id = s_id.upper().replace("-DNA", "").replace("_DNA", "").replace("-RNA", "").replace("_RNA", "")
                fallback_sample_type = "RNA" if "-RNA" in s_id.upper() else "DNA"
                
                tumor_type_raw = str(safe_get(matching_meta, 'Tumor_Type.1', safe_get(matching_meta, 'Tumor_Type', '81920005')))
                if tumor_type_raw.endswith('.0'): tumor_type_raw = tumor_type_raw[:-2]
                sex_raw = str(safe_get(matching_meta, 'Sex.1', safe_get(matching_meta, 'Sex', ''))).strip().upper()

                samplesheet_rows.append({
                    "Sample_ID": s_id,
                    "Sample_Name": str(safe_get(matching_meta, 'Patient_ID', s_id)),
                    "Sample_Plate": str(safe_get(matching_meta, 'Sample_Plate', '')),
                    "Sample_Well": str(safe_get(matching_meta, 'Sample_Well', '')),
                    "Index_ID": str(safe_get(matching_meta, 'Index_ID', "UP01" if fallback_sample_type=="DNA" else "UP02")),
                    "index": str(safe_get(matching_meta, 'index', "TCCGGAGA" if fallback_sample_type=="DNA" else "AGGATAGG")),
                    "index2": str(safe_get(matching_meta, 'index2', "AGGATAGG" if fallback_sample_type=="DNA" else "TCCGGAGA")),
                    "Sample_Type": str(safe_get(matching_meta, 'Sample_Type', fallback_sample_type)),
                    "Pair_ID": str(safe_get(matching_meta, 'Case_ID', clean_case_id)),
                    "Tumor_Type": tumor_type_raw,
                    "Sex": sex_raw,
                    "Sample_Project": str(safe_get(matching_meta, 'Sample_Project', s_id))
                })
                
                meta_row = {}
                for h in meta_headers:
                    meta_row[h] = safe_get(matching_meta, h, "")
                
                meta_row["Sample_ID"] = s_id
                meta_row["Case_ID"] = str(safe_get(matching_meta, 'Case_ID', clean_case_id))
                meta_row["Patient_Name"] = str(safe_get(matching_meta, 'Patient_ID', s_id))
                meta_row["Patient_ID"] = str(safe_get(matching_meta, 'Patient_ID', s_id))
                meta_row["Extraction_type"] = fallback_sample_type
                meta_row["Sex"] = sex_raw
                meta_row["Tumor_Type"] = tumor_type_raw
                
                metadata_rows.append(meta_row)
                success_count += 1
                
            db.commit()
            
            # 최종 파일 2개 발행 로직
            if success_count > 0 and samplesheet_rows:
                
                ss_template_path = os.path.join(BASE_DIR, "app", "templates", "analysis", panel, "template_SampleSheet.csv")
                ss_header_lines = []
                dynamic_experiment_name = f"{datetime.now().strftime('%y%m%d')}_{panel}"
                
                if os.path.exists(ss_template_path):
                    with open(ss_template_path, 'r', encoding='utf-8-sig') as f:
                        for line in f:
                            clean_line = line.strip('\n').strip('\r')
                            if clean_line.startswith("Experiment Name"):
                                clean_line = f"Experiment Name,{dynamic_experiment_name},,,,,,,,,,"
                            ss_header_lines.append(clean_line)
                            if clean_line.startswith('[Data]'): break
                else:
                    ss_header_lines = [
                        "[Header],,,,,,,,,,,", "IEMFileVersion,4,,,,,,,,,,", "Investigator Name,User Name,,,,,,,,,,",
                        f"Experiment Name,{dynamic_experiment_name},,,,,,,,,,", f"Date,{datetime.now().strftime('%m/%d/%Y')},,,,,,,,,,",
                        "Workflow,GenerateFASTQ,,,,,,,,,,", "Application,NextSeq FASTQ Only,,,,,,,,,,",
                        "Assay,,,,,,,,,,,", "Description,,,,,,,,,,,", "Chemistry,Default,,,,,,,,,,",
                        ",,,,,,,,,,,", "[Reads],,,,,,,,,,,", "101,,,,,,,,,,,", "101,,,,,,,,,,,",
                        ",,,,,,,,,,,", "[Settings],,,,,,,,,,,", "AdapterRead1,AGATCGGAAGAGCACACGTCTGAACTCCAGTCA,,,,,,,,,,",
                        "AdapterRead2,AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT,,,,,,,,,,", "AdapterBehavior,trim,,,,,,,,,,",
                        "MinimumTrimmedReadLength,35,,,,,,,,,,", "MaskShortReads,35,,,,,,,,,,", "OverrideCycles,U7N1Y93;I8;I8;U7N1Y93,,,,,,,,,,",
                        ",,,,,,,,,,,", "[Data],,,,,,,,,,,"
                    ]
                
                # 1. 파일 이름 정의
                time_stamp = datetime.now().strftime('%y%m%d_%H%M%S')
                ss_filename = f"SampleSheet_TSO500_{time_stamp}.csv"
                meta_filename = f"template_Metadata_TSO500_{time_stamp}.csv"

                # 2. 데이터 문자열 조합
                df_ss = pd.DataFrame(samplesheet_rows)
                raw_ss_str = "\n".join(ss_header_lines) + "\n" + df_ss.to_csv(index=False)
                
                df_meta = pd.DataFrame(metadata_rows)
                raw_meta_str = df_meta.to_csv(index=False)
                
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PW)
                sftp = ssh.open_sftp()
                
                try:
                    # dir_name 설정 (현재 실험 이름과 동일하게)
                    remote_dir = f"{REMOTE_SAVED_RESOURCES_DIR}/{dir_name}"
                    
                    # 1) 원격 디렉토리 생성 (없으면 생성)
                    try:
                        sftp.stat(remote_dir)
                    except IOError:
                        sftp.mkdir(remote_dir)
                    
                    # 2) 파일 전송 (write)
                    with sftp.open(f"{remote_dir}/{ss_filename}", "w") as f:
                        f.write(raw_ss_str)
                    with sftp.open(f"{remote_dir}/{meta_filename}", "w") as f:
                        f.write(raw_meta_str)
                finally:
                    sftp.close()
                    ssh.close()
                    
                ss_payload = dcc.send_string("\ufeff" + raw_ss_str, ss_filename)
                meta_payload = dcc.send_string("\ufeff" + raw_meta_str, meta_filename)
                
                if fail_msgs:
                    return dbc.Alert([f"⚠️ {success_count}건 처리 완료 (일부 누락 발생):"] + [html.Br()] + fail_msgs, color="warning"), ss_payload, meta_payload
                else:
                    return dbc.Alert(f"🎉 완벽합니다! 서버 경로에 파일이 저장되었으며, 브라우저 다운로드도 완료되었습니다.", color="success"), ss_payload, meta_payload
            else:
                return dbc.Alert("❌ 에러: 매칭에 성공한 건이 없습니다.", color="danger"), no_update, no_update
            
        except Exception as e:
            db.rollback()
            traceback.print_exc()
            return dbc.Alert(f"❌ 시스템 에러: {str(e)}", color="danger"), no_update, no_update
        finally:
            db.close()

    # 🚀 [MODIFIED] [콜백 5] 39번 분석 서버 SSH 접속 및 폴더 검색 후 데이터 동기화
    @dash_app.callback(
        [Output("tso-setup-remote-dir-dropdown", "options"),
         Output("tso-setup-remote-status-msg", "children")],
        [Input("tso-setup-btn-remote-search", "n_clicks"),
         Input("tso-setup-btn-remote-sync", "n_clicks")],
        State("tso-setup-remote-dir-dropdown", "value"),
        prevent_initial_call=True
    )
    def handle_remote_sync(btn_search, btn_sync, selected_dirs):
        triggered_id = ctx.triggered_id
        if not triggered_id: return no_update, no_update

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PW, timeout=5)
        except Exception as e:
            return no_update, dbc.Alert(f"❌ 39번 분석 서버 SSH 접속 실패: {e}", color="danger")
            
        try:
            # 1️⃣ 원격 서버 폴더 검색 모드
            if triggered_id == "tso-setup-btn-remote-search":
                # ls 명령어로 RunInfo.xml이 있는 폴더 목록만 가져오기
                command = f"ls -1 {REMOTE_BASE_DIR}/*/RunInfo.xml 2>/dev/null"
                stdin, stdout, stderr = ssh.exec_command(command)
                lines = stdout.readlines()
                
                options = []
                for line in lines:
                    line = line.strip()
                    if line:
                        # 경로 예: /data/results/TSO500/ACC-260623-01-001-DNA/Results.json -> ACC-260623-01-001-DNA
                        folder_name = line.split('/')[-2]
                        options.append({"label": f"📂 {folder_name}", "value": folder_name})
                        
                if not options:
                    msg = dbc.Alert("⚠️ 분석 완료된 폴더(Results.json)를 찾을 수 없습니다.", color="warning")
                else:
                    msg = dbc.Alert(f"✅ {len(options)}개의 분석 완료 폴더를 찾았습니다. 드롭다운에서 선택 후 수집을 진행하세요.", color="success")
                    
                # 폴더 이름을 역순(가장 최근 것이 위로 오게)으로 정렬하여 반환
                return sorted(options, key=lambda x: x["label"], reverse=True), msg

            # 2️⃣ 선택된 폴더 데이터 수집 모드
            elif triggered_id == "tso-setup-btn-remote-sync":
                if not selected_dirs:
                    return no_update, dbc.Alert("⚠️ 수집할 폴더를 먼저 선택해주세요.", color="warning")
                    
                messages = []
                db = SessionLocal()
                try:
                    for dir_name in selected_dirs:
                        target_file = f"{REMOTE_BASE_DIR}/{dir_name}/RunInfo.xml"
                        
                        # cat 명령어로 JSON 읽기
                        stdin, stdout, stderr = ssh.exec_command(f"cat {target_file}")
                        exit_status = stdout.channel.recv_exit_status()
                        
                        if exit_status == 0:
                            raw_json = stdout.read().decode('utf-8')
                            try:
                                parsed_metadata = json.loads(raw_json)
                                
                                # 폴더명과 동일한 sample_id 찾기
                                sample = db.query(Sample).filter(Sample.sample_id == dir_name).first()
                                if sample and sample.analysis:
                                    sample.analysis.analysis_status = "분석 완료"
                                    existing_results = sample.analysis.analysis_results or {}
                                    if isinstance(existing_results, str): existing_results = json.loads(existing_results)
                                    existing_results.update(parsed_metadata)
                                    sample.analysis.analysis_results = existing_results
                                    
                                    from sqlalchemy.orm.attributes import flag_modified
                                    flag_modified(sample.analysis, "analysis_results")
                                    
                                    messages.append(html.Div(f"✅ [{dir_name}] 메타데이터 수집 및 DB 업데이트 완료", className="text-success small fw-bold"))
                                else:
                                    messages.append(html.Div(f"⚠️ [{dir_name}] DB에서 해당 샘플을 찾을 수 없습니다. (폴더명과 Sample ID 불일치)", className="text-danger small"))
                            except json.JSONDecodeError:
                                messages.append(html.Div(f"⚠️ [{dir_name}] JSON 파일 파싱 실패", className="text-warning small"))
                        else:
                            messages.append(html.Div(f"❌ [{dir_name}] Results.json 파일 읽기 실패", className="text-danger small"))
                    
                    db.commit()
                    return no_update, dbc.Alert([html.Strong("📡 데이터 수집 결과:")] + messages, color="info")
                finally:
                    db.close()
                    
        except Exception as e:
            traceback.print_exc()
            return no_update, dbc.Alert(f"❌ 원격 동기화 중 에러 발생: {e}", color="danger")
        finally:
            ssh.close()

def create_tso_setup_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(get_tso_setup_layout)
    app = lims.get_app()
    register_tso_setup_callbacks(app)
    return app