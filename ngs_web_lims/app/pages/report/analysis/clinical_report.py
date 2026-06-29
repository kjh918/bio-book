from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from datetime import datetime
import os
import json
import ast
import re
import traceback
import base64
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.database import SessionLocal
from app.models._schema import Sample, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR

# 🚀 공통 레이아웃 함수 가져오기
from app.pages.report.base import create_shared_report_layout


# ==========================================
# [1] 데이터 파서 및 리포트 템플릿 생성기
# ==========================================
def parse_json_like(value):
    """DB에 저장된 analysis_results를 안전하게 복구하고 빈 값을 제거합니다."""
    if isinstance(value, dict):
        return {k: parse_json_like(v) for k, v in value.items() if parse_json_like(v) is not None and parse_json_like(v) != []}
    if isinstance(value, list):
        return [parse_json_like(v) for v in value if parse_json_like(v) is not None]
    if isinstance(value, str):
        s = value.strip()
        if not s or s.upper() in ["NA", "N/A", "NONE", "NULL"]: return None
        if s.startswith("{") or s.startswith("["):
            try: return parse_json_like(json.loads(s))
            except Exception:
                try:
                    s_safe = s.replace("null", "None").replace("true", "True").replace("false", "False").replace("nan", "None")
                    return parse_json_like(ast.literal_eval(s_safe))
                except Exception:
                    try: return parse_json_like(json.loads(re.sub(r"'([^']*)'", r'"\1"', s)))
                    except: return s
        return s
    return value


CLINICAL_REPORT_TEMPLATE_NAME = "gmc_tso_clinical_report.html"
CLINICAL_REPORT_TEMPLATE_PATH = os.environ.get("CLINICAL_REPORT_TEMPLATE_PATH")
CLINICAL_REPORT_TEMPLATE_DIR = os.environ.get("CLINICAL_REPORT_TEMPLATE_DIR")

CLINICAL_REPORT_TEMPLATE_DIR_CANDIDATES = [
    # QC 미리보기와 같은 계열: BASE_DIR/app/templates/reports/clinical/{template}.html
    os.path.join(BASE_DIR, "app", "templates", "reports", "analysis"),
    # 템플릿을 reports 바로 아래에 둔 경우: BASE_DIR/app/templates/reports/{template}.html
    os.path.join(BASE_DIR, "app", "templates", "reports"),
    # 기존 패치 구조: app/pages/report/templates/{template}.html
    os.path.join(os.path.dirname(__file__), "templates"),
]
if CLINICAL_REPORT_TEMPLATE_DIR:
    CLINICAL_REPORT_TEMPLATE_DIR_CANDIDATES.insert(0, CLINICAL_REPORT_TEMPLATE_DIR)


def _clean_value(value, default="-"):
    """템플릿에 안전하게 넣을 표시 값을 정리합니다."""
    value = parse_json_like(value)
    if value is None or value == "" or value == [] or value == {}:
        return default
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return str(value)
    return value


def _display(value, default="-"):
    value = _clean_value(value, default=default)
    if isinstance(value, (dict, list)):
        return value
    return str(value)


def _normalize_key(key):
    return re.sub(r"[^a-z0-9]+", "", str(key).lower())


def _find_key(mapping, *candidates):
    if not isinstance(mapping, dict):
        return None
    normalized = {_normalize_key(k): k for k in mapping.keys()}
    for candidate in candidates:
        found = normalized.get(_normalize_key(candidate))
        if found is not None:
            return found
    return None


def _get_any(mapping, *candidates, default=None):
    key = _find_key(mapping, *candidates)
    if key is None:
        return default
    return mapping.get(key, default)


def _flatten_analysis_data(data):
    """analysis_results 내부의 metrics/variants 같은 중첩 dict를 템플릿 context용으로 평탄화합니다."""
    data = parse_json_like(data) or {}
    if not isinstance(data, dict):
        return {}

    flat_data = {}
    for key, value in data.items():
        value = parse_json_like(value)
        if key in ["metrics", "variants"] and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat_data[sub_key] = parse_json_like(sub_value)
        else:
            flat_data[key] = value
    return flat_data


def _get_metric(flat_data, metric, default="-"):
    """평탄화 데이터와 자주 쓰는 nested section에서 metric 값을 찾습니다."""
    value = _get_any(flat_data, metric, default=None)
    if value is not None:
        if isinstance(value, dict):
            value = value.get("value", value.get("Value", default))
        return _display(value, default=default)

    for section in ["QC", "Run_QC_Metrics", "Analysis_Details", "Header"]:
        section_value = _get_any(flat_data, section, default=None)
        if isinstance(section_value, dict):
            nested_value = _get_any(section_value, metric, default=None)
            if nested_value is not None:
                if isinstance(nested_value, dict):
                    nested_value = nested_value.get("value", nested_value.get("Value", default))
                return _display(nested_value, default=default)
    return default


def _as_rows(value):
    """list/dict/string 형태의 변이 결과를 템플릿 테이블에 넣을 row list로 변환합니다."""
    value = parse_json_like(value)
    if value is None:
        return []
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        # {"0": {...}, "1": {...}} 또는 {"gene": ...} 모두 대응
        if value and all(isinstance(v, dict) for v in value.values()):
            rows = list(value.values())
        else:
            rows = [value]
    else:
        return []

    normalized_rows = []
    for row in rows:
        row = parse_json_like(row)
        if isinstance(row, dict):
            normalized_rows.append({str(k): _display(v, default="") for k, v in row.items()})
    return normalized_rows


def _pick_rows(flat_data, *candidate_keys):
    for key in candidate_keys:
        value = _get_any(flat_data, key, default=None)
        rows = _as_rows(value)
        if rows:
            return rows
    return []


