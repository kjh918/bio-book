from typing import Dict, Any, List, Optional
from app.core.rules import StageRules

# ─────────────────────────────────────────────
# Base Class
# ─────────────────────────────────────────────
class BaseProcessing:
    name: str = ""
    description: str = ""
    columns: Dict[str, Dict[str, Any]] = {}
    
    # 🚀 [MODIFIED] 범용 액션 상태 추적
    current_action: str = "READY"

    # 🚀 [MODIFIED] 모든 Stage 화면에서 공통으로 보여줄 추적 컬럼 세팅
    COMMON_COLUMNS = {
        "created_at": {"name": "최초 등록일시", "editable": False, "type": "datetime"},
        "updated_at": {"name": "최근 수정일시", "editable": False, "type": "datetime"},
        "updater_id": {"name": "최종 수정자", "editable": False},
    }

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None):
        if name: self.name = name
        if description: self.description = description

    def get_action_config(self) -> Dict[str, Any]:
        """UI 액션 버튼 속성 반환"""
        return StageRules.ACTION_STATE.get(self.current_action, StageRules.ACTION_STATE["READY"])

    def get_columns(self) -> List[Dict[str, Any]]:
        """프론트엔드(ag-Grid)에서 요구하는 리스트 형식으로 변환 (공통 컬럼 자동 병합)"""
        merged = {**self.columns, **self.COMMON_COLUMNS}
        return [{"id": col_id, **col_def} for col_id, col_def in merged.items()]

    def get_column(self, col_id: str) -> Dict[str, Any]:
        merged = {**self.columns, **self.COMMON_COLUMNS}
        return merged.get(col_id, {})

    @staticmethod
    def stage_rules():
        """각 Stage별로 적용되는 룰을 반환"""
        return {
            "kanban_stages": StageRules.KANBAN_STAGES,
            "stage_actions": StageRules.STAGE_ACTIONS,
            "inspection_options": StageRules.INSPECTION_OPTIONS,
        }


