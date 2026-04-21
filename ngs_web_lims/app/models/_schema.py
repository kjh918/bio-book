# app/models/schema.py

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

STAGE_SCHEMA_CONFIG = {
    "접수 대기": {
        "columns": [
            {"name": "입고 확인 📦", "id": "sample_received", "editable": True, "presentation": "dropdown", "required": True, "pass_value": "입고 완료"},
            {"name": "입고 담당자 👤", "id": "receiver_name", "editable": True, "required": True},
            {"name": "보관 위치 📍", "id": "storage_location", "editable": True},
            {"name": "실물 상태 👁️", "id": "visual_inspection", "editable": True, "presentation": "dropdown"},
        ]
    },
    "접수 완료": {
        "columns": [
            {"name": "초기 용량(uL)", "id": "initial_volume", "editable": True, "type": "numeric"},
        ]
    },
    "QC 진행": {
        "columns": [
            {"name": "검체 종류", "id": "specimen", "editable": False, "required": False},
            {"name": "추출 상태", "id": "extraction_status", "editable": True, "required": False},
            {"name": "농도(ng/uL)", "id": "concentration", "editable": True, "type": "numeric", "required": False},
        ]
    },
    "시퀀싱 진행": {
        "columns": [
            {"name": "재실험 횟수", "id": "attempt_num", "editable": True, "type": "numeric", "required": False},
            {"name": "달성 Depth/Output", "id": "depth_output", "editable": True, "required": False},
        ]
    },
    "분석 진행": {
        "columns": [
            {"name": "종양 비율(%)", "id": "tumor_purity", "editable": True, "type": "numeric", "required": False},
            {"name": "매핑률(%)", "id": "mapped_reads_pct", "editable": True, "type": "numeric", "required": False},
        ]
    },
    "정산 대기": {
        "columns": [
            {"name": "세금계산서 발행일", "id": "tax_invoice_date", "editable": True, "required": False},
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
    order_id = Column(String, unique=True, index=True, nullable=False) # C11-260421-01
    facility = Column(String, nullable=False)
    client_team = Column(String)
    reception_date = Column(Date, nullable=False)
    reception_type = Column(String, default="미정") # 🚀 접수 형태 (택배, 퀵 등)
    sales_unit_price = Column(Integer, default=0)
    samples = relationship("Sample", back_populates="order", cascade="all, delete-orphan")
# ==========================================
# 2. 검체 기본 정보 (Sample & JSON Metadata)
# ==========================================
class Sample(Base):
    __tablename__ = "samples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    sample_id = Column(String, unique=True, index=True, nullable=False) # ACC-260421-001
    sample_name = Column(String, nullable=False)
    outside_id_1 = Column(String)
    cancer_type = Column(String)
    specimen = Column(String)
    sample_group = Column(String)
    pairing_info = Column(String)
    target_panel = Column(String, nullable=False)
    
    # 입고 및 검수 정보
    sample_received = Column(String, default="대기중") # 입고 완료 여부
    receiver_name = Column(String)                   # 입고 담당자
    visual_inspection = Column(String, default="대기중")
    storage_location = Column(String)
    initial_volume = Column(Float)
    
    current_status = Column(String, default="접수 대기")
    issue_comment = Column(String)
    panel_metadata = Column(JSON, default={}) # 🚀 특수 정보 보따리
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계 설정
    order = relationship("Order", back_populates="samples")
    wet_lab = relationship("WetLabQC", back_populates="sample", uselist=False)
    sequencing = relationship("Sequencing", back_populates="sample", uselist=False)
    analysis = relationship("Analysis", back_populates="sample", uselist=False)
    logs = relationship("ActionLog", backref="sample")

# ==========================================
# 3. 추출 및 QC (Wet Lab)
# ==========================================
class WetLabQC(Base):
    __tablename__ = "wet_lab_qc"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    extraction_status = Column(String)
    concentration = Column(Float)
    sample_qc = Column(String)
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
    created_at = Column(DateTime, default=datetime.utcnow)