def _discover_columns(rows, preferred_columns=None, exclude_private=True):
    preferred_columns = preferred_columns or []
    columns = []

    for col in preferred_columns:
        if any(col in row for row in rows) and col not in columns:
            columns.append(col)

    for row in rows:
        for col in row.keys():
            if exclude_private and str(col).startswith("_"):
                continue
            if col not in columns:
                columns.append(col)
    return columns


def _fixed_variant_columns(rows, preferred_columns=None, exclude_private=True):
    """
    데이터가 없어도 보고서 테이블 header를 유지하기 위한 column 생성기입니다.
    preferred_columns는 항상 먼저 포함하고, 실제 row에만 있는 추가 컬럼은 뒤에 붙입니다.
    """
    preferred_columns = preferred_columns or []
    columns = []

    for col in preferred_columns:
        if col not in columns:
            columns.append(col)

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for col in row.keys():
            if exclude_private and str(col).startswith("_"):
                continue
            if col not in columns:
                columns.append(col)
    return columns


def _to_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None



# ==========================================
# [Small Variant 필터 기준]
# - 프로젝트 기준값이 이미 있으면 globals() 값을 사용하고,
#   없으면 환경변수 또는 아래 기본값을 fallback으로 사용합니다.
# ==========================================
VAF_MIN_THRESHOLD = float(os.environ.get("CLINICAL_VAF_MIN_THRESHOLD", globals().get("VAF_MIN_THRESHOLD", 0.01)))
VAF_REPORT_THRESHOLD = float(os.environ.get("CLINICAL_VAF_REPORT_THRESHOLD", globals().get("VAF_REPORT_THRESHOLD", 0.05)))
DEPTH_MIN = int(os.environ.get("CLINICAL_DEPTH_MIN", globals().get("DEPTH_MIN", 100)))

EXCLUDE_CONSEQUENCES = set(globals().get("EXCLUDE_CONSEQUENCES", {
    "synonymous_variant",
    "intron_variant",
    "intergenic_variant",
    "upstream_gene_variant",
    "downstream_gene_variant",
    "3_prime_utr_variant",
    "5_prime_utr_variant",
    "utr_variant",
    "non_coding_transcript_exon_variant",
    "non_coding_transcript_variant",
}))

INCLUDE_CONSEQUENCES = set(globals().get("INCLUDE_CONSEQUENCES", {
    "missense_variant",
    "frameshift_variant",
    "stop_gained",
    "stop_lost",
    "start_lost",
    "splice_acceptor_variant",
    "splice_donor_variant",
    "splice_region_variant",
    "inframe_deletion",
    "inframe_insertion",
    "protein_altering_variant",
    "coding_sequence_variant",
}))


def _is_blank_gene(value):
    text = str(value or "").strip()
    return text == "" or text == "-" or text.lower() in {"na", "n/a", "none", "null", "nan"}


def _is_truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in {"", "-", "0", "false", "no", "n", "none", "null", "nan"}:
        return False
    if text in {"1", "true", "yes", "y", "hotspot"}:
        return True
    return bool(text)


