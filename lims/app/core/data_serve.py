"""
DataService
===========
Data 엔티티 등록 / 경로 조립 / 메타 조회를 담당.

파일명 규칙:
    file_name = {data_id}.{file_ext}
    file_path = {BASE_DIR}/{analysis_id}/{file_name}

    예)
    data_id   = CBNIPT-202507-0001-A001-D001
    file_ext  = bam
    file_name = CBNIPT-202507-0001-A001-D001.bam
    file_path = /data/results/CBNIPT-202507-0001-A001/CBNIPT-202507-0001-A001-D001.bam

사용 예:
    svc = DataService(db, base_dir="/data/results")

    # 파일 등록
    data = svc.register(
        analysis_id="CBNIPT-202507-0001-A001",
        file_ext="bam",
        file_type="BAM",
        file_metadata={"ref_genome": "hg38", "mean_depth": 42.3},
    )
    print(data.data_id)   # CBNIPT-202507-0001-A001-D001
    print(data.file_path) # /data/results/CBNIPT-202507-0001-A001/CBNIPT-202507-0001-A001-D001.bam

    # ID로 메타 조회
    info = svc.get_info("CBNIPT-202507-0001-A001-D001")
    # {
    #   "data_id":    "CBNIPT-202507-0001-A001-D001",
    #   "file_name":  "CBNIPT-202507-0001-A001-D001.bam",
    #   "file_path":  "/data/results/...",
    #   "file_type":  "BAM",
    #   "file_ext":   "bam",
    #   "file_size_bytes": None,
    #   "md5_checksum":    None,
    #   "is_archived":     0,
    #   "analysis_id": "CBNIPT-202507-0001-A001",
    #   "metadata":    {"ref_genome": "hg38", "mean_depth": 42.3},
    # }
"""

import os
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.schema.objects import Data, Analysis
from app.service.id_service import IDService


# 파일 타입별 기본 확장자 힌트 (override 가능)
FILE_TYPE_EXT: dict[str, str] = {
    "BAM":         "bam",
    "BAM_INDEX":   "bam.bai",
    "FASTQ":       "fastq.gz",
    "VCF":         "vcf.gz",
    "VCF_INDEX":   "vcf.gz.tbi",
    "JSON_REPORT": "json",
    "QC_HTML":     "html",
    "QC_TSV":      "tsv",
    "PPTX_REPORT": "pptx",
    "PDF_REPORT":  "pdf",
}


class DataService:
    def __init__(self, db: Session, base_dir: str = "/data/results"):
        self.db = db
        self.base_dir = base_dir
        self._id_svc = IDService(db)

    # ── 경로 조립 ─────────────────────────────────────
    def resolve_path(self, analysis_id: str, data_id: str, file_ext: str) -> tuple[str, str]:
        """
        (file_name, file_path) 반환.
        file_name = {data_id}.{file_ext}
        file_path = {base_dir}/{analysis_id}/{file_name}
        """
        file_name = f"{data_id}.{file_ext}"
        file_path = os.path.join(self.base_dir, analysis_id, file_name)
        return file_name, file_path

    # ── 등록 ─────────────────────────────────────────
    def register(
        self,
        analysis_id: str,
        file_type: str,
        file_ext: Optional[str] = None,
        file_metadata: Optional[dict] = None,
        file_size_bytes: Optional[int] = None,
        md5_checksum: Optional[str] = None,
        creator_id: Optional[str] = None,
    ) -> Data:
        """
        Data 행 생성 + 경로 자동 조립.

        file_ext 미입력 시 FILE_TYPE_EXT 에서 자동 선택.
        """
        # analysis 존재 확인
        analysis = self.db.query(Analysis).filter(Analysis.analysis_id == analysis_id).first()
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        # ext 결정
        ext = file_ext or FILE_TYPE_EXT.get(file_type, "bin")

        # ID 채번
        data_id = self._id_svc.next_data_id(analysis_id)

        # 경로 조립
        file_name, file_path = self.resolve_path(analysis_id, data_id, ext)

        data = Data(
            data_id=data_id,
            analysis_pk=analysis.id,
            analysis_id=analysis_id,
            file_ext=ext,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            md5_checksum=md5_checksum,
            is_archived=0,
            file_metadata=file_metadata or {},
            creator_id=creator_id,
            updater_id=creator_id,
        )
        self.db.add(data)
        self.db.flush()   # data.id 확보 (commit은 호출자가)
        return data

    # ── 조회 ─────────────────────────────────────────
    def get_info(self, data_id: str) -> dict:
        """
        data_id 기준 key-value 메타 딕셔너리 반환.
        없으면 빈 dict.
        """
        row = self.db.query(Data).filter(Data.data_id == data_id).first()
        if not row:
            return {}
        return {
            "data_id":         row.data_id,
            "file_name":       row.file_name,
            "file_path":       row.file_path,
            "file_type":       row.file_type,
            "file_ext":        row.file_ext,
            "file_size_bytes": row.file_size_bytes,
            "md5_checksum":    row.md5_checksum,
            "is_archived":     row.is_archived,
            "analysis_id":     row.analysis_id,
            "created_at":      row.created_at.isoformat() if row.created_at else None,
            "updated_at":      row.updated_at.isoformat() if row.updated_at else None,
            "metadata":        row.file_metadata,
        }

    def get_info_by_analysis(self, analysis_id: str) -> list[dict]:
        """analysis_id 하위 전체 Data 목록 반환"""
        rows = self.db.query(Data).filter(Data.analysis_id == analysis_id).all()
        return [self.get_info(r.data_id) for r in rows]

    # ── 무결성 업데이트 ───────────────────────────────
    def update_checksum(self, data_id: str, md5: str, size_bytes: int) -> None:
        """파이프라인 완료 후 md5 / size 기록"""
        row = self.db.query(Data).filter(Data.data_id == data_id).first()
        if row:
            row.md5_checksum = md5
            row.file_size_bytes = size_bytes
            self.db.flush()

    def update_metadata(self, data_id: str, extra: dict) -> None:
        """file_metadata에 key-value merge"""
        row = self.db.query(Data).filter(Data.data_id == data_id).first()
        if row:
            merged = {**row.file_metadata, **extra}
            row.file_metadata = merged
            self.db.flush()

    def archive(self, data_id: str) -> None:
        """is_archived = 1 로 전환"""
        row = self.db.query(Data).filter(Data.data_id == data_id).first()
        if row:
            row.is_archived = 1
            self.db.flush()