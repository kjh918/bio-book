from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Union, Literal, Optional
from sqlalchemy.orm import Session

# 🚀 1. DB 세션 및 스키마 모델 불러오기
from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis

# 🚀 2. 라우터 객체 초기화 (이 부분이 빠지면 @router 에러가 납니다!)
router = APIRouter(tags=["Analysis API"])

# 🚀 3. DB 세션 의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------
# 🚀 4. 분석 종류(Panel)별로 엄격하게 정의된 JSON 스키마
# ---------------------------------------------------------

# [A] TSO500 전용 JSON 규격
class TSO500Result(BaseModel):
    analysis_type: Literal["TSO500"] # 반드시 "TSO500"이어야 함
    tumor_purity: float
    tmb_score: float
    msi_status: str
    mapped_reads_pct: float
    variants: List[dict]             # 변이 리스트

# [B] WES 전용 JSON 규격
class WESResult(BaseModel):
    analysis_type: Literal["WES"]    # 반드시 "WES"이어야 함
    tumor_purity: float
    mean_target_coverage: float
    somatic_snv_count: int
    variants: List[dict]

# [C] WTS (RNA) 전용 JSON 규격
class WTSResult(BaseModel):
    analysis_type: Literal["WTS"]    # 반드시 "WTS"이어야 함
    rin_score: float
    mapping_rate: float
    fusions: List[dict]              # 융합 유전자 리스트
    expression_profile: List[dict]   # 발현량 리스트

# ---------------------------------------------------------
# 🚀 5. LIMS API 수신 페이로드 (다형성 라우팅)
# ---------------------------------------------------------
class AnalysisPayload(BaseModel):
    batch_id: str          # 🚀 추가됨 (분석 실행 단위 ID)
    order_id: str          # 🚀 추가됨 (의뢰 고유 ID)
    sample_id: str         # (샘플 고유 ID)
    pipeline_version: str
    
    results: Union[TSO500Result, WESResult, WTSResult] = Field(discriminator='analysis_type')

# ---------------------------------------------------------
# 🚀 6. 수신 API 라우터 엔드포인트
# ---------------------------------------------------------
@router.post("/result")
def receive_formalized_analysis(payload: AnalysisPayload, db: Session = Depends(get_db)):
    sample = db.query(Sample).filter(
        Sample.sample_id == payload.sample_id,
        Sample.order_id == payload.order_id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=404, 
            detail=f"Sample mismatch! Could not find Sample '{payload.sample_id}' under Order '{payload.order_id}'."
        )
    if not sample:
        raise HTTPException(status_code=404, detail="Sample ID not found")
        
    if not sample.analysis:
        sample.analysis = Analysis(sample_id=sample.id)
        
    # 공통 컬럼 업데이트
    sample.analysis.analysis_status = "분석 완료"
    sample.analysis.pipeline_version = payload.pipeline_version
    
    # 규격화된 결과 JSON을 DB에 저장 (Pydantic이 이미 완벽히 검증했으므로 100% 안전함)
    sample.analysis.analysis_results = payload.results.model_dump()
    
    # 마스터 테이블이나 칸반 등 LIMS 전반의 상태 업데이트
    sample.current_status = "분석 진행" 
    
    db.commit()
    return {"message": f"Successfully saved {payload.results.analysis_type} formalized data."}