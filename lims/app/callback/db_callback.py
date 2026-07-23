"""
app/callbacks/db_callbacks.py
==============================
DB read / write 공통 콜백 등록 함수.

제공:
    register_db_callbacks(app, **ids)
        - grid → DB 저장  (변경된 셀 감지 후 upsert)
        - DB → grid 로드  (페이지 진입 시 초기 데이터)
        - ActionLog 기록  (status 컬럼 변경 시 자동)

호출 방법 (페이지 callbacks.py 에서):
    from app.callbacks.db_callbacks import register_db_callbacks

    def register_callbacks(app):
        register_db_callbacks(
            app,
            grid_id     = "sample-grid",
            save_id     = "sample-save",
            entity      = "library",          # objects.py 클래스명 소문자
            pk_field    = "library_id",        # grid row 의 PK 필드명
            status_field= "current_status",    # 상태 변경 감지 필드
        )
"""

from dash import Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from sqlalchemy.orm import Session

from app.core.db import get_session          # 프로젝트 DB 세션 팩토리
from app.schema.objects import (
    Sample, Library, SequencingRun, Analysis, Report, ActionLog
)

# entity 문자열 → ORM 클래스 매핑
_ENTITY_MAP = {
    "sample":         Sample,
    "library":        Library,
    "sequencing_run": SequencingRun,
    "analysis":       Analysis,
    "report":         Report,
}

# entity → PK 필드명 기본값
_PK_FIELD = {
    "sample":         "sample_id",
    "library":        "library_id",
    "sequencing_run": "run_id",
    "analysis":       "analysis_id",
    "report":         "id",
}


def _get_orm_class(entity: str):
    cls = _ENTITY_MAP.get(entity)
    if not cls:
        raise ValueError(f"Unknown entity: {entity}. 허용값: {list(_ENTITY_MAP)}")
    return cls


def register_db_callbacks(app, **ids):
    """
    ids 키:
        grid_id       : AG Grid id
        save_id       : 저장 버튼 id
        entity        : "sample" | "library" | "sequencing_run" | "analysis" | "report"
        pk_field      : grid row dict의 PK 컬럼명 (default: entity별 자동)
        status_field  : 상태 변경 감지 컬럼명 (default: "current_status")
        notify_id     : 저장 결과 알림 컴포넌트 id (optional)
        actor_id_store: dcc.Store id — 현재 로그인 사용자 id 저장 (optional)
    """
    grid_id       = ids.get("grid_id")
    save_id       = ids.get("save_id")       or f"{grid_id}-save"
    entity        = ids.get("entity")        or "library"
    pk_field      = ids.get("pk_field")      or _PK_FIELD.get(entity, "id")
    status_field  = ids.get("status_field")  or "current_status"
    notify_id     = ids.get("notify_id")     or f"{grid_id}-notify"
    actor_store   = ids.get("actor_id_store")

    if not grid_id:
        raise ValueError("grid_id 는 필수입니다.")

    orm_cls = _get_orm_class(entity)

    # ── DB → Grid 초기 로드 ───────────────────────────
    @app.callback(
        Output(grid_id, "rowData"),
        Input(f"{grid_id}-load-trigger", "data"),   # dcc.Store 트리거
        prevent_initial_call=False,
    )
    def load_from_db(trigger):
        with get_session() as db:
            rows = db.query(orm_cls).all()
            return [_row_to_dict(r) for r in rows]

    # ── Grid → DB 저장 ────────────────────────────────
    @app.callback(
        Output(notify_id, "children", allow_duplicate=True),
        Input(save_id, "n_clicks"),
        State(grid_id, "rowData"),
        State(grid_id, "cellValueChanged"),
        *([State(actor_store, "data")] if actor_store else []),
        prevent_initial_call=True,
    )
    def save_to_db(n_clicks, row_data, changed_cells, *extra):
        if not n_clicks or not changed_cells:
            raise PreventUpdate

        actor = extra[0] if extra else None

        try:
            with get_session() as db:
                for cell in changed_cells:
                    row    = cell.get("data", {})
                    pk_val = row.get(pk_field)
                    if not pk_val:
                        continue

                    obj = db.query(orm_cls).filter(
                        getattr(orm_cls, pk_field) == pk_val
                    ).first()

                    if not obj:
                        continue

                    col      = cell.get("colId")
                    old_val  = cell.get("oldValue")
                    new_val  = cell.get("value")

                    setattr(obj, col, new_val)
                    if actor:
                        obj.updater_id = actor

                    # status 변경 시 ActionLog 기록
                    if col == status_field:
                        log = ActionLog(
                            entity_type=entity,
                            entity_id=str(pk_val),
                            action_type="STATUS_CHANGE",
                            previous_state=str(old_val),
                            new_state=str(new_val),
                            actor_id=actor,
                            **_log_fk(entity, obj),
                        )
                        db.add(log)

                db.commit()

            return _notify("저장 완료", "success")

        except Exception as e:
            return _notify(f"저장 실패: {e}", "danger")

    # ── 셀 변경 즉시 저장 (자동 저장 모드) ─────────────
    @app.callback(
        Output(notify_id, "children", allow_duplicate=True),
        Input(grid_id, "cellValueChanged"),
        *([State(actor_store, "data")] if actor_store else []),
        prevent_initial_call=True,
    )
    def autosave_cell(changed_cells, *extra):
        """
        save 버튼 없이 셀 편집 즉시 DB 반영.
        save_id 방식과 병행 가능 (둘 중 하나만 활성화).
        현재는 save_id 방식 우선 — 이 콜백은 비활성화 상태.
        활성화하려면 아래 return no_update 제거.
        """
        return no_update  # 필요 시 save_to_db 로직 재사용


# ─────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────
def _row_to_dict(obj) -> dict:
    """SQLAlchemy 모델 인스턴스 → dict (관계 제외)."""
    return {
        c.name: getattr(obj, c.name)
        for c in obj.__table__.columns
    }


def _notify(message: str, color: str = "success") -> dbc.Alert:
    return dbc.Alert(message, color=color, duration=3000, dismissable=True)


def _log_fk(entity: str, obj) -> dict:
    """ActionLog 에 넣을 FK 딕셔너리. entity 종류에 따라 자동 결정."""
    mapping = {
        "sample":         {"sample_pk":         obj.id, "project_pk": getattr(obj, "project_pk", None)},
        "library":        {"library_pk":        obj.id, "sample_pk":  getattr(obj, "sample_pk", None)},
        "sequencing_run": {"sequencing_run_pk": obj.id},
        "analysis":       {"analysis_pk":       obj.id, "project_pk": getattr(obj, "project_pk", None)},
        "report":         {"analysis_pk":       getattr(obj, "analysis_pk", None)},
    }
    return mapping.get(entity, {})