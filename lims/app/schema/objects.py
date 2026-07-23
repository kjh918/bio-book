"""
LIMS Schema: Project-based hierarchy
=====================================
Project → Sample → Library → SequencingRun → Analysis → Data

ID 체계 (자동 채번):
  Project       : PRJ-{YYYYMM}-{seq:04d}          예) PRJ-202507-0001
  Sample        : {project_code}-S{seq:03d}        예) PRJ-202507-0001-S001
  Library       : {sample_id}-L{seq:03d}           예) PRJ-202507-0001-S001-L001
  SequencingRun : SEQ-{YYYYMM}-{seq:04d}           예) SEQ-202507-0001
  Analysis      : {project_code}-A{seq:03d}        예) PRJ-202507-0001-A001
  Data          : {analysis_id}-D{seq:03d}         예) PRJ-202507-0001-A001-D001

각 엔티티는 current_status + ActionLog로 상태 이력 관리.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, JSON, UniqueConstraint, Text, Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ─────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────
def _kst_now():
    return datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None)


# ─────────────────────────────────────────────────────
# Mixins
# ─────────────────────────────────────────────────────
class TrackingMixin:
    """등록/수정 일시 + 담당자 공통 컬럼"""
    created_at = Column(DateTime, nullable=False, default=_kst_now)
    updated_at = Column(DateTime, nullable=False, default=_kst_now, onupdate=_kst_now)
    creator_id = Column(String(50), nullable=True)
    updater_id = Column(String(50), nullable=True)


# ─────────────────────────────────────────────────────
# 0. 공통 마스터 테이블
# ─────────────────────────────────────────────────────
class ProjectMaster(Base):
    """
    사용자가 추가/관리하는 프로젝트 종류 마스터.
    예: cbNIPT, MRD, NGS Service, WGS Research …

    project_code: ID 생성에 사용되는 slug (공백→_, 소문자→대문자 자동 변환)
                  예) "NGS Service" → "NGS_SERVICE"
    project_label: UI에 표시되는 원본 이름 ("NGS Service")
    """
    __tablename__ = "project_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_code = Column(String(50), unique=True, index=True, nullable=False)  # NGS_SERVICE
    project_label = Column(String(200), nullable=False)                          # NGS Service
    description = Column(String(500), nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=_kst_now)


class PanelMaster(Base):
    """
    검사 패널 마스터.
    Library 단계에서 target_panel 선택 시 이 테이블을 참조.
    """
    __tablename__ = "panel_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_code = Column(String(50), unique=True, index=True, nullable=False)   # TSO500, WES, …
    panel_name = Column(String(200), nullable=False)                            # TruSight Oncology 500
    target_nucleic_acid = Column(String(20), nullable=False)                    # DNA | RNA | BOTH
    request_template_name = Column(String(100), nullable=False)
    default_analysis_version = Column(String(50), nullable=False)
    report_schema_type = Column(String(100), nullable=False)
    is_active = Column(Integer, nullable=False, default=1)


# ─────────────────────────────────────────────────────
# 1. Project
# ─────────────────────────────────────────────────────
class Project(Base, TrackingMixin):
    """
    최상위 단위. 하나의 수주/의뢰 건.
    ID: PRJ-{YYYYMM}-{seq:04d}

    Project 안에 여러 Sample이 존재.
    project_type: Research | Clinical | External
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), unique=True, index=True, nullable=False)   # CBNIPT-202507-0001

    project_code = Column(String(50), nullable=False, index=True)              # ProjectMaster.project_code
    project_name = Column(String(200), nullable=False)                          # 개별 프로젝트 이름 (자유 입력)
    project_type = Column(String(50), nullable=False)                           # Research / Clinical / External
    pi_name = Column(String(100), nullable=True)                                # 책임자/PI

    # 의뢰 기관 정보
    facility = Column(String(200), nullable=False)
    client_team = Column(String(100), nullable=False)
    client_name = Column(String(100), nullable=False)
    client_email = Column(String(200), nullable=False)
    client_phone = Column(String(50), nullable=False)

    reception_date = Column(Date, nullable=False)
    deadline = Column(Date, nullable=True)
    sales_unit_price = Column(Integer, nullable=False, default=0)

    current_status = Column(String(50), nullable=False)                         # 접수 완료 / 진행중 / 완료 / 취소
    issue_comment = Column(Text, nullable=True)
    project_metadata = Column(JSON, nullable=False, default=dict)

    # Relations
    samples = relationship("Sample", back_populates="project", cascade="all, delete-orphan")
    logs = relationship("ActionLog", back_populates="project", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────
# 2. Sample
# ─────────────────────────────────────────────────────
class Sample(Base, TrackingMixin):
    """
    물리적 검체(튜브 단위).
    ID: {project_id}-S{seq:03d}  예) PRJ-202507-0001-S001

    혈액 1건 → DNA 추출 Library + RNA 추출 Library 처럼
    한 Sample에서 여러 Library 파생 가능.
    """
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(String(50), unique=True, index=True, nullable=False)    # PRJ-202507-0001-S001

    project_pk = Column(Integer, ForeignKey("projects.id"), nullable=False)
    project_id = Column(String(30), index=True, nullable=False)                # 역참조 편의용 denorm

    sample_name = Column(String(200), nullable=False)
    origin = Column(String(100), nullable=False)                                # Blood / Tissue / FFPE / Urine …
    pairing_info = Column(String(100), nullable=True)                          # Tumor / Normal / Paired
    outside_id = Column(String(100), nullable=True)                            # 의뢰처 자체 ID

    # 입고/상태
    sample_received = Column(String(50), nullable=False)                        # 대기중 / 입고 완료
    receiver_name = Column(String(100), nullable=True)
    visual_inspection = Column(String(50), nullable=False)                      # 양호 / 불량 / 보류
    storage_location = Column(String(200), nullable=True)
    initial_volume = Column(Float, nullable=True)
    test_progress = Column(String(20), nullable=False)                          # 진행 / 보류 / 취소

    current_status = Column(String(50), nullable=False)                         # 단계별 현황
    issue_comment = Column(Text, nullable=True)
    sample_metadata = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("project_pk", "sample_id", name="uq_sample_project_sample_id"),
    )

    # Relations
    project = relationship("Project", back_populates="samples")
    libraries = relationship("Library", back_populates="sample", cascade="all, delete-orphan")
    logs = relationship("ActionLog", back_populates="sample")


