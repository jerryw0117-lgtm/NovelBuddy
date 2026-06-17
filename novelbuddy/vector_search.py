from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from .cli import read_json

# 与蛙趣插件 embeddingModel.js 保持一致
EMBEDDING_MODEL_ID = "BAAI/bge-small-zh-v1.5"
EMBEDDING_QUERY_PREFIX = "为这个句子生成表示以用于检索中文文档："
VECTOR_WEIGHT = 0.65
RRF_K = 30
BM25_K1 = 1.5
BM25_B = 0.75
STOP_WORDS = {"的", "了", "在", "是", "我", "他", "她", "和", "与", "等", "个", "这", "那", "有", "为", "一个", "没有", "可以"}

SOURCE_TYPE_LABELS = {
    "world_setting": "世界观",
    "character_profile": "人物",
    "character_state": "角色状态",
    "outline": "大纲",
    "chapter_summary": "摘要",
    "foreshadow": "伏笔",
    "organization": "组织",
    "character_relationship": "关系",
    "chapter": "章节",
    "material": "素材",
}


@dataclass
class VectorEntry:
    id: str
    content: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KeywordIndex:
    term_frequency: dict[str, dict[str, int]]
    document_frequency: dict[str, int]
    total_documents: int
    avg_doc_length: float


def vector_store_path(root: Path | str) -> Path:
    return Path(root) / ".novel-assistant" / "memory" / "vector_store.json"


def load_vector_entries(root: Path | str) -> list[VectorEntry]:
    path = vector_store_path(root)
    if not path.exists():
        return []
    raw = read_json(path, [])
    items = raw if isinstance(raw, list) else raw.get("vectors", []) if isinstance(raw, dict) else []
    entries: list[VectorEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        vector = item.get("vector")
        entry_id = str(item.get("id") or "").strip()
        if not content or not entry_id or not isinstance(vector, list) or not vector:
            continue
        entries.append(
            VectorEntry(
                id=entry_id,
                content=content,
                vector=[float(v) for v in vector],
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            )
        )
    return entries


def tokenize_cn(text: str) -> list[str]:
    clean = re.sub(r"\s+", "", text.lower())
    tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[a-z0-9]{2,}", clean)
    return [token for token in tokens if token not in STOP_WORDS]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    norm_left = 0.0
    norm_right = 0.0
    for a, b in zip(left, right):
        dot += a * b
        norm_left += a * a
        norm_right += b * b
    denom = math.sqrt(norm_left) * math.sqrt(norm_right)
    return dot / denom if denom else 0.0


def build_keyword_index(entries: list[VectorEntry]) -> KeywordIndex:
    term_frequency: dict[str, dict[str, int]] = {}
    document_frequency: dict[str, int] = {}
    total_len = 0
    for entry in entries:
        tokens = tokenize_cn(entry.content)
        freq: dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        term_frequency[entry.id] = freq
        total_len += len(tokens)
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    total_docs = max(len(entries), 1)
    avg_doc_length = total_len / total_docs
    return KeywordIndex(term_frequency, document_frequency, total_docs, avg_doc_length)


def bm25_for_entry(entry_id: str, query_tokens: list[str], index: KeywordIndex) -> float:
    term_freq = index.term_frequency.get(entry_id)
    if not term_freq or not query_tokens:
        return 0.0
    doc_len = sum(term_freq.values())
    score = 0.0
    for token in query_tokens:
        freq = term_freq.get(token, 0)
        if not freq:
            continue
        df = index.document_frequency.get(token, 0)
        idf = math.log(1 + (index.total_documents - df + 0.5) / (df + 0.5))
        denom = freq + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / max(index.avg_doc_length, 1))
        score += idf * (freq * (BM25_K1 + 1)) / max(denom, 0.001)
    return score


def keyword_search_entries(entries: list[VectorEntry], query: str, limit: int) -> list[tuple[VectorEntry, float]]:
    query_tokens = tokenize_cn(query)
    if not query_tokens:
        return []
    index = build_keyword_index(entries)
    ranked: list[tuple[float, VectorEntry]] = []
    for entry in entries:
        score = bm25_for_entry(entry.id, query_tokens, index)
        if query in entry.content:
            score += 3.0
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(entry, score) for score, entry in ranked[:limit]]


