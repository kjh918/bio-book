import dash_bootstrap_components as dbc

def create_navbar():
    return dbc.NavbarSimple(
        children=[
            # [Status Dashboard] 루트 경로로 설정
            dbc.NavItem(dbc.NavLink("📊 Status Dashboard", href="/", external_link=True, className="fs-5")),
            dbc.NavItem(dbc.NavLink("Registration", href="/reg/", external_link=True, className="fs-5")),
            dbc.NavItem(dbc.NavLink("📝 Excel Tracker", href="/excel/", external_link=True, className="fs-5")),
            
        ],
        brand="🧬 NGS LIMS MASTER CONTROL",
        brand_href="/",  # 브랜드 로고 클릭 시 루프 방지를 위해 루트로 설정
        color="primary",
        dark=True,
        className="mb-4 shadow-sm",
        fluid=True 
    )