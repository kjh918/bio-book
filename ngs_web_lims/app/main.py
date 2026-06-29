from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.wsgi import WSGIMiddleware

from app.pages.project_view import create_project_view_app
from app.pages.registration import create_registration_app
from app.pages.biling_dashboard import create_billing_dashboard_app 
from app.pages.kanban import create_kanban_app 
from app.pages.data_registration import create_data_registry_app 
from app.pages.chatbot import create_chatbot_app
from app.pages.batch_modify import create_batch_modify_app
from app.pages.master_table import create_master_app

from app.pages.analysis.base import create_analysis_dashboard_app
from app.pages.analysis.check_results import create_analysis_results_app
from app.pages.report.base import create_report_view_app
#from app.pages.report.analysis.clinical_report import create_tso_clinical_report_app

from app.core.database import engine
from app.models._schema import Base

# 🚀 [추가] 분리된 순수 API 라우터 모듈 불러오기
from app.api import analysis_api

from app.api.webhook import webhook_api

# [MODIFIED] 전역 실행 대신 Lifespan을 통한 안전한 DB 초기화 및 자원 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ❌ 무조건 다 날려버리는 코드는 영구 봉인!
    # Base.metadata.drop_all(bind=engine)
    
    print("🚀 System Starting: Initializing Database...")
    try:
        # 🟢 안전한 테이블 생성 코드 (기존 데이터 유지, 없는 테이블만 생성)
        Base.metadata.create_all(bind=engine)
        print("✅ DB 체크 완료: 누락된 테이블이 있다면 안전하게 생성되었습니다.")
    except Exception as e:
        print(f"❌ DB 연결/초기화 중 치명적 오류 발생: {str(e)}")
        raise e  # DB가 없으면 서버 구동을 중단하는 것이 안전합니다.
        
    yield
    
    print("🛑 System Shutting Down: Releasing Resources...")
    # 필요 시 DB connection pool 해제 로직 추가

app = FastAPI(title="NGS LIMS System", lifespan=lifespan)
# ==========================================
# 1. 서브 Dash 앱 마운트 (딕셔너리 기반으로 반복 제거 및 관리 용이성 확보)
# ==========================================
dash_apps = {
    "/reg": create_registration_app,
    "/data_reg": create_data_registry_app,
    "/pro": create_project_view_app,
    "/report": create_report_view_app,
    "/kanban": create_kanban_app,
    "/analysis": create_analysis_dashboard_app,
    "/modify": create_batch_modify_app,
    "/chatbot": create_chatbot_app,
    "/master": create_master_app,
    "/check_results": create_analysis_results_app,
    # 필요 시 "/billing": create_billing_dashboard_app 추가
}

for path, app_factory in dash_apps.items():
    dash_app_instance = app_factory(requests_pathname_prefix=f"{path}/")
    app.mount(path, WSGIMiddleware(dash_app_instance.server))

# ==========================================
# 2. 루트 접속 시 자동 이동 (Redirect)
# ==========================================
@app.get("/", include_in_schema=False)
def read_root():
    # 사용자가 localhost:8000 으로만 접속해도 알아서 칸반 보드로 넘겨줍니다.
    return RedirectResponse(url="/kanban")

# ==========================================
# 3. Native FastAPI API Endpoints (기계 간 통신용)
# ==========================================
# 🚀 분석 서버에서 LIMS로 데이터를 쏠 때 사용할 API 라우터 등록
# 이렇게 등록하면 자동으로 /api/v1/analysis/result 주소가 활성화됩니다.
app.include_router(analysis_api.router, prefix="/api/v1")
# 🌟 [추가] 39번 서버가 결과를 던질 Webhook 라우터 등록!
# webhook_api 안에 이미 '/api/analysis/complete' 경로가 선언되어 있으므로 그냥 추가만 하면 됩니다.
app.include_router(webhook_api)