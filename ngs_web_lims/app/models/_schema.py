from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

# ==========================================
# 1. 의뢰 (Order) 테이블: 프로젝트 단위
# ==========================================
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, unique=True, index=True, nullable=False) # 예: GCX-C11_260331
    facility = Column(String, nullable=False)                          # 의뢰 기관 (C01, C11 등)
    reception_date = Column(Date, nullable=False)                      # 접수일
    sales_revenue = Column(Integer, default=0)                         # 총 예상 매출
    
    # [관계 설정] 하나의 의뢰(Order)는 여러 개의 시료(Sample)를 가짐 (1:N)
    samples = relationship("Sample", back_populates="order", cascade="all, delete-orphan")

# ==========================================
# 2. 시료 (Sample) 테이블: 개별 시료 단위 (기준점)
# ==========================================
class Sample(Base):
    __tablename__ = "samples"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    
    sample_id = Column(String, unique=True, index=True, nullable=False) # 예: ACC-260415-001
    sample_name = Column(String, nullable=False)                        # 고객이 적어준 샘플명
    sample_type = Column(String)                                        # FFPE, Blood, Cell, cfDNA 등
    target_panel = Column(String, nullable=False)                       # WGS, WES, TSO, RNA 등
    
    current_status = Column(String, default="접수 완료")                  # 현재 시료의 위치/상태
    created_at = Column(DateTime, default=datetime.utcnow)

    # [관계 설정] 부모(Order)와 연결, 자식(QC, Seq, Analysis)과 1:1 연결
    order = relationship("Order", back_populates="samples")
    wet_lab = relationship("WetLabQC", back_populates="sample", uselist=False)
    sequencing = relationship("Sequencing", back_populates="sample", uselist=False)
    analysis = relationship("Analysis", back_populates="sample", uselist=False)

# ==========================================
# 3. 추출 및 QC (Wet Lab) 테이블: DNA/RNA 품질 검사
# ==========================================
class WetLabQC(Base):
    __tablename__ = "wet_lab_qc"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    nucleic_acid_type = Column(String)       # DNA or RNA
    concentration = Column(Float)            # 농도 (ng/uL)
    volume = Column(Float)                   # 볼륨 (uL)
    purity_260_280 = Column(Float)           # 순도
    din_rin = Column(Float)                  # DIN (DNA) 또는 RIN (RNA) 수치
    
    qc_result = Column(String)               # Pass, Fail, Hold
    qc_date = Column(Date)
    
    sample = relationship("Sample", back_populates="wet_lab")

# ==========================================
# 4. 시퀀싱 (Sequencing) 테이블: 라이브러리 및 생산 데이터
# ==========================================
class Sequencing(Base):
    __tablename__ = "sequencing"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    seq_id = Column(String, unique=True)     # 라이브러리/시퀀싱 고유 ID
    index_barcode = Column(String)           # 인덱스 정보
    platform = Column(String)                # NovaSeq 6000, NextSeq 등
    
    # 산출 데이터
    yield_gb = Column(Float)                 # 생산량 (Gb)
    q30_score = Column(Float)                # Q30 (%)
    reads_millions = Column(Float)           # Total Reads (M)
    
    seq_status = Column(String)              # 시퀀싱 대기, 진행중, 완료
    seq_date = Column(Date)
    
    sample = relationship("Sample", back_populates="sequencing")

# ==========================================
# 5. 분석 및 레포트 (Analysis) 테이블: Dry Lab
# ==========================================
class Analysis(Base):
    __tablename__ = "analysis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), unique=True)
    
    pipeline_version = Column(String)        # 사용된 파이프라인 (예: TSO500_v2.1)
    mean_depth = Column(Float)               # 평균 뎁스 (WES/WGS/TSO용)
    mapped_reads_pct = Column(Float)         # 매핑률 (%)
    
    # 파일 경로 (서버 내 위치)
    fastq_path = Column(String)
    bam_path = Column(String)
    vcf_path = Column(String)
    
    report_status = Column(String)           # 분석 대기, 분석 중, 레포트 발행 완료
    report_date = Column(Date)
    
    sample = relationship("Sample", back_populates="analysis")