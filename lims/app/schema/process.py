from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from typing import Dict, Any, List
from app.schema.objects import Base

class StageRules:
    """LIMS 시스템 전체에서 사용되는 비즈니스 규칙 및 상태값 정의"""

    # 1. 상태 및 단계 (Kanban Stages)
    KANBAN_STAGES = [
        "접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "완료", "보류/실패"
    ]

    # 2. 단계별 액션 버튼 매핑 룰 (버튼 텍스트, 색상, 다음 단계)
    STAGE_ACTIONS = {
        "접수 대기": {"text": "✅ 접수 심사하기", "color": "outline-dark", "next": "접수 완료"},
        "접수 완료": {"text": "QC 시작 ➡️", "color": "warning", "next": "QC 진행"},
        "QC 진행": {"text": "시퀀싱 시작 ➡️", "color": "primary", "next": "시퀀싱 진행"},
        "시퀀싱 진행": {"text": "분석 시작 ➡️", "color": "success", "next": "분석 진행"},
        "분석 진행": {"text": "정산 단계로 ➡️", "color": "dark", "next": "정산 대기"},
        "정산 대기": {"text": "✅ 최종 완료", "color": "secondary", "next": "완료"}
    }

    # 3. 육안 검수(Visual Inspection) 판정 옵션 룰
    INSPECTION_OPTIONS = [
        {"label": "대기중", "value": ""},
        {"label": "✅ 적합 (모두 일치)", "value": "Pass"},
        {"label": "⚠️ 보류 (용량 부족)", "value": "Hold_Volume"},
        {"label": "⚠️ 보류 (농도 미달)", "value": "Hold_Conc"},      # 언제든 쉽게 옵션 추가 가능!
        {"label": "❌ 불량 (라벨 불일치)", "value": "Fail_Label"},
        {"label": "❌ 불량 (튜브 파손)", "value": "Fail_Broken"}
    ]

class BaseStage:
    name: str = ""
    description: str = ""
    columns: Dict[str, Dict[str, Any]] = {}

    def __init__(self, name: str = None, description: str = None):
        if name: self.name = name
        if description: self.description = description

    def get_columns(self) -> List[Dict[str, Any]]:
        """프론트엔드(ag-Grid)에서 요구하는 리스트 형식으로 변환"""
        return [{"id": col_id, **col_def} for col_id, col_def in self.columns.items()]

    def get_column(self, col_id: str) -> Dict[str, Any]:
        return self.columns.get(col_id, {})

    def stage_rules(self):
        """각 Stage별로 적용되는 룰을 반환"""
        return {
            "kanban_stages": StageRules.KANBAN_STAGES,
            "stage_actions": StageRules.STAGE_ACTIONS,
            "inspection_options": StageRules.INSPECTION_OPTIONS
        }
# ── 단계 (Stages) 객체 ──
class RegistrationStage(BaseStage):
    """
    접수 상태(status)에 따라 표시되는 컬럼을 동적으로 반환합니다.
    """
    name = "검체 접수"
    
    # 1. 모든 가능한 컬럼 정의
    all_columns = {
        "sample_received": {"name": "입고 확인", "editable": True, "presentation": "dropdown", "options": ["대기중", "입고 완료"]},
        "receiver_name": {"name": "입고 담당자", "editable": True},
        "storage_location": {"name": "보관 위치", "editable": True},
        "visual_inspection": {"name": "실물 상태 👁️", "editable": True, "presentation": "dropdown", "options": [opt["value"] for opt in BaseStage.stage_rules()["inspection_options"] if opt["value"]]},
        "initial_volume": {"name": "초기 용량(uL)", "editable": True, "type": "numeric"},
        "test_progress": {"name": "검사진행 여부", "editable": True},
        "dead_line": {"name": "Dead Line", "editable": True, "type": "date"},
    }

    def get_columns(self, status: str = None) -> List[Dict[str, Any]]:
        """
        status: "대기중" -> 입고 관련 컬럼만 표시
                "입고 완료" -> 접수 완료 후 처리 컬럼들 표시
        """
        if status == "대기중":
            target_keys = ["sample_received", "receiver_name", "storage_location", "visual_inspection"]
        elif status == "입고 완료":
            target_keys = ["initial_volume", "test_progress", "dead_line"]
        else:
            target_keys = list(self.all_columns.keys())
            
        return [{"id": k, **self.all_columns[k]} for k in target_keys]


from typing import Dict, Any, List, Optional


