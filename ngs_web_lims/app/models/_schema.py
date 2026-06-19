# app/models/schema.py

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone, timedelta

# 🚀 Rules 파일 불러오기!
from app.core.rules import LimsRules

STAGE_SCHEMA_CONFIG = {
    "접수 대기": {
        "columns": [
            {
                "name": "입고 확인 📦", "id": "sample_received", "editable": True, 
                "presentation": "dropdown", "required": True, "pass_value": "입고 완료",
                "options": ["대기중", "입고 완료"] 
            },
            {
                "name": "입고 담당자 👤", "id": "receiver_name", "editable": True, "required": True
            },
            {
                "name": "보관 위치 📍", "id": "storage_location", "editable": True
            },
            {
                "name": "실물 상태 👁️", "id": "visual_inspection", "editable": True, 
                "presentation": "dropdown",
                "options": [opt["value"] for opt in LimsRules.INSPECTION_OPTIONS if opt["value"]] 
            },
        ]
    },
    "접수 완료": {
            "columns": [
                {"name": "초기 용량(uL)", "id": "initial_volume", "editable": True, "type": "numeric"},
                {"name": "검사진행 여부", "id": "test_progress", "editable": True, "presentation": "dropdown", "options": ["O", "X", "-"]},
                {"name": "Dead Line", "id": "dead_line", "editable": True, "type": "date"},
            ]
        },    
    "QC 진행": {
        "columns": [
            # 🧬 DNA 전용 항목
            {"name": "DNA QC", "id": "dna_qc", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
            {"name": "DNA 농도(ng/uL)", "id": "dna_concentration", "editable": True, "type": "numeric"},
            {"name": "DNA 순도(A260/280)", "id": "purity", "editable": True, "type": "numeric"},
            {"name": "DNA 용량(uL)", "id": "dna_volume", "editable": True, "type": "numeric"},
            {"name": "DNA 총량(μg)", "id": "dna_total_amount", "editable": True, "type": "numeric"},
            
            # 🧬 RNA 전용 항목
            {"name": "RNA QC", "id": "rna_qc", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
            {"name": "RNA 농도(ng/uL)", "id": "rna_concentration", "editable": True, "type": "numeric"},
            {"name": "RNA 용량(uL)", "id": "rna_volume", "editable": True, "type": "numeric"},
            {"name": "RNA 총량(μg)", "id": "rna_total_amount", "editable": True, "type": "numeric"},
            {"name": "DV200 (%)", "id": "dv200", "editable": True, "type": "numeric"},
            
            # 📌 부가 참조 항목 (필요 시 작성)
            {"name": "RIN (RNA)", "id": "rin", "editable": True, "type": "numeric"},
            {"name": "DIN (DNA)", "id": "din", "editable": True, "type": "numeric"},
        ]
    },
    "시퀀싱 진행": {
        "columns": [
            {"name": "SEQ ID", "id": "seq_id", "editable": True},
            {"name": "Depth/Output", "id": "depth_output", "editable": True},
            {"name": "달성 Depth/Output", "id": "depth_output_achieved", "editable": True, "required": False}, 
            {"name": "재실험 횟수", "id": "attempt_num", "editable": True, "type": "numeric", "required": False},
            {"name": "Seq QC Report Date", "id": "seq_qc_report_date", "editable": True, "type": "date"},
        ]
    },
    "분석 진행": {
        "columns": [
            {"name": "Std Report Date 01", "id": "standard_report_date_01", "editable": True, "type": "date"},
            {"name": "Std Report Date 02", "id": "standard_report_date_02", "editable": True, "type": "date"},
            {"name": "Adv Report Date 01", "id": "advanced_report_date_01", "editable": True, "type": "date"},
            {"name": "Adv Report Date 02", "id": "advanced_report_date_02", "editable": True, "type": "date"},
        ]
    },
    "정산 대기": {
        "columns": [
            {"name": "매출 여부", "id": "sales_yn", "editable": True, "presentation": "dropdown", "options": ["Y", "N", "-"]},
            {"name": "매출 단가", "id": "sales_unit_price", "editable": True, "type": "numeric"},
            {"name": "견적서 발행", "id": "quotation_yn", "editable": True, "presentation": "dropdown", "options": ["Y", "N", "-"]},
            {"name": "Quotation ID", "id": "quotation_id", "editable": True},
            {"name": "거래명세서 발행일", "id": "trading_statement_date", "editable": True, "type": "date"},
            {"name": "세금계산서 발행일", "id": "tax_invoice_date", "editable": True, "type": "date"},
            {"name": "매입 여부", "id": "purchase_yn", "editable": True, "presentation": "dropdown", "options": ["Y", "N", "-"]},
            {"name": "매입 단가", "id": "purchase_unit_price", "editable": True, "type": "numeric"},
            {"name": "품의(지출) 작성일", "id": "expense_report_date", "editable": True, "type": "date"},
            {"name": "품의 문서번호", "id": "expense_doc_num", "editable": True},
            {"name": "지출결의 번호", "id": "expense_resolution_num", "editable": True},
        ]
    }
}

REPORT_SCHEMA_CONFIG = {
    "QC Report": {
        "description": "실험 및 시퀀싱 품질 검증을 위한 내부 보고서 (TSO500 포함)",
        "columns": [
            {"name": "DNA QC", "id": "dna_qc", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "PENDING"]},
            {"name": "RNA QC", "id": "rna_qc", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "PENDING"]},
            {"name": "QC 발행일", "id": "sample_qc_report_date", "editable": True, "type": "date"},
            {"name": "DNA 농도", "id": "dna_concentration", "editable": False}, 
            {"name": "RNA 농도", "id": "rna_concentration", "editable": False}, 
            {"name": "검토자", "id": "qc_reviewer", "editable": True},
        ]
    },
    "Clinical Report": {
        "description": "최종 분석 결과를 바탕으로 고객/의료진에게 나가는 결과지",
        "columns": [
            {"name": "보고서 타입", "id": "report_type", "editable": True, "presentation": "dropdown", "options": ["Standard", "Advanced"]},
            {"name": "최종 발행일", "id": "standard_report_date_01", "editable": True, "type": "date"},
            {"name": "종양 비율(%)", "id": "tumor_purity", "editable": False},
            {"name": "매핑률(%)", "id": "mapped_reads_pct", "editable": False},
            {"name": "판독의", "id": "pathologist_name", "editable": True},
            {"name": "특이사항", "id": "report_comment", "editable": True},
        ]
    }
}


