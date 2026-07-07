from typing import Dict, List, Optional

from app.schema.process import (
    BaseProcessing,
    Registration,
    Procedure,
    SamplePreparation,
    LibraryQC,
    Sequencing,
    Analysis,
    Report,
    ClinicalReport,
)


class WorkflowTemplate:
    """
    특정 패널/버전에 맞게 Stage들을 묶어놓은 워크플로우 템플릿.

    수정:
        - stages를 dict로 유지하되 stage_order를 별도로 관리
        - Kanban에서 순서 기반 이동이 가능하도록 helper 함수 추가
    """

    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version

        # 기존 유지
        self.stages: Dict[str, BaseProcessing] = {}

        # 신규: 칸반 컬럼 순서 보장용
        self.stage_order: List[str] = []

    def add_stage(self, stage: BaseProcessing):
        """
        Stage 객체 추가.
        stage.name을 현재 상태명으로 사용.
        """
        self.stages[stage.name] = stage

        # 신규: stage 순서 보존
        if stage.name not in self.stage_order:
            self.stage_order.append(stage.name)

    def get_stage_config(self, stage_name: str) -> dict:
        """
        UI(Kanban, Modal 등)에서 렌더링하기 쉬운 포맷으로 변환.
        """
        stage_obj = self.stages.get(stage_name)

        if stage_obj:
            return {
                "name": stage_obj.name,
                "description": stage_obj.description,
                "columns": stage_obj.get_columns(),
            }

        return {
            "name": stage_name,
            "description": "",
            "columns": [],
        }

    # 신규
    def get_stage_names(self) -> List[str]:
        """
        Kanban 컬럼 순서 반환.
        """
        return list(self.stage_order)

    # 신규
    def get_stage_index(self, stage_name: str) -> int:
        """
        현재 stage의 index 반환.
        없는 stage는 0으로 처리.
        """
        try:
            return self.stage_order.index(stage_name)
        except ValueError:
            return 0

    # 신규
    def get_next_stage_name(self, stage_name: str) -> str:
        """
        현재 stage 기준 다음 stage 반환.
        마지막 stage면 자기 자신 반환.
        """
        idx = self.get_stage_index(stage_name)

        if idx + 1 < len(self.stage_order):
            return self.stage_order[idx + 1]

        return stage_name

    # 신규
    def is_backward_move(self, current_stage: str, next_stage: str) -> bool:
        """
        역방향 이동 여부 판단.
        """
        return self.get_stage_index(next_stage) < self.get_stage_index(current_stage)


# ─────────────────────────────────────────────
# 1. 기본 NGS 워크플로우
# ─────────────────────────────────────────────
class StandardWorkflow(WorkflowTemplate):
    def __init__(self):
        super().__init__(name="Standard_NGS", version="1.0")

        self.add_stage(Registration())
        self.add_stage(Procedure())
        self.add_stage(SamplePreparation())
        self.add_stage(LibraryQC())
        self.add_stage(Sequencing())
        self.add_stage(Analysis())
        self.add_stage(Report())


# ─────────────────────────────────────────────
# 2. WGS 워크플로우
# ─────────────────────────────────────────────
class WGSWorkflow(WorkflowTemplate):
    """
    신규: WGS 전용 workflow.
    현재는 StandardWorkflow와 동일하지만,
    추후 WGS 전용 컬럼/단계를 따로 확장 가능.
    """

    def __init__(self):
        super().__init__(name="WGS", version="1.0")

        self.add_stage(Registration())
        self.add_stage(Procedure())
        self.add_stage(SamplePreparation())
        self.add_stage(LibraryQC())
        self.add_stage(Sequencing())
        self.add_stage(Analysis())
        self.add_stage(Report())


# ─────────────────────────────────────────────
# 3. WES 워크플로우
# ─────────────────────────────────────────────
class WESWorkflow(WorkflowTemplate):
    """
    신규: WES 전용 workflow.
    """

    def __init__(self):
        super().__init__(name="WES", version="1.0")

        self.add_stage(Registration())
        self.add_stage(Procedure())
        self.add_stage(SamplePreparation())
        self.add_stage(LibraryQC())
        self.add_stage(Sequencing())
        self.add_stage(Analysis())
        self.add_stage(Report())


