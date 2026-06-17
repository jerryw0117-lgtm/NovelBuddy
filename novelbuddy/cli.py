from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai_tells import analyze_ai_tells
from .entity_enums import enum_label


AI_SIMPLE_PATTERNS = [
    "这说明",
    "这证明",
    "意味着",
    "显然",
    "某种意义上",
    "仿佛.*?一般",
    "内心深处",
    "他意识到",
    "她意识到",
    "让她明白",
    "让他明白",
]

# 「不是 A 而是 B」只抓解释腔；物证/感官描写（如「背面却不是满文，而是一道刻痕」）放行。
NEGATION_CONTRAST_RE = re.compile(r"不是.{1,28}?(而是|，是)")

PHYSICAL_EXEMPT_MARKERS = (
    "背面",
    "正面",
    "表面",
    "边缘",
    "刻着",
    "刻痕",
    "划痕",
    "纹路",
    "符号",
    "颜料",
    "颜色",
    "渗透",
    "涂鸦",
    "满文",
    "汉字",
    "文字",
    "图案",
    "草图",
    "碎布",
    "衣服",
    "石块",
    "砖头",
    "泥土",
    "石头",
    "裂缝",
    "墙",
    "门",
    "镜",
    "纸",
    "布",
    "钱",
    "铜",
    "灰",
    "粉",
    "脚步",
    "声音",
    "尖啸",
    "震动",
    "错觉",
    "温热",
    "温度",
    "通道口",
    "石头",
    "物质",
    "排列",
    "规整",
    "随意",
    "下陷",
    "来电",
    "提醒",
    "直播",
    "断面",
    "碎骨",
    "自然死亡",
    "尖啸",
    "裂缝",
    "空",
    "摸着",
    "触感",
    "落脚",
)

ABSTRACT_FLAG_MARKERS = (
    "偶然",
    "巧合",
    "意外",
    "命运",
    "注定",
    "意义",
    "真相",
    "证明",
    "说明",
    "意识到",
    "明白",
    "敬畏",
    "害怕",
    "软弱",
    "幻觉",
    "梦境",
    "假象",
    "不是在问",
    "不是在说",
    "并不是",
    "不只是",
    "至少不",
    "普通的",
    "简单",
    "选活",
    "选死",
    "守规矩",
    "拍摄素材",
    "废弃建筑",
    "镇魂庙",
    "表面上",
    "看起来",
)

DEFAULT_FORBIDDEN_WORDS = ["他妈"]

FORESHADOW_SYNONYM_MAP: dict[str, list[str]] = {
    "镜中倒影异常": ["镜中倒影", "镜中影像", "镜子里的影子", "倒影异常", "镜像", "影子在动", "倒影在动", "镜中人"],
    "符纸发黑": ["符纸变黑", "符纸焦化", "符纸边缘发黑", "符纸失效", "符纸颜色变暗", "符纸开始变黑", "符纸发暗"],
    "后颈勒痕": ["后颈有勒痕", "脖子上有痕迹", "颈部勒痕", "脖子被勒", "脖子上有红印", "后颈的勒痕"],
    "符纸变脆": ["符纸变脆", "符纸干燥", "符纸碎裂", "符纸失去弹性", "符纸发脆"],
    "灰色雾气": ["灰色雾气", "雾气", "灰雾", "黑雾", "雾气弥漫", "雾气从镜中"],
    "皮肤角质层": ["皮肤碎片", "皮肤角质", "皮屑", "皮肤组织", "皮肤碎片"],
    "手册空白页": ["空白页", "手册空白", "空白的书页", "没有字的页", "空白书页"],
    "书屋后物品": ["书屋后面", "书屋后", "书店后面", "书屋有东西"],
    "胶带翘起": ["胶带翘起", "胶带脱落", "胶带粘不住", "胶带松动", "胶带再次翘起"],
    "镜面刮擦": ["刮擦声", "镜子上刮", "镜面划痕", "刮东西的声音", "镜面上刮"],
    "守护者书屋": ["守护者书屋", "书屋", "名片上的地址", "周先生的书屋"],
    "选择迟早": ["选择", "迟早会来", "必须选择", "你的选择"],
    "手册冰冷": ["手册冰冷", "手册很冷", "手册冰凉", "手册温度", "手册比之前更冷"],
    "镜子不可遮盖": ["不能盖住镜子", "不能砸碎镜子", "镜子不能遮", "镜子不能砸", "遮盖镜子"],
    "楼下惨叫": ["惨叫", "楼下惨叫", "有人尖叫", "凄厉惨叫", "惨叫声"],
    "黄纸符": ["黄纸符", "符纸", "黄色符纸", "衣柜里的符", "衣柜门缝里塞着黄纸符"],
}

MARKDOWN_PATTERNS = [
    (r"\*\*.+?\*\*", "Markdown 加粗符号"),
    (r"(?m)^\s*[-*+]\s+", "Markdown 列表符号"),
    (r"(?m)^\s*#{1,6}\s+", "Markdown 标题符号"),
    (r"(?m)^\s*---+\s*$", "Markdown 分隔线"),
]

# 正文里直接写「想起第3章」会破坏沉浸感，多由上下文包里的章节标注诱发。
_CHAPTER_NUM = r"(?:\d+|[一二三四五六七八九十百千两]+)"
META_CHAPTER_REF_RE = re.compile(
    rf"(?:想起|回想|回顾|回到|如同|就像|类似)(?:第\s*{_CHAPTER_NUM}\s*章|前三章|前五章|前几章)"
    rf"|第\s*{_CHAPTER_NUM}\s*章\s*[———\-]"
)


@dataclass
class ProjectData:
    root: Path
    characters: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    outlines: list[dict[str, Any]]
    summaries: list[dict[str, Any]]
    foreshadows: list[dict[str, Any]]
    world: list[dict[str, Any]] | dict[str, Any] | str | None
    chapters: list[Path]
    outline_source: Path | None = None
    volumes: list[dict[str, Any]] | None = None
    outline_md_source: Path | None = None


def find_outline_md(root: Path) -> Path | None:
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() == ".md" and "大纲" in p.name:
            return p
    return None


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def best_json_list_source(paths: list[Path]) -> tuple[list[dict[str, Any]], Path | None]:
    best_items: list[dict[str, Any]] = []
    best_path: Path | None = None
    for path in paths:
        if not path.exists():
            continue
        items = as_list(read_json(path, []))
        if len(items) > len(best_items):
            best_items = items
            best_path = path
    return best_items, best_path


def load_project(root_arg: str, *, require_outline_md: bool = False) -> ProjectData:
    root = Path(root_arg).resolve()
    if not root.exists():
        raise SystemExit(f"项目目录不存在: {root}")

    outline_md = find_outline_md(root)
    if require_outline_md and not outline_md:
        raise ValueError(
            f"项目目录中未找到名称包含「大纲」的 .md 文件。\n"
            f"请在 {root} 下放置一个如「都市-大纲.md」的文件后重试。"
        )

    na = root / ".novel-assistant"
    ai = root / ".ai-novel" / "data"

    characters_path = first_existing(na / "characters.json", ai / "characters.json")
    relationships_path = first_existing(na / "characterRelationships.json", ai / "characterRelationships.json")
    outlines, outline_source = best_json_list_source([
        na / "outlines.json",
        na / "data" / "outlines.json",
        ai / "outlines.json",
    ])
    summaries_path = first_existing(na / "summaries.json")
    foreshadows_path = first_existing(na / "foreshadows.json")
    volumes_path = first_existing(na / "volumes.json")
    world_path = first_existing(na / "world-setting.json", na / "world-setting.md", root / "世界观设定.md")

    world: list[dict[str, Any]] | dict[str, Any] | str | None = None
    if world_path:
        world = read_json(world_path, None) if world_path.suffix.lower() == ".json" else read_text(world_path)

    chapters = sorted(
        [
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix.lower() in {".md", ".txt"}
            and "章" in p.name
            and "审查" not in p.stem
            and ".bak-" not in p.stem
            and not p.name.startswith("novelbuddy_")
        ],
        key=chapter_sort_key,
    )

    return ProjectData(
        root=root,
        characters=as_list(read_json(characters_path, [])) if characters_path else [],
        relationships=as_list(read_json(relationships_path, [])) if relationships_path else [],
        outlines=outlines,
        summaries=as_list(read_json(summaries_path, [])) if summaries_path else [],
        foreshadows=as_list(read_json(foreshadows_path, [])) if foreshadows_path else [],
        world=world,
        chapters=chapters,
        outline_source=outline_source,
        volumes=as_list(read_json(volumes_path, [])) if volumes_path else None,
        outline_md_source=outline_md,
    )


def as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def chapter_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"第\s*0*(\d+)\s*章", path.name)
    if match:
        return (int(match.group(1)), path.name)
    return (999999, path.name)


def chapter_number_from_name(path: Path) -> int | None:
    match = re.search(r"第\s*0*(\d+)\s*章", path.name)
    return int(match.group(1)) if match else None


def find_outline(data: ProjectData, chapter: int) -> dict[str, Any] | None:
    for item in data.outlines:
        if int(item.get("chapterNumber") or -1) == chapter:
            return item
    return None


def find_volume(data: ProjectData, chapter: int) -> dict[str, Any] | None:
    if not data.volumes:
        return None
    for vol in data.volumes:
        start = int(vol.get("startChapter") or 0)
        end = int(vol.get("endChapter") or 999999)
        if start <= chapter <= end:
            return vol
    return None


def get_volume_for_chapter(data: ProjectData, chapter: int) -> str:
    vol = find_volume(data, chapter)
    if vol:
        vol_num = vol.get("volumeNumber", "?")
        vol_title = vol.get("title", "")
        return f"第{vol_num}卷 {vol_title}".strip()
    return ""


