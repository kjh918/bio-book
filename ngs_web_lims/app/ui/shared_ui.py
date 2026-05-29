import dash_bootstrap_components as dbc
from dash import html
from dash_iconify import DashIconify
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# 🚀 1. 사이드바: 너비를 5rem(80px)으로 대폭 줄여 아이콘 전용 얇은 바(Bar)로 변경
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": "55px", # 네비게이션바 높이
    "left": 0,
    "bottom": 0,
    "width": "5rem", 
    "padding": "1rem 0",
    "backgroundColor": "#ffffff",
    "borderRight": "1px solid #e2e8f0",
    "zIndex": 1020,
    "display": "flex",
    "flexDirection": "column",
    "alignItems": "center",
    "boxShadow": "2px 0 8px rgba(0,0,0,0.02)"
}

# 🚀 2. 메인 컨텐츠: 사이드바가 줄어든 만큼 화면을 넓게 씁니다.
CONTENT_STYLE = {
    "marginLeft": "6.5rem",    # 사이드바(5rem)에서 1.5rem 띄움
    "marginTop": "75px",       # 상단바(55px)에서 20px 띄움
    "marginRight": "1.5rem",   # 오른쪽 화면 끝에서 띄움
    "marginBottom": "1.5rem",  # 아래쪽 화면 끝에서 띄움
    "padding": "2rem",
    "backgroundColor": "#ffffff", # 안쪽 페이지 배경은 깨끗한 흰색
    "borderRadius": "16px",    # 모서리를 부드럽게 둥글게
    "boxShadow": "0 10px 30px rgba(0, 0, 0, 0.08)", # 🚀 붕 떠보이는 짙은 그림자 효과
    "border": "1px solid #e2e8f0", # 미세한 윤곽선
    "minHeight": "calc(100vh - 100px)"
}

def create_navbar():
    return dbc.Navbar(
        dbc.Container([
            # 왼쪽: 로고 (얇아진 사이드바 너비에 맞게 조정)
            html.A(
                dbc.Row([
                    dbc.Col(DashIconify(icon="carbon:dna", width=26, color="#0d6efd")),
                    dbc.Col(dbc.NavbarBrand("LIMS", className="ms-2 fw-bold text-dark", style={"fontSize": "1.1rem"})),
                ], align="center", className="g-0"),
                href="/",
                style={"textDecoration": "none", "marginRight": "3rem"},
            ),
            
            # 🚀 중앙: 기존 사이드바에 있던 텍스트 메뉴들을 상단 드롭다운으로 전면 이동
            dbc.Nav([
                dbc.DropdownMenu(
                    label=html.Span([DashIconify(icon="carbon:dashboard", className="me-2", style={"verticalAlign": "middle"}), "OVERVIEW"], className="d-flex align-items-center"),
                    toggle_class_name="text-dark fw-bold px-3 border-0 bg-transparent d-flex align-items-center",
                    children=[
                        dbc.DropdownMenuItem("Dashboard", href="/", external_link=True),
                        dbc.DropdownMenuItem("Project View", href="/pro/", external_link=True),
                    ],
                    nav=True, in_navbar=True,
                ),
                dbc.DropdownMenu(
                    label=html.Span([DashIconify(icon="carbon:flow", className="me-2", style={"verticalAlign": "middle"}), "WORKFLOW"], className="d-flex align-items-center"),
                    toggle_class_name="text-dark fw-bold px-3 border-0 bg-transparent d-flex align-items-center",
                    children=[
                        dbc.DropdownMenuItem("Registration", href="/reg/", external_link=True),
                        dbc.DropdownMenuItem("Kanban Workflow", href="/kanban/", external_link=True),
                        dbc.DropdownMenuItem("QC Report", href="/report/", external_link=True),
                        dbc.DropdownMenuItem("Data Registry", href="/data_reg/", external_link=True),
                        dbc.DropdownMenuItem("AI Chatbot", href="/chatbot/", external_link=True),
                    ],
                    nav=True, in_navbar=True,
                ),
                dbc.DropdownMenu(
                    label=html.Span([DashIconify(icon="carbon:finance", className="me-2", style={"verticalAlign": "middle"}), "MANAGEMENT"], className="d-flex align-items-center"),
                    toggle_class_name="text-dark fw-bold px-3 border-0 bg-transparent d-flex align-items-center",
                    children=[
                        dbc.DropdownMenuItem("Billing", href="/biling/", external_link=True),
                    ],
                    nav=True, in_navbar=True,
                ),
            ], className="me-auto d-flex align-items-center", navbar=True, style={"fontSize": "0.85rem", "height": "55px"}),
            
            dbc.Nav([
                dbc.NavItem(
                    html.Div([
                        DashIconify(icon="carbon:notification", width=20, className="me-3 text-secondary", style={"cursor": "pointer"}),
                        html.Div("UA", className="rounded-circle d-flex justify-content-center align-items-center fw-bold text-primary shadow-sm", 
                                 style={"width": "32px", "height": "32px", "backgroundColor": "#e6f0ff", "fontSize": "0.8rem", "cursor": "pointer"})
                    ], className="d-flex align-items-center ms-auto h-100")
                )
            ], className="ms-auto", navbar=True),
        ], fluid=True),
        
        color="white",  
        className="shadow-sm border-bottom",
        style={"position": "fixed", "top": 0, "left": 0, "right": 0, "height": "55px", "zIndex": 1030, "padding": "0 20px"}
    )

