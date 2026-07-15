from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from datetime import datetime
import os, json, ast, re, traceback, base64
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.database import SessionLocal
from app.models._schema import Sample, REPORT_SCHEMA_CONFIG
from app.pages.base import LimsDashApp
from app.core.config import BASE_DIR
from app.pages.report.base import create_shared_report_layout


# ============================================================
# 섹션 1: 공통 유틸
# ============================================================

def _parse_json_like(value):
    """DB 저장값을 재귀적으로 파싱하고 빈 값을 None으로 정규화합니다."""
    if isinstance(value, dict):
        result = {k: _parse_json_like(v) for k, v in value.items()}
        return {k: v for k, v in result.items() if v is not None and v != []}
    if isinstance(value, list):
        return [_parse_json_like(v) for v in value if _parse_json_like(v) is not None]
    if isinstance(value, str):
        s = value.strip()
        if not s or s.upper() in {"NA", "N/A", "NONE", "NULL"}:
            return None
        if s.startswith(("{", "[")):
            for parser in [
                lambda x: json.loads(x),
                lambda x: ast.literal_eval(
                    x.replace("null", "None").replace("true", "True")
                     .replace("false", "False").replace("nan", "None")
                ),
                lambda x: json.loads(re.sub(r"'([^']*)'", r'"\1"', x)),
            ]:
                try:
                    return _parse_json_like(parser(s))
                except Exception:
                    continue
        return s
    return value


def _display(value, default="-"):
    """템플릿 출력용 문자열로 변환합니다."""
    value = _parse_json_like(value)
    if value is None or value == "" or value == [] or value == {}:
        return default
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (dict, list)):
        return value
    return str(value)


def _to_float(value):
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    try:
        return float(match.group(0)) if match else None
    except (ValueError, AttributeError):
        return None


def _is_blank(value):
    return str(value or "").strip().lower() in {"", "-", "na", "n/a", "none", "null", "nan"}


def _is_truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "hotspot"}


def _safe_filename(value, default="report"):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or default)).strip("._")
    return text or default


# ============================================================
# 섹션 2: flat_data 파서
# flat_data 구조를 명시적으로 처리합니다.
# ============================================================

def _flatten_analysis_data(raw_data):
    """
    analysis_results dict를 한 depth 평탄화합니다.
    "metrics" / "variants" 중첩 섹션은 바깥으로 꺼냅니다.
    """
    data = _parse_json_like(raw_data) or {}
    if not isinstance(data, dict):
        return {}

    flat = {}
    for key, value in data.items():
        value = _parse_json_like(value)
        if key in ("metrics", "variants") and isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _get_section(flat_data, *keys, default=None):
    """flat_data에서 대소문자 무관하게 첫 번째 매칭 키의 값을 반환합니다."""
    lookup = {k.lower(): v for k, v in flat_data.items()}
    for key in keys:
        value = lookup.get(key.lower())
        if value is not None:
            return _parse_json_like(value)
    return default


def _get_qc_value(qc_section, metric_key, default="-"):
    """
    QC 섹션에서 metric 값을 꺼냅니다.
    값 형태: {"value": "89.89/90.9", "section": ..., "metric": ...}
    또는 단순 문자열/숫자.
    """
    if not isinstance(qc_section, dict):
        return default
    entry = qc_section.get(metric_key)
    if entry is None:
        return default
    if isinstance(entry, dict):
        return _display(entry.get("value"), default=default)
    return _display(entry, default=default)


# ============================================================
# 섹션 3: 샘플 modality 판별 (DNA / RNA)
# sample_info["Extraction_type"] 우선, sample_id suffix 보조
# ============================================================

def _extraction_type_from_info(flat_data):
    """sample_info 섹션의 Extraction_type 필드를 반환합니다."""
    sample_info = _get_section(flat_data, "Sample_Info", "sample_info", default={})
    if not isinstance(sample_info, dict):
        return ""
    return str(sample_info.get("Extraction_type", "") or "").strip().upper()


