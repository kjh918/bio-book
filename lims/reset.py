from pathlib import Path
import importlib

from app.core.database import Base, engine


def import_all_models():
    """
    objects.py / process.py 안의 SQLAlchemy model을 import해서
    Base.metadata에 테이블을 등록합니다.
    """

    modules = [
        "app.schema.objects",
        "app.schema.process",
    ]

    for module_name in modules:
        try:
            print(f"[IMPORT] {module_name}")
            importlib.import_module(module_name)
        except ImportError as e:
            print(f"[WARN] {module_name} import 실패: {e}")


def reset_db():
    """
    SQLite DB 파일을 물리적으로 삭제하고,
    현재 schema 기준으로 DB를 다시 생성합니다.
    """

    import_all_models()

    db_path = engine.url.database

    if not db_path:
        raise RuntimeError("SQLite DB path를 찾을 수 없습니다.")

    db_file = Path(db_path).resolve()

    print(f"[INFO] DB path: {db_file}")

    if db_file.exists():
        print(f"[DELETE] 기존 DB 삭제: {db_file}")
        db_file.unlink()
    else:
        print("[INFO] 기존 DB 파일 없음")

    print("[INFO] 등록된 테이블:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")

    print("[CREATE] 테이블 생성 시작")
    Base.metadata.create_all(bind=engine)

    print("[DONE] DB 재세팅 완료")


if __name__ == "__main__":
    reset_db()