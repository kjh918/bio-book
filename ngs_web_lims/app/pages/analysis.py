from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

from app.core.database import SessionLocal
# 🚀 뼈대 설정 및 모델들 불러오기
from app.models._schema import Sample, Order, WetLabQC, Sequencing, Analysis, ANALYSIS_SCHEMA_CONFIG, STAGE_SCHEMA_CONFIG
from app.pages.base import LimsDashApp

def create_analysis_dashboard_layout():
    # 스키마에 정의된 패널 목록 목록 생성
    panel_options = [{"label": f"🧬 {panel} 분석 결과 비교", "value": panel} for panel in ANALYSIS_SCHEMA_CONFIG.keys()]
    default_panel = list(ANALYSIS_SCHEMA_CONFIG.keys())[0] if ANALYSIS_SCHEMA_CONFIG else None

    return html.Div([
        # 🚀 1. 페이지 헤더
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:chart-evaluation", className="me-2 text-dark"), "Analysis Results Dashboard"]),
                html.P("패널별 세부 분석 지표(Metrics)와 파이프라인 실행 결과를 한눈에 비교하고 검토합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        # 🚀 2. 컨트롤 패널 (패널 선택 및 내보내기 버튼)
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("📌 분석 종류(Panel) 선택", className="fw-bold small text-primary mb-1"),
                        dcc.Dropdown(
                            id="dashboard-panel-select",
                            options=panel_options,
                            value=default_panel,
                            clearable=False,
                            className="shadow-sm"
                        )
                    ], lg=4),
                    
                    dbc.Col([
                        html.Div("💡 열 헤더의 필터 마크(≡)를 누르면 엑셀처럼 지표별(예: TMB Score) 상세 필터링이 가능합니다.", className="text-muted small mt-4")
                    ], lg=5),
                    
                    dbc.Col([
                        dbc.Button([DashIconify(icon="carbon:csv", className="me-2"), "엑셀(CSV) 내보내기"], 
                                   id="btn-export-analysis-csv", color="success", className="fw-bold shadow-sm w-100 rounded-3 mt-3")
                    ], lg=3, className="text-end")
                ])
            ], className="py-3")
        ], className="border-0 shadow-sm rounded-4 mb-4"),

        # 🚀 3. 메인 분석 결과 그리드
        dbc.Card([
            dbc.CardBody([
                html.Div(id="analysis-dashboard-grid-container")
            ], className="p-0 rounded-4 overflow-hidden")
        ], className="border-0 shadow-sm rounded-4")
        
    ], className="pb-5", style={"padding": "20px"})


