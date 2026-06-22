from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_iconify import DashIconify
from datetime import datetime
import os
import base64
import traceback

from app.core.database import SessionLocal
from app.models._schema import Sample, Order, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR

# 🚨 주의: 여기에 있던 qc_report, clinical_report import 문을 삭제했습니다! (순환 참조 방지)

def create_shared_report_layout(prefix: str, title: str, template_options: list):
    """
    QC와 Clinical Report에서 공통으로 사용하는 화면 레이아웃을 생성합니다.
    prefix: 'qc' 또는 'clinical' (ID 충돌 방지용)
    """
    return html.Div([
        # 🚀 1. 상단 Grid 및 배치 필터
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label(f"📌 {prefix.upper()} 배치(Batch) 필터", className="fw-bold small text-muted mb-1"),
                        dbc.Select(id=f"{prefix}-batch-select", options=[{"label": "전체 보기", "value": "ALL"}], value="ALL", className="shadow-sm rounded-3", style={"width": "250px"})
                    ], width="auto"),
                    dbc.Col(html.H5(title, className="fw-bold m-0 mt-4 text-center"), align="center"),
                    dbc.Col([
                        dbc.Button([DashIconify(icon="carbon:settings-adjust", className="me-2"), "양식 설정 열기"], 
                                   id=f"{prefix}-btn-open-settings", color="light", className="fw-bold shadow-sm border rounded-3 text-secondary mt-3")
                    ], width="auto", className="text-end")
                ], className="mb-4 d-flex justify-content-between"),
                
                html.Div(id=f"{prefix}-grid-container") 
            ])
        ], className="border-0 shadow-sm rounded-4 mb-4"),
        
        # 🚀 2. 하단 보고서 빌더 (숨김 처리됨, '양식 설정 열기' 클릭 시 등장)
        html.Div(id=f"{prefix}-builder-section", style={"display": "none"}, children=[
            html.Hr(className="my-5 border-2 text-secondary"),
            dbc.Row([
                # 설정 폼
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("1. 양식 및 첨부파일 설정", className="fw-bold mb-0")),
                        dbc.CardBody([
                            html.Label("적용할 레포트 템플릿", className="fw-bold text-primary"),
                            dcc.Dropdown(
                                id=f"{prefix}-template-select", 
                                options=template_options, 
                                value=template_options[0]['value'] if template_options else None, 
                                clearable=False, className="mb-3"
                            ),
                            
                            html.Label("보고서 타이틀", className="fw-bold text-primary small"),
                            dbc.Input(id=f"{prefix}-title-input", placeholder="예: NGS 품질 검사 결과지", className="mb-3"),
                            
                            html.Label("총괄 책임자 서명", className="fw-bold text-primary small"),
                            dbc.Input(id=f"{prefix}-author-input", placeholder="책임자 이름 입력", className="mb-4"),
                            
                            html.Hr(),
                            
                            html.Label("📊 첨부 이미지 (다중 첨부 가능)", className="fw-bold text-primary mt-2"),
                            dcc.Upload(
                                id=f'{prefix}-upload-image', 
                                children=html.Div(['드래그 앤 드롭 또는 클릭하여 이미지 첨부']), 
                                style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '2px', 'borderStyle': 'dashed', 'borderColor': '#3498DB', 'borderRadius': '5px', 'textAlign': 'center', 'backgroundColor': '#f4f9fc', 'cursor': 'pointer'},
                                multiple=True
                            ),
                            html.Div(id=f"{prefix}-upload-preview", className="mt-2 text-muted small"),
                            
                            html.Hr(className="mt-4"),
                            dcc.Download(id=f"{prefix}-download-pdf-file"),
                            dbc.Button([DashIconify(icon="carbon:document-pdf", className="me-2"), "🖨️ 최종 PDF 생성 및 다운로드"], 
                                       id=f"{prefix}-btn-download-pdf", color="danger", className="w-100 fw-bold py-2 shadow-sm"),
                            html.Div(id=f"{prefix}-generate-message", className="mt-3 text-center")
                        ])
                    ], className="border-0 shadow-sm rounded-4 h-100")
                ], xs=12, lg=4),
                
                # 라이브 미리보기
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("2. A4 라이브 미리보기", className="fw-bold mb-0")),
                        dbc.CardBody([
                            html.Div(id=f"{prefix}-live-preview-container") 
                        ], className="bg-light p-0 rounded-bottom-4 overflow-hidden") 
                    ], className="border-0 shadow-sm rounded-4 h-100")
                ], xs=12, lg=8)
            ])
        ])
    ])


def create_report_view_layout():
    # 🚀 함수 내부(Local)에서 import를 수행하여 순환 참조를 회피합니다!
    from app.pages.report.qc_report import get_qc_report_layout
    from app.pages.report.clinical_report import get_clinical_report_layout

    return html.Div([
        # 페이지 공통 헤더
        html.Div([
            html.Div([
                html.H2([DashIconify(icon="carbon:document-report", className="me-2 text-dark"), "Report Management"], className="fw-bold text-dark"),
                html.P("QC 및 임상 보고서 양식을 설정하고 PDF로 발행합니다.", className="text-muted mt-1 mb-0")
            ])
        ], className="page-title-header mb-4"),

        # 🚀 탭으로 모듈화된 레이아웃 연동
        dbc.Tabs(id="report-tabs", active_tab="QC Report", children=[
            dbc.Tab(label="🔬 QC Report", tab_id="QC Report", children=[
                html.Div(get_qc_report_layout(), className="mt-4")
            ]),
            dbc.Tab(label="📋 Clinical Report", tab_id="Clinical Report", children=[
                html.Div(get_clinical_report_layout(), className="mt-4")
            ]),
        ], className="nav-fill mb-4")
        
    ], className="pb-5", style={"padding": "20px"})


def create_report_view_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_report_view_layout)
    app = lims.get_app() 
    
    # 🚀 함수 내부(Local)에서 콜백 등록 함수를 import 합니다!
    from app.pages.report.qc_report import register_qc_callbacks
    from app.pages.report.clinical_report import register_clinical_callbacks

    register_qc_callbacks(app)
    register_clinical_callbacks(app)
    
    return app