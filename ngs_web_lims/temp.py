import argparse
from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models._schema import Sample, Analysis


def reset_analysis_records(
    all_records: bool = False,
    sample_ids: list[str] | None = None,
    pair_id: str | None = None,
    commit: bool = False,
    delete_row: bool = False,
    reset_sample_status: str | None = None,
):
    """
    Analysis 테이블 초기화 스크립트.

    기본 동작:
      - dry-run: 실제 DB 반영 안 함
      - Analysis row는 유지
      - analysis_results / pipeline / 날짜 / 상태 필드만 초기화

    옵션:
      --delete-row           Analysis row 자체 삭제
      --sample-status VALUE  Sample.current_status도 VALUE로 변경
      --commit               실제 DB 반영
    """

    if not all_records and not sample_ids and not pair_id:
        raise ValueError("초기화 범위를 지정해야 합니다. --all, --sample-id, --pair-id 중 하나를 사용하세요.")

    db = SessionLocal()

    try:
        query = (
            db.query(Analysis)
            .options(joinedload(Analysis.sample))
            .join(Sample, Analysis.sample_id == Sample.id)
        )

        if not all_records:
            filters = []

            if sample_ids:
                filters.append(Sample.sample_id.in_(sample_ids))

            if pair_id:
                # ACC-260626-01-001 입력 시
                # ACC-260626-01-001-DNA / ACC-260626-01-001-RNA 둘 다 잡음
                filters.append(Sample.sample_id.like(f"{pair_id}%"))

            for condition in filters:
                query = query.filter(condition)

        records = query.all()

        if not records:
            print("초기화 대상 Analysis record가 없습니다.")
            return

        print(f"초기화 대상: {len(records)}건")
        print("-" * 80)

        for analysis in records:
            sample = analysis.sample
            sample_label = sample.sample_id if sample else f"sample_pk={analysis.sample_id}"

            print(
                f"[대상] {sample_label} | "
                f"analysis_id={analysis.id} | "
                f"pipeline={analysis.pipeline} | "
                f"status={analysis.analysis_status}"
            )

            if delete_row:
                db.delete(analysis)
            else:
                analysis.analysis_status = "대기중"
                analysis.analyst = None

                analysis.pipeline = None
                analysis.pipeline_version = None
                analysis.raw_data_pathway = None
                analysis.work_dir_pathway = None

                analysis.analysis_run_start_date = None
                analysis.analysis_run_end_date = None

                analysis.standard_report_date_01 = None
                analysis.advanced_report_date_01 = None

                # Dash / webhook에서 "결과 없음"으로 판단하기 쉽게 None 권장
                analysis.analysis_results = None

            if sample and reset_sample_status:
                sample.current_status = reset_sample_status

        print("-" * 80)

        if commit:
            db.commit()
            print("DB 초기화 반영 완료.")
        else:
            db.rollback()
            print("DRY-RUN 완료. 실제 DB에는 반영하지 않았습니다. 반영하려면 --commit을 붙이세요.")

    except Exception as e:
        db.rollback()
        print(f"초기화 중 오류 발생: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LIMS Analysis 결과 초기화")

    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="모든 Analysis 결과 초기화")
    scope.add_argument(
        "--sample-id",
        action="append",
        dest="sample_ids",
        help="초기화할 sample_id. 여러 개면 --sample-id를 반복 사용",
    )
    scope.add_argument(
        "--pair-id",
        help="Pair ID 기준 초기화. 예: ACC-260626-01-001 입력 시 DNA/RNA 둘 다 초기화",
    )

    parser.add_argument("--commit", action="store_true", help="실제 DB에 반영")
    parser.add_argument("--delete-row", action="store_true", help="Analysis row 자체 삭제")
    parser.add_argument(
        "--sample-status",
        default=None,
        help='Sample.current_status도 같이 변경. 예: "시퀀싱 완료", "분석 대기", "접수 완료"',
    )

    args = parser.parse_args()

    reset_analysis_records(
        all_records=args.all,
        sample_ids=args.sample_ids,
        pair_id=args.pair_id,
        commit=args.commit,
        delete_row=args.delete_row,
        reset_sample_status=args.sample_status,
    )