def filter_small_variants(variants: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    (included, excluded) 튜플을 반환합니다.
    included: 보고서 본문에 실릴 Small Variant
    excluded: gene name 없음 / VAF / Depth / Consequence 기준으로 제외된 Small Variant
    """
    included, excluded = [], []

    for v in variants or []:
        if not isinstance(v, dict):
            continue

        # ── 값 추출 ────────────────────────────────────────
        gene = str(_get_any(v, "Gene", "gene", "Gene_Name", "gene_name", default="")).strip()
        vaf = _to_float(_get_any(v, "Allele_Frequency", "Allele Frequency", "VAF", "vaf", "allele_frequency", default=0))
        dp = _to_float(_get_any(v, "DP", "Depth", "depth", "Read_Depth", "Read Depth", default=0))

        # Consequence는 콤마/슬래시/세미콜론으로 복수 표기될 수 있음 → set으로 파싱
        raw_csq = str(_get_any(v, "Consequences", "Consequence", "consequence", "variant_type", "Variant_Type", default=""))
        csq_set = {
            c.strip().lower()
            for c in re.sub(r"[;/]", ",", raw_csq).split(",")
            if c.strip()
        }

        # Hotspot 정보가 따로 들어오는 경우만 예외 처리합니다.
        # 기존 코드처럼 Consequence 문자열 자체를 hotspot 여부로 쓰면 대부분 True가 되어 필터가 무력화됩니다.
        is_hotspot = _is_truthy(_get_any(v, "Hotspot", "hotspot", "is_hotspot", "Is_Hotspot", "HOTSPOT", default=False))

        vaf_value = vaf if vaf is not None else 0.0
        dp_value = dp if dp is not None else 0.0

        reason = None

        # ── 제외 조건 ──────────────────────────────────────
        if _is_blank_gene(gene):
            reason = "Gene name 없음"
        elif vaf_value < VAF_MIN_THRESHOLD:
            reason = f"VAF {vaf_value:.3f} < {VAF_MIN_THRESHOLD}"
        elif dp_value < DEPTH_MIN:
            reason = f"Depth {int(dp_value)} < {DEPTH_MIN}"
        elif csq_set and csq_set.issubset(EXCLUDE_CONSEQUENCES):
            reason = f"Consequence 제외 ({', '.join(sorted(csq_set))})"

        # ── 임상 보고 포함 여부 보조 조건 ───────────────────
        # hotspot도 아니고 보고 대상 consequence도 아니면서 보고 VAF 기준 미만이면 appendix로 보냅니다.
        elif not is_hotspot and not csq_set.intersection(INCLUDE_CONSEQUENCES):
            if vaf_value < VAF_REPORT_THRESHOLD:
                reason = f"임상적 의의 없는 변이 (VAF {vaf_value:.3f})"

        row = dict(v)
        if reason:
            row["_filter_reason"] = reason
            excluded.append(row)
        else:
            included.append(row)

    return included, excluded


# Small Variant는 보고서에서 아래 9개 컬럼만 고정 순서로 표시합니다.
SMALL_VARIANT_REPORT_COLUMNS = [
    "Gene",
    "Pos",
    "REF->ALT",
    "Depth",
    "VAF",
    "Consequence",
    "Reference",
    "HGVSc",
    "HGVSp",
]


def _empty_if_dash(value):
    """보고서 테이블 안에서는 없는 값을 '-' 대신 공란으로 표시합니다."""
    text = _display(value, default="")
    if text in {"-", "None", "NULL", "null", "nan", "NaN"}:
        return ""
    return text


def _split_hgvs_reference(value):
    """NM_...:c.123A>T / NM_...:p.(...) 형태를 Reference와 HGVS 표기로 분리합니다."""
    text = _empty_if_dash(value).strip()
    if not text:
        return "", ""
    if ":" in text:
        reference, notation = text.split(":", 1)
        return reference.strip(), notation.strip()
    return "", text


def _format_small_variant_position(row):
    chrom = _empty_if_dash(_get_any(row, "Chromosome", "Chr", "CHROM", "chrom", "chromosome", default=""))
    pos = _empty_if_dash(_get_any(
        row,
        "Genomic_Position",
        "Genomic Position",
        "Position",
        "POS",
        "pos",
        "Start_Position",
        "Start Position",
        default="",
    ))

    if chrom and pos:
        chrom = re.sub(r"^chr", "", chrom, flags=re.IGNORECASE)
        return f"chr{chrom}:{pos}"

    return _empty_if_dash(_get_any(row, "Pos", "Pos", "Position", default=""))


def _format_small_variant_ref_alt(row):
    ref = _empty_if_dash(_get_any(
        row,
        "Reference_Call",
        "Reference Call",
        "Reference_Allele",
        "Reference Allele",
        "REF",
        "Ref",
        "ref",
        default="",
    ))
    alt = _empty_if_dash(_get_any(
        row,
        "Alternative_Call",
        "Alternative Call",
        "Alternate_Allele",
        "Alternate Allele",
        "ALT",
        "Alt",
        "alt",
        default="",
    ))

    if ref or alt:
        return f"{ref}->{alt}"
    return _empty_if_dash(_get_any(row, "REF->ALT", "Ref->Alt", "Ref Alt", default=""))


def _format_small_variant_report_row(row):
    """원본 Small Variant row를 보고서 표시용 9개 컬럼으로 재구성합니다."""
    hgvsc_raw = _get_any(
        row,
        "HGVSc",
        "HGVS.c",
        "HGVS_C",
        "C_Dot_Notation",
        "C Dot Notation",
        "c_dot_notation",
        "cDNA_Change",
        "cDNA Change",
        default="",
    )
    hgvsp_raw = _get_any(
        row,
        "HGVSp",
        "HGVS.p",
        "HGVS_P",
        "P_Dot_Notation",
        "P Dot Notation",
        "p_dot_notation",
        "Protein_Change",
        "Protein Change",
        default="",
    )

    ref_from_c, hgvsc = _split_hgvs_reference(hgvsc_raw)
    ref_from_p, hgvsp = _split_hgvs_reference(hgvsp_raw.replace('(','').replace(')',''))
    if hgvsp.find('c')>=0:
        hgvsp = 'p' + hgvsp.split('p')[1]
    reference = ref_from_c or ref_from_p or _empty_if_dash(_get_any(
        row,
        "Transcript",
        "Transcript_ID",
        "Transcript ID",
        "Feature",
        "Feature_ID",
        "RefSeq",
        "RefSeq_ID",
        "Reference",
        default="",
    ))

    return {
        "Gene": _empty_if_dash(_get_any(row, "Gene", "gene", "Gene_Name", "gene_name", default="")),
        "Pos": _format_small_variant_position(row),
        "REF->ALT": _format_small_variant_ref_alt(row),
        "Depth": _empty_if_dash(_get_any(row, "Depth", "DP", "depth", "Read_Depth", "Read Depth", default="")),
        "VAF": _empty_if_dash(_get_any(row, "VAF", "Allele_Frequency", "Allele Frequency", "allele_frequency", default="")),
        "Consequence": _empty_if_dash(_get_any(row, "Consequences", "Consequence", "consequence", "variant_type", "Variant_Type", default="")),
        "Reference": reference,
        "HGVSc": hgvsc,
        "HGVSp": hgvsp,
    }


# ==========================================
# [TSO DNA/RNA 샘플 그룹핑 유틸]
# ==========================================
def _base_sample_id(sample_id):
    """TSO DNA/RNA suffix를 제거한 base sample id를 반환합니다."""
    text = str(sample_id or "").strip()
    return re.sub(r"[-_](DNA|RNA)$", "", text, flags=re.IGNORECASE)


def _sample_modality_from_id(sample_id):
    match = re.search(r"[-_](DNA|RNA)$", str(sample_id or "").strip(), flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _sample_modality(sample):
    from_id = _sample_modality_from_id(getattr(sample, "sample_id", ""))
    if from_id:
        return from_id

    text = str(getattr(sample, "nucleic_acid_type", "") or "").upper()
    if "DNA" in text and "RNA" not in text:
        return "DNA"
    if "RNA" in text and "DNA" not in text:
        return "RNA"
    return ""


def _is_tso_panel(panel):
    text = str(panel or "").lower()
    return "tso" in text or "trusight oncology" in text


def _is_tso_sample(sample):
    return _is_tso_panel(getattr(sample, "target_panel", ""))


def _sort_samples_by_modality(samples):
    order = {"DNA": 0, "RNA": 1, "": 2}
    return sorted(samples or [], key=lambda s: (order.get(_sample_modality(s), 9), str(getattr(s, "sample_id", ""))))


def _primary_sample(samples):
    sorted_samples = _sort_samples_by_modality(samples)
    if not sorted_samples:
        return None
    return sorted_samples[0]


def _merge_panel_metadata(samples):
    merged = {}
    for sample in reversed(_sort_samples_by_modality(samples)):
        pm = parse_json_like(getattr(sample, "panel_metadata", None)) or {}
        if isinstance(pm, dict):
            merged.update(pm)
    return merged


def _merge_flat_analysis_data(samples):
    """
    TSO는 DNA/RNA가 한 case입니다.
    - DNA 쪽 결과를 기본값으로 사용합니다. Small Variant/CNV/TMB/MSI/QC는 보통 DNA 기준입니다.
    - RNA 쪽 Fusion/Splice 결과는 DNA context에 합칩니다.
    - DNA에 없는 보조 값은 RNA에서 채웁니다.
    """
    flat_items = []
    for sample in _sort_samples_by_modality(samples):
        raw_data = sample.analysis.analysis_results if getattr(sample, "analysis", None) else {}
        flat_items.append((_sample_modality(sample), _flatten_analysis_data(raw_data)))

    combined = {}

    # DNA를 먼저 기준 context로 사용합니다. DNA가 없으면 첫 번째 sample이 기준이 됩니다.
    for modality, flat in flat_items:
        if modality == "DNA" or not combined:
            combined.update(flat)

    # 비어 있는 키는 다른 modality에서 보완합니다.
    for modality, flat in flat_items:
        for key, value in flat.items():
            if key not in combined or combined[key] in (None, "", [], {}):
                combined[key] = value

    # RNA 분석에서 나오는 biomarker는 명시적으로 합칩니다.
    for modality, flat in flat_items:
        if modality != "RNA":
            continue
        for key, value in flat.items():
            normalized = _normalize_key(key)
            if "fusion" in normalized or "splice" in normalized:
                combined[key] = value

    return combined


def _decode_row_sample_ids(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, tuple):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                decoded = json.loads(text)
                return _decode_row_sample_ids(decoded)
            except Exception:
                pass
        return [part.strip() for part in text.split(",") if part.strip()]
    return []


def _query_samples_by_ids(db, sample_ids):
    sample_ids = list(dict.fromkeys([sid for sid in sample_ids if sid]))
    if not sample_ids:
        return []
    samples = db.query(Sample).filter(Sample.sample_id.in_(sample_ids)).all()
    return _sort_samples_by_modality(samples)


def _resolve_selected_samples(db, selected_row):
    """
    Grid row 하나에서 실제 Sample 객체 목록을 찾습니다.
    TSO grouped row이면 DNA/RNA 두 개를 반환하고, 일반 row이면 한 개만 반환합니다.
    """
    if not selected_row:
        return []

    sample_ids = []
    sample_ids.extend(_decode_row_sample_ids(selected_row.get("sample_ids")))

    for key in ("dna_sample_id", "rna_sample_id"):
        value = selected_row.get(key)
        if value:
            sample_ids.append(str(value))

    resolved = _query_samples_by_ids(db, sample_ids)
    if resolved:
        return resolved

    selected_sample_id = str(selected_row.get("sample_id") or "").strip()
    if not selected_sample_id:
        return []

    exact = db.query(Sample).filter(Sample.sample_id == selected_sample_id).first()

    # sample_id가 base id로 들어온 TSO row이면 base-DNA/base-RNA를 같이 찾습니다.
    base_id = _base_sample_id(selected_sample_id)
    possible_pair_ids = [f"{base_id}-DNA", f"{base_id}-RNA", f"{base_id}_DNA", f"{base_id}_RNA"]
    paired = _query_samples_by_ids(db, possible_pair_ids)
    if paired:
        return paired

    if exact:
        return [exact]

    return []


def _sample_to_grid_row(sample, config):
    metadata = parse_json_like(getattr(sample, "panel_metadata", None)) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    a_status = sample.analysis.analysis_status if getattr(sample, "analysis", None) else "대기중"
    row = {
        "id": getattr(sample, "id", None),
        "project_name": getattr(sample, "project_name", ""),
        "order_id": getattr(sample, "order_id", ""),
        "sample_id": getattr(sample, "sample_id", ""),
        "sample_ids": [getattr(sample, "sample_id", "")],
        "dna_sample_id": getattr(sample, "sample_id", "") if _sample_modality(sample) == "DNA" else "",
        "rna_sample_id": getattr(sample, "sample_id", "") if _sample_modality(sample) == "RNA" else "",
        "tso_pair": _sample_modality(sample) or "-",
        "sample_name": getattr(sample, "sample_name", ""),
        "target_panel": getattr(sample, "target_panel", ""),
        "nucleic_acid_type": getattr(sample, "nucleic_acid_type", "") or _sample_modality(sample),
        "current_status": getattr(sample, "current_status", ""),
        "analysis_status": a_status,
    }

    for col in config.get("columns", []):
        col_id = col["id"]
        val = getattr(sample, col_id, "")
        if not val:
            val = metadata.get(col_id, "")
        row[col_id] = val
    return row


def _combined_status(samples, analysis=False):
    samples = _sort_samples_by_modality(samples)
    values = []
    labeled = []
    for sample in samples:
        modality = _sample_modality(sample) or str(getattr(sample, "sample_id", ""))
        if analysis:
            value = sample.analysis.analysis_status if getattr(sample, "analysis", None) else "대기중"
        else:
            value = getattr(sample, "current_status", "") or "-"
        values.append(value)
        labeled.append(f"{modality}:{value}")

    unique_values = {v for v in values if v}
    if len(unique_values) == 1:
        return values[0]
    return " / ".join(labeled)


def _samples_to_tso_grid_row(base_id, samples, config):
    samples = _sort_samples_by_modality(samples)
    primary = _primary_sample(samples)
    row = _sample_to_grid_row(primary, config)

    dna = next((s for s in samples if _sample_modality(s) == "DNA"), None)
    rna = next((s for s in samples if _sample_modality(s) == "RNA"), None)
    sample_ids = [getattr(s, "sample_id", "") for s in samples]

    row.update({
        "id": "|".join(str(getattr(s, "id", "")) for s in samples),
        "sample_id": base_id,
        "sample_ids": sample_ids,
        "dna_sample_id": getattr(dna, "sample_id", "") if dna else "",
        "rna_sample_id": getattr(rna, "sample_id", "") if rna else "",
        "tso_pair": "DNA+RNA" if dna and rna else ("DNA만" if dna else "RNA만"),
        "nucleic_acid_type": "DNA/RNA" if dna and rna else (_sample_modality(primary) or "-"),
        "current_status": _combined_status(samples, analysis=False),
        "analysis_status": _combined_status(samples, analysis=True),
    })
    return row


def _report_sample_id(samples):
    primary = _primary_sample(samples)
    if not primary:
        return "-"
    modalities = {_sample_modality(s) for s in samples}
    if len(samples) > 1 and {"DNA", "RNA"}.intersection(modalities):
        return _base_sample_id(getattr(primary, "sample_id", ""))
    return getattr(primary, "sample_id", "-")

def _build_qc_metrics(flat_data):
    q30_r1 = _get_metric(flat_data, "PCT_Q30_R1")
    q30_r2 = _get_metric(flat_data, "PCT_Q30_R2")
    gc_r1 = _get_metric(flat_data, "PCT_GC_R1")
    gc_r2 = _get_metric(flat_data, "PCT_GC_R2")

    return [
        {"Metric": "Sample conc. (ng)", "Value": _get_metric(flat_data, "Sample_Conc")},
        {"Metric": "Library size (bp)", "Value": _get_metric(flat_data, "Library_Size")},
        {"Metric": "Q30 R1/R2 (%)", "Value": f"{q30_r1} / {q30_r2}"},
        {"Metric": "GC R1/R2 (%)", "Value": f"{gc_r1} / {gc_r2}"},
        {"Metric": "On target rate (%)", "Value": _get_metric(flat_data, "PCT_ON_TARGET_READS")},
        {"Metric": "Median insert size", "Value": _get_metric(flat_data, "MEDIAN_INSERT_SIZE")},
        {"Metric": "Median target depth", "Value": _get_metric(flat_data, "MEDIAN_TARGET_COVERAGE")},
        {"Metric": "Uniformity", "Value": _get_metric(flat_data, "PCT_EXON_50X")},
    ]


def _build_tmb(flat_data):
    raw_tmb = _get_any(flat_data, "TMB", "Tumor Mutational Burden", default=None)
    raw_tmb = parse_json_like(raw_tmb)
    if raw_tmb is None:
        return {}

    if isinstance(raw_tmb, dict):
        score = _get_any(raw_tmb, "Total TMB", "TMB", "TMB Score", "Score", default="-")
        eligible = _get_any(raw_tmb, "Eligible Variants", "Eligible_Variants", default="-")
        coding_region_size = _get_any(raw_tmb, "Coding Region Size", "Coding_region_size", default="1.26 Mb")
    else:
        score = raw_tmb
        eligible = "-"
        coding_region_size = "1.26 Mb"

    score_display = _display(score)
    score_float = _to_float(score_display)
    if score_float is None:
        status = "-"
    else:
        status = "TMB-High" if score_float >= 10 else "TMB-Low"

    return {
        "TMB_status": status,
        "TMB": f"{score_display} muts/Mb" if score_display != "-" else "-",
        "Eligible_variants": _display(eligible),
        "Coding_region_size": _display(coding_region_size),
    }


def _build_msi(flat_data):
    raw_msi = _get_any(flat_data, "MSI", "Microsatellite Instability", default=None)
    raw_msi = parse_json_like(raw_msi)
    if raw_msi is None:
        return {}

    if isinstance(raw_msi, dict):
        rate = _get_any(raw_msi, "Percent Unstable MSI Sites", "MSI Rate", "Rate", default="-")
        unstable = _get_any(raw_msi, "Unstable MSI Sites", "Unstable MSI Regions", default="-")
        usable = _get_any(raw_msi, "Usable MSI Sites", "Total Usable MSI Sites", default="-")
    else:
        rate = raw_msi
        unstable = "-"
        usable = "-"

    rate_display = _display(rate)
    rate_float = _to_float(rate_display)
    if rate_float is None:
        status = "-"
    else:
        status = "Microsatellite Instability-High (MSI-H)" if rate_float >= 20 else "Microsatellite Stable (MSS)"

    return {
        "MSI_status": status,
        "unstable_MSI_sites_rate (%)": rate_display,
        "unstable_MSI_regions": _display(unstable),
        "total_usable_MSI_sites": _display(usable),
    }


def build_clinical_report_context(sample_or_samples):
    """HTML 템플릿에 넘길 context만 생성합니다. 실제 HTML은 Jinja 렌더링이 담당합니다."""
    if isinstance(sample_or_samples, (list, tuple)):
        samples = [s for s in sample_or_samples if s is not None]
    else:
        samples = [sample_or_samples] if sample_or_samples is not None else []

    samples = _sort_samples_by_modality(samples)
    sample = _primary_sample(samples)
    if sample is None:
        raise ValueError("리포트를 생성할 Sample이 없습니다.")

    flat_data = _merge_flat_analysis_data(samples)
    pm = _merge_panel_metadata(samples)
    order = sample.order

    raw_small_variants = _pick_rows(flat_data, "Small_Variants", "Small Variants", "small_variants")
    filtered_small_variants, _filtered_out_small_variants = filter_small_variants(raw_small_variants)

    # 제외된 변이는 보고서/appendix에 추가하지 않습니다.
    # 필터 통과한 small_variants만 본문에 전달하고, 표시 컬럼은 고정 순서로 재구성합니다.
    excluded_variants = []
    small_variants = [_format_small_variant_report_row(v) for v in filtered_small_variants]

    gene_amplifications = _pick_rows(flat_data, "Gene_Amplifications", "Gene Amplifications", "CNV", "CNVs")
    splice_variants = _pick_rows(flat_data, "Splice_Variants", "Splice Variants")
    fusions = _pick_rows(flat_data, "Fusions", "Fusion")

    small_variant_cols = list(SMALL_VARIANT_REPORT_COLUMNS)
    excluded_variant_cols = []
    gene_amplification_cols = _fixed_variant_columns(
        gene_amplifications,
        ["Gene", "Fold Change", "Fold_Change", "Copy_Number", "Copy Number", "CN"],
    )
    splice_variant_cols = _fixed_variant_columns(
        splice_variants,
        ["Gene", "Affected_Exon", "Breakpoint_1","Breakpoint_2", "Splice_Supporting_Reads","Reference","Reads","Transcript"],
    )
    fusion_cols = _fixed_variant_columns(
        fusions,
        ["Gene_Pair", "Breakpoint 1", "Breakpoint 2", "Fusion_Supporting_Reads","Gene_1_Reference_Reads", "Gene_2_Reference_Reads"],
    )

    sequencing_info = _get_any(flat_data, "Sequencing_Info", "Sequencing Information", default=None)
    sequencing_info = parse_json_like(sequencing_info)
    if not isinstance(sequencing_info, dict):
        sequencing_info = {
            "Library kit": "TruSight Oncology 500 kit [ Illumina ]",
            "Capture methods": "Hybridization capture-based",
            "Sequencer": "Nextseq550 Dx [ Illumina ]",
            "Assembly version": "GRCh37/hg19",
        }

    return {
        "logo_path": _get_any(pm, "logo_path", "Logo_Path", default=""),
        "patient_name": _display(sample.sample_name),
        "patient_id": _display(_report_sample_id(samples)),
        "cancer_type": _display(getattr(sample, "cancer_type", None)),
        "specimen_type": _display(getattr(sample, "specimen", None)),
        "specimen_site": _display(_get_any(pm, "Specimen_Site", "Specimen site", default=getattr(sample, "specimen", None))),
        "facility": _display(getattr(order, "facility", None) if order else None),
        "facility_id": _display(_get_any(pm, "Facility_ID", "Facility ID", default=None)),
        "physician": _display(getattr(order, "client_name", None) if order else None),
        "pathologist": _display(_get_any(pm, "Pathologist", default=None)),
        "date_of_order": _display(getattr(order, "reception_date", None) if order else None),
        "specimen_id": _display(getattr(sample, "outside_id_1", None)),
        "tumor_purity": _display(_get_any(pm, "Tumor_Purity", "Tumor purity", default=None)),
        "date_of_collection": _display(_get_any(pm, "Collection_Date", "Date of collection", default=None)),
        "panel": _display(getattr(sample, "target_panel", None), default="TruSight Oncology 500"),
        "pipeline": _display(_get_any(flat_data, "Pipeline", "Workflow", default="NGS-TSO-v1")),
        "pipeline_version": _display(_get_any(flat_data, "Pipeline_Version", "Pipeline version", default="-")),
        "analyst": _display(_get_any(pm, "Analyst", default=None)),
        "date_of_receipt": _display(getattr(order, "reception_date", None) if order else None),
        "date_of_report": datetime.now().strftime("%Y-%m-%d"),
        "qc_metrics": _build_qc_metrics(flat_data),
        "small_variants": small_variants,
        "small_variant_cols": small_variant_cols,
        "excluded_variants": excluded_variants,
        "excluded_variant_cols": excluded_variant_cols,
        "tmb": _build_tmb(flat_data),
        "msi": _build_msi(flat_data),
        "gene_amplifications": gene_amplifications,
        "gene_amplification_cols": gene_amplification_cols,
        "splice_variants": splice_variants,
        "splice_variant_cols": splice_variant_cols,
        "fusions": fusions,
        "fusion_cols": fusion_cols,
        "sequencing_info": sequencing_info,
        "paired_sample_ids": [getattr(s, "sample_id", "") for s in samples],
        "extraction_type": "DNA/RNA" if len(samples) > 1 else (_sample_modality(sample) or _display(getattr(sample, "nucleic_acid_type", None))),
    }


def _normalize_template_name(template_type=None):
    """Dash template value를 실제 HTML 파일명으로 변환합니다."""
    template_name = template_type or CLINICAL_REPORT_TEMPLATE_NAME
    template_name = str(template_name).strip() or CLINICAL_REPORT_TEMPLATE_NAME
    if not template_name.endswith(".html"):
        template_name = f"{template_name}.html"
    return template_name


def _resolve_clinical_template(template_type=None):
    """선택된 템플릿을 찾습니다. QC callback 형태처럼 FileSystemLoader에 넘길 dir/name을 반환합니다."""
    if CLINICAL_REPORT_TEMPLATE_PATH:
        return os.path.dirname(CLINICAL_REPORT_TEMPLATE_PATH), os.path.basename(CLINICAL_REPORT_TEMPLATE_PATH)

    template_name = _normalize_template_name(template_type)
    for template_dir in CLINICAL_REPORT_TEMPLATE_DIR_CANDIDATES:
        if template_dir and os.path.exists(os.path.join(template_dir, template_name)):
            return template_dir, template_name

    # 존재하지 않으면 첫 번째 후보를 반환해 Jinja2가 명확한 TemplateNotFound를 내게 합니다.
    return CLINICAL_REPORT_TEMPLATE_DIR_CANDIDATES[0], template_name


def _image_file_to_data_uri(path):
    if not path or not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower()
    mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def _get_logo_data_uri(template_type=None):
    """QC 미리보기 코드와 동일하게 template_type 기준으로 로고를 data URI로 넣습니다."""
    template_text = str(template_type or "").lower()
    logo_filename = "gmc_logo.png" if "gmc" in template_text else "logo.png"
    candidates = [
        os.path.join(BASE_DIR, "app", "templates", "reports", logo_filename),
        os.path.join(BASE_DIR, "app", "templates", "reports", "clinical", logo_filename),
        os.path.join(os.path.dirname(__file__), "templates", logo_filename),
    ]
    for path in candidates:
        data_uri = _image_file_to_data_uri(path)
        if data_uri:
            return data_uri
    return ""


def _format_upload_message(img_names):
    if not img_names:
        return "첨부된 이미지가 없습니다."
    if isinstance(img_names, str):
        img_names = [img_names]
    return f"📎 첨부됨: {', '.join(img_names)}"


def _render_clinical_report_template(context, template_type=None):
    """템플릿 파일을 읽어 context로 렌더링합니다."""
    template_dir, template_name = _resolve_clinical_template(template_type)
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
    )
    template = env.get_template(template_name)
    return template.render(**context)


def generate_clinical_html_report(sample_or_samples, template_type=None, extra_context=None):
    """선택한 검체 데이터를 Jinja HTML 템플릿에 렌더링해서 iframe srcDoc에 넣을 HTML을 반환합니다."""
    context = build_clinical_report_context(sample_or_samples)

    # panel_metadata에 logo_path가 없으면 파일 로고를 data URI로 넣어 iframe/PDF에서 바로 보이게 합니다.
    if not context.get("logo_path") or context.get("logo_path") == "-":
        context["logo_path"] = _get_logo_data_uri(template_type)

    if extra_context:
        context.update(extra_context)

    return _render_clinical_report_template(context, template_type=template_type)


def _safe_filename_part(value, default="report"):
    """파일명에 안전하게 쓸 수 있도록 sample_id 등을 정리합니다."""
    text = str(value or default)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    return text or default

# ==========================================
# [2] 화면 레이아웃 구성
# ==========================================
def get_clinical_report_layout():
    clinical_templates = [
        {"label": "TSO500 Clinical Report", "value": "gmc_tso_clinical_report"},
        {"label": "cbNIPT Clinical Report", "value": "cbnipt_clinical_report"},
    ]

    # create_shared_report_layout 내부의 clinical-live-preview-container에 iframe을 직접 넣습니다.
    return html.Div([
        create_shared_report_layout(prefix="clinical", title="Clinical Report 작성 대상", template_options=clinical_templates),
    ])


# ==========================================
# [3] 콜백 로직
# ==========================================
def register_clinical_callbacks(dash_app):
    
    # 1. 배치 목록 업데이트
    @dash_app.callback(
        [Output("clinical-batch-select", "options"), Output("clinical-batch-select", "value")],
        Input("clinical-batch-select", "id") # 더미 트리거
    )
    def update_clinical_batch(_):
        db = SessionLocal()
        try:
            samples = db.query(Sample.sample_id).all()
            batches = sorted(list({f"{s_id[0].split('-')[0]}-{s_id[0].split('-')[1]}-{s_id[0].split('-')[2]}" for s_id in samples if s_id[0] and s_id[0].count("-") >= 2}), reverse=True)
            return [{"label": "전체 보기", "value": "ALL"}] + [{"label": f"📦 배치: {b}", "value": b} for b in batches], "ALL"
        finally: db.close()

    # 2. Grid 렌더링 (TSO DNA/RNA는 base sample id 기준으로 한 row로 묶습니다.)
    @dash_app.callback(
        Output("clinical-grid-container", "children"),
        Input("clinical-batch-select", "value")
    )
    def update_clinical_grid(selected_batch):
        config = REPORT_SCHEMA_CONFIG.get("Clinical Report", {"columns": []})

        base_cols = LimsDashApp.get_base_grid_columns(include_project=True)
        if base_cols:
            base_cols[0]["checkboxSelection"] = True
            base_cols[0]["headerCheckboxSelection"] = True
            base_cols[0]["pinned"] = "left"
            base_cols[0]["width"] = 140
            if len(base_cols) > 1:
                base_cols[1]["pinned"] = "left"

        columnDefs = base_cols + [
            {"headerName": "TSO 구성", "field": "tso_pair", "width": 100},
            {"headerName": "현재 상태", "field": "current_status", "width": 150, "cellStyle": {"fontWeight": "bold", "color": "#198754"}},
            {"headerName": "분석 상태", "field": "analysis_status", "width": 170},
        ]
        columnDefs.extend([{"headerName": col["name"], "field": col["id"], "width": 130} for col in config["columns"]])

        db = SessionLocal()
        try:
            query = db.query(Sample)
            if selected_batch and selected_batch != "ALL":
                query = query.filter(Sample.sample_id.like(f"{selected_batch}-%"))
            samples = query.all()

            tso_groups = {}
            standalone_samples = []

            for sample in samples:
                modality = _sample_modality(sample)
                if _is_tso_sample(sample) and modality in {"DNA", "RNA"}:
                    base_id = _base_sample_id(sample.sample_id)
                    tso_groups.setdefault(base_id, []).append(sample)
                else:
                    standalone_samples.append(sample)

            data = []
            for base_id, grouped_samples in tso_groups.items():
                data.append(_samples_to_tso_grid_row(base_id, grouped_samples, config))

            for sample in standalone_samples:
                data.append(_sample_to_grid_row(sample, config))

            data = sorted(data, key=lambda row: str(row.get("sample_id", "")), reverse=True)

            grid = LimsDashApp.create_standard_aggrid(id="clinical-ag-grid", columnDefs=columnDefs, height="40vh")
            grid.dashGridOptions["rowSelection"] = "multiple"
            grid.dashGridOptions["suppressRowClickSelection"] = True
            grid.rowData = data
            return grid
        finally:
            db.close()

    # 3. 라이브 미리보기 렌더링
    @dash_app.callback(
        [
            Output("clinical-builder-section", "style"),
            Output("clinical-live-preview-container", "children"),
            Output("clinical-upload-preview", "children"),
        ],
        [
            Input("clinical-btn-open-settings", "n_clicks"),
            Input("clinical-template-select", "value"),
            Input("clinical-title-input", "value"),
            Input("clinical-author-input", "value"),
            Input("clinical-upload-image", "contents"),
            Input("clinical-upload-image", "filename"),
        ],
        [State("clinical-ag-grid", "selectedRows")],
        prevent_initial_call=True,
    )
    def update_clinical_preview(btn_click, template_type, title, author, img_contents, img_names, selected_rows):
        if not selected_rows:
            return {"display": "none"}, "", ""

        img_msg = _format_upload_message(img_names)
        db = SessionLocal()
        try:
            first_row = selected_rows[0]
            sample_id = first_row.get("sample_id")
            if not sample_id:
                return (
                    {"display": "block"},
                    html.Pre("오류:\n선택된 행에서 sample_id를 찾을 수 없습니다.", style={"color": "red"}),
                    img_msg,
                )

            samples = _resolve_selected_samples(db, first_row)

            if not samples:
                return (
                    {"display": "block"},
                    html.Pre(f"오류:\n샘플을 찾을 수 없습니다: {sample_id}", style={"color": "red"}),
                    img_msg,
                )

            rendered_html = generate_clinical_html_report(
                samples,
                template_type=template_type,
                extra_context={
                    "report_title": title or "NGS Cancer Panel Report",
                    "author": author or "-",
                    # 현재 gmc_tso_clinical_report.html은 images를 사용하지 않지만,
                    # 다른 clinical 템플릿에서 필요하면 바로 받을 수 있게 비워 두지 않습니다.
                    "uploaded_image_contents": img_contents or [],
                },
            )

            return (
                {"display": "block"},
                html.Iframe(
                    srcDoc=rendered_html,
                    style={"width": "100%", "height": "842px", "border": "none"},
                ),
                img_msg,
            )
        except Exception:
            return (
                {"display": "block"},
                html.Pre(f"오류:\n{traceback.format_exc()}", style={"color": "red"}),
                img_msg,
            )
        finally:
            db.close()

    # 4. 최종 PDF 생성 (WeasyPrint)
    @dash_app.callback(
        [
            Output("clinical-download-pdf-file", "data"),
            Output("clinical-generate-message", "children"),
        ],
        Input("clinical-btn-download-pdf", "n_clicks"),
        [
            State("clinical-ag-grid", "selectedRows"),
            State("clinical-template-select", "value"),
            State("clinical-title-input", "value"),
            State("clinical-author-input", "value"),
            State("clinical-upload-image", "contents"),
        ],
        prevent_initial_call=True,
    )
    def download_clinical_pdf(n_clicks, selected_rows, template_type, title, author, image_contents):
        if not selected_rows:
            return no_update, dbc.Alert("선택된 샘플이 없습니다.", color="warning")

        db = SessionLocal()
        try:
            first_row = selected_rows[0]
            sample_id = first_row.get("sample_id")
            if not sample_id:
                return no_update, dbc.Alert("선택된 행에서 sample_id를 찾을 수 없습니다.", color="warning")

            samples = _resolve_selected_samples(db, first_row)
            if not samples:
                return no_update, dbc.Alert(f"샘플을 찾을 수 없습니다: {sample_id}", color="danger")

            html_out = generate_clinical_html_report(
                samples,
                template_type=template_type,
                extra_context={
                    "report_title": title or "NGS Cancer Panel Report",
                    "author": author or "-",
                    "uploaded_image_contents": image_contents or [],
                },
            )

            try:
                import weasyprint
            except ImportError:
                return no_update, dbc.Alert(
                    "WeasyPrint가 설치되어 있지 않습니다. `pip install weasyprint` 후 다시 실행하세요.",
                    color="danger",
                )

            template_dir, _ = _resolve_clinical_template(template_type)
            pdf_css = weasyprint.CSS(
                string="""
                @page {
                    size: A4;
                    margin: 12mm 10mm 12mm 10mm;
                }
                """
            )

            pdf_bytes = weasyprint.HTML(
                string=html_out,
                base_url=template_dir,
            ).write_pdf(
                stylesheets=[pdf_css],
            )
            filename = (
                f"Clinical_Report_{_safe_filename_part(_base_sample_id(sample_id), 'clinical')}"
                f"_{datetime.now().strftime('%y%m%d')}.pdf"
            )

            # dcc.send_bytes는 bytes 또는 writer 함수를 받을 수 있습니다.
            # writer 방식이 Dash 버전 차이를 가장 덜 탑니다.
            return (
                dcc.send_bytes(lambda buffer: buffer.write(pdf_bytes), filename),
                dbc.Alert("✅ PDF 다운로드 완료!", color="success"),
            )

        except Exception as e:
            print(traceback.format_exc())
            return no_update, dbc.Alert(f"❌ PDF 생성 오류: {e}", color="danger")

        finally:
            db.close()