@lru_cache(maxsize=1)
def _load_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_ID)


def embed_query(query: str) -> list[float] | None:
    text = f"{EMBEDDING_QUERY_PREFIX}{query.strip()}"
    try:
        model = _load_embedding_model()
        vector = model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vector]
    except Exception:
        return None


def vector_search_entries(entries: list[VectorEntry], query: str, limit: int) -> list[tuple[VectorEntry, float]]:
    query_vector = embed_query(query)
    if not query_vector:
        return []
    ranked: list[tuple[float, VectorEntry]] = []
    for entry in entries:
        similarity = cosine_similarity(query_vector, entry.vector)
        if similarity > 0:
            ranked.append((similarity, entry))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(entry, score) for score, entry in ranked[:limit]]


def fusion_rank_rrf(
    vector_hits: list[tuple[VectorEntry, float]],
    keyword_hits: list[tuple[VectorEntry, float]],
    limit: int,
    vector_weight: float = VECTOR_WEIGHT,
) -> list[dict[str, Any]]:
    alpha = max(0.0, min(1.0, vector_weight))
    beta = 1.0 - alpha
    score_map: dict[str, dict[str, Any]] = {}

    for idx, (entry, similarity) in enumerate(vector_hits):
        score_map[entry.id] = {
            "entry": entry,
            "vector_score": similarity,
            "keyword_score": 0.0,
            "fusion_score": alpha / (RRF_K + idx + 1),
            "search_method": "vector",
        }

    for idx, (entry, keyword_score) in enumerate(keyword_hits):
        rrf = beta / (RRF_K + idx + 1)
        existing = score_map.get(entry.id)
        if existing:
            existing["keyword_score"] = keyword_score
            existing["fusion_score"] += rrf
            existing["search_method"] = "hybrid"
        else:
            score_map[entry.id] = {
                "entry": entry,
                "vector_score": 0.0,
                "keyword_score": keyword_score,
                "fusion_score": rrf,
                "search_method": "keyword",
            }

    ranked = sorted(score_map.values(), key=lambda item: item["fusion_score"], reverse=True)
    return ranked[:limit]


def entry_title(entry: VectorEntry) -> str:
    first_line = entry.content.splitlines()[0].strip()
    if len(first_line) > 48:
        return first_line[:48] + "…"
    return first_line or entry.id


def entry_kind(entry: VectorEntry) -> str:
    source_type = str(entry.metadata.get("sourceType") or "").strip()
    return SOURCE_TYPE_LABELS.get(source_type, "向量")


def make_snippet(content: str, query: str, limit: int = 120) -> str:
    clean = re.sub(r"\s+", " ", content).strip()
    pos = clean.find(query)
    if pos >= 0:
        start = max(0, pos - 40)
        return clean[start : start + limit]
    return clean[:limit]


def hybrid_search_vector_store(root: Path | str, query: str, limit: int = 80) -> tuple[list[dict[str, Any]], str]:
    query = str(query or "").strip()
    if not query:
        return [], "empty"

    entries = load_vector_entries(root)
    if not entries:
        return [], "missing"

    candidate_limit = max(limit * 2, 30)
    keyword_hits = keyword_search_entries(entries, query, candidate_limit)
    vector_hits = vector_search_entries(entries, query, candidate_limit)

    if vector_hits:
        mode = "hybrid"
        fused = fusion_rank_rrf(vector_hits, keyword_hits, limit)
    else:
        mode = "keyword_only"
        fused = [
            {
                "entry": entry,
                "vector_score": 0.0,
                "keyword_score": score,
                "fusion_score": score,
                "search_method": "keyword",
            }
            for entry, score in keyword_hits[:limit]
        ]

    results: list[dict[str, Any]] = []
    for item in fused:
        entry: VectorEntry = item["entry"]
        results.append(
            {
                "kind": entry_kind(entry),
                "title": entry_title(entry),
                "location": f"vector_store.json#{entry.id}",
                "path": "",
                "snippet": make_snippet(entry.content, query),
                "score": round(float(item["fusion_score"]), 4),
                "vectorScore": round(float(item["vector_score"]), 4),
                "keywordScore": round(float(item["keyword_score"]), 4),
                "searchMethod": item["search_method"],
                "sourceType": entry.metadata.get("sourceType", ""),
            }
        )
    return results, mode