# ─────────────────────────────────────────────────────
# 3. Library
# ─────────────────────────────────────────────────────
class Library(Base, TrackingMixin):
    """
    핵산 추출 → Library 제작 단위.
    ID: {sample_id}-L{seq:03d}  예) PRJ-202507-0001-S001-L001

    같은 Sample에서 DNA Library, RNA Library 각각 생성 가능.
    nucleic_acid_type: DNA | RNA | cfDNA | gDNA
    """
    __tablename__ = "libraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(String(70), unique=True, index=True, nullable=False)   # PRJ-202507-0001-S001-L001

    sample_pk = Column(Integer, ForeignKey("samples.id"), nullable=False)
    sample_id = Column(String(50), index=True, nullable=False)

    # 패널/Assay 정보
    target_panel = Column(String(50), nullable=False)                           # TSO500 / WES / WGS …
    assay_type = Column(String(20), nullable=False)                             # DNA / RNA / DNA+RNA
    nucleic_acid_type = Column(String(20), nullable=False)                      # DNA / RNA / cfDNA

    # Sample QC (핵산 QC)
    dna_concentration = Column(Float, nullable=True)
    dna_volume = Column(Float, nullable=True)
    purity_260_280 = Column(Float, nullable=True)
    purity_260_230 = Column(Float, nullable=True)
    din = Column(Float, nullable=True)
    dna_qc = Column(String(20), nullable=True)                                  # PASS/FAIL/HOLD/RE-RUN/PENDING

    rna_concentration = Column(Float, nullable=True)
    rna_volume = Column(Float, nullable=True)
    dv200 = Column(Float, nullable=True)
    rin = Column(Float, nullable=True)
    rna_qc = Column(String(20), nullable=True)

    # Library QC
    library_method = Column(String(100), nullable=True)
    library_concentration = Column(Float, nullable=True)                        # ng/uL
    library_molarity = Column(Float, nullable=True)                             # nM
    library_volume = Column(Float, nullable=True)                               # uL
    library_size = Column(Float, nullable=True)                                 # bp
    index_id = Column(String(100), nullable=True)
    library_qc = Column(String(20), nullable=True)                              # PASS/FAIL/HOLD/RE-RUN/PENDING

    workflow_version = Column(String(50), nullable=False)
    current_status = Column(String(50), nullable=False)
    issue_comment = Column(Text, nullable=True)
    qc_comment = Column(Text, nullable=True)
    library_metadata = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("sample_pk", "library_id", name="uq_library_sample_library_id"),
    )

    # Relations
    sample = relationship("Sample", back_populates="libraries")
    sequencing_runs = relationship(
        "LibrarySequencingRun",
        back_populates="library",
        cascade="all, delete-orphan",
    )
    logs = relationship("ActionLog", back_populates="library")


