#!/usr/bin/env python3
import os
import sys
import requests

# (이전에 작성한 parse_metrics_tsv, parse_combined_variant_tsv 함수는 그대로 유지)
def parse_metrics_tsv(metrics_path):
    metrics_data = {}
    with open(metrics_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('[') or line.startswith('#'): continue
            parts = line.split('\t')
            if len(parts) >= 2:
                metrics_data[parts[0].strip().lower().replace(" ", "_").replace(".", "")] = parts[1].strip()

    return {
        "tumor_purity": float(metrics_data.get("tumor_purity", metrics_data.get("estimated_tumor_purity", 35.0))),
        "tmb_score": float(metrics_data.get("tmb_score", metrics_data.get("total_tmb", 0.0))),
        "tmb_status": metrics_data.get("tmb_status", "TMB-Low"),
        "msi_status": metrics_data.get("msi_status", "MSS"),
        "unstable_msi_sites_rate": float(metrics_data.get("unstable_msi_sites_rate", 0.0)),
        "mapped_reads_pct": float(metrics_data.get("mapped_reads_pct", 100.0)),
    }

def parse_combined_variant_tsv(variant_path):
    small_variants = []
    current_section, headers = None, []
    with open(variant_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1].strip().lower()
                headers = [] 
                continue
            parts = line.split('\t')
            if not headers and ("gene" in [p.lower() for p in parts] or "sample id" in [p.lower() for p in parts]):
                headers = [p.strip().lower() for p in parts]
                continue
            if not headers: continue
            
            row_dict = dict(zip(headers, [p.strip() for p in parts]))
            if "small variants" in current_section:
                gene = row_dict.get("gene")
                if gene and gene.upper() != "GENE":
                    try:
                        vaf_str = row_dict.get("variant allele frequency", row_dict.get("vaf", "0"))
                        vaf = float(vaf_str.replace("%", "")) / 100.0 if "%" in vaf_str else float(vaf_str)
                        small_variants.append({
                            "gene": gene,
                            "variant_type": row_dict.get("variant type", "missense variant"),
                            "protein_change": row_dict.get("protein", "-"),
                            "cds_change": row_dict.get("nucleotide", "-"),
                            "vaf": vaf,
                            "depth": int(row_dict.get("depth", 0))
                        })
                    except Exception: pass
    return small_variants


def upload_to_lims(lims_url, batch_id, order_id, sample_id, pipeline_version, metrics, variants):
    """
    3중 교차 검증 식별자와 함께 다형성(Polymorphic) JSON 포맷으로 LIMS에 슛팅합니다.
    """
    payload = {
        "batch_id": batch_id,
        "order_id": order_id,
        "sample_id": sample_id,
        "pipeline_version": pipeline_version,
        
        # 🚀 다형성 라우팅 필드 (TSO500 규격 강제 적용)
        "results": {
            "analysis_type": "TSO500", # 서버에서 이 값으로 스키마를 판별합니다.
            "tumor_purity": metrics["tumor_purity"],
            "tmb_score": metrics["tmb_score"],
            "msi_status": metrics["msi_status"],
            "mapped_reads_pct": metrics["mapped_reads_pct"],
            "variants": variants # 파싱된 SNV/INDEL 등 변이 리스트
        }
    }
    
    headers = {"Content-Type": "application/json"}
    target_endpoint = f"{lims_url.rstrip('/')}/api/v1/analysis/result"
    
    print(f"📡 LIMS DB로 전송 중... (Order: {order_id} | Sample: {sample_id})")
    
    try:
        response = requests.post(target_endpoint, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print("🎉 [성공] 결과가 LIMS 데이터베이스에 안전하게 매핑되었습니다.")
        else:
            print(f"❌ [실패] HTTP {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"💥 [네트워크 오류] {e}")

if __name__ == "__main__":
    LIMS_SERVER_URL = "http://127.0.0.1:8000"
    PIPELINE_VERSION = "v2.2.0"
    
    # 🚀 사용법 및 인자 개수 변경
    if len(sys.argv) < 6:
        print("사용법: python upload_tso500_to_lims.py [BATCH_ID] [ORDER_ID] [SAMPLE_ID] [Metrics.tsv] [Variant.tsv]")
        sys.exit(1)
        
    TARGET_BATCH_ID = sys.argv[1]
    TARGET_ORDER_ID = sys.argv[2]
    TARGET_SAMPLE_ID = sys.argv[3]
    METRICS_FILE = sys.argv[4]
    VARIANT_FILE = sys.argv[5]
    
    print(f"▶️ BATCH: {TARGET_BATCH_ID} | ORDER: {TARGET_ORDER_ID} | SAMPLE: {TARGET_SAMPLE_ID}")
    
    parsed_metrics = parse_metrics_tsv(METRICS_FILE)
    small_vars = parse_combined_variant_tsv(VARIANT_FILE)
    
    upload_to_lims(
        lims_url=LIMS_SERVER_URL,
        batch_id=TARGET_BATCH_ID,
        order_id=TARGET_ORDER_ID,
        sample_id=TARGET_SAMPLE_ID,
        pipeline_version=PIPELINE_VERSION,
        metrics=parsed_metrics,
        variants=small_vars
    )