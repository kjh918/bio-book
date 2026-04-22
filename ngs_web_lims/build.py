import os
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 계산
BASE_DIR = Path(__file__).resolve().parent

# 환경변수 설정 (테스트용 DB 파일 경로)
os.environ["LIMS_DATABASE_URL"] = f"sqlite:///{BASE_DIR}/lims.db"

from app.core.database import SessionLocal, engine
from app.models._schema import Base, Order, Sample 

def insert_all_dummy_data():
    # 1. 테이블 전체 재생성 (스키마 변경사항 반영)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("🚀 더미 데이터 생성을 시작합니다...")

        # 2. Order (프로젝트/주문) 생성# 2. Order (프로젝트/주문) 생성
        order1 = Order(
            order_id="GCX-260422-001", 
            facility="C01", 
            client_team="혈액종양내과", 
            reception_date=datetime.strptime("2026-04-22", "%Y-%m-%d").date(), # 🚀 변환 완료!
            sales_unit_price=450000
        )
        order2 = Order(
            order_id="GCX-260422-002", 
            facility="C03", 
            client_team="진단검사의학과", 
            reception_date=datetime.strptime("2026-04-22", "%Y-%m-%d").date(), # 🚀 변환 완료!
            sales_unit_price=550000
        )
        db.add_all([order1, order2])
        db.flush() # ID 할당

        # 3. Sample (시료) 생성 - 각 단계별로 고르게 배치
        samples = [
            # order1: 접수 대기 상태
            Sample(order_id=order1.order_id, sample_id="ACC-260422-001", sample_name="Patient-A", 
                   target_panel="OncoPanel-V1", current_status="접수 대기", sample_received="대기중"),
            Sample(order_id=order1.order_id, sample_id="ACC-260422-002", sample_name="Patient-B", 
                   target_panel="OncoPanel-V1", current_status="접수 대기", sample_received="대기중"),
            
            # order2: QC 및 분석 중 상태
            Sample(order_id=order2.order_id, sample_id="ACC-260422-003", sample_name="Patient-C", 
                   target_panel="WES", current_status="QC 진행", visual_inspection="Pass", issue_comment="추출 농도 양호"),
            Sample(order_id=order2.order_id, sample_id="ACC-260422-004", sample_name="Patient-D", 
                   target_panel="WES", current_status="분석 진행", issue_comment="데이터 QC 진행 중"),
            Sample(order_id=order2.order_id, sample_id="ACC-260422-005", sample_name="Patient-E", 
                   target_panel="WES", current_status="정산 대기")
        ]
        db.add_all(samples)
        
        db.commit()
        print("✅ 샘플 데이터 생성이 완료되었습니다.")
        print(f"   - 주문: {order1.order_id}, {order2.order_id}")
        print(f"   - 총 샘플 수: {len(samples)}개")

    except Exception as e:
        db.rollback()
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    insert_all_dummy_data()