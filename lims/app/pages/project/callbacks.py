"""
app/pages/project/callbacks.py
================================
프로젝트 관리 페이지 콜백.
"""

import io
import pandas as pd
from dash import Input, Output, State, callback_context, no_update, dcc
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from app.core.database import get_session
from app.core.id_service import IDService
from app.schema.objects import Project, Sample, ProjectMaster, ActionLog

P = "prj"


def register_callbacks(app):

    # ── 초기 로드 ─────────────────────────────────────
    @app.callback(
        Output(f"{P}-grid",   "rowData"),
        Output(f"{P}-f-code", "options"),
        Input(f"{P}-selected", "data"),
        prevent_initial_call=False,
    )
    def load(_):
        with get_session() as db:
            projects = db.query(Project).order_by(Project.created_at.desc()).all()
            rows = []
            for p in projects:
                cnt = db.query(Sample).filter(Sample.project_pk == p.id).count()
                row = {c.name: getattr(p, c.name) for c in p.__table__.columns}
                row["_sample_count"] = cnt
                for f in ("reception_date", "deadline", "created_at", "updated_at"):
                    if row.get(f): row[f] = str(row[f])
                rows.append(row)

            masters = db.query(ProjectMaster).filter(ProjectMaster.is_active == 1).all()
            opts = [{"label": m.project_label, "value": m.project_code} for m in masters]

        return rows, opts

    # ── KPI ──────────────────────────────────────────
    @app.callback(
        Output(f"{P}-kpi-total",   "children"),
        Output(f"{P}-kpi-active",  "children"),
        Output(f"{P}-kpi-done",    "children"),
        Output(f"{P}-kpi-samples", "children"),
        Input(f"{P}-grid", "rowData"),
    )
    def kpi(rows):
        if not rows: return "0","0","0","0"
        return (
            str(len(rows)),
            str(sum(1 for r in rows if r.get("current_status") == "진행중")),
            str(sum(1 for r in rows if r.get("current_status") == "완료")),
            str(sum(r.get("_sample_count", 0) for r in rows)),
        )

    # ── 검색 / 필터 ───────────────────────────────────
    @app.callback(
        Output(f"{P}-grid", "rowData", allow_duplicate=True),
        Input(f"{P}-search",        "value"),
        Input(f"{P}-filter-status", "value"),
        prevent_initial_call=True,
    )
    def filter_grid(search, status):
        with get_session() as db:
            q = db.query(Project)
            if status: q = q.filter(Project.current_status == status)
            if search:
                like = f"%{search}%"
                q = q.filter(
                    Project.project_id.ilike(like)   |
                    Project.project_name.ilike(like) |
                    Project.facility.ilike(like)
                )
            rows = []
            for p in q.order_by(Project.created_at.desc()).all():
                cnt = db.query(Sample).filter(Sample.project_pk == p.id).count()
                row = {c.name: getattr(p, c.name) for c in p.__table__.columns}
                row["_sample_count"] = cnt
                for f in ("reception_date","deadline","created_at","updated_at"):
                    if row.get(f): row[f] = str(row[f])
                rows.append(row)
        return rows

    # ── 행 선택 ──────────────────────────────────────
    @app.callback(
        Output(f"{P}-edit-btn",  "disabled"),
        Output(f"{P}-del-btn",   "disabled"),
        Output(f"{P}-selected",  "data"),
        Input(f"{P}-grid",       "selectedRows"),
    )
    def row_select(sel):
        if not sel: return True, True, no_update
        return False, False, sel[0]

    # ── 사이드 폼 토글 ────────────────────────────────
    @app.callback(
        Output(f"{P}-form-col",   "style"),
        Output(f"{P}-grid-col",   "md"),
        Output(f"{P}-form-title", "children"),
        Output(f"{P}-form-mode",  "data"),
        Output(f"{P}-f-code",     "value"),
        Output(f"{P}-f-name",     "value"),
        Output(f"{P}-f-type",     "value"),
        Output(f"{P}-f-facility", "value"),
        Output(f"{P}-f-team",     "value"),
        Output(f"{P}-f-cname",    "value"),
        Output(f"{P}-f-email",    "value"),
        Output(f"{P}-f-phone",    "value"),
        Output(f"{P}-f-rdate",    "date"),
        Output(f"{P}-f-ddate",    "date"),
        Output(f"{P}-f-price",    "value"),
        Output(f"{P}-f-comment",  "value"),
        Input(f"{P}-new-btn",    "n_clicks"),
        Input(f"{P}-edit-btn",   "n_clicks"),
        Input(f"{P}-form-close", "n_clicks"),
        State(f"{P}-selected",   "data"),
        prevent_initial_call=True,
    )
    def toggle_form(new_n, edit_n, close_n, sel):
        ctx = callback_context.triggered_id
        SHOW   = {"display": "block"}
        HIDDEN = {"display": "none"}
        blank  = (None,) * 11

        if ctx == f"{P}-form-close":
            return HIDDEN, 12, "", "new", *blank

        if ctx == f"{P}-new-btn":
            return SHOW, 8, "새 프로젝트 등록", "new", *blank

        if ctx == f"{P}-edit-btn" and sel:
            return (
                SHOW, 8, f"수정 — {sel.get('project_id','')}","edit",
                sel.get("project_code"), sel.get("project_name"), sel.get("project_type"),
                sel.get("facility"),     sel.get("client_team"),  sel.get("client_name"),
                sel.get("client_email"), sel.get("client_phone"),
                sel.get("reception_date"), sel.get("deadline"),
                sel.get("sales_unit_price"), sel.get("issue_comment"),
            )
        raise PreventUpdate

    # ── 폼 초기화 ─────────────────────────────────────
    @app.callback(
        Output(f"{P}-f-code",    "value", allow_duplicate=True),
        Output(f"{P}-f-name",    "value", allow_duplicate=True),
        Output(f"{P}-f-facility","value", allow_duplicate=True),
        Output(f"{P}-f-cname",   "value", allow_duplicate=True),
        Output(f"{P}-f-email",   "value", allow_duplicate=True),
        Output(f"{P}-f-phone",   "value", allow_duplicate=True),
        Output(f"{P}-f-price",   "value", allow_duplicate=True),
        Output(f"{P}-f-comment", "value", allow_duplicate=True),
        Input(f"{P}-form-reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_form(n):
        if not n: raise PreventUpdate
        return (None,) * 8

    # ── 저장 ─────────────────────────────────────────
    @app.callback(
        Output(f"{P}-selected",  "data",     allow_duplicate=True),
        Output(f"{P}-form-fb",   "children"),
        Output(f"{P}-toast",     "children"),
        Output(f"{P}-toast",     "is_open"),
        Output(f"{P}-toast",     "header"),
        Input(f"{P}-form-save",  "n_clicks"),
        State(f"{P}-form-mode",  "data"),
        State(f"{P}-selected",   "data"),
        State(f"{P}-f-code",     "value"),
        State(f"{P}-f-name",     "value"),
        State(f"{P}-f-type",     "value"),
        State(f"{P}-f-facility", "value"),
        State(f"{P}-f-team",     "value"),
        State(f"{P}-f-cname",    "value"),
        State(f"{P}-f-email",    "value"),
        State(f"{P}-f-phone",    "value"),
        State(f"{P}-f-rdate",    "date"),
        State(f"{P}-f-ddate",    "date"),
        State(f"{P}-f-price",    "value"),
        State(f"{P}-f-comment",  "value"),
        prevent_initial_call=True,
    )
    def save(n, mode, sel,
             code, name, ptype,
             facility, team, cname, email, phone,
             rdate, ddate, price, comment):
        if not n: raise PreventUpdate

        missing = [l for l, v in [("프로젝트 종류", code), ("프로젝트명", name),
                                    ("기관명", facility),   ("접수일", rdate)] if not v]
        if missing:
            return no_update, dbc.Alert(f"필수 항목: {', '.join(missing)}", color="warning",
                                        className="rounded-3 py-2 mt-1"), no_update, no_update, no_update
        try:
            with get_session() as db:
                svc = IDService(db)
                if mode == "new":
                    pid = svc.next_project_id(code)
                    obj = Project(
                        project_id=pid, project_code=code, project_name=name,
                        project_type=ptype or "Clinical",
                        facility=facility,   client_team=team   or "",
                        client_name=cname or "", client_email=email or "",
                        client_phone=phone or "",
                        reception_date=rdate, deadline=ddate,
                        sales_unit_price=int(price) if price else 0,
                        current_status="접수 완료", issue_comment=comment,
                        project_metadata={},
                    )
                    db.add(obj)
                    db.flush()
                    db.add(ActionLog(entity_type="project", entity_id=pid,
                                     project_pk=obj.id, action_type="CREATED",
                                     new_state="접수 완료"))
                    db.commit()
                    msg = f"프로젝트 {pid} 등록 완료"
                else:
                    pid = sel.get("project_id") if sel else None
                    obj = db.query(Project).filter(Project.project_id == pid).first()
                    if not obj: raise ValueError(f"Not found: {pid}")
                    obj.project_name     = name
                    obj.project_type     = ptype     or obj.project_type
                    obj.facility         = facility
                    obj.client_team      = team      or obj.client_team
                    obj.client_name      = cname     or obj.client_name
                    obj.client_email     = email     or obj.client_email
                    obj.client_phone     = phone     or obj.client_phone
                    obj.reception_date   = rdate
                    obj.deadline         = ddate
                    obj.sales_unit_price = int(price) if price else obj.sales_unit_price
                    obj.issue_comment    = comment
                    db.commit()
                    msg = f"프로젝트 {pid} 수정 완료"

            return {"_refresh": True}, None, msg, True, "저장 완료 ✓"
        except Exception as e:
            return no_update, dbc.Alert(f"오류: {e}", color="danger",
                                        className="rounded-3 py-2 mt-1"), str(e), True, "오류"

    # ── 삭제 ─────────────────────────────────────────
    @app.callback(
        Output(f"{P}-del-modal", "is_open"),
        Output(f"{P}-selected",  "data",    allow_duplicate=True),
        Output(f"{P}-toast",     "children", allow_duplicate=True),
        Output(f"{P}-toast",     "is_open",  allow_duplicate=True),
        Output(f"{P}-toast",     "header",   allow_duplicate=True),
        Input(f"{P}-del-btn",    "n_clicks"),
        Input(f"{P}-del-confirm","n_clicks"),
        State(f"{P}-del-modal",  "is_open"),
        State(f"{P}-selected",   "data"),
        prevent_initial_call=True,
    )
    def delete(open_n, confirm_n, is_open, sel):
        ctx = callback_context.triggered_id
        if ctx == f"{P}-del-btn":
            return True, no_update, no_update, no_update, no_update
        if ctx == f"{P}-del-confirm" and sel:
            pid = sel.get("project_id")
            try:
                with get_session() as db:
                    obj = db.query(Project).filter(Project.project_id == pid).first()
                    if obj: db.delete(obj)
                    db.commit()
                return False, {"_refresh": True}, f"{pid} 삭제 완료", True, "삭제"
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
        df  = pd.DataFrame(rows).drop(columns=["_sample_count"], errors="ignore")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="Projects")
        buf.seek(0)
        return dcc.send_bytes(buf.read(), "projects.xlsx")