def _modality_from_sample_id(sample_id):
    match = re.search(r"[-_](DNA|RNA)$", str(sample_id or ""), flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _sample_modality(sample):
    """Sample 객체에서 DNA/RNA modality를 결정합니다."""
    flat = _flatten_analysis_data(
        sample.analysis.analysis_results if getattr(sample, "analysis", None) else {}
    )
    extraction = _extraction_type_from_info(flat)
    if extraction in {"DNA", "RNA"}:
        return extraction

    from_id = _modality_from_sample_id(getattr(sample, "sample_id", ""))
    if from_id:
        return from_id

    nat = str(getattr(sample, "nucleic_acid_type", "") or "").upper()
    if "DNA" in nat and "RNA" not in nat:
        return "DNA"
    if "RNA" in nat and "DNA" not in nat:
        return "RNA"
    return ""


def _sort_by_modality(samples):
    order = {"DNA": 0, "RNA": 1, "": 2}
    return sorted(samples or [], key=lambda s: (order.get(_sample_modality(s), 9),
                                                 str(getattr(s, "sample_id", ""))))


def _primary_sample(samples):
    sorted_s = _sort_by_modality(samples)
    return sorted_s[0] if sorted_s else None


def _base_sample_id(sample_id):
    return re.sub(r"[-_](DNA|RNA)$", "", str(sample_id or "").strip(), flags=re.IGNORECASE)


# ============================================================
# 섹션 4: DNA / RNA flat_data 분리 병합
# ============================================================

def _split_by_modality(samples):
    """
    samples 목록을 DNA flat_data / RNA flat_data 로 분리합니다.
    Returns: (dna_flat, rna_flat)  –  없으면 {}
    """
    dna_flat, rna_flat = {}, {}

    for sample in _sort_by_modality(samples):
        raw = sample.analysis.analysis_results if getattr(sample, "analysis", None) else {}
        flat = _flatten_analysis_data(raw)
        modality = _sample_modality(sample)

        if modality == "DNA":
            dna_flat = flat
        elif modality == "RNA":
            rna_flat = flat
        else:
            # modality 불명 → DNA 취급 (single sample 기본값)
            if not dna_flat:
                dna_flat = flat

    return dna_flat, rna_flat


def _merge_flat_data(dna_flat, rna_flat):
    """
    DNA를 기준 컨텍스트로, RNA에서 Fusion/Splice를 보완합니다.
    """
    combined = dict(dna_flat)

    # DNA에 없는 키는 RNA에서 보완
    for key, value in rna_flat.items():
        if key not in combined or combined[key] in (None, "", [], {}):
            combined[key] = value

    # RNA 전용 바이오마커 명시적 오버라이드
    for key, value in rna_flat.items():
        norm = key.lower().replace("_", "")
        if "fusion" in norm or "splicevariant" in norm or "splice" in norm:
            combined[key] = value

    return combined


# ============================================================
# 섹션 5: QC 메트릭 빌더 (DNA / RNA 각각)
# ============================================================
def _validate_and_convert_to_float(metric_name: str, value: any, ndigits: int = 2) -> float:
    """
    [MODIFIED] Rule 0 반영: default 값(예: 0.0 이나 '-') 부여를 차단하고, 
    값이 누락되거나 형식에 맞지 않으면 파이프라인/DB 데이터를 고칠 수 있도록 즉시 명시적 에러를 발생시킵니다.
    """
    if value is None or str(value).strip() in ["", "-", "NA", "N/A"]:
        raise ValueError(f"🚨 QC 검증 에러: '{metric_name}' 값이 누락되었거나 부적절한 기호입니다. (입력값: '{value}')")
    try:
        return round(float(value), ndigits)
    except (ValueError, TypeError):
        raise ValueError(f"🚨 QC 검증 에러: '{metric_name}' 항목은 숫자로 변환 가능해야 합니다. (입력값: '{value}')")

def _build_dna_qc_metrics(sample, dna_flat):
    """
    DNA QC 메트릭을 flat_data["QC"] + flat_data["Sample_Info"] 기준으로 구성합니다.

    실제 DNA QC 섹션 키:
      Q30, GC, Mean_target_coverage, Median_target_coverage,
      Median_insert_size, Pct_read_enrichment, Pct_exon_50x,
      Pct_target_100x, Total_pf_reads, Uniformity,
      Usable_msi_sites, Pct_chimeric_reads
    """
    if not dna_flat:
        return []

    qc = _get_section(dna_flat, "QC", default={})
    if not isinstance(qc, dict):
        return []

    def get(key):
        return _get_qc_value(qc, key)

    sample_info = _get_section(dna_flat, "Sample_Info", default={})
    conc        = _display(sample_info.get("Concentration")) if isinstance(sample_info, dict) else "-"
    r1_q_value = round(float(qc.get('Q30').get('value').split('/')[0]),1)
    r2_q_value = round(float(qc.get('Q30').get('value').split('/')[1]),1)
    q_value = f'{r1_q_value}/{r2_q_value}'
    print(sample.panel_metadata['dna_concentration'])
    return [
        {"Metric": "Sample conc. (ng/µL)",      "Value": sample.panel_metadata['dna_concentration']},
        {"Metric": "Q30 R1/R2 (%)",             "Value": q_value},
        {"Metric": "GC R1/R2 (%)",              "Value": qc.get('GC').get('value')},
        {"Metric": "Total PF reads",             "Value": qc.get('Total_pf_reads').get('value')},
        {"Metric": "Mean target coverage (x)",  "Value": qc.get('Mean_target_coverage').get('value')},
        {"Metric": "Median target coverage (x)","Value": qc.get('Median_target_coverage').get('value')},
        {"Metric": "Median insert size (bp)",   "Value": qc.get('Median_insert_size').get('value')},
        {"Metric": "Read enrichment (%)",        "Value": qc.get('PCT_READ_ENRICHMENT_Pct').get('value')},
        {"Metric": "Exon ≥50x (%)",             "Value": qc.get('PCT_EXON_50X_Pct').get('value')},
        {"Metric": "Target ≥100x (%)",          "Value": qc.get('PCT_TARGET_100X_Pct').get('value')},
        {"Metric": "Uniformity (%)",             "Value": qc.get('Uniformity').get('value')},
        {"Metric": "Contamination Score",        "Value": qc.get('CONTAMINATION_SCORE_NA').get('value')},
        {"Metric": "Chimeric reads (%)",         "Value": qc.get('PCT_CHIMERIC_READS_Pct').get('value')},
    ]


def _build_rna_qc_metrics(rna_flat):
    """
    RNA QC 메트릭. DNA 단독 샘플이면 rna_flat=={} → 빈 리스트 반환 → 템플릿 공란.

    실제 RNA QC 섹션 키:
      Q30, GC, Scaled_median_gene_coverage, Median_insert_size,
      Pct_chimeric_reads, Pct_on_target_reads,
      Total_on_target_reads, Total_pf_reads,
      Uniquely_mapped_rate, Median_cv_gene_500x
    """
    if not rna_flat:
        return []  # DNA 단독 → 공란

    qc = _get_section(rna_flat, "QC", default={})
    if not isinstance(qc, dict):
        return []

    def get(key):
        return _get_qc_value(qc, key)

    sample_info = _get_section(rna_flat, "Sample_Info", default={})
    conc        = _display(sample_info.get("Concentration")) if isinstance(sample_info, dict) else "-"
    return [
        {"Metric": "Sample conc. (ng/µL)",        "Value": conc},
        {"Metric": "Q30 R1/R2 (%)",               "Value": get("Q30")},
        {"Metric": "GC R1/R2 (%)",                "Value": get("GC")},
        {"Metric": "On-target reads (%)",          "Value": get("Pct_on_target_reads")},
        {"Metric": "Total on-target reads",        "Value": get("Total_on_target_reads")},
        {"Metric": "Total PF reads",               "Value": get("Total_pf_reads")},
        {"Metric": "Median insert size (bp)",      "Value": get("Median_insert_size")},
        {"Metric": "Scaled median gene cov. (x)",  "Value": get("Scaled_median_gene_coverage")},
        {"Metric": "CV gene 500x",                 "Value": get("Median_cv_gene_500x")},
        {"Metric": "Uniquely mapped rate (%)",     "Value": get("Uniquely_mapped_rate")},
        {"Metric": "Chimeric reads (%)",           "Value": get("Pct_chimeric_reads")},
    ]


# ============================================================
# 섹션 6: Small Variant 필터 및 포매터
# ============================================================

VAF_MIN_THRESHOLD    = float(os.environ.get("CLINICAL_VAF_MIN_THRESHOLD",    0.01))
VAF_REPORT_THRESHOLD = float(os.environ.get("CLINICAL_VAF_REPORT_THRESHOLD", 0.05))
DEPTH_MIN            = int(os.environ.get("CLINICAL_DEPTH_MIN",              100))

EXCLUDE_CONSEQUENCES = {
    "synonymous_variant", "intron_variant", "intergenic_variant",
    "upstream_gene_variant", "downstream_gene_variant",
    "3_prime_utr_variant", "5_prime_utr_variant", "utr_variant",
    "non_coding_transcript_exon_variant", "non_coding_transcript_variant",
}
INCLUDE_CONSEQUENCES = {
    "missense_variant", "frameshift_variant", "stop_gained", "stop_lost",
    "start_lost", "splice_acceptor_variant", "splice_donor_variant",
    "splice_region_variant", "inframe_deletion", "inframe_insertion",
    "protein_altering_variant", "coding_sequence_variant",
}

SMALL_VARIANT_REPORT_COLUMNS = [
    "Gene", "Pos", "REF->ALT", "Depth", "VAF",
    "Consequence", "Reference", "HGVSc", "HGVSp",
]

def _get_variant_field(row, *candidates, default=""):
    """variant row dict에서 대소문자 무관하게 첫 매칭 값을 반환합니다."""
    lookup = {k.lower().replace(" ", "_").replace("-", "_"): v for k, v in row.items()}
    for c in candidates:
        v = lookup.get(c.lower().replace(" ", "_").replace("-", "_"))
        if v is not None:
            return str(v).strip()
    return default


def _csq_set(row):
    raw = _get_variant_field(
        row, "Consequences", "Consequence", "consequence",
        "variant_type", "Variant_Type",
    )
    return {c.strip().lower() for c in re.sub(r"[;/]", ",", raw).split(",") if c.strip()}


def filter_small_variants(variants):
    """
    (included, excluded) 튜플 반환.
    included: 보고서 본문 대상
    excluded: 필터 탈락 (현재 보고서에서 사용 안 함)
    """
    included, excluded = [], []

    for v in variants or []:
        if not isinstance(v, dict):
            continue

        gene = _get_variant_field(v, "Gene", "gene", "Gene_Name", "gene_name")
        vaf  = _to_float(_get_variant_field(v, "Allele_Frequency", "Allele Frequency", "VAF", "vaf")) or 0.0
        dp   = _to_float(_get_variant_field(v, "DP", "Depth", "depth", "Read_Depth")) or 0.0
        csq  = _csq_set(v)
        is_hotspot = _is_truthy(_get_variant_field(v, "Hotspot", "hotspot", "is_hotspot", "HOTSPOT"))

        reason = None
        if _is_blank(gene):
            reason = "Gene name 없음"
        elif vaf < VAF_MIN_THRESHOLD:
            reason = f"VAF {vaf:.3f} < {VAF_MIN_THRESHOLD}"
        elif dp < DEPTH_MIN:
            reason = f"Depth {int(dp)} < {DEPTH_MIN}"
        elif csq and csq.issubset(EXCLUDE_CONSEQUENCES):
            reason = f"Consequence 제외 ({', '.join(sorted(csq))})"
        elif not is_hotspot and not csq.intersection(INCLUDE_CONSEQUENCES) and vaf < VAF_REPORT_THRESHOLD:
            reason = f"임상적 의의 없는 변이 (VAF {vaf:.3f})"

        row = dict(v)
        if reason:
            row["_filter_reason"] = reason
            excluded.append(row)
        else:
            included.append(row)

    return included, excluded


def _split_hgvs(raw):
    """'NM_...:c.123A>T' → (reference, notation)"""
    text = str(raw or "").strip()
    if not text or text == "-":
        return "", ""
    if ":" in text:
        ref, notation = text.split(":", 1)
        return ref.strip(), notation.strip()
    return "", text


def _format_position(row):
    chrom = _get_variant_field(row, "Chromosome", "Chr", "CHROM", "chrom")
    pos   = _get_variant_field(row, "Genomic_Position", "Genomic Position", "Position",
                                "POS", "pos", "Start_Position", "Start Position")
    if chrom and pos:
        chrom = re.sub(r"^chr", "", chrom, flags=re.IGNORECASE)
        return f"chr{chrom}:{pos}"
    return _get_variant_field(row, "Pos", "Position")


def _format_ref_alt(row):
    ref = _get_variant_field(row, "Reference_Call", "Reference Call", "Reference_Allele",
                              "Reference Allele", "REF", "Ref", "ref")
    alt = _get_variant_field(row, "Alternative_Call", "Alternative Call", "Alternate_Allele",
                              "Alternate Allele", "ALT", "Alt", "alt")
    if ref or alt:
        return f"{ref}->{alt}"
    return _get_variant_field(row, "REF->ALT", "Ref->Alt", "Ref Alt")


def _format_small_variant_row(row):
    """
    원본 Small Variant row → 보고서 9컬럼 dict.

    실제 DNA payload HGVS 필드:
      C_Dot_Notation: "NM_003820.3:c.50A>G"   → Reference=NM_003820.3, HGVSc=c.50A>G
      P_Dot_Notation: "NP_003811.2:p.(Lys17Arg)" → HGVSp=p.Lys17Arg (괄호 제거)
    Reference 우선순위: NM_ (C_Dot) > NP_ (P_Dot) > Transcript 필드
    """
    hgvsc_raw = _get_variant_field(
        row, "C_Dot_Notation", "HGVSc", "HGVS.c", "HGVS_C",
        "C Dot Notation", "cDNA_Change", "cDNA Change",
    )
    hgvsp_raw = _get_variant_field(
        row, "P_Dot_Notation", "HGVSp", "HGVS.p", "HGVS_P",
        "P Dot Notation", "Protein_Change", "Protein Change",
    )
    # 괄호 제거: "p.(Lys17Arg)" → "p.Lys17Arg"
    hgvsp_raw = hgvsp_raw.replace("(", "").replace(")", "")

    ref_c, hgvsc = _split_hgvs(hgvsc_raw)   # NM_... / c.50A>G
    ref_p, hgvsp = _split_hgvs(hgvsp_raw)   # NP_... / p.Lys17Arg

    if hgvsp and "c." in hgvsp:
        hgvsp = "p." + hgvsp.split("p.", 1)[1]

    # Reference: NM_ 우선 (transcript), NP_ 보조, 그 외 Transcript 필드
    reference = ref_c or ref_p or _get_variant_field(
        row, "Transcript", "Transcript_ID", "Transcript ID",
        "Feature", "RefSeq", "RefSeq_ID", "Reference",
    )

    return {
        "Gene":        _get_variant_field(row, "Gene", "gene", "Gene_Name", "gene_name"),
        "Pos":         _format_position(row),
        "REF->ALT":    _format_ref_alt(row),
        "Depth":       _get_variant_field(row, "Depth", "DP", "depth", "Read_Depth", "Read Depth"),
        "VAF":         _get_variant_field(row, "Allele_Frequency", "VAF", "Allele Frequency", "allele_frequency"),
        "Consequence": _get_variant_field(row, "Consequences"),
        "Reference":   reference,
        "HGVSc":       hgvsc,
        "HGVSp":       hgvsp,
    }


# ============================================================
# 섹션 7: Biomarker 빌더 (TMB / MSI)
# ============================================================

def _build_tmb(merged_flat):
    """
    flat_data["TMB"] 기준으로 TMB 컨텍스트를 구성합니다.

    실제 DNA payload TMB 키:
      Total_TMB, Coding_Region_Size_in_Megabases,
      Number_of_Passing_Eligible_Variants
    """
    raw = _parse_json_like(_get_section(merged_flat, "TMB", "Tumor Mutational Burden"))
    if raw is None:
        return {}

    if isinstance(raw, dict):
        # 실제 키 우선, 구버전 키 fallback
        score = _display(
            raw.get("Total_TMB")
            or raw.get("Total TMB")
            or raw.get("TMB")
            or raw.get("TMB Score")
            or raw.get("Score")
        )
        eligible = _display(
            raw.get("Number_of_Passing_Eligible_Variants")
            or raw.get("Eligible Variants")
            or raw.get("Eligible_Variants"),
            default="-",
        )
        coding_region = _display(
            raw.get("Coding_Region_Size_in_Megabases")
            or raw.get("Coding Region Size")
            or raw.get("Coding_region_size"),
            default="1.24 Mb",
        )
        # coding_region 값이 단위 없는 숫자면 "X Mb" 형식으로 통일
        if coding_region != "-" and not coding_region.endswith("Mb"):
            coding_region = f"{coding_region} Mb"
    else:
        score         = _display(raw)
        eligible      = "-"
        coding_region = "1.24 Mb"

    score_float = _to_float(score)
    status = ("-" if score_float is None
              else "TMB-High" if score_float >= 10
              else "TMB-Low")

    return {
        "TMB_status":         status,
        "TMB":                f"{score} muts/Mb" if score != "-" else "-",
        "Eligible_variants":  eligible,
        "Coding_region_size": coding_region,
    }


def _build_msi(merged_flat):
    """
    flat_data["MSI"] 기준으로 MSI 컨텍스트를 구성합니다.

    실제 DNA payload MSI 키:
      Percent_Unstable_MSI_Sites, Total_MSI_Sites_Unstable, Usable_MSI_Sites
    """
    raw = _parse_json_like(_get_section(merged_flat, "MSI", "Microsatellite Instability"))
    if raw is None:
        return {}

    if isinstance(raw, dict):
        rate = _display(
            raw.get("Percent_Unstable_MSI_Sites")
            or raw.get("Percent Unstable MSI Sites")
            or raw.get("MSI Rate")
            or raw.get("Rate")
        )
        unstable = _display(
            raw.get("Total_MSI_Sites_Unstable")
            or raw.get("Unstable MSI Sites")
            or raw.get("Unstable MSI Regions"),
            default="-",
        )
        usable = _display(
            raw.get("Usable_MSI_Sites")
            or raw.get("Usable MSI Sites")
            or raw.get("Total Usable MSI Sites"),
            default="-",
        )
    else:
        rate     = _display(raw)
        unstable = "-"
        usable   = "-"

    rate_float = _to_float(rate)
    status = ("-" if rate_float is None
              else "Microsatellite Instability-High (MSI-H)" if rate_float >= 20
              else "Microsatellite Stable (MSS)")

    return {
        "MSI_status":                  status,
        "Unstable MSI sites rate (%)": rate,
        "Unstable MSI sites":          unstable,
        "Total usable MSI sites":      usable,
    }


# ============================================================
# 섹션 8: Variant row 유틸
# ============================================================

def _pick_rows(flat_data, *keys):
    """flat_data에서 첫 번째 유효한 리스트를 반환합니다."""
    for key in keys:
        value = _parse_json_like(_get_section(flat_data, key))
        rows = _as_rows(value)
        if rows:
            return rows
    return []


def _as_rows(value):
    if value is None:
        return []
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and all(isinstance(v, dict) for v in value.values()):
        rows = list(value.values())
    elif isinstance(value, dict):
        rows = [value]
    else:
        return []
    return [
        {str(k): _display(v, default="") for k, v in row.items()}
        for row in rows if isinstance(row, dict)
    ]


def _fixed_columns(rows, preferred):
    """preferred 컬럼을 앞에 고정하고, rows에서 추가 컬럼을 뒤에 붙입니다."""
    columns = list(preferred)
    for row in rows or []:
        for col in row.keys():
            if not col.startswith("_") and col not in columns:
                columns.append(col)
    return columns


# ============================================================
# 섹션 9: 메타데이터 유틸
# ============================================================

def _panel_metadata(sample):
    pm = _parse_json_like(getattr(sample, "panel_metadata", None)) or {}
    return pm if isinstance(pm, dict) else {}


def _merge_panel_metadata(samples):
    merged = {}
    for sample in reversed(_sort_by_modality(samples)):
        merged.update(_panel_metadata(sample))
    return merged


def _report_sample_id(samples):
    primary = _primary_sample(samples)
    if not primary:
        return "-"
    modalities = {_sample_modality(s) for s in samples}
    if len(samples) > 1 and {"DNA", "RNA"}.intersection(modalities):
        return _base_sample_id(getattr(primary, "sample_id", ""))
    return getattr(primary, "sample_id", "-")


def _combined_status(samples, analysis=False):
    labeled = []
    values  = []
    for s in _sort_by_modality(samples):
        modality = _sample_modality(s) or str(getattr(s, "sample_id", ""))
        value    = (s.analysis.analysis_status
                    if analysis and getattr(s, "analysis", None)
                    else getattr(s, "current_status", "") or "-")
        values.append(value)
        labeled.append(f"{modality}:{value}")
    unique = {v for v in values if v}
    return values[0] if len(unique) == 1 else " / ".join(labeled)


def _is_tso_sample(sample):
    panel = str(getattr(sample, "target_panel", "") or "").lower()
    return "tso" in panel or "trusight oncology" in panel


# ============================================================
# 섹션 10: 리포트 컨텍스트 빌더 (메인)
# ============================================================

def build_clinical_report_context(sample_or_samples):
    """
    Jinja2 템플릿에 넘길 context dict를 생성합니다.
    DNA+RNA pair, DNA 단독, RNA 단독 모두 처리합니다.
    """
    samples = ([s for s in sample_or_samples if s is not None]
               if isinstance(sample_or_samples, (list, tuple))
               else [sample_or_samples] if sample_or_samples else [])

    samples = _sort_by_modality(samples)
    sample  = _primary_sample(samples)
    

    if sample is None:
        raise ValueError("리포트를 생성할 Sample이 없습니다.")

    dna_flat, rna_flat = _split_by_modality(samples)
    merged_flat        = _merge_flat_data(dna_flat, rna_flat)
    pm                 = _merge_panel_metadata(samples)
    order              = sample.order
    print(sample.panel_metadata)
    # ── Small Variants ──────────────────────────────────────
    raw_svs                  = _pick_rows(merged_flat, "Small_Variants", "Small Variants", "small_variants")
    included_svs, _excl_svs  = filter_small_variants(raw_svs)
    small_variants           = [_format_small_variant_row(v) for v in included_svs]

    # ── RNA-side 바이오마커 ─────────────────────────────────
    fusions        = _pick_rows(rna_flat or merged_flat, "Fusions", "Fusion")
    splice_variants = _pick_rows(rna_flat or merged_flat, "Splice_Variants", "Splice Variants")

    # ── DNA-side 바이오마커 ─────────────────────────────────
    gene_amplifications = _pick_rows(dna_flat or merged_flat,
                                     "Gene_Amplifications", "Gene Amplifications")

    # ── 컬럼 정의 ───────────────────────────────────────────
    gene_amp_cols   = _fixed_columns(gene_amplifications,   ["Gene", "Fold_Change"])
    splice_cols     = _fixed_columns(splice_variants,       ["Gene", "Affected_Exon", "Breakpoint_1",
                                                              "Breakpoint_2", "Splice_Supporting_Reads",
                                                              "Reference", "Reads", "Transcript"])
    fusion_cols     = _fixed_columns(fusions,               ["Gene_Pair", "Breakpoint 1", "Breakpoint 2",
                                                              "Fusion_Supporting_Reads",
                                                              "Gene_1_Reference_Reads",
                                                              "Gene_2_Reference_Reads"])

    # Sample_Info 에서 DB에 없는 필드를 보완합니다 (DNA payload 기준)
    dna_sample_info = _get_section(dna_flat, "Sample_Info", default={}) if dna_flat else {}
    if not isinstance(dna_sample_info, dict):
        dna_sample_info = {}

    def _si(key, fallback=None):
        """Sample_Info 우선 → panel_metadata → DB 필드 → fallback 순으로 값을 찾습니다."""
        return (dna_sample_info.get(key)
                or pm.get(key)
                or fallback)

    # Pipeline_Version: Analysis_Details 또는 Header 에서 꺼냅니다.
    analysis_details = _get_section(merged_flat, "Analysis_Details", default={})
    header           = _get_section(merged_flat, "Header", default={})
    pipeline_version = (
        (analysis_details.get("Pipeline_Version") if isinstance(analysis_details, dict) else None)
        or (header.get("Workflow_Version") if isinstance(header, dict) else None)
    )

    return {
        # Header
        "logo_path":        pm.get("logo_path", ""),

        # Patient  (DB → Sample_Info 보완)
        "patient_name":     _display(sample.sample_name or _si("Patient_Name")),
        "patient_id":       '-',#_display(_report_sample_id(samples)),
        "cancer_type":      '-', #_display(getattr(sample, "cancer_type", None) or _si("Diagnosis")),
        "specimen_type":    _display(getattr(sample, "specimen", None) or _si("Specimen_type")),
        "specimen_site":    _display(_si("Specimen_Site") or _si("Specimen site")
                                     or getattr(sample, "specimen", None)),

        # Order
        "facility":         '젠큐릭스',#_display(getattr(order, "facility", None) if order else None),
        "facility_id":      '-',#_display(_si("Facility_ID") or _si("Facility ID")),
        "physician":        '-',#_display(getattr(order, "client_name", None) if order else None),
        "pathologist":      '-',#_display(_si("Pathologist")),
        # date_of_order: DB reception_date → Sample_Info.Date_of_order 순
        "date_of_order":    _display(
            (getattr(order, "reception_date", None) if order else None)
            or dna_sample_info.get("Date_of_order")
        ),

        # Specimen
        "specimen_id":      _display(getattr(sample, "outside_id_1", None)
                                     or _si("Case_ID") or _si("Sample_ID")),
        "tumor_purity":     _display(_si("Tumor_Purity") or _si("Tumor purity")),
        "date_of_collection": _display(_si("Collection_Date") or _si("Date of collection")),

        # Case
        "panel":            _display(
            getattr(sample, "target_panel", None)
            or _si("Panel_information"),
            default="TruSight Oncology 500",
        ),
        "pipeline":         _display(_get_section(merged_flat, "Pipeline", "Workflow"), default="NGS-TSO-v1"),
        "pipeline_version": _display(pipeline_version, default="-"),
        "analyst":          _display(_si("Analyst")),
        "date_of_receipt":  _display(getattr(order, "reception_date", None) if order else None),
        "date_of_report":   datetime.now().strftime("%Y-%m-%d"),

        # QC  –  DNA 단독이면 rna_qc_metrics == []
        "dna_qc_metrics":   _build_dna_qc_metrics(sample, dna_flat),
        "rna_qc_metrics":   _build_rna_qc_metrics(rna_flat),

        # Variants
        "small_variants":          small_variants,
        "small_variant_cols":      list(SMALL_VARIANT_REPORT_COLUMNS),
        "excluded_variants":       [],
        "excluded_variant_cols":   [],
        "gene_amplifications":     gene_amplifications,
        "gene_amplification_cols": gene_amp_cols,
        "splice_variants":         splice_variants,
        "splice_variant_cols":     splice_cols,
        "fusions":                 fusions,
        "fusion_cols":             fusion_cols,

        # Biomarkers
        "tmb": _build_tmb(merged_flat),
        "msi": _build_msi(merged_flat),

        # Meta
        "extraction_type":   ("DNA/RNA" if (dna_flat and rna_flat)
                              else ("RNA" if rna_flat else "DNA")),
        "paired_sample_ids": [getattr(s, "sample_id", "") for s in samples],
    }


# ============================================================
# 섹션 11: 템플릿 렌더링
# ============================================================

CLINICAL_REPORT_TEMPLATE_NAME = "gmc_tso_clinical_report.html"
CLINICAL_REPORT_TEMPLATE_PATH = os.environ.get("CLINICAL_REPORT_TEMPLATE_PATH")
CLINICAL_REPORT_TEMPLATE_DIR  = os.environ.get("CLINICAL_REPORT_TEMPLATE_DIR")

_TEMPLATE_DIR_CANDIDATES = [
    os.path.join(BASE_DIR, "app", "templates", "reports", "analysis"),
    os.path.join(BASE_DIR, "app", "templates", "reports"),
    os.path.join(os.path.dirname(__file__), "templates"),
]
if CLINICAL_REPORT_TEMPLATE_DIR:
    _TEMPLATE_DIR_CANDIDATES.insert(0, CLINICAL_REPORT_TEMPLATE_DIR)


def _resolve_template(template_type=None):
    if CLINICAL_REPORT_TEMPLATE_PATH:
        return (os.path.dirname(CLINICAL_REPORT_TEMPLATE_PATH),
                os.path.basename(CLINICAL_REPORT_TEMPLATE_PATH))

    name = str(template_type or CLINICAL_REPORT_TEMPLATE_NAME).strip()
    if not name.endswith(".html"):
        name += ".html"

    for directory in _TEMPLATE_DIR_CANDIDATES:
        if directory and os.path.exists(os.path.join(directory, name)):
            return directory, name

    return _TEMPLATE_DIR_CANDIDATES[0], name


def _image_to_data_uri(path):
    if not path or not os.path.exists(path):
        return ""
    ext  = os.path.splitext(path)[1].lower()
    mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _logo_data_uri(template_type=None):
    name = "gmc_logo.png" if "gmc" in str(template_type or "").lower() else "logo.png"
    candidates = [
        os.path.join(BASE_DIR, "app", "templates", "reports", name),
        os.path.join(BASE_DIR, "app", "templates", "reports", "clinical", name),
        os.path.join(os.path.dirname(__file__), "templates", name),
    ]
    for path in candidates:
        uri = _image_to_data_uri(path)
        if uri:
            return uri
    return ""


def _render_template(context, template_type=None):
    template_dir, template_name = _resolve_template(template_type)
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
    )
    return env.get_template(template_name).render(**context)


