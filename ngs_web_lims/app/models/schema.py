from sqlalchemy import Column, String, Float, JSON, Integer
from sqlalchemy.orm import declarative_base

# 1. Base 객체 선언
Base = declarative_base()

# 2. 기존 모델: 샘플 기본 정보 (Dash Dashboard 용)
class Sample(Base):
    __tablename__ = "samples"
    sample_id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    qc_result = Column(String, nullable=False)
    yield_gb = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=True, default={}) # nullable 허용 및 기본값 설정

    def __init__(self, sample_id: str, project_id: str, status: str, qc_result: str, yield_gb: float, metrics: dict = None):
        if not sample_id: raise ValueError("Sample ID 필수")
        self.sample_id = sample_id
        self.project_id = project_id
        self.status = status
        self.qc_result = qc_result
        self.yield_gb = yield_gb
        # metrics가 None으로 들어오면 빈 딕셔너리로 초기화 (에러 방지)
        self.metrics = metrics if metrics is not None else {}

class NGSTracking(Base):
    __tablename__ = "ngs_tracking"
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    registration_id = Column(String, nullable=True)
    order_id = Column(String, nullable=False)
    sample_name = Column(String, nullable=False)
    seq_id = Column(String, nullable=False, unique=True)
    
    excel_data = Column(JSON, nullable=False)

    # 🚀 [수정됨] Date -> String 으로 변경! (Dash/Plotly 충돌 방지)
    reception_date = Column(String, index=True, nullable=True)   # YYYY-MM-DD (String)
    reception_year = Column(Integer, index=True, nullable=True)  # 2026 (Integer)
    reception_month = Column(Integer, nullable=True)             # 4 (Integer)
    order_facility = Column(String, index=True, nullable=True)   
    analysis_type = Column(String, index=True, nullable=True)    
    sales_revenue = Column(Integer, default=0, nullable=False)   
    purchase_cost = Column(Integer, default=0, nullable=False)   
    

    def __init__(
        self, order_id: str, sample_name: str, seq_id: str, excel_data: dict, 
        registration_id: str = None, reception_date: str = None, # 🚀 타입 힌트도 str로 변경
        reception_year: int = None, reception_month: int = None,
        order_facility: str = None, analysis_type: str = None,
        sales_revenue: int = 0, purchase_cost: int = 0,
    ):
        if not order_id: raise ValueError("Order ID는 필수입니다.")
        if not sample_name: raise ValueError("Sample Name은 필수입니다.")
        if not seq_id: raise ValueError("SEQ ID는 필수입니다.")
        if not excel_data or not isinstance(excel_data, dict):
            raise ValueError("excel_data(dict)는 필수입니다.")
            
        self.registration_id = registration_id
        self.order_id = order_id
        self.sample_name = sample_name 
        self.seq_id = seq_id
        self.excel_data = excel_data
        
        self.reception_date = reception_date
        self.reception_year = reception_year
        self.reception_month = reception_month
        self.order_facility = order_facility
        self.analysis_type = analysis_type
        self.sales_revenue = sales_revenue
        self.purchase_cost = purchase_cost