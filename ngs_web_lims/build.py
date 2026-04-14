import os
import json
import yaml
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 경로 계산
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "columns.yaml"

# 환경변수 설정 (없을 경우 기본값)
if not os.getenv("LIMS_DATABASE_URL"):
    os.environ["LIMS_DATABASE_URL"] = f"sqlite:///{BASE_DIR}/lims_test.db"

from app.core.database import SessionLocal, engine
from app.models.schema import Base, Sample, NGSTracking

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def insert_all_dummy_data():
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 1. 시료 상태 대시보드용 (Old Schema)
        if not db.query(Sample).first():
            samples = [
                Sample(sample_id="S-26001", project_id="PRJ-26-01", status="COMPLETED", qc_result="PASS", yield_gb=15.2),
                Sample(sample_id="S-26002", project_id="PRJ-26-01", status="EXPERIMENTING", qc_result="PENDING", yield_gb=0.0)
            ]
            db.add_all(samples)
            print("✅ Samples 데이터 삽입 완료")

        # 2. 실무형 엑셀 트래킹용 (New Form - 44개 컬럼 대응)
        if not db.query(NGSTracking).first():
            config = load_config()
            mapping = config.get('facility_mapping', {})
            today_str = datetime.now().strftime("%y%m%d")

            # --- 샘플 데이터 생성기 ---
            def create_row(idx, sample_name, status, days_delta):
                # 1. 입력 데이터 (User Input)
                order_id = "GCX-C01-260408"
                fac_code = "C01"
                row = {
                    "GMC/GCX": "GCX",
                    "Order Facility": fac_code,
                    "Reception Date": datetime.now().strftime("%Y-%m-%d"),
                    "Order ID": order_id,
                    "Order No": f"{idx:02d}",
                    "Sample Name": sample_name,
                    "Cancer Type": "LC",
                    "Specimen": "ORG",
                    "추출 진행": "O",
                    "Sample Type": "DNA",
                    "Analysis Type": "WES",
                    "Depth/Output": "100X",
                    "Conc.(ng/uL)": 45.5,
                    "Sample QC": "PASS",
                    "검사진행 여부": "O",
                    "진행사항": status,
                    "의뢰사": mapping.get(fac_code, {}).get('facility', ""),
                    "의뢰인": mapping.get(fac_code, {}).get('team', ""),
                    "매출 단가": 450000,
                    "매입 단가": 300000,
                    "Dead Line": (datetime.now() + timedelta(days=days_delta)).strftime("%Y-%m-%d"),
                    "매출": "Y", "매입": "Y", "견적서 발행": "Y"
                }
                
                # 2. 생성 데이터 (System Generated)
                reg_id = f"ACC-{today_str}-{idx:03d}"
                row["Registration ID"] = reg_id
                row["Sample ID"] = f"{order_id}_{sample_name}"
                row["SEQ ID"] = f"{reg_id}_R1"
                
                return row

            # 데이터 3종 세트 (완료건, 임박건, 대기건)
            data_list = [
                create_row(1, "Normal-01", "데이터 전달받음", 10),
                create_row(2, "Tumor-01", "시퀀싱 진행 중", 2), # TAT 임박
                create_row(3, "Cell-01", "라이브러리 제작", 15)
            ]

            records = [
                NGSTracking(
                    registration_id=r["Registration ID"],
                    order_id=r["Order ID"],
                    sample_name=r["Sample Name"],
                    seq_id=r["SEQ ID"],
                    excel_data=r # 전체 JSON 저장
                ) for r in data_list
            ]
            
            db.add_all(records)
            print("✅ NGSTracking(44개 컬럼) 데이터 삽입 완료")

        db.commit()
        print("🎉 모든 더미 데이터 셋업이 완료되었습니다.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    insert_all_dummy_data()