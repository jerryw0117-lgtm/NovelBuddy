from __future__ import annotations

import re
from typing import Any, Literal

AITellLanguage = Literal["zh", "en"]

HEDGE_WORDS: dict[AITellLanguage, tuple[str, ...]] = {
    "zh": ("似乎", "可能", "或许", "大概", "某种程度上", "一定程度上", "在某种意义上"),
    "en": ("seems", "seemed", "perhaps", "maybe", "apparently", "in some ways", "to some extent"),
}

TRANSITION_WORDS: dict[AITellLanguage, tuple[str, ...]] = {
    "zh": ("然而", "不过", "与此同时", "另一方面", "尽管如此", "话虽如此", "但值得注意的是"),
    "en": ("however", "meanwhile", "on the other hand", "nevertheless", "even so", "still"),
}


def split_body_paragraphs(content: str) -> list[str]:
    """Split chapter body into paragraphs.

    NovelBuddy chapters usually use single newlines between paragraphs, not blank lines.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    has_blank_line_breaks = bool(re.search(r"\n\s*\n", normalized))
    paragraphs: list[str] = []

    if has_blank_line_breaks:
        buffer: list[str] = []
        for raw_line in normalized.split("\n"):
            line = raw_line.strip()
            if not line:
                if buffer:
                    paragraphs.append("".join(buffer))
                    buffer = []
                continue
            if line.startswith("#") or re.fullmatch(r"第\s*\d+\s*章.*", line):
                if buffer:
                    paragraphs.append("".join(buffer))
                    buffer = []
                continue
            buffer.append(line)
        if buffer:
            paragraphs.append("".join(buffer))
    else:
        for raw_line in normalized.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") or re.fullmatch(r"第\s*\d+\s*章.*", line):
                continue
            paragraphs.append(line)

    return [paragraph for paragraph in paragraphs if len(paragraph) >= 4]


def split_body_sentences(content: str, *, language: AITellLanguage = "zh") -> list[str]:
    if language == "en":
        parts = re.split(r"[.!?\n]", content)
    else:
        parts = re.split(r"[。！？\n]", content)
    return [part.strip() for part in parts if len(part.strip()) > 2]


def analyze_ai_tells(content: str, *, language: AITellLanguage = "zh") -> list[dict[str, Any]]:
    """InkOS-style structural AI-tell detection (rule-based, no LLM)."""
    issues: list[dict[str, Any]] = []
    is_english = language == "en"
    joiner = ", " if is_english else "、"

    paragraphs = split_body_paragraphs(content)

    if len(paragraphs) >= 3:
        lengths = [len(paragraph) for paragraph in paragraphs]
        mean = sum(lengths) / len(lengths)
        if mean > 0:
            variance = sum((length - mean) ** 2 for length in lengths) / len(lengths)
            std_dev = variance**0.5
            cv = std_dev / mean
            if cv < 0.15:
                issues.append(
                    {
                        "severity": "warning",
                        "category": "Paragraph uniformity" if is_english else "段落等长",
                        "description": (
                            f"Paragraph-length coefficient of variation is only {cv:.3f} (threshold <0.15)"
                            if is_english
                            else f"段落长度变异系数仅{cv:.3f}（阈值<0.15），段落长度过于均匀"
                        ),
                        "suggestion": (
                            "Increase paragraph-length contrast: shorter beats for impact, longer blocks for detail"
                            if is_english
                            else "增加段落长度差异：短段落用于节奏加速，长段落用于沉浸描写"
                        ),
                    }
                )

    total_chars = len(content)
    if total_chars > 0:
        hedge_count = 0
        for word in HEDGE_WORDS[language]:
            regex = re.compile(word, re.IGNORECASE if is_english else 0)
            hedge_count += len(regex.findall(content))
        hedge_density = hedge_count / (total_chars / 1000)
        if hedge_density > 3:
            issues.append(
                {
                    "severity": "warning",
                    "category": "Hedge density" if is_english else "套话密度",
                    "description": (
                        f"Hedge-word density is {hedge_density:.1f} per 1k characters (threshold >3)"
                        if is_english
                        else f"套话词密度为{hedge_density:.1f}次/千字（阈值>3），语气过于模糊犹豫"
                    ),
                    "suggestion": (
                        "Replace hedges with firmer narration and concrete detail"
                        if is_english
                        else "用确定性叙述替代模糊表达，用具体细节替代「可能」「似乎」"
                    ),
                }
            )

    transition_counts: dict[str, int] = {}
    for word in TRANSITION_WORDS[language]:
        regex = re.compile(word, re.IGNORECASE if is_english else 0)
        count = len(regex.findall(content))
        if count > 0:
            transition_counts[word.lower() if is_english else word] = count
    repeated_transitions = [(word, count) for word, count in transition_counts.items() if count >= 3]
    if repeated_transitions:
        detail = joiner.join(f'"{word}"×{count}' for word, count in repeated_transitions)
        issues.append(
            {
                "severity": "warning",
                "category": "Formulaic transitions" if is_english else "公式化转折",
                "description": (
                    f"Transition words repeat too often: {detail}"
                    if is_english
                    else f"转折词重复使用：{detail}"
                ),
                "suggestion": (
                    "Let scenes pivot through action, timing, or viewpoint shifts"
                    if is_english
                    else "用情节自然转折替代转折词，或换用动作切入、时间跳跃、视角切换"
                ),
            }
        )

    sentences = split_body_sentences(content, language=language)
    if len(sentences) >= 3:
        consecutive = 1
        max_consecutive = 1
        for index in range(1, len(sentences)):
            if is_english:
                prev_prefix = sentences[index - 1].split()[0].lower() if sentences[index - 1].split() else ""
                curr_prefix = sentences[index].split()[0].lower() if sentences[index].split() else ""
            else:
                prev_prefix = sentences[index - 1][:2]
                curr_prefix = sentences[index][:2]
            if prev_prefix and prev_prefix == curr_prefix:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 1
        if max_consecutive >= 3:
            issues.append(
                {
                    "severity": "info",
                    "category": "List-like structure" if is_english else "列表式结构",
                    "description": (
                        f"Detected {max_consecutive} consecutive sentences with the same opening pattern"
                        if is_english
                        else f"检测到{max_consecutive}句连续以相同开头的句子，呈现列表式结构"
                    ),
                    "suggestion": (
                        "Vary how sentences open: change subject, timing, or action entry"
                        if is_english
                        else "变换句式开头：用不同主语、时间词、动作词开头，打破列表感"
                    ),
                }
            )

    return issues