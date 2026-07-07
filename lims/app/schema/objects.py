from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, declared_attr
from datetime import datetime, timezone, timedelta

Base = declarative_base()

class PanelMaster(Base):
    """
    검사 종류(Panel)에 따른 접수 양식, 필수 핵산, 분석 버전, 리포트 양식을 중앙 관리합니다.
    """
    __tablename__ = "panel_master"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_code = Column(String, unique=True, index=True, nullable=False) # 예: TSO500, WES
    panel_name = Column(String, nullable=False)                          # 예: TruSight Oncology 500
    
    # 접수 로직 제어
    target_nucleic_acid = Column(String, nullable=False)                 # DNA, RNA, BOTH (접수 시 자동 분할 기준)
    request_template_name = Column(String, nullable=False)               # 엑셀 양식 파일명 (예: tso_request)
    
    # 분석 및 리포트 제어
    default_analysis_version = Column(String, nullable=False)            # 예: v2.1.0
    report_schema_type = Column(String, nullable=False)                  # 예: Clinical Report, Standard Report
    
    is_active = Column(Integer, nullable=False)       

class TrackingMixin:
    """DB 레벨에서의 등록/수정 일시 및 공통 메타데이터 관리"""
    # DB 기록용이므로 여기서는 시스템 기본값을 사용하되, 비즈니스 데이터의 default는 제거함
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None), 
                        onupdate=lambda: datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None))
    creator_id = Column(String, nullable=True) # 등록자 사번/ID
    updater_id = Column(String, nullable=True) # 수정자 사번/ID


class Order(Base, TrackingMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, unique=True, index=True, nullable=False)

    facility = Column(String, nullable=False)
    client_team = Column(String, nullable=False) # [MODIFIED] 필수값으로 변경
    client_name = Column(String, nullable=False)
    client_email = Column(String, nullable=False)
    client_phone = Column(String, nullable=False)

    reception_date = Column(Date, nullable=False)
    reception_type = Column(String, nullable=False) # [MODIFIED] default="미정" 제거
    sales_unit_price = Column(Integer, nullable=False) # [MODIFIED] default=0 제거

    samples = relationship(
        "Sample",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class Sample(Base, TrackingMixin):
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, autoincrement=True)

    order_pk = Column(Integer, ForeignKey("orders.id"), nullable=False)
    order_id = Column(String, index=True, nullable=False)

    sample_id = Column(String, index=True, nullable=False)
    project_name = Column(String, nullable=False) # [MODIFIED] default="Default_Project" 제거

    sample_name = Column(String, nullable=False)
    type = Column(String, nullable=False) # DNA, RNA 등 (필수)
    origin = Column(String, nullable=False) # 검체 유래 (Tissue, Blood 등)
    pairing_info = Column(String)

    outside_id_1 = Column(String)
    sample_received = Column(String, nullable=False) # [MODIFIED] default 제거, 강제 주입
    receiver_name = Column(String)
    visual_inspection = Column(String, nullable=False)
    storage_location = Column(String)
    initial_volume = Column(Float)

    nucleic_acid_type = Column(String)
    current_status = Column(String, nullable=False) # [MODIFIED] default="접수 완료" 제거
    issue_comment = Column(String)

    panel_metadata = Column(JSON, nullable=False) # [MODIFIED] default=dict 제거

    __table_args__ = (
        UniqueConstraint(
            "order_pk",
            "sample_id",
            name="uq_samples_order_pk_sample_id",
        ),
    )

    order = relationship("Order", back_populates="samples")

    analysis_requests = relationship(
        "SampleAnalysisRequest",
        back_populates="sample",
        cascade="all, delete-orphan",
    )

    logs = relationship("ActionLog", backref="sample")


class SampleAnalysisRequest(Base, TrackingMixin):
    __tablename__ = "sample_analysis_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_pk = Column(Integer, ForeignKey("samples.id"), nullable=False)

    target_panel = Column(String, nullable=False)
    assay_type = Column(String, nullable=False)

    current_status = Column(String, nullable=False) # [MODIFIED] default 제거
    project_name = Column(String, nullable=False)   # [MODIFIED] default 제거
    workflow_version = Column(String, nullable=False)
    
    sales_unit_price = Column(Integer, nullable=False)
    issue_comment = Column(String)
    analysis_metadata = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "sample_pk",
            "target_panel",
            "assay_type",
            name="uq_analysis_request_sample_panel_assay",
        ),
    )

    sample = relationship("Sample", back_populates="analysis_requests")
    data_files = relationship("Data", back_populates="analysis_request", cascade="all, delete-orphan")


class Data(Base, TrackingMixin):
    """
    🚀 [MODIFIED] 신규: 생성된 결과 파일(Raw, Bam, Vcf 등)의 메타데이터와 물리적 경로를 추적
    """
    __tablename__ = "data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_request_pk = Column(Integer, ForeignKey("sample_analysis_requests.id"), nullable=False)
    
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False) # 예: FASTQ, BAM, VCF, JSON_REPORT
    file_path = Column(String, nullable=False) # 스토리지 내 절대/상대 경로
    file_size_bytes = Column(Integer)
    md5_checksum = Column(String)              # 데이터 무결성 검증용
    
    is_archived = Column(Integer, nullable=False) # 1=보관됨, 0=활성 (default 제외, boolean 대체용 int)

    analysis_request = relationship("SampleAnalysisRequest", back_populates="data_files")


class ActionLog(Base):
    """이력은 수정되지 않으므로 TrackingMixin 제외, 생성 시간만 기록"""
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    action_type = Column(String, nullable=False)
    previous_state = Column(String)
    new_state = Column(String)
    details = Column(String)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None))