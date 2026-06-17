import pytest

from novelbuddy.entity_enums import (
    decorate_entity_for_ui,
    enum_label,
    normalize_entity_payload,
    normalize_enum_value,
)


def test_normalize_enum_value_accepts_english_and_chinese():
    assert normalize_enum_value("character.role", "protagonist") == "protagonist"
    assert normalize_enum_value("character.role", "主角") == "protagonist"
    assert normalize_enum_value("foreshadow.importance", "高") == "high"
    assert normalize_enum_value("organization.type", "政府/官方") == "government"


def test_normalize_enum_value_rejects_invalid_role():
    with pytest.raises(ValueError, match="字段值无效"):
        normalize_enum_value("character.role", "hero")


def test_normalize_entity_payload_normalizes_aliases():
    payload = normalize_entity_payload("character", {"name": "李默", "role": "配角"})
    assert payload["role"] == "supporting"


def test_decorate_entity_for_ui_adds_chinese_labels():
    character = decorate_entity_for_ui("character", {"name": "李默", "role": "protagonist"})
    foreshadow = decorate_entity_for_ui(
        "foreshadow",
        {"keyword": "钥匙", "importance": "high", "status": "pending"},
    )
    organization = decorate_entity_for_ui(
        "organization",
        {"name": "市局", "type": "government", "status": "active", "level": "local", "powerLevel": "high"},
    )
    assert character["roleLabel"] == "主角"
    assert foreshadow["importanceLabel"] == "高"
    assert foreshadow["statusLabel"] == "待回收"
    assert organization["typeLabel"] == "政府/官方"
    assert organization["statusLabel"] == "活跃"
    assert organization["levelLabel"] == "地方"
    assert organization["powerLevelLabel"] == "强"


def test_enum_label_falls_back_to_raw_unknown_value():
    assert enum_label("character.role", "custom-role") == "custom-role"