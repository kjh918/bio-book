import sys
import os
from datetime import date, datetime, timedelta
import random

# 프로젝트 루트 경로를 sys.path에 추가하여 app 모듈 import 에러 방지
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.schema.objects import Base, Order, Sample, ActionLog

def seed_test_data():
    # 테이블이 없으면 생성 (안전장치)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 고유한 배치 번호 생성 (실행할 때마다 새로운 데이터 생성)
        batch = datetime.now().strftime("%y%m%d%H%M")
        today = date.today()

        print("🚀 테스트 데이터 생성을 시작합니다...")

        # ==========================================================
        # 1. 접수 대기 오더 (WGS 패널)
        # ==========================================================
        o1 = Order(
            order_id=f"GCX-C01-{batch}-01",
            facility="GCX",
            client_team="NGS",
            client_name="김지훈",
            client_email="jihoon@test.com",
            client_phone="010-1234-5678",
            reception_date=today,
            sales_unit_price=150000
        )
        db.add(o1)
        db.flush() # id 값을 얻기 위해 flush

        for i in range(1, 4):
            s = Sample(
                order_pk=o1.id,
                order_id=o1.order_id,
                sample_id=f"ACC-{batch}-01-{i:03d}-DNA",
                target_panel="WGS",
                project_name=f"WGS_Research_{batch}",
                sample_name=f"Patient_WGS_{i}",
                nucleic_acid_type="DNA",
                sample_received="대기중",
                visual_inspection="대기중",
                current_status="접수 대기",
                panel_metadata={}
            )
            db.add(s)

        # ==========================================================
        # 2. QC 진행 / 시퀀싱 진행 오더 (TSO500 패널 - 다중 상태)
        # ==========================================================
        o2 = Order(
            order_id=f"GMC-C02-{batch}-02",
            facility="GMC",
            client_team="연구소",
            client_name="박민수",
            client_email="minsoo@test.com",
            client_phone="010-9876-5432",
            reception_date=today - timedelta(days=2),
            sales_unit_price=1200000
        )
        db.add(o2)
        db.flush()

        # 2-1. QC 진행 중인 샘플
        s_qc = Sample(
            order_pk=o2.id,
            order_id=o2.order_id,
            sample_id=f"ACC-{batch}-02-001-DNA",
            target_panel="TSO500",
            project_name=f"TSO_Clinical_{batch}",
            sample_name="Patient_TSO_1",
            nucleic_acid_type="DNA",
            sample_received="입고 완료",
            receiver_name="이영희",
            visual_inspection="Pass",
            initial_volume=100.5,
            current_status="QC 진행",
            # 칸반 보드 모달에서 보여줄 동적 데이터 주입
            panel_metadata={
                "dna_qc": "PENDING",
                "dna_concentration": 45.2,
                "dna_volume": 40,
                "purity": 1.85
            }
        )
        db.add(s_qc)
        db.flush()
        
        # 액션 로그 추가 (타임라인 확인용)
        db.add(ActionLog(sample_id=s_qc.id, action_type="상태 변경", previous_state="접수 완료", new_state="QC 진행", details="입고 완료 및 QC 이관"))

        # 2-2. 시퀀싱 진행 중인 샘플
        s_seq = Sample(
            order_pk=o2.id,
            order_id=o2.order_id,
            sample_id=f"ACC-{batch}-02-002-RNA",
            target_panel="TSO500",
            project_name=f"TSO_Clinical_{batch}",
            sample_name="Patient_TSO_2",
            nucleic_acid_type="RNA",
            sample_received="입고 완료",
            receiver_name="이영희",
            visual_inspection="Pass",
            current_status="시퀀싱 진행",
            panel_metadata={
                "rna_qc": "PASS",
                "rna_concentration": 80.5,
                "dv200": 85.2,
                "seq_id": f"SEQ-{batch}-001",
                "platform": "NovaSeq 6000",
                "q30_score": 92.5
            }
        )
        db.add(s_seq)

        # ==========================================================
        # 3. 분석 진행 오더 (WES 패널)
        # ==========================================================
        o3 = Order(
            order_id=f"MAC-C14-{batch}-03",
            facility="마크로젠",
            client_team="Clinical Sales Dept.",
            client_name="최수아",
            client_email="sooah@test.com",
            client_phone="010-3333-4444",
            reception_date=today - timedelta(days=5),
            sales_unit_price=450000
        )
        db.add(o3)
        db.flush()

        s_ana = Sample(
            order_pk=o3.id,
            order_id=o3.order_id,
            sample_id=f"ACC-{batch}-03-001-DNA",
            target_panel="WES",
            project_name=f"WES_Proj_{batch}",
            sample_name="Patient_WES_1",
            nucleic_acid_type="DNA",
            sample_received="입고 완료",
            receiver_name="이영희",
            visual_inspection="Pass",
            current_status="분석 진행",
            issue_comment="빠른 분석 요망",
            panel_metadata={
                "dna_qc": "PASS",
                "seq_qc_status": "PASS",
                "analysis_status": "분석 진행중",
                "analyst": "데이터분석팀",
                "pipeline_version": "v2.1.0"
            }
        )
        db.add(s_ana)

        # 트랜잭션 확정
        db.commit()
        print(f"🎉 성공! 총 3개의 오더와 5개의 샘플이 LIMS 데이터베이스에 생성되었습니다.")
        print(f"   - 확인 가능한 패널 필터: WGS, TSO500, WES")
        print(f"   - 분포된 스테이지: 접수 대기, QC 진행, 시퀀싱 진행, 분석 진행")

    except Exception as e:
        db.rollback()
        print(f"🚨 데이터 생성 중 오류가 발생했습니다: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_test_data()