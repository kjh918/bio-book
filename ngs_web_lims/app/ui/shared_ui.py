import dash_bootstrap_components as dbc
from dash import html
from dash_iconify import DashIconify
from datetime import datetime, timezone, timedelta

# --- 레이아웃 스타일 설정 (중복 선언 제거 및 깔끔한 정리) ---
KST = timezone(timedelta(hours=9))

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

#CONTENT_STYLE = {
#    "marginLeft": "16rem", # 사이드바 너비만큼 메인 컨텐츠 우측으로 밀기
#    "padding": "2rem 2rem", 
#    "backgroundColor": "#F8F9FA",
#    "minHeight": "100vh"
#}
CONTENT_STYLE = {
    "marginLeft": "0",      # 🚀 0으로 변경하거나 아예 줄을 지우세요!
    "marginRight": "0",
    "padding": "2rem 1rem",
}

from dash import html
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

def create_navbar():
    return dbc.Navbar(
        dbc.Container([
            # 🚀 1. 왼쪽: 로고 및 타이틀
            html.A(
                dbc.Row([
                    dbc.Col(DashIconify(icon="carbon:dna", width=35, color="#18BC9C")),
                    dbc.Col(dbc.NavbarBrand("NGS LIMS", className="ms-2 fw-bold fs-4 text-dark")),
                ], align="center", className="g-0"),
                href="/",
                style={"textDecoration": "none"},
            ),
            
            # 🚀 2. 오른쪽: 토글 버튼
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            
            # 🚀 3. 메뉴 리스트
            dbc.Collapse(
                dbc.Nav([
                    dbc.DropdownMenu(
                        label="📊 OVERVIEW",
                        toggle_class_name="text-dark fw-bold",
                        children=[
                            # 🎨 하위 항목 통일: 아이콘과 텍스트 모두 text-secondary(다크그레이) 및 text-dark(블랙)로 통일
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:dashboard", className="me-2 text-secondary"), 
                                html.Span("Dashboard", className="text-dark")
                            ], active="exact", external_link=True, href="/", className="py-2"),
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:data-table", className="me-2 text-secondary"), 
                                html.Span("Project View", className="text-dark")
                            ], active="exact", external_link=True, href="/pro/", className="py-2"),
                        ],
                        nav=True, in_navbar=True, className="me-2"
                    ),
                    
                    dbc.DropdownMenu(
                        label="🧪 WORKFLOW",
                        toggle_class_name="text-dark fw-bold",
                        children=[
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:document-add", className="me-2 text-secondary"), 
                                html.Span("Registration", className="text-dark")
                            ], active="exact", external_link=True, href="/reg/", className="py-2"),
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:report", className="me-2 text-secondary"), 
                                html.Span("QC Report", className="text-dark")
                            ], active="exact", external_link=True, href="/report/", className="py-2"),
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:document-add", className="me-2 text-secondary"), 
                                html.Span("Data Registration", className="text-dark")
                            ], active="exact", external_link=True, href="/data_reg/", className="py-2"),
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:analytics", className="me-2 text-secondary"), 
                                html.Span("Analysis", className="text-dark")
                            ], active="exact", external_link=True, href="/analysis/", className="py-2"),
                        ],
                        nav=True, in_navbar=True, className="me-2"
                    ),

                    dbc.DropdownMenu(
                        label="💼 MANAGEMENT",
                        toggle_class_name="text-dark fw-bold",
                        children=[
                            dbc.DropdownMenuItem([
                                DashIconify(icon="carbon:finance", className="me-2 text-secondary"), 
                                html.Span("매입/매출", className="text-dark")
                            ], active="exact", external_link=True, href="/biling/", className="py-2"),
                        ],
                        nav=True, in_navbar=True, className="me-2"
                    ),
                    
                    dbc.NavItem(
                        html.Div([
                            DashIconify(icon="carbon:user-avatar-filled-alt", width=25, className="me-2 text-secondary"),
                            html.Span("Admin", className="text-dark fw-bold small")
                        ], className="d-flex align-items-center ms-4 h-100")
                    )
                ], className="ms-auto", navbar=True),
                id="navbar-collapse",
                is_open=False,
                navbar=True,
            ),
        ], fluid=True),
        
        color="white",  
        className="mb-4 shadow-sm border-bottom navbar-light",
        style={"padding": "10px 20px"}
    )

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
            
            dbc.NavLink([DashIconify(icon="carbon:finance", width=20, className="me-2"), "Workflow"], 
                        href="/kanban/", active="exact", external_link=True, className="text-white mb-1 rounded hover-bg-primary ms-2"),
            
            dbc.NavLink([DashIconify(icon="carbon:report", width=20, className="me-2l"), "QC Report"], 
                        href="/report/", active="exact", external_link=True, className="text-white mb-3 rounded hover-bg-primary ms-2"),

            # ------------------------------------------------
            # 📌 GROUP 3: MANAGEMENT (관리 및 정산)
            # ------------------------------------------------
            # 🚀 콤마(,) 추가, 오타(mall) 수정, text-white 적용, 마진 축소(mt-3, mb-1)
            html.Div("💼 MANAGEMENT", className="text-white small fw-bold mt-3 mb-1 ms-2 letter-spacing-1"),
            
            dbc.NavLink([DashIconify(icon="carbon:finance", width=20, className="me-2"), "매입/매출"], 
                        href="/biling/", active="exact", external_link=True, className="text-white mb-1 rounded hover-bg-primary ms-2"),
            
            
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