class BaseStage:
    name: str = ""
    description: str = ""
    columns: Dict[str, Dict[str, Any]] = {}

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None):
        if name:
            self.name = name
        if description:
            self.description = description

    def get_columns(self) -> List[Dict[str, Any]]:
        """프론트엔드(ag-Grid)에서 요구하는 리스트 형식으로 변환"""
        return [{"id": col_id, **col_def} for col_id, col_def in self.columns.items()]

    def get_column(self, col_id: str) -> Dict[str, Any]:
        return self.columns.get(col_id, {})

    # 수정: RegistrationStage에서 BaseStage.stage_rules()처럼 호출 가능하도록 staticmethod 처리
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
class RegistrationStage(BaseStage):
    """
    검체 입고 및 접수 단계.
    status에 따라 표시 컬럼을 동적으로 변경.
    """

    name = "검체 접수"
    description = "검체 입고 확인, 보관 위치, 실물 상태 확인 단계"

    all_columns = {
        "sample_received": {
            "name": "입고 확인",
            "editable": True,
            "presentation": "dropdown",
            "options": ["대기중", "입고 완료"],
        },
        "receiver_name": {
            "name": "입고 담당자",
            "editable": True,
        },
        "storage_location": {
            "name": "보관 위치",
            "editable": True,
        },
        "visual_inspection": {
            "name": "실물 상태 👁️",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                opt["value"]
                for opt in BaseStage.stage_rules()["inspection_options"]
                if opt["value"]
            ],
        },

        # 수정: 입고 완료 이후 처리 컬럼
        "initial_volume": {
            "name": "초기 용량(uL)",
            "editable": True,
            "type": "numeric",
        },
        "test_progress": {
            "name": "검사진행 여부",
            "editable": True,
            "presentation": "dropdown",
            "options": ["진행", "보류", "취소"],
        },
        "dead_line": {
            "name": "Dead Line",
            "editable": True,
            "type": "date",
        },
    }

    def get_columns(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        status:
            대기중     -> 입고 관련 컬럼
            입고 완료  -> 접수 완료 후 처리 컬럼
            None       -> 전체 컬럼
        """
        if status == "대기중":
            target_keys = [
                "sample_received",
                "receiver_name",
                "storage_location",
                "visual_inspection",
            ]
        elif status == "입고 완료":
            target_keys = [
                "initial_volume",
                "test_progress",
                "dead_line",
            ]
        else:
            target_keys = list(self.all_columns.keys())

        return [{"id": k, **self.all_columns[k]} for k in target_keys]


# ─────────────────────────────────────────────
# 2. 절차 진행 Stage
# ─────────────────────────────────────────────
class ProcedureProcessing(BaseStage):
    """
    신규: 검체별 전체 절차 진행 상태 관리.
    WGS/WES/WTS처럼 동일 검체에서 여러 검사 요청이 있을 때,
    각 검사 요청 단위의 진행 상태를 관리하는 용도.
    """

    name = "절차 진행"
    description = "검사 요청, 재검 여부, 외부 위탁 여부, 진행 상태 관리"

    columns = {
        # 신규
        "analysis_request_id": {
            "name": "검사 요청 ID",
            "editable": False,
        },
        "target_panel": {
            "name": "Target Panel",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "WGS",
                "WES",
                "WTS",
                "RNA-seq",
                "TSO500",
                "CBNIPT",
                "기타",
            ],
        },
        "assay_type": {
            "name": "Assay Type",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "DNA",
                "RNA",
                "DNA+RNA",
                "cfDNA",
                "gDNA",
                "기타",
            ],
        },
        "request_status": {
            "name": "요청 상태",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "접수 완료",
                "QC 대기",
                "QC 진행중",
                "Library 대기",
                "Sequencing 대기",
                "분석 대기",
                "보고 대기",
                "최종 완료",
                "보류",
                "취소",
            ],
        },
        "is_rerun": {
            "name": "재검 여부",
            "editable": True,
            "presentation": "dropdown",
            "options": ["No", "Yes"],
        },
        "rerun_reason": {
            "name": "재검 사유",
            "editable": True,
        },
        "outsourcing_status": {
            "name": "외부 위탁 여부",
            "editable": True,
            "presentation": "dropdown",
            "options": ["내부 진행", "외부 위탁", "해당 없음"],
        },
        "procedure_comment": {
            "name": "절차 Comment",
            "editable": True,
        },
    }


# ─────────────────────────────────────────────
# 3. 검체 QC Stage
# ─────────────────────────────────────────────
class SampleQCProcessing(BaseStage):
    """
    수정: 기존 QCProcessing을 검체 QC 중심으로 분리.
    DNA/RNA 농도, 총량, 순도, RIN/DIN/DV200 관리.
    """

    name = "검체 QC"
    description = "DNA/RNA 추출물 QC 및 농도/순도/총량 확인"

    columns = {
        "nucleic_acid_type": {
            "name": "핵산 종류",
            "editable": True,
            "presentation": "dropdown",
            "options": ["DNA", "RNA", "DNA+RNA", "cfDNA", "기타"],
        },

        # DNA QC
        "dna_qc": {
            "name": "DNA QC",
            "editable": True,
            "presentation": "dropdown",
            "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"],
        },
        "dna_concentration": {
            "name": "DNA 농도(ng/uL)",
            "editable": True,
            "type": "numeric",
        },
        "dna_volume": {
            "name": "DNA 용량(uL)",
            "editable": True,
            "type": "numeric",
        },
        "dna_total_amount": {
            "name": "DNA 총량(ng)",
            "editable": True,
            "type": "numeric",
        },
        "purity_260_280": {
            "name": "A260/280",
            "editable": True,
            "type": "numeric",
        },
        "purity_260_230": {
            "name": "A260/230",
            "editable": True,
            "type": "numeric",
        },
        "din": {
            "name": "DIN",
            "editable": True,
            "type": "numeric",
        },

        # RNA QC
        "rna_qc": {
            "name": "RNA QC",
            "editable": True,
            "presentation": "dropdown",
            "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"],
        },
        "rna_concentration": {
            "name": "RNA 농도(ng/uL)",
            "editable": True,
            "type": "numeric",
        },
        "rna_volume": {
            "name": "RNA 용량(uL)",
            "editable": True,
            "type": "numeric",
        },
        "rna_total_amount": {
            "name": "RNA 총량(ng)",
            "editable": True,
            "type": "numeric",
        },
        "dv200": {
            "name": "DV200 (%)",
            "editable": True,
            "type": "numeric",
        },
        "rin": {
            "name": "RIN",
            "editable": True,
            "type": "numeric",
        },
        "qc_comment": {
            "name": "QC Comment",
            "editable": True,
        },
    }


# ─────────────────────────────────────────────
# 4. Library QC Stage
# ─────────────────────────────────────────────
class LibraryQCProcessing(BaseStage):
    """
    신규: Library 제작 및 Library QC 단계.
    WGS/WES/WTS/Panel 별 library 결과가 달라질 수 있으므로 별도 Stage로 분리.
    """

    name = "Library QC"
    description = "Library 제작, 농도, size, yield, library QC 결과 관리"

    columns = {
        "library_id": {
            "name": "Library ID",
            "editable": True,
        },
        "library_method": {
            "name": "Library Method",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "WGS",
                "WES",
                "RNA-seq",
                "Target Panel",
                "Amplicon",
                "Low-pass WGS",
                "기타",
            ],
        },
        "library_qc": {
            "name": "Library QC",
            "editable": True,
            "presentation": "dropdown",
            "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"],
        },
        "library_concentration": {
            "name": "Library 농도(ng/uL)",
            "editable": True,
            "type": "numeric",
        },
        "library_molarity": {
            "name": "Library 농도(nM)",
            "editable": True,
            "type": "numeric",
        },
        "library_volume": {
            "name": "Library 용량(uL)",
            "editable": True,
            "type": "numeric",
        },
        "library_total_amount": {
            "name": "Library 총량(ng)",
            "editable": True,
            "type": "numeric",
        },
        "library_size": {
            "name": "Library Size(bp)",
            "editable": True,
            "type": "numeric",
        },
        "index_id": {
            "name": "Index ID",
            "editable": True,
        },
        "library_comment": {
            "name": "Library Comment",
            "editable": True,
        },
    }


# ─────────────────────────────────────────────
# 5. Sequencing Stage
# ─────────────────────────────────────────────
class SequencingProcessing(BaseStage):
    """
    수정: 시퀀싱 진행 + Seq QC를 포함.
    """

    name = "시퀀싱 진행"
    description = "시퀀싱 run 정보, FASTQ 경로, Q30, Seq QC 결과 관리"

    columns = {
        "seq_id": {
            "name": "SEQ ID",
            "editable": True,
        },
        "seq_facility_type": {
            "name": "수행 기관구분",
            "editable": True,
            "presentation": "dropdown",
            "options": ["내부 진행", "외부 위탁"],
        },
        "platform": {
            "name": "Platform",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "NovaSeq 6000",
                "NovaSeq X",
                "NextSeq 550",
                "NextSeq 2000",
                "MiSeq",
                "기타",
            ],
        },
        "run_id": {
            "name": "Run ID",
            "editable": True,
        },
        "flowcell_id": {
            "name": "Flowcell ID",
            "editable": True,
        },
        "read_type": {
            "name": "Read Type",
            "editable": True,
            "presentation": "dropdown",
            "options": ["SE", "PE"],
        },
        "read_length": {
            "name": "Read Length",
            "editable": True,
            "presentation": "dropdown",
            "options": ["50", "75", "100", "150", "151", "기타"],
        },
        "q30_score": {
            "name": "Q30 (%)",
            "editable": True,
            "type": "numeric",
        },
        "total_reads": {
            "name": "Total Reads",
            "editable": True,
            "type": "numeric",
        },
        "total_bases": {
            "name": "Total Bases",
            "editable": True,
            "type": "numeric",
        },
        "fastq_path": {
            "name": "FASTQ 경로",
            "editable": True,
        },
        "seq_qc_status": {
            "name": "Seq QC 결과",
            "editable": True,
            "presentation": "dropdown",
            "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"],
        },
        "seq_comment": {
            "name": "Sequencing Comment",
            "editable": True,
        },
    }


# ─────────────────────────────────────────────
# 6. Analysis Stage
# ─────────────────────────────────────────────
class AnalysisProcessing(BaseStage):
    """
    수정: 분석 진행 상태와 분석 결과 경로/버전 관리.
    """

    name = "분석 진행"
    description = "Pipeline 실행, 분석 상태, 결과 경로, 담당자 관리"

    columns = {
        "analysis_status": {
            "name": "분석 상태",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "대기중",
                "분석 진행중",
                "분석 완료",
                "판독중",
                "최종 완료",
                "보류",
                "재분석 필요",
            ],
        },
        "analyst": {
            "name": "분석 담당자",
            "editable": True,
        },
        "pipeline_name": {
            "name": "Pipeline Name",
            "editable": True,
        },
        "pipeline_version": {
            "name": "Pipeline Version",
            "editable": True,
        },
        "reference_version": {
            "name": "Reference Version",
            "editable": True,
            "presentation": "dropdown",
            "options": ["hg19", "hg38", "GRCh37", "GRCh38", "기타"],
        },
        "analysis_start_date": {
            "name": "분석 시작일",
            "editable": True,
            "type": "date",
        },
        "analysis_end_date": {
            "name": "분석 완료일",
            "editable": True,
            "type": "date",
        },
        "result_path": {
            "name": "결과 경로",
            "editable": True,
        },
        "analysis_qc_status": {
            "name": "Analysis QC",
            "editable": True,
            "presentation": "dropdown",
            "options": ["PASS", "FAIL", "HOLD", "RE-RUN", "PENDING"],
        },
        "analysis_comment": {
            "name": "Analysis Comment",
            "editable": True,
        },
    }


# ─────────────────────────────────────────────
# 7. Report Stage
# ─────────────────────────────────────────────
class ReportProcessing(BaseStage):
    """
    신규: 보고서 발행 및 최종 완료 단계.
    """

    name = "보고 진행"
    description = "보고서 발행일, 검토자, 최종 상태 관리"

    columns = {
        "report_status": {
            "name": "보고 상태",
            "editable": True,
            "presentation": "dropdown",
            "options": [
                "대기중",
                "작성중",
                "검토중",
                "수정 요청",
                "발행 완료",
                "최종 완료",
            ],
        },
        "reviewer": {
            "name": "검토자",
            "editable": True,
        },
        "reporter": {
            "name": "보고 담당자",
            "editable": True,
        },
        "standard_report_date_01": {
            "name": "Std Report 발행일",
            "editable": True,
            "type": "date",
        },
        "final_report_date": {
            "name": "Final Report 발행일",
            "editable": True,
            "type": "date",
        },
        "report_file_path": {
            "name": "Report File 경로",
            "editable": True,
        },
        "report_comment": {
            "name": "Report Comment",
            "editable": True,
        },
    }


# ─────────────────────────────────────────────
# 8. Stage Registry
# ─────────────────────────────────────────────
class StageRegistry:
    """
    신규: Stage들을 한 곳에서 관리.
    프론트엔드에서 stage_key 기준으로 컬럼을 가져오기 쉽게 구성.
    """

    stages = {
        "registration": RegistrationStage(),
        "procedure": ProcedureProcessing(),
        "sample_qc": SampleQCProcessing(),
        "library_qc": LibraryQCProcessing(),
        "sequencing": SequencingProcessing(),
        "analysis": AnalysisProcessing(),
        "report": ReportProcessing(),
    }

    @classmethod
    def get_stage(cls, stage_key: str) -> BaseStage:
        return cls.stages.get(stage_key)

    @classmethod
    def get_stage_columns(
        cls,
        stage_key: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stage = cls.get_stage(stage_key)

        if not stage:
            return []

        # 수정: RegistrationStage만 status 기반 동적 컬럼 처리
        if isinstance(stage, RegistrationStage):
            return stage.get_columns(status=status)

        return stage.get_columns()

    @classmethod
    def get_stage_list(cls) -> List[Dict[str, str]]:
        return [
            {
                "id": stage_key,
                "name": stage.name,
                "description": stage.description,
            }
            for stage_key, stage in cls.stages.items()
        ]

# ── 리포트 양식 객체 ──
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