def generate_clinical_html_report(sample_or_samples, template_type=None, extra_context=None):
    context = build_clinical_report_context(sample_or_samples)

    if not context.get("logo_path") or context["logo_path"] == "-":
        context["logo_path"] = _logo_data_uri(template_type)

    if extra_context:
        context.update(extra_context)

    return _render_template(context, template_type=template_type)


# ============================================================
# 섹션 12: Grid 유틸 (DB 조회 / row 변환)
# ============================================================

def _decode_sample_ids(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    text = str(value).strip()
    if text.startswith("["):
        try:
            return _decode_sample_ids(json.loads(text))
        except Exception:
            pass
    return [p.strip() for p in text.split(",") if p.strip()]


def _query_samples(db, sample_ids):
    ids = list(dict.fromkeys(sid for sid in sample_ids if sid))
    if not ids:
        return []
    return _sort_by_modality(db.query(Sample).filter(Sample.sample_id.in_(ids)).all())


def _resolve_selected_samples(db, selected_row):
    if not selected_row:
        return []

    sample_ids = []
    sample_ids.extend(_decode_sample_ids(selected_row.get("sample_ids")))
    for key in ("dna_sample_id", "rna_sample_id"):
        if selected_row.get(key):
            sample_ids.append(str(selected_row[key]))

    resolved = _query_samples(db, sample_ids)
    if resolved:
        return resolved

    selected_id = str(selected_row.get("sample_id") or "").strip()
    if not selected_id:
        return []

    base_id = _base_sample_id(selected_id)
    pair_ids = [f"{base_id}-DNA", f"{base_id}-RNA", f"{base_id}_DNA", f"{base_id}_RNA"]
    paired = _query_samples(db, pair_ids)
    if paired:
        return paired

    exact = db.query(Sample).filter(Sample.sample_id == selected_id).first()
    return [exact] if exact else []


def _sample_to_grid_row(sample, config):
    metadata = _panel_metadata(sample)
    a_status = (sample.analysis.analysis_status
                if getattr(sample, "analysis", None) else "대기중")

    row = {
        "id":               getattr(sample, "id", None),
        "project_name":     getattr(sample, "project_name", ""),
        "order_id":         getattr(sample, "order_id", ""),
        "sample_id":        getattr(sample, "sample_id", ""),
        "sample_ids":       [getattr(sample, "sample_id", "")],
        "dna_sample_id":    getattr(sample, "sample_id", "") if _sample_modality(sample) == "DNA" else "",
        "rna_sample_id":    getattr(sample, "sample_id", "") if _sample_modality(sample) == "RNA" else "",
        "tso_pair":         _sample_modality(sample) or "-",
        "sample_name":      getattr(sample, "sample_name", ""),
        "target_panel":     getattr(sample, "target_panel", ""),
        "nucleic_acid_type": getattr(sample, "nucleic_acid_type", "") or _sample_modality(sample),
        "current_status":   getattr(sample, "current_status", ""),
        "analysis_status":  a_status,
    }
    for col in config.get("columns", []):
        col_id   = col["id"]
        row[col_id] = getattr(sample, col_id, "") or metadata.get(col_id, "")
    return row


def _samples_to_tso_grid_row(base_id, samples, config):
    samples = _sort_by_modality(samples)
    primary = _primary_sample(samples)
    row     = _sample_to_grid_row(primary, config)

    dna        = next((s for s in samples if _sample_modality(s) == "DNA"), None)
    rna        = next((s for s in samples if _sample_modality(s) == "RNA"), None)
    sample_ids = [getattr(s, "sample_id", "") for s in samples]

    row.update({
        "id":               "|".join(str(getattr(s, "id", "")) for s in samples),
        "sample_id":        base_id,
        "sample_ids":       sample_ids,
        "dna_sample_id":    getattr(dna, "sample_id", "") if dna else "",
        "rna_sample_id":    getattr(rna, "sample_id", "") if rna else "",
        "tso_pair":         ("DNA+RNA" if dna and rna else ("DNA만" if dna else "RNA만")),
        "nucleic_acid_type": ("DNA/RNA" if dna and rna else (_sample_modality(primary) or "-")),
        "current_status":   _combined_status(samples, analysis=False),
        "analysis_status":  _combined_status(samples, analysis=True),
    })
    return row


# ============================================================
# 섹션 13: 레이아웃
# ============================================================

def get_clinical_report_layout():
    clinical_templates = [
        {"label": "TSO500 Clinical Report",  "value": "gmc_tso_clinical_report"},
        {"label": "cbNIPT Clinical Report",  "value": "cbnipt_clinical_report"},
    ]
    return html.Div([
        create_shared_report_layout(
            prefix="clinical",
            title="Clinical Report 작성 대상",
            template_options=clinical_templates,
        ),
    ])


# ============================================================
# 섹션 14: Dash 콜백
# ============================================================

def register_clinical_callbacks(dash_app):

    # ── 배치 목록 ────────────────────────────────────────────
    @dash_app.callback(
        [Output("clinical-batch-select", "options"),
         Output("clinical-batch-select", "value")],
        Input("clinical-batch-select", "id"),
    )
    def update_batch(_):
        db = SessionLocal()
        try:
            sample_ids = [row[0] for row in db.query(Sample.sample_id).all()]
            batches = sorted(
                {"-".join(sid.split("-")[:3]) for sid in sample_ids
                 if sid and sid.count("-") >= 2},
                reverse=True,
            )
            options = [{"label": "전체 보기", "value": "ALL"}] + \
                      [{"label": f"📦 배치: {b}", "value": b} for b in batches]
            return options, "ALL"
        finally:
            db.close()

    # ── Grid 렌더링 ──────────────────────────────────────────
    @dash_app.callback(
        Output("clinical-grid-container", "children"),
        Input("clinical-batch-select", "value"),
    )
    def update_grid(selected_batch):
        config    = REPORT_SCHEMA_CONFIG.get("Clinical Report", {"columns": []})
        base_cols = LimsDashApp.get_base_grid_columns(include_project=True)

        if base_cols:
            base_cols[0].update({"checkboxSelection": True, "headerCheckboxSelection": True,
                                  "pinned": "left", "width": 140})
            if len(base_cols) > 1:
                base_cols[1]["pinned"] = "left"

        column_defs = base_cols + [
            {"headerName": "TSO 구성",  "field": "tso_pair",         "width": 100},
            {"headerName": "현재 상태", "field": "current_status",    "width": 150,
             "cellStyle": {"fontWeight": "bold", "color": "#198754"}},
            {"headerName": "분석 상태", "field": "analysis_status",   "width": 170},
        ] + [{"headerName": col["name"], "field": col["id"], "width": 130}
             for col in config["columns"]]

        db = SessionLocal()
        try:
            query   = db.query(Sample)
            if selected_batch and selected_batch != "ALL":
                query = query.filter(Sample.sample_id.like(f"{selected_batch}-%"))
            samples = query.all()

            tso_groups   = {}
            standalone   = []

            for sample in samples:
                modality = _sample_modality(sample)
                if _is_tso_sample(sample) and modality in {"DNA", "RNA"}:
                    tso_groups.setdefault(_base_sample_id(sample.sample_id), []).append(sample)
                else:
                    standalone.append(sample)

            data = (
                [_samples_to_tso_grid_row(bid, sps, config) for bid, sps in tso_groups.items()] +
                [_sample_to_grid_row(s, config) for s in standalone]
            )
            data.sort(key=lambda r: str(r.get("sample_id", "")), reverse=True)

            grid = LimsDashApp.create_standard_aggrid(
                id="clinical-ag-grid", columnDefs=column_defs, height="40vh"
            )
            grid.dashGridOptions["rowSelection"]              = "multiple"
            grid.dashGridOptions["suppressRowClickSelection"] = True
            grid.rowData = data
            return grid
        finally:
            db.close()

    # ── 라이브 미리보기 ──────────────────────────────────────
    @dash_app.callback(
        [Output("clinical-builder-section",        "style"),
         Output("clinical-live-preview-container", "children"),
         Output("clinical-upload-preview",         "children")],
        [Input("clinical-btn-open-settings",  "n_clicks"),
         Input("clinical-template-select",    "value"),
         Input("clinical-title-input",        "value"),
         Input("clinical-author-input",       "value"),
         Input("clinical-upload-image",       "contents"),
         Input("clinical-upload-image",       "filename")],
        State("clinical-ag-grid", "selectedRows"),
        prevent_initial_call=True,
    )
    def update_preview(_, template_type, title, author, img_contents, img_names, selected_rows):
        img_msg = (f"📎 첨부됨: {', '.join(img_names)}"
                   if img_names else "첨부된 이미지가 없습니다.")

        if not selected_rows:
            return {"display": "none"}, "", img_msg

        db = SessionLocal()
        try:
            first_row = selected_rows[0]
            sample_id = first_row.get("sample_id")
            if not sample_id:
                return ({"display": "block"},
                        html.Pre("오류: 선택된 행에서 sample_id를 찾을 수 없습니다.",
                                  style={"color": "red"}),
                        img_msg)

            samples = _resolve_selected_samples(db, first_row)
            if not samples:
                return ({"display": "block"},
                        html.Pre(f"오류: 샘플을 찾을 수 없습니다: {sample_id}",
                                  style={"color": "red"}),
                        img_msg)

            html_out = generate_clinical_html_report(
                samples,
                template_type=template_type,
                extra_context={
                    "report_title":            title or "NGS Cancer Panel Report",
                    "author":                  author or "-",
                    "uploaded_image_contents": img_contents or [],
                },
            )
            return (
                {"display": "block"},
                html.Iframe(srcDoc=html_out,
                            style={"width": "100%", "height": "842px", "border": "none"}),
                img_msg,
            )
        except Exception:
            return ({"display": "block"},
                    html.Pre(f"오류:\n{traceback.format_exc()}", style={"color": "red"}),
                    img_msg)
        finally:
            db.close()

    # ── PDF 다운로드 ─────────────────────────────────────────
    @dash_app.callback(
        [Output("clinical-download-pdf-file",  "data"),
         Output("clinical-generate-message",   "children")],
        Input("clinical-btn-download-pdf", "n_clicks"),
        [State("clinical-ag-grid",          "selectedRows"),
         State("clinical-template-select",  "value"),
         State("clinical-title-input",      "value"),
         State("clinical-author-input",     "value"),
         State("clinical-upload-image",     "contents")],
        prevent_initial_call=True,
    )
    def download_pdf(_, selected_rows, template_type, title, author, image_contents):
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
                    "report_title":            title or "NGS Cancer Panel Report",
                    "author":                  author or "-",
                    "uploaded_image_contents": image_contents or [],
                },
            )

            try:
                import weasyprint
            except ImportError:
                return no_update, dbc.Alert(
                    "WeasyPrint 미설치. `pip install weasyprint` 후 재실행하세요.", color="danger"
                )

            template_dir, _ = _resolve_template(template_type)
            pdf_bytes = weasyprint.HTML(
                string=html_out, base_url=template_dir,
            ).write_pdf(
                stylesheets=[weasyprint.CSS(string="@page { size: A4; margin: 12mm 10mm; }")]
            )

            filename = (
                f"Clinical_Report_{_safe_filename(_base_sample_id(sample_id), 'clinical')}"
                f"_{datetime.now().strftime('%y%m%d')}.pdf"
            )
            return (
                dcc.send_bytes(lambda buf: buf.write(pdf_bytes), filename),
                dbc.Alert("✅ PDF 다운로드 완료!", color="success"),
            )

        except Exception as e:
            print(traceback.format_exc())
            return no_update, dbc.Alert(f"❌ PDF 생성 오류: {e}", color="danger")
        finally:
            db.close()