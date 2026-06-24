from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import json
from sqlalchemy.orm import joinedload
from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis
from app.pages.base import LimsDashApp

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
        # 🚀 수정: Analysis 모델을 joinedload로 함께 로드하여 세션 종료 후에도 데이터 접근 가능하게 함
        sample = db.query(Sample).options(joinedload(Sample.analysis)).filter(Sample.sample_id == sample_id).first()
        db.close()
        
        # 🚀 수정: 연결된 analysis 객체 및 results 데이터 유무 확인
        if not sample or not sample.analysis or not sample.analysis.analysis_results:
            return html.Div("해당 검체의 분석 결과 데이터가 없습니다.", className="text-danger p-3")
        
        try:
            data = sample.analysis.analysis_results
            if isinstance(data, str):
                data = json.loads(data)
        except Exception:
            return html.Div("데이터 파싱 중 오류가 발생했습니다.", className="text-danger p-3")
        
        # 1. 고정 정보 및 핵심 Metric 표 구성
        metrics = data.get("metrics", {})
        summary_data = [{"항목": k, "값": v} for k, v in metrics.items()]
        
        return dbc.Card([
            dbc.CardHeader(html.H5(f"분석 상세: {sample_id} - {sample.target_panel}", className="mb-0")),
            dbc.CardBody([
                dcc.Tabs([
                    dcc.Tab(label="요약 및 Metric", children=[
                        dag.AgGrid(
                            rowData=summary_data,
                            columnDefs=[{"field": "항목"}, {"field": "값"}],
                            defaultColDef={"flex": 1, "sortable": True},
                            style={"height": "300px"}
                        )
                    ]),
                    dcc.Tab(label="상세 변이 정보", children=[
                        html.Div(className="p-3", children=[
                            html.Pre(json.dumps(data.get("variants", []), indent=2), style={"maxHeight": "500px", "overflowY": "scroll"})
                        ])
                    ])
                ])
            ])
        ])

def create_analysis_results_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_analysis_results_layout)
    app = lims.get_app()
    register_analysis_results_callbacks(app)
    return app