def create_sidebar():
    nav_item_style = {
        "display": "flex", "justifyContent": "center", "alignItems": "center", 
        "padding": "12px", "borderRadius": "10px", "marginBottom": "12px", 
        "color": "#64748b", "transition": "0.2s"
    }
    
    return html.Div([
        # 🚀 에러 수정 완료: dbc.NavLink 대신 내부 html.Div에 title(툴팁) 속성 적용
        dbc.Nav([
            dbc.NavLink(html.Div(DashIconify(icon="carbon:dashboard", width=22), title="Dashboard"), href="/", active="exact", external_link=True, style=nav_item_style, className="side-nav-icon"),
            dbc.NavLink(html.Div(DashIconify(icon="carbon:flow", width=22), title="Kanban Workflow"), href="/kanban/", active="exact", external_link=True, style=nav_item_style, className="side-nav-icon"),
            dbc.NavLink(html.Div(DashIconify(icon="carbon:report", width=22), title="QC Report"), href="/report/", active="exact", external_link=True, style=nav_item_style, className="side-nav-icon"),
            dbc.NavLink(html.Div(DashIconify(icon="carbon:cloud-download", width=22), title="Data Registry"), href="/data_reg/", active="exact", external_link=True, style=nav_item_style, className="side-nav-icon"),
            dbc.NavLink(html.Div(DashIconify(icon="carbon:chat-bot", width=22), title="AI Chatbot"), href="/chatbot/", active="exact", external_link=True, style=nav_item_style, className="side-nav-icon"),
        ], vertical=True, pills=True, className="w-100 px-2 mt-3"),
        
        # 하단 설정 아이콘
        html.Div([
            dbc.NavLink(html.Div(DashIconify(icon="carbon:settings", width=22), title="Settings"), href="#", style=nav_item_style)
        ], style={"position": "absolute", "bottom": "10px", "width": "100%", "padding": "0 8px"})
        
    ], style=SIDEBAR_STYLE, className="side-navbar")

