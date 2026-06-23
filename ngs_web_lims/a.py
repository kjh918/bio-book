import sqlite3

# ⚠️ lims.db 파일이 있는 정확한 경로를 입력하세요. (보통 최상단에 있습니다)
db_path = "lims.db" 

def migrate_samples():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # SQLite에서 샘플 테이블에 새 컬럼 추가
        cursor.execute("ALTER TABLE samples ADD COLUMN nucleic_acid_type VARCHAR;")
        print("✅ 'nucleic_acid_type' 컬럼 추가 성공!")
    except sqlite3.OperationalError as e:
        print(f"⚠️ 스킵됨 또는 에러: {str(e)}")
    
    conn.commit()
    conn.close()
    print("🚀 Samples 테이블 마이그레이션 완료! 서버를 켜보세요.")

if __name__ == "__main__":
    migrate_samples()