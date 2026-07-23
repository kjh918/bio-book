"""
ID 채번 서비스
==============
ID 규칙:
  Project       : {PROJECT_CODE}-{YYYYMM}-{seq:04d}   예) CBNIPT-202507-0001
  Sample        : {project_id}-S{seq:03d}              예) CBNIPT-202507-0001-S001
  Library       : {sample_id}-L{seq:03d}               예) CBNIPT-202507-0001-S001-L001
  SequencingRun : {PANEL_CODE}-{YYYYMM}-{seq:04d}      예) TSO500-202507-0001
  Analysis      : {project_id}-A{seq:03d}              예) CBNIPT-202507-0001-A001
  Data          : {analysis_id}-D{seq:03d}             예) CBNIPT-202507-0001-A001-D001

project_code / panel_code 정규화:
  공백 → '_', 소문자 → 대문자  예) "NGS Service" → "NGS_SERVICE"
"""

import re
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.schema.objects import Project, Sample, Library, SequencingRun, Analysis, Data


def _kst_yyyymm() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m")


def _normalize_code(code: str) -> str:
    """'NGS Service' → 'NGS_SERVICE'"""
    return re.sub(r"\s+", "_", code.strip()).upper()


class IDService:
    def __init__(self, db: Session):
        self.db = db

    # ── Project ──────────────────────────────────────
    def next_project_id(self, project_code: str) -> str:
        """{PROJECT_CODE}-{YYYYMM}-{seq:04d}"""
        code = _normalize_code(project_code)
        yyyymm = _kst_yyyymm()
        prefix = f"{code}-{yyyymm}-"
        count = (
            self.db.query(func.count(Project.id))
            .filter(Project.project_id.like(f"{prefix}%"))
            .scalar()
        ) or 0
        return f"{prefix}{count + 1:04d}"

    # ── Sample ───────────────────────────────────────
    def next_sample_id(self, project_id: str) -> str:
        """{project_id}-S{seq:03d}"""
        count = (
            self.db.query(func.count(Sample.id))
            .filter(Sample.project_id == project_id)
            .scalar()
        ) or 0
        return f"{project_id}-S{count + 1:03d}"

    # ── Library ──────────────────────────────────────
    def next_library_id(self, sample_id: str) -> str:
        """{sample_id}-L{seq:03d}"""
        count = (
            self.db.query(func.count(Library.id))
            .filter(Library.sample_id == sample_id)
            .scalar()
        ) or 0
        return f"{sample_id}-L{count + 1:03d}"

    # ── SequencingRun ────────────────────────────────
    def next_run_id(self, panel_code: str) -> str:
        """{PANEL_CODE}-{YYYYMM}-{seq:04d}"""
        code = _normalize_code(panel_code)
        yyyymm = _kst_yyyymm()
        prefix = f"{code}-{yyyymm}-"
        count = (
            self.db.query(func.count(SequencingRun.id))
            .filter(SequencingRun.run_id.like(f"{prefix}%"))
            .scalar()
        ) or 0
        return f"{prefix}{count + 1:04d}"

    # ── Analysis ─────────────────────────────────────
    def next_analysis_id(self, project_id: str) -> str:
        """{project_id}-A{seq:03d}"""
        count = (
            self.db.query(func.count(Analysis.id))
            .filter(Analysis.project_id == project_id)
            .scalar()
        ) or 0
        return f"{project_id}-A{count + 1:03d}"

    # ── Data ─────────────────────────────────────────
    def next_data_id(self, analysis_id: str) -> str:
        """{analysis_id}-D{seq:03d}"""
        count = (
            self.db.query(func.count(Data.id))
            .filter(Data.analysis_id == analysis_id)
            .scalar()
        ) or 0
        return f"{analysis_id}-D{count + 1:03d}"