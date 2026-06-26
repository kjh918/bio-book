from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import json
import ast
from sqlalchemy.orm import joinedload
from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis
from app.pages.base import LimsDashApp

def parse_json_like(value):
    """
    DB에 저장된 analysis_results를 안전하게 복구.

    처리 가능 형태:
    1. dict
    2. list
    3. 정상 JSON 문자열: '{"metrics": {...}}'
    4. Python dict 문자열: "{'metrics': {...}}"
    """

    if isinstance(value, dict):
        return {k: parse_json_like(v) for k, v in value.items()}

    if isinstance(value, list):
        return [parse_json_like(v) for v in value]

    if isinstance(value, str):
        s = value.strip()

        if not s:
            return ""

        # dict/list처럼 생긴 문자열만 파싱 시도
        if s.startswith("{") or s.startswith("["):
            try:
                return parse_json_like(json.loads(s))
            except json.JSONDecodeError:
                try:
                    return parse_json_like(ast.literal_eval(s))
                except Exception:
                    return value

        return value

    return value

def create_analysis_results_layout():
    return html.Div([
        html.H3("🧬 분석 결과 상세 조회", className="fw-bold text-secondary mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Dropdown(id="dropdown-sample-select", placeholder="분석 완료된 검체를 선택하세요...", className="mb-3")
            ], width=4),
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
        samples = db.query(Sample).filter(Sample.current_status == "분석 완료").all()
        options = [{"label": f"{s.sample_id} ({s.target_panel})", "value": s.sample_id} for s in samples]
        db.close()
        return options

    @dash_app.callback(
        Output("div-analysis-results-content", "children"),
        Input("dropdown-sample-select", "value")
    )
    def display_results(sample_id):
        if not sample_id: return html.Div("검체를 선택하면 상세 데이터가 표시됩니다.", className="text-muted")
        
        db = SessionLocal()
        sample = db.query(Sample).options(joinedload(Sample.analysis)).filter(Sample.sample_id == sample_id).first()
        db.close()
        
        if not sample or not sample.analysis or not sample.analysis.analysis_results:
            return html.Div("해당 검체의 분석 결과 데이터가 없습니다.", className="text-danger p-3")
        
        # 1. JSON 데이터 안전하게 파싱
        try:
            raw_data = sample.analysis.analysis_results
            data = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
        except Exception:
            return html.Div("데이터 파싱 중 오류가 발생했습니다.", className="text-danger p-3")
            
        columns = ['metrics', 'variants']

        
        for key, value in data.items():
            # [예외 처리] 공백 키 무시
            
            if not str(key).strip(): 
                continue
                
            #parsed_val = value
            #if isinstance(value, str):
            #    try: parsed_val = json.loads(value)
            #    except: pass
            parsed_val = parse_json_like(value)
            
            for key, values in parsed_val.items():
                print(key)
            # Header
            # Analysis_Status
            # QC
            # Notes
            # [A] 변이 데이터 (Small Variants, Fusions, Amplifications 등) -> 개별 탭
            if key in ["Small_Variants", "Gene_Amplifications", "Splice_Variants", "Fusions"]:
                if isinstance(parsed_val, list) and len(parsed_val) > 0:
                    cols = [{"field": str(k), "tooltipField": str(k)} for k in parsed_val[0].keys() if str(k).strip() and str(k).lower() != 'na']
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
            
            # [B] QC 데이터 (Metric, LSL, USL, Value 구조)
            elif key == "QC":
                if isinstance(parsed_val, dict):
                    for m_key, m_val in parsed_val.items():
                        if not str(m_key).strip() or str(m_key).lower() == "na": continue # 🚀 [핵심 수정 2] 공백 항목 무시
                        if isinstance(m_val, dict):
                            qc_data.append({
                                "Section": m_val.get("section", "QC"),
                                "Metric": m_val.get("metric", m_key),
                                "LSL": m_val.get("LSL", ""),
                                "USL": m_val.get("USL", ""),
                                "Value": str(m_val.get("value", ""))
                            })
            
            elif key == "Run_QC_Metrics":
                if isinstance(parsed_val, dict):
                    for m_key, m_val in parsed_val.items():
                        if not str(m_key).strip() or str(m_key).lower() == "na": continue
                        if isinstance(m_val, dict):
                            qc_data.append({
                                "Section": "Run QC Metrics",
                                "Metric": m_key,
                                "LSL": m_val.get("LSL", ""),
                                "USL": m_val.get("USL", ""),
                                "Value": str(m_val.get("Value", ""))
                            })

            # [C] 단순 정보 (Header, Analysis_Status, Notes, TMB, MSI 등)
            elif key in ["Header", "Analysis_Status", "Notes", "TMB", "MSI"]:
                if isinstance(parsed_val, dict):
                    for sub_k, sub_v in parsed_val.items():
                        if not str(sub_k).strip() or str(sub_k).lower() == "na": continue
                        summary_data.append({"섹션": key.replace("_", " "), "항목": sub_k, "값": str(sub_v)})
                        
            # [D] 기타 데이터
            else:
                if isinstance(parsed_val, dict):
                     for sub_k, sub_v in parsed_val.items():
                        if not str(sub_k).strip() or str(sub_k).lower() == "na": continue
                        summary_data.append({"섹션": "기타", "항목": f"{key} - {sub_k}", "값": str(sub_v)})
                elif isinstance(parsed_val, list):
                    pass # 리스트 데이터는 위에서 분기했으므로 그 외 리스트는 무시
                else:
                    if str(parsed_val).strip() and str(parsed_val).lower() != "na":
                        summary_data.append({"섹션": "기타", "항목": key, "값": str(parsed_val)})
                
        # 3. 화면 렌더링용 탭 리스트 조립
        all_tabs = []
        
        if summary_data:
            all_tabs.append(
                dcc.Tab(label="📋 요약 정보", children=[
                    dag.AgGrid(
                        rowData=summary_data,
                        columnDefs=[
                            {"field": "섹션", "flex": 1, "filter": True},
                            {"field": "항목", "flex": 2, "filter": True}, 
                            {"field": "값", "flex": 3}
                        ],
                        defaultColDef={"sortable": True, "resizable": True},
                        style={"height": "450px", "marginTop": "15px"}
                    )
                ])
            )
            
        if qc_data:
            all_tabs.append(
                dcc.Tab(label="📊 QC Metrics", children=[
                    dag.AgGrid(
                        rowData=qc_data,
                        columnDefs=[
                            {"field": "Section", "flex": 2, "filter": True},
                            {"field": "Metric", "flex": 3, "filter": True}, 
                            {"field": "LSL", "flex": 1},
                            {"field": "USL", "flex": 1},
                            {"field": "Value", "flex": 1}
                        ],
                        defaultColDef={"sortable": True, "resizable": True},
                        style={"height": "450px", "marginTop": "15px"}
                    )
                ])
            )
            
        all_tabs.extend(variant_tabs)

        return dbc.Card([
            dbc.CardHeader(html.H5(f"분석 상세: {sample_id} - {sample.target_panel}", className="mb-0 fw-bold text-primary")),
            dbc.CardBody([
                dcc.Tabs(all_tabs)
            ])
        ], className="shadow-sm border-0")

def create_analysis_results_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_analysis_results_layout)
    app = lims.get_app()
    register_analysis_results_callbacks(app)
    return app