from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone, timedelta

Base = declarative_base()


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

    # 수정: Order는 여러 Sample을 가질 수 있음
    samples = relationship(
        "Sample",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class Sample(Base):
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, autoincrement=True)

    order_pk = Column(Integer, ForeignKey("orders.id"), nullable=False)
    order_id = Column(String, index=True, nullable=False)

    # 수정: sample_id unique 제거
    # 이유: 같은 sample_id가 다른 order에 들어올 가능성을 고려하려면
    #      전체 DB unique보다는 order_pk + sample_id 조합 unique가 더 안전함
    sample_id = Column(String, index=True, nullable=False)

    project_name = Column(String, default="Default_Project")

    sample_name = Column(String, nullable=False)
    outside_id_1 = Column(String)
    cancer_type = Column(String)
    specimen = Column(String)
    pairing_info = Column(String)

    sample_received = Column(String, default="대기중")
    receiver_name = Column(String)
    visual_inspection = Column(String, default="대기중")
    storage_location = Column(String)
    initial_volume = Column(Float)
    nucleic_acid_type = Column(String)

    current_status = Column(String, default="접수 완료")
    issue_comment = Column(String)

    # 수정: JSON default={}는 mutable object라서 callable 사용 권장
    panel_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 수정: 같은 주문 안에서는 sample_id 중복 방지
    __table_args__ = (
        UniqueConstraint(
            "order_pk",
            "sample_id",
            name="uq_samples_order_pk_sample_id",
        ),
    )

    order = relationship("Order", back_populates="samples")

    # 신규: 하나의 검체에서 WGS/WTS/WES/Panel 등 여러 분석 요청 가능
    analysis_requests = relationship(
        "SampleAnalysisRequest",
        back_populates="sample",
        cascade="all, delete-orphan",
    )

    # 기존 관계 유지
    # 주의: wet_lab/sequencing/analysis가 검체 단위인지, 검사 단위인지에 따라
    #      아래 관계는 SampleAnalysisRequest로 이동하는 것이 더 적절할 수 있음
    logs = relationship("ActionLog", backref="sample")


class SampleAnalysisRequest(Base):
    """
    신규 테이블

    하나의 Sample에 대해 실제 수행할 검사 단위를 저장.
    예:
        sample_id = S001
            - WGS
            - WTS
            - WES

    기존 Sample.target_panel을 이 테이블로 분리한 구조.
    """

    __tablename__ = "sample_analysis_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    sample_pk = Column(Integer, ForeignKey("samples.id"), nullable=False)

    # 수정: 기존 Sample.target_panel을 여기로 이동
    # 예: WGS, WTS, WES, TSO500, CBNIPT, RNAseq 등
    target_panel = Column(String, nullable=False)

    # 신규: 검사 타입을 별도 관리
    # 예: DNA, RNA, WGS, WES, WTS, Panel, CNV, Fusion 등
    assay_type = Column(String, nullable=False)

    # 신규: 동일 검체에서 여러 분석이 생기므로 분석별 상태 필요
    current_status = Column(String, default="접수 완료")

    # 신규: 분석별 프로젝트명/워크플로우 버전 관리 가능
    project_name = Column(String, default="Default_Project")
    workflow_version = Column(String)

    # 신규: 분석별 단가가 다를 수 있으면 여기에 저장
    sales_unit_price = Column(Integer, default=0)

    # 신규: 분석별 comment
    issue_comment = Column(String)

    # 신규: 분석별 metadata
    analysis_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 수정: 같은 sample에서 같은 target_panel/assay_type 중복 등록 방지
    __table_args__ = (
        UniqueConstraint(
            "sample_pk",
            "target_panel",
            "assay_type",
            name="uq_analysis_request_sample_panel_assay",
        ),
    )

    sample = relationship("Sample", back_populates="analysis_requests")

    # 수정 권장:
    # 기존 WetLabQC / Sequencing / Analysis가 실제로는 검체 단위가 아니라
    # WGS/WTS/WES 각각에 따라 달라지는 결과라면 Sample이 아니라
    # SampleAnalysisRequest에 연결하는 것이 더 적절함
    wet_lab = relationship(
        "WetLabQC",
        back_populates="analysis_request",
        uselist=False,
    )
    sequencing = relationship(
        "Sequencing",
        back_populates="analysis_request",
        uselist=False,
    )
    analysis = relationship(
        "Analysis",
        back_populates="analysis_request",
        uselist=False,
    )
    
class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    action_type = Column(String, nullable=False)
    previous_state = Column(String)
    new_state = Column(String)
    details = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None))