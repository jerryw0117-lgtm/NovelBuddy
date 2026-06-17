from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .cli import call_openai_compatible, truncate

DEFAULT_STYLE_REFERENCE: dict[str, Any] = {
    "enabled": False,
    "source": "",
    "novelName": "",
    "styleGuide": "",
    "sampleExcerpt": "",
    "updatedAt": "",
}


def style_reference_path(root: Path) -> Path:
    return root / ".novelbuddy" / "style-reference.json"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load_style_reference(root: Path) -> dict[str, Any]:
    path = style_reference_path(root)
    if not path.exists():
        return dict(DEFAULT_STYLE_REFERENCE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_STYLE_REFERENCE)
    if not isinstance(data, dict):
        return dict(DEFAULT_STYLE_REFERENCE)
    merged = dict(DEFAULT_STYLE_REFERENCE)
    merged.update(data)
    return merged


def save_style_reference(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    current = load_style_reference(root)
    for key in DEFAULT_STYLE_REFERENCE:
        if key in payload:
            current[key] = payload[key]
    current["updatedAt"] = now_iso()
    path = style_reference_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def clear_style_reference(root: Path) -> dict[str, Any]:
    path = style_reference_path(root)
    if path.exists():
        path.unlink()
    return dict(DEFAULT_STYLE_REFERENCE)


def is_style_enabled(ref: dict[str, Any] | None) -> bool:
    if not ref:
        return False
    return bool(ref.get("enabled")) and bool(str(ref.get("styleGuide") or "").strip())


def sample_text_for_analysis(text: str, max_chars: int = 12000) -> str:
    clean = str(text or "").replace("\r\n", "\n").strip()
    if not clean:
        return ""
    if len(clean) <= max_chars:
        return clean
    chunk = max_chars // 3
    middle_start = max(0, len(clean) // 2 - chunk // 2)
    parts = [
        clean[:chunk],
        clean[middle_start : middle_start + chunk],
        clean[-chunk:],
    ]
    return "\n\n---\n\n".join(part.strip() for part in parts if part.strip())


def build_style_prompt_section(ref: dict[str, Any]) -> str:
    if not is_style_enabled(ref):
        return ""
    novel = str(ref.get("novelName") or "").strip()
    source = str(ref.get("source") or "").strip()
    source_label = {
        "upload": "上传样本",
        "search": "联网搜索",
        "manual": "手动编辑",
    }.get(source, "文风引用")
    title = f"《{novel}》" if novel else source_label
    guide = str(ref.get("styleGuide") or "").strip()
    excerpt = str(ref.get("sampleExcerpt") or "").strip()
    lines = [
        "## 文风引用（必须模仿）",
        f"参考作品：{title}",
        "写作时优先模仿以下文风特征，但不要抄袭剧情、人物和专有设定。",
        guide,
    ]
    if excerpt:
        lines.extend(["", "### 参考语感片段", excerpt])
    return "\n".join(lines).strip() + "\n"


def append_style_reference(prompt: str, root: Path) -> str:
    ref = load_style_reference(root)
    section = build_style_prompt_section(ref)
    if not section:
        return prompt
    return f"{prompt.rstrip()}\n\n{section}"


def build_extract_style_prompt(sample: str, novel_name: str = "") -> str:
    title = f"《{novel_name}》" if novel_name else "该作品"
    return (
        "你是资深文学编辑。请阅读下面的小说正文样本，提炼可执行的「文风指南」，供另一位作者模仿写作。\n"
        "要求：\n"
        "1. 只分析语言技法，不要复述剧情。\n"
        "2. 用中文输出，分条列出，覆盖：叙事视角、句式节奏、段落密度、环境/动作/对话比例、用词气质、情绪渲染、悬念推进方式。\n"
        "3. 明确写出 3-5 条「应模仿」和 3-5 条「应避免」。\n"
        "4. 最后附 1 段 120-180 字的「模仿示范」（原创场景，只展示语感，不要抄样本剧情）。\n"
        "5. 不要输出 Markdown 标题符号以外的多余解释。\n\n"
        f"作品：{title}\n\n"
        "## 正文样本\n"
        f"{sample}"
    )


def build_search_style_prompt(novel_name: str, web_context: str) -> str:
    context_block = web_context.strip() or "（联网检索未返回有效资料，请结合你对该作品的常识谨慎总结。）"
    return (
        "你是资深文学编辑。用户想模仿某部小说的文风来创作新书。\n"
        "请根据下面的作品名称和联网检索摘要，提炼可执行的「文风指南」。\n"
        "要求：\n"
        "1. 用中文输出，聚焦语言技法，不要写剧情梗概。\n"
        "2. 分条列出：叙事视角、句式节奏、描写重心、对话风格、情绪氛围、类型化特征。\n"
        "3. 写出 3-5 条「应模仿」和 3-5 条「应避免」。\n"
        "4. 若检索信息不足，请明确标注「推测」，不要编造具体情节。\n"
        "5. 最后附 1 段 120-180 字的模仿示范段落。\n\n"
        f"作品名称：{novel_name}\n\n"
        "## 联网检索摘要\n"
        f"{truncate(context_block, 6000)}"
    )


def fetch_web_context_for_novel(novel_name: str) -> str:
    query = f"{novel_name} 小说 文风 叙事风格 写作特点"
    url = f"https://s.jina.ai/{urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NovelBuddy/0.1.0",
            "Accept": "text/plain",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            text = response.read().decode("utf-8", errors="ignore").strip()
            return truncate(text, 8000)
    except Exception:
        return ""


def call_style_llm(prompt: str, config: dict[str, str], temperature: float = 0.35) -> str:
    try:
        return str(call_openai_compatible(prompt, config, temperature)).strip()
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc


def extract_style_from_text(
    text: str,
    config: dict[str, str],
    *,
    novel_name: str = "",
    temperature: float = 0.35,
) -> dict[str, Any]:
    sample = sample_text_for_analysis(text)
    if len(re.sub(r"\s+", "", sample)) < 200:
        raise ValueError("样本文本太短，请至少提供约 200 字的正文片段。")
    guide = call_style_llm(build_extract_style_prompt(sample, novel_name), config, temperature)
    if not guide:
        raise ValueError("AI 没有返回文风指南。")
    return {
        "enabled": True,
        "source": "upload",
        "novelName": str(novel_name or "").strip(),
        "styleGuide": guide,
        "sampleExcerpt": truncate(sample, 500),
    }


def search_novel_style(
    novel_name: str,
    config: dict[str, str],
    *,
    temperature: float = 0.35,
) -> dict[str, Any]:
    clean_name = str(novel_name or "").strip()
    if not clean_name:
        raise ValueError("请填写小说名称。")
    web_context = fetch_web_context_for_novel(clean_name)
    guide = call_style_llm(build_search_style_prompt(clean_name, web_context), config, temperature)
    if not guide:
        raise ValueError("AI 没有返回文风指南。")
    return {
        "enabled": True,
        "source": "search",
        "novelName": clean_name,
        "styleGuide": guide,
        "sampleExcerpt": truncate(web_context, 500) if web_context else "",
        "webContextLength": len(web_context),
    }