def register_analysis_dashboard_callbacks(dash_app):

    # 🚀 [콜백 1] 선택된 패널에 따라 동적으로 AG Grid 생성 및 데이터 로드
    @dash_app.callback(
        Output("analysis-dashboard-grid-container", "children"),
        Input("dashboard-panel-select", "value")
    )
    def update_dashboard_grid(selected_panel):
        if not selected_panel:
            return html.Div("패널을 선택해주세요.", className="p-4 text-center text-muted")

        # 1. 🚀 LimsDashApp 표준 고정 기본 컬럼 불러오기 (Left Pinning 포함)
        base_cols = LimsDashApp.get_base_grid_columns(include_project=True)
        for col in base_cols:
            col["editable"] = False # 대시보드 화면이므로 편집 비활성화

        # 2. 🚀 STAGE_SCHEMA_CONFIG의 "분석 진행" 영역 컬럼들을 동적으로 긁어와 배치
        analysis_stage_config = STAGE_SCHEMA_CONFIG.get("분석 진행", {"columns": []})
        common_analysis_cols = []
        COMMON_FIELD_IDS = []

        for col in analysis_stage_config["columns"]:
            c_id = col["id"]
            COMMON_FIELD_IDS.append(c_id)
            
            ag_col = {
                "headerName": col["name"],
                "field": c_id,
                "editable": False,
                "width": 130,
                "cellStyle": {"backgroundColor": "#f8f9fa"} # 공통 인프라 구분을 위해 연회색 적용
            }
            if col.get("type") == "numeric":
                ag_col["filter"] = "agNumberColumnFilter"
            common_analysis_cols.append(ag_col)

        # 3. 🚀 ANALYSIS_SCHEMA_CONFIG에서 선택된 패널의 고유 지표 컬럼 동적 로드 (JSON 평탄화용)
        panel_config = ANALYSIS_SCHEMA_CONFIG.get(selected_panel, {"columns": []})
        specific_cols = []
        SPECIFIC_FIELD_IDS = []

        for col in panel_config["columns"]:
            c_id = col["id"]
            SPECIFIC_FIELD_IDS.append(c_id)
            
            col_def = {
                "headerName": col["name"], 
                "field": c_id, 
                "editable": False,
                "width": 140,
                # JSON 변수 필드임을 식별하기 위해 스카이블루 스타일 적용
                "cellStyle": {"backgroundColor": "#e3f2fd", "color": "#0d47a1", "fontWeight": "500"}
            }
            if col.get("type") == "numeric":
                col_def["filter"] = "agNumberColumnFilter"
            specific_cols.append(col_def)

        # 최종 컬럼 정의 조립
        columnDefs = base_cols + common_analysis_cols + specific_cols

        # 4. 🚀 데이터 동적 매핑 로드
        db = SessionLocal()
        try:
            # 선택된 패널에 매칭되는 샘플만 타겟팅 필터링
            samples = db.query(Sample).filter(Sample.target_panel == selected_panel).all()
            data = []
            
            for s in samples:
                # [A] 기본 정보 로드
                row = {
                    "id": s.id,
                    "project_name": s.project_name,
                    "order_id": s.order_id,
                    "sample_id": s.sample_id,
                    "sample_name": s.sample_name,
                    "target_panel": s.target_panel
                }
                
                # [B] "분석 진행" 단계의 공통 컬럼 관계형 매핑 처리 (자동 순회)
                for col_id in COMMON_FIELD_IDS:
                    val = None
                    if hasattr(s, col_id): val = getattr(s, col_id)
                    elif s.analysis and hasattr(s.analysis, col_id): val = getattr(s.analysis, col_id)
                    
                    row[col_id] = val if val is not None else "-"

                # [C] 🌟 JSON 필드(analysis_results) 내부의 패널 고유 데이터 평탄화 처리
                results_json = {}
                if s.analysis and s.analysis.analysis_results:
                    # 데이터가 문자열로 들어가 있을 경우를 대비한 안전한 딕셔너리 변환 방어코드
                    if isinstance(s.analysis.analysis_results, str):
                        import json
                        try: results_json = json.loads(s.analysis.analysis_results)
                        except: results_json = {}
                    else:
                        results_json = s.analysis.analysis_results

                for col_id in SPECIFIC_FIELD_IDS:
                    # JSON 내부 깊숙이 박혀있는 고유 메트릭 키값 로드, 없을 시 기본값 '-' 처리
                    row[col_id] = results_json.get(col_id, "-")

                data.append(row)

            # 🚀 5. LimsDashApp 표준 AG Grid 명세서 호출 생성
            grid = LimsDashApp.create_standard_aggrid(
                id="analysis-dashboard-grid",
                columnDefs=columnDefs,
                height="68vh"
            )
            
            # 대시보드용 페이지네이션 추가 구성 옵션 주입
            grid.dashGridOptions.update({
                "pagination": True,
                "paginationPageSize": 25,
                "enableCellTextSelection": True
            })
            grid.rowData = data
            return grid
            
        finally:
            db.close()

    # 🚀 [콜백 2] 엑셀(CSV) 내보내기 기능
    @dash_app.callback(
        Output("analysis-dashboard-grid", "exportDataAsCsv"),
        Input("btn-export-analysis-csv", "n_clicks"),
        prevent_initial_call=True
    )
    def export_csv(n_clicks):
        if n_clicks:
            return True
        return False


def create_analysis_dashboard_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_analysis_dashboard_layout)
    app = lims.get_app() 
    register_analysis_dashboard_callbacks(app)
    return app