# ─────────────────────────────────────────────────────
# 4. SequencingRun  (장비/런 단위)
# ─────────────────────────────────────────────────────
class SequencingRun(Base, TrackingMixin):
    """
    시퀀서 1회 Run 단위. 여러 Library가 한 Run에 pooling됨.
    ID: SEQ-{YYYYMM}-{seq:04d}  예) SEQ-202507-0001

    Library와는 LibrarySequencingRun (M:N 연결 테이블) 로 연결.
    """
    __tablename__ = "sequencing_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), unique=True, index=True, nullable=False)        # TSO500-202507-0001

    platform = Column(String(50), nullable=False)                               # NovaSeq X / NextSeq 2000 …
    flowcell_id = Column(String(100), nullable=True)
    instrument_id = Column(String(100), nullable=True)
    read_type = Column(String(10), nullable=True)                               # SE / PE
    read_length = Column(String(20), nullable=True)                             # 150 / 151 …
    seq_facility_type = Column(String(50), nullable=False)                      # 내부 진행 / 외부 위탁

    run_date = Column(Date, nullable=True)
    q30_score = Column(Float, nullable=True)
    total_reads = Column(Float, nullable=True)
    total_bases = Column(Float, nullable=True)
    fastq_path = Column(String(500), nullable=True)

    seq_qc_status = Column(String(20), nullable=True)                           # PASS/FAIL/HOLD …
    current_status = Column(String(50), nullable=False)
    seq_comment = Column(Text, nullable=True)
    run_metadata = Column(JSON, nullable=False, default=dict)

    # Relations
    library_links = relationship(
        "LibrarySequencingRun",
        back_populates="sequencing_run",
        cascade="all, delete-orphan",
    )
    logs = relationship("ActionLog", back_populates="sequencing_run")


# ─────────────────────────────────────────────────────
# 4-1. Library ↔ SequencingRun  M:N 연결 테이블
# ─────────────────────────────────────────────────────
class LibrarySequencingRun(Base, TrackingMixin):
    """
    Library가 어떤 SequencingRun에 로드됐는지 기록.
    한 Library가 재런(Re-run)으로 여러 Run에 들어갈 수 있고,
    한 Run에 여러 Library가 pooling되므로 M:N 구조.
    """
    __tablename__ = "library_sequencing_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_pk = Column(Integer, ForeignKey("libraries.id"), nullable=False)
    sequencing_run_pk = Column(Integer, ForeignKey("sequencing_runs.id"), nullable=False)

    # 이 조합별 결과 (같은 Library라도 Re-run마다 다를 수 있음)
    is_rerun = Column(Integer, nullable=False, default=0)                       # 0=최초, 1=재런
    rerun_reason = Column(String(200), nullable=True)
    lane_number = Column(String(20), nullable=True)
    sample_sheet_index = Column(String(50), nullable=True)

    per_sample_reads = Column(Float, nullable=True)
    per_sample_bases = Column(Float, nullable=True)
    per_sample_q30 = Column(Float, nullable=True)
    demux_status = Column(String(20), nullable=True)                            # PASS/FAIL/PENDING

    __table_args__ = (
        UniqueConstraint(
            "library_pk", "sequencing_run_pk", "is_rerun",
            name="uq_lib_seq_run_rerun",
        ),
    )

    # Relations
    library = relationship("Library", back_populates="sequencing_runs")
    sequencing_run = relationship("SequencingRun", back_populates="library_links")


