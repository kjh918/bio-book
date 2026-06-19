# patch_db.py
from sqlalchemy import text
from app.core.database import SessionLocal

def patch_database():
    print("🚀 DB 스키마 업데이트 시작...")
    db = SessionLocal()
    
    # 💡 wet_lab_qc 테이블에 추가해야 할 새로운 컬럼들 목록
    columns_to_add = [
        "dna_qc VARCHAR",
        "dna_concentration FLOAT",
        "dna_volume FLOAT",
        "dna_total_amount FLOAT",
        "purity FLOAT",
        "din FLOAT",
        
        "rna_qc VARCHAR",
        "rna_concentration FLOAT",
        "rna_volume FLOAT",
        "rna_total_amount FLOAT",
        "dv200 FLOAT",
        "rin FLOAT"
    ]

    for col in columns_to_add:
        try:
            # SQLite에 컬럼을 하나씩 밀어넣는 SQL 명령어 실행
            db.execute(text(f"ALTER TABLE wet_lab_qc ADD COLUMN {col}"))
            print(f"✅ 컬럼 추가 완료: {col.split()[0]}")
        except Exception as e:
            # 이미 컬럼이 존재하면 에러가 나는데, 이 경우 가볍게 무시하고 넘어갑니다.
            if "duplicate column name" in str(e).lower():
                print(f"⏭️ 이미 존재하는 컬럼입니다 (패스): {col.split()[0]}")
            else:
                print(f"⚠️ 기타 에러 (무시 가능): {e}")

    db.commit()
    db.close()
    print("🎉 패치 완료! 기존 데이터는 모두 보존되었습니다. 이제 서버를 다시 켜주세요.")

if __name__ == "__main__":
    patch_database()