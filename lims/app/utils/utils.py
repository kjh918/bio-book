# app/dash_apps/utils.py
import dash_bootstrap_components as dbc
from contextlib import contextmanager
from app.core.database import SessionLocal

# 1. 공통 Alert 생성기
def create_alert(success: bool, message: str, count: int = 0):
    if success:
        return dbc.Alert(f"✅ {message} ({count}건 반영)", color="success", duration=3000)
    return dbc.Alert(f"❌ 실패: {message}", color="danger")

# 2. 안전한 DB 세션 관리자 (Context Manager)
@contextmanager
def get_safe_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit() # 에러가 없으면 자동 커밋
    except Exception as e:
        db.rollback() # 에러 시 자동 롤백
        raise e       # 에러를 밖으로 던져서 콜백이 알 수 있게 함
    finally:
        db.close()    # 무조건 세션 닫기