# ─────────────────────────────────────────────────────
# 5. Analysis
# ─────────────────────────────────────────────────────
class Analysis(Base, TrackingMixin):
    """
    Sequencing 결과 → 파이프라인 분석 단위.
    ID: {project_id}-A{seq:03d}  예) PRJ-202507-0001-A001

    하나의 Project(또는 Library)에 대해 버전/파라미터를 달리한
    여러 Analysis가 생성될 수 있음.
    """
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(50), unique=True, index=True, nullable=False)  # PRJ-202507-0001-A001

    # 연결: Analysis는 Library 단위로 실행 (복수 Library → 별도 Analysis)
    library_pk = Column(Integer, ForeignKey("libraries.id"), nullable=False)
    library_id = Column(String(70), index=True, nullable=False)

    # Project 역참조 (쿼리 편의)
    project_pk = Column(Integer, ForeignKey("projects.id"), nullable=False)
    project_id = Column(String(30), index=True, nullable=False)

    # 파이프라인 정보
    pipeline_name = Column(String(100), nullable=True)
    pipeline_version = Column(String(50), nullable=False)
    reference_version = Column(String(30), nullable=True)                       # hg38 / GRCh38 …
    analyst = Column(String(100), nullable=True)

    analysis_start_date = Column(Date, nullable=True)
    analysis_end_date = Column(Date, nullable=True)
    result_path = Column(String(500), nullable=True)

    analysis_qc_status = Column(String(20), nullable=True)                      # PASS/FAIL/HOLD …
    current_status = Column(String(50), nullable=False)                         # 대기중 / 분석 진행중 / 완료 …
    issue_comment = Column(Text, nullable=True)
    analysis_metadata = Column(JSON, nullable=False, default=dict)

    # Relations
    library = relationship("Library")
    project = relationship("Project")
    data_files = relationship("Data", back_populates="analysis", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="analysis", cascade="all, delete-orphan")
    logs = relationship("ActionLog", back_populates="analysis")


# ─────────────────────────────────────────────────────
# 6. Data
# ─────────────────────────────────────────────────────
class Data(Base, TrackingMixin):
    """
    Analysis 결과 파일 메타데이터.
    ID: {analysis_id}-D{seq:03d}  예) PRJ-202507-0001-A001-D001

    Analysis 1건당 FASTQ, BAM, VCF, JSON 등 복수 파일 생성 가능.
    """
    """
    data_id 자체가 파일명 stem:
      data_id   = CBNIPT-202507-0001-A001-D001
      file_ext  = bam
      file_name = CBNIPT-202507-0001-A001-D001.bam          (자동 조립)
      file_path = {base_dir}/{analysis_id}/{file_name}      (자동 조립)

    DataService.register() 로 등록 → 경로/파일명 자동 생성.
    DataService.get_info(data_id) 로 key-value 메타 딕셔너리 반환.
    """
    __tablename__ = "data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_id = Column(String(100), unique=True, index=True, nullable=False)     # CBNIPT-202507-0001-A001-D001

    analysis_pk = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    analysis_id = Column(String(70), index=True, nullable=False)

    # 파일 식별 — data_id 가 stem, ext 붙이면 file_name
    file_ext  = Column(String(30), nullable=False)                             # bam / vcf / fastq.gz / json / html
    file_name = Column(String(200), nullable=False)                            # {data_id}.{file_ext}  자동 조립
    file_path = Column(String(1000), nullable=False)                           # {base_dir}/{analysis_id}/{file_name}
    file_type = Column(String(30), nullable=False)                             # BAM / VCF / FASTQ / JSON_REPORT / QC_HTML

    # 무결성 / 보관
    file_size_bytes = Column(Integer, nullable=True)
    md5_checksum    = Column(String(64), nullable=True)
    is_archived     = Column(Integer, nullable=False, default=0)               # 0=활성, 1=보관

    # 파일별 자유 메타 (key-value 확장용)
    # BAM  예) {"ref_genome": "hg38", "mean_depth": 42.3, "mapped_pct": 99.1}
    # FASTQ예) {"read_count": 1200000, "q30_pct": 94.2, "read_length": 150}
    # VCF  예) {"variant_count": 312, "caller": "Mutect2", "filter_pass": 210}
    file_metadata = Column(JSON, nullable=False, default=dict)

    # Relations
    analysis = relationship("Analysis", back_populates="data_files")