Base = declarative_base()

# ==========================================
# 1. 의뢰 및 정산 (Order)
# ==========================================
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    facility = Column(String, nullable=False)
    client_team = Column(String)
    client_name = Column(String)    
    client_email = Column(String)   
    client_phone = Column(String)   
    reception_date = Column(Date, nullable=False)
    reception_type = Column(String, default="미정") 
    sales_unit_price = Column(Integer, default=0)
    
    samples = relationship("Sample", back_populates="order", cascade="all, delete-orphan")

# ==========================================
# 2. 🚀 검체 마스터 (Sample)
# ==========================================
class Sample(Base):
    __tablename__ = "samples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 📌 4대 고정 컬럼
    order_pk = Column(Integer, ForeignKey("orders.id"), nullable=False)
    order_id = Column(String, index=True, nullable=False) 
    project_name = Column(String, default="Default_Project") 
    sample_id = Column(String, unique=True, index=True, nullable=False) 
    target_panel = Column(String, nullable=False) 
    
    # 기본 메타데이터
    sample_name = Column(String, nullable=False)
    outside_id_1 = Column(String)
    cancer_type = Column(String)
    specimen = Column(String)
    pairing_info = Column(String)
    
    # 입고 및 상태 관리
    sample_received = Column(String, default="대기중") 
    receiver_name = Column(String)                   
    visual_inspection = Column(String, default="대기중")
    storage_location = Column(String)
    initial_volume = Column(Float)
    
    # 🚀 핵심 상태 관리
    current_status = Column(String, default="접수 완료")
    issue_comment = Column(String)
    panel_metadata = Column(JSON, default={}) # TSO500 등 유동적 QC 데이터 자동 저장소
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계 설정 (1:1 매핑)
    order = relationship("Order", back_populates="samples")
    wet_lab = relationship("WetLabQC", back_populates="sample", uselist=False)
    sequencing = relationship("Sequencing", back_populates="sample", uselist=False)
    analysis = relationship("Analysis", back_populates="sample", uselist=False)
    logs = relationship("ActionLog", backref="sample")

# ==========================================
# 3. 추출 및 QC (Wet Lab) - 🚀 DNA/RNA 명시적 확장
# ==========================================
class WetLabQC(Base):
    __tablename__ = "wet_lab_qc"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    extraction_status = Column(String)
    
    # 🧬 DNA 관련 DB 컬럼
    dna_qc = Column(String)
    dna_concentration = Column(Float)
    dna_volume = Column(Float)
    dna_total_amount = Column(Float)
    purity = Column(Float) # A260/280
    din = Column(Float)
    
    # 🧬 RNA 관련 DB 컬럼
    rna_qc = Column(String)
    rna_concentration = Column(Float)
    rna_volume = Column(Float)
    rna_total_amount = Column(Float)
    dv200 = Column(Float)
    rin = Column(Float)
    
    sample_qc_report_date = Column(DateTime)
    
    sample = relationship("Sample", back_populates="wet_lab")

# ==========================================
# 4. 시퀀싱 (Sequencing)
# ==========================================
class Sequencing(Base):
    __tablename__ = "sequencing"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    test_status = Column(String)
    seq_id = Column(String, unique=True)
    depth_output = Column(String)
    seq_qc_report_date = Column(DateTime)
    attempt_num = Column(Integer, default=1)
    
    sample = relationship("Sample", back_populates="sequencing")

# ==========================================
# 5. 분석 (Analysis)
# ==========================================
class Analysis(Base):
    __tablename__ = "analysis"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    mapped_reads_pct = Column(Float)
    deadline_date = Column(DateTime)
    std_report_date_01 = Column(DateTime)
    adv_report_date_01 = Column(DateTime)
    
    sample = relationship("Sample", back_populates="analysis")

# ==========================================
# 6. 로그 (Action Log)
# ==========================================
class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    action_type = Column(String, nullable=False)
    previous_state = Column(String)
    new_state = Column(String)
    details = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None))