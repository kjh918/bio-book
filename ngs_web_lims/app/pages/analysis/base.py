from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify
from datetime import datetime
import pandas as pd
import io
import os
import base64
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, Order, Analysis, ANALYSIS_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR
def create_shared_analysis_layout(
    prefix: str, 
    title: str, 
    description: str, 
    panel_options: list, 
    pipeline_options: list,
    default_panel: str = None
):
    """
    모든 패널(TSO, WGS, WTS 등)의 분석 셋업 페이지가 공유하는 표준 4-Step 레이아웃입니다.
    :param prefix: 콜백 ID 충돌 방지를 위한 접두사 (예: 'tso-setup', 'wgs-setup')
    """
    if default_panel is None and panel_options:
        default_panel = panel_options[0]['value']

    return html.Div([
        # 🚀 Hidden 1: 파일 다운로드 및 세션 스토어
        dcc.Download(id=f"{prefix}-download-template"),
        dcc.Download(id=f"{prefix}-download-samplesheet"), 
        dcc.Store(id=f"{prefix}-uploaded-store", data=None),

        # 🚀 2. STEP 1 & 2: 설정 및 템플릿 업다운로드
        dbc.Card([
            dbc.CardHeader(html.Strong("Step 1 & 2. 분석 환경 설정 및 메타데이터 업로드", className="text-primary")),
            dbc.CardBody([
                dbc.Row([
                    # 설정 영역
                    dbc.Col([
                        html.Label("📌 분석 패널(Panel)", className="fw-bold small"),
                        dcc.Dropdown(
                            id=f"{prefix}-panel-select", 
                            options=panel_options, 
                            value=default_panel, 
                            clearable=False, 
                            className="mb-3 shadow-sm"
                        ),
                        
                        html.Label("⚙️ 파이프라인(Pipeline)", className="fw-bold small"),
                        dcc.Dropdown(
                            id=f"{prefix}-pipeline-select", 
                            options=pipeline_options, 
                            value=pipeline_options[0]['value'] if pipeline_options else None, 
                            clearable=False,
                            className="shadow-sm"
                        )
                    ], lg=4, className="border-end pe-4"),
                    
                    # 템플릿 및 업로드 영역
                    dbc.Col([
                        html.Div("📥 템플릿 다운로드", className="fw-bold text-dark mb-2 small"),
                        dbc.Button(
                            [DashIconify(icon="carbon:template", className="me-2"), "표준 메타데이터 양식(.csv) 받기"], 
                            id=f"{prefix}-btn-download", color="outline-primary", className="w-100 fw-bold shadow-sm mb-3"
                        ),
                        
                        html.Div("📤 메타데이터 업로드 및 파싱", className="fw-bold text-dark mb-2 small"),
                        dcc.Upload(
                            id=f"{prefix}-upload-file",
                            children=html.Div([
                                DashIconify(icon="carbon:cloud-upload", className="me-2"), 
                                '작성된 metadata.csv 드래그 앤 드롭 또는 클릭'
                            ]),
                            style={
                                'width': '100%', 'height': '40px', 'lineHeight': '38px', 
                                'borderWidth': '1px', 'borderStyle': 'dashed', 'textAlign': 'center', 
                                'cursor': 'pointer', 'backgroundColor': '#f8f9fa'
                            }
                        ),
                        html.Div(id=f"{prefix}-upload-status", className="mt-2 small")
                    ], lg=8, className="ps-4")
                ])
            ])
        ], className="border-0 shadow-sm rounded-4 mb-4"),

        # 🚀 3. STEP 3: 샘플 선택 그리드
        dbc.Card([
            dbc.CardHeader(html.Strong("Step 3. 분석 대상 샘플 선택 (대기열 Pool)", className="text-primary")),
            dbc.CardBody([
                html.P("LIMS에 등록된 '분석 진행' 상태의 샘플들 중 이번 런(Run)에 포함할 대상을 체크하세요.", className="small text-muted mb-2"),
                html.Div(id=f"{prefix}-grid-container")
            ], className="p-0 overflow-hidden")
        ], className="border-0 shadow-sm rounded-4 mb-4"),

        # 🚀 4. STEP 4: 매칭 검증 및 실행 제어바
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(html.Div("체크된 샘플과 업로드된 파일을 매칭하여 DB에 적재하고 장비 구동용 SampleSheet를 발행합니다.", className="text-muted small pt-2"), lg=7),
                    dbc.Col(dbc.Button(
                        [DashIconify(icon="carbon:flash", className="me-2"), "Step 4. 매칭 검증 및 SampleSheet 발행"], 
                        id=f"{prefix}-btn-execute", color="success", className="fw-bold shadow-sm w-100 py-2"
                    ), lg=5)
                ]),
                html.Div(id=f"{prefix}-execute-status", className="mt-3")
            ])
        ], className="border-0 shadow-sm rounded-4 mb-5")
        
    ]) # 탭 내부에 들어갈 것이므로 하단 여백 제거


# 🌟 [추가] 통합 대시보드 뷰 레이아웃 (Tabs 구조)
def create_analysis_view_layout():
    # 🚀 함수 내부(Local)에서 import를 수행하여 순환 참조를 회피합니다!
    from app.pages.analysis.tso import get_tso_setup_layout
    
    # 향후 wgs, wts 등을 만들면 여기에 추가 import 하시면 됩니다.
    # from app.pages.analysis.wgs import get_wgs_setup_layout 

    return html.Div([
        # 페이지 공통 헤더
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:pipeline", className="me-2 text-dark"), "Analysis Run Setup Hub"], className="fw-bold text-dark"),
                html.P("패널별(TSO500, WGS 등)로 임상 메타데이터를 파싱하고 장비용 SampleSheet를 발행합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        # 🚀 탭으로 모듈화된 레이아웃 연동
        dbc.Tabs(id="analysis-tabs", active_tab="tab-tso500", children=[
            dbc.Tab(label="🧬 TSO500 Setup", tab_id="tab-tso500", children=[
                html.Div(get_tso_setup_layout(), className="mt-4")
            ]),
            # 향후 wgs 탭을 만들면 아래 주석을 풀고 사용하시면 됩니다.
            # dbc.Tab(label="🧬 WGS Setup", tab_id="tab-wgs", children=[
            #     html.Div(get_wgs_setup_layout(), className="mt-4")
            # ]),
        ], className="nav-fill mb-4")
        
    ], className="pb-5", style={"padding": "20px"})


# 🌟 [추가] 통합 대시보드 앱 생성기
def create_analysis_dashboard_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    
    # 🌟 base 공통 껍데기가 아니라, 탭이 포함된 전체 뷰 레이아웃을 넣습니다!
    lims.set_content(create_analysis_view_layout)
    app = lims.get_app() 
    
    # 🚀 함수 내부(Local)에서 콜백 등록 함수를 import 합니다!
    from app.pages.analysis.tso import register_tso_setup_callbacks
    register_tso_setup_callbacks(app)
    
    # 향후 wgs 탭을 만들면 아래 주석을 풀고 사용하시면 됩니다.
    # from app.pages.analysis.wgs import register_wgs_setup_callbacks
    # register_wgs_setup_callbacks(app)
    
    return app