from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .cli import (
    ProjectData,
    as_list,
    backup_assistant_file,
    chapter_number_from_name,
    check_character_consistency,
    check_foreshadow_health,
    check_outline_deviation,
    load_novelbuddy_state,
    read_json,
    read_text,
    update_chapter_state,
    write_json,
)


ENTITY_TYPES = ("character", "foreshadow", "organization", "relationship", "summary", "world")


def assistant_dir(root: Path) -> Path:
    return root / ".novel-assistant"


def assistant_file_paths(root: Path) -> dict[str, Path]:
    na = assistant_dir(root)
    return {
        "characters": na / "characters.json",
        "relationships": na / "characterRelationships.json",
        "foreshadows": na / "foreshadows.json",
        "organizations": na / "organizations.json",
        "summaries": na / "summaries.json",
        "world": na / "world-setting.json",
        "outlines": na / "outlines.json",
        "refineTemplates": na / "xiezuoguize" / "custom-prompts.json",
        "stylePackages": na / "xiezuoguize" / "custom-style-packages.json",
        "vectorStore": na / "memory" / "vector_store.json",
    }


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    stamp = int(datetime.now().timestamp() * 1000)
    return f"{prefix}_{stamp}"


def is_valid_for_chapter(item: dict[str, Any], chapter: int) -> bool:
    valid_from = int(item.get("validFromChapter") or 0)
    invalid_after = int(item.get("invalidAfterChapter") or item.get("invalidAfter") or 0)
    if valid_from and chapter < valid_from:
        return False
    if invalid_after and chapter > invalid_after:
        return False
    return True


def load_organizations(root: Path) -> list[dict[str, Any]]:
    path = assistant_file_paths(root)["organizations"]
    return as_list(read_json(path, [])) if path.exists() else []


def load_entity_store(root: Path, entity_type: str) -> tuple[list[dict[str, Any]] | dict[str, Any], Path | None]:
    paths = assistant_file_paths(root)
    if entity_type == "world":
        path = paths["world"]
        if not path.exists():
            return {}, path
        value = read_json(path, {})
        return value if isinstance(value, dict) else {}, path
    key_map = {
        "character": "characters",
        "foreshadow": "foreshadows",
        "organization": "organizations",
        "relationship": "relationships",
        "summary": "summaries",
    }
    key = key_map.get(entity_type)
    if not key:
        raise ValueError(f"未知实体类型: {entity_type}")
    path = paths[key]
    return as_list(read_json(path, [])), path


def save_entity_store(
    root: Path,
    entity_type: str,
    value: list[dict[str, Any]] | dict[str, Any],
) -> dict[str, Any]:
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"未知实体类型: {entity_type}")
    _, path = load_entity_store(root, entity_type)
    if path is None:
        path = assistant_file_paths(root)[
            {
                "character": "characters",
                "foreshadow": "foreshadows",
                "organization": "organizations",
                "relationship": "relationships",
                "summary": "summaries",
                "world": "world",
            }[entity_type]
        ]
    backup = backup_assistant_file(path, root) if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, value)
    return {"path": str(path), "backup": str(backup) if backup else ""}


def upsert_list_item(items: list[dict[str, Any]], item: dict[str, Any], id_field: str = "id") -> list[dict[str, Any]]:
    item_id = str(item.get(id_field, "")).strip()
    if not item_id:
        item_id = new_id("ID")
        item[id_field] = item_id
    now = now_iso()
    item.setdefault("createdAt", now)
    item["updatedAt"] = now
    replaced = False
    result: list[dict[str, Any]] = []
    for existing in items:
        if str(existing.get(id_field, "")) == item_id:
            merged = {**existing, **item}
            merged[id_field] = item_id
            result.append(merged)
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(item)
    return result


def delete_list_item(items: list[dict[str, Any]], item_id: str, id_field: str = "id") -> list[dict[str, Any]]:
    clean = str(item_id or "").strip()
    return [item for item in items if str(item.get(id_field, "")) != clean]


