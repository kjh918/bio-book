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
            {"name": "재실험 횟수", "id": "attempt_num", "editable": True, "type": "numeric"},
            
            # 🚀 [추가] 시퀀싱 수행 기관 (내부/외주 추적)
            {"name": "수행 기관구분", "id": "seq_facility_type", "editable": True, "presentation": "dropdown", "options": ["내부 진행", "외부 위탁"]},
            {"name": "외주 업체명", "id": "outsourced_facility", "editable": True, "presentation": "dropdown", "options": ["마크로젠", "테라젠", "랩지노믹스", "노보진"]},
            {"name": "외주 발송일", "id": "outsourced_date", "editable": True, "type": "date"},
            {"name": "외주 수령일", "id": "received_date", "editable": True, "type": "date"},

            # 장비 및 Run 메타데이터
            {"name": "Platform", "id": "platform", "editable": True, "presentation": "dropdown", "options": ["NovaSeq 6000", "NovaSeq X", "NextSeq 550", "MiSeq", "기타"]},
            {"name": "Run ID", "id": "run_id", "editable": True},
            {"name": "Flowcell ID", "id": "flowcell_id", "editable": True},
            
            # 시퀀싱 QC 메트릭
            {"name": "Traget Amount (Gb)", "id": "target_gb", "editable": True, "type": "numeric"},
            {"name": "Produced Amount (Gb)", "id": "produced_gb", "editable": True, "type": "numeric"},
            {"name": "Total BP (M)", "id": "total_basepair_m", "editable": True, "type": "numeric"},
            {"name": "Total Reads (M)", "id": "total_reads_m", "editable": True, "type": "numeric"},
            {"name": "Q30 (%)", "id": "q30_score", "editable": True, "type": "numeric"},
            
            # FASTQ 파일 연동 경로
            {"name": "FASTQ 경로", "id": "fastq_path", "editable": True},
            
            {"name": "Seq QC 결과", "id": "seq_qc_status", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "PENDING"]},
            {"name": "Seq QC Report Date", "id": "seq_qc_report_date", "editable": True, "type": "date"},
        ]
    },
    "분석 진행": {
        "columns": [
            {"name": "분석 상태", "id": "analysis_status", "editable": True, "presentation": "dropdown", "options": ["대기중", "분석 진행중", "분석 완료", "판독중", "최종 완료"]},
            {"name": "분석 담당자", "id": "analyst", "editable": True},
            
            # 인프라 데이터
            {"name": "Pipeline", "id": "pipeline", "editable": True, "presentation": "dropdown", "options": ["DNA", "RNA", "DNA/RNA 통합"]},
            {"name": "Pipeline Version", "id": "pipeline_version", "editable": True},
            {"name": "Raw Data 경로", "id": "raw_data_pathway", "editable": True},
            {"name": "Work Dir 경로", "id": "work_dir_pathway", "editable": True},
            
            # 일정 데이터
            {"name": "분석 시작일", "id": "analysis_run_start_date", "editable": True, "type": "date"},
            {"name": "분석 종료일", "id": "analysis_run_end_date", "editable": True, "type": "date"},
            {"name": "Std Report 발행일", "id": "standard_report_date_01", "editable": True, "type": "date"},
            {"name": "Adv Report 발행일", "id": "advanced_report_date_01", "editable": True, "type": "date"},
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

ANALYSIS_SCHEMA_CONFIG = {
    "TSO500": {
        "description": "실험 및 시퀀싱 품질 검증을 위한 내부 보고서 (TSO500 포함)",
        "columns": [
            {"name": "DATA ID", "id": "data_id"},
            {"name": "분석 담당자", "id": "analyst", "editable": True},
            {"name": "Panel", "id": "pipeline", "editable": True, "presentation": "dropdown", "options": ["DNA", "RNA"]},
            {"name": "Pipeline Version", "id": "pipeline_version", "editable": True, "presentation": "dropdown", "options": [""]},
            {"name": "분석 시작 일자", "id": "analysis_run_start_date", "editable": True, "type": "date"},
            {"name": "분석 종료 일자", "id": "analysis_run_end_date", "editable": True, "type": "date"},
            {"name": "데이터 경로", "id": "raw_data_pathway", "editable": True},
            {"name": "분석작업폴더 경로", "id": "work_dir_pathway", "editable": True},
        ]
    },
}

REPORT_SCHEMA_CONFIG = {
    "QC Report": {
        "description": "실험 및 시퀀싱 품질 검증을 위한 내부 보고서 (TSO500 포함)",
        "columns": [
            {"name": "DNA QC", "id": "dna_qc", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "PENDING"]},
            {"name": "RNA QC", "id": "rna_qc", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "PENDING"]},
            {"name": "QC 발행일", "id": "sample_qc_report_date", "editable": True, "type": "date"},
            {"name": "검토자", "id": "qc_reviewer", "editable": True},
            
            # 🚀 누락되었던 PDF 연동 필수 항목들을 화면에 보이도록 추가! (수정 불가 처리)
            {"name": "DNA 농도", "id": "dna_concentration", "editable": False, "type": "numeric"}, 
            {"name": "DNA 용량", "id": "dna_volume", "editable": False, "type": "numeric"},
            {"name": "DNA 총량", "id": "dna_total_amount", "editable": False, "type": "numeric"},
            {"name": "DNA 순도", "id": "purity", "editable": False, "type": "numeric"},
            {"name": "RNA 농도", "id": "rna_concentration", "editable": False, "type": "numeric"}, 
            {"name": "RNA 용량", "id": "rna_volume", "editable": False, "type": "numeric"},
            {"name": "RNA 총량", "id": "rna_total_amount", "editable": False, "type": "numeric"},
            {"name": "DV200", "id": "dv200", "editable": False, "type": "numeric"},
            {"name": "특이사항", "id": "issue_comment", "editable": False},
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
    nucleic_acid_type = Column(String)

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
    
    # 식별 및 진행 정보
    seq_id = Column(String, unique=True)
    attempt_num = Column(Integer, default=1)
    
    # 🚀 시퀀싱 수행 기관 정보 (내부/외주 추적)
    seq_facility_type = Column(String, default="내부 진행")
    outsourced_facility = Column(String)
    outsourced_date = Column(Date)
    received_date = Column(Date)          # [신규] 외주 수령일
    
    # 🚀 장비 및 배치 정보
    platform = Column(String)
    run_id = Column(String)
    flowcell_id = Column(String)
    
    # 🚀 시퀀싱 QC 메트릭 (Gb, BP 등 명세 세분화 반영)
    target_gb = Column(Float)             # [신규] 목표 데이터량
    produced_gb = Column(Float)           # [신규] 생산 데이터량
    total_basepair_m = Column(Float)      # [신규] Total BP (M)
    total_reads_m = Column(Float)
    q30_score = Column(Float)
    
    # 🚀 연동 경로
    fastq_path = Column(String)
    
    # 보고 및 상태
    seq_qc_status = Column(String, default="PENDING")
    seq_qc_report_date = Column(Date)
    
    sample = relationship("Sample", back_populates="sequencing")

# ==========================================
# 5. 분석 (Analysis)
# ==========================================
class Analysis(Base):
    __tablename__ = "analysis"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    # 📌 [정형화된 공통 컬럼] 어떤 분석이든 공통으로 가지는 메타데이터
    analysis_status = Column(String, default="대기중")
    analyst = Column(String)

    pipeline = Column(String)           # 예: DNA, RNA, DNA/RNA
    pipeline_version = Column(String)   # 예: v2.3.1
    raw_data_pathway = Column(String)
    work_dir_pathway = Column(String)
    
    analysis_run_start_date = Column(Date)
    analysis_run_end_date = Column(Date)
    
    # 📌 [레포트 연동 공통 컬럼] Clinical Report 호환용
    standard_report_date_01 = Column(Date)
    advanced_report_date_01 = Column(Date)
    
    # 🚀 [분석별 규격화된 JSON] TSO, WES, WTS 등 분석 타입에 따라 형태가 보장된 JSON 데이터
    # API에서 pydantic을 통해 엄격하게 검증된 값만 이 컬럼에 저장됩니다.
    analysis_results = Column(JSON, default={}) 
    
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