from pathlib import Path

from novelbuddy.cli import REWRITE_ANTI_AI_RULES, build_rewrite_prompt


class DummyData:
    root = Path(".")
    outline_source = "test"
    outlines = []
    world = {}
    characters = []
    relationships = []
    foreshadows = []
    organizations = []
    chapters = []
    summaries = []


def test_build_rewrite_prompt_includes_anti_ai_rules_and_original():
    original = "第22章 测试\n李默刚站稳，肺里呛进一口凉气。"
    prompt = build_rewrite_prompt(DummyData(), 22, original, rewrite_note="少用比喻")
    assert "## 重写任务" in prompt
    assert REWRITE_ANTI_AI_RULES.splitlines()[0] in prompt
    assert original in prompt
    assert "少用比喻" in prompt
    assert "整齐、克制、不快不慢" in prompt