def create_project_summary_card(order_obj, current_sample_count=None):
    if order_obj is None:
        raise ValueError("order_obj cannot be None")

    sample_count = current_sample_count if current_sample_count is not None else len(order_obj.samples)
    revenue = (order_obj.sales_unit_price or 0) * sample_count

    all_logs = []
    for s in order_obj.samples:
        if hasattr(s, 'logs') and s.logs:
            for log in s.logs:
                all_logs.append({
                    "sample_name": s.sample_name, "action": log.action_type,
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
            elif "변경" in log["action"]: badge_color = "dark" 
            elif "특이사항" in log["action"]: badge_color = "warning text-dark"

            log_items.append(
                html.Div([
                    html.Span(f"[{time_str}]", className="text-muted me-2", style={"fontFamily": "monospace", "fontSize": "0.75rem"}),
                    html.Strong(f"{log['sample_name']}", className="me-2 text-dark", style={"width": "110px", "display": "inline-block", "fontSize": "0.8rem"}),
                    dbc.Badge(log['action'], color=badge_color, className="me-2 rounded-pill", style={"fontSize": "0.7rem"}), 
                    html.Span(f"{log['details']}", className="text-secondary fw-bold", style={"fontSize": "0.75rem", "whiteSpace": "pre-wrap"})
                ], className="border-bottom py-2 d-flex align-items-center")
            )

    log_container = html.Div(log_items, style={"maxHeight": "140px", "overflowY": "auto", "backgroundColor": "#f8fafc", "padding": "10px", "borderRadius": "8px", "border": "1px solid #e2e8f0"})
    note_val = getattr(order_obj, 'notes', "") or ""
    return dbc.Card([
        # 🚀 헤더 테두리 색상 강제 적용
        dbc.CardHeader(
            html.H5([DashIconify(icon="carbon:folder-open", className="me-2 text-dark"), f"Project : {order_obj.order_id}"], 
            className="mb-0 fw-bold", style={"fontSize": "1rem"}), 
            className="bg-white pt-3 pb-0",
        ),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([html.Div("🏢 의뢰 기관", className="text-muted mb-1", style={"fontSize": "0.75rem"}), html.Strong(order_obj.facility, style={"fontSize": "0.85rem"})], md=3, sm=6, className="mb-3"),
                dbc.Col([html.Div("📅 접수 일자", className="text-muted mb-1", style={"fontSize": "0.75rem"}), html.Strong(str(order_obj.reception_date), style={"fontSize": "0.85rem"})], md=3, sm=6, className="mb-3"),
                dbc.Col([html.Div("📊 대상 검체", className="text-muted mb-1", style={"fontSize": "0.75rem"}), html.Strong(f"{sample_count}건", style={"fontSize": "0.85rem"})], md=3, sm=6, className="mb-3"),
                dbc.Col([html.Div("💰 예상 매출", className="text-muted mb-1", style={"fontSize": "0.75rem"}), html.Strong(f"{revenue:,}원", className="text-dark", style={"fontSize": "0.85rem"})], md=3, sm=6, className="mb-3"),
            ]),
            html.Div("📝 특이사항 메모", className="fw-bold text-slate-700 mb-2 mt-1", style={"fontSize": "0.8rem"}),
            dbc.Textarea(
                id="order-notes-input", 
                placeholder="특이사항을 입력하세요.", 
                style={
                    "fontSize": "0.85rem", 
                    "borderRadius": "8px", 
                    "border": "1px solid #1a2a40", # 🚀 테두리 색상 명시
                    "padding": "10px",
                    "width": "100%",
                    "resize": "vertical" # 사용자가 줄바꿈을 많이 할 경우 높이를 조절할 수 있게 함
                },
                rows=3,
                className="form-control" 
            ),

            html.Div("🕒 최근 활동 로그 (최신 50건)", className="fw-bold text-slate-700 mb-2 border-top pt-2 mt-3", style={"fontSize": "0.8rem"}),
            log_container
        ], className="pb-3")
    ], className="mb-4 shadow-sm border-0 rounded-4", style={"border": "1px solid #1a2a40 !important"}) # 🚀 카드 전체 테두리 색상 강제


def apply_modern_layout(page_content):
    if page_content is None:
        raise ValueError("page_content cannot be None")
    return html.Div([
        create_navbar(),
        create_sidebar(),
        html.Div(page_content, style=CONTENT_STYLE, className="main-content") 
    ], style={"backgroundColor": "#F4F7F9", "minHeight": "100vh", "overflow": "auto"})