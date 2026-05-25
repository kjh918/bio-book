import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# 🚀 중요: 모델 파일(Base)을 가져와야 테이블을 생성할 수 있습니다.
from app.models._schema import Base 

# 🟢 핵심 수정 포인트: 환경변수가 없으면 무조건 에러를 내는 대신,
# 기본값으로 "sqlite:///./lims.db"를 사용하도록 융통성을 줍니다!
DATABASE_URL = os.getenv("LIMS_DATABASE_URL", "sqlite:///./lims.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

# 🚀 테이블 생성: 데이터베이스에 테이블이 없으면 자동으로 만들어줍니다!
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()