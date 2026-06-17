from novelbuddy.style_reference import (
    build_style_prompt_section,
    is_style_enabled,
    sample_text_for_analysis,
)


def test_sample_text_for_analysis_keeps_short_text():
    text = "这是一段测试正文。" * 20
    assert sample_text_for_analysis(text) == text


def test_sample_text_for_analysis_samples_long_text():
    text = "甲" * 20000
    sample = sample_text_for_analysis(text, max_chars=9000)
    assert len(sample) <= 9100
    assert "甲" in sample


def test_build_style_prompt_section_when_enabled():
    ref = {
        "enabled": True,
        "source": "upload",
        "novelName": "测试小说",
        "styleGuide": "短句为主，对话干脆。",
        "sampleExcerpt": "他推门进去。",
    }
    section = build_style_prompt_section(ref)
    assert "## 文风引用（必须模仿）" in section
    assert "短句为主" in section
    assert is_style_enabled(ref) is True


def test_build_style_prompt_section_when_disabled():
    ref = {"enabled": False, "styleGuide": "有内容"}
    assert build_style_prompt_section(ref) == ""
    assert is_style_enabled(ref) is False