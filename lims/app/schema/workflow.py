"""
WorkflowTemplate / WorkflowManager
====================================
Project-based LIMS에 맞게 재편.

Stage 순서:
  검체 접수 → Sample QC → Library 제작 → Library QC
  → Sequencing → 분석 진행 → 보고 진행

각 Stage는 objects.py 의 엔티티와 1:1 대응:
  Registration    → Project / Sample
  SampleQC        → Library (nucleic acid QC)
  LibraryPrep     → Library (library 제작/QC)
  Sequencing      → SequencingRun + LibrarySequencingRun
  Analysis        → Analysis
  Report          → Report
"""

from typing import Dict, List, Optional

from app.schema.process import (
    BaseProcessing,
    Registration,
    SamplePreparation,
    LibraryQC,
    Sequencing,
    Analysis,
    Report,
    ClinicalReport,
)


class WorkflowTemplate:
    """
    패널/버전에 따른 Stage 묶음.

    stages: { stage_name: BaseProcessing }
    stage_order: Kanban 컬럼 순서 보장용 리스트
    """

    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.stages: Dict[str, BaseProcessing] = {}
        self.stage_order: List[str] = []

    def add_stage(self, stage: BaseProcessing):
        self.stages[stage.name] = stage
        if stage.name not in self.stage_order:
            self.stage_order.append(stage.name)

    def get_stage_config(self, stage_name: str) -> dict:
        stage_obj = self.stages.get(stage_name)
        if stage_obj:
            return {
                "name": stage_obj.name,
                "description": stage_obj.description,
                "columns": stage_obj.get_columns(),
            }
        return {"name": stage_name, "description": "", "columns": []}

    def get_stage_names(self) -> List[str]:
        return list(self.stage_order)

    def get_stage_index(self, stage_name: str) -> int:
        try:
            return self.stage_order.index(stage_name)
        except ValueError:
            return 0

    def get_next_stage_name(self, stage_name: str) -> str:
        idx = self.get_stage_index(stage_name)
        if idx + 1 < len(self.stage_order):
            return self.stage_order[idx + 1]
        return stage_name

    def is_backward_move(self, current_stage: str, next_stage: str) -> bool:
        return self.get_stage_index(next_stage) < self.get_stage_index(current_stage)


# ─────────────────────────────────────────────
# Stage 순서 정의 (모든 패널 공통 기본값)
# ─────────────────────────────────────────────
#   Registration  → 검체 접수 (Project/Sample 등록)
#   SamplePrep    → Sample QC (핵산 QC)
#   LibraryQC     → Library 제작 + Library QC
#   Sequencing    → Sequencing Run
#   Analysis      → 분석 진행
#   Report        → 보고 진행
# ─────────────────────────────────────────────

class StandardWorkflow(WorkflowTemplate):
    def __init__(self):
        super().__init__(name="Standard_NGS", version="2.0")
        for stage in [Registration(), SamplePreparation(), LibraryQC(),
                      Sequencing(), Analysis(), Report()]:
            self.add_stage(stage)


class WGSWorkflow(WorkflowTemplate):
    def __init__(self):
        super().__init__(name="WGS", version="2.0")
        for stage in [Registration(), SamplePreparation(), LibraryQC(),
                      Sequencing(), Analysis(), Report()]:
            self.add_stage(stage)


class WESWorkflow(WorkflowTemplate):
    def __init__(self):
        super().__init__(name="WES", version="2.0")
        for stage in [Registration(), SamplePreparation(), LibraryQC(),
                      Sequencing(), Analysis(), Report()]:
            self.add_stage(stage)


class WTSWorkflow(WorkflowTemplate):
    def __init__(self):
        super().__init__(name="WTS", version="2.0")
        for stage in [Registration(), SamplePreparation(), LibraryQC(),
                      Sequencing(), Analysis(), Report()]:
            self.add_stage(stage)


class TSO500Workflow(WorkflowTemplate):
    """
    DNA+RNA 동시 진행 가능.
    Library가 DNA/RNA 각각 생성되고 Analysis도 분리 실행.
    Report는 ClinicalReport 타입 사용.
    """
    def __init__(self):
        super().__init__(name="TSO500", version="2.0")
        for stage in [Registration(), SamplePreparation(), LibraryQC(),
                      Sequencing(), Analysis(), Report()]:
            self.add_stage(stage)


# ─────────────────────────────────────────────
# WorkflowManager
# ─────────────────────────────────────────────
class WorkflowManager:
    """
    target_panel → WorkflowTemplate 매핑.
    Kanban stage 순서 / 다음 단계 이동 / 역방향 차단 로직 제공.
    """

    def __init__(self):
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
        if not panel_name or panel_name == "ALL":
            return self.workflows["DEFAULT"]
        return self.workflows.get(panel_name, self.workflows["DEFAULT"])

    def get_stage_names(self, panel_name: Optional[str]) -> List[str]:
        return self.get_workflow(panel_name).get_stage_names()

    def get_stage_config(self, panel_name: Optional[str], stage_name: str) -> dict:
        return self.get_workflow(panel_name).get_stage_config(stage_name)

    def get_next_stage_name(self, panel_name: Optional[str], stage_name: str) -> str:
        return self.get_workflow(panel_name).get_next_stage_name(stage_name)

    def is_backward_move(
        self,
        panel_name: Optional[str],
        current_stage: str,
        next_stage: str,
    ) -> bool:
        return self.get_workflow(panel_name).is_backward_move(current_stage, next_stage)

    def get_report_config(self, report_name: str) -> dict:
        report = self.reports.get(report_name)
        if report:
            return {"columns": report.get_columns(), "description": report.description}
        return {"columns": []}


# 전역 인스턴스
workflow_manager = WorkflowManager()