def save_entity(root: Path, entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .entity_enums import normalize_entity_payload

    payload = normalize_entity_payload(entity_type, payload)
    if entity_type == "world":
        current, _ = load_entity_store(root, "world")
        if not isinstance(current, dict):
            current = {}
        merged = {**current, **payload}
        merged.setdefault("id", current.get("id", "WORLD001"))
        merged["updatedAt"] = now_iso()
        result = save_entity_store(root, "world", merged)
        result["item"] = merged
        return result

    items, _ = load_entity_store(root, entity_type)
    if not isinstance(items, list):
        items = []
    updated = upsert_list_item(items, payload)
    result = save_entity_store(root, entity_type, updated)
    item_id = str(payload.get("id") or updated[-1].get("id", ""))
    saved = next((item for item in updated if str(item.get("id", "")) == item_id), payload)
    result["item"] = saved
    return result


def delete_entity(root: Path, entity_type: str, item_id: str) -> dict[str, Any]:
    if entity_type == "world":
        raise ValueError("世界观不支持删除，请直接编辑。")
    items, _ = load_entity_store(root, entity_type)
    if not isinstance(items, list):
        items = []
    updated = delete_list_item(items, item_id)
    result = save_entity_store(root, entity_type, updated)
    result["deletedId"] = item_id
    return result


def list_entities(root: Path, entity_type: str) -> list[dict[str, Any]] | dict[str, Any]:
    value, _ = load_entity_store(root, entity_type)
    return value


def load_refine_templates(root: Path) -> list[dict[str, Any]]:
    path = assistant_file_paths(root)["refineTemplates"]
    templates = as_list(read_json(path, []))
    style_path = assistant_file_paths(root)["stylePackages"]
    styles = as_list(read_json(style_path, []))
    return templates + [{"id": f"style_{idx}", "name": s.get("name", "风格包"), "content": s.get("content", "")} for idx, s in enumerate(styles)]


def tokenize_cn(text: str) -> list[str]:
    clean = re.sub(r"\s+", "", text.lower())
    tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[a-z0-9]{2,}", clean)
    stop = {"的", "了", "在", "是", "我", "他", "她", "和", "与", "等", "个", "这", "那", "有", "为", "一个", "没有", "可以"}
    return [token for token in tokens if token not in stop]


def bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_len: float, doc_freq: dict[str, int], total_docs: int) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    k1 = 1.5
    b = 0.75
    doc_len = len(doc_tokens)
    tf: dict[str, int] = {}
    for token in doc_tokens:
        tf[token] = tf.get(token, 0) + 1
    score = 0.0
    for token in query_tokens:
        freq = tf.get(token, 0)
        if not freq:
            continue
        df = doc_freq.get(token, 0)
        idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
        denom = freq + k1 * (1 - b + b * doc_len / max(avg_len, 1))
        score += idf * (freq * (k1 + 1)) / max(denom, 0.001)
    return score