# ─────────────────────────────────────────────────────
# 7. Report
# ─────────────────────────────────────────────────────
class Report(Base, TrackingMixin):
    """
    Analysis → 보고서 발행 단위.
    Analysis 1건에 Standard/Clinical 등 복수 보고서 가능.
    """
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)

    analysis_pk = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    analysis_id = Column(String(50), index=True, nullable=False)

    # Project 역참조
    project_pk = Column(Integer, ForeignKey("projects.id"), nullable=False)
    project_id = Column(String(30), index=True, nullable=False)

    report_type = Column(String(50), nullable=False)                            # Standard / Clinical / Advanced
    report_status = Column(String(50), nullable=False)                          # 대기중 / 작성중 / 발행 완료 …
    reviewer = Column(String(100), nullable=True)
    reporter = Column(String(100), nullable=True)
    pathologist_name = Column(String(100), nullable=True)

    standard_report_date = Column(Date, nullable=True)
    final_report_date = Column(Date, nullable=True)
    report_file_path = Column(String(1000), nullable=True)
    report_comment = Column(Text, nullable=True)
    report_metadata = Column(JSON, nullable=False, default=dict)

    # Relations
    analysis = relationship("Analysis", back_populates="reports")
    project = relationship("Project")


# ─────────────────────────────────────────────────────
# 8. ActionLog  (모든 단계 이력 통합)
# ─────────────────────────────────────────────────────
class ActionLog(Base):
    """
    각 엔티티의 status 변경 이력을 단일 테이블에서 추적.
    entity_type + entity_pk 조합으로 어떤 레코드의 이력인지 식별.

    entity_type: project | sample | library | sequencing_run | analysis | data | report
    """
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=_kst_now)

    # 어느 엔티티의 이력인가 (polymorphic FK 대신 type+pk 조합 사용)
    entity_type = Column(String(30), nullable=False, index=True)
    entity_id = Column(String(70), nullable=False, index=True)                 # 해당 엔티티의 human-readable ID

    # 편의용 FK (nullable — 모든 컬럼이 항상 채워지지 않음)
    project_pk = Column(Integer, ForeignKey("projects.id"), nullable=True)
    sample_pk = Column(Integer, ForeignKey("samples.id"), nullable=True)
    library_pk = Column(Integer, ForeignKey("libraries.id"), nullable=True)
    sequencing_run_pk = Column(Integer, ForeignKey("sequencing_runs.id"), nullable=True)
    analysis_pk = Column(Integer, ForeignKey("analyses.id"), nullable=True)

    action_type = Column(String(50), nullable=False)                           # STATUS_CHANGE / QC_UPDATE / FILE_UPLOAD …
    previous_state = Column(String(100), nullable=True)
    new_state = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    actor_id = Column(String(50), nullable=True)                               # 수행자 사번/ID

    # Relations (back_populates는 각 엔티티에서 선언)
    project = relationship("Project", back_populates="logs", foreign_keys=[project_pk])
    sample = relationship("Sample", back_populates="logs", foreign_keys=[sample_pk])
    library = relationship("Library", back_populates="logs", foreign_keys=[library_pk])
    sequencing_run = relationship("SequencingRun", back_populates="logs", foreign_keys=[sequencing_run_pk])
    analysis = relationship("Analysis", back_populates="logs", foreign_keys=[analysis_pk])

    __table_args__ = (
        Index("ix_action_log_entity", "entity_type", "entity_id"),
        Index("ix_action_log_project_type", "project_pk", "entity_type"),
    )