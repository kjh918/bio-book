import argparse
import json
import os
from pathlib import Path
from llama_cpp import Llama

SYSTEM_PROMPT = """
You are an AI assistant specialized in fetal and embryonic genetic disorders.
You must NOT make final medical diagnoses or treatment decisions.

CRITICAL LANGUAGE RULES:
1. You MUST write the entire response ONLY in standard Korean (Hangul).
2. DO NOT use any Chinese characters (Hanja/Hanzi) under any circumstances. If you think of a Chinese word, translate it and write it purely in Hangul.
3. Preserve specific scientific/medical terminology in English when necessary.

INTERPRETATION RULES:
- Use only the provided database evidence and retrieved references.
- Prioritize ACMG/AMP guideline-based interpretation principles.
- Mention evidence source categories: ClinVar, PubMed, ACMG guideline.
- If no evidence exists, explicitly state that reliable evidence was not identified.

Output format must follow:
[질환 요약]
[유전적 특징]
[임상적 영향]
[병원성/위험도]
[근거 문헌]
[ACMG/가이드라인 해석]
"""

def load_model(model_path: str):
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {model_path}")

    # 스레드 제한 로직 (CPU 과부하 방지)
    total_cores = os.cpu_count() or 8
    optimal_threads = min(total_cores, 32) 
    
    print(f"Loading GGUF model on CPU with {optimal_threads} threads...")
    
    llm = Llama(
        model_path=model_path,
        n_ctx=4096,          
        n_threads=optimal_threads,
        verbose=False        
    )
    
    # Llama.cpp는 별도의 tokenizer 객체가 필요 없으므로 None 반환
    return None, llm

def load_json_documents(path: str):
    path_obj = Path(path)

    if path_obj.suffix == ".jsonl":
        docs = []
        with path_obj.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    docs.append(json.loads(line))
        return docs

    with path_obj.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        docs = []
        for key, value in data.items():
            if isinstance(value, dict):
                item = value.copy()
                if "pmid" not in item:
                    item["pmid"] = key
                docs.append(item)
        return docs

    raise ValueError("Unsupported JSON format")

def doc_to_text(doc: dict):
    fields = [
        "pmid", "variation_id", "variant_id", "accession", "title", 
        "gene", "classification", "clinical_significance", "review_status", 
        "journal", "abstract", "text", "url"
    ]

    parts = []
    for field in fields:
        value = doc.get(field)
        if value:
            parts.append(f"{field}: {value}")

    if "germline_classification" in doc:
        parts.append(f"germline_classification: {doc['germline_classification']}")

    if "all_pubmed_ids" in doc:
        parts.append(f"all_pubmed_ids: {doc['all_pubmed_ids']}")

    return "\n".join(parts)

def simple_retrieve(query: str, docs: list, top_k: int):
    if not query:
        raise ValueError("query가 누락되었습니다.")
    if top_k is None or top_k <= 0:
        raise ValueError("top_k 값이 올바르지 않습니다.")

    query_tokens = set(query.lower().replace(",", " ").replace(":", " ").split())

    scored = []
    for doc in docs:
        text = doc_to_text(doc)
        text_lower = text.lower()

        score = 0
        for token in query_tokens:
            if token and token in text_lower:
                score += 1

        if score > 0:
            scored.append((score, doc, text))

    scored.sort(key=lambda x: x[0], reverse=True)

    return scored[:top_k]

def build_context(retrieved: list):
    if not retrieved:
        return "No reliable evidence was retrieved from the local JSON database."

    blocks = []
    for i, (score, doc, text) in enumerate(retrieved, start=1):
        pmid = doc.get("pmid", "")
        accession = doc.get("accession", "")
        title = doc.get("title", "")

        blocks.append(
            f"""
[Evidence {i}]
pmid: {pmid}
accession: {accession}
title: {title}
retrieval_score: {score}

{text}
"""
        )

    return "\n".join(blocks)

# [MODIFIED] 문제의 원인이었던 generate_response 함수를 Llama.cpp 전용으로 교체
def generate_response(
    tokenizer,  # UI와의 파라미터 호환성을 위해 남겨둠 (실제로는 None)
    model,
    user_prompt: str,
    context: str,
    system_prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
):
    if not user_prompt:
        raise ValueError("user_prompt가 비어있습니다.")
        
    prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\nContext: {context}\nQuestion: {user_prompt}<|im_end|>\n<|im_start|>assistant\n"
    
    # tokenizer(...) 호출 코드를 완전히 삭제하고 model 객체 직접 호출
    output = model(
        prompt,
        max_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        stop=["<|im_end|>"]
    )
    
    # 딕셔너리 구조에서 텍스트 결과만 추출하여 반환
    return output["choices"][0]["text"]