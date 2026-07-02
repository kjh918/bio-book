from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from datetime import datetime
import pandas as pd
import io
import os
import base64
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR
from app.pages.analysis.base import create_shared_analysis_layout

# 🚀 1. TSO500 전용 레이아웃 생성
def get_tso_setup_layout():
    return create_shared_analysis_layout(
        prefix="tso-setup",
        title="TSO500 Analysis Run Setup",
        description="Illumina TSO500 패널의 DNA/RNA 통합 분석 셋업 및 SampleSheet 발행 화면입니다.",
        panel_options=[{"label": "🧬 TSO500", "value": "TSO500"}],
        pipeline_options=[{"label": "DNA/RNA Integrated", "value": "DNA/RNA 통합"}]
    )

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
         Input("tso-setup-execute-status", "children")] 
    )
    def load_pending_grid(panel, _):
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
            samples = db.query(Sample).filter(Sample.target_panel == panel, Sample.current_status == "분석 진행").all()
            data = []
            for s in samples:
                a_status = s.analysis.analysis_status if s.analysis else "대기중"
                if a_status != "대기중": continue 
                
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

    # 🚀 [콜백 4] 매칭 실행 + SampleSheet & Metadata 동시 발행!
    @dash_app.callback(
        [Output("tso-setup-execute-status", "children"),
         Output("tso-setup-download-samplesheet", "data"),
         Output("tso-setup-download-template", "data", allow_duplicate=True)], 
        Input("tso-setup-btn-execute", "n_clicks"),
        [State("tso-setup-aggrid", "selectedRows"),
         State("tso-setup-uploaded-store", "data"),
         State("tso-setup-panel-select", "value"),
         State("tso-setup-pipeline-select", "value")],
        prevent_initial_call=True
    )
    def execute_analysis_setup(n_clicks, selected_rows, metadata_list, panel, pipeline):
        if not selected_rows: return dbc.Alert("⚠️ Grid에서 분석할 샘플을 먼저 선택해주세요.", color="warning"), no_update, no_update
        if not metadata_list: return dbc.Alert("⚠️ Step 2에서 메타데이터 파일을 먼저 업로드해주세요.", color="warning"), no_update, no_update
            
        def safe_get(meta, key, default):
            val = meta.get(key, default)
            if pd.isna(val) or str(val).strip().lower() == "nan": return default
            return val

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

                # 🌟 [추가된 로직] 서버 지정 경로에 물리 파일(Physical File)로 저장!
                # 예시: 프로젝트 최상단 폴더 아래에 'exports/TSO500' 폴더를 만들어 저장합니다. 
                # (실제 서버의 절대경로, 예: '/data/sequencer_run/' 등으로 변경하셔도 됩니다)
                server_export_dir = os.path.join(BASE_DIR, "exports", "TSO500")
                os.makedirs(server_export_dir, exist_ok=True) # 폴더가 없으면 자동 생성
                
                # 서버 하드디스크에 한글이 깨지지 않게 utf-8-sig 모드로 물리적 쓰기(Write)
                with open(os.path.join(server_export_dir, ss_filename), 'w', encoding='utf-8-sig') as f:
                    f.write(raw_ss_str)
                    
                with open(os.path.join(server_export_dir, meta_filename), 'w', encoding='utf-8-sig') as f:
                    f.write(raw_meta_str)

                # 3. 연구원 브라우저로도 동시 다운로드 쏴주기 (기존과 동일, 수동 BOM 추가)
                ss_payload = dcc.send_string("\ufeff" + raw_ss_str, ss_filename)
                meta_payload = dcc.send_string("\ufeff" + raw_meta_str, meta_filename)
                
                if fail_msgs:
                    return dbc.Alert([f"⚠️ {success_count}건 처리 완료 (일부 누락 발생):"] + [html.Br()] + fail_msgs, color="warning"), ss_payload, meta_payload
                else:
                    return dbc.Alert(f"🎉 완벽합니다! 서버 경로({server_export_dir})에 파일이 저장되었으며, 브라우저 다운로드도 완료되었습니다.", color="success"), ss_payload, meta_payload
            else:
                return dbc.Alert("❌ 에러: 매칭에 성공한 건이 없습니다.", color="danger"), no_update, no_update
            
        except Exception as e:
            db.rollback()
            traceback.print_exc()
            return dbc.Alert(f"❌ 시스템 에러: {str(e)}", color="danger"), no_update, no_update
        finally:
            db.close()