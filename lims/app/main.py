from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.wsgi import WSGIMiddleware

from app.core.database import engine
from app.schema.objects import Base
from app.pages.project import create_project_app
from app.pages.sample  import create_sample_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting: Initializing DB…")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ DB 준비 완료")
    except Exception as e:
        print(f"❌ DB 초기화 오류: {e}")
        raise
    yield
    print("🛑 Shutting down…")


app = FastAPI(title="NGS LIMS", lifespan=lifespan)

# ── Dash 앱 마운트 ────────────────────────────────────
dash_apps = {
    "/project": create_project_app,
    "/sample":  create_sample_app,
}

for path, factory in dash_apps.items():
    instance = factory(requests_pathname_prefix=f"{path}/")
    app.mount(path, WSGIMiddleware(instance.server))

# ── 루트 리다이렉트 ──────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/project/")