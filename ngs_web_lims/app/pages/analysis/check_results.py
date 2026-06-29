from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import json
import ast
import re
from sqlalchemy.orm import joinedload
from app.core.database import SessionLocal
from app.models._schema import Sample
from app.pages.base import LimsDashApp

def parse_json_like(value):
    """
    DB에 저장된 analysis_results를 안전하게 복구하고 빈 값이나 NA를 재귀적으로 제거합니다.
    작은따옴표가 포함된 파이썬 dict 형태의 문자열도 완벽하게 파싱합니다.
    """
    if isinstance(value, dict):
        return {k: parse_json_like(v) for k, v in value.items() if parse_json_like(v) is not None and parse_json_like(v) != []}

    if isinstance(value, list):
        return [parse_json_like(v) for v in value if parse_json_like(v) is not None]

    if isinstance(value, str):
        s = value.strip()
        if not s or s.upper() in ["NA", "N/A", "NONE", "NULL"]:
            return None

        # dict/list처럼 생긴 문자열만 파싱 시도
        if s.startswith("{") or s.startswith("["):
            try:
                # 1. 표준 JSON 파싱 시도
                return parse_json_like(json.loads(s))
            except Exception:
                try:
                    # 2. Python dict 문자열(작은따옴표, null, nan 등) 파싱 시도
                    s_safe = s.replace("null", "None").replace("true", "True").replace("false", "False").replace("nan", "None")
                    return parse_json_like(ast.literal_eval(s_safe))
                except Exception:
                    # 3. 정규식으로 따옴표 강제 교체 후 최후의 JSON 파싱 시도
                    try:
                        s_json = re.sub(r"'([^']*)'", r'"\1"', s)
                        return parse_json_like(json.loads(s_json))
                    except:
                        return s
        return s

    return value

def create_analysis_results_layout():
    return html.Div([
        html.H3("🧬 분석 결과 상세 조회", className="fw-bold text-secondary mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Dropdown(id="dropdown-sample-select", placeholder="분석 완료된 검체를 선택하세요...", className="mb-3 shadow-sm")
            ], width=5),
        ]),
        
        html.Div(id="div-analysis-results-content")
    ], className="pb-5", style={"padding": "20px"})

