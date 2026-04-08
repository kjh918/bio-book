from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware
# 반드시 본인의 파일명/함수명에 맞게 임포트 확인
from app.dash_apps.main_dashboard import create_summary_dashboard
from app.dash_apps.excel_tracker import create_excel_tracker_app
from app.dash_apps.registration import create_registration_app

app = FastAPI()

# 1. 상세 앱들을 먼저 마운트 (이들은 루트보다 구체적인 경로를 가짐)
excel_app = create_excel_tracker_app(requests_pathname_prefix="/excel/")
app.mount("/excel", WSGIMiddleware(excel_app.server))

reg_app = create_registration_app(requests_pathname_prefix="/reg/")
app.mount("/reg", WSGIMiddleware(reg_app.server))

main_dash = create_summary_dashboard(requests_pathname_prefix="/")
app.mount("/", WSGIMiddleware(main_dash.server))