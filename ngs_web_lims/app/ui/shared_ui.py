import dash_bootstrap_components as dbc
from dash import html
from dash_iconify import DashIconify

# --- 레이아웃 스타일 설정 (중복 선언 제거 및 깔끔한 정리) ---
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "16rem",
    "padding": "2rem 1rem",
    "backgroundColor": "#2C3E50",
    "color": "white",
    "boxShadow": "2px 0 5px rgba(0,0,0,0.1)",
    "zIndex": 1020,
    "overflowY": "auto"
}

CONTENT_STYLE = {
    "marginLeft": "16rem", # 사이드바 너비만큼 메인 컨텐츠 우측으로 밀기
    "padding": "2rem 2rem", 
    "backgroundColor": "#F8F9FA",
    "minHeight": "100vh"
}

# [1] 좌측 사이드바 (계층형 메뉴 적용)
def create_sidebar():
    return html.Div([
        # 사이드바 헤더 (로고 및 타이틀)
        html.Div([
            DashIconify(icon="carbon:dna", width=40, color="#18BC9C", className="me-2"),
            html.H4("NGS LIMS", className="fw-bold m-0")
        ], className="d-flex align-items-center mb-4 pb-3 border-bottom border-secondary"),
        
        # 계층형 메뉴 시작
        dbc.Nav([
            
            # ------------------------------------------------
            # 📌 GROUP 1: OVERVIEW (오버뷰)
            # ------------------------------------------------
            # 🚀 콤마(,) 추가 및 text-white 적용, 마진 축소(mt-2, mb-1)
            html.Div("📊 OVERVIEW", className="text-white small fw-bold mt-2 mb-1 ms-2 letter-spacing-1"),
            
            dbc.NavLink([DashIconify(icon="carbon:dashboard", width=20, className="me-2"), "Dashboard"], 
                        href="/", active="exact", external_link=True, className="text-white mb-1 rounded hover-bg-primary ms-2"),
            
            dbc.NavLink([DashIconify(icon="carbon:data-table", width=20, className="me-2"), "Project View"], 
                        href="/pro/", active="exact", external_link=True, className="text-white mb-3 rounded hover-bg-primary ms-2"),
            
            # ------------------------------------------------
            # 📌 GROUP 2: WORKFLOW (실험/업무 단계)
            # ------------------------------------------------
            # 🚀 text-muted 제거, text-white 적용, 마진 축소(mt-3, mb-1)
            html.Div("🧪 WORKFLOW", className="text-white small fw-bold mt-3 mb-1 ms-2 letter-spacing-1"),
            
            dbc.NavLink([DashIconify(icon="carbon:document-add", width=20, className="me-2"), "Registration"], 
                        href="/reg/", active="exact", external_link=True, className="text-white mb-1 rounded hover-bg-primary ms-2"),
            
            dbc.NavLink([DashIconify(icon="carbon:report", width=20, className="me-2"), "QC Report"], 
                        href="/report/", active="exact", external_link=True, className="text-white mb-3 rounded hover-bg-primary ms-2"),

            # ------------------------------------------------
            # 📌 GROUP 3: MANAGEMENT (관리 및 정산)
            # ------------------------------------------------
            # 🚀 콤마(,) 추가, 오타(mall) 수정, text-white 적용, 마진 축소(mt-3, mb-1)
            html.Div("💼 MANAGEMENT", className="text-white small fw-bold mt-3 mb-1 ms-2 letter-spacing-1"),
            
            dbc.NavLink([DashIconify(icon="carbon:finance", width=20, className="me-2"), "매입/매출"], 
                        href="/biling/", active="exact", external_link=True, className="text-white mb-1 rounded hover-bg-primary ms-2"),
            
            dbc.NavLink([DashIconify(icon="carbon:database", width=20, className="me-2"), "Raw DB Excel"], 
                        href="/excel/", active="exact", external_link=True, className="text-white mb-3 rounded hover-bg-primary ms-2"),
            
        ], vertical=True, pills=True),

        # 하단 유저 정보 (웹앱 느낌을 주는 디테일)
        html.Div([
            html.Hr(className="border-secondary"),
            html.Div([
                DashIconify(icon="carbon:user-avatar-filled-alt", width=30, className="me-2 text-muted"),
                html.Span("Admin User", className="small")
            ], className="d-flex align-items-center")
        ], style={"position": "absolute", "bottom": "20px", "width": "14rem"})
        
    ], style=SIDEBAR_STYLE)

# [2] 전체 레이아웃 래퍼
def apply_modern_layout(page_content):
    return html.Div([
        create_sidebar(),
        html.Div(page_content, style=CONTENT_STYLE)
    ])