"""
app/pages/sample/callbacks.py
================================
샘플 접수 페이지 콜백.
"""

import io
import pandas as pd
from dash import Input, Output, State, callback_context, no_update, dcc
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from app.core.database import get_session
from app.core.id_service import IDService
from app.schema.objects import Project, Sample, ActionLog

P = "smp"


def register_callbacks(app):

    # ── 프로젝트 드롭다운 옵션 로드 ──────────────────
    @app.callback(
        Output(f"{P}-project-select", "options"),
        Input(f"{P}-project-id",      "data"),
        prevent_initial_call=False,
    )
    def load_project_options(_):
        with get_session() as db:
            projects = db.query(Project).order_by(Project.created_at.desc()).all()
            return [
                {"label": f"{p.project_id}  |  {p.project_name}  ({p.facility})",
                 "value": p.project_id}
                for p in projects
            ]

    # ── 프로젝트 선택 → 샘플 로드 + 버튼/배지 활성 ──
    @app.callback(
        Output(f"{P}-grid",           "rowData"),
        Output(f"{P}-project-id",     "data"),
        Output(f"{P}-project-badge",  "children"),
        Output(f"{P}-new-btn",        "disabled"),
        Input(f"{P}-project-select",  "value"),
    )
    def on_project_select(project_id):
        if not project_id:
            return [], None, None, True

        with get_session() as db:
            p = db.query(Project).filter(Project.project_id == project_id).first()
            samples = db.query(Sample).filter(Sample.project_id == project_id).all()
            rows = []
            for s in samples:
                row = {c.name: getattr(s, c.name) for c in s.__table__.columns}
                for f in ("created_at", "updated_at"):
                    if row.get(f): row[f] = str(row[f])
                rows.append(row)

        status_color = {"접수 완료": "primary", "진행중": "success", "완료": "secondary", "취소": "danger"}
        badge = dbc.Badge(
            f"{p.current_status}  |  {p.facility}  |  샘플 {len(rows)}건",
            color=status_color.get(p.current_status, "secondary"),
            className="rounded-pill px-3 py-2 ms-2",
        ) if p else None

        return rows, project_id, badge, False

    # ── KPI ──────────────────────────────────────────
    @app.callback(
        Output(f"{P}-kpi-total",    "children"),
        Output(f"{P}-kpi-received", "children"),
        Output(f"{P}-kpi-pending",  "children"),
        Output(f"{P}-kpi-issue",    "children"),
        Input(f"{P}-grid", "rowData"),
    )
    def kpi(rows):
        if not rows: return "0","0","0","0"
        return (
            str(len(rows)),
            str(sum(1 for r in rows if r.get("sample_received") == "입고 완료")),
            str(sum(1 for r in rows if r.get("sample_received") == "대기중")),
            str(sum(1 for r in rows if r.get("issue_comment"))),
        )

    # ── 검색 / 필터 ───────────────────────────────────
    @app.callback(
        Output(f"{P}-grid", "rowData", allow_duplicate=True),
        Input(f"{P}-search",          "value"),
        Input(f"{P}-filter-received", "value"),
        Input(f"{P}-filter-progress", "value"),
        State(f"{P}-project-id",      "data"),
        prevent_initial_call=True,
    )
    def filter_grid(search, received, progress, project_id):
        if not project_id: raise PreventUpdate
        with get_session() as db:
            q = db.query(Sample).filter(Sample.project_id == project_id)
            if received: q = q.filter(Sample.sample_received  == received)
            if progress: q = q.filter(Sample.test_progress    == progress)
            if search:
                like = f"%{search}%"
                q = q.filter(Sample.sample_id.ilike(like) | Sample.sample_name.ilike(like))
            rows = []
            for s in q.all():
                row = {c.name: getattr(s, c.name) for c in s.__table__.columns}
                for f in ("created_at","updated_at"):
                    if row.get(f): row[f] = str(row[f])
                rows.append(row)
        return rows

    # ── 행 선택 ──────────────────────────────────────
    @app.callback(
        Output(f"{P}-edit-btn", "disabled"),
        Output(f"{P}-del-btn",  "disabled"),
        Output(f"{P}-selected", "data"),
        Input(f"{P}-grid",      "selectedRows"),
    )
    def row_select(sel):
        if not sel: return True, True, no_update
        return False, False, sel[0]

    # ── 사이드 폼 토글 ────────────────────────────────
    @app.callback(
        Output(f"{P}-form-col",          "style"),
        Output(f"{P}-grid-col",          "md"),
        Output(f"{P}-form-title",        "children"),
        Output(f"{P}-form-mode",         "data"),
        Output(f"{P}-form-project-info", "children"),
        Output(f"{P}-f-name",     "value"),
        Output(f"{P}-f-origin",   "value"),
        Output(f"{P}-f-pairing",  "value"),
        Output(f"{P}-f-outside",  "value"),
        Output(f"{P}-f-received", "value"),
        Output(f"{P}-f-receiver", "value"),
        Output(f"{P}-f-visual",   "value"),
        Output(f"{P}-f-storage",  "value"),
        Output(f"{P}-f-volume",   "value"),
        Output(f"{P}-f-progress", "value"),
        Output(f"{P}-f-comment",  "value"),
        Input(f"{P}-new-btn",    "n_clicks"),
        Input(f"{P}-edit-btn",   "n_clicks"),
        Input(f"{P}-form-close", "n_clicks"),
        State(f"{P}-selected",   "data"),
        State(f"{P}-project-id", "data"),
        prevent_initial_call=True,
    )
    def toggle_form(new_n, edit_n, close_n, sel, project_id):
        ctx    = callback_context.triggered_id
        SHOW   = {"display": "block"}
        HIDDEN = {"display": "none"}

        def proj_info():
            if not project_id: return "프로젝트 미선택"
            with get_session() as db:
                p = db.query(Project).filter(Project.project_id == project_id).first()
            return f"Project: {project_id}  |  {p.project_name if p else ''}" if p else project_id

        blank = (None,) * 11

        if ctx == f"{P}-form-close":
            return HIDDEN, 12, "", "new", "", *blank

        if ctx == f"{P}-new-btn":
            return SHOW, 8, "새 샘플 등록", "new", proj_info(), *blank

        if ctx == f"{P}-edit-btn" and sel:
            return (
                SHOW, 8, f"수정 — {sel.get('sample_id','')}", "edit", proj_info(),
                sel.get("sample_name"),   sel.get("origin"),          sel.get("pairing_info"),
                sel.get("outside_id"),    sel.get("sample_received"), sel.get("receiver_name"),
                sel.get("visual_inspection"), sel.get("storage_location"),
                sel.get("initial_volume"), sel.get("test_progress"),  sel.get("issue_comment"),
            )
        raise PreventUpdate

    # ── 폼 초기화 ─────────────────────────────────────
    @app.callback(
        Output(f"{P}-f-name",    "value", allow_duplicate=True),
        Output(f"{P}-f-origin",  "value", allow_duplicate=True),
        Output(f"{P}-f-outside", "value", allow_duplicate=True),
        Output(f"{P}-f-storage", "value", allow_duplicate=True),
        Output(f"{P}-f-volume",  "value", allow_duplicate=True),
        Output(f"{P}-f-comment", "value", allow_duplicate=True),
        Input(f"{P}-form-reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_form(n):
        if not n: raise PreventUpdate
        return (None,) * 6

    # ── 저장 ─────────────────────────────────────────
    @app.callback(
        Output(f"{P}-grid",     "rowData",  allow_duplicate=True),
        Output(f"{P}-form-fb",  "children"),
        Output(f"{P}-toast",    "children"),
        Output(f"{P}-toast",    "is_open"),
        Output(f"{P}-toast",    "header"),
        Input(f"{P}-form-save", "n_clicks"),
        State(f"{P}-form-mode", "data"),
        State(f"{P}-selected",  "data"),
        State(f"{P}-project-id","data"),
        State(f"{P}-f-name",    "value"),
        State(f"{P}-f-origin",  "value"),
        State(f"{P}-f-pairing", "value"),
        State(f"{P}-f-outside", "value"),
        State(f"{P}-f-received","value"),
        State(f"{P}-f-receiver","value"),
        State(f"{P}-f-visual",  "value"),
        State(f"{P}-f-storage", "value"),
        State(f"{P}-f-volume",  "value"),
        State(f"{P}-f-progress","value"),
        State(f"{P}-f-comment", "value"),
        prevent_initial_call=True,
    )
    def save(n, mode, sel, project_id,
             name, origin, pairing, outside,
             received, receiver, visual, storage, volume, progress, comment):
        if not n: raise PreventUpdate
        if not project_id:
            return no_update, dbc.Alert("프로젝트를 먼저 선택하세요.", color="warning",
                                        className="rounded-3 py-2 mt-1"), no_update, no_update, no_update

        missing = [l for l, v in [("샘플명", name), ("검체 유래", origin)] if not v]
        if missing:
            return no_update, dbc.Alert(f"필수 항목: {', '.join(missing)}", color="warning",
                                        className="rounded-3 py-2 mt-1"), no_update, no_update, no_update
        try:
            with get_session() as db:
                svc = IDService(db)
                p   = db.query(Project).filter(Project.project_id == project_id).first()
                if not p: raise ValueError(f"Project not found: {project_id}")

                if mode == "new":
                    sid = svc.next_sample_id(project_id)
                    obj = Sample(
                        sample_id=sid,        project_pk=p.id,     project_id=project_id,
                        sample_name=name,     origin=origin,       pairing_info=pairing or "N/A",
                        outside_id=outside,
                        sample_received=received  or "대기중",
                        receiver_name=receiver,
                        visual_inspection=visual  or "양호",
                        storage_location=storage,
                        initial_volume=float(volume) if volume else None,
                        test_progress=progress or "진행",
                        issue_comment=comment,
                        current_status="접수 완료",
                        sample_metadata={},
                    )
                    db.add(obj)
                    db.flush()
                    db.add(ActionLog(
                        entity_type="sample", entity_id=sid,
                        project_pk=p.id, sample_pk=obj.id,
                        action_type="CREATED", new_state="접수 완료",
                    ))
                    db.commit()
                    msg = f"샘플 {sid} 등록 완료"
                else:
                    sid = sel.get("sample_id") if sel else None
                    obj = db.query(Sample).filter(Sample.sample_id == sid).first()
                    if not obj: raise ValueError(f"Not found: {sid}")
                    obj.sample_name       = name
                    obj.origin            = origin
                    obj.pairing_info      = pairing  or obj.pairing_info
                    obj.outside_id        = outside
                    obj.sample_received   = received or obj.sample_received
                    obj.receiver_name     = receiver
                    obj.visual_inspection = visual   or obj.visual_inspection
                    obj.storage_location  = storage
                    obj.initial_volume    = float(volume) if volume else obj.initial_volume
                    obj.test_progress     = progress or obj.test_progress
                    obj.issue_comment     = comment
                    db.commit()
                    msg = f"샘플 {sid} 수정 완료"

                # 갱신된 목록 반환
                samples = db.query(Sample).filter(Sample.project_id == project_id).all()
                rows = []
                for s in samples:
                    row = {c.name: getattr(s, c.name) for c in s.__table__.columns}
                    for f in ("created_at","updated_at"):
                        if row.get(f): row[f] = str(row[f])
                    rows.append(row)

            return rows, None, msg, True, "저장 완료 ✓"
        except Exception as e:
            return no_update, dbc.Alert(f"오류: {e}", color="danger",
                                        className="rounded-3 py-2 mt-1"), str(e), True, "오류"

    # ── 삭제 ─────────────────────────────────────────
    @app.callback(
        Output(f"{P}-del-modal", "is_open"),
        Output(f"{P}-grid",      "rowData",   allow_duplicate=True),
        Output(f"{P}-toast",     "children",  allow_duplicate=True),
        Output(f"{P}-toast",     "is_open",   allow_duplicate=True),
        Output(f"{P}-toast",     "header",    allow_duplicate=True),
        Input(f"{P}-del-btn",    "n_clicks"),
        Input(f"{P}-del-confirm","n_clicks"),
        State(f"{P}-del-modal",  "is_open"),
        State(f"{P}-selected",   "data"),
        State(f"{P}-project-id", "data"),
        prevent_initial_call=True,
    )
    def delete(open_n, confirm_n, is_open, sel, project_id):
        ctx = callback_context.triggered_id
        if ctx == f"{P}-del-btn":
            return True, no_update, no_update, no_update, no_update
        if ctx == f"{P}-del-confirm" and sel:
            sid = sel.get("sample_id")
            try:
                with get_session() as db:
                    obj = db.query(Sample).filter(Sample.sample_id == sid).first()
                    if obj: db.delete(obj)
                    db.commit()
                    samples = db.query(Sample).filter(Sample.project_id == project_id).all()
                    rows = [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in samples]
                return False, rows, f"{sid} 삭제 완료", True, "삭제"
            except Exception as e:
                return False, no_update, str(e), True, "오류"
        raise PreventUpdate

    # ── Excel 다운로드 ────────────────────────────────
    @app.callback(
        Output(f"{P}-download", "data"),
        Input(f"{P}-export",    "n_clicks"),
        State(f"{P}-grid",      "rowData"),
        prevent_initial_call=True,
    )
    def export(n, rows):
        if not n or not rows: raise PreventUpdate
        df  = pd.DataFrame(rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="Samples")
        buf.seek(0)
        return dcc.send_bytes(buf.read(), "samples.xlsx")