def collect_search_documents(data: ProjectData) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for char in data.characters:
        docs.append(
            {
                "kind": "人物",
                "title": str(char.get("name", "")),
                "location": "characters.json",
                "text": " ".join(
                    str(char.get(key, "")) for key in ("name", "role", "description", "personality", "background", "aliases")
                ),
            }
        )
    for org in load_organizations(data.root):
        docs.append(
            {
                "kind": "组织",
                "title": str(org.get("name", "")),
                "location": "organizations.json",
                "text": " ".join(str(org.get(key, "")) for key in ("name", "type", "description", "leader", "goals", "location")),
            }
        )
    for fw in data.foreshadows:
        docs.append(
            {
                "kind": "伏笔",
                "title": str(fw.get("keyword", "")),
                "location": "foreshadows.json",
                "text": " ".join(str(fw.get(key, "")) for key in ("keyword", "description", "status", "importance")),
            }
        )
    for summary in data.summaries:
        docs.append(
            {
                "kind": "摘要",
                "title": f"第{summary.get('chapterNumber', summary.get('chapter', ''))}章",
                "location": "summaries.json",
                "text": str(summary.get("summary", "") or summary.get("content", "")),
            }
        )
    for outline in data.outlines:
        docs.append(
            {
                "kind": "大纲",
                "title": f"第{outline.get('chapterNumber', '')}章 {outline.get('title', '')}",
                "location": "outlines.json",
                "text": str(outline.get("content", "")),
            }
        )
    if isinstance(data.world, dict):
        docs.append(
            {
                "kind": "世界观",
                "title": str(data.world.get("title", "世界观")),
                "location": "world-setting.json",
                "text": " ".join(
                    [
                        str(data.world.get("additionalInfo", "")),
                        " ".join(str(rule) for rule in data.world.get("rules", []) if rule),
                    ]
                ),
            }
        )
    for path in data.chapters:
        text = read_text(path)
        docs.append(
            {
                "kind": "章节",
                "title": path.name,
                "location": str(path),
                "text": text,
            }
        )
    return docs


