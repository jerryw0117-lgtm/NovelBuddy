from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from novelbuddy.ai_tells import analyze_ai_tells
from novelbuddy.cli import (
    ProjectData,
    audit_stats,
    build_context,
    build_foreshadow_pressure_section,
    foreshadow_pressure_meta,
)


def test_detects_uniform_paragraphs() -> None:
    para = "这是一个测试段落的内容，长度大约相同。"
    content = "\n".join([para, para, para, para])
    issues = analyze_ai_tells(content)
    assert any(item["category"] == "段落等长" for item in issues)


def test_detects_formulaic_transitions() -> None:
    content = "第一段。然而事情不简单。\n第二段。然而他没有放弃。\n第三段。然而命运弄人。"
    issues = analyze_ai_tells(content)
    assert any(item["category"] == "公式化转折" for item in issues)


def test_audit_stats_includes_structural_tells() -> None:
    content = "第一段。然而事情不简单。\n第二段。然而他没有放弃。\n第三段。然而命运弄人。"
    stats = audit_stats(ProjectData(Path("."), [], [], [], [], [], [], "", []), content)
    assert "structuralTells" in stats
    assert stats["structuralTells"]


def test_build_context_includes_foreshadow_pressure() -> None:
    data = ProjectData(
        root=Path("."),
        characters=[],
        relationships=[],
        outlines=[],
        summaries=[],
        foreshadows=[
            {
                "id": "F001",
                "keyword": "旧照片",
                "description": "前任住户留下的照片",
                "importance": "high",
                "status": "pending",
                "plantedChapter": 3,
                "invalidAfter": 12,
            }
        ],
        world=[],
        outline_source="",
        chapters=[],
    )
    chapter = 20
    meta = foreshadow_pressure_meta(data.foreshadows[0], chapter)
    assert meta["urgency"] == "已过期"
    assert meta["pressure"] >= 100

    section = build_foreshadow_pressure_section(data, chapter)
    assert "伏笔回收压力" in section
    assert "旧照片" in section

    context = build_context(data, chapter, max_tokens=4500)
    assert "伏笔回收压力" in context
    assert "失效超期" in context


if __name__ == "__main__":
    test_detects_uniform_paragraphs()
    test_detects_formulaic_transitions()
    test_audit_stats_includes_structural_tells()
    test_build_context_includes_foreshadow_pressure()
    print("all tests passed")