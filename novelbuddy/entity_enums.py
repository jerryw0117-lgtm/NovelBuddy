from __future__ import annotations

from typing import Any

# value 存英文（兼容 .novel-assistant），label 给用户看中文

SELECT_OPTIONS: dict[str, list[dict[str, str]]] = {
    "character.role": [
        {"value": "protagonist", "label": "主角"},
        {"value": "supporting", "label": "配角"},
        {"value": "antagonist", "label": "反派"},
        {"value": "minor", "label": "次要角色"},
    ],
    "foreshadow.importance": [
        {"value": "high", "label": "高"},
        {"value": "medium", "label": "中"},
        {"value": "low", "label": "低"},
    ],
    "foreshadow.status": [
        {"value": "pending", "label": "待回收"},
        {"value": "resolved", "label": "已回收"},
        {"value": "advanced", "label": "已推进"},
        {"value": "cancelled", "label": "已作废"},
    ],
    "organization.type": [
        {"value": "other", "label": "其他"},
        {"value": "government", "label": "政府/官方"},
        {"value": "criminal", "label": "地下/犯罪"},
        {"value": "military", "label": "军事"},
        {"value": "religious", "label": "宗教"},
        {"value": "corporation", "label": "企业/公司"},
    ],
    "organization.status": [
        {"value": "active", "label": "活跃"},
        {"value": "inactive", "label": "休眠"},
        {"value": "destroyed", "label": "已覆灭"},
        {"value": "unknown", "label": "未知"},
    ],
    "organization.level": [
        {"value": "local", "label": "地方"},
        {"value": "regional", "label": "区域"},
        {"value": "national", "label": "全国"},
        {"value": "international", "label": "国际"},
    ],
    "organization.powerLevel": [
        {"value": "low", "label": "弱"},
        {"value": "medium", "label": "中"},
        {"value": "high", "label": "强"},
    ],
}

# 中文/别名 → 标准英文 value
_ALIASES: dict[str, dict[str, str]] = {
    "character.role": {
        "主角": "protagonist",
        "男主": "protagonist",
        "女主": "protagonist",
        "配角": "supporting",
        "支援角色": "supporting",
        "反派": "antagonist",
        "对手": "antagonist",
        "敌人": "antagonist",
        "次要角色": "minor",
        "龙套": "minor",
        "路人": "minor",
    },
    "foreshadow.importance": {"高": "high", "中": "medium", "低": "low"},
    "foreshadow.status": {
        "待回收": "pending",
        "待处理": "pending",
        "已回收": "resolved",
        "已推进": "advanced",
        "已作废": "cancelled",
    },
    "organization.type": {
        "其他": "other",
        "政府": "government",
        "政府/官方": "government",
        "官方": "government",
        "地下": "criminal",
        "地下/犯罪": "criminal",
        "犯罪": "criminal",
        "军事": "military",
        "宗教": "religious",
        "企业": "corporation",
        "企业/公司": "corporation",
        "公司": "corporation",
    },
    "organization.status": {
        "活跃": "active",
        "休眠": "inactive",
        "已覆灭": "destroyed",
        "未知": "unknown",
    },
    "organization.level": {
        "地方": "local",
        "区域": "regional",
        "全国": "national",
        "国际": "international",
    },
    "organization.powerLevel": {"弱": "low", "中": "medium", "强": "high"},
}

_ENTITY_FIELD_MAP: dict[str, tuple[str, str]] = {
    "character": ("role", "character.role"),
    "foreshadow": ("importance", "foreshadow.importance"),
    "foreshadow_status": ("status", "foreshadow.status"),
    "organization_type": ("type", "organization.type"),
    "organization_status": ("status", "organization.status"),
    "organization_level": ("level", "organization.level"),
    "organization_power": ("powerLevel", "organization.powerLevel"),
}

_ENUM_FIELDS_BY_ENTITY: dict[str, list[tuple[str, str]]] = {
    "character": [("role", "character.role")],
    "foreshadow": [("importance", "foreshadow.importance"), ("status", "foreshadow.status")],
    "organization": [
        ("type", "organization.type"),
        ("status", "organization.status"),
        ("level", "organization.level"),
        ("powerLevel", "organization.powerLevel"),
    ],
}


def enum_options(enum_key: str) -> list[dict[str, str]]:
    return list(SELECT_OPTIONS.get(enum_key, []))


def enum_values(enum_key: str) -> set[str]:
    return {item["value"] for item in enum_options(enum_key)}


def enum_label(enum_key: str, value: str, *, default: str = "") -> str:
    clean = str(value or "").strip()
    if not clean:
        return default or "未标注"
    for item in enum_options(enum_key):
        if item["value"] == clean:
            return item["label"]
    alias = _ALIASES.get(enum_key, {}).get(clean)
    if alias:
        return enum_label(enum_key, alias, default=default)
    return clean


def normalize_enum_value(enum_key: str, raw: Any, *, default: str = "") -> str:
    clean = str(raw or "").strip()
    if not clean:
        return default
    lowered = clean.lower()
    allowed = enum_values(enum_key)
    if lowered in allowed:
        return lowered
    if clean in allowed:
        return clean
    alias = _ALIASES.get(enum_key, {}).get(clean)
    if alias:
        return alias
    alias = _ALIASES.get(enum_key, {}).get(lowered)
    if alias:
        return alias
    for item in enum_options(enum_key):
        if item["label"] == clean:
            return item["value"]
    raise ValueError(f"字段值无效：{clean}。请从下拉列表中选择。")


def normalize_entity_payload(entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for field_key, enum_key in _ENUM_FIELDS_BY_ENTITY.get(entity_type, []):
        if field_key not in normalized:
            continue
        raw = normalized.get(field_key)
        if raw in (None, ""):
            continue
        normalized[field_key] = normalize_enum_value(enum_key, raw)
    return normalized


def decorate_entity_for_ui(entity_type: str, item: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(item)
    if entity_type == "character":
        decorated["roleLabel"] = enum_label("character.role", str(item.get("role", "")), default="未标注")
    elif entity_type == "foreshadow":
        decorated["importanceLabel"] = enum_label("foreshadow.importance", str(item.get("importance", "")), default="未标注")
        decorated["statusLabel"] = enum_label("foreshadow.status", str(item.get("status", "")), default="未标注")
    elif entity_type == "organization":
        decorated["typeLabel"] = enum_label("organization.type", str(item.get("type", "")), default="未标注")
        decorated["statusLabel"] = enum_label("organization.status", str(item.get("status", "")), default="未标注")
        decorated["levelLabel"] = enum_label("organization.level", str(item.get("level", "")), default="未标注")
        decorated["powerLevelLabel"] = enum_label("organization.powerLevel", str(item.get("powerLevel", "")), default="未标注")
    return decorated