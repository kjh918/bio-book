from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify
import datetime

from app.core.database import SessionLocal
from app.models._schema import Sample, Order
from app.pages.base import LimsDashApp

# LIMS의 전체 파이프라인 단계 (순서대로)
PIPELINE_STAGES = ["접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기"]

def create_tracking_view_layout():
    return html.Div([
        html.H3("🔍 샘플 경로 추적 (Sample Tracker)", className="fw-bold text-secondary mb-4"),
        
        # 1. 🔍 검색 영역
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText(DashIconify(icon="carbon:search")),
                            dbc.Input(id="track-search-input", placeholder="Sample ID 또는 Patient ID를 입력하세요 (예: ACC-260424-01-001)", debounce=True),
                            dbc.Button("추적하기", id="btn-track-search", color="primary", className="fw-bold")
                        ], className="shadow-sm")
                    ], md=8, lg=6)
                ], justify="center")
            ])
        ], className="border-0 bg-transparent mb-4"),
        
        # 2. 📊 검색 결과 영역 (기본적으로 숨김)
        html.Div(id="track-result-container", style={"display": "none"})
        
    ], className="pb-5", style={"padding": "20px"})


def register_tracking_callbacks(dash_app):
    
    @dash_app.callback(
        [Output("track-result-container", "style"),
         Output("track-result-container", "children")],
        [Input("btn-track-search", "n_clicks"),
         Input("track-search-input", "n_submit"), 
         Input({"type": "btn-quick-receive", "sample_id": "ALL"}, "n_clicks")], 
        [State("track-search-input", "value")],
        prevent_initial_call=True
    )
    def update_tracking_view(btn_search, enter_search, btn_receive, search_val):
        if not search_val: return {"display": "none"}, ""
        
        db = SessionLocal()
        try:
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
            
            # 🚀 샘플 조회
            search_val = search_val.strip()
            sample = db.query(Sample).filter(
                (Sample.sample_id == search_val) | (Sample.sample_name == search_val)
            ).first()
            
            if not sample:
                return {"display": "block"}, dbc.Alert("❌ 일치하는 샘플을 찾을 수 없습니다. 번호를 다시 확인해 주세요.", color="danger", className="shadow-sm")

            # 🚀 [빠른 입고 처리 로직]
            if "btn-quick-receive" in triggered_id:
                if sample.current_status == "접수 대기":
                    sample.current_status = "접수 완료"
                    db.commit()
                    db.refresh(sample) 

            order = sample.order

            # --------------------------------------------------------
            # 🎨 UI 구성 1: 샘플 메타 정보 카드 (최신 스키마 적용 🚀)
            # --------------------------------------------------------
            meta_card = dbc.Card([
                dbc.CardHeader(html.H5("📝 검체 상세 정보", className="fw-bold mb-0")),
                dbc.CardBody([
                    html.Table([
                        html.Tbody([
                            # 📌 1. 접수 ID (Order ID)
                            html.Tr([
                                html.Th("접수 ID (Order ID)", style={"width": "40%", "color": "#666"}), 
                                html.Td(html.Strong(sample.order_id, className="text-secondary"))
                            ]),
                            
                            # 📌 2. 샘플 ID (ACC ID)
                            html.Tr([
                                html.Th("샘플 ID (ACC ID)"), 
                                html.Td(html.Strong(sample.sample_id, className="text-primary"))
                            ]),
                            
                            # 📌 3. 환자 ID (Patient ID)
                            html.Tr([
                                html.Th("환자 ID (Patient ID)"), 
                                html.Td(sample.sample_name) # 받은 그대로의 ID
                            ]),
                            
                            html.Tr([html.Th("Project 명"), html.Td(sample.project_name)]),
                            html.Tr([html.Th("의뢰자 정보"), html.Td(f"{order.client_name} ({order.facility})" if order and order.client_name != "-" else (order.facility if order else "-"))]),
                            html.Tr([html.Th("분석 패널"), html.Td(dbc.Badge(sample.target_panel, color="info"))]),
                            html.Tr([html.Th("검체 종류"), html.Td(sample.specimen or "-")]),
                            html.Tr([html.Th("현재 상태"), html.Td(dbc.Badge(sample.current_status, color="success" if sample.current_status not in ["보류/실패", "재실험"] else "danger", className="px-3 py-2 fs-6"))]),
                        ])
                    ], className="table table-borderless table-sm mb-0")
                ])
            ], className="border-0 shadow-sm rounded-4 h-100")
            # --------------------------------------------------------
            # 🎨 UI 구성 2: 지하철 노선도 형태의 타임라인
            # --------------------------------------------------------
            is_failed = sample.current_status in ["보류/실패", "재실험"]
            current_idx = PIPELINE_STAGES.index(sample.current_status) if sample.current_status in PIPELINE_STAGES else -1
            
            timeline_items = []
            
            # 실패/보류 시 타임라인 상단에 경고 메시지 표기
            if is_failed:
                timeline_items.append(
                    html.Div([
                        html.Div(DashIconify(icon="carbon:warning-filled", width=28, color="var(--bs-danger)"), style={"width": "40px", "textAlign": "center"}),
                        html.Div([
                            html.H6(f"🚨 {sample.current_status}", className="mb-1 text-danger fw-bold"),
                            html.P(sample.issue_comment or "실험 및 분석이 중단되었습니다.", className="small text-muted mb-0")
                        ], style={"flex": 1, "paddingBottom": "25px", "borderLeft": "2px dashed var(--bs-danger)", "paddingLeft": "15px", "marginLeft": "-20px"})
                    ], style={"display": "flex", "alignItems": "flex-start"})
                )

            for i, stage in enumerate(PIPELINE_STAGES):
                if is_failed:
                    # 에러 상태면 모든 일반 진행 타임라인은 회색 처리
                    icon_color, text_color, icon_name = "secondary", "text-muted", "carbon:radio-button"
                elif i < current_idx:
                    icon_color, text_color, icon_name = "success", "text-success", "carbon:checkmark-filled"
                elif i == current_idx:
                    icon_color, text_color, icon_name = "primary", "text-primary fw-bold", "carbon:radio-button-checked"
                else:
                    icon_color, text_color, icon_name = "secondary", "text-muted", "carbon:radio-button"

                timeline_items.append(
                    html.Div([
                        html.Div(DashIconify(icon=icon_name, width=24, color=f"var(--bs-{icon_color})"), style={"width": "40px", "textAlign": "center"}),
                        html.Div([
                            html.H6(stage, className=f"mb-0 {text_color}"),
                            html.Div(
                                dbc.Button("📦 실물 입고 확인 (Check-in)", id={"type": "btn-quick-receive", "sample_id": sample.sample_id}, size="sm", color="primary", className="mt-2 fw-bold shadow-sm")
                                if i == current_idx and stage == "접수 대기" else "",
                            )
                        ], style={"flex": 1, "paddingBottom": "25px", "borderLeft": f"2px solid {'var(--bs-success)' if (i < current_idx and not is_failed) else '#ddd'}", "paddingLeft": "15px", "marginLeft": "-20px"})
                    ], style={"display": "flex", "alignItems": "flex-start"})
                )

            timeline_card = dbc.Card([
                dbc.CardHeader(html.H5("🛤️ 워크플로우 경로 (Timeline)", className="fw-bold mb-0")),
                dbc.CardBody(timeline_items, className="pt-4 px-4")
            ], className="border-0 shadow-sm rounded-4 h-100")

            result_ui = dbc.Row([
                dbc.Col(meta_card, xs=12, lg=5, className="mb-4 mb-lg-0"),
                dbc.Col(timeline_card, xs=12, lg=7)
            ])
            
            return {"display": "block"}, result_ui
            
        except Exception as e:
            return {"display": "block"}, dbc.Alert(f"시스템 오류: {e}", color="danger")
        finally:
            db.close()

def create_tracking_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_tracking_view_layout)
    app = lims.get_app() 
    register_tracking_callbacks(app)
    return app