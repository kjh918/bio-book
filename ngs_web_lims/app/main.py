from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.wsgi import WSGIMiddleware

from app.pages.project_view import create_project_view_app
from app.pages.registration import create_registration_app
from app.pages.analysis import create_analysis_app
from app.pages.report import create_report_view_app
from app.pages.biling_dashboard import create_billing_dashboard_app 
from app.pages.kanban import create_kanban_app 
from app.pages.data_registration import create_data_registry_app 
from app.pages.chatbot import create_chatbot_app

from app.pages.batch_modify import create_batch_modify_app


from app.core.database import engine
from app.models._schema import Base

# ❌ 무조건 다 날려버리는 코드는 영구 봉인! (절대 주석 해제 금지)
# Base.metadata.drop_all(bind=engine)

# 🟢 안전한 테이블 생성 코드 (기존 데이터 유지, 없는 테이블만 생성)
Base.metadata.create_all(bind=engine)
print("✅ DB 체크 완료: 누락된 테이블이 있다면 안전하게 생성되었습니다.")

app = FastAPI(title="NGS LIMS System")

# ==========================================
# 1. 서브 Dash 앱 마운트
# ==========================================
reg_app = create_registration_app(requests_pathname_prefix="/reg/")
app.mount("/reg", WSGIMiddleware(reg_app.server))

data_reg_app = create_data_registry_app(requests_pathname_prefix="/data_reg/")
app.mount("/data_reg", WSGIMiddleware(data_reg_app.server))

pro_app = create_project_view_app(requests_pathname_prefix="/pro/")
app.mount("/pro", WSGIMiddleware(pro_app.server))

report_app = create_report_view_app(requests_pathname_prefix="/report/")
app.mount("/report", WSGIMiddleware(report_app.server))

kanban_app = create_kanban_app(requests_pathname_prefix="/kanban/")
app.mount("/kanban", WSGIMiddleware(kanban_app.server))

analysis_app = create_analysis_app(requests_pathname_prefix="/analysis/")
app.mount("/analysis", WSGIMiddleware(analysis_app.server))

modify_app = create_batch_modify_app(requests_pathname_prefix="/modify/")
app.mount("/modify", WSGIMiddleware(modify_app.server))

chatbot_app = create_chatbot_app(requests_pathname_prefix="/chatbot/")
app.mount("/chatbot", WSGIMiddleware(chatbot_app.server))

# ==========================================
# 2. 루트 접속 시 자동 이동 (Redirect)
# ==========================================
@app.get("/")
def read_root():
    # 사용자가 localhost:8000 으로만 접속해도 알아서 칸반 보드로 넘겨줍니다.
    # 앱을 메모리에 두 번 올리지 않아 성능이 훨씬 좋아집니다!
    return RedirectResponse(url="/kanban")