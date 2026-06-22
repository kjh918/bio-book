import sqlite3
from app.core.database import DATABASE_URL

# DATABASE_URL이 "sqlite:///./lims.db" 형태라고 가정합니다.
db_path = DATABASE_URL.replace("sqlite:///", "")

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 추가할 컬럼 목록 (Analysis 테이블)
    new_columns = [
        ("analysis_status", "VARCHAR DEFAULT '대기중'"),
        ("analyst", "VARCHAR"),
        ("pathologist_name", "VARCHAR"),
        ("pipeline", "VARCHAR"),
        ("pipeline_version", "VARCHAR"),
        ("raw_data_pathway", "VARCHAR"),
        ("work_dir_pathway", "VARCHAR"),
        ("analysis_run_start_date", "DATE"),
        ("analysis_run_end_date", "DATE"),
        ("standard_report_date_01", "DATE"),
        ("advanced_report_date_01", "DATE"),
        ("analysis_results", "JSON")
    ]
    
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE analysis ADD COLUMN {col_name} {col_type}")
            print(f"✅ 컬럼 추가 완료: {col_name}")
        except sqlite3.OperationalError:
            print(f"⚠️ 이미 존재하는 컬럼입니다: {col_name}")
    
    conn.commit()
    conn.close()
    print("🚀 마이그레이션 종료.")

if __name__ == "__main__":
    migrate()