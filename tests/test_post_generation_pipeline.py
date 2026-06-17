from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from novelbuddy.cli import (
    ProjectData,
    audit_stats,
    needs_auto_fix,
    run_post_generation_pipeline,
)


def test_needs_auto_fix_detects_markdown_and_ai() -> None:
    stats = {
        "markdownHits": [{"label": "Markdown 加粗符号", "count": 1, "lines": [2]}],
        "aiHits": [],
        "structuralTells": [],
        "forbiddenHits": [],
    }
    assert needs_auto_fix(stats)


def test_pipeline_audit_only_when_clean() -> None:
    text = "第1章 测试\n" + ("陈风推开房门，屋里一片漆黑。他压低声音问了一句。" * 20)
    data = ProjectData(Path("."), [], [], [], [], [], [], "", [])
    path = Path("chapter-test.md")
    path.write_text(text, encoding="utf-8")
    try:
        result = run_post_generation_pipeline(
            data,
            1,
            path,
            text,
            auto_fix=False,
        )
        assert result["stages"] == ["audit"]
        assert result["fixed"] is False
        assert "auditText" in result
    finally:
        path.unlink(missing_ok=True)
        audit_path = path.with_name(path.stem + "-审查.md")
        audit_path.unlink(missing_ok=True)


def test_pipeline_runs_fix_stage_when_issues_exist() -> None:
    text = "第1章 测试\n这不是偶然，而是命运。**加粗**"
    stats = audit_stats(ProjectData(Path("."), [], [], [], [], [], [], "", []), text, 1)
    assert needs_auto_fix(stats)


if __name__ == "__main__":
    test_needs_auto_fix_detects_markdown_and_ai()
    test_pipeline_audit_only_when_clean()
    test_pipeline_runs_fix_stage_when_issues_exist()
    print("all tests passed")