def hybrid_search_project(data: ProjectData, query: str, limit: int = 80) -> list[dict[str, Any]]:
    query = str(query or "").strip()
    if not query:
        return []

    from .vector_search import hybrid_search_vector_store

    vector_results, vector_mode = hybrid_search_vector_store(data.root, query, limit=limit)
    if vector_results:
        if vector_mode == "hybrid":
            return vector_results
        # 向量模型未就绪时，继续用项目资料 BM25 补足章节正文命中
        doc_results = _bm25_search_documents(data, query, limit=limit)
        merged: list[dict[str, Any]] = []
        seen = set()
        for item in vector_results + doc_results:
            key = (item.get("kind"), item.get("title"), item.get("location"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged[:limit]

    return _bm25_search_documents(data, query, limit=limit)


def _bm25_search_documents(data: ProjectData, query: str, limit: int = 80) -> list[dict[str, Any]]:
    docs = collect_search_documents(data)
    query_tokens = tokenize_cn(query)
    if not query_tokens:
        query_tokens = [query]

    indexed = []
    doc_freq: dict[str, int] = {}
    total_len = 0
    for doc in docs:
        tokens = tokenize_cn(doc["text"])
        indexed.append((doc, tokens))
        total_len += len(tokens)
        seen = set(tokens)
        for token in seen:
            doc_freq[token] = doc_freq.get(token, 0) + 1
    avg_len = total_len / max(len(indexed), 1)
    total_docs = max(len(indexed), 1)

    results: list[tuple[float, dict[str, Any]]] = []
    for doc, tokens in indexed:
        if query in doc["text"]:
            bonus = 3.0
        else:
            bonus = 0.0
        score = bm25_score(query_tokens, tokens, avg_len, doc_freq, total_docs) + bonus
        if score <= 0:
            continue
        snippet = doc["text"]
        pos = snippet.find(query)
        if pos >= 0:
            start = max(0, pos - 40)
            snippet = snippet[start : start + 120]
        else:
            snippet = snippet[:120]
        results.append(
            (
                score,
                {
                    "kind": doc["kind"],
                    "title": doc["title"],
                    "location": doc["location"],
                    "path": doc["location"] if doc["kind"] == "章节" else "",
                    "snippet": snippet.replace("\n", " "),
                    "score": round(score, 3),
                },
            )
        )
    results.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in results[:limit]]


def batch_analyze_chapters(data: ProjectData, chapter_numbers: list[int] | None = None) -> dict[str, Any]:
    targets: list[tuple[int, Path]] = []
    for path in data.chapters:
        number = chapter_number_from_name(path)
        if number:
            targets.append((number, path))
    targets.sort(key=lambda item: item[0])
    if chapter_numbers:
        wanted = {int(num) for num in chapter_numbers}
        targets = [item for item in targets if item[0] in wanted]

    analyzed: list[dict[str, Any]] = []
    for number, path in targets:
        text = read_text(path)
        analysis = update_chapter_state(data, number, text)
        analyzed.append(
            {
                "chapter": number,
                "path": str(path),
                "characters": len(analysis.get("characters") or []),
                "relationshipHints": len(analysis.get("relationshipHints") or []),
                "foreshadowHits": sum(1 for fw in analysis.get("foreshadows") or [] if fw.get("hit")),
            }
        )
    return {"count": len(analyzed), "chapters": analyzed}


def self_check_report(data: ProjectData) -> dict[str, Any]:
    paths = assistant_file_paths(data.root)
    state = load_novelbuddy_state(data.root)
    issues: list[str] = []
    warnings: list[str] = []
    ok: list[str] = []

    required = {
        "人物档案": paths["characters"],
        "伏笔库": paths["foreshadows"],
        "大纲": paths["outlines"],
    }
    for label, path in required.items():
        if path.exists():
            ok.append(f"{label} 存在：{path.name}")
        else:
            issues.append(f"缺少 {label}：{path}")

    optional = {
        "组织势力": paths["organizations"],
        "关系图谱": paths["relationships"],
        "世界观": paths["world"],
        "向量库": paths["vectorStore"],
        "精修模板": paths["refineTemplates"],
    }
    for label, path in optional.items():
        if path.exists():
            ok.append(f"{label} 已配置")
        else:
            warnings.append(f"未找到 {label}")

    chapter_keys = [int(key) for key in state.get("chapters", {}) if str(key).isdigit()]
    if chapter_keys:
        ok.append(f"NovelBuddy 已分析 {len(chapter_keys)} 章资料")
    else:
        warnings.append('NovelBuddy 尚未同步章节资料，建议执行"同步章节资料"或"批量分析"')

    orgs = load_organizations(data.root)
    if orgs:
        ok.append(f"组织势力 {len(orgs)} 个")
    rels = as_list(read_json(paths["relationships"], [])) if paths["relationships"].exists() else []
    with_validity = sum(1 for rel in rels if rel.get("validFromChapter") or rel.get("invalidAfterChapter"))
    if with_validity:
        ok.append(f"关系有效期标注 {with_validity} 条")

    vector_path = paths["vectorStore"]
    if vector_path.exists():
        store = read_json(vector_path, [])
        if isinstance(store, list):
            count = len(store)
        elif isinstance(store, dict):
            vectors = store.get("vectors")
            count = len(vectors) if isinstance(vectors, list) else 0
        else:
            count = 0
        if count:
            from .vector_search import embedding_status

            status = embedding_status(data.root)
            if status.get("semanticReady"):
                ok.append(
                    f"蛙趣向量库条目约 {count} 条；NovelBuddy 已启用混合检索（bge-small-zh-v1.5 向量 + BM25 + RRF）"
                )
            else:
                warnings.append(
                    f"蛙趣向量库条目约 {count} 条，但本地 embedding 模型未就绪；当前检索降级为关键词 BM25。"
                    " 请执行：cd E:\\obs\\novelbuddy && uv sync"
                )
        else:
            warnings.append("蛙趣向量库文件存在但为空，建议在 VS Code 蛙趣中重建向量索引")
    else:
        warnings.append("蛙趣向量库不存在，NovelBuddy 将仅使用项目资料 BM25 检索")

    latest_chapter = max(chapter_keys) if chapter_keys else 0

    character_issues = check_character_consistency(data)
    for ci in character_issues:
        issues.append(ci["message"])

    foreshadow_issues = check_foreshadow_health(data, latest_chapter)
    for fi in foreshadow_issues:
        if fi["type"] == "foreshadow_expired":
            issues.append(fi["message"])
        else:
            warnings.append(fi["message"])

    outline_issues = check_outline_deviation(data)
    for oi in outline_issues:
        issues.append(oi["message"])

    status = "需要处理" if issues else ("有提醒" if warnings else "正常")
    lines = ["# NovelBuddy 自检报告", f"结论：{status}", ""]
    if issues:
        lines.append("## 需要处理")
        lines.extend(f"- {item}" for item in issues)
        lines.append("")
    if warnings:
        lines.append("## 提醒")
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")
    if ok:
        lines.append("## 正常")
        lines.extend(f"- {item}" for item in ok)
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "ready": ok,
        "text": "\n".join(lines).strip() + "\n",
        "organizations": len(orgs),
        "relationships": len(rels),
        "characterIssues": character_issues,
        "foreshadowIssues": foreshadow_issues,
        "outlineIssues": outline_issues,
    }
    for label, path in required.items():
        if path.exists():
            ok.append(f"{label} 存在：{path.name}")
        else:
            issues.append(f"缺少 {label}：{path}")

    optional = {
        "组织势力": paths["organizations"],
        "关系图谱": paths["relationships"],
        "世界观": paths["world"],
        "向量库": paths["vectorStore"],
        "精修模板": paths["refineTemplates"],
    }
    for label, path in optional.items():
        if path.exists():
            ok.append(f"{label} 已配置")
        else:
            warnings.append(f"未找到 {label}")

    chapter_keys = [int(key) for key in state.get("chapters", {}) if str(key).isdigit()]
    if chapter_keys:
        ok.append(f"NovelBuddy 已分析 {len(chapter_keys)} 章资料")
    else:
        warnings.append("NovelBuddy 尚未同步章节资料，建议执行“同步章节资料”或“批量分析”")

    orgs = load_organizations(data.root)
    if orgs:
        ok.append(f"组织势力 {len(orgs)} 个")
    rels = as_list(read_json(paths["relationships"], [])) if paths["relationships"].exists() else []
    with_validity = sum(1 for rel in rels if rel.get("validFromChapter") or rel.get("invalidAfterChapter"))
    if with_validity:
        ok.append(f"关系有效期标注 {with_validity} 条")

    vector_path = paths["vectorStore"]
    if vector_path.exists():
        store = read_json(vector_path, [])
        if isinstance(store, list):
            count = len(store)
        elif isinstance(store, dict):
            vectors = store.get("vectors")
            count = len(vectors) if isinstance(vectors, list) else 0
        else:
            count = 0
        if count:
            from .vector_search import embedding_status

            status = embedding_status(data.root)
            if status.get("semanticReady"):
                ok.append(
                    f"蛙趣向量库条目约 {count} 条；NovelBuddy 已启用混合检索（bge-small-zh-v1.5 向量 + BM25 + RRF）"
                )
            else:
                warnings.append(
                    f"蛙趣向量库条目约 {count} 条，但本地 embedding 模型未就绪；当前检索降级为关键词 BM25。"
                    " 请执行：cd E:\\obs\\novelbuddy && uv sync"
                )
        else:
            warnings.append("蛙趣向量库文件存在但为空，建议在 VS Code 蛙趣中重建向量索引")
    else:
        warnings.append("蛙趣向量库不存在，NovelBuddy 将仅使用项目资料 BM25 检索")

    status = "需要处理" if issues else ("有提醒" if warnings else "正常")
    lines = ["# NovelBuddy 自检报告", f"结论：{status}", ""]
    if issues:
        lines.append("## 需要处理")
        lines.extend(f"- {item}" for item in issues)
        lines.append("")
    if warnings:
        lines.append("## 提醒")
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")
    if ok:
        lines.append("## 正常")
        lines.extend(f"- {item}" for item in ok)
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "ready": ok,
        "text": "\n".join(lines).strip() + "\n",
        "organizations": len(orgs),
        "relationships": len(rels),
    }