# ─────────────────────────────────────────────
# 4. WTS 워크플로우
# ─────────────────────────────────────────────
class WTSWorkflow(WorkflowTemplate):
    """
    신규: WTS/RNA 기반 workflow.
    """

    def __init__(self):
        super().__init__(name="WTS", version="1.0")

        self.add_stage(Registration())
        self.add_stage(Procedure())
        self.add_stage(SamplePreparation())
        self.add_stage(LibraryQC())
        self.add_stage(Sequencing())
        self.add_stage(Analysis())
        self.add_stage(Report())


# ─────────────────────────────────────────────
# 5. TSO500 워크플로우
# ─────────────────────────────────────────────
class TSO500Workflow(WorkflowTemplate):
    """
    신규: TSO500 전용 workflow.

    DNA/RNA 동시 진행이 있을 수 있으므로,
    우선 Standard와 동일하게 두고 이후 ClinicalReport, Fusion, TMB/MSI 등을
    별도 stage 또는 report config로 확장하면 됨.
    """

    def __init__(self):
        super().__init__(name="TSO500", version="1.0")

        self.add_stage(Registration())
        self.add_stage(Procedure())
        self.add_stage(SamplePreparation())
        self.add_stage(LibraryQC())
        self.add_stage(Sequencing())
        self.add_stage(Analysis())
        self.add_stage(Report())


# ─────────────────────────────────────────────
# 6. 워크플로우 매니저
# ─────────────────────────────────────────────
class WorkflowManager:
    """
    샘플의 Target Panel이나 버전에 따라 적절한 Workflow 객체를 반환.
    """

    def __init__(self):
        # 수정: panel_name 기준 workflow 매핑 추가
        self.workflows: Dict[str, WorkflowTemplate] = {
            "DEFAULT": StandardWorkflow(),
            "WGS": WGSWorkflow(),
            "WES": WESWorkflow(),
            "WTS": WTSWorkflow(),
            "TSO500": TSO500Workflow(),
        }

        self.reports = {
            "Clinical Report": ClinicalReport(),
        }

    def get_workflow(self, panel_name: Optional[str]) -> WorkflowTemplate:
        """
        panel_name이 없거나 ALL이면 DEFAULT workflow 반환.
        """
        if not panel_name or panel_name == "ALL":
            return self.workflows["DEFAULT"]

        return self.workflows.get(panel_name, self.workflows["DEFAULT"])

    def get_stage_names(self, panel_name: Optional[str]) -> List[str]:
        """
        신규: Kanban에서 사용할 stage 목록 반환.
        """
        workflow = self.get_workflow(panel_name)
        return workflow.get_stage_names()

    def get_stage_config(self, panel_name: Optional[str], stage_name: str) -> dict:
        """
        신규: Kanban modal에서 사용할 stage column config 반환.
        """
        workflow = self.get_workflow(panel_name)
        return workflow.get_stage_config(stage_name)

    def get_next_stage_name(self, panel_name: Optional[str], stage_name: str) -> str:
        """
        신규: 선택 row 다음 단계 이동용.
        """
        workflow = self.get_workflow(panel_name)
        return workflow.get_next_stage_name(stage_name)

    def is_backward_move(
        self,
        panel_name: Optional[str],
        current_stage: str,
        next_stage: str,
    ) -> bool:
        """
        신규: 역방향 이동 차단용.
        """
        workflow = self.get_workflow(panel_name)
        return workflow.is_backward_move(current_stage, next_stage)

    def get_report_config(self, report_name: str) -> dict:
        report = self.reports.get(report_name)

        if report:
            return {
                "columns": report.get_columns(),
                "description": report.description,
            }

        return {"columns": []}


# 전역 인스턴스
workflow_manager = WorkflowManager()