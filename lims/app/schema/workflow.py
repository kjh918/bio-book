from typing import Dict
from app.schema.process import (
    BaseStage, RegistrationPending, RegistrationComplete, 
    QCProcessing, SequencingProcessing, AnalysisProcessing, BillingPending,
    ClinicalReport
)

class WorkflowTemplate:
    """특정 패널/버전에 맞게 Stage들을 묶어놓은 워크플로우 템플릿"""
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.stages: Dict[str, BaseStage] = {}
        
    def add_stage(self, stage: BaseStage):
        self.stages[stage.name] = stage

    def get_stage_config(self, stage_name: str) -> dict:
        """UI(Kanban 등)에서 렌더링하기 쉽게 포맷 변환"""
        stage_obj = self.stages.get(stage_name)
        if stage_obj:
            return {"columns": stage_obj.get_columns(), "description": stage_obj.description}
        return {"columns": []}

# ── 1. 기본 NGS 워크플로우 (v1.0) ──
class StandardWorkflow(WorkflowTemplate):
    def __init__(self):
        super().__init__(name="Standard_NGS", version="1.0")
        # 객체를 생성해서 조립합니다.
        self.add_stage(RegistrationPending())
        self.add_stage(RegistrationComplete())
        self.add_stage(QCProcessing())
        self.add_stage(SequencingProcessing())
        self.add_stage(AnalysisProcessing())
        self.add_stage(BillingPending())


# ── 2. 워크플로우 매니저 (패널 라우터) ──
class WorkflowManager:
    """샘플의 Target Panel이나 버전에 따라 적절한 Workflow 객체를 반환합니다."""
    def __init__(self):
        self.workflows = {
            "DEFAULT": StandardWorkflow(),
            # 🚀 향후 TSO500, WES 등의 클래스(상속)를 만들어 매핑하기만 하면 됩니다.
        }
        
        self.reports = {
            "Clinical Report": ClinicalReport()
        }
        
    def get_workflow(self, panel_name: str) -> WorkflowTemplate:
        return self.workflows.get(panel_name, self.workflows["DEFAULT"])
        
    def get_report_config(self, report_name: str) -> dict:
        report = self.reports.get(report_name)
        return {"columns": report.get_columns(), "description": report.description} if report else {"columns": []}

# 전역에서 쉽게 불러다 쓸 인스턴스
workflow_manager = WorkflowManager()