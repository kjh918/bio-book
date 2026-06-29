"""
gmc_tso_clinical_report.py

TSO500 Clinical Report 생성기.
- Sample.analysis.analysis_results (JSON) → parse_json_like() 로 파싱
- Small Variants: VAF / Depth / Consequence 기준으로 필터링 후 보고서에 포함
- QC, TMB, MSI, Small_Variants, Gene_Amplifications, Splice_Variants, Fusions 포함
- Jinja2 → HTML → WeasyPrint → PDF 다운로드
"""

from __future__ import annotations
import os, base64, traceback
from datetime import datetime
from typing import Any

from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

from app.core.database import SessionLocal
from app.models._schema import Sample
from app.pages.base import LimsDashApp


# ============================================================
# Small Variants 필터링 규칙
# ============================================================
# 제외 조건 (하나라도 해당되면 보고서에서 제외)
#
#  1. VAF < VAF_MIN_THRESHOLD  → 너무 낮은 변이 분율 (artifact 가능성)
#  2. DP  < DEPTH_MIN          → 커버리지 부족 (신뢰도 낮음)
#  3. Consequence가 EXCLUDE_CONSEQUENCES 에 포함
#     → synonymous_variant (동의 변이) 등 임상 의미 없는 변이 제외
#
# 포함 조건 (아래 우선순위로 "임상적 의의 있는 변이"만 보고서에 실음)
#  - clinically_significant_consequences 에 포함되거나
#  - hotspot == True 이거나
#  - VAF >= VAF_REPORT_THRESHOLD
# ============================================================

VAF_MIN_THRESHOLD    = 0.03   # 3% 미만은 무조건 제외
DEPTH_MIN            = 100    # 100x 미만 커버리지는 제외

EXCLUDE_CONSEQUENCES = {
    "synonymous_variant",
    "stop_retained_variant",
    "start_retained_variant",
    "3_prime_UTR_variant",
    "5_prime_UTR_variant",
    "intron_variant",
    "intergenic_variant",
    "upstream_gene_variant",
    "downstream_gene_variant",
    "non_coding_transcript_exon_variant",
}

INCLUDE_CONSEQUENCES = {          # 이 중 하나면 VAF·Depth 조건 완화 (hotspot처럼 취급)
    "missense_variant",
    "nonsense_variant",             # stop_gained
    "stop_gained",
    "frameshift_variant",
    "splice_acceptor_variant",
    "splice_donor_variant",
    "splice_region_variant",
    "inframe_insertion",
    "inframe_deletion",
    "protein_altering_variant",
    "transcript_ablation",
}

VAF_REPORT_THRESHOLD = 0.05    # include_consequences 에 포함되어도 이 값 이상이어야 포함

def parse_json_like(value):
    """
    DB에 저장된 analysis_results를 안전하게 복구하고 빈 값이나 NA를 재귀적으로 제거합니다.
    작은따옴표가 포함된 파이썬 dict 형태의 문자열도 완벽하게 파싱합니다.
    """
    if isinstance(value, dict):
        return {k: parse_json_like(v) for k, v in value.items() if parse_json_like(v) is not None and parse_json_like(v) != []}

    if isinstance(value, list):
        return [parse_json_like(v) for v in value if parse_json_like(v) is not None]

    if isinstance(value, str):
        s = value.strip()
        if not s or s.upper() in ["NA", "N/A", "NONE", "NULL"]:
            return None

        # dict/list처럼 생긴 문자열만 파싱 시도
        if s.startswith("{") or s.startswith("["):
            try:
                # 1. 표준 JSON 파싱 시도
                return parse_json_like(json.loads(s))
            except Exception:
                try:
                    # 2. Python dict 문자열(작은따옴표, null, nan 등) 파싱 시도
                    s_safe = s.replace("null", "None").replace("true", "True").replace("false", "False").replace("nan", "None")
                    return parse_json_like(ast.literal_eval(s_safe))
                except Exception:
                    # 3. 정규식으로 따옴표 강제 교체 후 최후의 JSON 파싱 시도
                    try:
                        s_json = re.sub(r"'([^']*)'", r'"\1"', s)
                        return parse_json_like(json.loads(s_json))
                    except:
                        return s
        return s

    return value