def embedding_status(root: Path | str) -> dict[str, Any]:
    entries = load_vector_entries(root)
    dims_path = Path(root) / ".novel-assistant" / "memory" / "embedding_dimensions.json"
    dims = read_json(dims_path, {}) if dims_path.exists() else {}
    query_vector = None
    model_ready = False
    try:
        query_vector = embed_query("测试")
        model_ready = bool(query_vector)
    except Exception:
        model_ready = False
    return {
        "entryCount": len(entries),
        "model": dims.get("model") or EMBEDDING_MODEL_ID,
        "dimensions": dims.get("dimensions") or (len(query_vector) if query_vector else None),
        "semanticReady": model_ready,
    }


CHAPTER_CHUNK_SIZE = 500
CHAPTER_CHUNK_OVERLAP = 100


def _chunk_chapter_text(text: str, chunk_size: int = CHAPTER_CHUNK_SIZE, overlap: int = CHAPTER_CHUNK_OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n" + para if overlap else para
        else:
            current = current + "\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:chunk_size]]


def build_chapter_vector_index(root: Path | str, chapter_numbers: list[int] | None = None) -> dict[str, Any]:
    root = Path(root)
    path = vector_store_path(root)
    existing_raw = read_json(path, []) if path.exists() else []
    existing_items = existing_raw if isinstance(existing_raw, list) else existing_raw.get("vectors", []) if isinstance(existing_raw, dict) else []
    existing_ids = {str(item.get("id", "")) for item in existing_items if isinstance(item, dict)}

    chapters_dir = root / "AAA" / "chapters"
    if not chapters_dir.exists():
        for d in root.iterdir():
            if d.is_dir() and (d / "chapters").exists():
                chapters_dir = d / "chapters"
                break

    new_entries: list[dict[str, Any]] = []
    skipped = 0
    indexed = 0

    if not chapters_dir.exists():
        return {"error": "未找到章节目录", "new": 0, "skipped": 0}

    chapter_files = sorted(
        [f for f in chapters_dir.iterdir()
         if f.is_file() and f.suffix.lower() == ".md" and "章" in f.name
         and "审查" not in f.stem and ".bak-" not in f.stem],
        key=lambda f: f.name,
    )

    for cf in chapter_files:
        import re as _re
        m = _re.search(r"第(\d+)章", cf.name)
        if not m:
            continue
        ch_num = int(m.group(1))
        if chapter_numbers and ch_num not in chapter_numbers:
            continue

        content = cf.read_text(encoding="utf-8")
        title_match = _re.search(r"第\d+章\s*(.+?)(?:\n|$)", content)
        title = title_match.group(1).strip() if title_match else cf.stem

        chunks = _chunk_chapter_text(content)
        for ci, chunk in enumerate(chunks):
            entry_id = f"ch{ch_num:03d}_p{ci:03d}"
            if entry_id in existing_ids:
                skipped += 1
                continue

            embedding = embed_query(chunk)
            if not embedding:
                continue

            new_entries.append({
                "id": entry_id,
                "content": chunk,
                "vector": embedding,
                "metadata": {
                    "sourceType": "chapter",
                    "sourceId": f"chapter_{ch_num}",
                    "chapterNumber": ch_num,
                    "chunkIndex": ci,
                    "title": f"第{ch_num}章 {title}",
                    "timestamp": int(__import__("time").time() * 1000),
                },
            })
            indexed += 1

    if new_entries:
        all_items = existing_items + new_entries
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            __import__("json").dumps(all_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "new": indexed,
        "skipped": skipped,
        "total": len(existing_items) + len(new_entries),
        "chapters": len(chapter_files),
    }