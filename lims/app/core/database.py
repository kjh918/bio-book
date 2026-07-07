import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 수정: 현재 프로젝트 기준 Base는 objects.py에서 관리
from app.schema.objects import Base

DATABASE_URL = os.getenv("LIMS_DATABASE_URL", "sqlite:///./lims.db")

connect_args = {
    "check_same_thread": False
} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# 수정: import 시점 자동 create_all 제거
# Base.metadata.create_all(bind=engine)


def init_db():
    """
    현재 등록된 SQLAlchemy model 기준으로 테이블 생성.
    서버 시작 시 필요하면 명시적으로 호출.
    """
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    개발용: 현재 등록된 테이블 삭제.
    SQLite 파일 삭제 방식이 더 깔끔하지만,
    필요 시 metadata 기준 drop 가능.
    """
    Base.metadata.drop_all(bind=engine)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()