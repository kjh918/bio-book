from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
import json
import traceback
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis

# 🚀 Flask Blueprint 대신 FastAPI APIRouter 사용!
webhook_api = APIRouter()

@webhook_api.post('/api/analysis/complete')
def receive_analysis_results(data: dict = Body(...)):
    """
    39번 분석 서버에서 파이프라인이 종료될 때 JSON 데이터를 쏘는 수신처입니다.
    """
    if not data:
        return JSONResponse(status_code=400, content={"status": "error", "message": "요청 본문(JSON)이 비어있습니다."})
        
    sample_id = data.get("sample_id")
    pipeline = data.get("pipeline", "TSO500")
    results_data = data.get("results", {})
    
    if not sample_id:
        return JSONResponse(status_code=400, content={"status": "error", "message": "sample_id가 누락되었습니다."})

    db = SessionLocal()
    try:
        sample = db.query(Sample).filter(Sample.sample_id == sample_id).first()
        if not sample:
            return JSONResponse(status_code=404, content={"status": "error", "message": f"LIMS에 등록되지 않은 Sample ID입니다: {sample_id}"})
            
        if not sample.analysis:
            sample.analysis = Analysis(sample_id=sample.id)
            db.add(sample.analysis)
            
        # 1. 기존 분석 데이터에 수신받은 새 아웃풋 데이터 병합
        current_results = sample.analysis.analysis_results or {}
        if isinstance(current_results, str):
            current_results = json.loads(current_results) if current_results else {}
            
        for k, v in results_data.items():
            current_results[k] = str(v)
            
        # 타임스탬프 기록
        current_results["pipeline_finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # JSON 업데이트 반영
        sample.analysis.analysis_results = current_results
        flag_modified(sample.analysis, "analysis_results") 
        
        # 🌟 2. 상태 전이: 다음 단계인 레포트 작성 대기열로 이동
        sample.analysis.analysis_status = "분석 완료"
        sample.current_status = "분석 완료"
        
        db.commit()
        print(f"🎉 [Webhook] {sample_id} 결과 수신 및 LIMS DB 적재 완료!")
        
        return JSONResponse(status_code=200, content={
            "status": "success", 
            "message": f"샘플 {sample_id}의 분석 결과가 성공적으로 반영되었습니다."
        })
        
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": f"서버 내부 오류: {str(e)}"})
    finally:
        db.close()