# ─────────────────────────────────────────────
# 1. 검체 접수 Stage
# ─────────────────────────────────────────────
class Registration(BaseProcessing):
    """검체 입고 및 접수 단계. status에 따라 표시 컬럼을 동적으로 변경."""
    name = "검체 접수"
    description = "검체 입고 확인, 보관 위치, 실물 상태 확인 단계"

    # 🚀 [MODIFIED] all_columns 대신 BaseProcessing 동일한 columns 사용
    columns = {
        "sample_received": {"name": "입고 확인", "editable": True, "presentation": "dropdown", "options": ["대기중", "입고 완료"]},
        "receiver_name": {"name": "입고 담당자", "editable": True},
        "storage_location": {"name": "보관 위치", "editable": True},
        "visual_inspection": {"name": "상태", "editable": True, "presentation": "dropdown", "options": [opt["value"] for opt in StageRules.INSPECTION_OPTIONS if opt["value"]]},
        "initial_volume": {"name": "초기 용량", "editable": True, "type": "str"},
        "test_progress": {"name": "검사진행 여부", "editable": True, "presentation": "dropdown", "options": ["진행", "보류", "취소"]},
        "dead_line": {"name": "Dead Line", "editable": True, "type": "date"},
    }

    def get_columns(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """상태에 따른 컬럼 필터링 및 공통 컬럼 병합"""
        if status == "대기중":
            target_keys = ["sample_received", "receiver_name", "storage_location", "visual_inspection"]
        elif status == "입고 완료":
            target_keys = ["initial_volume", "test_progress", "dead_line"]
        else:
            target_keys = list(self.columns.keys())

        # 🚀 [MODIFIED] 필터링된 컬럼에 COMMON_COLUMNS를 합쳐서 반환
        filtered_cols = {k: self.columns[k] for k in target_keys}
        merged = {**filtered_cols, **self.COMMON_COLUMNS}
        return [{"id": k, **v} for k, v in merged.items()]


# ─────────────────────────────────────────────
# 2. 절차 진행 Stage
# ─────────────────────────────────────────────
class Procedure(BaseProcessing):
    name = "절차 진행"
    description = "검사 요청, 재검 여부, 외부 위탁 여부, 진행 상태 관리"
    columns = {
        "analysis_request_id": {"name": "검사 요청 ID", "editable": False},
        "target_panel": {"name": "Target Panel", "editable": True, "presentation": "dropdown", "options": ["WGS", "WES", "WTS", "RNA-seq", "TSO500", "CBNIPT", "기타"]},
        "assay_type": {"name": "Assay Type", "editable": True, "presentation": "dropdown", "options": ["DNA", "RNA", "DNA+RNA", "cfDNA", "gDNA", "기타"]},
        "request_status": {"name": "요청 상태", "editable": True, "presentation": "dropdown", "options": ["접수 완료", "QC 대기", "QC 진행중", "Library 대기", "Sequencing 대기", "분석 대기", "보고 대기", "최종 완료", "보류", "취소"]},
        "is_rerun": {"name": "재검 여부", "editable": True, "presentation": "dropdown", "options": ["No", "Yes"]},
        "rerun_reason": {"name": "재검 사유", "editable": True},
        "outsourcing_status": {"name": "외부 위탁 여부", "editable": True, "presentation": "dropdown", "options": ["내부 진행", "외부 위탁", "해당 없음"]},
        "procedure_comment": {"name": "절차 Comment", "editable": True},
    }

# ─────────────────────────────────────────────
# 3. 검체 QC Stage
# ─────────────────────────────────────────────
class SamplePreparation(BaseProcessing):
    name = "sample_preparation"
    description = "DNA/RNA 추출물 QC 및 농도/순도/총량 확인"
    columns = {
        "nucleic_acid_type": {"name": "핵산 종류", "editable": True, "presentation": "dropdown", "options": ["DNA", "RNA", "DNA+RNA", "cfDNA", "기타"]},
        "dna_qc": {"name": "DNA QC", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
        "dna_concentration": {"name": "DNA 농도(ng/uL)", "editable": True, "type": "numeric"},
        "dna_volume": {"name": "DNA 용량(uL)", "editable": True, "type": "numeric"},
        "dna_total_amount": {
            "name": "Library 총량(ng)", 
            "editable": False, # 자동 계산되므로 직접 수정 불가
            "type": "numeric",
            "valueGetter": {"function": "Number(params.data.dna_concentration) * Number(params.data.dna_volume) || ''"}
        },
        
        "purity_260_280": {"name": "A260/280", "editable": True, "type": "numeric"},
        "purity_260_230": {"name": "A260/230", "editable": True, "type": "numeric"},
        "din": {"name": "DIN", "editable": True, "type": "numeric"},
        "rna_qc": {"name": "RNA QC", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
        "rna_concentration": {"name": "RNA 농도(ng/uL)", "editable": True, "type": "numeric"},
        "rna_volume": {"name": "RNA 용량(uL)", "editable": True, "type": "numeric"},
        
        "rna_total_amount": {
            "name": "Library 총량(ng)", 
            "editable": False, # 자동 계산되므로 직접 수정 불가
            "type": "numeric",
            "valueGetter": {"function": "Number(params.data.rna_concentration) * Number(params.data.rna_volume) || ''"}
        },
        "dv200": {"name": "DV200 (%)", "editable": True, "type": "numeric"},
        "rin": {"name": "RIN", "editable": True, "type": "numeric"},
        "qc_comment": {"name": "QC Comment", "editable": True},
    }

# ─────────────────────────────────────────────
# 4. Library QC Stage
# ─────────────────────────────────────────────
class LibraryQC(BaseProcessing):
    name = "Library QC"
    description = "Library 제작, 농도, size, yield, library QC 결과 관리"
    columns = {
        "library_id": {"name": "Library ID", "editable": True},
        "library_method": {"name": "Library Method", "editable": True, "presentation": "dropdown", "options": ["WGS", "WES", "RNA-seq", "Target Panel", "Amplicon", "Low-pass WGS", "기타"]},
        "library_qc": {"name": "Library QC", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
        "library_concentration": {"name": "Library 농도(ng/uL)", "editable": True, "type": "numeric"},
        "library_molarity": {"name": "Library 농도(nM)", "editable": True, "type": "numeric"},
        "library_volume": {"name": "Library 용량(uL)", "editable": True, "type": "numeric"},
        "library_total_amount": {
            "name": "Library 총량(ng)", 
            "editable": False, # 자동 계산되므로 직접 수정 불가
            "type": "numeric",
            "valueGetter": {"function": "Number(params.data.library_concentration) * Number(params.data.library_volume) || ''"}
        },
        "library_size": {"name": "Library Size(bp)", "editable": True, "type": "numeric"},
        "index_id": {"name": "Index ID", "editable": True},
        "library_comment": {"name": "Library Comment", "editable": True},
    }

# ─────────────────────────────────────────────
# 5. Sequencing Stage
# ─────────────────────────────────────────────
class Sequencing(BaseProcessing):
    name = "sequencing"
    description = "시퀀싱 run 정보, FASTQ 경로, Q30, Seq QC 결과 관리"
    columns = {
        "seq_id": {"name": "SEQ ID", "editable": True},
        "seq_facility_type": {"name": "수행 기관구분", "editable": True, "presentation": "dropdown", "options": ["내부 진행", "외부 위탁"]},
        "platform": {"name": "Platform", "editable": True, "presentation": "dropdown", "options": ["NovaSeq 6000", "NovaSeq X", "NextSeq 550", "NextSeq 2000", "MiSeq", "기타"]},
        "run_id": {"name": "Run ID", "editable": True},
        "flowcell_id": {"name": "Flowcell ID", "editable": True},
        "read_type": {"name": "Read Type", "editable": True, "presentation": "dropdown", "options": ["SE", "PE"]},
        "read_length": {"name": "Read Length", "editable": True, "presentation": "dropdown", "options": ["50", "75", "100", "150", "151", "기타"]},
        "q30_score": {"name": "Q30 (%)", "editable": True, "type": "numeric"},
        "total_reads": {"name": "Total Reads", "editable": True, "type": "numeric"},
        "total_bases": {"name": "Total Bases", "editable": True, "type": "numeric"},
        "fastq_path": {"name": "FASTQ 경로", "editable": True},
        "seq_qc_status": {"name": "Seq QC 결과", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
        "seq_comment": {"name": "Sequencing Comment", "editable": True},
    }

# ─────────────────────────────────────────────
# 6. Analysis Stage
# ─────────────────────────────────────────────
class Analysis(BaseProcessing):
    name = "분석 진행"
    description = "Pipeline 실행, 분석 상태, 결과 경로, 담당자 관리"
    columns = {
        "analysis_status": {"name": "분석 상태", "editable": True, "presentation": "dropdown", "options": ["대기중", "분석 진행중", "분석 완료", "판독중", "최종 완료", "보류", "재분석 필요"]},
        "analyst": {"name": "분석 담당자", "editable": True},
        "pipeline_name": {"name": "Pipeline Name", "editable": True},
        "pipeline_version": {"name": "Pipeline Version", "editable": True},
        "reference_version": {"name": "Reference Version", "editable": True, "presentation": "dropdown", "options": ["hg19", "hg38", "GRCh37", "GRCh38", "기타"]},
        "analysis_start_date": {"name": "분석 시작일", "editable": True, "type": "date"},
        "analysis_end_date": {"name": "분석 완료일", "editable": True, "type": "date"},
        "result_path": {"name": "결과 경로", "editable": True},
        "analysis_qc_status": {"name": "Analysis QC", "editable": True, "presentation": "dropdown", "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"]},
        "analysis_comment": {"name": "Analysis Comment", "editable": True},
    }

# ─────────────────────────────────────────────
# 7. Report Stage
# ─────────────────────────────────────────────
class Report(BaseProcessing):
    name = "보고 진행"
    description = "보고서 발행일, 검토자, 최종 상태 관리"
    columns = {
        "report_status": {"name": "보고 상태", "editable": True, "presentation": "dropdown", "options": ["대기중", "작성중", "검토중", "수정 요청", "발행 완료", "최종 완료"]},
        "reviewer": {"name": "검토자", "editable": True},
        "reporter": {"name": "보고 담당자", "editable": True},
        "standard_report_date_01": {"name": "Std Report 발행일", "editable": True, "type": "date"},
        "final_report_date": {"name": "Final Report 발행일", "editable": True, "type": "date"},
        "report_file_path": {"name": "Report File 경로", "editable": True},
        "report_comment": {"name": "Report Comment", "editable": True},
    }

# ─────────────────────────────────────────────
# 8. Stage Registry
# ─────────────────────────────────────────────
class Processingegistry:
    """Stage들을 한 곳에서 관리. 프론트엔드에서 stage_key 기준으로 컬럼을 가져오기 쉽게 구성."""
    stages = {
        "registration": Registration(),
        "procedure": Procedure(),
        "sample_qc": SamplePreparation(),
        "library_qc": LibraryQC(),
        "sequencing": Sequencing(),
        "analysis": Analysis(),
        "report": Report(),
    }

    @classmethod
    def get_stage(cls, stage_key: str) -> BaseProcessing:
        return cls.stages.get(stage_key)

    @classmethod
    def get_stage_columns(cls, stage_key: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        stage = cls.get_stage(stage_key)
        if not stage:
            return []
            
        if isinstance(stage, Registration):
            return stage.get_columns(status=status)
        return stage.get_columns()

    @classmethod
    def get_stage_list(cls) -> List[Dict[str, str]]:
        return [
            {"id": stage_key, "name": stage.name, "description": stage.description}
            for stage_key, stage in cls.stages.items()
        ]

# ─────────────────────────────────────────────
# 9. Report Schema
# ─────────────────────────────────────────────
class ReportSchema:
    name: str = ""
    description: str = ""
    columns: Dict[str, Dict[str, Any]] = {}
    def get_columns(self) -> List[Dict[str, Any]]:
        return [{"id": col_id, **col_def} for col_id, col_def in self.columns.items()]

class ClinicalReport(ReportSchema):
    name = "Clinical Report"
    columns = {
        "report_type": {"name": "보고서 타입", "editable": True, "presentation": "dropdown", "options": ["Standard", "Advanced"]},
        "standard_report_date_01": {"name": "최종 발행일", "editable": True, "type": "date"},
        "tumor_purity": {"name": "종양 비율(%)", "editable": False},
        "mapped_reads_pct": {"name": "매핑률(%)", "editable": False},
        "pathologist_name": {"name": "판독의", "editable": True},
        "report_comment": {"name": "특이사항", "editable": True},
    }