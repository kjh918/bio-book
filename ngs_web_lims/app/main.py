# app/main.py (수정 후)
from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware

# 중간 폴더들이 사라져서 경로가 엄청 직관적입니다!
from app.pages.dashboard import create_summary_dashboard
from app.pages.project_view import create_project_view_app
from app.pages.registration import create_registration_app
from app.pages.excel_tracker import create_excel_tracker_app
from app.pages.report import create_report_app
from app.pages.biling_dashboard import create_billing_dashboard_app 

app = FastAPI()

# 1. 상세 앱들을 먼저 마운트
excel_app = create_excel_tracker_app(requests_pathname_prefix="/excel/")
app.mount("/excel", WSGIMiddleware(excel_app.server))

reg_app = create_registration_app(requests_pathname_prefix="/reg/")
app.mount("/reg", WSGIMiddleware(reg_app.server))

pro_app = create_project_view_app(requests_pathname_prefix="/pro/")
app.mount("/pro", WSGIMiddleware(pro_app.server))

report_app = create_report_app(requests_pathname_prefix="/report/")
app.mount("/report", WSGIMiddleware(report_app.server))

biling_app = create_billing_dashboard_app(requests_pathname_prefix="/biling/")
app.mount("/biling", WSGIMiddleware(biling_app.server))

# 2. 루트 대시보드 마운트
main_dash = create_summary_dashboard(requests_pathname_prefix="/")
app.mount("/", WSGIMiddleware(main_dash.server))