def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(str(val).replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def filter_small_variants(variants: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    (included, excluded) 튜플을 반환한다.
    included: 보고서에 실릴 변이
    excluded: 제외된 변이 (필터 사유 기록)
    """
    included, excluded = [], []

    for v in variants:
        # ── 값 추출 ────────────────────────────────────────
        vaf = _to_float(v.get("VAF") or v.get("vaf") or v.get("allele_frequency") or 0)
        dp  = _to_float(v.get("DP")  or v.get("depth") or v.get("Depth") or 0)
        # Consequence 는 콤마/슬래시로 복수 표기될 수 있음 → set으로 파싱
        raw_csq = str(v.get("Consequence") or v.get("consequence") or v.get("variant_type") or "")
        csq_set = {c.strip().lower() for c in raw_csq.replace("/", ",").split(",") if c.strip()}
        is_hotspot = str(v.get("hotspot") or v.get("Hotspot") or "").lower() in ("true", "yes", "1")

        reason = None

        # ── 제외 조건 ──────────────────────────────────────
        if vaf < VAF_MIN_THRESHOLD:
            reason = f"VAF {vaf:.3f} < {VAF_MIN_THRESHOLD}"
        elif dp < DEPTH_MIN:
            reason = f"Depth {int(dp)} < {DEPTH_MIN}"
        elif csq_set and csq_set.issubset(EXCLUDE_CONSEQUENCES):
            reason = f"Consequence 제외 ({', '.join(csq_set)})"
        # ── 포함 조건 ──────────────────────────────────────
        elif not is_hotspot and not csq_set.intersection(INCLUDE_CONSEQUENCES):
            if vaf < VAF_REPORT_THRESHOLD:
                reason = f"임상적 의의 없는 변이 (VAF {vaf:.3f})"

        if reason:
            row = dict(v)
            row["_filter_reason"] = reason
            excluded.append(row)
        else:
            included.append(dict(v))

    return included, excluded


# ============================================================
# HTML 렌더링 헬퍼
# ============================================================

def _kv_rows(items: list[tuple[str, str]]) -> str:
    """항목명 / 값 행 쌍 → HTML <tr> 문자열 반환."""
    rows = ""
    for label, value in items:
        rows += f"""
        <tr>
          <td style="text-align:left;font-weight:bold;color:rgba(0,0,0,255)!important;
                     border-bottom:1px solid;border-color:#eaeaea;">{label}</td>
          <td style="text-align:right;border-bottom:1px solid;border-color:#eaeaea;">{value or '-'}</td>
        </tr>"""
    return rows


def _info_table(caption: str, rows_html: str) -> str:
    return f"""
    <table class="table table-condensed"
           style="font-size:10px;font-family:Arial;">
      <caption style="font-size:initial!important;">{caption}</caption>
      <thead><tr><th></th><th></th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>"""


def _variant_table(title: str, variants: list[dict], color: str = "#06615c") -> str:
    if not variants:
        return f'<p style="color:#888;font-size:10px;">보고할 변이 없음</p>'

    keys = [k for k in variants[0].keys() if not k.startswith("_")]
    header = "".join(
        f'<th style="background:{color};color:#fff;padding:4px 6px;font-size:9px;">{k}</th>'
        for k in keys)
    body = ""
    for v in variants:
        cols = "".join(
            f'<td style="padding:3px 6px;font-size:9px;border-bottom:1px solid #e0e0e0;">'
            f'{v.get(k, "")}</td>'
            for k in keys)
        body += f"<tr>{cols}</tr>"

    return f"""
    <div style="margin-bottom:18px;">
      <div style="font-size:13px;font-weight:bold;color:{color};margin-bottom:6px;">{title}</div>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-family:Arial;">
          <thead><tr>{header}</tr></thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    </div>"""


def _qc_metric_rows(qc_list: list[dict]) -> str:
    rows = ""
    for item in qc_list:
        rows += f"""
        <tr>
          <td style="text-align:left;width:16em;font-weight:bold;color:rgba(0,0,0,255)!important;
                     border-bottom:1px solid;border-top:1px solid;border-color:#d6d6d6;">
            {item.get('Metric', '')}</td>
          <td style="text-align:right;border-bottom:1px solid;border-top:1px solid;border-color:#d6d6d6;">
            {item.get('Value', '')}</td>
        </tr>"""
    return rows


# ============================================================
# 보고서 HTML 생성
# ============================================================

def build_report_html(s: Sample, logo_data_uri: str = "") -> str:
    """Sample 객체 → 완성된 HTML 문자열."""

    # ── 분석 데이터 파싱 ────────────────────────────────────
    raw = getattr(getattr(s, "analysis", None), "analysis_results", None)
    data: dict = {}
    if raw:
        parsed = parse_json_like(raw)
        if isinstance(parsed, dict):
            # flatten (metrics / variants 중첩 구조 처리)
            flat = {}
            for k, v in parsed.items():
                if k in ("metrics", "variants") and isinstance(v, dict):
                    flat.update(v)
                else:
                    flat[k] = v
            data = flat

    order = s.order

    # ── QC 지표 ────────────────────────────────────────────
    qc_list: list[dict] = []
    for qc_key in ("QC", "Run_QC_Metrics"):
        section = data.get(qc_key)
        if isinstance(section, dict):
            for m_key, m_val in section.items():
                if isinstance(m_val, dict):
                    qc_list.append({
                        "Metric": m_val.get("metric", m_key),
                        "Value":  m_val.get("value", m_val.get("Value", ""))
                    })
                else:
                    qc_list.append({"Metric": m_key, "Value": str(m_val)})

    # ── Biomarker 섹션 ─────────────────────────────────────
    def _get_dict(key: str) -> dict:
        v = data.get(key)
        return v if isinstance(v, dict) else {}

    tmb = _get_dict("TMB")
    msi = _get_dict("MSI")

    def _get_list(key: str) -> list:
        v = data.get(key)
        return v if isinstance(v, list) else []

    raw_sv   = _get_list("Small_Variants")
    raw_ga   = _get_list("Gene_Amplifications")
    raw_spl  = _get_list("Splice_Variants")
    raw_fus  = _get_list("Fusions")

    included_sv, excluded_sv = filter_small_variants(raw_sv)

    # ── Panel metadata ──────────────────────────────────────
    meta = s.panel_metadata or {}

    # ── 날짜 ───────────────────────────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    recept_date = str(order.reception_date) if order and order.reception_date else "-"

    # ── 좌측 패널 구성 ──────────────────────────────────────
    patient_rows = _kv_rows([
        ("Patient Name",   s.sample_name),
        ("Patient ID",     s.outside_id_1 or s.sample_id),
        ("Cancer type",    s.cancer_type or "-"),
        ("Specimen type",  s.specimen or "-"),
    ])

    order_rows = _kv_rows([
        ("Medical facility", order.facility   if order else "-"),
        ("Client team",      order.client_team if order else "-"),
        ("Physician",        order.client_name if order else "-"),
        ("Date of order",    recept_date),
    ])

    analysis_obj = getattr(s, "analysis", None)
    pathologist  = meta.get("pathologist_name") or (
        getattr(analysis_obj, "pathologist_name", None) if analysis_obj else None) or "-"
    analyst      = meta.get("analyst") or "-"
    pipeline     = meta.get("pipeline") or "-"
    pipeline_ver = meta.get("pipeline_version") or "-"
    report_date  = meta.get("standard_report_date_01") or today

    case_rows = _kv_rows([
        ("Panel",           s.target_panel or "-"),
        ("Pipeline",        f"{pipeline} {pipeline_ver}".strip()),
        ("Pathologist",     pathologist),
        ("Analyst",         analyst),
        ("Date of Receipt", recept_date),
        ("Date of report",  report_date),
    ])

    qc_rows_html = _qc_metric_rows(qc_list) if qc_list else "<tr><td colspan='2'>QC 데이터 없음</td></tr>"

    # ── 우측 패널 구성 ──────────────────────────────────────
    def _biomarker_block(title: str, d: dict) -> str:
        if not d:
            return ""
        rows = ""
        for k, v in d.items():
            rows += (f'<div style="font-size:10px;margin-top:6px;">'
                     f'<span style="font-weight:bold;">{k.replace("_"," ")}:</span>'
                     f' <span style="font-size:11px;font-weight:bold;">{v}</span></div>')
        return f"""
        <div style="font-size:17px;font-weight:bold;color:#000;margin-top:20px;">{title}</div>
        <hr style="border:solid 1px #d6d6d6;margin-bottom:10px;margin-top:5px;">
        {rows}
        <hr style="border:solid 1px #d6d6d6;margin-bottom:5px;margin-top:10px;">"""

    biomarker_html  = _variant_table("Small Variants (Filtered)", included_sv)
    biomarker_html += _biomarker_block("Tumor Mutational Burden (TMB)", tmb)
    biomarker_html += _biomarker_block("Microsatellite Instability (MSI)", msi)
    if raw_ga:
        biomarker_html += _variant_table("Gene Amplifications", raw_ga, "#4f46e5")
    if raw_spl:
        biomarker_html += _variant_table("Splice Variants", raw_spl, "#d97706")
    if raw_fus:
        biomarker_html += _variant_table("Fusions", raw_fus, "#9333ea")

    # ── 필터 제외 내역 (부록) ──────────────────────────────
    excluded_html = ""
    if excluded_sv:
        rows_ex = ""
        for v in excluded_sv:
            reason = v.pop("_filter_reason", "")
            cols = "".join(
                f'<td style="padding:3px 6px;font-size:8px;border-bottom:1px solid #eee;">{v.get(k,"")}</td>'
                for k in [kk for kk in v.keys() if not kk.startswith("_")][:6])
            rows_ex += f"<tr>{cols}<td style='font-size:8px;color:#c0392b;padding:3px 6px;'>{reason}</td></tr>"

        ex_keys = [k for k in (excluded_sv[0].keys() if excluded_sv else []) if not k.startswith("_")][:6]
        ex_header = "".join(
            f'<th style="background:#888;color:#fff;padding:3px 6px;font-size:8px;">{k}</th>'
            for k in ex_keys) + '<th style="background:#888;color:#fff;font-size:8px;">제외 사유</th>'

        excluded_html = f"""
        <div style="page-break-before:always;padding-top:20px;">
          <div style="font-size:14px;font-weight:bold;color:#555;margin-bottom:8px;">
            APPENDIX — 필터링 제외 Small Variants ({len(excluded_sv)}건)</div>
          <table style="width:100%;border-collapse:collapse;font-family:Arial;">
            <thead><tr>{ex_header}</tr></thead>
            <tbody>{rows_ex}</tbody>
          </table>
        </div>"""

    # ── 최종 HTML ─────────────────────────────────────────
    logo_tag = (f'<img src="{logo_data_uri}" width="70px" '
                f'style="display:block;margin:auto 0 auto auto;">'
                if logo_data_uri else "")

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-size:12px; font-family:Arial; }}
  h1   {{ font-size:18px; font-weight:bold; }}
  h2   {{ font-size:14px; font-weight:bold; }}
  caption {{ font-size:initial!important; font-weight:bold; color:black; }}
  .table {{ width:100%; border-collapse:collapse; }}
  .table-condensed td, .table-condensed th {{ padding:4px 6px; }}
</style>
</head>
<body>

<!-- HEADER -->
<div style="float:left;width:75%;font-size:25px;font-weight:bold;color:black;vertical-align:bottom;">
  NGS Cancer Panel Report
</div>
<div style="float:right;width:25%;">{logo_tag}</div>
<div style="clear:both;"></div>
<hr style="border:solid 2px #06615c;margin-top:0;">

<!-- BODY: LEFT + RIGHT -->
<div style="display:flex;">

  <!-- LEFT -->
  <div style="flex:3;padding-right:12px;">
    {_info_table("Patient Information",  patient_rows)}
    {_info_table("Order Information",    order_rows)}
    {_info_table("Case Information",     case_rows)}
    <table class="table table-condensed"
           style="font-size:10px;font-family:Arial;margin-left:auto;margin-right:auto;">
      <caption style="font-size:initial!important;">NGS QC Metrics</caption>
      <thead><tr><th style="border-bottom:0;border-color:#d6d6d6;"></th>
                 <th style="border-bottom:0;border-color:#d6d6d6;"></th></tr></thead>
      <tbody>{qc_rows_html}</tbody>
    </table>
  </div>

  <!-- RIGHT -->
  <div style="flex:7;padding-left:20px;">
    <div style="font-size:18px;font-weight:bold;color:#000;">Genomic Biomarker Details</div>
    <hr style="border:solid 1px #d6d6d6;margin-bottom:10px;margin-top:5px;">
    {biomarker_html}
  </div>

</div><!-- /body flex -->

<!-- PAGE BREAK → APPENDIX -->
{excluded_html}

<hr style="border:solid 1px #06615c;margin-top:30px;margin-bottom:5px;">
<div style="color:#5b5b5b;font-size:10px;">GMC Medical Center</div>
<div style="color:#5b5b5b;font-size:10px;">TEL: 070-7425-0529 | E-mail: gmcinfo@gmcmedi.com</div>

</body>
</html>"""
    return html_doc


# ============================================================
# Dash 콜백 (report.py 의 download_pdf 콜백에서 호출)
# ============================================================

def generate_tso_clinical_pdf(selected_rows: list[dict],
                               template_dir: str) -> tuple[bytes | None, str]:
    """
    selected_rows: AG Grid selectedRows
    template_dir : logo.png 가 있는 디렉토리

    반환: (pdf_bytes, filename) — 실패 시 (None, error_message)
    """
    try:
        import weasyprint
    except ImportError:
        return None, "WeasyPrint 미설치 (pip install weasyprint)"

    # 로고 로드
    logo_uri = ""
    logo_path = os.path.join(template_dir, "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_uri = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

    if not selected_rows:
        return None, "선택된 샘플이 없습니다."

    db = SessionLocal()
    try:
        all_pages_html = []
        for row in selected_rows:
            sid = row.get("sample_id") or row.get("id")
            if not sid:
                continue
            s = (db.query(Sample)
                   .filter(Sample.sample_id == sid)
                   .first())
            if not s:
                s = db.query(Sample).filter(Sample.id == sid).first()
            if not s:
                continue
            all_pages_html.append(build_report_html(s, logo_uri))

        if not all_pages_html:
            return None, "유효한 샘플이 없습니다."

        # 여러 샘플을 page-break 로 이어 붙임
        combined = '<div style="page-break-after:always;">'.join(all_pages_html)
        pdf_bytes = weasyprint.HTML(string=combined).write_pdf()
        fname = f"TSO500_Clinical_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return pdf_bytes, fname

    finally:
        db.close()


# ============================================================
# 단독 실행용 미니 Dash 앱 (report.py 와 분리해서 테스트할 때)
# ============================================================

def create_tso_clinical_report_app(requests_pathname_prefix: str):
    from dash import Dash
    app = Dash(__name__,
               requests_pathname_prefix=requests_pathname_prefix,
               external_stylesheets=[__import__("dash_bootstrap_components").themes.BOOTSTRAP])

    app.layout = html.Div([
        html.H4("TSO500 Clinical Report 생성기", className="m-3"),
        dbc.Alert(
            "이 모듈은 report.py 의 PDF 다운로드 콜백에서 generate_tso_clinical_pdf() 를 호출해 사용합니다.",
            color="info", className="m-3"),
    ])
    return app


# ============================================================
# report.py 연동용 패치 (기존 download_pdf 콜백에 아래 분기 추가)
# ============================================================
# 기존 report.py의 download_pdf 콜백 안에서:
#
#   if template_type == "gmc_tso_clinical_report":
#       from app.pages.report.gmc_tso_clinical_report import generate_tso_clinical_pdf
#       template_path = os.path.join(BASE_DIR, "app", "templates", "reports")
#       pdf_bytes, result = generate_tso_clinical_pdf(selected_rows, template_path)
#       if pdf_bytes is None:
#           return no_update, dbc.Alert(f"❌ {result}", color="danger")
#       return dcc.send_bytes(pdf_bytes, result), dbc.Alert("✅ PDF 다운로드 완료!", color="success")
#