def create_project_summary_card(order_obj, current_sample_count=None):
    sample_count = current_sample_count if current_sample_count is not None else len(order_obj.samples)
    revenue = (order_obj.sales_unit_price or 0) * sample_count

    all_logs = []
    for s in order_obj.samples:
        if hasattr(s, 'logs') and s.logs:
            for log in s.logs:
                all_logs.append({
                    "sample_name": s.sample_name, "action": log.action_type,
                    "prev": log.previous_state or "-", "new": log.new_state or "-",
                    "details": log.details or "-", "time": log.created_at
                })
    
    all_logs.sort(key=lambda x: x["time"] if x["time"] else datetime.min, reverse=True)

    log_items = []
    if not all_logs:
        log_items.append(html.Div("기록된 활동 로그가 없습니다.", className="text-muted small p-2 text-center"))
    else:
        for log in all_logs[:50]: 
            time_str = log["time"].strftime("%m/%d %H:%M") if log["time"] else ""
            badge_color = "secondary"
            if "제외" in log["action"] or "실패" in log["action"]: badge_color = "danger"
            elif "완료" in log["action"]: badge_color = "success"
            elif "변경" in log["action"]: badge_color = "primary"
            elif "특이사항" in log["action"]: badge_color = "warning text-dark"

            log_items.append(
                html.Div([
                    html.Span(f"[{time_str}]", className="text-muted small me-2", style={"fontFamily": "monospace"}),
                    html.Strong(f"{log['sample_name']}", className="me-2 text-dark", style={"width": "110px", "display": "inline-block", "fontSize": "0.85rem"}),
                    dbc.Badge(log['action'], color=badge_color, className="me-2"),
                    html.Span(f" {log['details']}", className="text-info small fw-bold")
                ], className="border-bottom py-1 d-flex align-items-center")
            )

    log_container = html.Div(log_items, style={"maxHeight": "140px", "overflowY": "auto", "backgroundColor": "#f8f9fa", "padding": "8px", "borderRadius": "5px", "border": "1px solid #dee2e6"})

    return dbc.Card([
        dbc.CardHeader(html.H5(f"📂 Projcet : {order_obj.order_id}", className="mb-0 fw-bold text-primary")),
        dbc.CardBody([
            # 🚀 글씨가 겹치지 않도록 반응형(md=3, sm=6) 컬럼 적용
            dbc.Row([
                dbc.Col([html.Small("🏢 의뢰 기관", className="text-muted d-block"), html.Strong(order_obj.facility)], md=3, sm=6, className="mb-2"),
                dbc.Col([html.Small("📅 접수 일자", className="text-muted d-block"), html.Strong(str(order_obj.reception_date))], md=3, sm=6, className="mb-2"),
                dbc.Col([html.Small("📊 대상 검체", className="text-muted d-block"), html.Strong(f"{sample_count}건")], md=3, sm=6, className="mb-2"),
                dbc.Col([html.Small("💰 예상 매출", className="text-muted d-block"), html.Strong(f"{revenue:,}원", className="text-success")], md=3, sm=6, className="mb-2"),
            ], className="mb-1"),
            
            html.H6(f"🕒 최근 활동 로그 (최신 50건)", className="fw-bold text-secondary mb-2 border-top pt-2"),
            log_container
            
        ], className="pb-3")
    ], className="mb-3 shadow-sm border-primary", style={"borderWidth": "2px"})


# [2] 전체 레이아웃 래퍼
def apply_modern_layout(page_content):
    return html.Div([
        create_navbar(),
        html.Div(page_content, style=CONTENT_STYLE)
    ])
