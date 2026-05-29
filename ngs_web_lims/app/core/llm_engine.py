import argparse
import json
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM


SYSTEM_PROMPT = """
You are an AI assistant specialized in fetal and embryonic genetic disorders.

You must NOT make final medical diagnoses or treatment decisions.

You must:
- Use only the provided database evidence and retrieved references.
- Prioritize ACMG/AMP guideline-based interpretation principles.
- Clearly distinguish established evidence, uncertain evidence, and speculation.
- Explain limitations when evidence is insufficient.
- Always provide responses in Korean.
- Preserve scientific terminology in English when needed.
- Mention evidence source categories: ClinVar, PubMed, AMCG guideline, internal classification rule.
- Do not hallucinate missing clinical evidence.
- If no evidence exists, explicitly state that reliable evidence was not identified.

Output format must follow:

[질환 요약]
[유전적 특징]
[임상적 영향]
[병원성/위험도]
[근거 문헌]
[AMCG/가이드라인 해석]
[주의사항 및 한계]
"""


def load_model(model_id: str):
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    print("Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float32,
        device_map="cpu"
    )

    return tokenizer, model


def load_json_documents(path: str):
    """
    Supports:
    1. JSONL: one JSON object per line
    2. JSON list: [{...}, {...}]
    3. JSON dict: {"pmid": {...}, "pmid2": {...}}
    """
    path = Path(path)

    if path.suffix == ".jsonl":
        docs = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    docs.append(json.loads(line))
        return docs

    with path.open("r", encoding="utf-8") as f:
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
        "pmid",
        "variation_id",
        "variant_id",
        "accession",
        "title",
        "gene",
        "classification",
        "clinical_significance",
        "review_status",
        "journal",
        "abstract",
        "text",
        "url",
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


def simple_retrieve(query: str, docs: list, top_k: int = 5):
    """
    Very simple keyword retrieval.
    Later replace this with FAISS embedding search.
    """
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


def build_context(retrieved):
    if not retrieved:
        return "No reliable evidence was retrieved from the local JSON database."

    blocks = []

    for i, (score, doc, text) in enumerate(retrieved, start=1):
        source = doc.get("source", "local_json")
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


def generate_response(
    tokenizer,
    model,
    user_prompt: str,
    context: str,
    system_prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
):
    prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\nContext: {context}\nQuestion: {user_prompt}<|im_end|>\n<|im_start|>assistant\n"
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    # 2. 답변 생성
    outputs = model.generate(
        **inputs, 
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p
    )
    
    # 🚀 [핵심 해결법] 전체 출력에서 '입력된 프롬프트 길이'만큼 잘라내야 순수 답변만 남습니다!
    input_length = inputs.input_ids.shape[1]
    generated_tokens = outputs[0][input_length:]
    
    # 디코딩 후 순수 답변만 리턴
    pure_response = tokenizer.decode(generated_tokens, skip_special_tokens=True)
    
    return pure_response


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        type=str,
        default="Qwen/Qwen2.5-0.5B-Instruct"
    )

    parser.add_argument(
        "--prompt",
        type=str,
        required=True
    )

    parser.add_argument(
        "--json_path",
        type=str,
        required=True,
        help="Path to JSON or JSONL evidence file"
    )

    parser.add_argument(
        "--top_k",
        type=int,
        default=5
    )

    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=512
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3
    )

    parser.add_argument(
        "--top_p",
        type=float,
        default=0.9
    )

    args = parser.parse_args()

    print("Loading JSON evidence...")
    docs = load_json_documents(args.json_path)
    print(f"Loaded documents: {len(docs)}")

    print("Retrieving evidence...")
    retrieved = simple_retrieve(
        query=args.prompt,
        docs=docs,
        top_k=args.top_k
    )

    context = build_context(retrieved)

    print("\n===== RETRIEVED EVIDENCE =====")
    print(context)

    tokenizer, model = load_model(args.model)

    response = generate_response(
        tokenizer=tokenizer,
        model=model,
        user_prompt=args.prompt,
        context=context,
        system_prompt=SYSTEM_PROMPT,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
    )

    print("\n===== RESPONSE =====\n")
    print(response)


if __name__ == "__main__":
    main()