def register_analysis_results_callbacks(dash_app):
    
    @dash_app.callback(
        Output("dropdown-sample-select", "options"),
        Input("dropdown-sample-select", "id")
    )
    def load_samples(_):
        db = SessionLocal()
        try:
            samples = db.query(Sample).filter(Sample.current_status == "분석 완료").all()
            
            # 🚀 고유한 Base Sample ID만 추출 (DNA/RNA 접미사 제거하여 그룹핑)
            unique_base_ids = set()
            for s in samples:
                base_id = s.sample_id.replace("-DNA", "").replace("-RNA", "")
                unique_base_ids.add((base_id, s.target_panel))
                
            options = [{"label": f"{base_id} ({panel})", "value": base_id} for base_id, panel in unique_base_ids]
            
            # 이름 역순 정렬 (가장 최근 접수번호가 위로 오도록)
            return sorted(options, key=lambda x: x["label"], reverse=True)
        finally:
            db.close()

    @dash_app.callback(
        Output("div-analysis-results-content", "children"),
        Input("dropdown-sample-select", "value")
    )
    def display_results(sample_id):
        if not sample_id: return html.Div("검체를 선택하면 상세 데이터가 표시됩니다.", className="text-muted")
        
        db = SessionLocal()
        try:
            # 🚀 DNA/RNA 매칭: 선택한 Base ID로 시작하는 모든 샘플(-DNA, -RNA) 동시 조회
            samples = db.query(Sample).options(joinedload(Sample.analysis)).filter(Sample.sample_id.like(f"{sample_id}%")).all()
        finally:
            db.close()
        
        if not samples:
            return html.Div("해당 검체의 분석 결과 데이터가 없습니다.", className="text-danger p-3")
        
        all_tabs = []
        
        for s in samples:
            # 데이터가 아예 없는 경우에도 샘플 탭 형태는 유지
            if not s.analysis or not s.analysis.analysis_results:
                all_tabs.append(dcc.Tab(label=f"🔬 {s.sample_id}", children=[
                    html.Div("해당 검체(DNA/RNA)의 분석 결과가 비어 있습니다.", className="p-3 text-warning")
                ]))
                continue
                
            # 1. JSON 데이터 안전하게 파싱 및 정제
            raw_data = s.analysis.analysis_results
            data = parse_json_like(raw_data)
            
            if not data:
                all_tabs.append(dcc.Tab(label=f"🔬 {s.sample_id}", children=[
                    html.Div("해당 검체(DNA/RNA)의 파싱 가능한 데이터가 없습니다.", className="p-3 text-warning")
                ]))
                continue
                
            # 🚀 과거 구조 호환: {"metrics": {...}, "variants": {...}} 형태 평탄화(Flatten)
            # 파싱이 완료된 딕셔너리 내부를 샅샅이 뒤져 TMB/MSI를 밖으로 꺼냅니다.
            flattened_data = {}
            for k, v in data.items():
                if isinstance(v, str) and (v.strip().startswith("{") or v.strip().startswith("[")):
                    v = parse_json_like(v)
                    
                if k in ["metrics", "variants"] and isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        flattened_data[sub_k] = sub_v
                else:
                    flattened_data[k] = v
            data = flattened_data
            
            # 루프 시작 전 변수 초기화
            summary_data = []
            qc_data = []
            variant_tabs = []
            
            for key, parsed_val in data.items():
                if not str(key).strip() or str(key).upper() == "NA" or parsed_val is None: 
                    continue
                    
                # [A] 변이 데이터 탭 구성 (표 형태) - 값이 없으면 탭을 생성하지 않음 (형태 유지)
                if key in ["Small_Variants", "Gene_Amplifications", "Splice_Variants", "Fusions"]:
                    if isinstance(parsed_val, list) and len(parsed_val) > 0:
                        cols = [{"field": str(k), "tooltipField": str(k)} for k in parsed_val[0].keys() if str(k).strip() and str(k).upper() != 'NA']
                        if cols:
                            variant_tabs.append(
                                dcc.Tab(label=key.replace("_", " "), children=[
                                    dag.AgGrid(
                                        rowData=parsed_val,
                                        columnDefs=cols,
                                        defaultColDef={"sortable": True, "filter": True, "resizable": True},
                                        dashGridOptions={"pagination": True, "paginationPageSize": 15},
                                        style={"height": "450px", "marginTop": "15px"}
                                    )
                                ])
                            )
                
                # [B] QC 데이터 구성
                elif key in ["QC", "Run_QC_Metrics"]:
                    if isinstance(parsed_val, dict):
                        for m_key, m_val in parsed_val.items():
                            if not str(m_key).strip() or str(m_key).upper() == "NA": continue
                            if isinstance(m_val, dict):
                                qc_data.append({
                                    "Section": key.replace("_", " "),
                                    "Metric": str(m_val.get("metric", m_key)),
                                    "LSL": str(m_val.get("LSL", "")),
                                    "USL": str(m_val.get("USL", "")),
                                    "Value": str(m_val.get("value", m_val.get("Value", "")))
                                })
                            else:
                                qc_data.append({
                                    "Section": key.replace("_", " "),
                                    "Metric": str(m_key),
                                    "LSL": "",
                                    "USL": "",
                                    "Value": str(m_val)
                                })
                
                # [C-1] 🚀 TMB, MSI 강제 추출 및 시각적 강조 (최우선 배치)
                elif key in ["TMB", "MSI"]:
                    if isinstance(parsed_val, dict):
                        for sub_k, sub_v in parsed_val.items():
                            if not str(sub_k).strip() or str(sub_k).upper() == "NA": continue
                            summary_data.append({"섹션": f"📌 {key}", "항목": str(sub_k).replace("_", " "), "값": str(sub_v)})
                    else:
                        summary_data.append({"섹션": f"📌 {key}", "항목": str(key).replace("_", " "), "값": str(parsed_val)})
                
                # [C-2] 일반 요약 데이터 구성
                elif key in ["Header", "Analysis_Status", "Notes", "Analysis_Details"]:
                    if isinstance(parsed_val, dict):
                        for sub_k, sub_v in parsed_val.items():
                            if not str(sub_k).strip() or str(sub_k).upper() == "NA": continue
                            summary_data.append({"섹션": key.replace("_", " "), "항목": str(sub_k), "값": str(sub_v)})
                    else:
                        summary_data.append({"섹션": "요약", "항목": str(key).replace("_", " "), "값": str(parsed_val)})
                        
                elif key == "pipeline_finished_at":
                    summary_data.append({"섹션": "기본 정보", "항목": "Pipeline Finished At", "값": str(parsed_val)})
                
                # [D] 그 외 기타 데이터
                else:
                    if isinstance(parsed_val, dict):
                         for sub_k, sub_v in parsed_val.items():
                            if not str(sub_k).strip() or str(sub_k).upper() == "NA": continue
                            summary_data.append({"섹션": "기타", "항목": f"{key} - {sub_k}", "값": str(sub_v)})
                    elif str(parsed_val).strip() and str(parsed_val).upper() != "NA":
                        summary_data.append({"섹션": "기타", "항목": str(key), "값": str(parsed_val)})
                        
            # 각 DNA/RNA 샘플 별로 탭 내부에 요약/QC/변이 서브 탭 구성
            inner_tabs = []
            
            # 요약 정보 표의 정렬: 📌 TMB/MSI가 상단에 위치하도록 정렬 로직 추가
            if summary_data:
                summary_data = sorted(summary_data, key=lambda x: (0 if "📌" in x["섹션"] else 1, x["섹션"], x["항목"]))
                inner_tabs.append(dcc.Tab(label="📋 요약 정보", children=[
                    dag.AgGrid(rowData=summary_data, columnDefs=[{"field": "섹션", "flex": 1, "filter": True}, {"field": "항목", "flex": 2, "filter": True}, {"field": "값", "flex": 3}], defaultColDef={"sortable": True, "resizable": True}, style={"height": "450px", "marginTop": "15px"})
                ]))
                
            if qc_data:
                inner_tabs.append(dcc.Tab(label="📊 QC Metrics", children=[
                    dag.AgGrid(rowData=qc_data, columnDefs=[{"field": "Section", "flex": 2, "filter": True}, {"field": "Metric", "flex": 3, "filter": True}, {"field": "LSL", "flex": 1}, {"field": "USL", "flex": 1}, {"field": "Value", "flex": 1}], defaultColDef={"sortable": True, "resizable": True}, style={"height": "450px", "marginTop": "15px"})
                ]))
                
            # 변이가 있으면(리스트 요소가 존재하면) 탭이 추가되고, 없으면 추가되지 않음
            inner_tabs.extend(variant_tabs)
            
            # 메인 탭(DNA/RNA 탭)에 조립된 서브 탭 추가 (샘플 자체가 있으면 형태는 항상 유지됨)
            all_tabs.append(dcc.Tab(label=f"🔬 {s.sample_id}", children=[
                html.Div(dcc.Tabs(inner_tabs), className="mt-3")
            ], selected_style={'borderTop': '3px solid #18BC9C', 'fontWeight': 'bold'}))

        if not all_tabs:
            return html.Div("해당 검체의 유효한 결과 데이터가 없습니다.", className="text-warning p-3")
            
        return dbc.Card([
            dbc.CardHeader([
                html.H5(f"분석 상세: {sample_id}", className="mb-0 fw-bold text-primary")
            ]),
            dbc.CardBody([dcc.Tabs(all_tabs)])
        ], className="shadow-sm border-0")

def create_analysis_results_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_analysis_results_layout)
    app = lims.get_app()
    register_analysis_results_callbacks(app)
    return app