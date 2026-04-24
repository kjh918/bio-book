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
         Input("track-search-input", "n_submit"), # 엔터키 지원
         Input({"type": "btn-quick-receive", "sample_id": "ALL"}, "n_clicks")], # 빠른 접수 버튼
        [State("track-search-input", "value")],
        prevent_initial_call=True
    )
    def update_tracking_view(btn_search, enter_search, btn_receive, search_val):
        if not search_val: return {"display": "none"}, ""
        
        db = SessionLocal()
        try:
            # 트리거 확인 (접수 버튼을 눌렀는지, 검색을 눌렀는지)
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
            
            # 🚀 샘플 조회 (Sample ID 또는 Patient ID로 유연하게 검색)
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
                    db.refresh(sample) # 업데이트된 상태 반영

            # 의뢰(Order) 정보 가져오기
            order = sample.order

            # --------------------------------------------------------
            # 🎨 UI 구성 1: 샘플 메타 정보 카드
            # --------------------------------------------------------
            meta_card = dbc.Card([
                dbc.CardHeader(html.H5("📝 검체 상세 정보", className="fw-bold mb-0")),
                dbc.CardBody([
                    html.Table([
                        html.Tbody([
                            html.Tr([html.Th("Regist ID", style={"width": "30%", "color": "#666"}), html.Td(html.Strong(sample.sample_id, className="text-primary"))]),
                            html.Tr([html.Th("Patient ID"), html.Td(sample.sample_name)]),
                            html.Tr([html.Th("의뢰 기관"), html.Td(f"{order.facility} ({order.client_team})" if order else "-")]),
                            html.Tr([html.Th("분석 패널"), html.Td(dbc.Badge(sample.target_panel, color="info"))]),
                            html.Tr([html.Th("검체 종류"), html.Td(sample.specimen or "-")]),
                            html.Tr([html.Th("현재 상태"), html.Td(dbc.Badge(sample.current_status, color="success", className="px-3 py-2 fs-6"))]),
                        ])
                    ], className="table table-borderless mb-0")
                ])
            ], className="border-0 shadow-sm rounded-4 h-100")

            # --------------------------------------------------------
            # 🎨 UI 구성 2: 지하철 노선도 형태의 타임라인
            # --------------------------------------------------------
            current_idx = PIPELINE_STAGES.index(sample.current_status) if sample.current_status in PIPELINE_STAGES else -1
            
            timeline_items = []
            for i, stage in enumerate(PIPELINE_STAGES):
                # 상태 판별: 지나온 단계(과거), 현재 단계, 아직 안 온 단계(미래)
                if i < current_idx:
                    icon_color, text_color, icon_name = "success", "text-success", "carbon:checkmark-filled"
                elif i == current_idx:
                    icon_color, text_color, icon_name = "primary", "text-primary fw-bold", "carbon:radio-button-checked"
                else:
                    icon_color, text_color, icon_name = "secondary", "text-muted", "carbon:radio-button"

                # 타임라인 아이템 UI
                timeline_items.append(
                    html.Div([
                        html.Div(DashIconify(icon=icon_name, width=24, color=f"var(--bs-{icon_color})"), style={"width": "40px", "textAlign": "center"}),
                        html.Div([
                            html.H6(stage, className=f"mb-0 {text_color}"),
                            # 현재 단계면 추가 정보나 버튼 표시
                            html.Div(
                                dbc.Button("📦 실물 입고 확인 (Check-in)", id={"type": "btn-quick-receive", "sample_id": sample.sample_id}, size="sm", color="primary", className="mt-2 fw-bold shadow-sm")
                                if i == current_idx and stage == "접수 대기" else "",
                            )
                        ], style={"flex": 1, "paddingBottom": "25px", "borderLeft": f"2px solid {'var(--bs-success)' if i < current_idx else '#ddd'}", "paddingLeft": "15px", "marginLeft": "-20px"})
                    ], style={"display": "flex", "alignItems": "flex-start"})
                )

            timeline_card = dbc.Card([
                dbc.CardHeader(html.H5("🛤️ 워크플로우 경로 (Timeline)", className="fw-bold mb-0")),
                dbc.CardBody(timeline_items, className="pt-4 px-4")
            ], className="border-0 shadow-sm rounded-4 h-100")

            # 최종 레이아웃 조합
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