def save_outline(data: ProjectData, chapter: int, title: str, content: str) -> tuple[Path, Path | None, dict[str, Any]]:
    source = data.outline_source or data.root / ".novel-assistant" / "data" / "outlines.json"
    outlines = as_list(read_json(source, []))
    backup_path: Path | None = None
    if source.exists():
        backup_dir = data.root / ".novelbuddy" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"{source.stem}-{stamp}{source.suffix}"
        backup_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    existing = None
    for item in outlines:
        if int(item.get("chapterNumber") or 0) == chapter:
            existing = item
            break

    if existing is None:
        existing = {
            "id": f"NB-OUT-{chapter:04d}",
            "chapterNumber": chapter,
            "type": "chapter",
            "orderIndex": chapter,
            "volumeNumber": 1,
        }
        outlines.append(existing)

    existing["chapterNumber"] = chapter
    existing["title"] = title.strip() or f"第{chapter}章"
    existing["content"] = content.strip()
    existing.setdefault("type", "chapter")
    existing.setdefault("orderIndex", chapter)
    existing["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    outlines.sort(key=lambda item: int(item.get("chapterNumber") or item.get("orderIndex") or 999999))
    write_json(source, outlines)
    return source, backup_path, existing


def generate_outline_data(data: ProjectData, config: dict[str, str]) -> dict[str, Any]:
    if not data.outline_md_source:
        return {"error": "未找到大纲 .md 文件"}
    parsed = parse_outline_with_ai(data.outline_md_source, config)
    na = data.root / ".novel-assistant"
    na.mkdir(parents=True, exist_ok=True)

    char_id_map: dict[str, str] = {}
    characters = []
    for i, c in enumerate(parsed.get("characters", []), 1):
        cid = f"OC-{i:04d}"
        char_id_map[c.get("name", "")] = cid
        characters.append({
            "id": cid,
            "name": c.get("name", ""),
            "role": c.get("role", "minor"),
            "description": c.get("description", ""),
            "personality": c.get("personality", ""),
            "background": c.get("background", ""),
        })

    relationships = []
    for r in parsed.get("relationships", []):
        name1 = r.get("characterName1", "")
        name2 = r.get("characterName2", "")
        cid1 = char_id_map.get(name1, "")
        cid2 = char_id_map.get(name2, "")
        if not cid1 or not cid2:
            continue
        relationships.append({
            "characterId1": cid1,
            "characterId2": cid2,
            "relationshipLabel": r.get("relationshipLabel", ""),
            "relationshipType": "",
        })

    organizations = []
    for o in parsed.get("organizations", []):
        oid = f"ORG-{len(organizations)+1:04d}"
        organizations.append({
            "id": oid,
            "name": o.get("name", ""),
            "type": o.get("type", "other"),
            "description": o.get("description", ""),
            "status": o.get("status", "unknown"),
            "level": o.get("level", "local"),
            "powerLevel": o.get("powerLevel", "medium"),
        })

    worldview = parsed.get("worldview", {})

    write_json(na / "characters.json", characters)
    write_json(na / "characterRelationships.json", relationships)
    write_json(na / "organizations.json", organizations)
    if worldview:
        write_json(na / "world-setting.json", worldview)

    return {
        "characters": len(characters),
        "relationships": len(relationships),
        "organizations": len(organizations),
        "worldview": bool(worldview),
    }


def find_summary(data: ProjectData, chapter: int) -> dict[str, Any] | None:
    for item in data.summaries:
        if int(item.get("chapterNumber") or -1) == chapter:
            return item
    return None


def chapter_bridge_text(data: ProjectData, chapter: int, tail_chars: int = 520) -> str:
    summary = find_summary(data, chapter)
    lines: list[str] = []
    if summary:
        title = summary.get("chapterTitle", "")
        lines.append(f"第{chapter}章《{title}》：{summary.get('summary', '')}")
        events = summary.get("keyEvents") or []
        if events:
            lines.append("关键事件：")
            lines.extend(f"- {event}" for event in events[:5])
        return "\n".join(line for line in lines if str(line).strip())

    state = load_novelbuddy_state(data.root)
    local_summary = state.get("localSummaries", {}).get(str(chapter), {})
    if local_summary:
        title = local_summary.get("chapterTitle", "")
        summary_text = str(local_summary.get("summary", "")).strip()
        if summary_text:
            lines.append(f"第{chapter}章《{title}》：{summary_text}")
        events = local_summary.get("keyEvents") or []
        if events:
            lines.append("关键事件：")
            lines.extend(f"- {event}" for event in events[:5])

    chapter_state = state.get("chapters", {}).get(str(chapter), {})
    events = chapter_state.get("events") or []
    characters = chapter_state.get("characters") or []
    foreshadows = chapter_state.get("foreshadows") or []
    if events and not local_summary:
        lines.append("本地事件线：")
        for event in events[:6]:
            summary_text = str(event.get("summary", "")).strip()
            if summary_text:
                lines.append(f"- {summary_text}")
    if characters:
        names = "、".join(str(char.get("name", "")).strip() for char in characters[:8] if char.get("name"))
        if names:
            lines.append(f"出场人物：{names}")
    hit_foreshadows = [fw for fw in foreshadows if fw.get("hit")]
    if hit_foreshadows:
        lines.append("已触碰伏笔：" + "、".join(str(fw.get("keyword", "")).strip() for fw in hit_foreshadows[:6] if fw.get("keyword")))

    chapter_file = find_chapter_file(data, chapter)
    if chapter_file and chapter_file.exists():
        text = normalize_chapter_text(read_text(chapter_file)).strip()
        if text:
            lines.append("上一章结尾原文：")
            lines.append(truncate(text[-tail_chars:], tail_chars))

    return "\n".join(line for line in lines if str(line).strip())


def find_chapter_file(data: ProjectData, chapter: int) -> Path | None:
    for path in data.chapters:
        if chapter_number_from_name(path) == chapter:
            return path
    return None


def novelbuddy_dir(root: Path) -> Path:
    path = root / ".novelbuddy"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_novelbuddy_state(root: Path) -> dict[str, Any]:
    path = root / ".novelbuddy" / "state.json"
    fallback: dict[str, Any] = {"chapters": {}, "localSummaries": {}}
    value = read_json(path, fallback)
    if not isinstance(value, dict):
        return fallback
    if not isinstance(value.get("chapters"), dict):
        value["chapters"] = {}
    if not isinstance(value.get("localSummaries"), dict):
        value["localSummaries"] = {}
    return value


def save_novelbuddy_state(root: Path, state: dict[str, Any]) -> Path:
    path = novelbuddy_dir(root) / "state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def character_display_name(data: ProjectData, character_id: str) -> str:
    for char in data.characters:
        if str(char.get("id", "")) == character_id:
            return str(char.get("name", "") or character_id)
    return character_id


def relationship_display(data: ProjectData, rel: dict[str, Any]) -> dict[str, Any]:
    left_id = str(rel.get("characterId1", ""))
    right_id = str(rel.get("characterId2", ""))
    return {
        "id": rel.get("id", ""),
        "left": character_display_name(data, left_id),
        "right": character_display_name(data, right_id),
        "leftId": left_id,
        "rightId": right_id,
        "label": rel.get("relationshipLabel") or rel.get("relationshipType") or "关系",
        "strength": rel.get("strength", ""),
        "status": rel.get("status", ""),
        "notes": rel.get("notes", ""),
        "validFromChapter": rel.get("validFromChapter", ""),
        "invalidAfterChapter": rel.get("invalidAfterChapter") or rel.get("invalidAfter", ""),
    }


def character_profile_index(data: ProjectData) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for char in data.characters:
        name = str(char.get("name", "")).strip()
        if not name:
            continue
        profiles[name] = {
            "id": str(char.get("id", "")),
            "name": name,
            "role": str(char.get("role", "") or "未标注"),
            "description": str(char.get("description", "") or ""),
            "personality": str(char.get("personality", "") or ""),
            "background": str(char.get("background", "") or ""),
        }
    return profiles


def character_role_group(role: str) -> str:
    clean = str(role or "").strip().lower()
    if any(token in clean for token in ("主角", "protagonist", "男主", "女主")):
        return "protagonist"
    if any(token in clean for token in ("反派", "对立", "antagonist", "对手", "敌人")):
        return "antagonist"
    if any(token in clean for token in ("配角", "支援", "support", "盟友", "同伴", "朋友")):
        return "support"
    return "neutral"


def collect_character_chapters(chapters: dict[str, Any]) -> dict[str, set[int]]:
    appearances: dict[str, set[int]] = {}
    for key, chapter_data in chapters.items():
        if not str(key).isdigit():
            continue
        chapter_num = int(key)
        for char in chapter_data.get("characters") or []:
            name = str(char.get("name", "")).strip()
            if name:
                appearances.setdefault(name, set()).add(chapter_num)
        for hint in chapter_data.get("relationshipHints") or []:
            for side in ("left", "right"):
                name = str(hint.get(side, "")).strip()
                if name:
                    appearances.setdefault(name, set()).add(chapter_num)
    return appearances


def build_relationship_graph(
    data: ProjectData,
    chapter: int = 0,
    *,
    scope: str = "window",
    window_size: int = 8,
) -> dict[str, Any]:
    state = load_novelbuddy_state(data.root)
    chapters = state.get("chapters", {})
    chapter_numbers = sorted(int(key) for key in chapters.keys() if str(key).isdigit())
    latest = chapter_numbers[-1] if chapter_numbers else 0
    target = chapter or latest or 1
    use_full_scope = scope == "full"
    window_start = 1 if use_full_scope else max(1, target - window_size)

    profiles = character_profile_index(data)
    appearances = collect_character_chapters(chapters)

    names: dict[str, str] = {}
    node_ids: dict[str, str] = {}

    def add_name(name: str) -> None:
        clean = str(name or "").strip()
        if not clean:
            return
        if clean not in node_ids:
            node_ids[clean] = f"P{len(node_ids) + 1}"
            names[node_ids[clean]] = clean

    for char in data.characters:
        add_name(str(char.get("name", "")))

    formal_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for rel in data.relationships:
        shown = relationship_display(data, rel)
        left = str(shown.get("left") or "").strip()
        right = str(shown.get("right") or "").strip()
        if not left or not right:
            continue
        add_name(left)
        add_name(right)
        key = tuple(sorted((left, right)))
        formal_edges[key] = shown

    hint_edges: dict[tuple[str, str], set[int]] = {}
    for key in chapter_numbers:
        if key < window_start or key > target:
            continue
        ch = chapters.get(str(key), {})
        for hint in ch.get("relationshipHints") or []:
            left = str(hint.get("left") or "").strip()
            right = str(hint.get("right") or "").strip()
            if not left or not right or left == right:
                continue
            add_name(left)
            add_name(right)
            edge_key = tuple(sorted((left, right)))
            hint_edges.setdefault(edge_key, set()).add(key)

    edge_names: set[str] = set()
    for left, right in formal_edges:
        edge_names.update([left, right])
    for left, right in hint_edges:
        edge_names.update([left, right])

    display_names: set[str] = set(edge_names)
    for char in data.characters:
        name = str(char.get("name", "")).strip()
        if name:
            add_name(name)
            display_names.add(name)
    for key in chapter_numbers:
        if key < window_start or key > target:
            continue
        ch = chapters.get(str(key), {})
        for char in ch.get("characters") or []:
            name = str(char.get("name", "")).strip()
            if name:
                add_name(name)
                display_names.add(name)

    connection_counts: dict[str, int] = {name: 0 for name in display_names if name}
    graph_edges: list[dict[str, Any]] = []
    mermaid = ["```mermaid", "graph LR"]
    for name in sorted(display_names):
        if name and name in node_ids:
            mermaid.append(f'  {node_ids[name]}["{name}"]')

    for (left, right), rel in sorted(formal_edges.items()):
        if left not in display_names or right not in display_names:
            continue
        label = str(rel.get("label") or "关系").replace('"', "'")
        strength = str(rel.get("strength") or "").strip()
        weight = 4
        if strength in {"强", "高", "紧密", "核心"}:
            weight = 6
        elif strength in {"弱", "低", "疏远"}:
            weight = 2
        mermaid.append(f'  {node_ids[left]} -->|"{label}"| {node_ids[right]}')
        graph_edges.append(
            {
                "id": f"E{len(graph_edges) + 1}",
                "from": node_ids[left],
                "to": node_ids[right],
                "left": left,
                "right": right,
                "label": label,
                "kind": "formal",
                "weight": weight,
                "strength": strength,
                "status": str(rel.get("status") or ""),
                "notes": str(rel.get("notes") or ""),
                "chapters": [],
            }
        )
        connection_counts[left] = connection_counts.get(left, 0) + 1
        connection_counts[right] = connection_counts.get(right, 0) + 1

    for (left, right), chapter_set in sorted(hint_edges.items()):
        if (left, right) in formal_edges or left not in display_names or right not in display_names:
            continue
        chapter_list = sorted(chapter_set)
        chapter_label = "、".join(f"第{num}章" for num in chapter_list[-4:])
        weight = min(5, 1 + len(chapter_list))
        mermaid.append(f'  {node_ids[left]} -. "{chapter_label}同场" .-> {node_ids[right]}')
        graph_edges.append(
            {
                "id": f"E{len(graph_edges) + 1}",
                "from": node_ids[left],
                "to": node_ids[right],
                "left": left,
                "right": right,
                "label": f"同场 {len(chapter_list)}",
                "kind": "hint",
                "weight": weight,
                "strength": "",
                "status": "",
                "notes": "",
                "chapters": chapter_list,
            }
        )
        connection_counts[left] = connection_counts.get(left, 0) + 1
        connection_counts[right] = connection_counts.get(right, 0) + 1

    mermaid.append("```")
    graph_nodes = []
    for name in sorted(display_names):
        if not name or name not in node_ids:
            continue
        profile = profiles.get(name, {})
        role = profile.get("role", "未标注")
        role_label = enum_label("character.role", str(role), default="未标注")
        chapter_list = sorted(
            num for num in appearances.get(name, set()) if window_start <= num <= target
        )
        graph_nodes.append(
            {
                "id": node_ids[name],
                "name": name,
                "role": role,
                "roleLabel": role_label,
                "roleGroup": character_role_group(role),
                "description": profile.get("description", ""),
                "personality": profile.get("personality", ""),
                "background": profile.get("background", ""),
                "connectionCount": connection_counts.get(name, 0),
                "chapters": chapter_list,
                "lastChapter": chapter_list[-1] if chapter_list else 0,
            }
        )

    scope_label = "全书" if use_full_scope else f"第{window_start}章至第{target}章"
    lines = [f"# 第{target}章关系图谱", f"统计范围：{scope_label}", ""]
    lines.extend(mermaid)
    lines.append("")
    lines.append("## 正式关系")
    if formal_edges:
        for (left, right), rel in sorted(formal_edges.items()):
            details = "；".join(str(rel.get(key, "")) for key in ("label", "status", "notes") if rel.get(key))
            lines.append(f"- {left} ↔ {right}：{details or '关系未标注'}")
    else:
        lines.append("暂无正式关系文件记录。")
    lines.append("")
    lines.append("## 最近同章线索")
    recent_hints = [
        (left, right, sorted(chapter_set))
        for (left, right), chapter_set in hint_edges.items()
        if (left, right) not in formal_edges
    ]
    if recent_hints:
        for left, right, chapter_set in sorted(recent_hints, key=lambda item: (-len(item[2]), item[0], item[1]))[:40]:
            lines.append(f"- {left} ↔ {right}：同章出现 {len(chapter_set)} 次｜" + "、".join(f"第{num}章" for num in chapter_set))
    else:
        lines.append("最近章节没有新的同章关系线索。")
    lines.append("")
    lines.append("## 使用建议")
    lines.append("- 正式关系适合写进人物档案；同章线索只代表近期互动频率。")
    lines.append("- 高频同章但无正式关系的人物，建议补一句关系状态或冲突方向。")
    lines.append("- 生成新章节前，优先检查主角、支援者、对立者之间的行动目的是否清楚。")

    return {
        "chapter": target,
        "windowStart": window_start,
        "scope": "full" if use_full_scope else "window",
        "nodeCount": len(graph_nodes),
        "formalEdgeCount": len(formal_edges),
        "hintEdgeCount": len(hint_edges),
        "nodes": graph_nodes,
        "edges": graph_edges,
        "text": "\n".join(lines).strip() + "\n",
    }


def split_sentences(text: str) -> list[str]:
    body_lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or re.fullmatch(r"第\s*\d+\s*章.*", stripped):
            continue
        body_lines.append(stripped)
    clean = re.sub(r"\s+", "", "\n".join(body_lines))
    return [s.strip() for s in re.split(r"(?<=[。！？!?])", clean) if s.strip()]


def extract_timeline_events(
    text: str,
    chapter: int,
    mentioned: list[dict[str, Any]],
    limit: int = 12,
) -> list[dict[str, Any]]:
    character_names = [str(c.get("name", "")).strip() for c in mentioned if str(c.get("name", "")).strip()]
    time_words = [
        "凌晨", "清晨", "上午", "中午", "下午", "晚上", "夜里", "半夜", "天亮", "昨天", "前天",
        "后来", "这时", "此刻", "几秒", "几分钟", "点", "分",
    ]
    action_words = [
        "推开", "走", "站", "看", "盯", "问", "说", "递", "拿", "放下", "打开", "关上",
        "回头", "离开", "出现", "消失", "浮现", "发现", "确认", "提醒", "警告", "审查",
        "拜访", "触发", "失效", "发黑", "变淡", "沉默",
    ]
    abnormal_words = [
        "手册", "镜", "符纸", "黑影", "鬼", "煞", "规则", "异常", "危机", "钥匙", "书屋",
        "倒影", "探查", "守护者",
    ]
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentence in split_sentences(text):
        if sentence.startswith("#"):
            continue
        names = [name for name in character_names if name in sentence]
        has_time = any(word in sentence for word in time_words)
        has_action = any(word in sentence for word in action_words)
        has_abnormal = any(word in sentence for word in abnormal_words)
        score = len(names) * 3 + int(has_time) * 2 + int(has_abnormal) * 2 + int(has_action)
        if score < 3:
            continue
        summary = truncate(sentence.strip("“”\"'’‘。！？!?"), 110)
        if summary in seen:
            continue
        seen.add(summary)
        events.append(
            {
                "chapter": chapter,
                "summary": summary,
                "characters": names,
                "tags": [
                    tag
                    for tag, ok in [
                        ("时间", has_time),
                        ("行动", has_action),
                        ("异常", has_abnormal),
                    ]
                    if ok
                ],
            }
        )
        if len(events) >= limit:
            break
    return events


LOCATION_HINTS = [
    "房间", "客厅", "楼道", "门口", "屋外", "屋里", "镜子前", "楼下", "楼上",
    "书屋", "庙宇", "墓地", "医院", "铁门", "水泥路", "出租屋", "402", "太平间",
]
TIME_HINTS = [
    "凌晨", "清晨", "早上", "上午", "中午", "下午", "傍晚", "晚上", "夜里",
    "半夜", "午夜", "天亮", "黄昏", "深夜",
]


def backup_assistant_file(path: Path, root: Path) -> Path | None:
    if not path.exists():
        return None
    backup_dir = novelbuddy_dir(root) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{path.stem}-assistant-{stamp}{path.suffix}"
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def chapter_title_from_path(path: Path | None, chapter: int) -> str:
    if not path:
        return f"第{chapter}章"
    title = re.sub(r"^第\s*0*\d+\s*章[-：: ]*", "", path.stem).strip()
    return title or f"第{chapter}章"


def extract_description_anchors(description: str, keyword: str = "") -> list[str]:
    anchors: list[str] = []
    for chunk in re.findall(r"[\u4e00-\u9fff]{4,}", description):
        if keyword and (chunk == keyword or chunk in keyword or keyword in chunk):
            continue
        anchors.append(chunk)
    return list(dict.fromkeys(anchors))[:8]


def foreshadow_recovery_level(text: str, fw: dict[str, Any]) -> str:
    if fw.get("status") == "resolved":
        return "none"
    keyword = str(fw.get("keyword", "")).strip()
    description = str(fw.get("description", "")).strip()
    anchors = extract_description_anchors(description, keyword)
    expanded_keywords = [keyword] + FORESHADOW_SYNONYM_MAP.get(keyword, [])
    keyword_hit = any(kw and kw in text for kw in expanded_keywords)
    anchor_hit = any(anchor in text for anchor in anchors)
    if not keyword_hit and not anchor_hit:
        return "none"
    importance = str(fw.get("importance", "medium"))
    if keyword_hit:
        if importance == "high":
            return "resolved" if anchor_hit else "advanced"
        return "resolved"
    return "advanced"


def apply_foreshadow_sync(root: Path, chapter: int, text: str) -> dict[str, Any]:
    path = root / ".novel-assistant" / "foreshadows.json"
    if not path.exists():
        return {"resolved": [], "advanced": [], "path": "", "backup": ""}
    foreshadows = as_list(read_json(path, []))
    backup = backup_assistant_file(path, root)
    now = datetime.now().isoformat(timespec="seconds") + "Z"
    resolved: list[dict[str, Any]] = []
    advanced: list[dict[str, Any]] = []
    changed = False
    for fw in foreshadows:
        planted = int(fw.get("plantedChapter") or 0)
        if planted > chapter or fw.get("status") == "resolved":
            continue
        level = foreshadow_recovery_level(text, fw)
        if level == "none":
            continue
        changed = True
        if level == "advanced":
            fw["lastContextChapter"] = chapter
            fw["updatedAt"] = now
            advanced.append(
                {
                    "id": fw.get("id", ""),
                    "keyword": fw.get("keyword", ""),
                    "chapter": chapter,
                }
            )
            continue
        fw["status"] = "resolved"
        fw["resolvedChapter"] = chapter
        fw["lastContextChapter"] = chapter
        fw["updatedAt"] = now
        resolved.append(
            {
                "id": fw.get("id", ""),
                "keyword": fw.get("keyword", ""),
                "chapter": chapter,
            }
        )
    if changed:
        write_json(path, foreshadows)
    return {
        "resolved": resolved,
        "advanced": advanced,
        "path": str(path),
        "backup": str(backup) if backup else "",
    }


def infer_time_from_text(text: str) -> str:
    for word in TIME_HINTS:
        if word in text:
            return word
    return ""


def infer_location_from_text(text: str, char_name: str) -> str:
    for sentence in split_sentences(text):
        if char_name not in sentence:
            continue
        for loc in LOCATION_HINTS:
            if loc in sentence:
                return loc
    return ""


def upsert_summary_file(
    root: Path,
    chapter: int,
    analysis: dict[str, Any],
    text: str,
    title: str,
) -> Path | None:
    path = root / ".novel-assistant" / "summaries.json"
    if not path.parent.exists():
        return None
    summaries = as_list(read_json(path, [])) if path.exists() else []
    backup_assistant_file(path, root) if path.exists() else None
    entry = local_summary_entry(chapter, text, analysis, title)
    entry.update(
        {
            "id": f"SUM_NB_{chapter:04d}",
            "wordCount": len(re.findall(r"[\u4e00-\u9fff]", text)),
            "keyCharacters": [char.get("name", "") for char in analysis.get("characters", []) if char.get("name")],
            "keyEvents": [event.get("summary", "") for event in analysis.get("events", [])[:6] if event.get("summary")],
            "emotionalTone": "待标注",
            "paceLevel": "fast",
            "createdAt": datetime.now().isoformat(timespec="seconds") + "Z",
        }
    )
    replaced = False
    for index, item in enumerate(summaries):
        if int(item.get("chapterNumber") or 0) == chapter:
            entry["id"] = item.get("id", entry["id"])
            summaries[index] = entry
            replaced = True
            break
    if not replaced:
        summaries.append(entry)
    summaries.sort(key=lambda item: int(item.get("chapterNumber") or 999999))
    write_json(path, summaries)
    return path


def merge_characters_by_name(characters_out: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并同名角色，保留最新的状态和非temp的ID。支持别名匹配。"""
    name_map: dict[str, dict[str, Any]] = {}
    name_aliases: dict[str, str] = {}
    result: list[dict[str, Any]] = []

    def resolve_name(char: dict[str, Any]) -> str:
        name = str(char.get("characterName", "")).strip()
        if name in name_aliases:
            return name_aliases[name]
        aliases = char.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [a.strip() for a in aliases.split(",") if a.strip()]
        for alias in aliases:
            alias = str(alias).strip()
            if alias and alias in name_map:
                name_aliases[name] = alias
                return alias
        return name

    for char in characters_out:
        canonical = resolve_name(char)
        if not canonical:
            result.append(char)
            continue
        if canonical in name_map:
            existing = name_map[canonical]
            existing_id = str(existing.get("characterId", ""))
            new_id = str(char.get("characterId", ""))
            if existing_id.startswith("temp_") and not new_id.startswith("temp_"):
                existing["characterId"] = new_id
            existing_events = list(existing.get("recentEvents", []))
            new_events = list(char.get("recentEvents", []))
            seen = set(new_events)
            merged = new_events + [e for e in existing_events if e not in seen]
            existing["recentEvents"] = merged[:3]
            if char.get("currentStatus") and char["currentStatus"] != "本章新出场":
                existing["currentStatus"] = char["currentStatus"]
            if char.get("location") and char["location"] != "未知":
                existing["location"] = char["location"]
            if char.get("emotionalState") and char["emotionalState"] not in ("待更新", "未知"):
                existing["emotionalState"] = char["emotionalState"]
        else:
            name_map[canonical] = char
            result.append(char)
    return result


def sync_story_state_file(
    root: Path,
    data: ProjectData,
    chapter: int,
    analysis: dict[str, Any],
    text: str,
    foreshadow_sync: dict[str, Any],
) -> Path | None:
    path = root / ".novel-assistant" / "current-story-state.json"
    if not path.parent.exists():
        return None
    state = read_json(path, {}) if path.exists() else {}
    if not isinstance(state, dict):
        state = {}
    backup_assistant_file(path, root) if path.exists() else None

    characters_out: list[dict[str, Any]] = list(state.get("characters", []))
    time_hint = infer_time_from_text(text) or f"第{chapter}章"

    for char_entry in analysis.get("characters", []):
        char_id = str(char_entry.get("id", "")).strip()
        char_name = str(char_entry.get("name", "")).strip()
        if not char_name:
            continue
        events = [
            str(event.get("summary", "")).strip()
            for event in analysis.get("events", [])
            if char_name in event.get("characters", []) and event.get("summary")
        ]
        location = infer_location_from_text(text, char_name)
        updated = False
        for index, existing in enumerate(characters_out):
            same_id = char_id and existing.get("characterId") == char_id
            same_name = existing.get("characterName") == char_name
            if not same_id and not same_name:
                continue
            characters_out[index] = {
                **existing,
                "characterId": char_id or existing.get("characterId", ""),
                "characterName": char_name,
                "currentStatus": events[0] if events else existing.get("currentStatus", "本章出场"),
                "location": location or existing.get("location", "未知"),
                "lastKnownTime": time_hint,
                "recentEvents": events[:3] or existing.get("recentEvents", []),
                "psychologyNote": truncate(events[0], 100) if events else existing.get("psychologyNote", ""),
            }
            updated = True
            break
        if not updated:
            characters_out.append(
                {
                    "characterId": char_id or f"temp_{char_name}_{int(datetime.now().timestamp() * 1000)}",
                    "characterName": char_name,
                    "currentStatus": events[0] if events else "本章新出场",
                    "location": location or "未知",
                    "lastKnownTime": time_hint,
                    "emotionalState": "待更新",
                    "titles": [],
                    "recentEvents": events[:3],
                    "psychologyNote": truncate(events[0], 100) if events else "",
                }
            )

    foreshadows_path = root / ".novel-assistant" / "foreshadows.json"
    all_foreshadows = as_list(read_json(foreshadows_path, [])) if foreshadows_path.exists() else data.foreshadows
    pending_count = sum(1 for item in all_foreshadows if item.get("status") != "resolved")
    plot = dict(state.get("plotProgress", {}))
    resolved_keywords = [
        str(item.get("keyword", "")).strip()
        for item in foreshadow_sync.get("resolved", [])
        if str(item.get("keyword", "")).strip()
    ]
    existing_resolved = list(plot.get("foreshadowsResolved", []))
    for keyword in resolved_keywords:
        if keyword not in existing_resolved:
            existing_resolved.append(keyword)
    plot["foreshadowsResolved"] = existing_resolved
    plot["pendingForeshadowCount"] = pending_count

    characters_out = merge_characters_by_name(characters_out)

    state.update(
        {
            "lastChapter": max(int(state.get("lastChapter") or 0), chapter),
            "lastUpdated": datetime.now().isoformat(timespec="seconds") + "Z",
            "characters": characters_out,
            "plotProgress": plot,
        }
    )
    write_json(path, state)
    return path


def sync_novel_assistant(
    data: ProjectData,
    chapter: int,
    text: str,
    analysis: dict[str, Any],
    title: str | None = None,
) -> dict[str, Any]:
    chapter_file = find_chapter_file(data, chapter)
    chapter_title = title or chapter_title_from_path(chapter_file, chapter)
    foreshadow_sync = apply_foreshadow_sync(data.root, chapter, text)
    summary_path = upsert_summary_file(data.root, chapter, analysis, text, chapter_title)
    story_path = sync_story_state_file(data.root, data, chapter, analysis, text, foreshadow_sync)
    return {
        "foreshadows": foreshadow_sync,
        "summaryPath": str(summary_path) if summary_path else "",
        "storyStatePath": str(story_path) if story_path else "",
        "resolvedCount": len(foreshadow_sync.get("resolved", [])),
        "advancedCount": len(foreshadow_sync.get("advanced", [])),
    }


def dedupe_foreshadow_sync_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in items:
        key = str(item.get("id") or item.get("keyword") or "")
        if not key:
            continue
        existing = latest.get(key)
        if not existing or int(item.get("chapter") or 0) >= int(existing.get("chapter") or 0):
            latest[key] = item
    return list(latest.values())


def format_assistant_sync_summary(sync: dict[str, Any] | None) -> str:
    if not sync:
        return ""
    lines = ["## 插件资料同步"]
    resolved = dedupe_foreshadow_sync_items(sync.get("foreshadows", {}).get("resolved", []))
    advanced = dedupe_foreshadow_sync_items(sync.get("foreshadows", {}).get("advanced", []))
    if resolved:
        lines.append(f"- 伏笔已回收：{len(resolved)} 条")
        lines.extend(
            f"  - {item.get('id', '')} {item.get('keyword', '')}（第{item.get('chapter', '')}章）"
            for item in resolved[:12]
        )
    if advanced:
        lines.append(f"- 伏笔已推进：{len(advanced)} 条")
        lines.extend(
            f"  - {item.get('id', '')} {item.get('keyword', '')}（第{item.get('chapter', '')}章，未结案）"
            for item in advanced[:12]
        )
    if sync.get("storyStatePath"):
        lines.append(f"- 故事状态：{sync['storyStatePath']}")
    if sync.get("summaryPath"):
        lines.append(f"- 章节摘要：{sync['summaryPath']}")
    backup = sync.get("foreshadows", {}).get("backup", "")
    if backup:
        lines.append(f"- 备份：{backup}")
    if len(lines) == 1:
        lines.append("- 本章未触发新的伏笔回收或人物状态更新。")
    return "\n".join(lines)


def analyze_chapter_assets(data: ProjectData, text: str, chapter: int) -> dict[str, Any]:
    mentioned: list[dict[str, Any]] = []
    mentioned_ids: set[str] = set()
    for char in data.characters:
        names = [str(char.get("name", "")).strip()]
        names.extend(str(alias).strip() for alias in char.get("aliases", []) if str(alias).strip())
        hits = [name for name in names if name and name in text]
        if hits:
            char_id = str(char.get("id", ""))
            mentioned_ids.add(char_id)
            mentioned.append(
                {
                    "id": char_id,
                    "name": char.get("name", ""),
                    "role": char.get("role", ""),
                    "hits": hits,
                }
            )

    relation_hits: list[dict[str, Any]] = []
    for rel in data.relationships:
        left_id = str(rel.get("characterId1", ""))
        right_id = str(rel.get("characterId2", ""))
        if left_id in mentioned_ids and right_id in mentioned_ids:
            relation_hits.append(relationship_display(data, rel))

    relationship_hints: list[dict[str, Any]] = []
    for idx, left in enumerate(mentioned):
        for right in mentioned[idx + 1 :]:
            relationship_hints.append(
                {
                    "left": left.get("name", ""),
                    "right": right.get("name", ""),
                    "label": "同章出现",
                    "chapter": chapter,
                }
            )

    selected = select_foreshadows(data, chapter, limit=999, include_expired=False)
    foreshadow_hits: list[dict[str, Any]] = []
    for fw in selected:
        keyword = str(fw.get("keyword", "")).strip()
        hit = bool(keyword and keyword in text)
        foreshadow_hits.append(
            {
                "id": fw.get("id", ""),
                "keyword": keyword,
                "description": fw.get("description", ""),
                "importance": fw.get("importance", ""),
                "sourceStatus": fw.get("status", ""),
                "plantedChapter": fw.get("plantedChapter", ""),
                "invalidAfter": fw.get("invalidAfter") or fw.get("invalidAfterChapter", ""),
                "hit": hit,
                "novelbuddyStatus": "命中" if hit else "未命中",
            }
        )

    return {
        "chapter": chapter,
        "characters": mentioned,
        "relationships": relation_hits,
        "relationshipHints": relationship_hints,
        "foreshadows": foreshadow_hits,
        "events": extract_timeline_events(text, chapter, mentioned),
    }


def update_chapter_state(data: ProjectData, chapter: int, text: str) -> dict[str, Any]:
    analysis = analyze_chapter_assets(data, text, chapter)
    state = load_novelbuddy_state(data.root)
    state["chapters"][str(chapter)] = analysis
    state["localSummaries"][str(chapter)] = local_summary_entry(chapter, text, analysis)
    save_novelbuddy_state(data.root, state)
    analysis["assistantSync"] = sync_novel_assistant(data, chapter, text, analysis)
    return analysis


def local_summary_entry(chapter: int, text: str, analysis: dict[str, Any], title: str = "") -> dict[str, Any]:
    events = [str(event.get("summary", "")).strip() for event in analysis.get("events", []) if event.get("summary")]
    cleaned = normalize_chapter_text(text).strip()
    summary = "；".join(events[:4])
    if not summary and cleaned:
        summary = truncate(cleaned[:360], 360)
    return {
        "chapterNumber": chapter,
        "chapterTitle": title or f"第{chapter}章",
        "summary": summary,
        "keyEvents": events[:8],
        "characters": [char.get("name", "") for char in analysis.get("characters", []) if char.get("name")],
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def sync_project_state(data: ProjectData) -> dict[str, Any]:
    state = load_novelbuddy_state(data.root)
    chapters = state.setdefault("chapters", {})
    summaries = state.setdefault("localSummaries", {})
    synced: list[int] = []
    all_resolved: list[dict[str, Any]] = []
    all_advanced: list[dict[str, Any]] = []
    latest_chapter = 0
    latest_analysis: dict[str, Any] | None = None
    latest_text = ""
    for path in data.chapters:
        chapter = chapter_number_from_name(path)
        if not chapter:
            continue
        text = read_text(path)
        analysis = analyze_chapter_assets(data, text, chapter)
        analysis["sourcePath"] = str(path)
        analysis["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        chapters[str(chapter)] = analysis
        title = chapter_title_from_path(path, chapter)
        entry = local_summary_entry(chapter, text, analysis, title)
        entry["sourcePath"] = str(path)
        summaries[str(chapter)] = entry
        synced.append(chapter)

        foreshadow_sync = apply_foreshadow_sync(data.root, chapter, text)
        all_resolved.extend(foreshadow_sync.get("resolved", []))
        all_advanced.extend(foreshadow_sync.get("advanced", []))
        foreshadows_path = data.root / ".novel-assistant" / "foreshadows.json"
        if foreshadows_path.exists():
            data.foreshadows = as_list(read_json(foreshadows_path, []))
        upsert_summary_file(data.root, chapter, analysis, text, title)

        if chapter >= latest_chapter:
            latest_chapter = chapter
            latest_analysis = analysis
            latest_text = text

    if latest_analysis and latest_chapter:
        sync_story_state_file(
            data.root,
            data,
            latest_chapter,
            latest_analysis,
            latest_text,
            {"resolved": all_resolved, "advanced": all_advanced},
        )

    state_path = save_novelbuddy_state(data.root, state)
    assistant_sync = {
        "foreshadows": {
            "resolved": all_resolved,
            "advanced": all_advanced,
            "path": str(data.root / ".novel-assistant" / "foreshadows.json"),
            "backup": "",
        },
        "storyStatePath": str(data.root / ".novel-assistant" / "current-story-state.json"),
        "summaryPath": str(data.root / ".novel-assistant" / "summaries.json"),
        "resolvedCount": len(all_resolved),
        "advancedCount": len(all_advanced),
    }
    return {
        "statePath": str(state_path),
        "count": len(synced),
        "chapters": sorted(synced),
        "summaryCount": len(summaries),
        "assistantSync": assistant_sync,
        "assistantSyncText": format_assistant_sync_summary(assistant_sync),
    }


def safe_filename_part(text: str, fallback: str = "未命名") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def chapter_output_path(data: ProjectData, chapter: int, title: str | None = None) -> Path:
    chapters_dir = data.root / "AAA" / "chapters"
    if not chapters_dir.exists():
        chapters_dir = data.root / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    final_title = safe_filename_part(title or f"第{chapter}章")
    base = chapters_dir / f"第{chapter}章-{final_title}.md"
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = chapters_dir / f"第{chapter}章-{final_title}-{idx}.md"
        if not candidate.exists():
            return candidate
        idx += 1


def truncate(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def normalize_chapter_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line.strip()).strip() + "\n"


def estimate_cn_tokens(text: str) -> int:
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other = max(0, len(text) - ascii_words - cjk_chars)
    return int(cjk_chars * 0.7 + ascii_words * 1.2 + other * 0.25)


def select_characters(data: ProjectData, target_outline: str, limit: int = 8) -> list[dict[str, Any]]:
    scored: list[tuple[int, dict[str, Any]]] = []
    for char in data.characters:
        name = str(char.get("name", ""))
        score = 0
        if name and name in target_outline:
            score += 10
        role = str(char.get("role", ""))
        if role == "protagonist":
            score += 8
        elif role == "supporting":
            score += 4
        if char.get("description"):
            score += 1
        scored.append((score, char))
    return [c for _, c in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]


FORESHADOW_HALF_LIFE = {
    "high": 10,
    "medium": 12,
    "low": 15,
}


def foreshadow_urgency(item: dict[str, Any], chapter: int) -> str:
    planted = int(item.get("plantedChapter") or 0)
    invalid_after = int(item.get("invalidAfter") or item.get("invalidAfterChapter") or 999999)
    if invalid_after < chapter:
        return "已过期"
    if invalid_after - chapter <= 5:
        return "临近失效"
    if planted and chapter - planted >= 8:
        return "拖延较久"
    return "本章关注"


def foreshadow_pressure_meta(item: dict[str, Any], chapter: int) -> dict[str, Any]:
    planted = int(item.get("plantedChapter") or 0)
    invalid_after = int(item.get("invalidAfter") or item.get("invalidAfterChapter") or 999999)
    importance = str(item.get("importance") or "medium")
    half_life = FORESHADOW_HALF_LIFE.get(importance, 12)
    distance = max(0, chapter - planted) if planted else 0
    deadline_left = invalid_after - chapter if invalid_after < 999999 else None
    overdue_chapters = max(0, chapter - invalid_after) if invalid_after < chapter else 0

    pressure = 0
    tags: list[str] = []
    urgency = foreshadow_urgency(item, chapter)
    if urgency == "已过期":
        pressure += 100 + overdue_chapters * 4
        tags.append("已过期")
    elif urgency == "临近失效":
        left = max(0, invalid_after - chapter)
        pressure += 60 + (5 - left) * 6
        tags.append("临近失效")
    if distance > half_life:
        pressure += 30 + min(distance - half_life, 20) * 2
        if "拖延较久" not in tags:
            tags.append("拖延较久")
    elif urgency == "拖延较久":
        pressure += 25 + min(distance - 8, 12) * 2
        tags.append("拖延较久")

    marker_parts: list[str] = []
    if urgency == "已过期" and overdue_chapters:
        marker_parts.append(f"失效超期 (超={overdue_chapters}章)")
    elif urgency == "已过期":
        marker_parts.append("失效超期")
    if distance > half_life:
        marker_parts.append(f"拖延 (距={distance}/半衰={half_life})")
    elif urgency == "拖延较久":
        marker_parts.append(f"拖延 (距={distance}章)")
    if "临近失效" in tags and deadline_left is not None:
        marker_parts.append(f"临近失效 (剩={deadline_left}章)")

    return {
        "pressure": pressure,
        "urgency": urgency,
        "distance": distance,
        "halfLife": half_life,
        "deadlineLeft": deadline_left,
        "overdueChapters": overdue_chapters,
        "tags": tags or [urgency],
        "marker": "；".join(marker_parts) if marker_parts else urgency,
    }


def select_pressured_foreshadows(
    data: ProjectData,
    chapter: int,
    *,
    limit: int = 6,
) -> list[tuple[int, dict[str, Any], dict[str, Any]]]:
    pressured: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for item in data.foreshadows:
        planted = int(item.get("plantedChapter") or 0)
        if planted > chapter or item.get("status") == "resolved":
            continue
        meta = foreshadow_pressure_meta(item, chapter)
        if meta["urgency"] in {"已过期", "临近失效", "拖延较久"} or int(meta["pressure"]) >= 25:
            pressured.append((int(meta["pressure"]), item, meta))
    return sorted(pressured, key=lambda entry: entry[0], reverse=True)[:limit]


def build_foreshadow_pressure_section(data: ProjectData, chapter: int, limit: int = 6) -> str:
    pressured = select_pressured_foreshadows(data, chapter, limit=limit)
    if not pressured:
        return ""
    lines = [f"## 伏笔回收压力（信息截至第 {max(chapter - 1, 0)} 章）"]
    for _, fw, meta in pressured:
        planted = fw.get("plantedChapter", "")
        invalid_after = fw.get("invalidAfter") or fw.get("invalidAfterChapter") or ""
        deadline = f"，有效至第{invalid_after}章" if invalid_after else ""
        strategy = "补救解释、呈现后果或转成新悬念"
        if meta["urgency"] == "临近失效":
            strategy = "必须给出新信息、代价或选择"
        elif meta["urgency"] == "拖延较久":
            strategy = "推进、回收或明确延期，避免只重复关键词"
        lines.append(
            f"- {fw.get('id', '')} [{fw.get('importance', '')}｜压力={meta['pressure']}] "
            f"{fw.get('keyword', '')}：第{planted}章埋入{deadline}。"
            f"{meta['marker']}。{truncate(str(fw.get('description', '')), 100)}"
        )
        lines.append(f"  处理：{strategy}")
    lines.append(
        "压力原则：已过期伏笔不能假装按时回收；临近失效必须出新信息；拖延较久的伏笔本章至少要有一次可追踪推进。"
    )
    return "\n".join(lines)


STRUCTURAL_QUALITY_WARNINGS = frozenset({"章节偏短", "章节偏长", "缺少明显对话"})


def normalize_world_for_ui(world: list[dict[str, Any]] | dict[str, Any] | str | None) -> dict[str, Any]:
    if isinstance(world, dict):
        return world
    if isinstance(world, str) and world.strip():
        return {"title": "世界观设定", "additionalInfo": world.strip()}
    return {}


def select_foreshadows(
    data: ProjectData,
    chapter: int,
    limit: int = 8,
    *,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    pending = []
    for item in data.foreshadows:
        planted = int(item.get("plantedChapter") or 0)
        invalid_after = int(item.get("invalidAfter") or item.get("invalidAfterChapter") or 999999)
        if planted <= chapter and item.get("status") != "resolved":
            if not include_expired and invalid_after < chapter:
                continue
            importance = {"high": 3, "medium": 2, "low": 1}.get(str(item.get("importance")), 0)
            age = max(0, chapter - planted)
            deadline_pressure = 0
            if invalid_after < chapter:
                deadline_pressure = 80
            elif invalid_after - chapter <= 5:
                deadline_pressure = 60
            elif age >= 8:
                deadline_pressure = 25
            pending.append((importance * 100 + deadline_pressure + age, item))
    return [f for _, f in sorted(pending, key=lambda x: x[0], reverse=True)[:limit]]


def world_to_text(world: list[dict[str, Any]] | dict[str, Any] | str | None) -> str:
    if world is None:
        return ""
    if isinstance(world, str):
        return world
    return json.dumps(world, ensure_ascii=False, indent=2)


def suggest_chapter_temperature(outline_text: str, fallback: float = 0.6) -> float:
    text = str(outline_text or "")
    if any(token in text for token in ("战斗", "追逐", "爆炸", "对抗", "高潮", "厮杀")):
        return 0.85
    if any(token in text for token in ("对话", "谈判", "交谈", "质问", "谈话")):
        return 0.75
    if any(token in text for token in ("描写", "环境", "氛围", "铺垫", "回忆")):
        return 0.62
    return fallback


def build_foreshadow_plan_section(data: ProjectData, chapter: int, limit: int = 8) -> str:
    selected = select_foreshadows(data, chapter, limit=limit, include_expired=True)
    if not selected:
        return ""
    lines = [f"## 本章伏笔回收提示（信息截至第 {max(chapter - 1, 0)} 章）"]
    for fw in selected:
        planted = fw.get("plantedChapter", "")
        invalid_after = fw.get("invalidAfter") or fw.get("invalidAfterChapter") or ""
        deadline = f"，有效至第{invalid_after}章" if invalid_after else ""
        lines.append(
            f"- {fw.get('id', '')} [{fw.get('importance', '')}｜{foreshadow_urgency(fw, chapter)}] "
            f"{fw.get('keyword', '')}：第{planted}章埋入{deadline}。"
            f"{truncate(str(fw.get('description', '')), 100)}"
        )
    lines.append(
        "处理原则：自然相关的伏笔要推进或回收；临近失效的伏笔必须给出新信息；不要为回收而硬塞无关剧情。"
    )
    return "\n".join(lines)


def run_writing_preflight(
    data: ProjectData,
    chapter: int,
    *,
    words: int = 3000,
    api_key: str = "",
    api_base: str = "",
    model: str = "",
    writing_rules: str = "",
    require_api: bool = True,
    base_temperature: float = 0.6,
) -> dict[str, Any]:
    outline = find_outline(data, chapter)
    outline_text = str(outline.get("content", "")).strip() if outline else ""
    existing = find_chapter_file(data, chapter)
    previous = chapter_bridge_text(data, chapter - 1) if chapter > 1 else ""
    blocker: list[str] = []
    warning: list[str] = []
    ok: list[str] = []
    auto_sync_recommended = False

    if outline_text:
        title = str(outline.get("title", "") or f"第{chapter}章")
        ok.append(f"本章大纲存在：{title}")
        if len(outline_text) < 80:
            warning.append(f"本章大纲较短（约 {len(outline_text)} 字），建议扩展到 300 字以上再生成。")
    else:
        blocker.append("缺少本章大纲。请先点「编辑本章大纲」补齐。")

    if chapter <= 1:
        ok.append("首章无需上章衔接。")
    elif previous:
        ok.append("上章衔接可用。")
    else:
        warning.append("没有找到上章摘要、事件线或正文尾段，续写可能断层。")

    prev_file = find_chapter_file(data, chapter - 1) if chapter > 1 else None
    if chapter > 1 and not prev_file:
        blocker.append(f"缺少第{chapter - 1}章正文文件，章节连续性不完整。")

    chapter_numbers = sorted(
        num for num in (chapter_number_from_name(path) for path in data.chapters) if num
    )
    if chapter > 1 and chapter_numbers and (chapter - 1) not in chapter_numbers:
        blocker.append(f"章节编号不连续：第{chapter - 1}章文件缺失。")

    if existing:
        warning.append(f"第{chapter}章正文已存在：{existing.name}。再次生成会覆盖同名输出文件。")
    else:
        ok.append("本章正文尚未生成。")

    if require_api:
        if api_key:
            ok.append("API Key 已配置。")
        else:
            blocker.append("缺少 API Key。请先点「API 设置」填写。")
        if api_base and model:
            ok.append(f"模型接口：{api_base} / {model}")
        else:
            blocker.append("API Base 或模型为空。")

    if data.foreshadows:
        ok.append(f"伏笔库可用：{len(data.foreshadows)} 条。")
        urgent = []
        for fw in select_foreshadows(data, chapter, limit=20, include_expired=True):
            urgency = foreshadow_urgency(fw, chapter)
            if urgency in {"已过期", "临近失效", "拖延较久"}:
                urgent.append(f"{fw.get('keyword', '')}（{urgency}）")
        if urgent:
            warning.append("本章需优先关注的伏笔：" + "、".join(urgent[:6]))
    else:
        warning.append("没有伏笔库，生成时无法主动检查伏笔回收。")

    if writing_rules.strip():
        ok.append(f"自定义写作规则已启用：约 {len(writing_rules.strip())} 字。")
    else:
        warning.append("没有设置自定义写作规则，将只使用默认写作约束。")

    from .style_reference import is_style_enabled, load_style_reference

    style_ref = load_style_reference(data.root)
    if is_style_enabled(style_ref):
        label = str(style_ref.get("novelName") or "自定义样本").strip()
        ok.append(f"文风引用已启用：{label}（约 {len(str(style_ref.get('styleGuide') or '').strip())} 字）。")
    else:
        warning.append("未启用文风引用。可在「文风引用」上传样本或联网搜索目标作品文风。")

    nb_state = load_novelbuddy_state(data.root)
    synced = {int(key) for key in nb_state.get("chapters", {}) if str(key).isdigit()}
    file_chapters = {num for num in chapter_numbers}
    stale = sorted(file_chapters - synced)
    if stale:
        preview = "、".join(f"第{num}章" for num in stale[:6])
        if len(stale) > 6:
            preview += " 等"
        warning.append(f"本地章节资料未同步：{preview}。建议先点「同步章节资料」。")
        if max(stale) >= chapter - 1:
            auto_sync_recommended = True

    if prev_file and prev_file.exists():
        prev_stats = audit_stats(data, read_text(prev_file), chapter - 1)
        prev_issues = []
        if prev_stats.get("aiHits"):
            prev_issues.append(f"AI句式 {len(prev_stats['aiHits'])} 处")
        if prev_stats.get("markdownHits"):
            prev_issues.append(f"格式残留 {len(prev_stats['markdownHits'])} 处")
        if prev_stats.get("forbiddenHits"):
            prev_issues.append("含禁用词")
        if prev_issues:
            warning.append(f"上一章存在质量问题：{'；'.join(prev_issues)}。建议先在「问题总览」修复后再写新章。")

    temperature = suggest_chapter_temperature(outline_text, base_temperature)
    ok.append(f"建议生成温度：{temperature}（基准 {base_temperature}，按大纲类型调整）")

    can_proceed = not blocker
    status = "可以生成" if can_proceed else "暂不建议生成"
    lines = [f"# 第{chapter}章联动写作检查", f"结论：{status}", ""]
    if blocker:
        lines.append("## 阻断项")
        lines.extend(f"- {item}" for item in blocker)
        lines.append("")
    if warning:
        lines.append("## 风险提醒")
        lines.extend(f"- {item}" for item in warning)
        lines.append("")
    if ok:
        lines.append("## 已就绪")
        lines.extend(f"- {item}" for item in ok)
        lines.append("")
    lines.append("## 联动说明")
    lines.append("- 生成正文前会自动执行本检查；有阻断项时默认暂停生成。")
    lines.append("- 生成后会自动执行：审计 → 定点修 → 再审计，并同步章节资料、回写 `.novel-assistant`。")
    lines.append("- 若定点修后仍有质量问题，可到「问题总览」继续处理。")
    lines.append("")
    lines.append("## 生成信息")
    lines.append(f"- 章节：第{chapter}章")
    lines.append(f"- 参考字数：约 {words} 字")
    lines.append(f"- 大纲来源：{data.outline_source or '无'}")

    return {
        "status": status,
        "canProceed": can_proceed,
        "blockers": blocker,
        "warnings": warning,
        "ready": ok,
        "autoSyncRecommended": auto_sync_recommended,
        "suggestedTemperature": temperature,
        "text": "\n".join(lines).strip() + "\n",
    }


def quality_warnings_from_stats(stats: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if stats.get("aiHits"):
        warnings.append(f"AI 解释腔 {len(stats['aiHits'])} 处")
    structural_tells = stats.get("structuralTells") or []
    warning_tells = [item for item in structural_tells if item.get("severity") == "warning"]
    if warning_tells:
        warnings.append(f"AI 结构痕迹 {len(warning_tells)} 项")
    if stats.get("markdownHits"):
        warnings.append(f"Markdown/格式残留 {len(stats['markdownHits'])} 处")
    if stats.get("forbiddenHits"):
        warnings.append(f"禁用词 {len(stats['forbiddenHits'])} 处")
    if stats.get("metaChapterHits"):
        warnings.append(f"章节号穿帮 {len(stats['metaChapterHits'])} 处")
    cn_chars = int(stats.get("cnChars") or 0)
    if cn_chars and cn_chars < 1200:
        warnings.append(f"字数偏短（约 {cn_chars} 字）")
    return warnings


def build_context(data: ProjectData, chapter: int, max_tokens: int = 4500) -> str:
    outline = find_outline(data, chapter)
    previous_bridge = chapter_bridge_text(data, chapter - 1) if chapter > 1 else ""
    target_outline = str(outline.get("content", "")) if outline else ""
    characters = select_characters(data, target_outline)
    foreshadows = select_foreshadows(data, chapter)
    world_text = world_to_text(data.world)

    parts: list[str] = []
    parts.append(f"# 第{chapter}章上下文包")
    parts.append("## 本章大纲")
    if outline:
        parts.append(f"标题：{outline.get('title', '')}\n\n{outline.get('content', '')}")
    else:
        parts.append("未找到本章大纲。")

    if previous_bridge:
        parts.append("## 上章衔接")
        parts.append(previous_bridge)

    if characters:
        parts.append("## 相关人物")
        lines = []
        for char in characters:
            lines.append(
                f"- {char.get('name', '')}｜{char.get('role', '')}："
                f"{truncate(str(char.get('description', '')), 120)}"
                f" 性格：{truncate(str(char.get('personality', '')), 80)}"
            )
        parts.append("\n".join(lines))

    foreshadow_pressure = build_foreshadow_pressure_section(data, chapter)
    if foreshadow_pressure:
        parts.append(foreshadow_pressure)

    if foreshadows:
        parts.append("## 待处理伏笔")
        lines = []
        for fw in foreshadows:
            planted = fw.get("plantedChapter", "")
            invalid_after = fw.get("invalidAfter") or fw.get("invalidAfterChapter") or ""
            deadline = f"，有效至第{invalid_after}章" if invalid_after else ""
            meta = foreshadow_pressure_meta(fw, chapter)
            marker = f"｜{meta['marker']}" if meta.get("marker") else ""
            lines.append(
                f"- {fw.get('id', '')} [{fw.get('importance', '')}｜{foreshadow_urgency(fw, chapter)}{marker}] "
                f"{fw.get('keyword', '')}：第{planted}章埋入{deadline}。{truncate(str(fw.get('description', '')), 120)}"
            )
        parts.append("\n".join(lines))
        parts.append(
            "## 伏笔处理策略\n"
            "- 本章必须主动评估待处理伏笔，但不要为了回收而硬塞。\n"
            "- 如果伏笔和本章大纲、人物行动、场景物证自然相关，优先推进或回收。\n"
            "- 如果伏笔暂时不适合回收，可用一个动作、物件、对话停顿或异常细节轻微推进。\n"
            "- 临近失效的伏笔要优先给出新信息；已过期的伏笔只能做补救解释或后果呈现，不能强行假装按时回收。\n"
            "- 高重要度伏笔不能长期只重复关键词，应该让它产生新的信息、代价或选择。"
        )

    if world_text:
        parts.append("## 世界观摘要")
        parts.append(truncate(world_text, 1200))
        parts.append(f"（信息截至第 {max(chapter - 1, 0)} 章）")

    try:
        from .entities import is_valid_for_chapter, load_organizations

        orgs = [org for org in load_organizations(data.root) if is_valid_for_chapter(org, chapter)]
        if orgs:
            parts.append("## 相关组织势力")
            org_lines = []
            for org in orgs[:8]:
                org_lines.append(
                    f"- {org.get('name', '')}｜{org.get('status', '')}："
                    f"{truncate(str(org.get('description', '')), 100)}"
                )
            parts.append("\n".join(org_lines))
            parts.append(f"（信息截至第 {max(chapter - 1, 0)} 章）")

        rel_lines = []
        for rel in data.relationships:
            if not is_valid_for_chapter(rel, chapter):
                continue
            shown = relationship_display(data, rel)
            rel_lines.append(
                f"- {shown.get('left', '')} ↔ {shown.get('right', '')}："
                f"{shown.get('label', '')}（{shown.get('status', '')}）"
            )
        if rel_lines:
            parts.append("## 正式人物关系")
            parts.append("\n".join(rel_lines[:10]))
            parts.append(f"（信息截至第 {max(chapter - 1, 0)} 章）")
    except Exception:
        pass

    parts.append("## 写作约束")
    parts.append(
        "- 用动作、物证、声音、停顿和人物反应承载信息。\n"
        "- 少用解释型判断句，避免「A是B」「这说明/意味着」。\n"
        "- 对话保留犹豫、吞咽、停顿等人类质感。\n"
        "- 悬疑信息逐层释放，不用作者直接解释真相。\n"
        "- 禁用高频脏话。\n"
        "- 自动考虑待处理伏笔的推进或回收，不需要用户每次额外提醒。\n"
        "- 章节正文不留空行，段落之间只换行一次。\n"
        "- 正文只能使用小说排版，不要输出 Markdown 符号，例如 **加粗**、列表、分隔线、代码块。\n"
        "- 正文禁止出现「想起第X章」「第X章——」等章节号索引式回忆；"
        "人物回忆要用具体场景、动作、对话呈现，不能像目录提要。"
    )

    try:
        from .vector_search import hybrid_search_vector_store
        search_parts = [target_outline]
        for c in characters[:5]:
            search_parts.append(str(c.get("name", "")))
        search_query = " ".join(p for p in search_parts if p).strip()
        if search_query:
            vector_results, _ = hybrid_search_vector_store(data.root, search_query, limit=10)
            if vector_results:
                parts.append("## 相关前文片段（向量检索）")
                for vr in vector_results[:6]:
                    snippet = truncate(str(vr.get("snippet", "")), 300)
                    title = str(vr.get("title", ""))
                    parts.append(f"- 【{title}】{snippet}")
    except Exception:
        pass

    text = "\n\n".join(parts)
    if estimate_cn_tokens(text) <= max_tokens:
        return text
    return trim_context(text, max_tokens)


def build_chapter_plan(data: ProjectData, chapter: int, words: int = 3000) -> str:
    outline = find_outline(data, chapter)
    previous_bridge = chapter_bridge_text(data, chapter - 1) if chapter > 1 else ""
    chapter_file = find_chapter_file(data, chapter)
    target_outline = str(outline.get("content", "")) if outline else ""
    characters = select_characters(data, target_outline, limit=10)
    character_ids = {str(char.get("id", "")) for char in characters if char.get("id")}
    try:
        from .entities import is_valid_for_chapter

        relationships = [
            relationship_display(data, rel)
            for rel in data.relationships
            if str(rel.get("characterId1", "")) in character_ids
            and str(rel.get("characterId2", "")) in character_ids
            and is_valid_for_chapter(rel, chapter)
        ]
    except Exception:
        relationships = [
            relationship_display(data, rel)
            for rel in data.relationships
            if str(rel.get("characterId1", "")) in character_ids and str(rel.get("characterId2", "")) in character_ids
        ]
    foreshadows = select_foreshadows(data, chapter, limit=10)

    lines: list[str] = [f"# 第{chapter}章写作计划"]
    lines.append(f"- 参考篇幅：约 {words} 字，只作节奏参考")
    lines.append(f"- 章节文件：{'已存在，生成会覆盖前请确认' if chapter_file else '未生成'}")

    lines.append("\n## 本章大纲")
    if outline:
        lines.append(f"标题：{outline.get('title', '')}")
        lines.append(str(outline.get("content", "")).strip() or "大纲内容为空。")
    else:
        lines.append("未找到本章大纲。建议先补大纲，或在生成提示词里明确本章目标。")

    lines.append("\n## 上章衔接")
    if previous_bridge:
        lines.append(previous_bridge)
    else:
        lines.append("没有找到上一章摘要或正文。")

    lines.append("\n## 出场人物重点")
    if characters:
        for char in characters:
            lines.append(
                f"- {char.get('name', '')}：{truncate(str(char.get('description', '')), 90)}"
                f"｜性格/状态：{truncate(str(char.get('personality', '')), 70)}"
            )
    else:
        lines.append("未从大纲中匹配到人物，生成前建议手动指定核心人物。")

    lines.append("\n## 关系线索")
    if relationships:
        for rel in relationships[:8]:
            details = "；".join(str(rel.get(key, "")) for key in ("label", "status", "notes") if rel.get(key))
            lines.append(f"- {rel.get('left', '')} ↔ {rel.get('right', '')}：{details or '同场关系待明确'}")
    else:
        lines.append("本章大纲未明显触发既有关系列表。")

    lines.append("\n## 伏笔处理")
    if foreshadows:
        for fw in foreshadows:
            planted = fw.get("plantedChapter", "")
            invalid_after = fw.get("invalidAfter") or fw.get("invalidAfterChapter") or ""
            deadline = f"，有效至第{invalid_after}章" if invalid_after else ""
            lines.append(
                f"- {fw.get('id', '')} [{fw.get('importance', '')}｜{foreshadow_urgency(fw, chapter)}] {fw.get('keyword', '')}"
                f"：第{planted}章埋入{deadline}。{truncate(str(fw.get('description', '')), 100)}"
            )
        lines.append("处理建议：本章自然相关的伏笔要推进或回收；不相关的只保留轻微触碰，避免硬塞。")
    else:
        lines.append("当前没有需要本章关注的未回收伏笔。")

    lines.append("\n## 场次建议")
    beats = [item.strip(" -。；;") for item in split_sentences(target_outline) if len(item.strip()) >= 6]
    if beats:
        for index, beat in enumerate(beats[:5], start=1):
            lines.append(f"{index}. {truncate(beat, 90)}")
    else:
        lines.extend(
            [
                "1. 承接上一章的动作状态，不复述剧情。",
                "2. 用可观察物证或对话推进本章核心问题。",
                "3. 安排一次人物选择或代价，让悬疑信息发生变化。",
                "4. 结尾落在具体钩子上，指向下一章行动。",
            ]
        )

    lines.append("\n## 生成前检查")
    lines.append("- 是否已确认本章核心冲突、出场人物、结尾钩子")
    lines.append("- 是否有必须推进或回收的高优先级伏笔")
    lines.append("- 是否避免 Markdown 符号、空行、解释腔和作者旁白")
    return "\n".join(lines).strip() + "\n"


def trim_context(text: str, max_tokens: int) -> str:
    sections = text.split("\n\n")
    kept: list[str] = []
    for section in sections:
        candidate = "\n\n".join(kept + [section])
        if estimate_cn_tokens(candidate) > max_tokens:
            break
        kept.append(section)
    return "\n\n".join(kept) + "\n\n> 上下文已按 token 预算裁剪。"


def build_prompt(data: ProjectData, chapter: int, words: int, max_tokens: int) -> str:
    ctx = build_context(data, chapter, max_tokens=max_tokens)
    foreshadow_section = build_foreshadow_plan_section(data, chapter)
    sections = [ctx]
    if foreshadow_section:
        sections.append(foreshadow_section)
    body = "\n\n".join(sections)
    return (
        f"{body}\n\n"
        "## 任务\n"
        f"请写第{chapter}章正文。参考篇幅约 {words} 字，但这不是硬性字数限制；优先保证场景完整、动作连续、悬疑节奏成立。\n\n"
        "要求：\n"
        "1. **严格遵循本章大纲**的核心事件、情绪节奏和人物行动，不要偏离主线。大纲中的关键事件必须在正文中体现。\n"
        "2. 直接输出正文，不要解释创作思路。\n"
        "3. 开头承接上章状态，但不要复述上章剧情。\n"
        "4. 每个场景都要有可观察动作和物理细节。\n"
        "5. 保持人物当前认知边界，不能提前知道未揭示真相。\n"
        "6. 结尾留下一个具体、可追踪的悬念或行动钩子。\n"
        "7. 不要使用 Markdown 格式符号；手册文字、纸条内容、提示语也直接写成普通正文或引号。\n"
        "8. 自动处理上下文里的待处理伏笔：自然相关的要推进或回收，不相关的不要硬塞。\n"
        "9. 输出章节正文不要带空行；段落之间只换行一次。\n"
        "10. 禁止在正文里写「想起第X章」「第X章——」这类章节号索引；"
        "回忆前情只能写成人物脑中的具体画面，不能像在翻目录。\n"
        "11. 引用前情细节必须与上下文包、上章衔接一致，不能拼凑不同章节的片段，"
        "更不能编造原文没有发生过的情节。\n"
    )


def load_api_config(args: argparse.Namespace) -> dict[str, str]:
    return {
        "api_key": args.api_key or os.environ.get("NOVELBUDDY_API_KEY", ""),
        "api_base": (args.api_base or os.environ.get("NOVELBUDDY_API_BASE", "https://api.openai.com/v1")).rstrip("/"),
        "model": args.model or os.environ.get("NOVELBUDDY_MODEL", "gpt-4o-mini"),
    }


def parse_api_error_body(body: str) -> str:
    clean = body.strip()
    if not clean:
        return "未知错误"
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        return truncate(clean, 500)
    if isinstance(parsed.get("error"), dict):
        return str(parsed["error"].get("message") or parsed["error"].get("code") or clean)
    if parsed.get("message"):
        return str(parsed["message"])
    return truncate(clean, 500)


def test_api_connection(config: dict[str, str]) -> dict[str, Any]:
    api_key = str(config.get("api_key", "")).strip()
    api_base = str(config.get("api_base", "")).strip().rstrip("/") or "https://api.openai.com/v1"
    model = str(config.get("model", "")).strip() or "gpt-4o-mini"

    if not api_key:
        return {"ok": False, "error": "缺少 API Key。请填写 Key，或设置环境变量 NOVELBUDDY_API_KEY。"}
    if not api_base.startswith(("http://", "https://")):
        return {"ok": False, "error": "API Base 必须以 http:// 或 https:// 开头。"}

    url = f"{api_base}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复：连接成功"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "NovelBuddy/0.1.0",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return {
            "ok": False,
            "error": f"HTTP {exc.code}: {parse_api_error_body(body)}",
            "apiBase": api_base,
            "model": model,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "error": f"网络请求失败: {exc.reason}",
            "apiBase": api_base,
            "model": model,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    except TimeoutError:
        return {
            "ok": False,
            "error": "请求超时（30 秒）。请检查 API Base 是否正确，或网络是否可达。",
            "apiBase": api_base,
            "model": model,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }

    latency_ms = int((time.monotonic() - started) * 1000)
    try:
        reply = str(data["choices"][0]["message"]["content"]).strip()
    except Exception:
        return {
            "ok": False,
            "error": f"返回格式无法解析: {truncate(json.dumps(data, ensure_ascii=False), 500)}",
            "apiBase": api_base,
            "model": model,
            "latencyMs": latency_ms,
        }

    return {
        "ok": True,
        "message": "连接成功",
        "apiBase": api_base,
        "model": model,
        "latencyMs": latency_ms,
        "reply": truncate(reply, 120),
    }


def call_openai_compatible(prompt: str, config: dict[str, str], temperature: float) -> str:
    if not config["api_key"]:
        raise SystemExit(
            "缺少 API Key。设置环境变量 NOVELBUDDY_API_KEY，或使用 --api-key 传入。"
        )
    url = f"{config['api_base']}/chat/completions"
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": "你是小说创作助手。只输出用户要求的正文或编辑结果，不解释过程。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
            "User-Agent": "NovelBuddy/0.1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise SystemExit(f"AI 请求失败 HTTP {exc.code}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"AI 请求失败: {exc}") from exc
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except Exception as exc:
        raise SystemExit(f"AI 返回格式无法解析: {json.dumps(data, ensure_ascii=False)[:1000]}") from exc


def parse_outline_with_ai(outline_path: Path, config: dict[str, str]) -> dict[str, Any]:
    raw = outline_path.read_text(encoding="utf-8")
    outline_text = raw[:60000] if len(raw) > 60000 else raw
    prompt = (
        "你是一个小说数据分析助手。请从以下小说大纲中提取结构化信息。\n\n"
        "大纲内容：\n"
        "```\n"
        f"{outline_text}\n"
        "```\n\n"
        "请提取以下信息，严格输出 JSON（不要输出其他任何内容）：\n"
        "{\n"
        '  "characters": [\n'
        '    {"name": "角色名", "role": "protagonist/supporting/antagonist/minor",\n'
        '     "description": "角色简介", "personality": "性格特点", "background": "背景故事"}\n'
        "  ],\n"
        '  "relationships": [\n'
        '    {"characterName1": "角色A", "characterName2": "角色B",\n'
        '     "relationshipLabel": "关系描述"}\n'
        "  ],\n"
        '  "organizations": [\n'
        '    {"name": "组织名", "type": "government/criminal/military/religious/corporation/other",\n'
        '     "description": "组织描述", "status": "active/inactive/destroyed/unknown",\n'
        '     "level": "local/regional/national/international",\n'
        '     "powerLevel": "low/medium/high"}\n'
        "  ],\n"
        '  "worldview": {\n'
        '    "setting": "故事背景设定",\n'
        '    "rules": "核心规则或世界观设定",\n'
        '    "powerSystem": "力量体系或超自然体系描述"\n'
        "  },\n"
        '  "timeline": [\n'
        '    {"chapter": 章节号, "event": "关键事件摘要", "characters": ["涉及角色"]}\n'
        "  ]\n"
        "}\n\n"
        "注意：\n"
        "- role 只能是 protagonist（主角）、supporting（配角）、antagonist（反派）、minor（次要）\n"
        "- organization type 只能是 government、criminal、military、religious、corporation、other\n"
        "- 只提取大纲中明确提到的角色和组织，不要凭空捏造\n"
        "- timeline 只提取每章的核心事件（1-2条）"
    )
    config_for_parse = dict(config)
    config_for_parse["temperature"] = "0.3"
    result_text = call_openai_compatible(prompt, config_for_parse, 0.3)
    result_text = result_text.strip()
    if result_text.startswith("```"):
        lines = result_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        result_text = "\n".join(lines)
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {
            "characters": [],
            "relationships": [],
            "organizations": [],
            "worldview": {},
            "timeline": [],
        }


def is_exempt_negation_contrast(snippet: str, line: str) -> bool:
    if any(marker in snippet for marker in ABSTRACT_FLAG_MARKERS):
        return False
    if any(marker in snippet or marker in line for marker in PHYSICAL_EXEMPT_MARKERS):
        return True
    concrete = re.match(r"不是(.{1,8}?)[，,]?而是(.{1,10})", snippet)
    if concrete:
        left, right = concrete.group(1), concrete.group(2)
        abstract_words = ("觉得", "认为", "因为", "所以", "其实", "根本", "真正", "本质上")
        if not any(word in left + right for word in abstract_words):
            return True
    return False


def collect_ai_pattern_hits(text: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    def add_hit(pattern: str, line_no: int, snippet: str) -> None:
        bucket = grouped.setdefault(pattern, {"pattern": pattern, "count": 0, "lines": [], "snippets": []})
        bucket["count"] += 1
        if line_no not in bucket["lines"]:
            bucket["lines"].append(line_no)
        bucket["snippets"].append(snippet[:48])

    for pattern in AI_SIMPLE_PATTERNS:
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in re.finditer(pattern, line):
                add_hit(pattern, line_no, match.group(0))

    for line_no, line in enumerate(text.splitlines(), start=1):
        seen_spans: list[tuple[int, int]] = []
        for match in NEGATION_CONTRAST_RE.finditer(line):
            snippet = match.group(0)
            if is_exempt_negation_contrast(snippet, line):
                continue
            span = match.span()
            if any(start <= span[0] < end or start < span[1] <= end for start, end in seen_spans):
                continue
            seen_spans.append(span)
            pattern = "不是.*?而是" if "而是" in snippet else "不是.*?是"
            add_hit(pattern, line_no, snippet)

    ai_hits: list[dict[str, Any]] = []
    for item in grouped.values():
        ai_hits.append(
            {
                "pattern": item["pattern"],
                "count": item["count"],
                "lines": item["lines"][:8],
            }
        )
    return ai_hits


def collect_meta_chapter_ref_hits(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line_no == 1 and re.match(r"^\s*#\s*第\s*\d+\s*章", line):
            continue
        for match in META_CHAPTER_REF_RE.finditer(line):
            hits.append(
                {
                    "line": line_no,
                    "snippet": truncate(match.group(0), 40),
                }
            )
    return hits


def audit_stats(data: ProjectData, text: str, chapter: int | None = None) -> dict[str, Any]:
    cn_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    forbidden_hits = [
        {"word": word, "count": text.count(word)}
        for word in DEFAULT_FORBIDDEN_WORDS
        if text.count(word)
    ]
    ai_hits = collect_ai_pattern_hits(text)
    structural_tells = analyze_ai_tells(text)

    markdown_hits = []
    for pattern, label in MARKDOWN_PATTERNS:
        hit_lines = []
        for idx, line in enumerate(text.splitlines(), start=1):
            if idx == 1 and re.match(r"^\s*#\s*第\s*\d+\s*章", line):
                continue
            if re.search(pattern, line):
                hit_lines.append(idx)
        if hit_lines:
            markdown_hits.append({"label": label, "count": len(hit_lines), "lines": hit_lines[:8]})

    foreshadow_hits: list[dict[str, Any]] = []
    foreshadow_pending_total = 0
    if chapter is not None:
        pending_foreshadows = select_foreshadows(data, chapter, limit=999, include_expired=False)
        foreshadow_pending_total = len(pending_foreshadows)
        for fw in pending_foreshadows[:12]:
            keyword = str(fw.get("keyword", "")).strip()
            foreshadow_hits.append(
                {
                    "id": fw.get("id", ""),
                    "keyword": keyword,
                    "hit": bool(keyword and keyword in text),
                }
            )

    meta_chapter_hits = collect_meta_chapter_ref_hits(text)
    dialogue_count = len(re.findall(r"[“\"].+?[”\"]", text))
    warnings = []
    if cn_chars < 1800:
        warnings.append("章节偏短")
    if cn_chars > 4500:
        warnings.append("章节偏长")
    if dialogue_count == 0:
        warnings.append("缺少明显对话")
    if ai_hits:
        warnings.append("AI句式风险")
    if any(item.get("severity") == "warning" for item in structural_tells):
        warnings.append("AI结构痕迹")
    if markdown_hits:
        warnings.append("非正文格式残留")
    if forbidden_hits:
        warnings.append("禁用词")
    if meta_chapter_hits:
        warnings.append("正文出现章节号回忆")

    return {
        "cnChars": cn_chars,
        "forbiddenHits": forbidden_hits,
        "aiHits": ai_hits,
        "structuralTells": structural_tells,
        "markdownHits": markdown_hits,
        "metaChapterHits": meta_chapter_hits,
        "dialogueCount": dialogue_count,
        "foreshadows": foreshadow_hits,
        "foreshadowPendingTotal": foreshadow_pending_total,
        "warnings": warnings,
    }


def audit_text(data: ProjectData, text: str, chapter: int | None = None) -> str:
    lines: list[str] = []
    lines.append("# 章节审查报告")
    stats = audit_stats(data, text, chapter)
    cn_chars = int(stats["cnChars"])
    lines.append(f"- 中文字数估算：{cn_chars}")

    forbidden_hits = stats["forbiddenHits"]
    if forbidden_hits:
        lines.append("## 禁用词")
        for item in forbidden_hits:
            lines.append(f"- `{item['word']}`：{item['count']} 次")

    pattern_hits = stats["aiHits"]
    if pattern_hits:
        lines.append("## AI痕迹风险")
        for item in pattern_hits:
            pattern = item["pattern"]
            count = item["count"]
            hit_lines = item["lines"]
            suffix = f"；行 {', '.join(map(str, hit_lines))}" if hit_lines else ""
            lines.append(f"- `{pattern}`：{count} 次{suffix}")
    else:
        lines.append("## AI痕迹风险\n- 未发现高频风险句式。")

    structural_tells = stats.get("structuralTells") or []
    if structural_tells:
        lines.append("## AI结构痕迹（InkOS 式检测）")
        for item in structural_tells:
            severity = "警告" if item.get("severity") == "warning" else "提示"
            lines.append(f"- [{severity}] {item.get('category', '')}：{item.get('description', '')}")
            suggestion = str(item.get("suggestion") or "").strip()
            if suggestion:
                lines.append(f"  建议：{suggestion}")
    else:
        lines.append("## AI结构痕迹\n- 未发现段落等长、套话密度、公式化转折或列表式结构问题。")

    markdown_hits = stats["markdownHits"]
    if markdown_hits:
        lines.append("## 非正文格式残留")
        for item in markdown_hits:
            label = item["label"]
            count = item["count"]
            hit_lines = item["lines"]
            suffix = f"；行 {', '.join(map(str, hit_lines))}" if hit_lines else ""
            lines.append(f"- {label}：{count} 处{suffix}")

    meta_chapter_hits = stats.get("metaChapterHits") or []
    if meta_chapter_hits:
        lines.append("## 章节号穿帮（应改写为场景回忆）")
        for item in meta_chapter_hits:
            lines.append(f"- 行 {item['line']}：`{item['snippet']}`")
        lines.append(
            "- 建议：不要用「想起第X章」，改成具体画面、动作或对话；"
            "回忆应像人物自然想起，而不是目录索引。"
        )

    if chapter is not None:
        foreshadows = stats["foreshadows"]
        if foreshadows:
            lines.append("## 伏笔命中")
            for fw in foreshadows:
                mark = "命中" if fw.get("hit") else "未命中"
                keyword = fw.get("keyword", "")
                lines.append(f"- {mark}：{fw.get('id', '')} {keyword}")

    dialogue_count = int(stats["dialogueCount"])
    lines.append("## 结构观察")
    lines.append(f"- 对话段落估算：{dialogue_count}")
    if dialogue_count == 0:
        lines.append("- 风险：没有明显对话，若本章有人物互动，可能会偏叙述化。")
    if cn_chars < 1800:
        lines.append("- 风险：章节偏短，可能承载不了完整起承转合。")
    if cn_chars > 4500:
        lines.append("- 风险：章节偏长，注意场景切换和重复说明。")

    return "\n".join(lines) + "\n"


def apply_rule_fixes(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    fixed_lines: list[str] = []
    for idx, line in enumerate(lines, start=1):
        cleaned = line
        if idx == 1 and re.match(r"^\s*#\s*第\s*\d+\s*章", cleaned):
            cleaned = re.sub(r"^\s*#\s*", "", cleaned).strip()
            if cleaned != line.strip():
                changes.append("移除章节标题 Markdown #")
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"__(.+?)__", r"\1", cleaned)
        cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned)
        cleaned = re.sub(r"^\s*#{1,6}\s+", "", cleaned)
        cleaned = re.sub(r"^\s*---+\s*$", "", cleaned)
        for word in DEFAULT_FORBIDDEN_WORDS:
            if word and word in cleaned:
                cleaned = cleaned.replace(word, "")
                changes.append(f"移除禁用词：{word}")
        if cleaned != line and "格式残留" not in changes:
            if re.search(r"\*\*|__|^\s*[-*+#]", line):
                changes.append("清理 Markdown 格式残留")
        fixed_lines.append(cleaned)
    result = normalize_chapter_text("\n".join(fixed_lines))
    return result, list(dict.fromkeys(changes))


def quality_item_from_stats(
    stats: dict[str, Any],
    chapter: int,
    name: str,
    path: str,
) -> dict[str, Any]:
    foreshadows = stats.get("foreshadows", [])
    problems: list[str] = []
    for item in stats.get("aiHits", []):
        suffix = f"，行 {', '.join(map(str, item.get('lines', [])))}" if item.get("lines") else ""
        problems.append(f"AI句式：{item.get('pattern', '')}（{item.get('count', 0)}次{suffix}）")
    for item in stats.get("structuralTells", []):
        if item.get("severity") != "warning":
            continue
        problems.append(f"AI结构：{item.get('category', '')}（{item.get('description', '')}）")
    for item in stats.get("markdownHits", []):
        suffix = f"，行 {', '.join(map(str, item.get('lines', [])))}" if item.get("lines") else ""
        problems.append(f"格式残留：{item.get('label', '')}（{item.get('count', 0)}处{suffix}）")
    for item in stats.get("forbiddenHits", []):
        problems.append(f"禁用词：{item.get('word', '')}（{item.get('count', 0)}次）")
    for warning in stats.get("warnings", []):
        if warning in STRUCTURAL_QUALITY_WARNINGS:
            problems.append(str(warning))
    ai_risk = sum(int(item.get("count", 0)) for item in stats.get("aiHits", []))
    structural_risk = sum(
        1 for item in stats.get("structuralTells", []) if item.get("severity") == "warning"
    )
    format_risk = sum(int(item.get("count", 0)) for item in stats.get("markdownHits", []))
    forbidden = sum(int(item.get("count", 0)) for item in stats.get("forbiddenHits", []))
    has_problems = bool(ai_risk or structural_risk or format_risk or forbidden)
    return {
        "chapter": chapter,
        "name": name,
        "path": path,
        "cnChars": stats.get("cnChars", 0),
        "dialogueCount": stats.get("dialogueCount", 0),
        "aiRiskCount": ai_risk,
        "structuralTellCount": structural_risk,
        "formatRiskCount": format_risk,
        "forbiddenCount": forbidden,
        "foreshadowHitCount": sum(1 for item in foreshadows if item.get("hit")),
        "foreshadowTotal": int(stats.get("foreshadowPendingTotal") or len(foreshadows)),
        "warnings": stats.get("warnings", []),
        "problems": problems,
        "hasProblems": has_problems,
        "canRuleFix": bool(stats.get("markdownHits") or stats.get("forbiddenHits")),
        "needsAiFix": bool(stats.get("aiHits") or structural_risk),
    }


def needs_auto_fix(stats: dict[str, Any]) -> bool:
    if stats.get("markdownHits") or stats.get("forbiddenHits"):
        return True
    if stats.get("metaChapterHits"):
        return True
    if stats.get("aiHits"):
        return True
    if any(item.get("severity") == "warning" for item in stats.get("structuralTells", [])):
        return True
    return False


REWRITE_ANTI_AI_RULES = (
    "1. 保留原章节标题（如有）和全部核心剧情：事件顺序、人物出场、对话信息、伏笔推进不能删改。\n"
    "2. 重写的是**文笔和节奏**，不是剧情。禁止擅自增删关键情节或改变结局。\n"
    "3. 禁止破折号后叠排抽象形容词，如「整齐、克制、不快不慢」。\n"
    "4. 禁止「不快不慢 / 不疾不徐 / 不紧不慢」等对称节奏词。\n"
    "5. 少用「刚…还没…就…」镜头链；单句逗号不超过 2 个，过长就拆句。\n"
    "6. 比喻每段最多 1 处；优先动作、对话、感官细节，少写气氛修饰。\n"
    "7. 禁止「这说明 / 这意味着 / 显然 / 他意识到」等解释腔。\n"
    "8. 对话要像真人说话：有停顿、省略、不完整句，不要太工整。\n"
    "9. 不要用 Markdown 符号；正文不要空行，段落之间只换行一次。\n"
    "10. 只输出重写后的完整章节正文，不要输出修改说明。\n"
    "11. 禁止「想起第X章」「第X章——」等章节号索引式回忆。"
)


def build_rewrite_prompt(
    data: ProjectData,
    chapter: int,
    original: str,
    *,
    writing_rules: str = "",
    rewrite_note: str = "",
) -> str:
    outline = find_outline(data, chapter)
    outline_block = ""
    if outline:
        title = str(outline.get("title", "") or f"第{chapter}章").strip()
        content = str(outline.get("content", "")).strip()
        outline_block = f"## 本章大纲\n标题：{title}\n{content}\n\n"

    rules_section = f"## 用户自定义写作规则\n{writing_rules.strip()}\n\n" if writing_rules.strip() else ""
    note_section = f"## 用户补充要求\n{rewrite_note.strip()}\n\n" if rewrite_note.strip() else ""
    cn_chars = len(re.findall(r"[\u4e00-\u9fff]", original))

    return (
        f"{build_context(data, chapter, max_tokens=4500)}\n\n"
        f"{outline_block}"
        f"{rules_section}"
        f"{note_section}"
        "## 重写任务\n"
        f"请重写第{chapter}章正文。原文约 {cn_chars} 字，重写后篇幅接近原文（±15%）。\n\n"
        "## 反 AI 文风要求\n"
        f"{REWRITE_ANTI_AI_RULES}\n\n"
        "## 原文\n"
        f"{original}"
    )


def build_ai_revise_prompt(
    data: ProjectData,
    chapter: int,
    original: str,
    *,
    writing_rules: str = "",
    source_text: str | None = None,
) -> str:
    report = audit_text(data, source_text or original, chapter)
    rules_section = f"## 用户自定义写作规则\n{writing_rules.strip()}\n\n" if writing_rules.strip() else ""
    return (
        f"{build_context(data, chapter, max_tokens=4500)}\n\n"
        f"{rules_section}"
        "## 修改任务\n"
        f"下面是第{chapter}章原文和审查报告。请直接输出修改后的完整章节正文。\n"
        "要求：保留原章节标题；不改变大纲方向；优先修复审查报告中的问题；删掉 Markdown 加粗、列表、分隔线等非正文符号；"
        "减少“不是A，是B”“这说明/意味着/显然”等解释腔；修正明显错字和标点；不要输出修改说明；正文不要带空行，段落之间只换行一次。\n\n"
        f"## 审查报告\n{report}\n\n"
        f"## 原文\n{source_text or original}"
    )


def auto_fix_chapter_content(
    data: ProjectData,
    chapter: int,
    original: str,
    *,
    mode: str = "auto",
    config: dict[str, Any] | None = None,
    writing_rules: str = "",
) -> dict[str, Any]:
    if mode not in {"rules", "ai", "auto"}:
        raise ValueError("修复模式无效，请使用 rules、ai 或 auto。")

    before_stats = audit_stats(data, original, chapter)
    fixes_applied: list[str] = []
    working = original

    if mode in {"rules", "auto"}:
        working, rule_changes = apply_rule_fixes(original)
        fixes_applied.extend(rule_changes)

    from .style_reference import append_style_reference

    if mode == "ai":
        if not config or not str(config.get("api_key") or "").strip():
            raise ValueError("缺少 API Key。AI 修复前请先在页面 API 设置里填写。")
        prompt = append_style_reference(
            build_ai_revise_prompt(data, chapter, original, writing_rules=writing_rules),
            data.root,
        )
        working = normalize_chapter_text(call_openai_compatible(prompt, config, 0.35))
        if not working:
            raise ValueError("AI 没有返回修改后的正文。")
        fixes_applied.append("AI 定点改写")
    elif mode == "auto":
        after_rule_stats = audit_stats(data, working, chapter)
        if needs_auto_fix(after_rule_stats):
            if not config or not str(config.get("api_key") or "").strip():
                if needs_auto_fix(before_stats) and not fixes_applied:
                    raise ValueError("检测到可修复问题，但缺少 API Key，无法继续 AI 定点修复。")
            else:
                prompt = append_style_reference(
                    build_ai_revise_prompt(
                        data,
                        chapter,
                        original,
                        writing_rules=writing_rules,
                        source_text=working,
                    ),
                    data.root,
                )
                ai_text = normalize_chapter_text(call_openai_compatible(prompt, config, 0.35))
                if not ai_text:
                    raise ValueError("AI 没有返回修改后的正文。")
                working = ai_text
                fixes_applied.append("AI 定点改写")

    working = normalize_chapter_text(working)
    unchanged = working == normalize_chapter_text(original)
    after_stats = audit_stats(data, working if not unchanged else original, chapter)
    return {
        "text": working,
        "unchanged": unchanged,
        "fixesApplied": fixes_applied,
        "beforeStats": before_stats,
        "afterStats": after_stats,
        "mode": mode,
    }


def check_outline_consistency(data: ProjectData, chapter: int, text: str) -> dict[str, Any]:
    """检测正文与大纲的一致性，返回偏离信息"""
    outline = find_outline(data, chapter)
    if not outline:
        return {"consistent": True, "deviation": "", "missingEvents": [], "suggestion": "未找到本章大纲，建议先补大纲"}

    outline_content = str(outline.get("content", ""))
    lines = [line.strip() for line in outline_content.split("\n") if line.strip()]
    key_events = [line.lstrip("- •·→> ").strip() for line in lines if len(line.strip()) > 8]
    key_events = [e for e in key_events if not e.startswith("#") and not e.startswith(">")]

    missing_events: list[str] = []
    for event in key_events[:8]:
        event_keywords = [kw for kw in event.split() if len(kw) >= 2]
        if event_keywords and not any(kw in text for kw in event_keywords):
            missing_events.append(truncate(event, 60))

    if not missing_events:
        return {"consistent": True, "deviation": "", "missingEvents": [], "suggestion": ""}

    deviation = f"大纲中 {len(missing_events)} 个关键事件未在正文中体现"
    return {
        "consistent": False,
        "deviation": deviation,
        "missingEvents": missing_events,
        "suggestion": f"建议对照大纲调整正文，补充以下事件：{'；'.join(missing_events[:3])}",
    }


def check_character_consistency(data: ProjectData) -> list[dict[str, Any]]:
    """检测角色数据一致性：同名不同ID、ID为空等"""
    issues: list[dict[str, Any]] = []
    name_to_ids: dict[str, list[str]] = {}
    for char in data.characters:
        name = str(char.get("name", "")).strip()
        cid = str(char.get("id", "")).strip()
        if name:
            name_to_ids.setdefault(name, []).append(cid)

    for name, ids in name_to_ids.items():
        unique_ids = [i for i in ids if i]
        if len(unique_ids) > 1:
            issues.append({
                "type": "duplicate_character",
                "name": name,
                "ids": unique_ids,
                "message": f"角色「{name}」存在 {len(unique_ids)} 个不同ID，建议合并",
            })
        elif len(unique_ids) == 0:
            issues.append({
                "type": "missing_id",
                "name": name,
                "ids": [],
                "message": f"角色「{name}」缺少ID",
            })
    return issues


def check_foreshadow_health(data: ProjectData, current_chapter: int) -> list[dict[str, Any]]:
    """检测伏笔健康状态：过期、拖延、高优先级未回收"""
    issues: list[dict[str, Any]] = []
    for fw in data.foreshadows:
        if fw.get("status") == "resolved":
            continue
        fw_id = str(fw.get("id", ""))
        keyword = str(fw.get("keyword", ""))
        importance = str(fw.get("importance", "medium"))
        planted = int(fw.get("plantedChapter") or 0)
        invalid_after = int(fw.get("invalidAfter") or fw.get("invalidAfterChapter") or 999999)

        if invalid_after < current_chapter:
            issues.append({
                "type": "foreshadow_expired",
                "id": fw_id,
                "keyword": keyword,
                "importance": importance,
                "plantedChapter": planted,
                "invalidAfter": invalid_after,
                "message": f"伏笔「{keyword}」已过期（第{planted}章埋入，有效至第{invalid_after}章，当前第{current_chapter}章）",
            })
        elif invalid_after - current_chapter <= 5 and importance == "high":
            issues.append({
                "type": "foreshadow_expiring",
                "id": fw_id,
                "keyword": keyword,
                "importance": importance,
                "plantedChapter": planted,
                "invalidAfter": invalid_after,
                "message": f"高优先级伏笔「{keyword}」临近失效（剩{invalid_after - current_chapter}章）",
            })
        elif planted and current_chapter - planted >= 10:
            issues.append({
                "type": "foreshadow_stale",
                "id": fw_id,
                "keyword": keyword,
                "importance": importance,
                "plantedChapter": planted,
                "message": f"伏笔「{keyword}」已拖延 {current_chapter - planted} 章未回收",
            })
    return issues


def check_outline_deviation(data: ProjectData) -> list[dict[str, Any]]:
    """检测所有已写章节与大纲的偏离"""
    issues: list[dict[str, Any]] = []
    for path in data.chapters:
        chapter = chapter_number_from_name(path)
        if not chapter:
            continue
        text = read_text(path)
        result = check_outline_consistency(data, chapter, text)
        if not result["consistent"]:
            issues.append({
                "type": "outline_deviation",
                "chapter": chapter,
                "deviation": result["deviation"],
                "missingEvents": result.get("missingEvents", []),
                "message": f"第{chapter}章偏离大纲：{result['deviation']}",
            })
    return issues


def run_post_generation_pipeline(
    data: ProjectData,
    chapter: int,
    file_path: Path,
    text: str,
    *,
    config: dict[str, Any] | None = None,
    writing_rules: str = "",
    auto_fix: bool = True,
    fix_mode: str = "auto",
) -> dict[str, Any]:
    initial_stats = audit_stats(data, text, chapter)
    initial_report = audit_text(data, text, chapter)
    audit_path = file_path.with_name(file_path.stem + "-审查.md")
    audit_path.write_text(initial_report, encoding="utf-8")
    analysis = update_chapter_state(data, chapter, text)

    outline_check = check_outline_consistency(data, chapter, text)

    pipeline: dict[str, Any] = {
        "stages": ["audit"],
        "initialStats": initial_stats,
        "finalStats": initial_stats,
        "auditPath": str(audit_path),
        "auditText": initial_report,
        "analysis": analysis,
        "text": text,
        "fixesApplied": [],
        "fixed": False,
        "unchanged": True,
        "backupPath": "",
        "outlineCheck": outline_check,
    }

    if not outline_check["consistent"]:
        pipeline.setdefault("qualityWarnings", [])
        pipeline["qualityWarnings"].append({
            "type": "outline_deviation",
            "message": outline_check["deviation"],
            "suggestion": outline_check["suggestion"],
            "missingEvents": outline_check.get("missingEvents", []),
        })

    if not auto_fix or not needs_auto_fix(initial_stats):
        pipeline["qualityWarnings"] = quality_warnings_from_stats(initial_stats)
        if not outline_check["consistent"]:
            pipeline["qualityWarnings"].append({
                "type": "outline_deviation",
                "message": outline_check["deviation"],
                "suggestion": outline_check["suggestion"],
            })
        pipeline["suggestedFix"] = bool(pipeline["qualityWarnings"])
        return pipeline

    fix_result = auto_fix_chapter_content(
        data,
        chapter,
        text,
        mode=fix_mode,
        config=config,
        writing_rules=writing_rules,
    )
    pipeline["stages"].append("fix")
    pipeline["fixesApplied"] = fix_result.get("fixesApplied", [])
    pipeline["beforeStats"] = fix_result.get("beforeStats", initial_stats)

    if fix_result.get("unchanged"):
        pipeline["qualityWarnings"] = quality_warnings_from_stats(initial_stats)
        if not outline_check["consistent"]:
            pipeline["qualityWarnings"].append({
                "type": "outline_deviation",
                "message": outline_check["deviation"],
                "suggestion": outline_check["suggestion"],
            })
        pipeline["suggestedFix"] = bool(pipeline["qualityWarnings"])
        return pipeline

    saved = save_fixed_chapter(data, chapter, file_path, text, fix_result["text"])
    pipeline["stages"].append("re-audit")
    pipeline.update(saved)
    pipeline["fixed"] = True
    pipeline["unchanged"] = False
    pipeline["finalStats"] = saved.get("afterStats", fix_result.get("afterStats", initial_stats))
    pipeline["qualityWarnings"] = quality_warnings_from_stats(pipeline["finalStats"])
    if not outline_check["consistent"]:
        pipeline["qualityWarnings"].append({
            "type": "outline_deviation",
            "message": outline_check["deviation"],
            "suggestion": outline_check["suggestion"],
        })
    pipeline["suggestedFix"] = bool(pipeline["qualityWarnings"])
    return pipeline


def save_fixed_chapter(
    data: ProjectData,
    chapter: int,
    file_path: Path,
    original: str,
    revised: str,
) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = file_path.with_name(f"{file_path.stem}.bak-{stamp}{file_path.suffix}")
    backup_path.write_text(original, encoding="utf-8")
    file_path.write_text(revised, encoding="utf-8")
    audit_report = audit_text(data, revised, chapter)
    audit_path = file_path.with_name(file_path.stem + "-审查.md")
    audit_path.write_text(audit_report, encoding="utf-8")
    analysis = update_chapter_state(data, chapter, revised)
    return {
        "chapterPath": str(file_path),
        "backupPath": str(backup_path),
        "auditPath": str(audit_path),
        "text": revised,
        "auditText": audit_report,
        "analysis": analysis,
        "beforeStats": audit_stats(data, original, chapter),
        "afterStats": audit_stats(data, revised, chapter),
    }


def export_markdown(data: ProjectData) -> str:
    lines: list[str] = ["# NovelBuddy 项目导出", f"项目：{data.root}"]
    lines.append("\n## 人物")
    for char in data.characters:
        lines.append(f"### {char.get('name', '')}")
        lines.append(f"- 角色：{char.get('role', '')}")
        lines.append(f"- 描述：{char.get('description', '')}")
        if char.get("personality"):
            lines.append(f"- 性格：{char.get('personality')}")
        if char.get("background"):
            lines.append(f"- 背景：{char.get('background')}")

    lines.append("\n## 大纲")
    for outline in sorted(data.outlines, key=lambda x: int(x.get("chapterNumber") or 999999)):
        lines.append(f"### 第{outline.get('chapterNumber', '')}章 {outline.get('title', '')}")
        lines.append(str(outline.get("content", "")))

    lines.append("\n## 伏笔")
    for fw in data.foreshadows:
        lines.append(
            f"- {fw.get('id', '')} [{fw.get('status', '')}/{fw.get('importance', '')}] "
            f"第{fw.get('plantedChapter', '')}章 {fw.get('keyword', '')}：{fw.get('description', '')}"
        )

    lines.append("\n## 世界观")
    lines.append(world_to_text(data.world) or "无")
    return "\n\n".join(lines) + "\n"


def export_manuscript(data: ProjectData) -> str:
    lines: list[str] = ["# 正文合集", f"项目：{data.root}"]
    for path in data.chapters:
        text = normalize_chapter_text(read_text(path)).strip()
        if not text:
            continue
        lines.append(text)
    return "\n\n".join(lines).strip() + "\n"


def cmd_scan(args: argparse.Namespace) -> int:
    data = load_project(args.project)
    print(f"项目: {data.root}")
    print(f"人物: {len(data.characters)}")
    print(f"大纲: {len(data.outlines)}")
    print(f"摘要: {len(data.summaries)}")
    print(f"伏笔: {len(data.foreshadows)}")
    print(f"章节文件: {len(data.chapters)}")
    print(f"世界观: {'有' if data.world else '无'}")
    print(f"大纲来源: {data.outline_source or '无'}")
    if data.chapters:
        print("最近章节:")
        for path in data.chapters[-5:]:
            print(f"- {path}")
    return 0


def write_or_print(content: str, out: str | None) -> None:
    if out:
        path = Path(out).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"已写入: {path}")
    else:
        print(content)


def cmd_context(args: argparse.Namespace) -> int:
    data = load_project(args.project)
    write_or_print(build_context(data, args.chapter, args.max_tokens), args.out)
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    data = load_project(args.project)
    write_or_print(build_prompt(data, args.chapter, args.words, args.max_tokens), args.out)
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    data = load_project(args.project)
    prompt = build_prompt(data, args.chapter, args.words, args.max_tokens)
    if args.prompt_out:
        Path(args.prompt_out).resolve().write_text(prompt, encoding="utf-8")
        print(f"提示词已写入: {Path(args.prompt_out).resolve()}")
    draft = normalize_chapter_text(call_openai_compatible(prompt, load_api_config(args), args.temperature))
    write_or_print(draft, args.out)
    if args.audit_out:
        report = audit_text(data, draft, args.chapter)
        Path(args.audit_out).resolve().write_text(report, encoding="utf-8")
        print(f"审查报告已写入: {Path(args.audit_out).resolve()}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    data = load_project(args.project)
    file_path = Path(args.file).resolve()
    text = read_text(file_path)
    chapter = args.chapter or chapter_number_from_name(file_path)
    write_or_print(audit_text(data, text, chapter), args.out)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    data = load_project(args.project)
    write_or_print(export_markdown(data), args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novelbuddy", description="Local novel writing assistant.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="扫描小说项目")
    scan.add_argument("project")
    scan.set_defaults(func=cmd_scan)

    context = sub.add_parser("context", help="生成章节上下文包")
    context.add_argument("project")
    context.add_argument("chapter", type=int)
    context.add_argument("--max-tokens", type=int, default=4500)
    context.add_argument("--out")
    context.set_defaults(func=cmd_context)

    prompt = sub.add_parser("prompt", help="生成章节写作提示词")
    prompt.add_argument("project")
    prompt.add_argument("chapter", type=int)
    prompt.add_argument("--words", type=int, default=3000)
    prompt.add_argument("--max-tokens", type=int, default=4500)
    prompt.add_argument("--out")
    prompt.set_defaults(func=cmd_prompt)

    draft = sub.add_parser("draft", help="调用自己的 OpenAI 兼容 API 生成章节草稿")
    draft.add_argument("project")
    draft.add_argument("chapter", type=int)
    draft.add_argument("--words", type=int, default=3000)
    draft.add_argument("--max-tokens", type=int, default=4500)
    draft.add_argument("--temperature", type=float, default=0.72)
    draft.add_argument("--api-key")
    draft.add_argument("--api-base")
    draft.add_argument("--model")
    draft.add_argument("--out", required=True)
    draft.add_argument("--prompt-out")
    draft.add_argument("--audit-out")
    draft.set_defaults(func=cmd_draft)

    audit = sub.add_parser("audit", help="审查章节正文")
    audit.add_argument("project")
    audit.add_argument("file")
    audit.add_argument("--chapter", type=int)
    audit.add_argument("--out")
    audit.set_defaults(func=cmd_audit)

    export = sub.add_parser("export", help="导出项目资料")
    export.add_argument("project")
    export.add_argument("--out")
    export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
