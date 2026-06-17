from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .cli import (
    audit_text,
    audit_stats,
    build_chapter_plan,
    build_context,
    build_prompt,
    call_openai_compatible,
    test_api_connection,
    chapter_output_path,
    export_manuscript,
    export_markdown,
    find_outline,
    find_outline_md,
    find_chapter_file,
    chapter_bridge_text,
    foreshadow_urgency,
    generate_outline_data,
    load_project,
    load_novelbuddy_state,
    normalize_chapter_text,
    normalize_world_for_ui,
    read_text,
    build_relationship_graph,
    relationship_display,
    auto_fix_chapter_content,
    build_ai_revise_prompt,
    build_rewrite_prompt,
    run_post_generation_pipeline,
    save_fixed_chapter,
    save_outline,
    quality_item_from_stats,
    quality_warnings_from_stats,
    run_writing_preflight,
    select_foreshadows,
    suggest_chapter_temperature,
    sync_project_state,
    truncate,
    update_chapter_state,
)
from .entities import (
    batch_analyze_chapters,
    delete_entity,
    hybrid_search_project,
    list_entities,
    load_organizations,
    load_refine_templates,
    save_entity,
    self_check_report,
)
from .entity_enums import decorate_entity_for_ui
from .style_reference import (
    append_style_reference,
    clear_style_reference,
    extract_style_from_text,
    load_style_reference,
    save_style_reference,
    search_novel_style,
)


DEFAULT_PROJECT = os.environ.get("NOVELBUDDY_PROJECT", "")


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NovelBuddy</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0c0e14;
      --bg-soft: #111520;
      --panel: #171b26;
      --panel-2: #1e2433;
      --line: #2b3347;
      --line-soft: #222938;
      --text: #e8ecf4;
      --muted: #8b95a8;
      --accent: #c9956a;
      --accent-hover: #dbaa7e;
      --accent2: #5b9fd4;
      --accent2-hover: #7ab5e0;
      --danger: #e07070;
      --success: #6bc9a0;
      --shadow: 0 12px 32px rgba(0, 0, 0, .35);
      --radius: 10px;
      --radius-sm: 7px;
      --sidebar-w: 300px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.55 "Segoe UI", "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      min-height: 100vh;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 50% at 10% -10%, rgba(201, 149, 106, .08), transparent 55%),
        radial-gradient(ellipse 60% 40% at 90% 0%, rgba(91, 159, 212, .06), transparent 50%);
      pointer-events: none;
      z-index: 0;
    }
    .app-header {
      height: 58px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(17, 21, 32, .92);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .brand-mark {
      width: 34px;
      height: 34px;
      border-radius: 9px;
      background: linear-gradient(135deg, var(--accent), #8b5e3c);
      display: grid;
      place-items: center;
      font-size: 17px;
      flex-shrink: 0;
      box-shadow: 0 4px 14px rgba(201, 149, 106, .25);
    }
    .brand-text h1 {
      font-size: 17px;
      margin: 0;
      font-weight: 700;
      letter-spacing: .02em;
    }
    .brand-text .subtitle {
      font-size: 11px;
      color: var(--muted);
      margin-top: 1px;
    }
    .header-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 11px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
    }
    .status-pill .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 8px rgba(107, 201, 160, .6);
    }
    .status-pill.loading .dot {
      background: var(--accent);
      animation: pulse 1.2s ease-in-out infinite;
    }
    .chapter-badge {
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(91, 159, 212, .12);
      color: var(--accent2);
      border: 1px solid rgba(91, 159, 212, .25);
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: .5; transform: scale(.85); }
    }
    main {
      display: grid;
      grid-template-columns: var(--sidebar-w) 1fr;
      min-height: calc(100vh - 58px);
      position: relative;
      z-index: 1;
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--bg-soft);
      padding: 14px 12px 18px;
      overflow-y: auto;
      max-height: calc(100vh - 58px);
    }
    .sidebar-section {
      background: var(--panel);
      border: 1px solid var(--line-soft);
      border-radius: var(--radius);
      padding: 12px;
      margin-bottom: 10px;
    }
    .sidebar-section-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--muted);
      margin: 0 0 10px;
    }
    section.content {
      padding: 18px 20px 24px;
      overflow: hidden;
    }
    label {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .04em;
      margin: 0 0 5px;
    }
    input, select, textarea, button {
      width: 100%;
      font: inherit;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--panel-2);
      color: var(--text);
      transition: border-color .15s, background .15s, box-shadow .15s;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: rgba(91, 159, 212, .55);
      box-shadow: 0 0 0 3px rgba(91, 159, 212, .12);
    }
    input, select { height: 34px; padding: 0 10px; }
    textarea { min-height: 120px; padding: 10px; resize: vertical; }
    button {
      height: 34px;
      cursor: pointer;
      background: linear-gradient(180deg, var(--accent), #a87a52);
      color: #1a1208;
      border-color: transparent;
      font-weight: 650;
    }
    button:hover { filter: brightness(1.06); }
    button:active { transform: translateY(1px); }
    button.secondary {
      background: var(--panel-2);
      color: var(--text);
      border-color: var(--line);
      font-weight: 550;
    }
    button.secondary:hover {
      border-color: rgba(91, 159, 212, .45);
      color: var(--accent2);
      background: rgba(91, 159, 212, .08);
    }
    button.warn {
      background: rgba(224, 112, 112, .1);
      color: var(--danger);
      border-color: rgba(224, 112, 112, .35);
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .field { margin-bottom: 8px; }
    .field:last-child { margin-bottom: 0; }
    details.action-group {
      border: 1px solid var(--line-soft);
      border-radius: var(--radius);
      background: var(--panel);
      margin-bottom: 8px;
      overflow: hidden;
    }
    details.action-group[open] { border-color: var(--line); }
    details.action-group > summary {
      list-style: none;
      cursor: pointer;
      padding: 10px 12px;
      font-size: 12px;
      font-weight: 650;
      color: var(--muted);
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
      transition: color .15s, background .15s;
    }
    details.action-group > summary::-webkit-details-marker { display: none; }
    details.action-group > summary::after {
      content: "▾";
      font-size: 11px;
      color: var(--muted);
      transition: transform .2s;
    }
    details.action-group:not([open]) > summary::after { transform: rotate(-90deg); }
    details.action-group > summary:hover { color: var(--text); background: var(--panel-2); }
    .actions {
      display: grid;
      gap: 6px;
      padding: 0 10px 10px;
    }
    .actions button { font-size: 13px; }
    .stats {
      display: grid;
      grid-template-columns: repeat(7, minmax(88px, 1fr));
      gap: 8px;
      margin-bottom: 14px;
    }
    .stat {
      background: var(--panel);
      border: 1px solid var(--line-soft);
      border-radius: var(--radius);
      padding: 11px 12px;
      position: relative;
      overflow: hidden;
    }
    .stat::before {
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 3px;
      background: var(--accent);
      opacity: .7;
    }
    .stat:nth-child(2)::before { background: var(--accent2); }
    .stat:nth-child(3)::before { background: #9b8fd4; }
    .stat:nth-child(4)::before { background: #d4a574; }
    .stat:nth-child(5)::before { background: #6bc9a0; }
    .stat:nth-child(6)::before { background: #e8a87c; }
    .stat:nth-child(7)::before { background: #7ec8e8; }
    .stat span {
      display: block;
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .stat strong {
      display: block;
      font-size: 21px;
      font-weight: 700;
      line-height: 1.1;
      color: var(--text);
    }
    .tabs-wrap {
      margin-bottom: 12px;
      overflow-x: auto;
      scrollbar-width: thin;
    }
    .tabs {
      display: flex;
      gap: 4px;
      min-width: max-content;
      padding: 3px;
      background: var(--panel);
      border: 1px solid var(--line-soft);
      border-radius: var(--radius);
    }
    .tab {
      width: auto;
      min-width: 0;
      padding: 0 14px;
      height: 32px;
      background: transparent;
      color: var(--muted);
      border: none;
      border-radius: 7px;
      font-weight: 550;
      font-size: 13px;
    }
    .tab:hover { color: var(--text); background: var(--panel-2); }
    .tab.active {
      background: rgba(91, 159, 212, .15);
      color: var(--accent2);
      box-shadow: inset 0 0 0 1px rgba(91, 159, 212, .25);
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line-soft);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .chapter-list, .quality-list {
      display: grid;
      gap: 8px;
      padding: 12px;
      background: var(--panel);
      min-height: 460px;
      max-height: calc(100vh - 250px);
      overflow: auto;
    }
    .chapter-link {
      display: block;
      width: 100%;
      height: auto;
      min-height: 40px;
      padding: 9px 12px;
      text-align: left;
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line-soft);
      border-radius: var(--radius-sm);
      font-weight: 500;
    }
    .chapter-link:hover {
      border-color: rgba(91, 159, 212, .4);
      color: var(--accent2);
      background: rgba(91, 159, 212, .06);
    }
    .quality-summary {
      border: 1px solid var(--line-soft);
      border-radius: var(--radius-sm);
      padding: 10px 12px;
      background: var(--panel-2);
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 12px;
    }
    .quality-item {
      border: 1px solid var(--line-soft);
      border-radius: var(--radius-sm);
      padding: 12px;
      background: var(--panel-2);
      display: grid;
      gap: 8px;
    }
    .quality-item.risk { border-color: rgba(224, 112, 112, .4); background: rgba(224, 112, 112, .05); }
    .quality-item.note { border-color: rgba(224, 176, 80, .35); background: rgba(224, 176, 80, .04); }
    .quality-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }
    .quality-title { font-weight: 650; }
    .quality-metrics { color: var(--muted); font-size: 12px; }
    .quality-warnings { color: var(--danger); font-size: 12px; }
    .quality-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .quality-actions button { width: auto; padding: 0 12px; }
    .quality-toolbar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .quality-toolbar button { width: auto; padding: 0 12px; height: 32px; font-size: 12px; }
    .quality-problems {
      margin: 0;
      padding-left: 18px;
      color: #f0a8a8;
      font-size: 12px;
      line-height: 1.55;
    }
    .quality-project-issues {
      border: 1px solid rgba(224, 112, 112, .3);
      border-radius: var(--radius-sm);
      padding: 12px;
      margin-bottom: 16px;
      background: rgba(224, 112, 112, .05);
    }
    .quality-project-header {
      font-weight: 650;
      color: var(--danger);
      margin-bottom: 10px;
      font-size: 14px;
    }
    .quality-issue-group {
      margin-bottom: 10px;
    }
    .quality-issue-title {
      font-weight: 600;
      color: var(--accent);
      margin-bottom: 4px;
      font-size: 13px;
    }
    .quality-issue-item {
      padding: 4px 8px;
      margin: 2px 0;
      font-size: 12px;
      color: var(--text);
      background: rgba(255,255,255,.03);
      border-radius: 4px;
    }
    .quality-problems li { margin: 2px 0; }
    .quality-ok { color: var(--success); font-size: 12px; }
    .character-badges { display: flex; gap: 6px; flex-wrap: wrap; }
    .character-badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
    }
    .foreshadow-hit { border-color: rgba(107, 201, 160, .45); }
    .foreshadow-risk { border-color: rgba(224, 112, 112, .4); }
    .field-hint {
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.45;
    }
    .style-toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
      font-size: 14px;
    }
    .style-mode-tabs {
      display: flex;
      gap: 8px;
      margin: 12px 0;
    }
    .style-tab.active {
      border-color: var(--accent);
      color: var(--accent);
    }
    .style-mode-panel {
      display: grid;
      gap: 8px;
      margin-bottom: 12px;
    }
    .graph-view {
      display: flex;
      flex-direction: column;
      gap: 0;
      padding: 0;
      background: var(--panel);
      min-height: calc(100vh - 250px);
      max-height: calc(100vh - 250px);
      overflow: hidden;
    }
    .graph-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line-soft);
      background: var(--panel-2);
    }
    .graph-toolbar .graph-stats {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
      margin-right: auto;
    }
    .graph-toolbar .graph-stats span { white-space: nowrap; }
    .graph-toolbar button,
    .graph-toolbar select,
    .graph-toolbar input {
      width: auto;
      height: 30px;
      font-size: 12px;
      padding: 0 10px;
    }
    .graph-toolbar input { min-width: 140px; }
    .graph-toolbar .graph-filter-group {
      display: inline-flex;
      gap: 4px;
      padding: 2px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--panel);
    }
    .graph-toolbar .graph-filter-group button {
      border: none;
      background: transparent;
      color: var(--muted);
      height: 26px;
    }
    .graph-toolbar .graph-filter-group button.active {
      background: rgba(91, 159, 212, .18);
      color: var(--text);
    }
    .graph-main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      min-height: 0;
      flex: 1;
    }
    .graph-stage {
      position: relative;
      min-height: 0;
      background:
        radial-gradient(circle at 50% 50%, rgba(91, 159, 212, .04), transparent 55%),
        var(--panel-2);
      border-right: 1px solid var(--line-soft);
      overflow: hidden;
      cursor: grab;
    }
    .graph-stage.panning { cursor: grabbing; }
    .graph-canvas {
      width: 100%;
      height: 100%;
      min-height: 420px;
      display: block;
      user-select: none;
    }
    .graph-line {
      stroke: #5a6a85;
      stroke-width: 1.5;
      stroke-opacity: .55;
      transition: stroke-opacity .15s, stroke-width .15s;
    }
    .graph-line.formal { stroke: var(--accent2); stroke-width: 2.5; stroke-opacity: .75; }
    .graph-line.hint { stroke-dasharray: 5 4; stroke-opacity: .45; }
    .graph-line.dim { stroke-opacity: .08; }
    .graph-line.highlight { stroke-opacity: 1; stroke-width: 3; }
    .graph-node { cursor: pointer; }
    .graph-node circle {
      stroke-width: 2;
      transition: stroke-width .15s, filter .15s;
    }
    .graph-node text {
      font-size: 11px;
      fill: var(--text);
      text-anchor: middle;
      pointer-events: none;
      paint-order: stroke;
      stroke: rgba(12, 14, 20, .85);
      stroke-width: 3px;
    }
    .graph-node.dim circle { opacity: .18; }
    .graph-node.dim text { opacity: .2; }
    .graph-node.selected circle { stroke-width: 3.5; filter: drop-shadow(0 0 6px rgba(201, 149, 106, .55)); }
    .graph-node.neighbor circle { filter: drop-shadow(0 0 4px rgba(91, 159, 212, .45)); }
    .graph-node.role-protagonist circle { fill: rgba(201, 149, 106, .22); stroke: var(--accent); }
    .graph-node.role-antagonist circle { fill: rgba(224, 112, 112, .18); stroke: var(--danger); }
    .graph-node.role-support circle { fill: rgba(107, 201, 160, .16); stroke: var(--success); }
    .graph-node.role-neutral circle { fill: rgba(91, 159, 212, .14); stroke: var(--accent2); }
    .graph-edge-label {
      font-size: 10px;
      fill: var(--muted);
      text-anchor: middle;
      pointer-events: none;
      opacity: 0;
      transition: opacity .15s;
    }
    .graph-edge-label.visible { opacity: 1; }
    .graph-sidebar {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 12px;
      overflow: auto;
      background: var(--panel);
    }
    .graph-sidebar h3 {
      margin: 0;
      font-size: 15px;
      color: var(--text);
    }
    .graph-sidebar .graph-side-meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .graph-sidebar .graph-side-section {
      border-top: 1px solid var(--line-soft);
      padding-top: 10px;
    }
    .graph-sidebar .graph-side-section h4 {
      margin: 0 0 8px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
      letter-spacing: .02em;
    }
    .graph-relation-item {
      padding: 8px 10px;
      margin-bottom: 6px;
      border: 1px solid var(--line-soft);
      border-radius: var(--radius-sm);
      background: var(--panel-2);
      font-size: 12px;
      line-height: 1.45;
      cursor: pointer;
    }
    .graph-relation-item:hover { border-color: var(--accent2); }
    .graph-relation-item .rel-kind {
      display: inline-block;
      margin-right: 6px;
      padding: 1px 6px;
      border-radius: 999px;
      font-size: 11px;
      color: var(--muted);
      border: 1px solid var(--line);
    }
    .graph-relation-item .rel-kind.formal { color: var(--accent2); border-color: rgba(91, 159, 212, .35); }
    .graph-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      padding: 8px 12px;
      border-top: 1px solid var(--line-soft);
      color: var(--muted);
      font-size: 11px;
      background: var(--panel-2);
    }
    .graph-legend span { display: inline-flex; align-items: center; gap: 6px; }
    .graph-legend i {
      display: inline-block;
      width: 18px;
      height: 0;
      border-top: 2px solid currentColor;
    }
    .graph-legend i.hint { border-top-style: dashed; }
    .graph-empty-hint {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-size: 13px;
      pointer-events: none;
    }
    .toolbar {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      padding: 11px 14px;
      border-bottom: 1px solid var(--line-soft);
      background: var(--panel-2);
    }
    .toolbar #title { font-weight: 650; font-size: 14px; }
    .toolbar button { width: auto; padding: 0 14px; height: 30px; font-size: 12px; }
    pre {
      margin: 0;
      padding: 16px 18px;
      min-height: 460px;
      max-height: calc(100vh - 250px);
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font: 13px/1.65 "Cascadia Code", Consolas, "Microsoft YaHei", monospace;
      background: var(--panel);
      color: #d4dae8;
    }
    .muted { color: var(--muted); }
    .notice {
      background: rgba(107, 201, 160, .08);
      color: #9ed9be;
      border: 1px solid rgba(107, 201, 160, .22);
      padding: 9px 11px;
      border-radius: var(--radius-sm);
      margin-top: 10px;
      font-size: 12px;
      line-height: 1.5;
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, .55);
      backdrop-filter: blur(4px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 20;
      padding: 18px;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      width: min(560px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: 0 24px 64px rgba(0, 0, 0, .5);
      overflow: hidden;
    }
    .modal header {
      position: static;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 48px;
      height: auto;
      padding: 10px 14px;
      background: var(--panel-2);
      border-bottom: 1px solid var(--line-soft);
    }
    .modal header h1 {
      flex: 1;
      min-width: 0;
      margin: 0;
      font-size: 15px;
      color: var(--text);
    }
    .modal-close {
      width: auto !important;
      flex-shrink: 0;
      height: 30px;
      padding: 0 12px;
      font-size: 12px;
      white-space: nowrap;
    }
    .modal-body { padding: 16px; }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      padding: 12px 16px;
      border-top: 1px solid var(--line-soft);
      background: var(--panel-2);
    }
    .modal-actions button { width: auto; padding: 0 14px; }
    .api-saved-status {
      margin-bottom: 12px;
      padding: 10px 12px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(91, 159, 212, .25);
      background: rgba(91, 159, 212, .08);
      color: #9ec5e8;
      font-size: 12px;
      line-height: 1.55;
      word-break: break-all;
    }
    .api-saved-status.empty {
      border-color: var(--line);
      background: var(--panel-2);
      color: var(--muted);
    }
    .api-test-status {
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .api-test-status.ok {
      border: 1px solid rgba(107, 201, 160, .35);
      background: rgba(107, 201, 160, .1);
      color: #9fd9bc;
    }
    .api-test-status.error {
      border: 1px solid rgba(224, 112, 112, .35);
      background: rgba(224, 112, 112, .1);
      color: #f0a8a8;
    }
    .api-test-status.pending {
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--muted);
    }
    .loading-overlay {
      position: fixed;
      inset: 0;
      background: rgba(12, 14, 20, .55);
      backdrop-filter: blur(3px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 15;
      flex-direction: column;
      gap: 14px;
    }
    .loading-overlay.show { display: flex; }
    .spinner {
      width: 36px;
      height: 36px;
      border: 3px solid var(--line);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin .8s linear infinite;
    }
    .loading-text { font-size: 13px; color: var(--muted); }
    @keyframes spin { to { transform: rotate(360deg); } }
    .toast {
      position: fixed;
      bottom: 22px;
      right: 22px;
      padding: 10px 16px;
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      color: var(--text);
      font-size: 13px;
      box-shadow: var(--shadow);
      z-index: 30;
      opacity: 0;
      transform: translateY(8px);
      transition: opacity .2s, transform .2s;
      pointer-events: none;
    }
    .toast.show { opacity: 1; transform: translateY(0); }
    ::-webkit-scrollbar { width: 7px; height: 7px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--line); border-radius: 99px; }
    ::-webkit-scrollbar-thumb:hover { background: #3d4a62; }
    @media (max-width: 960px) {
      main { grid-template-columns: 1fr; }
      aside {
        border-right: 0;
        border-bottom: 1px solid var(--line);
        max-height: none;
      }
      .stats { grid-template-columns: repeat(3, 1fr); }
      .header-meta .chapter-badge { display: none; }
    }
    @media (max-width: 560px) {
      .stats { grid-template-columns: repeat(2, 1fr); }
      section.content { padding: 14px; }
    }
    .help-btn {
      height: 28px; padding: 0 10px; border-radius: 6px;
      background: var(--panel-2); border: 1px solid var(--line);
      color: var(--muted); font-size: 12px; font-weight: 500;
      cursor: pointer; display: grid; place-items: center;
      transition: all .15s; white-space: nowrap;
    }
    .help-btn:hover { background: var(--accent); color: #fff; border-color: var(--accent); }
    .help-modal-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.6);
      z-index: 100; display: grid; place-items: center;
    }
    .help-modal {
      background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
      width: 560px; max-width: 92vw; max-height: 80vh; overflow-y: auto;
      box-shadow: var(--shadow); padding: 28px 32px;
    }
    .help-modal h2 { margin: 0 0 18px; font-size: 18px; }
    .help-modal h3 { margin: 16px 0 6px; font-size: 14px; color: var(--accent); }
    .help-modal p, .help-modal li { font-size: 13px; line-height: 1.7; color: var(--text); }
    .help-modal ul { margin: 4px 0 8px 18px; padding: 0; }
    .help-modal .close-help {
      float: right; background: none; border: none; color: var(--muted);
      font-size: 20px; cursor: pointer; line-height: 1;
    }
    .help-modal .close-help:hover { color: var(--text); }
  </style>
</head>
<body>
  <header class="app-header">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">📖</div>
      <div class="brand-text">
        <h1>NovelBuddy</h1>
        <div class="subtitle">本地小说辅助控制台</div>
      </div>
    </div>
    <div class="header-meta">
      <div class="status-pill" id="statusPill"><span class="dot"></span><span id="statusText">就绪</span></div>
      <div class="chapter-badge" id="chapterBadge">第 8 章</div>
      <button class="help-btn" onclick="openHelpModal()" title="功能说明">操作说明</button>
    </div>
  </header>
  <main>
    <aside>
      <div class="sidebar-section">
        <p class="sidebar-section-title">项目配置</p>
        <div class="field">
          <label>项目目录</label>
          <input id="project" placeholder="输入小说项目目录路径" />
        </div>
        <div class="actions">
          <button onclick="loadProject()">加载项目</button>
        </div>
        <div class="row">
          <div class="field">
            <label>章节号</label>
            <input id="chapter" type="number" value="8" min="1" />
          </div>
          <div class="field">
            <label>参考字数</label>
            <input id="words" type="number" value="3000" min="500" />
          </div>
        </div>
        <div class="field">
          <label>审查文件</label>
          <select id="auditFile"></select>
        </div>
        <div class="field">
          <label>检索关键词</label>
          <input id="searchQuery" placeholder="人物、物件、线索、地点" />
        </div>
        <div class="actions">
          <button class="secondary" onclick="searchProject()">全文检索</button>
        </div>
      </div>
      <details class="action-group" open>
        <summary>核心操作</summary>
        <div class="actions">
          <button onclick="scan()">扫描项目</button>
          <button class="secondary" onclick="goNextChapter()">切到下一章</button>
          <button onclick="generateNextChapter()">生成下一章</button>
          <button class="secondary" onclick="syncProjectState()">同步章节资料</button>
          <button class="secondary" onclick="refreshOutline()">刷新大纲解析</button>
          <button class="secondary" onclick="buildVectorIndex()">构建向量索引</button>
        </div>
      </details>
      <details class="action-group" open>
        <summary>写作准备</summary>
        <div class="actions">
          <button class="secondary" onclick="openApiModal()">API 设置</button>
          <button class="secondary" onclick="openRulesModal()">写作规则</button>
          <button class="secondary" onclick="openStyleModal()">文风引用</button>
          <button class="secondary" onclick="openOutlineModal()">编辑本章大纲</button>
          <button class="secondary" onclick="chapterPlan()">生成章节计划</button>
          <button class="secondary" onclick="preflightChapter()">生成前检查</button>
          <button class="secondary" onclick="foreshadowPlan()">伏笔回收计划</button>
          <button class="secondary" onclick="roadmap()">后续路线图</button>
        </div>
      </details>
      <details class="action-group">
        <summary>生成与审查</summary>
        <div class="actions">
          <button class="secondary" onclick="contextPack()">生成上下文</button>
          <button class="secondary" onclick="promptPack()">生成写作提示词</button>
          <button onclick="regenerateChapter()">重新生成章节</button>
          <button class="secondary" onclick="openReviewApiModal()">审查 API</button>
          <button class="secondary" onclick="auditChapter()">审查章节</button>
          <button class="secondary" onclick="reviseChapter()">审查并自动修改</button>
          <button onclick="rewriteChapter()">重写本章</button>
        </div>
      </details>
      <details class="action-group">
        <summary>数据与导出</summary>
        <div class="actions">
          <button class="secondary" onclick="diagnoseProject()">项目诊断</button>
          <button class="secondary" onclick="selfCheckProject()">自检报告</button>
          <button class="secondary" onclick="batchAnalyzeChapters()">批量分析章节</button>
          <button class="secondary" onclick="listBackups()">备份管理</button>
          <button class="secondary" onclick="searchProject()">全文检索</button>
          <button class="secondary" onclick="relationshipGraph()">生成关系图谱</button>
          <button class="secondary" onclick="exportProject()">导出资料</button>
          <button class="secondary" onclick="exportManuscript()">导出正文合集</button>
        </div>
      </details>
      <div class="notice">API Key 只发给本机服务，用来请求你填写的 API Base。不要把页面暴露到公网。</div>
    </aside>
    <section class="content">
      <div class="stats">
        <div class="stat"><span>人物</span><strong id="sCharacters">-</strong></div>
        <div class="stat"><span>大纲</span><strong id="sOutlines">-</strong></div>
        <div class="stat"><span>摘要</span><strong id="sSummaries">-</strong></div>
        <div class="stat"><span>伏笔</span><strong id="sForeshadows">-</strong></div>
        <div class="stat"><span>章节文件</span><strong id="sChapters">-</strong></div>
        <div class="stat"><span>已写到</span><strong id="sLatestChapter">-</strong></div>
        <div class="stat"><span>下一章</span><strong id="sNextChapter">-</strong></div>
      </div>
      <div class="tabs-wrap">
        <div class="tabs">
          <button class="tab active" data-tab="output" onclick="showTab('output')">输出</button>
          <button class="tab" data-tab="outlines" onclick="showTab('outlines')">大纲</button>
          <button class="tab" data-tab="chapters" onclick="showTab('chapters')">章节</button>
          <button class="tab" data-tab="characters" onclick="showTab('characters')">人物</button>
          <button class="tab" data-tab="relationships" onclick="showTab('relationships')">关系图谱</button>
          <button class="tab" data-tab="timeline" onclick="showTab('timeline')">时间线</button>
          <button class="tab" data-tab="quality" onclick="showTab('quality')">问题总览</button>
          <button class="tab" data-tab="foreshadows" onclick="showTab('foreshadows')">伏笔情况</button>
          <button class="tab" data-tab="organizations" onclick="showTab('organizations')">组织势力</button>
          <button class="tab" data-tab="world" onclick="showTab('world')">世界观</button>
        </div>
      </div>
      <div class="panel">
        <div class="toolbar">
          <span id="title">输出</span>
          <button class="secondary" onclick="copyOutput()">复制</button>
        </div>
        <pre id="output">点击「扫描项目」开始。</pre>
      </div>
    </section>
  </main>
  <div class="loading-overlay" id="loadingOverlay">
    <div class="spinner"></div>
    <div class="loading-text" id="loadingText">处理中…</div>
  </div>
  <div class="toast" id="toast"></div>
  <div class="modal-backdrop" id="apiModal" onclick="closeApiModalOnBackdrop(event)">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="apiModalTitle" onclick="event.stopPropagation()">
      <header>
        <h1 id="apiModalTitle">API 设置</h1>
        <button type="button" class="secondary modal-close" onclick="closeApiModal()">关闭</button>
      </header>
      <div class="modal-body">
        <div class="api-saved-status empty" id="apiSavedStatus">正在读取已保存配置…</div>
        <label>API Key</label>
        <input id="apiKey" type="password" autocomplete="off" placeholder="输入新 Key；已保存时留空则保持不变" />
        <label>API Base</label>
        <input id="apiBase" value="https://api.openai.com/v1" />
        <label>模型</label>
        <input id="model" value="gpt-4o-mini" />
        <label>生成温度（0-2）</label>
        <input id="apiTemperature" type="number" min="0" max="2" step="0.05" value="0.6" />
        <div class="notice">设置会保存在当前浏览器本地。API Key 不会写入小说项目文件。打开本页时会自动载入已保存配置。</div>
        <div class="api-test-status pending" id="apiTestStatus" hidden>尚未测试连接。</div>
      </div>
      <div class="modal-actions">
        <button type="button" class="secondary" onclick="closeApiModal()">取消</button>
        <button type="button" class="secondary" onclick="clearApiSettings()">清空</button>
        <button type="button" class="secondary" id="apiTestBtn" onclick="testApiConnection()">测试连接</button>
        <button type="button" onclick="saveApiSettings()">保存</button>
      </div>
    </div>
  </div>
  <div class="modal-backdrop" id="reviewApiModal" onclick="closeReviewApiModalOnBackdrop(event)">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="reviewApiModalTitle" onclick="event.stopPropagation()">
      <header>
        <h1 id="reviewApiModalTitle">审查 API</h1>
        <button type="button" class="secondary modal-close" onclick="closeReviewApiModal()">关闭</button>
      </header>
      <div class="modal-body">
        <div class="api-saved-status empty" id="reviewApiSavedStatus">未单独配置时将使用「API 设置」中的默认接口。</div>
        <label>API Key</label>
        <input id="reviewApiKey" type="password" autocomplete="off" placeholder="留空则使用默认 API Key" />
        <label>API Base</label>
        <input id="reviewApiBase" placeholder="留空则使用默认 API Base" />
        <label>模型</label>
        <input id="reviewModel" placeholder="留空则使用默认模型" />
        <label>温度（0-2，重写时使用）</label>
        <input id="reviewApiTemperature" type="number" min="0" max="2" step="0.05" placeholder="留空则使用默认温度" />
        <div class="notice">仅用于「审查并自动修改」「重写本章」。全部留空并清空保存时，回退到默认 API 设置。</div>
        <div class="api-test-status pending" id="reviewApiTestStatus" hidden>尚未测试连接。</div>
      </div>
      <div class="modal-actions">
        <button type="button" class="secondary" onclick="closeReviewApiModal()">取消</button>
        <button type="button" class="secondary" onclick="clearReviewApiSettings()">清空</button>
        <button type="button" class="secondary" id="reviewApiTestBtn" onclick="testReviewApiConnection()">测试连接</button>
        <button type="button" onclick="saveReviewApiSettings()">保存</button>
      </div>
    </div>
  </div>
  <div class="modal-backdrop" id="outlineModal" onclick="closeOutlineModalOnBackdrop(event)">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="outlineModalTitle" onclick="event.stopPropagation()">
      <header>
        <h1 id="outlineModalTitle">编辑本章大纲</h1>
        <button type="button" class="secondary modal-close" onclick="closeOutlineModal()">关闭</button>
      </header>
      <div class="modal-body">
        <label>章节号</label>
        <input id="outlineChapter" type="number" min="1" />
        <label>标题</label>
        <input id="outlineTitle" />
        <label>大纲内容</label>
        <textarea id="outlineContent" style="width:100%; min-height:260px; resize:vertical;"></textarea>
        <div class="notice">保存会先备份原大纲文件，再写入当前项目的大纲数据。</div>
      </div>
      <div class="modal-actions">
        <button class="secondary" onclick="closeOutlineModal()">取消</button>
        <button onclick="saveCurrentOutline()">保存大纲</button>
      </div>
    </div>
  </div>
  <div class="modal-backdrop" id="entityModal" onclick="closeEntityModalOnBackdrop(event)">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="entityModalTitle" onclick="event.stopPropagation()">
      <header>
        <h1 id="entityModalTitle">编辑资料</h1>
        <button type="button" class="secondary modal-close" onclick="closeEntityModal()">关闭</button>
      </header>
      <div class="modal-body">
        <input type="hidden" id="entityType" />
        <input type="hidden" id="entityId" />
        <div id="entityFormFields"></div>
        <div class="notice">保存会写入 `.novel-assistant`，并自动备份原文件。</div>
      </div>
      <div class="modal-actions">
        <button type="button" class="secondary" onclick="closeEntityModal()">取消</button>
        <button type="button" class="secondary" id="entityDeleteBtn" onclick="deleteCurrentEntity()">删除</button>
        <button type="button" onclick="saveCurrentEntity()">保存</button>
      </div>
    </div>
  </div>
  <div class="modal-backdrop" id="styleModal" onclick="closeStyleModalOnBackdrop(event)">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="styleModalTitle" onclick="event.stopPropagation()">
      <header>
        <h1 id="styleModalTitle">文风引用</h1>
        <button type="button" class="secondary modal-close" onclick="closeStyleModal()">关闭</button>
      </header>
      <div class="modal-body">
        <label class="style-toggle">
          <input type="checkbox" id="styleEnabled" />
          启用文风引用（生成、重写、自动修改时带入）
        </label>
        <div class="quality-metrics" id="styleMeta">尚未配置文风。</div>
        <div class="style-mode-tabs">
          <button type="button" class="secondary style-tab active" data-style-mode="upload" onclick="switchStyleMode('upload')">上传样本</button>
          <button type="button" class="secondary style-tab" data-style-mode="search" onclick="switchStyleMode('search')">联网搜索</button>
        </div>
        <div id="styleModeUpload" class="style-mode-panel">
          <label>作品名称（可选）</label>
          <input id="styleUploadName" type="text" placeholder="例如：诡秘之主" />
          <label>上传小说文件或粘贴正文样本</label>
          <input id="styleFileInput" type="file" accept=".txt,.md,.markdown" />
          <textarea id="styleSampleText" style="width:100%; min-height:180px; resize:vertical;" placeholder="粘贴 500 字以上的正文片段，或上传 txt/md 文件。系统会分析叙事节奏、句式、描写风格等特征。"></textarea>
          <button type="button" class="secondary" onclick="extractStyleFromSample()">分析样本文风</button>
        </div>
        <div id="styleModeSearch" class="style-mode-panel" hidden>
          <label>小说名称</label>
          <input id="styleSearchName" type="text" placeholder="例如：道诡异仙" />
          <div class="notice">会联网检索该作品的文风讨论与评论，再由 AI 提炼成可执行的文风指南。</div>
          <button type="button" class="secondary" onclick="searchStyleByName()">搜索并提炼文风</button>
        </div>
        <label>文风指南（可手动微调）</label>
        <textarea id="styleGuideText" style="width:100%; min-height:220px; resize:vertical;" placeholder="分析或搜索后会自动填入。你也可以直接手写文风要求。"></textarea>
      </div>
      <div class="modal-actions">
        <button type="button" class="secondary" onclick="closeStyleModal()">取消</button>
        <button type="button" class="secondary" onclick="clearStyleReference()">清空</button>
        <button type="button" onclick="saveStyleReference()">保存</button>
      </div>
    </div>
  </div>
  <div class="modal-backdrop" id="rulesModal" onclick="closeRulesModalOnBackdrop(event)">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="rulesModalTitle" onclick="event.stopPropagation()">
      <header>
        <h1 id="rulesModalTitle">写作规则</h1>
        <button type="button" class="secondary modal-close" onclick="closeRulesModal()">关闭</button>
      </header>
      <div class="modal-body">
        <label>自定义规则</label>
        <textarea id="writingRules" style="width:100%; min-height:260px; resize:vertical;" placeholder="例如：禁止心理旁白；对话要有停顿；章节正文不要空行；不要使用 Markdown 加粗符号。"></textarea>
        <div class="notice">规则保存在当前浏览器本地，会自动加入生成提示词和自动修改提示词。</div>
      </div>
      <div class="modal-actions">
        <button type="button" class="secondary" onclick="closeRulesModal()">取消</button>
        <button type="button" class="secondary" onclick="clearWritingRules()">清空</button>
        <button type="button" onclick="saveWritingRules()">保存</button>
      </div>
    </div>
  </div>
  <script>
    let state = {
      scan: null,
      output: "",
      copyText: "",
      outlinesText: "",
      chaptersText: "",
      charactersText: "",
      relationshipsText: "",
      organizationsText: "",
      styleReference: null,
      worldText: "",
      relationshipGraphData: null,
      graphScope: "window",
      graphEdgeFilter: "all",
      graphSimHandle: null,
      graphInteractionAbort: null,
      timelineText: "",
      qualityText: "",
      foreshadowsText: "",
      chapters: [],
      latestChapter: 0,
      nextChapter: 1
    };

    function getSavedApiSettings() {
      return JSON.parse(localStorage.getItem("novelbuddy.api") || "{}");
    }

    function getSavedReviewApiSettings() {
      return JSON.parse(localStorage.getItem("novelbuddy.reviewApi") || "{}");
    }

    function isReviewApiConfigured(saved = getSavedReviewApiSettings()) {
      return !!(saved.apiKey || saved.apiBase || saved.model || saved.temperature != null);
    }

    function resolveReviewApiSettings() {
      const saved = getSavedReviewApiSettings();
      const keyInput = document.getElementById("reviewApiKey")?.value.trim() || "";
      const baseInput = document.getElementById("reviewApiBase")?.value.trim() || "";
      const modelInput = document.getElementById("reviewModel")?.value.trim() || "";
      const tempRaw = document.getElementById("reviewApiTemperature")?.value;
      const tempInput = tempRaw === "" || tempRaw == null ? null : Number(tempRaw);
      return {
        apiKey: keyInput || saved.apiKey || "",
        apiBase: baseInput || saved.apiBase || "",
        model: modelInput || saved.model || "",
        temperature: tempInput ?? saved.temperature ?? null,
      };
    }

    function reviewApiFields() {
      const saved = getSavedReviewApiSettings();
      if (!isReviewApiConfigured(saved)) return {};
      return {
        reviewApiKey: saved.apiKey || "",
        reviewApiBase: saved.apiBase || "",
        reviewModel: saved.model || "",
        reviewTemperature: saved.temperature ?? "",
      };
    }

    function reviewPayload(extra = {}) {
      return { ...payload(extra), ...reviewApiFields() };
    }

    function reviewApiLabel() {
      const saved = getSavedReviewApiSettings();
      if (!isReviewApiConfigured(saved)) {
        const def = getSavedApiSettings();
        return def.model ? `默认 API（${def.model}）` : "默认 API";
      }
      const model = saved.model || getSavedApiSettings().model || "未指定模型";
      return `审查 API（${model}）`;
    }

    function maskApiKey(key) {
      const value = String(key || "").trim();
      if (!value) return "未设置";
      if (value.length <= 8) return "••••••••";
      return `${value.slice(0, 3)}••••${value.slice(-4)}`;
    }

    function resolveApiSettings() {
      const saved = getSavedApiSettings();
      const apiKeyInput = document.getElementById("apiKey").value.trim();
      return {
        apiKey: apiKeyInput || saved.apiKey || "",
        apiBase: document.getElementById("apiBase").value.trim() || saved.apiBase || "https://api.openai.com/v1",
        model: document.getElementById("model").value.trim() || saved.model || "gpt-4o-mini",
        temperature: Number(document.getElementById("apiTemperature")?.value || saved.temperature || 0.6),
      };
    }

    function payload(extra = {}) {
      saveWorkspaceSettings();
      const api = resolveApiSettings();
      return {
        project: document.getElementById("project").value,
        chapter: Number(document.getElementById("chapter").value),
        words: Number(document.getElementById("words").value),
        apiKey: api.apiKey,
        apiBase: api.apiBase,
        model: api.model,
        temperature: api.temperature,
        writingRules: document.getElementById("writingRules").value,
        file: document.getElementById("auditFile").value,
        ...extra
      };
    }

    function loadWorkspaceSettings() {
      const saved = JSON.parse(localStorage.getItem("novelbuddy.workspace") || "{}");
      if (saved.project) document.getElementById("project").value = saved.project;
      if (saved.chapter) document.getElementById("chapter").value = saved.chapter;
      if (saved.words) document.getElementById("words").value = saved.words;
      if (saved.searchQuery) document.getElementById("searchQuery").value = saved.searchQuery;
    }

    function saveWorkspaceSettings() {
      localStorage.setItem("novelbuddy.workspace", JSON.stringify({
        project: document.getElementById("project").value,
        chapter: document.getElementById("chapter").value,
        words: document.getElementById("words").value,
        searchQuery: document.getElementById("searchQuery").value
      }));
    }

    function selectChapterFileByNumber() {
      const chapter = Number(document.getElementById("chapter").value);
      const select = document.getElementById("auditFile");
      const match = state.chapters.find(ch => Number(ch.number) === chapter);
      if (match) {
        select.value = match.path;
      } else {
        select.value = "";
      }
      return match;
    }

    function syncChapterFromSelectedFile() {
      const file = document.getElementById("auditFile").value || "";
      const chapter = file.match(/第\s*0*(\d+)\s*章/);
      if (chapter) document.getElementById("chapter").value = chapter[1];
      return chapter ? Number(chapter[1]) : null;
    }

    function goNextChapter() {
      const next = Number(state.nextChapter || 1);
      document.getElementById("chapter").value = next;
      selectChapterFileByNumber();
      updateHeaderMeta();
      setOutput(`已切到第${next}章。可以先生成章节计划，再生成正文。`, `第${next}章`);
    }

    async function generateNextChapter() {
      const next = Number(state.nextChapter || 1);
      document.getElementById("chapter").value = next;
      selectChapterFileByNumber();
      updateHeaderMeta();
      await regenerateChapter();
    }

    function refreshApiModalStatus() {
      const saved = getSavedApiSettings();
      const status = document.getElementById("apiSavedStatus");
      if (!status) return;
      if (saved.apiKey || saved.apiBase || saved.model) {
        const parts = [];
        if (saved.apiKey) parts.push(`Key ${maskApiKey(saved.apiKey)}`);
        if (saved.apiBase) parts.push(`Base ${saved.apiBase}`);
        if (saved.model) parts.push(`Model ${saved.model}`);
        status.textContent = `当前已保存：${parts.join("  ·  ")}`;
        status.classList.remove("empty");
      } else {
        status.textContent = "尚未保存 API 配置。留空 Key 时将尝试使用环境变量 NOVELBUDDY_API_KEY。";
        status.classList.add("empty");
      }
    }

    function clearApiTestStatus() {
      const status = document.getElementById("apiTestStatus");
      if (!status) return;
      status.hidden = true;
      status.textContent = "";
      status.className = "api-test-status";
    }

    function setApiTestStatus(kind, text) {
      const status = document.getElementById("apiTestStatus");
      if (!status) return;
      status.hidden = false;
      status.className = `api-test-status ${kind}`;
      status.textContent = text;
    }

    function loadApiSettings() {
      const saved = getSavedApiSettings();
      document.getElementById("apiBase").value = saved.apiBase || "https://api.openai.com/v1";
      document.getElementById("model").value = saved.model || "gpt-4o-mini";
      document.getElementById("apiTemperature").value = saved.temperature ?? 0.6;
      document.getElementById("apiKey").value = "";
      document.getElementById("apiKey").placeholder = saved.apiKey
        ? `已保存 ${maskApiKey(saved.apiKey)}，留空则保持不变`
        : "输入 API Key；留空则使用 NOVELBUDDY_API_KEY";
      clearApiTestStatus();
      refreshApiModalStatus();
    }

    async function testApiConnection() {
      const btn = document.getElementById("apiTestBtn");
      const api = resolveApiSettings();
      if (!api.apiKey) {
        setApiTestStatus("error", "请先填写 API Key，或先保存 Key 后再测试。");
        showToast("缺少 API Key");
        return;
      }
      btn.disabled = true;
      setApiTestStatus("pending", `正在测试连接…\nBase：${api.apiBase}\nModel：${api.model}`);
      try {
        const res = await fetch("/api/test-connection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project: document.getElementById("project").value,
            apiKey: api.apiKey,
            apiBase: api.apiBase,
            model: api.model,
          }),
        });
        const data = await res.json();
        if (!res.ok || data.error) {
          throw new Error(data.error || "连接失败");
        }
        if (!data.ok) {
          throw new Error(data.error || data.message || "连接失败");
        }
        const lines = [
          `连接成功（${data.latencyMs}ms）`,
          `Base：${data.apiBase}`,
          `Model：${data.model}`,
        ];
        if (data.reply) lines.push(`模型回复：${data.reply}`);
        setApiTestStatus("ok", lines.join("\n"));
        showToast("API 连接测试成功");
      } catch (err) {
        setApiTestStatus("error", `连接失败：${err.message || err}`);
        showToast("API 连接测试失败");
      } finally {
        btn.disabled = false;
      }
    }

    function saveApiSettings() {
      const saved = getSavedApiSettings();
      const apiKeyInput = document.getElementById("apiKey").value.trim();
      const next = {
        apiKey: apiKeyInput || saved.apiKey || "",
        apiBase: document.getElementById("apiBase").value.trim() || "https://api.openai.com/v1",
        model: document.getElementById("model").value.trim() || "gpt-4o-mini",
        temperature: Number(document.getElementById("apiTemperature").value || 0.6),
      };
      localStorage.setItem("novelbuddy.api", JSON.stringify(next));
      loadApiSettings();
      closeApiModal();
      setOutput(
        `API 设置已保存。\nKey：${maskApiKey(next.apiKey)}\nBase：${next.apiBase}\nModel：${next.model}`,
        "API 设置"
      );
    }

    function clearApiSettings() {
      document.getElementById("apiKey").value = "";
      document.getElementById("apiBase").value = "https://api.openai.com/v1";
      document.getElementById("model").value = "gpt-4o-mini";
      document.getElementById("apiTemperature").value = 0.6;
      localStorage.removeItem("novelbuddy.api");
      loadApiSettings();
    }

    function openHelpModal() {
      let overlay = document.getElementById("helpModalOverlay");
      if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "helpModalOverlay";
        overlay.className = "help-modal-overlay";
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
        overlay.innerHTML = `
          <div class="help-modal">
            <button class="close-help" onclick="document.getElementById('helpModalOverlay').remove()">&times;</button>
            <h2>NovelBuddy 功能说明</h2>

            <h3>项目配置</h3>
            <ul>
              <li><b>项目目录</b> — 输入小说项目根目录路径，系统会自动查找大纲文件</li>
              <li><b>加载项目</b> — 必须在项目根目录找到名称含「大纲」的 .md 文件</li>
            </ul>

            <h3>核心操作</h3>
            <ul>
              <li><b>扫描项目</b> — 扫描项目目录，加载人物、关系、伏笔、大纲、世界观等数据</li>
              <li><b>切到下一章</b> — 将当前章节切换到下一章</li>
              <li><b>生成下一章</b> — 切到下一章并直接生成正文（含生成前检查）</li>
              <li><b>同步章节资料</b> — 从已写章节中提取人物、关系、伏笔等信息同步到项目数据</li>
              <li><b>刷新大纲解析</b> — 调用AI从大纲 .md 文件中自动提取人物、关系、组织势力、世界观</li>
              <li><b>构建向量索引</b> — 将章节正文切片并生成向量嵌入，用于生成时自动检索相关前文片段</li>
            </ul>

            <h3>写作准备</h3>
            <ul>
              <li><b>API 设置</b> — 配置 OpenAI 兼容 API 的 Key、Base URL、模型</li>
              <li><b>写作规则</b> — 设定写作时的风格、禁忌、偏好规则</li>
              <li><b>文风引用</b> — 导入参考文风，生成时自动带入风格特征</li>
              <li><b>编辑本章大纲</b> — 编辑当前章节的大纲内容</li>
              <li><b>生成章节计划</b> — 根据大纲和上下文生成详细的章节写作计划</li>
              <li><b>生成前检查</b> — 检查大纲、伏笔、人物等是否就绪，有无阻断项</li>
              <li><b>伏笔回收计划</b> — 分析过期伏笔，生成回收建议</li>
              <li><b>后续路线图</b> — 基于当前进度生成后续章节的剧情路线图</li>
            </ul>

            <h3>生成与审查</h3>
            <ul>
              <li><b>生成上下文</b> — 汇总当前章节需要的所有上下文信息</li>
              <li><b>生成写作提示词</b> — 生成完整的章节写作提示词</li>
              <li><b>重新生成章节</b> — 调用AI生成当前章节正文（已存在则覆盖）</li>
              <li><b>审查章节</b> — 对章节正文进行质量审查</li>
              <li><b>审查并自动修改</b> — 审查后自动修复发现的问题</li>
              <li><b>重写本章</b> — 基于审查意见重写章节</li>
            </ul>

            <h3>数据与导出</h3>
            <ul>
              <li><b>项目诊断</b> — 检查项目数据完整性和一致性</li>
              <li><b>自检报告</b> — 生成项目整体质量报告</li>
              <li><b>批量分析章节</b> — 批量分析所有已写章节</li>
              <li><b>备份管理</b> — 查看和恢复项目备份</li>
              <li><b>全文检索</b> — 在项目全文中搜索关键词</li>
              <li><b>生成关系图谱</b> — 可视化人物关系网络</li>
              <li><b>导出资料</b> — 导出项目所有资料为文本</li>
              <li><b>导出正文合集</b> — 导出所有已写章节的正文合集</li>
            </ul>
          </div>`;
        document.body.appendChild(overlay);
      }
    }

    function openApiModal() {
      loadApiSettings();
      document.getElementById("apiModal").classList.add("open");
      if (getSavedApiSettings().apiKey) {
        document.getElementById("apiBase").focus();
      } else {
        document.getElementById("apiKey").focus();
      }
    }

    function closeApiModal() {
      document.getElementById("apiModal").classList.remove("open");
    }

    function closeApiModalOnBackdrop(event) {
      if (event.target.id === "apiModal") closeApiModal();
    }

    function refreshReviewApiModalStatus() {
      const saved = getSavedReviewApiSettings();
      const status = document.getElementById("reviewApiSavedStatus");
      if (!status) return;
      if (!isReviewApiConfigured(saved)) {
        status.textContent = "未单独配置，将使用「API 设置」中的默认接口。";
        status.className = "api-saved-status empty";
        return;
      }
      const parts = [];
      if (saved.apiKey) parts.push(`Key ${maskApiKey(saved.apiKey)}`);
      if (saved.apiBase) parts.push(`Base ${saved.apiBase}`);
      if (saved.model) parts.push(`Model ${saved.model}`);
      if (saved.temperature != null) parts.push(`Temp ${saved.temperature}`);
      status.textContent = `审查 API 已配置：${parts.join("  ·  ")}`;
      status.className = "api-saved-status";
    }

    function clearReviewApiTestStatus() {
      const status = document.getElementById("reviewApiTestStatus");
      if (status) status.hidden = true;
    }

    function setReviewApiTestStatus(kind, text) {
      const status = document.getElementById("reviewApiTestStatus");
      if (!status) return;
      status.hidden = false;
      status.className = `api-test-status ${kind}`;
      status.textContent = text;
    }

    function loadReviewApiSettings() {
      const saved = getSavedReviewApiSettings();
      document.getElementById("reviewApiBase").value = saved.apiBase || "";
      document.getElementById("reviewModel").value = saved.model || "";
      document.getElementById("reviewApiTemperature").value = saved.temperature ?? "";
      document.getElementById("reviewApiKey").value = "";
      document.getElementById("reviewApiKey").placeholder = saved.apiKey
        ? `已保存 ${maskApiKey(saved.apiKey)}，留空则保持不变`
        : "留空则使用默认 API Key";
      clearReviewApiTestStatus();
      refreshReviewApiModalStatus();
    }

    async function testReviewApiConnection() {
      const btn = document.getElementById("reviewApiTestBtn");
      const review = resolveReviewApiSettings();
      const fallback = resolveApiSettings();
      const api = {
        apiKey: review.apiKey || fallback.apiKey,
        apiBase: review.apiBase || fallback.apiBase,
        apiModel: review.model || fallback.model,
      };
      if (!api.apiKey) {
        setReviewApiTestStatus("error", "请先填写审查 API Key，或先在默认 API 设置中保存 Key。");
        showToast("缺少 API Key");
        return;
      }
      btn.disabled = true;
      setReviewApiTestStatus("pending", `正在测试审查 API…\nBase：${api.apiBase}\nModel：${api.apiModel}`);
      try {
        const body = {
          project: document.getElementById("project").value,
          apiKey: fallback.apiKey,
          apiBase: fallback.apiBase,
          model: fallback.model,
        };
        if (isReviewApiConfigured() || review.apiKey || review.apiBase || review.model) {
          body.reviewApiKey = review.apiKey || "";
          body.reviewApiBase = review.apiBase || "";
          body.reviewModel = review.model || "";
        }
        const res = await fetch("/api/test-connection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || "连接失败");
        if (!data.ok) throw new Error(data.error || data.message || "连接失败");
        const lines = [
          `连接成功（${data.latencyMs}ms）`,
          `Base：${data.apiBase}`,
          `Model：${data.model}`,
        ];
        if (data.reply) lines.push(`模型回复：${data.reply}`);
        setReviewApiTestStatus("ok", lines.join("\n"));
        showToast("审查 API 连接测试成功");
      } catch (err) {
        setReviewApiTestStatus("error", `连接失败：${err.message || err}`);
        showToast("审查 API 连接测试失败");
      } finally {
        btn.disabled = false;
      }
    }

    function saveReviewApiSettings() {
      const saved = getSavedReviewApiSettings();
      const keyInput = document.getElementById("reviewApiKey").value.trim();
      const baseInput = document.getElementById("reviewApiBase").value.trim();
      const modelInput = document.getElementById("reviewModel").value.trim();
      const tempRaw = document.getElementById("reviewApiTemperature").value;
      const next = {
        apiKey: keyInput || saved.apiKey || "",
        apiBase: baseInput,
        model: modelInput,
        temperature: tempRaw === "" ? null : Number(tempRaw),
      };
      if (!next.apiKey && !next.apiBase && !next.model && next.temperature == null) {
        localStorage.removeItem("novelbuddy.reviewApi");
      } else {
        localStorage.setItem("novelbuddy.reviewApi", JSON.stringify(next));
      }
      loadReviewApiSettings();
      closeReviewApiModal();
      showToast(isReviewApiConfigured() ? "审查 API 已保存" : "已清空审查 API，将使用默认接口");
    }

    function clearReviewApiSettings() {
      document.getElementById("reviewApiKey").value = "";
      document.getElementById("reviewApiBase").value = "";
      document.getElementById("reviewModel").value = "";
      document.getElementById("reviewApiTemperature").value = "";
      localStorage.removeItem("novelbuddy.reviewApi");
      loadReviewApiSettings();
    }

    function openReviewApiModal() {
      loadReviewApiSettings();
      document.getElementById("reviewApiModal").classList.add("open");
      document.getElementById("reviewApiBase").focus();
    }

    function closeReviewApiModal() {
      document.getElementById("reviewApiModal").classList.remove("open");
    }

    function closeReviewApiModalOnBackdrop(event) {
      if (event.target.id === "reviewApiModal") closeReviewApiModal();
    }

    function loadWritingRules() {
      document.getElementById("writingRules").value = localStorage.getItem("novelbuddy.rules") || "";
    }

    function saveWritingRules() {
      localStorage.setItem("novelbuddy.rules", document.getElementById("writingRules").value);
      closeRulesModal();
      setOutput("写作规则已保存。之后生成提示词、生成正文、自动修改都会带上这些规则。", "写作规则");
    }

    function clearWritingRules() {
      document.getElementById("writingRules").value = "";
      localStorage.removeItem("novelbuddy.rules");
    }

    function openRulesModal() {
      document.getElementById("rulesModal").classList.add("open");
      document.getElementById("writingRules").focus();
    }

    function closeRulesModal() {
      document.getElementById("rulesModal").classList.remove("open");
    }

    function closeRulesModalOnBackdrop(event) {
      if (event.target.id === "rulesModal") closeRulesModal();
    }

    function switchStyleMode(mode) {
      document.querySelectorAll(".style-tab").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-style-mode") === mode);
      });
      document.getElementById("styleModeUpload").hidden = mode !== "upload";
      document.getElementById("styleModeSearch").hidden = mode !== "search";
    }

    function renderStyleMeta(ref) {
      const meta = document.getElementById("styleMeta");
      if (!ref || !ref.styleGuide) {
        meta.textContent = "尚未配置文风。上传样本或联网搜索后保存。";
        return;
      }
      const sourceMap = { upload: "上传样本", search: "联网搜索", manual: "手动编辑" };
      const source = sourceMap[ref.source] || "文风引用";
      const name = ref.novelName ? `《${ref.novelName}》` : "";
      const status = ref.enabled ? "已启用" : "未启用";
      const updated = ref.updatedAt ? `｜更新于 ${ref.updatedAt}` : "";
      meta.textContent = `${status}｜来源：${source}${name ? "｜" + name : ""}｜指南约 ${ref.styleGuide.length} 字${updated}`;
    }

    function applyStyleReference(ref) {
      ref = ref || {};
      document.getElementById("styleEnabled").checked = !!ref.enabled;
      document.getElementById("styleGuideText").value = ref.styleGuide || "";
      document.getElementById("styleUploadName").value = ref.novelName || "";
      document.getElementById("styleSearchName").value = ref.novelName || "";
      renderStyleMeta(ref);
    }

    async function loadStyleReference() {
      try {
        const data = await post("/api/style-reference", payload());
        state.styleReference = data.reference || {};
        applyStyleReference(state.styleReference);
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    function openStyleModal() {
      switchStyleMode("upload");
      loadStyleReference();
      document.getElementById("styleModal").classList.add("open");
      document.getElementById("styleSampleText").focus();
    }

    function closeStyleModal() {
      document.getElementById("styleModal").classList.remove("open");
    }

    function closeStyleModalOnBackdrop(event) {
      if (event.target.id === "styleModal") closeStyleModal();
    }

    document.getElementById("styleFileInput").addEventListener("change", event => {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        document.getElementById("styleSampleText").value = String(reader.result || "");
        if (!document.getElementById("styleUploadName").value.trim()) {
          const base = file.name.replace(/\.[^.]+$/, "");
          document.getElementById("styleUploadName").value = base;
        }
      };
      reader.readAsText(file, "UTF-8");
    });

    async function extractStyleFromSample() {
      const sampleText = document.getElementById("styleSampleText").value.trim();
      if (!sampleText) {
        showToast("请先上传文件或粘贴正文样本");
        return;
      }
      showToast("正在分析样本文风…");
      try {
        const data = await post("/api/style-reference/extract", payload({
          sampleText,
          novelName: document.getElementById("styleUploadName").value.trim(),
        }));
        applyStyleReference(data.reference);
        showToast("文风分析完成，请确认后保存");
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    async function searchStyleByName() {
      const novelName = document.getElementById("styleSearchName").value.trim();
      if (!novelName) {
        showToast("请填写小说名称");
        return;
      }
      showToast(`正在联网搜索《${novelName}》文风…`);
      try {
        const data = await post("/api/style-reference/search", payload({ novelName }));
        applyStyleReference(data.reference);
        showToast("文风提炼完成，请确认后保存");
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    async function saveStyleReference() {
      const styleGuide = document.getElementById("styleGuideText").value.trim();
      if (!styleGuide) {
        showToast("文风指南不能为空");
        return;
      }
      const uploadName = document.getElementById("styleUploadName").value.trim();
      const searchName = document.getElementById("styleSearchName").value.trim();
      const source = searchName && !uploadName ? "search" : (uploadName ? "upload" : "manual");
      try {
        const data = await post("/api/style-reference/save", payload({
          enabled: document.getElementById("styleEnabled").checked,
          styleGuide,
          novelName: searchName || uploadName,
          source,
        }));
        state.styleReference = data.reference || {};
        applyStyleReference(state.styleReference);
        closeStyleModal();
        showToast("文风引用已保存到项目");
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    async function clearStyleReference() {
      if (!confirm("确定清空文风引用吗？")) return;
      try {
        await post("/api/style-reference/clear", payload());
        state.styleReference = {};
        applyStyleReference({});
        showToast("文风引用已清空");
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    function currentOutline() {
      const chapter = Number(document.getElementById("chapter").value);
      return (state.scan?.outlines || []).find(o => Number(o.chapterNumber) === chapter) || null;
    }

    function openOutlineModal() {
      const chapter = Number(document.getElementById("chapter").value) || 1;
      const outline = currentOutline();
      document.getElementById("outlineChapter").value = chapter;
      document.getElementById("outlineTitle").value = outline?.title || "";
      document.getElementById("outlineContent").value = outline?.content || "";
      document.getElementById("outlineModal").classList.add("open");
      document.getElementById("outlineTitle").focus();
    }

    function closeOutlineModal() {
      document.getElementById("outlineModal").classList.remove("open");
    }

    function closeOutlineModalOnBackdrop(event) {
      if (event.target.id === "outlineModal") closeOutlineModal();
    }

    async function saveCurrentOutline() {
      const chapter = Number(document.getElementById("outlineChapter").value) || Number(document.getElementById("chapter").value) || 1;
      const title = document.getElementById("outlineTitle").value.trim();
      const content = document.getElementById("outlineContent").value.trim();
      if (!content) {
        setOutput("大纲内容不能为空。", "保存大纲");
        return;
      }
      try {
        const data = await post("/api/outline", payload({ chapter, outlineTitle: title, outlineContent: content }));
        closeOutlineModal();
        document.getElementById("chapter").value = chapter;
        await scan();
        setOutput(`已保存第${chapter}章大纲。\n写入：${data.path}\n备份：${data.backupPath || "本次为新文件，无旧备份"}\n\n${data.outline.title}\n${data.outline.content}`, "保存大纲");
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    let loadingCount = 0;

    function setLoading(on, text = "处理中…") {
      loadingCount += on ? 1 : -1;
      if (loadingCount < 0) loadingCount = 0;
      const busy = loadingCount > 0;
      document.getElementById("loadingOverlay").classList.toggle("show", busy);
      document.getElementById("loadingText").textContent = text;
      const pill = document.getElementById("statusPill");
      pill.classList.toggle("loading", busy);
      if (busy) {
        document.getElementById("statusText").textContent = "处理中";
      } else {
        updateHeaderMeta();
      }
    }

    function showToast(message) {
      const toast = document.getElementById("toast");
      toast.textContent = message;
      toast.classList.add("show");
      clearTimeout(showToast.timer);
      showToast.timer = setTimeout(() => toast.classList.remove("show"), 2200);
    }

    function updateHeaderMeta() {
      const chapter = Number(document.getElementById("chapter").value) || 1;
      document.getElementById("chapterBadge").textContent = `第 ${chapter} 章`;
      if (state.latestChapter) {
        document.getElementById("statusText").textContent = `已写 ${state.latestChapter} 章`;
      }
    }

    async function post(url, body = {}) {
      setLoading(true);
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || "请求失败");
        return data;
      } finally {
        setLoading(false);
      }
    }

    function renderText(text) {
      const current = document.getElementById("output");
      if (current.tagName.toLowerCase() === "pre") {
        current.textContent = text;
        return;
      }
      const pre = document.createElement("pre");
      pre.id = "output";
      pre.textContent = text;
      current.replaceWith(pre);
    }

    function renderChapters() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "chapter-list";
      state.chapters.forEach(ch => {
        const btn = document.createElement("button");
        btn.className = "chapter-link";
        btn.textContent = `${ch.number || "-"}  ${ch.name}`;
        btn.onclick = () => openChapter(ch.path);
        wrap.appendChild(btn);
      });
      current.replaceWith(wrap);
    }

    function qualityFixableRisk(item) {
      return Boolean(item?.aiRiskCount || item?.formatRiskCount || item?.forbiddenCount);
    }

    function qualityHasProblems(item) {
      return qualityFixableRisk(item);
    }

    function countAuditIssues(stats, key) {
      return (stats?.[key] || []).reduce((sum, hit) => sum + Number(hit.count || 0), 0);
    }

    function formatFixResult(data, item) {
      const before = data.beforeStats || {};
      const after = data.afterStats || {};
      const fixes = (data.fixesApplied || []).length ? data.fixesApplied.join("、") : "无";
      return [
        `第${item.chapter}章修复完成（${data.mode || "auto"}）`,
        `处理项：${fixes}`,
        `修复前：AI ${countAuditIssues(before, "aiHits")}｜格式 ${countAuditIssues(before, "markdownHits")}｜禁用词 ${countAuditIssues(before, "forbiddenHits")}`,
        `修复后：AI ${countAuditIssues(after, "aiHits")}｜格式 ${countAuditIssues(after, "markdownHits")}｜禁用词 ${countAuditIssues(after, "forbiddenHits")}`,
        `备份：${data.backupPath || "无"}`,
        `审查：${data.auditPath || "无"}`,
        "",
        data.auditText || data.message || ""
      ].join("\n");
    }

    function formatPipelineSummary(pipeline) {
      if (!pipeline?.stages?.length) return "";
      const stageLabel = {
        rewrite: "重写",
        audit: "审计",
        fix: "定点修",
        "re-audit": "再审计",
      };
      const lines = [`联动流水线：${pipeline.stages.map((s) => stageLabel[s] || s).join(" → ")}`];
      if (pipeline.fixesApplied?.length) {
        lines.push(`定点修处理：${pipeline.fixesApplied.join("、")}`);
      }
      if (pipeline.backupPath) {
        lines.push(`修复前备份：${pipeline.backupPath}`);
      }
      const before = pipeline.beforeStats || pipeline.initialStats || {};
      const after = pipeline.finalStats || {};
      if (pipeline.fixed) {
        lines.push(
          `问题变化：AI ${countAuditIssues(before, "aiHits")}→${countAuditIssues(after, "aiHits")}｜` +
          `格式 ${countAuditIssues(before, "markdownHits")}→${countAuditIssues(after, "markdownHits")}｜` +
          `禁用词 ${countAuditIssues(before, "forbiddenHits")}→${countAuditIssues(after, "forbiddenHits")}`
        );
      }
      return lines.join("\n");
    }

    async function fixQualityChapter(item, mode = "auto") {
      const modeLabel = mode === "rules" ? "快速修复" : mode === "ai" ? "AI修复" : "自动修复";
      const ok = confirm(`将对第${item.chapter}章执行${modeLabel}。\n会先备份原文件，再覆盖正文。继续吗？`);
      if (!ok) return;
      document.getElementById("loadingText").textContent = `正在${modeLabel}第${item.chapter}章…`;
      try {
        const data = await post("/api/fix-chapter", payload({ chapter: item.chapter, file: item.path, mode }));
        await scan();
        if (data.unchanged) {
          showToast(`第${item.chapter}章无需修复`);
          showTab("quality");
          return;
        }
        document.getElementById("chapter").value = item.chapter;
        document.getElementById("auditFile").value = data.chapterPath || item.path;
        const after = data.afterStats || {};
        const aiLeft = (after.aiHits || []).reduce((sum, hit) => sum + Number(hit.count || 0), 0);
        const fmtLeft = (after.markdownHits || []).reduce((sum, hit) => sum + Number(hit.count || 0), 0);
        const forbLeft = (after.forbiddenHits || []).reduce((sum, hit) => sum + Number(hit.count || 0), 0);
        const warnLeft = (after.warnings || []).filter(w => !["AI句式风险", "非正文格式残留", "禁用词"].includes(w)).length;
        const stillRisk = aiLeft || fmtLeft || forbLeft || warnLeft;
        setOutput(formatFixResult(data, item), `${modeLabel}完成`, data.text || data.auditText || "");
        showTab("quality");
        if (stillRisk) {
          const parts = [];
          if (aiLeft) parts.push(`AI句式 ${aiLeft} 处`);
          if (fmtLeft) parts.push(`格式残留 ${fmtLeft} 处`);
          if (forbLeft) parts.push(`禁用词 ${forbLeft} 处`);
          if (warnLeft) parts.push(`结构提醒 ${warnLeft} 项`);
          const aiHint = aiLeft ? "（AI 句式需点「AI修复」）" : "";
          showToast(`第${item.chapter}章已处理，仍有：${parts.join("、")}${aiHint}`);
        } else {
          showToast(`第${item.chapter}章${modeLabel}完成，问题已清空`);
        }
      } catch (err) {
        setOutput(String(err.message || err), "修复失败");
      }
    }

    async function fixAllQualityProblems(mode = "auto") {
      const items = (state.scan?.quality || []).filter(qualityHasProblems);
      if (!items.length) {
        showToast("没有需要修复的章节");
        return;
      }
      const modeLabel = mode === "rules" ? "快速修复" : mode === "ai" ? "AI修复" : "自动修复";
      const ok = confirm(`将依次对 ${items.length} 个有问题章节执行${modeLabel}。\n每章都会先备份。继续吗？`);
      if (!ok) return;
      const logs = [`# 批量${modeLabel}`, `章节数：${items.length}`, ""];
      setLoading(true, `正在批量${modeLabel}…`);
      try {
        for (const item of items) {
          document.getElementById("loadingText").textContent = `正在${modeLabel}第${item.chapter}章…`;
          const res = await fetch("/api/fix-chapter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload({ chapter: item.chapter, file: item.path, mode }))
          });
          const data = await res.json();
          if (!res.ok || data.error) throw new Error(data.error || "请求失败");
          if (data.unchanged) {
            logs.push(`第${item.chapter}章：无需修复`);
          } else {
            logs.push(formatFixResult(data, item));
          }
        }
        await scan();
        showTab("quality");
        showToast(`批量${modeLabel}完成`);
        setOutput(logs.join("\n\n---\n\n"), `批量${modeLabel}`);
      } catch (err) {
        setOutput(String(err.message || err), "批量修复失败");
      } finally {
        setLoading(false);
      }
    }

    function renderQuality() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";

      const projectIssues = state.scan?.projectIssues || {};
      const charIssues = projectIssues.characterIssues || [];
      const fwIssues = projectIssues.foreshadowIssues || [];
      const outlineIssues = projectIssues.outlineIssues || [];
      const totalProjectIssues = charIssues.length + fwIssues.filter(i => i.type === "foreshadow_expired").length + outlineIssues.length;

      if (totalProjectIssues > 0) {
        const projectSection = document.createElement("div");
        projectSection.className = "quality-project-issues";
        projectSection.innerHTML = `
          <div class="quality-project-header">项目级问题（${totalProjectIssues}）</div>
        `;

        if (charIssues.length) {
          const charDiv = document.createElement("div");
          charDiv.className = "quality-issue-group";
          charDiv.innerHTML = `<div class="quality-issue-title">角色冲突（${charIssues.length}）</div>`;
          charIssues.forEach(issue => {
            const item = document.createElement("div");
            item.className = "quality-issue-item";
            item.textContent = issue.message;
            charDiv.appendChild(item);
          });
          projectSection.appendChild(charDiv);
        }

        const expiredFw = fwIssues.filter(i => i.type === "foreshadow_expired");
        if (expiredFw.length) {
          const fwDiv = document.createElement("div");
          fwDiv.className = "quality-issue-group";
          fwDiv.innerHTML = `<div class="quality-issue-title">伏笔已过期（${expiredFw.length}）</div>`;
          expiredFw.forEach(issue => {
            const item = document.createElement("div");
            item.className = "quality-issue-item";
            item.textContent = issue.message;
            fwDiv.appendChild(item);
          });
          projectSection.appendChild(fwDiv);
        }

        if (outlineIssues.length) {
          const outlineDiv = document.createElement("div");
          outlineDiv.className = "quality-issue-group";
          outlineDiv.innerHTML = `<div class="quality-issue-title">大纲偏离（${outlineIssues.length}章）</div>`;
          outlineIssues.forEach(issue => {
            const item = document.createElement("div");
            item.className = "quality-issue-item";
            item.textContent = issue.message;
            outlineDiv.appendChild(item);
          });
          projectSection.appendChild(outlineDiv);
        }

        wrap.appendChild(projectSection);
      }

      const items = state.scan?.quality || [];
      if (!items.length && !totalProjectIssues) {
        const empty = document.createElement("div");
        empty.className = "quality-summary";
        empty.textContent = "还没有质量数据。扫描项目后会自动汇总。";
        wrap.appendChild(empty);
        current.replaceWith(wrap);
        return;
      }
      const problemItems = items.filter(qualityHasProblems);
      const totalAi = items.reduce((sum, item) => sum + Number(item.aiRiskCount || 0), 0);
      const totalFormat = items.reduce((sum, item) => sum + Number(item.formatRiskCount || 0), 0);
      const totalForbidden = items.reduce((sum, item) => sum + Number(item.forbiddenCount || 0), 0);
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>章节：${items.length}</span><span>有风险：${problemItems.length}</span><span>AI句式：${totalAi}</span><span>格式残留：${totalFormat}</span><span>禁用词：${totalForbidden}</span>`;
      wrap.appendChild(summary);

      if (problemItems.length) {
        const toolbar = document.createElement("div");
        toolbar.className = "quality-toolbar";
        const batchAuto = document.createElement("button");
        batchAuto.textContent = `批量自动修复（${problemItems.length}）`;
        batchAuto.onclick = () => fixAllQualityProblems("auto");
        const batchRules = document.createElement("button");
        batchRules.className = "secondary";
        batchRules.textContent = "批量快速修复";
        batchRules.onclick = () => fixAllQualityProblems("rules");
        const batchAi = document.createElement("button");
        batchAi.className = "secondary";
        batchAi.textContent = "批量 AI 修复";
        batchAi.onclick = () => fixAllQualityProblems("ai");
        toolbar.appendChild(batchAuto);
        toolbar.appendChild(batchRules);
        toolbar.appendChild(batchAi);
        wrap.appendChild(toolbar);
      }

      items.forEach(item => {
        const card = document.createElement("div");
        const risk = qualityFixableRisk(item);
        const hasNotes = (item.problems || []).length && !risk;
        card.className = `quality-item${risk ? " risk" : hasNotes ? " note" : ""}`;
        const foreshadow = item.foreshadowTotal ? `${item.foreshadowHitCount}/${item.foreshadowTotal}` : "-";
        const head = document.createElement("div");
        head.className = "quality-head";
        head.innerHTML = `
          <div class="quality-title">第${item.chapter}章 ${item.name}</div>
          <div class="quality-metrics">字数 ${item.cnChars}｜对话 ${item.dialogueCount}｜伏笔 ${foreshadow}</div>
        `;
        card.appendChild(head);

        const metrics = document.createElement("div");
        metrics.className = "quality-metrics";
        metrics.textContent = `AI风险 ${item.aiRiskCount}｜格式残留 ${item.formatRiskCount}｜禁用词 ${item.forbiddenCount}`;
        card.appendChild(metrics);

        if ((item.problems || []).length) {
          const problemList = document.createElement("ul");
          problemList.className = "quality-problems";
          item.problems.forEach(problem => {
            const li = document.createElement("li");
            li.textContent = problem;
            problemList.appendChild(li);
          });
          card.appendChild(problemList);
        } else {
          const ok = document.createElement("div");
          ok.className = "quality-ok";
          ok.textContent = "未发现明显文本问题。";
          card.appendChild(ok);
        }

        const actions = document.createElement("div");
        actions.className = "quality-actions";
        const open = document.createElement("button");
        open.className = "secondary";
        open.textContent = "打开";
        open.onclick = () => openChapter(item.path);
        const audit = document.createElement("button");
        audit.className = "secondary";
        audit.textContent = "审查";
        audit.onclick = async () => {
          document.getElementById("chapter").value = item.chapter;
          document.getElementById("auditFile").value = item.path;
          await auditChapter();
        };
        actions.appendChild(open);
        actions.appendChild(audit);

        if (risk) {
          const fixAuto = document.createElement("button");
          fixAuto.textContent = "自动修复";
          fixAuto.onclick = () => fixQualityChapter(item, "auto");
          actions.appendChild(fixAuto);

          if (item.canRuleFix) {
            const fixRules = document.createElement("button");
            fixRules.className = "secondary";
            fixRules.textContent = "快速修复";
            fixRules.onclick = () => fixQualityChapter(item, "rules");
            actions.appendChild(fixRules);
          }
          if (item.needsAiFix) {
            const fixAi = document.createElement("button");
            fixAi.className = "secondary";
            fixAi.textContent = "AI修复";
            fixAi.onclick = () => fixQualityChapter(item, "ai");
            actions.appendChild(fixAi);
          }
        }

        card.appendChild(actions);
        wrap.appendChild(card);
      });
      current.replaceWith(wrap);
    }

    function renderBackups(items) {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "quality-summary";
        empty.textContent = "当前没有可用备份。";
        wrap.appendChild(empty);
        current.replaceWith(wrap);
        return;
      }
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>备份：${items.length}</span><span>恢复前会自动备份当前文件</span>`;
      wrap.appendChild(summary);
      items.forEach(item => {
        const card = document.createElement("div");
        card.className = "quality-item";
        card.innerHTML = `
          <div class="quality-head">
            <div class="quality-title">${item.kind}｜${item.name}</div>
            <div class="quality-metrics">${item.modified}｜${item.size} 字节</div>
          </div>
          <div class="quality-metrics">目标：${item.target || "无法自动识别"}</div>
          <div class="quality-metrics">备份：${item.path}</div>
        `;
        const actions = document.createElement("div");
        actions.className = "quality-actions";
        const open = document.createElement("button");
        open.className = "secondary";
        open.textContent = "打开";
        open.onclick = () => openChapter(item.path);
        const restore = document.createElement("button");
        restore.className = "secondary";
        restore.textContent = "恢复";
        restore.onclick = () => restoreBackup(item.path, item.target);
        actions.appendChild(open);
        actions.appendChild(restore);
        card.appendChild(actions);
        wrap.appendChild(card);
      });
      current.replaceWith(wrap);
    }

    function renderSearchResults(items) {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "quality-summary";
        empty.textContent = "没有找到匹配结果。";
        wrap.appendChild(empty);
        current.replaceWith(wrap);
        return;
      }
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>结果：${items.length}</span><span>正文结果可以直接打开章节</span>`;
      wrap.appendChild(summary);
      items.forEach(item => {
        const card = document.createElement("div");
        card.className = "quality-item";
        const head = document.createElement("div");
        head.className = "quality-head";
        const title = document.createElement("div");
        title.className = "quality-title";
        title.textContent = `${item.kind}｜${item.title}`;
        const metrics = document.createElement("div");
        metrics.className = "quality-metrics";
        metrics.textContent = item.location || "";
        head.appendChild(title);
        head.appendChild(metrics);
        const snippet = document.createElement("div");
        snippet.className = "quality-metrics";
        snippet.textContent = item.snippet;
        card.appendChild(head);
        card.appendChild(snippet);
        if (item.path) {
          const actions = document.createElement("div");
          actions.className = "quality-actions";
          const open = document.createElement("button");
          open.className = "secondary";
          open.textContent = "打开";
          open.onclick = () => openChapter(item.path);
          actions.appendChild(open);
          card.appendChild(actions);
        }
        wrap.appendChild(card);
      });
      current.replaceWith(wrap);
    }

    function characterAppearances() {
      const appearances = {};
      const chapters = Object.values(state.scan?.novelbuddyState?.chapters || {})
        .filter(ch => ch && Number(ch.chapter))
        .sort((a, b) => Number(a.chapter) - Number(b.chapter));
      chapters.forEach(ch => {
        (ch.characters || []).forEach(char => {
          const name = (char.name || "").trim();
          if (!name) return;
          if (!appearances[name]) appearances[name] = [];
          appearances[name].push(Number(ch.chapter));
        });
      });
      return appearances;
    }

    function renderCharacters() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      const chars = state.scan?.characters || [];
      const appearances = characterAppearances();
      if (!chars.length) {
        const empty = document.createElement("div");
        empty.className = "quality-summary";
        empty.textContent = "还没有人物档案。";
        wrap.appendChild(empty);
        current.replaceWith(wrap);
        return;
      }
      const appeared = chars.filter(char => (appearances[char.name] || []).length).length;
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>人物：${chars.length}</span><span>有出场记录：${appeared}</span><span>未出场/未同步：${chars.length - appeared}</span>`;
      const addBtn = document.createElement("button");
      addBtn.className = "secondary";
      addBtn.textContent = "新建人物";
      addBtn.onclick = () => openEntityModal("character", {});
      summary.appendChild(addBtn);
      wrap.appendChild(summary);

      chars.forEach(char => {
        const chapters = appearances[char.name] || [];
        const recent = chapters.slice(-6);
        const card = document.createElement("div");
        card.className = "quality-item";
        const desc = char.description || "未填写";
        const personality = char.personality || "未填写";
        const background = char.background || "未填写";
        card.innerHTML = `
          <div class="quality-head">
            <div class="quality-title">${char.name || "未命名"} [${roleDisplayLabel(char.role, char.roleLabel)}]</div>
            <div class="quality-metrics">出场 ${chapters.length} 次｜最近 ${recent.length ? "第" + recent.join("、第") + "章" : "无记录"}</div>
          </div>
          <div class="quality-metrics">描述：${desc}</div>
          <div class="quality-metrics">性格：${personality}</div>
          <div class="quality-metrics">背景：${background}</div>
        `;
        const actions = document.createElement("div");
        actions.className = "quality-actions";
        const editBtn = document.createElement("button");
        editBtn.className = "secondary";
        editBtn.textContent = "编辑人物";
        editBtn.onclick = () => openEntityModal("character", char);
        actions.appendChild(editBtn);
        card.appendChild(actions);
        if (recent.length) {
          const badges = document.createElement("div");
          badges.className = "character-badges";
          recent.forEach(chapter => {
            const badge = document.createElement("button");
            badge.className = "character-badge";
            badge.textContent = `第${chapter}章`;
            badge.onclick = () => {
              document.getElementById("chapter").value = chapter;
              selectChapterFileByNumber();
              const match = state.chapters.find(item => Number(item.number) === Number(chapter));
              if (match?.path) openChapter(match.path);
            };
            badges.appendChild(badge);
          });
          card.appendChild(badges);
        }
        wrap.appendChild(card);
      });
      current.replaceWith(wrap);
    }

    function timelineChapters() {
      return Object.values(state.scan?.novelbuddyState?.chapters || {})
        .filter(ch => ch && Number(ch.chapter))
        .sort((a, b) => Number(a.chapter) - Number(b.chapter));
    }

    function renderTimeline() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      const chapters = timelineChapters();
      const chaptersWithEvents = chapters.filter(ch => (ch.events || []).length);
      const eventCount = chaptersWithEvents.reduce((sum, ch) => sum + (ch.events || []).length, 0);
      if (!chaptersWithEvents.length) {
        const empty = document.createElement("div");
        empty.className = "quality-summary";
        empty.textContent = "还没有时间线。审查或生成章节后会自动更新。";
        wrap.appendChild(empty);
        current.replaceWith(wrap);
        return;
      }
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>章节：${chaptersWithEvents.length}</span><span>事件：${eventCount}</span><span>范围：第${chaptersWithEvents[0].chapter}章至第${chaptersWithEvents[chaptersWithEvents.length - 1].chapter}章</span>`;
      wrap.appendChild(summary);

      chaptersWithEvents.forEach(ch => {
        const card = document.createElement("div");
        card.className = "quality-item";
        const eventLines = (ch.events || []).slice(0, 12).map((event, index) => {
          const chars = (event.characters || []).length ? `｜人物：${event.characters.join("、")}` : "";
          const tags = (event.tags || []).length ? `｜${event.tags.join("/")}` : "";
          return `<div class="quality-metrics">${index + 1}. ${event.summary || ""}${chars}${tags}</div>`;
        }).join("");
        card.innerHTML = `
          <div class="quality-head">
            <div class="quality-title">第${ch.chapter}章</div>
            <div class="quality-metrics">事件 ${(ch.events || []).length} 条</div>
          </div>
          ${eventLines}
        `;
        const actions = document.createElement("div");
        actions.className = "quality-actions";
        const open = document.createElement("button");
        open.className = "secondary";
        open.textContent = "打开章节";
        open.onclick = () => {
          document.getElementById("chapter").value = ch.chapter;
          selectChapterFileByNumber();
          const match = state.chapters.find(item => Number(item.number) === Number(ch.chapter));
          if (match?.path) openChapter(match.path);
        };
        actions.appendChild(open);
        card.appendChild(actions);
        wrap.appendChild(card);
      });
      current.replaceWith(wrap);
    }

    const ENTITY_SCHEMAS = {
      character: {
        title: "人物",
        fields: [
          { key: "name", label: "姓名", type: "text", required: true },
          {
            key: "role",
            label: "角色类型",
            type: "select",
            hint: "主角/配角/反派/次要角色，用于人物归档与关系图谱分组。",
            options: [
              { value: "protagonist", label: "主角" },
              { value: "supporting", label: "配角" },
              { value: "antagonist", label: "反派" },
              { value: "minor", label: "次要角色" },
            ],
          },
          { key: "description", label: "描述", type: "textarea" },
          { key: "personality", label: "性格", type: "textarea" },
          { key: "background", label: "背景", type: "textarea" },
        ],
      },
      foreshadow: {
        title: "伏笔",
        fields: [
          { key: "keyword", label: "关键词", type: "text", required: true },
          { key: "description", label: "描述", type: "textarea" },
          {
            key: "importance",
            label: "重要度",
            type: "select",
            options: [
              { value: "high", label: "高" },
              { value: "medium", label: "中" },
              { value: "low", label: "低" },
            ],
          },
          {
            key: "status",
            label: "状态",
            type: "select",
            options: [
              { value: "pending", label: "待回收" },
              { value: "resolved", label: "已回收" },
              { value: "advanced", label: "已推进" },
              { value: "cancelled", label: "已作废" },
            ],
          },
          { key: "plantedChapter", label: "埋入章节", type: "number" },
          { key: "invalidAfter", label: "失效章节", type: "number" },
        ],
      },
      organization: {
        title: "组织势力",
        fields: [
          { key: "name", label: "名称", type: "text", required: true },
          {
            key: "type",
            label: "组织类型",
            type: "select",
            options: [
              { value: "other", label: "其他" },
              { value: "government", label: "政府/官方" },
              { value: "criminal", label: "地下/犯罪" },
              { value: "military", label: "军事" },
              { value: "religious", label: "宗教" },
              { value: "corporation", label: "企业/公司" },
            ],
          },
          {
            key: "status",
            label: "状态",
            type: "select",
            options: [
              { value: "active", label: "活跃" },
              { value: "inactive", label: "休眠" },
              { value: "destroyed", label: "已覆灭" },
              { value: "unknown", label: "未知" },
            ],
          },
          { key: "leader", label: "首领", type: "text" },
          { key: "location", label: "地点", type: "text" },
          {
            key: "level",
            label: "影响范围",
            type: "select",
            options: [
              { value: "local", label: "地方" },
              { value: "regional", label: "区域" },
              { value: "national", label: "全国" },
              { value: "international", label: "国际" },
            ],
          },
          {
            key: "powerLevel",
            label: "实力等级",
            type: "select",
            options: [
              { value: "low", label: "弱" },
              { value: "medium", label: "中" },
              { value: "high", label: "强" },
            ],
          },
          { key: "validFromChapter", label: "生效章节", type: "number" },
          { key: "invalidAfterChapter", label: "失效章节", type: "number" },
          { key: "description", label: "描述", type: "textarea" },
        ],
      },
      world: {
        title: "世界观",
        fields: [
          { key: "title", label: "标题", type: "text" },
          { key: "timePeriod", label: "时代", type: "text" },
          { key: "location", label: "地点", type: "text" },
          { key: "atmosphere", label: "氛围", type: "text" },
          { key: "rulesText", label: "规则（每行一条）", type: "textarea" },
          { key: "additionalInfo", label: "补充信息", type: "textarea" },
        ],
      },
    };

    function entityFieldValue(item, field) {
      if (field.key === "rulesText" && item.rules) {
        return Array.isArray(item.rules) ? item.rules.join("\n") : "";
      }
      return item[field.key] ?? "";
    }

    const ENUM_FALLBACKS = {
      role: { protagonist: "主角", supporting: "配角", antagonist: "反派", minor: "次要角色" },
      importance: { high: "高", medium: "中", low: "低" },
      foreshadowStatus: { pending: "待回收", resolved: "已回收", advanced: "已推进", cancelled: "已作废" },
      orgType: { other: "其他", government: "政府/官方", criminal: "地下/犯罪", military: "军事", religious: "宗教", corporation: "企业/公司" },
      orgStatus: { active: "活跃", inactive: "休眠", destroyed: "已覆灭", unknown: "未知" },
      level: { local: "地方", regional: "区域", national: "全国", international: "国际" },
      powerLevel: { low: "弱", medium: "中", high: "强" },
    };

    function enumDisplayLabel(value, displayLabel, fallbackKey) {
      if (displayLabel) return displayLabel;
      const map = ENUM_FALLBACKS[fallbackKey] || {};
      return map[String(value || "").toLowerCase()] || value || "未标注";
    }

    function roleDisplayLabel(role, roleLabel) {
      return enumDisplayLabel(role, roleLabel, "role");
    }

    function renderEntityField(field, value) {
      const safeValue = String(value ?? "").replace(/"/g, "&quot;");
      if (field.type === "textarea") {
        return `<label>${field.label}</label><textarea data-key="${field.key}" style="width:100%;min-height:90px;">${value ?? ""}</textarea>`;
      }
      if (field.type === "select") {
        const options = (field.options || []).map(opt => {
          const selected = String(value ?? "") === String(opt.value) ? " selected" : "";
          return `<option value="${opt.value}"${selected}>${opt.label}</option>`;
        }).join("");
        const placeholder = value ? "" : `<option value="">请选择${field.label}</option>`;
        const hint = field.hint ? `<div class="field-hint">${field.hint}</div>` : "";
        return `<label>${field.label}</label><select data-key="${field.key}" style="width:100%;">${placeholder}${options}</select>${hint}`;
      }
      return `<label>${field.label}</label><input data-key="${field.key}" type="${field.type || "text"}" value="${safeValue}" />`;
    }

    function openEntityModal(type, item = {}) {
      const schema = ENTITY_SCHEMAS[type];
      if (!schema) return;
      document.getElementById("entityType").value = type;
      document.getElementById("entityId").value = item.id || "";
      document.getElementById("entityModalTitle").textContent = item.id ? `编辑${schema.title}` : `新建${schema.title}`;
      document.getElementById("entityDeleteBtn").style.display = item.id ? "inline-flex" : "none";
      const wrap = document.getElementById("entityFormFields");
      wrap.innerHTML = schema.fields.map(field => renderEntityField(field, entityFieldValue(item, field))).join("");
      document.getElementById("entityModal").classList.add("open");
    }

    function closeEntityModal() {
      document.getElementById("entityModal").classList.remove("open");
    }

    function closeEntityModalOnBackdrop(event) {
      if (event.target.id === "entityModal") closeEntityModal();
    }

    function collectEntityPayload() {
      const type = document.getElementById("entityType").value;
      const payload = {};
      const id = document.getElementById("entityId").value.trim();
      if (id) payload.id = id;
      document.querySelectorAll("#entityFormFields [data-key]").forEach(el => {
        const key = el.getAttribute("data-key");
        let value = el.value;
        if (el.type === "number") value = value ? Number(value) : "";
        payload[key] = value;
      });
      if (type === "world" && payload.rulesText) {
        payload.rules = String(payload.rulesText).split("\n").map(line => line.trim()).filter(Boolean);
        delete payload.rulesText;
      }
      return { type, payload };
    }

    function validateEntityPayload(type, payload) {
      const schema = ENTITY_SCHEMAS[type];
      if (!schema) return "";
      for (const field of schema.fields) {
        const raw = payload[field.key];
        const text = String(raw ?? "").trim();
        if (field.required && !text) {
          return `请填写${field.label}`;
        }
        if (field.type === "select" && text) {
          const allowed = new Set((field.options || []).map(opt => String(opt.value)));
          if (!allowed.has(text)) {
            return `请从下拉列表选择${field.label}`;
          }
        }
      }
      return "";
    }

    async function saveCurrentEntity() {
      const { type, payload } = collectEntityPayload();
      const validationError = validateEntityPayload(type, payload);
      if (validationError) {
        showToast(validationError);
        return;
      }
      try {
        const data = await post("/api/save-entity", payload({ entityType: type, entity: payload }));
        closeEntityModal();
        await scan();
        if (type === "character") showTab("characters");
        else if (type === "foreshadow") showTab("foreshadows");
        else if (type === "organization") showTab("organizations");
        else if (type === "world") showTab("world");
        showToast(`${ENTITY_SCHEMAS[type]?.title || "资料"}已保存`);
        if (data.backup) showToast(`已备份：${data.backup.split(/[/\\]/).pop()}`);
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    async function deleteCurrentEntity() {
      const type = document.getElementById("entityType").value;
      const id = document.getElementById("entityId").value.trim();
      if (!id || !confirm(`确定删除这个${ENTITY_SCHEMAS[type]?.title || "资料"}吗？`)) return;
      try {
        await post("/api/delete-entity", payload({ entityType: type, id }));
        closeEntityModal();
        await scan();
        showTab(type === "organization" ? "organizations" : type === "foreshadow" ? "foreshadows" : "characters");
        showToast("已删除");
      } catch (err) {
        showToast(String(err.message || err));
      }
    }

    function renderOrganizations() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      const orgs = state.scan?.organizations || [];
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>组织：${orgs.length}</span>`;
      const addBtn = document.createElement("button");
      addBtn.className = "secondary";
      addBtn.textContent = "新建组织";
      addBtn.onclick = () => openEntityModal("organization", {});
      summary.appendChild(addBtn);
      wrap.appendChild(summary);
      if (!orgs.length) {
        const empty = document.createElement("div");
        empty.className = "quality-metrics";
        empty.textContent = "还没有组织势力记录。";
        wrap.appendChild(empty);
        current.replaceWith(wrap);
        return;
      }
      orgs.forEach(org => {
        const card = document.createElement("div");
        card.className = "quality-item";
        const validity = [org.validFromChapter ? `生效第${org.validFromChapter}章` : "", org.invalidAfterChapter ? `失效第${org.invalidAfterChapter}章` : ""].filter(Boolean).join("｜");
        const statusText = enumDisplayLabel(org.status, org.statusLabel, "orgStatus");
        const typeText = enumDisplayLabel(org.type, org.typeLabel, "orgType");
        const levelText = enumDisplayLabel(org.level, org.levelLabel, "level");
        const powerText = enumDisplayLabel(org.powerLevel, org.powerLevelLabel, "powerLevel");
        const meta = [typeText, org.leader || "首领未填", levelText !== "未标注" ? levelText : "", powerText !== "未标注" ? `实力${powerText}` : ""].filter(Boolean).join("｜");
        card.innerHTML = `
          <div class="quality-head">
            <div class="quality-title">${org.name || "未命名"} [${statusText}]</div>
            <div class="quality-metrics">${meta}${validity ? "｜" + validity : ""}</div>
          </div>
          <div class="quality-metrics">${org.description || ""}</div>
        `;
        const actions = document.createElement("div");
        actions.className = "quality-actions";
        const editBtn = document.createElement("button");
        editBtn.className = "secondary";
        editBtn.textContent = "编辑";
        editBtn.onclick = () => openEntityModal("organization", org);
        actions.appendChild(editBtn);
        card.appendChild(actions);
        wrap.appendChild(card);
      });
      current.replaceWith(wrap);
    }

    function renderWorld() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      const world = state.scan?.world || {};
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>${world.title || "世界观设定"}</span>`;
      const editBtn = document.createElement("button");
      editBtn.className = "secondary";
      editBtn.textContent = "编辑世界观";
      editBtn.onclick = () => openEntityModal("world", { ...world, rulesText: (world.rules || []).join("\n") });
      summary.appendChild(editBtn);
      wrap.appendChild(summary);
      const card = document.createElement("div");
      card.className = "quality-item";
      const rules = (world.rules || []).slice(0, 12).map((rule, idx) => `<div class="quality-metrics">${idx + 1}. ${rule}</div>`).join("");
      card.innerHTML = `
        <div class="quality-metrics">时代：${world.timePeriod || "-"}｜地点：${world.location || "-"}</div>
        <div class="quality-metrics">氛围：${world.atmosphere || "-"}</div>
        ${rules}
        <div class="quality-metrics">${world.additionalInfo || ""}</div>
      `;
      wrap.appendChild(card);
      current.replaceWith(wrap);
    }

    async function batchAnalyzeChapters() {
      if (!confirm("将批量分析所有章节正文并更新本地资料，可能耗时较长。继续吗？")) return;
      setOutput("批量分析中...");
      try {
        const data = await post("/api/batch-analyze", payload());
        await scan();
        const lines = data.chapters.map(ch => `第${ch.chapter}章：人物 ${ch.characters}｜同章线索 ${ch.relationshipHints}｜伏笔命中 ${ch.foreshadowHits}`).join("\n");
        setOutput(`批量分析完成，共 ${data.count} 章。\n\n${lines}`, "批量分析章节");
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    async function selfCheckProject() {
      setOutput("生成自检报告中...");
      try {
        const data = await post("/api/self-check", payload());
        setOutput(data.text, "自检报告");
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    function stopGraphSimulation() {
      if (state.graphSimHandle) {
        cancelAnimationFrame(state.graphSimHandle);
        state.graphSimHandle = null;
      }
      if (state.graphInteractionAbort) {
        state.graphInteractionAbort.abort();
        state.graphInteractionAbort = null;
      }
    }

    function bindRelationshipGraphToolbar(toolbar, data) {
      toolbar.querySelectorAll("[data-filter]").forEach(btn => {
        btn.addEventListener("click", () => {
          state.graphEdgeFilter = btn.getAttribute("data-filter") || "all";
          renderRelationshipGraph(data, { edgeFilter: state.graphEdgeFilter });
        });
      });
      document.getElementById("graphScopeSelect").addEventListener("change", event => {
        loadRelationshipGraphTab({ scope: event.target.value, edgeFilter: state.graphEdgeFilter });
      });
      document.getElementById("graphReload").addEventListener("click", () => {
        loadRelationshipGraphTab({ scope: state.graphScope, edgeFilter: state.graphEdgeFilter });
      });
    }

    function filterGraphEdges(edges, filter) {
      if (filter === "formal") return edges.filter(edge => edge.kind === "formal");
      if (filter === "hint") return edges.filter(edge => edge.kind === "hint");
      return edges;
    }

    function graphNodeRadius(node) {
      return 12 + Math.min((node.connectionCount || 0) * 2.5, 18);
    }

    function renderRelationshipGraph(data, options = {}) {
      stopGraphSimulation();
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "graph-view";

      const edgeFilter = options.edgeFilter || state.graphEdgeFilter || "all";
      const scope = data.scope || state.graphScope || "window";
      state.graphEdgeFilter = edgeFilter;
      state.graphScope = scope;

      const allNodes = (data.nodes || []).map(node => ({ ...node }));
      const allEdges = (data.edges || []).map(edge => ({ ...edge }));
      const visibleEdges = filterGraphEdges(allEdges, edgeFilter);
      const activeNodeIds = new Set();
      visibleEdges.forEach(edge => {
        activeNodeIds.add(edge.from);
        activeNodeIds.add(edge.to);
      });
      const nodes = edgeFilter === "all"
        ? allNodes
        : allNodes.filter(node => activeNodeIds.has(node.id));
      const edges = visibleEdges;

      const toolbar = document.createElement("div");
      toolbar.className = "graph-toolbar";
      const scopeLabel = scope === "full"
        ? `全书（至第${data.chapter || "-"}章）`
        : `第${data.windowStart || "-"}章至第${data.chapter || "-"}章`;
      toolbar.innerHTML = `
        <div class="graph-stats">
          <span>人物 ${nodes.length}</span>
          <span>连线 ${edges.length}</span>
          <span>正式 ${data.formalEdgeCount || 0}</span>
          <span>同章 ${data.hintEdgeCount || 0}</span>
          <span>${scopeLabel}</span>
        </div>
        <div class="graph-filter-group" data-filter-group>
          <button type="button" data-filter="all" class="${edgeFilter === "all" ? "active" : ""}">全部</button>
          <button type="button" data-filter="formal" class="${edgeFilter === "formal" ? "active" : ""}">正式</button>
          <button type="button" data-filter="hint" class="${edgeFilter === "hint" ? "active" : ""}">同章</button>
        </div>
        <select id="graphScopeSelect">
          <option value="window" ${scope === "window" ? "selected" : ""}>近期窗口</option>
          <option value="full" ${scope === "full" ? "selected" : ""}>全书范围</option>
        </select>
        <input id="graphSearch" type="search" placeholder="搜索人物..." />
        <button type="button" class="secondary" id="graphResetView">重置视图</button>
        <button type="button" class="secondary" id="graphReload">刷新图谱</button>
      `;
      wrap.appendChild(toolbar);

      const main = document.createElement("div");
      main.className = "graph-main";

      const stage = document.createElement("div");
      stage.className = "graph-stage";
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "graph-canvas");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "人物关系图谱");
      const zoomLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      zoomLayer.setAttribute("class", "graph-zoom-layer");
      svg.appendChild(zoomLayer);
      stage.appendChild(svg);
      if (!nodes.length) {
        const empty = document.createElement("div");
        empty.className = "graph-empty-hint";
        if (edgeFilter === "hint") {
          empty.textContent = "当前范围没有同章线索。点「全部」可查看人物档案与正式关系。";
        } else if (edgeFilter === "formal") {
          empty.textContent = "当前范围没有正式关系记录。点「全部」可查看所有人物。";
        } else {
          empty.textContent = "当前范围没有可显示的人物，请切换全书范围或先同步章节资料。";
        }
        stage.appendChild(empty);
      }
      main.appendChild(stage);

      const sidebar = document.createElement("aside");
      sidebar.className = "graph-sidebar";
      sidebar.innerHTML = `<h3>人物关联</h3><div class="graph-side-meta">点击节点查看此人的全部关联；拖拽节点、滚轮缩放、拖动画布平移。</div>`;
      main.appendChild(sidebar);
      wrap.appendChild(main);

      const legend = document.createElement("div");
      legend.className = "graph-legend";
      legend.innerHTML = `
        <span><i></i> 正式关系</span>
        <span><i class="hint"></i> 同章线索</span>
        <span><i style="border-color:var(--accent)"></i> 主角</span>
        <span><i style="border-color:var(--success)"></i> 支援</span>
        <span><i style="border-color:var(--danger)"></i> 对立</span>
      `;
      wrap.appendChild(legend);
      current.replaceWith(wrap);
      bindRelationshipGraphToolbar(toolbar, data);

      if (!nodes.length) return;

      const graphInteractionAbort = new AbortController();
      state.graphInteractionAbort = graphInteractionAbort;
      const graphSignal = graphInteractionAbort.signal;

      const simNodes = nodes.map((node, index) => {
        const angle = nodes.length === 1 ? 0 : (Math.PI * 2 * index / nodes.length) - Math.PI / 2;
        const spread = Math.min(220, 70 + nodes.length * 14);
        return {
          ...node,
          x: Math.cos(angle) * spread,
          y: Math.sin(angle) * spread,
          vx: 0,
          vy: 0,
          r: graphNodeRadius(node),
          fx: null,
          fy: null,
        };
      });
      const simNodeById = Object.fromEntries(simNodes.map(node => [node.id, node]));
      const simEdges = edges
        .filter(edge => simNodeById[edge.from] && simNodeById[edge.to])
        .map(edge => ({
          ...edge,
          source: simNodeById[edge.from],
          target: simNodeById[edge.to],
        }));

      const edgeEls = new Map();
      const labelEls = new Map();
      const nodeEls = new Map();
      let selectedId = null;
      let view = { x: 0, y: 0, scale: 1 };
      let panning = false;
      let panStart = null;
      let draggingNode = null;

      function applyViewTransform() {
        zoomLayer.setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.scale})`);
      }

      function neighborMap() {
        const map = new Map();
        simEdges.forEach(edge => {
          if (!map.has(edge.source.id)) map.set(edge.source.id, new Set());
          if (!map.has(edge.target.id)) map.set(edge.target.id, new Set());
          map.get(edge.source.id).add(edge.target.id);
          map.get(edge.target.id).add(edge.source.id);
        });
        return map;
      }
      const neighbors = neighborMap();

      function highlightState(focusId) {
        const focusNeighbors = focusId ? (neighbors.get(focusId) || new Set()) : null;
        nodeEls.forEach((group, id) => {
          group.classList.toggle("selected", focusId === id);
          group.classList.toggle("neighbor", !!focusId && focusId !== id && focusNeighbors.has(id));
          group.classList.toggle("dim", !!focusId && focusId !== id && !focusNeighbors.has(id));
        });
        edgeEls.forEach((line, id) => {
          const edge = simEdges.find(item => item.id === id);
          if (!edge) return;
          const linked = focusId && (edge.source.id === focusId || edge.target.id === focusId);
          line.classList.toggle("highlight", !!linked);
          line.classList.toggle("dim", !!focusId && !linked);
        });
        labelEls.forEach((label, id) => {
          const edge = simEdges.find(item => item.id === id);
          if (!edge) return;
          const linked = focusId && (edge.source.id === focusId || edge.target.id === focusId);
          label.classList.toggle("visible", !!linked);
        });
      }

      function renderSidebar(node) {
        if (!node) {
          sidebar.innerHTML = `<h3>人物关联</h3><div class="graph-side-meta">点击节点查看此人的全部关联；拖拽节点、滚轮缩放、拖动画布平移。</div>`;
          return;
        }
        const related = simEdges
          .filter(edge => edge.source.id === node.id || edge.target.id === node.id)
          .map(edge => {
            const other = edge.source.id === node.id ? edge.target : edge.source;
            return { edge, other };
          })
          .sort((a, b) => (b.edge.kind === "formal") - (a.edge.kind === "formal") || (b.edge.weight || 0) - (a.edge.weight || 0));

        const chapterText = (node.chapters || []).length
          ? (node.chapters || []).map(num => `第${num}章`).join("、")
          : "暂无出场记录";
        const desc = [node.description, node.personality].filter(Boolean).join("｜") || "暂无人物档案描述。";

        sidebar.innerHTML = `
          <h3>${node.name}</h3>
          <div class="graph-side-meta">${roleDisplayLabel(node.role, node.roleLabel)} · 关联 ${node.connectionCount || 0} · 最近第${node.lastChapter || "-"}章</div>
          <div class="graph-side-meta">${desc}</div>
          <div class="graph-side-section">
            <h4>出场章节</h4>
            <div class="graph-side-meta">${chapterText}</div>
          </div>
          <div class="graph-side-section">
            <h4>关联人物（${related.length}）</h4>
            ${related.length ? related.map(({ edge, other }) => `
              <div class="graph-relation-item" data-target="${other.id}">
                <span class="rel-kind ${edge.kind || "hint"}">${edge.kind === "formal" ? "正式" : "同章"}</span>
                <strong>${other.name}</strong> — ${edge.label || "关系"}
                ${edge.status ? `<div>状态：${edge.status}</div>` : ""}
                ${edge.notes ? `<div>备注：${edge.notes}</div>` : ""}
                ${edge.chapters?.length ? `<div>章节：${edge.chapters.map(num => `第${num}章`).join("、")}</div>` : ""}
              </div>
            `).join("") : `<div class="graph-side-meta">此人当前筛选下没有可见关联。</div>`}
          </div>
        `;
        sidebar.querySelectorAll("[data-target]").forEach(item => {
          item.addEventListener("click", () => {
            const targetId = item.getAttribute("data-target");
            const target = simNodeById[targetId];
            if (target) selectNode(target.id);
          });
        });
      }

      function selectNode(id) {
        selectedId = selectedId === id ? null : id;
        highlightState(selectedId);
        renderSidebar(selectedId ? simNodeById[selectedId] : null);
      }

      function clientToGraph(clientX, clientY) {
        const rect = svg.getBoundingClientRect();
        return {
          x: (clientX - rect.left - view.x) / view.scale,
          y: (clientY - rect.top - view.y) / view.scale,
        };
      }

      function updatePositions() {
        simEdges.forEach(edge => {
          const line = edgeEls.get(edge.id);
          const label = labelEls.get(edge.id);
          if (!line) return;
          line.setAttribute("x1", edge.source.x);
          line.setAttribute("y1", edge.source.y);
          line.setAttribute("x2", edge.target.x);
          line.setAttribute("y2", edge.target.y);
          if (label) {
            label.setAttribute("x", (edge.source.x + edge.target.x) / 2);
            label.setAttribute("y", (edge.source.y + edge.target.y) / 2 - 4);
          }
        });
        simNodes.forEach(node => {
          const group = nodeEls.get(node.id);
          if (!group) return;
          const circle = group.querySelector("circle");
          const text = group.querySelector("text");
          circle.setAttribute("cx", node.x);
          circle.setAttribute("cy", node.y);
          text.setAttribute("x", node.x);
          text.setAttribute("y", node.y + node.r + 12);
        });
      }

      simEdges.forEach(edge => {
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("class", `graph-line ${edge.kind || "hint"}`);
        zoomLayer.appendChild(line);
        edgeEls.set(edge.id, line);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("class", "graph-edge-label");
        label.textContent = edge.label || "";
        zoomLayer.appendChild(label);
        labelEls.set(edge.id, label);
      });

      simNodes.forEach(node => {
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.setAttribute("class", `graph-node role-${node.roleGroup || "neutral"}`);
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("r", node.r);
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.textContent = node.name;
        group.appendChild(circle);
        group.appendChild(text);
        zoomLayer.appendChild(group);
        nodeEls.set(node.id, group);

        group.addEventListener("mouseenter", () => {
          if (!selectedId) highlightState(node.id);
        });
        group.addEventListener("mouseleave", () => {
          if (!selectedId) highlightState(null);
        });
        group.addEventListener("click", event => {
          event.stopPropagation();
          selectNode(node.id);
        });
        group.addEventListener("mousedown", event => {
          event.stopPropagation();
          draggingNode = node;
          node.fx = node.x;
          node.fy = node.y;
        });
      });

      function fitView() {
        if (!simNodes.length) return;
        const rect = svg.getBoundingClientRect();
        const padding = 70;
        const xs = simNodes.map(node => node.x);
        const ys = simNodes.map(node => node.y);
        const minX = Math.min(...xs) - padding;
        const maxX = Math.max(...xs) + padding;
        const minY = Math.min(...ys) - padding;
        const maxY = Math.max(...ys) + padding;
        const graphW = Math.max(120, maxX - minX);
        const graphH = Math.max(120, maxY - minY);
        const scale = Math.min(2.2, Math.max(0.35, Math.min((rect.width - 40) / graphW, (rect.height - 40) / graphH)));
        view.scale = scale;
        view.x = (rect.width - graphW * scale) / 2 - minX * scale;
        view.y = (rect.height - graphH * scale) / 2 - minY * scale;
        applyViewTransform();
      }

      let alpha = 1;
      function tickSimulation() {
        const centerStrength = 0.03;
        const chargeStrength = -320;
        const linkDistance = 110;

        simNodes.forEach(node => {
          node.vx += (0 - node.x) * centerStrength;
          node.vy += (0 - node.y) * centerStrength;
        });

        for (let i = 0; i < simNodes.length; i += 1) {
          for (let j = i + 1; j < simNodes.length; j += 1) {
            const a = simNodes[i];
            const b = simNodes[j];
            let dx = b.x - a.x;
            let dy = b.y - a.y;
            let dist = Math.hypot(dx, dy) || 1;
            const minDist = a.r + b.r + 24;
            if (dist < minDist) {
              const push = (minDist - dist) * 0.5;
              dx /= dist;
              dy /= dist;
              a.vx -= dx * push;
              a.vy -= dy * push;
              b.vx += dx * push;
              b.vy += dy * push;
            }
            const force = chargeStrength / (dist * dist);
            dx /= dist;
            dy /= dist;
            a.vx -= dx * force;
            a.vy -= dy * force;
            b.vx += dx * force;
            b.vy += dy * force;
          }
        }

        simEdges.forEach(edge => {
          const source = edge.source;
          const target = edge.target;
          let dx = target.x - source.x;
          let dy = target.y - source.y;
          let dist = Math.hypot(dx, dy) || 1;
          const strength = 0.04 + (edge.weight || 1) * 0.01;
          const gap = linkDistance + source.r + target.r;
          const diff = (dist - gap) * strength;
          dx /= dist;
          dy /= dist;
          if (!source.fx) {
            source.vx += dx * diff;
            source.vy += dy * diff;
          }
          if (!target.fx) {
            target.vx -= dx * diff;
            target.vy -= dy * diff;
          }
        });

        simNodes.forEach(node => {
          if (node.fx != null) {
            node.x = node.fx;
            node.vx = 0;
          } else {
            node.vx *= 0.84;
            node.x += node.vx;
          }
          if (node.fy != null) {
            node.y = node.fy;
            node.vy = 0;
          } else {
            node.vy *= 0.84;
            node.y += node.vy;
          }
        });

        updatePositions();
        alpha *= 0.985;
        if (alpha > 0.02 || draggingNode) {
          state.graphSimHandle = requestAnimationFrame(tickSimulation);
        }
      }

      svg.addEventListener("mousedown", event => {
        if (event.target === svg || event.target === zoomLayer) {
          panning = true;
          panStart = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
          stage.classList.add("panning");
        }
      });
      window.addEventListener("mousemove", event => {
        if (draggingNode) {
          const point = clientToGraph(event.clientX, event.clientY);
          draggingNode.fx = point.x;
          draggingNode.fy = point.y;
          alpha = 1;
          if (!state.graphSimHandle) state.graphSimHandle = requestAnimationFrame(tickSimulation);
          return;
        }
        if (!panning || !panStart) return;
        view.x = panStart.viewX + (event.clientX - panStart.x);
        view.y = panStart.viewY + (event.clientY - panStart.y);
        applyViewTransform();
      }, { signal: graphSignal });
      window.addEventListener("mouseup", () => {
        if (draggingNode) {
          draggingNode.fx = null;
          draggingNode.fy = null;
          draggingNode = null;
        }
        panning = false;
        panStart = null;
        stage.classList.remove("panning");
      }, { signal: graphSignal });
      svg.addEventListener("wheel", event => {
        event.preventDefault();
        const point = clientToGraph(event.clientX, event.clientY);
        const factor = event.deltaY < 0 ? 1.12 : 0.9;
        const nextScale = Math.min(3, Math.max(0.25, view.scale * factor));
        view.x -= point.x * (nextScale - view.scale);
        view.y -= point.y * (nextScale - view.scale);
        view.scale = nextScale;
        applyViewTransform();
      }, { passive: false });
      svg.addEventListener("click", () => {
        if (!draggingNode) selectNode(null);
      });

      document.getElementById("graphSearch").addEventListener("input", event => {
        const query = String(event.target.value || "").trim();
        if (!query) {
          highlightState(selectedId);
          return;
        }
        const match = simNodes.find(node => node.name.includes(query));
        if (match) selectNode(match.id);
      });
      document.getElementById("graphResetView").addEventListener("click", () => fitView());

      applyViewTransform();
      updatePositions();
      state.graphSimHandle = requestAnimationFrame(tickSimulation);
      setTimeout(fitView, 260);
    }

    async function loadRelationshipGraphTab(options = {}) {
      if (!state.scan) {
        renderText("请先扫描项目。");
        return;
      }
      const scope = options.scope || state.graphScope || "window";
      const chapter = Number(document.getElementById("chapter").value) || state.latestChapter || 1;
      const output = document.getElementById("output");
      if (output && !output.classList.contains("graph-view")) {
        renderText("加载关系图谱中...");
      }
      try {
        const data = await post("/api/relationship-graph", payload({ chapter, scope }));
        state.relationshipGraphData = data;
        state.relationshipsText = data.text;
        state.graphScope = scope;
        state.copyText = data.text;
        document.getElementById("title").textContent = `第${data.chapter || chapter}章关系图谱`;
        renderRelationshipGraph(data, { edgeFilter: options.edgeFilter || state.graphEdgeFilter });
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    function chapterState(chapter) {
      const stateFile = state.scan?.novelbuddyState || {};
      return stateFile.chapters?.[String(chapter)] || null;
    }

    function buildForeshadowsText(items) {
      if (!items || items.length === 0) return "没有可显示的伏笔。";
      return items.map(f => {
        const local = f.novelbuddyStatus ? `NovelBuddy: ${f.novelbuddyStatus}` : "";
        const hit = f.hit === true ? "命中" : f.hit === false ? "未命中" : "";
        const importanceText = enumDisplayLabel(f.importance, f.importanceLabel, "importance");
        const statusText = enumDisplayLabel(f.status || f.sourceStatus, f.statusLabel, "foreshadowStatus");
        const status = [importanceText, statusText, hit || local].filter(Boolean).join("/");
        return `${f.id} [${status}] 第${f.plantedChapter || "-"}章 ${f.keyword}\n${f.description}`;
      }).join("\n\n");
    }

    function foreshadowRisk(item, chapter) {
      const invalidAfter = Number(item.invalidAfter || item.invalidAfterChapter || 999999);
      if (item.hit === true || item.status === "resolved" || item.sourceStatus === "resolved") return "已命中";
      if (invalidAfter < chapter) return "已过期";
      if (invalidAfter - chapter <= 5) return "临近失效";
      const planted = Number(item.plantedChapter || 0);
      if (planted && chapter - planted >= 8) return "拖延较久";
      return "待处理";
    }

    function renderForeshadows() {
      const current = document.getElementById("output");
      const wrap = document.createElement("div");
      wrap.id = "output";
      wrap.className = "quality-list";
      const currentChapter = Number(document.getElementById("chapter").value) || state.latestChapter || 1;
      const local = chapterState(currentChapter);
      const items = local?.foreshadows?.length ? local.foreshadows : (state.scan?.foreshadows || []);
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "quality-summary";
        empty.textContent = "没有可显示的伏笔。";
        wrap.appendChild(empty);
        const footer = document.createElement("div");
        footer.className = "quality-actions";
        const addBtn = document.createElement("button");
        addBtn.className = "secondary";
        addBtn.textContent = "新建伏笔";
        addBtn.onclick = () => openEntityModal("foreshadow", {});
        footer.appendChild(addBtn);
        wrap.appendChild(footer);
        current.replaceWith(wrap);
        return;
      }
      const counts = items.reduce((acc, item) => {
        const risk = foreshadowRisk(item, currentChapter);
        acc[risk] = (acc[risk] || 0) + 1;
        return acc;
      }, {});
      const summary = document.createElement("div");
      summary.className = "quality-summary";
      summary.innerHTML = `<span>伏笔：${items.length}</span><span>命中：${counts["已命中"] || 0}</span><span>临近/过期：${(counts["临近失效"] || 0) + (counts["已过期"] || 0)}</span><span>当前：第${currentChapter}章</span>`;
      wrap.appendChild(summary);

      items.forEach(item => {
        const risk = foreshadowRisk(item, currentChapter);
        const card = document.createElement("div");
        card.className = `quality-item${risk === "已命中" ? " foreshadow-hit" : (risk === "已过期" || risk === "临近失效" ? " foreshadow-risk" : "")}`;
        const importanceText = enumDisplayLabel(item.importance, item.importanceLabel, "importance");
        const statusText = enumDisplayLabel(item.status || item.sourceStatus, item.statusLabel, "foreshadowStatus");
        const status = [importanceText, statusText, item.novelbuddyStatus || risk].filter(Boolean).join(" / ");
        const invalidAfter = item.invalidAfter || item.invalidAfterChapter || "-";
        card.innerHTML = `
          <div class="quality-head">
            <div class="quality-title">${item.id || "-"}｜${item.keyword || "未命名伏笔"}</div>
            <div class="quality-metrics">${status}</div>
          </div>
          <div class="quality-metrics">埋入：第${item.plantedChapter || "-"}章｜有效至：第${invalidAfter}章｜风险：${risk}</div>
          <div class="quality-metrics">${item.description || ""}</div>
        `;
        const actions = document.createElement("div");
        actions.className = "quality-actions";
        const editBtn = document.createElement("button");
        editBtn.className = "secondary";
        editBtn.textContent = "编辑伏笔";
        const full = (state.scan?.foreshadows || []).find(fw => fw.id === item.id) || item;
        editBtn.onclick = () => openEntityModal("foreshadow", full);
        actions.appendChild(editBtn);
        card.appendChild(actions);
        wrap.appendChild(card);
      });
      const footer = document.createElement("div");
      footer.className = "quality-actions";
      const addBtn = document.createElement("button");
      addBtn.className = "secondary";
      addBtn.textContent = "新建伏笔";
      addBtn.onclick = () => openEntityModal("foreshadow", {});
      footer.appendChild(addBtn);
      wrap.appendChild(footer);
      current.replaceWith(wrap);
    }

    function buildTimelineText(stateFile) {
      const chapters = Object.values(stateFile?.chapters || {})
        .filter(ch => ch && Number(ch.chapter))
        .sort((a, b) => Number(a.chapter) - Number(b.chapter));
      if (!chapters.length) return "还没有时间线。审查或生成章节后会自动更新。";
      const blocks = [];
      chapters.forEach(ch => {
        const events = ch.events || [];
        if (!events.length) return;
        blocks.push(
          `第${ch.chapter}章\n` +
          events.map((event, idx) => {
            const chars = event.characters?.length ? `｜人物：${event.characters.join("、")}` : "";
            const tags = event.tags?.length ? `｜${event.tags.join("/")}` : "";
            return `${idx + 1}. ${event.summary}${chars}${tags}`;
          }).join("\n")
        );
      });
      return blocks.join("\n\n---\n\n") || "还没有可展示的事件。";
    }

    function buildQualityText(items) {
      if (!items || !items.length) return "还没有质量数据。扫描项目后会自动汇总。";
      const problemItems = items.filter(qualityFixableRisk);
      const header = [
        `章节数：${items.length}`,
        `有风险章节：${problemItems.length}`,
        `AI句式风险：${items.reduce((sum, item) => sum + Number(item.aiRiskCount || 0), 0)} 次`,
        `格式残留：${items.reduce((sum, item) => sum + Number(item.formatRiskCount || 0), 0)} 处`,
        `禁用词：${items.reduce((sum, item) => sum + Number(item.forbiddenCount || 0), 0)} 次`
      ].join("\n");
      const rows = items.map(item => {
        const warnings = item.warnings?.length ? item.warnings.join("、") : "无";
        const foreshadow = item.foreshadowTotal
          ? `${item.foreshadowHitCount}/${item.foreshadowTotal}`
          : "-";
        return [
          `第${item.chapter}章 ${item.name}`,
          `字数：${item.cnChars}｜对话：${item.dialogueCount}｜伏笔命中：${foreshadow}`,
          `AI风险：${item.aiRiskCount}｜格式残留：${item.formatRiskCount}｜禁用词：${item.forbiddenCount}`,
          `提示：${warnings}`,
          `文件：${item.path}`
        ].join("\n");
      }).join("\n\n---\n\n");
      return `${header}\n\n${rows}`;
    }

    function setOutput(text, title = "输出", copyText = null) {
      state.output = text;
      state.copyText = copyText === null ? text : copyText;
      renderText(text);
      document.getElementById("title").textContent = title;
      activateTab("output");
    }

    function activateTab(name) {
      document.querySelectorAll(".tab").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === name);
      });
    }

    function showTab(name) {
      activateTab(name);
      const title = name === "outlines" ? "大纲" : name === "chapters" ? "章节" : name === "characters" ? "人物" : name === "relationships" ? "关系图谱" : name === "timeline" ? "时间线" : name === "quality" ? "问题总览" : name === "foreshadows" ? "伏笔情况" : name === "organizations" ? "组织势力" : name === "world" ? "世界观" : "输出";
      document.getElementById("title").textContent = title;
      if (name === "chapters") {
        renderChapters();
        return;
      }
      if (name === "quality") {
        renderQuality();
        state.copyText = state.qualityText;
        return;
      }
      if (name === "characters") {
        renderCharacters();
        state.copyText = state.charactersText;
        return;
      }
      if (name === "timeline") {
        renderTimeline();
        state.copyText = state.timelineText;
        return;
      }
      if (name === "foreshadows") {
        renderForeshadows();
        state.copyText = state.foreshadowsText;
        return;
      }
      if (name === "relationships") {
        if (state.relationshipGraphData) {
          renderRelationshipGraph(state.relationshipGraphData, { edgeFilter: state.graphEdgeFilter });
          state.copyText = state.relationshipsText;
        } else {
          loadRelationshipGraphTab();
        }
        return;
      }
      if (name === "organizations") {
        renderOrganizations();
        state.copyText = state.organizationsText;
        return;
      }
      if (name === "world") {
        renderWorld();
        state.copyText = state.worldText;
        return;
      }
      const text = name === "outlines" ? state.outlinesText
        : name === "characters" ? state.charactersText
        : name === "relationships" ? state.relationshipsText
        : name === "timeline" ? state.timelineText
        : name === "quality" ? state.qualityText
        : name === "foreshadows" ? state.foreshadowsText
        : state.output;
      state.copyText = text;
      renderText(text);
    }

    function resetProjectStats() {
      ["sCharacters", "sOutlines", "sSummaries", "sForeshadows", "sChapters", "sLatestChapter", "sNextChapter"].forEach(id => {
        document.getElementById(id).textContent = "-";
      });
    }

    function clearProjectCaches() {
      stopGraphSimulation();
      state.scan = null;
      state.output = "";
      state.copyText = "";
      state.outlinesText = "";
      state.chaptersText = "";
      state.charactersText = "";
      state.relationshipsText = "";
      state.organizationsText = "";
      state.worldText = "";
      state.relationshipGraphData = null;
      state.timelineText = "";
      state.qualityText = "";
      state.foreshadowsText = "";
      state.chapters = [];
      state.latestChapter = 0;
      state.nextChapter = 1;
      state.graphScope = "window";
      state.graphEdgeFilter = "all";
      document.getElementById("auditFile").innerHTML = "";
      resetProjectStats();
    }

    function applyScanData(data, options = {}) {
      state.scan = data;
      document.getElementById("sCharacters").textContent = data.counts.characters;
      document.getElementById("sOutlines").textContent = data.counts.outlines;
      document.getElementById("sSummaries").textContent = data.counts.summaries;
      document.getElementById("sForeshadows").textContent = data.counts.foreshadows;
      document.getElementById("sChapters").textContent = data.counts.chapters;
      state.latestChapter = data.progress.latestChapter || 0;
      state.nextChapter = data.progress.nextChapter || 1;
      document.getElementById("sLatestChapter").textContent = state.latestChapter || "-";
      document.getElementById("sNextChapter").textContent = state.nextChapter || "-";
      if (options.resetToNextChapter) {
        document.getElementById("chapter").value = state.nextChapter || 1;
        saveWorkspaceSettings();
      }
      const select = document.getElementById("auditFile");
      select.innerHTML = "";
      data.chapters.forEach(ch => {
        const opt = document.createElement("option");
        opt.value = ch.path;
        opt.textContent = ch.name;
        select.appendChild(opt);
      });
      state.chapters = data.chapters;
      selectChapterFileByNumber();
      state.outlinesText = data.outlines.map(o => `第${o.chapterNumber}章 ${o.title}\n${o.content}`).join("\n\n---\n\n");
      state.chaptersText = data.chapters.map(ch => `${ch.number || "-"}  ${ch.name}\n${ch.path}`).join("\n\n");
      state.charactersText = data.characters.map(c => `${c.name} [${roleDisplayLabel(c.role, c.roleLabel)}]\n${c.description || ""}\n性格：${c.personality || "未填写"}\n背景：${c.background || "未填写"}`).join("\n\n---\n\n");
      const currentChapter = Number(document.getElementById("chapter").value);
      const currentState = chapterState(currentChapter);
      const baseRelationships = data.relationships.length
        ? data.relationships.map(r => `${r.left} -- ${r.label}(${r.strength || "-"}) -- ${r.right}\n状态：${r.status || "未标注"}\n备注：${r.notes || "无"}`).join("\n\n")
        : "当前没有正式关系记录。";
      const hints = currentState?.relationshipHints?.length
        ? currentState.relationshipHints.map(r => `${r.left} -- ${r.label} -- ${r.right}`).join("\n")
        : "当前章节还没有同章关系线索。";
      state.relationshipsText = `正式关系图谱\n\n${baseRelationships}\n\n---\n\n第${currentChapter}章同章关系线索\n\n${hints}`;
      if (options.refreshRelationshipGraph !== false) {
        state.relationshipGraphData = null;
        post("/api/relationship-graph", payload({ chapter: currentChapter, scope: state.graphScope }))
          .then(graphData => { state.relationshipGraphData = graphData; state.relationshipsText = graphData.text; })
          .catch(() => {});
      }
      state.timelineText = buildTimelineText(data.novelbuddyState);
      state.qualityText = buildQualityText(data.quality);
      state.organizationsText = (data.organizations || []).map(org => {
        const validity = [org.validFromChapter ? `生效第${org.validFromChapter}章` : "", org.invalidAfterChapter ? `失效第${org.invalidAfterChapter}章` : ""].filter(Boolean).join("｜");
        const statusText = enumDisplayLabel(org.status, org.statusLabel, "orgStatus");
        const typeText = enumDisplayLabel(org.type, org.typeLabel, "orgType");
        const levelText = enumDisplayLabel(org.level, org.levelLabel, "level");
        const powerText = enumDisplayLabel(org.powerLevel, org.powerLevelLabel, "powerLevel");
        const meta = [typeText, levelText !== "未标注" ? levelText : "", powerText !== "未标注" ? `实力${powerText}` : ""].filter(Boolean).join("｜");
        return `${org.name} [${statusText}] ${meta}\n首领：${org.leader || "-"}\n${validity}\n${org.description || ""}`;
      }).join("\n\n---\n\n") || "还没有组织势力记录。";
      const world = data.world || {};
      state.worldText = [
        world.title || "世界观设定",
        `时代：${world.timePeriod || "-"}`,
        `地点：${world.location || "-"}`,
        `氛围：${world.atmosphere || "-"}`,
        (world.rules || []).map((rule, idx) => `${idx + 1}. ${rule}`).join("\n"),
        world.additionalInfo || "",
      ].filter(Boolean).join("\n\n");
      state.foreshadowsText = currentState?.foreshadows?.length
        ? `第${currentChapter}章伏笔情况（NovelBuddy 本地状态）\n\n${buildForeshadowsText(currentState.foreshadows)}`
        : buildForeshadowsText(data.foreshadows);
      updateHeaderMeta();
    }

    async function scan() {
      setOutput("扫描中...");
      try {
        const data = await post("/api/scan", payload());
        applyScanData(data);
        setOutput(data.summary, "扫描结果");
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    async function loadProject(options = {}) {
      const project = document.getElementById("project").value.trim();
      if (!project) {
        showToast("请先填写项目目录");
        return;
      }
      saveWorkspaceSettings();
      clearProjectCaches();
      if (!options.silent) {
        setOutput(`正在加载项目：\n${project}`, "加载项目");
      }
      try {
        const data = await post("/api/scan", payload());
        applyScanData(data, { resetToNextChapter: true });
        if (!options.silent) {
          showToast(`已加载：${project}`);
        }
        setOutput(data.summary, options.silent ? "扫描结果" : "项目已加载");
      } catch (err) {
        setOutput(String(err.message || err), "加载失败");
      }
    }

    function dedupeForeshadowItems(items) {
      const latest = {};
      (items || []).forEach(item => {
        const key = item.id || item.keyword;
        if (!key) return;
        if (!latest[key] || Number(item.chapter || 0) >= Number(latest[key].chapter || 0)) latest[key] = item;
      });
      return Object.values(latest);
    }

    function formatAssistantSync(sync) {
      if (!sync) return "";
      const lines = ["", "## 插件资料同步"];
      const resolved = dedupeForeshadowItems(sync.foreshadows?.resolved);
      const advanced = dedupeForeshadowItems(sync.foreshadows?.advanced);
      if (resolved.length) {
        lines.push(`- 伏笔已回收：${resolved.length} 条`);
        resolved.slice(0, 12).forEach(item => lines.push(`  - ${item.id || ""} ${item.keyword || ""}（第${item.chapter || ""}章）`));
      }
      if (advanced.length) {
        lines.push(`- 伏笔已推进：${advanced.length} 条`);
        advanced.slice(0, 12).forEach(item => lines.push(`  - ${item.id || ""} ${item.keyword || ""}（第${item.chapter || ""}章，未结案）`));
      }
      if (sync.storyStatePath) lines.push(`- 故事状态：${sync.storyStatePath}`);
      if (sync.summaryPath) lines.push(`- 章节摘要：${sync.summaryPath}`);
      if (lines.length === 2) lines.push("- 未触发新的伏笔回收或人物状态更新。");
      return lines.join("\n");
    }

    async function syncProjectState() {
      setOutput("正在同步章节资料...");
      try {
        const data = await post("/api/sync-state", payload());
        await scan();
        setOutput(
          `已同步章节资料：${data.count} 章\n本地摘要：${data.summaryCount} 条\n状态文件：${data.statePath}\n章节：${data.chapters.join("、")}${formatAssistantSync(data.assistantSync)}`,
          "同步完成"
        );
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    async function refreshOutline() {
      setOutput("正在从大纲解析人物、关系、组织、世界观...");
      try {
        const data = await post("/api/refresh-outline", payload());
        await scan();
        setOutput(data.text || "大纲解析完成", "大纲刷新");
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    async function buildVectorIndex() {
      setOutput("正在构建章节正文向量索引...");
      try {
        const data = await post("/api/build-vector-index", payload());
        await scan();
        setOutput(data.text || "向量索引构建完成", "向量索引");
      } catch (err) {
        setOutput(String(err.message || err), "错误");
      }
    }

    document.addEventListener("dblclick", (event) => {
      if (document.getElementById("title").textContent !== "大纲") return;
      const selection = window.getSelection().toString() || "";
      const text = selection || document.getElementById("output").textContent;
      const match = text.match(/第(\d+)章/);
      if (match) {
        document.getElementById("chapter").value = match[1];
        selectChapterFileByNumber();
      }
    });

    document.getElementById("chapter").addEventListener("change", () => {
      saveWorkspaceSettings();
      selectChapterFileByNumber();
      updateHeaderMeta();
    });
    document.getElementById("chapter").addEventListener("input", () => {
      saveWorkspaceSettings();
      selectChapterFileByNumber();
      updateHeaderMeta();
    });
    document.getElementById("project").addEventListener("change", () => {
      loadProject({ silent: true });
    });
    document.getElementById("words").addEventListener("change", saveWorkspaceSettings);
    document.getElementById("searchQuery").addEventListener("change", saveWorkspaceSettings);
    document.getElementById("searchQuery").addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchProject();
      }
    });
    document.getElementById("auditFile").addEventListener("change", () => {
      syncChapterFromSelectedFile();
      saveWorkspaceSettings();
    });

    async function contextPack() {
      setOutput("生成上下文中...");
      try {
        const data = await post("/api/context", payload());
        setOutput(data.text, `第${payload().chapter}章上下文`);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function chapterPlan() {
      setOutput("生成章节计划中...");
      try {
        const data = await post("/api/plan", payload());
        setOutput(data.text, `第${payload().chapter}章写作计划`);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function preflightChapter() {
      setOutput("生成前检查中...");
      try {
        const data = await post("/api/preflight", payload());
        state.lastPreflight = data;
        const suffix = data.canProceed
          ? "\n\n【可以生成】点击「重新生成章节」将按同一套流程生成并覆盖当前章节正文。"
          : "\n\n【暂不建议生成】仍有阻断项，重新生成时会再次提示确认。";
        setOutput(data.text + suffix, `第${payload().chapter}章生成前检查`);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function foreshadowPlan() {
      setOutput("整理伏笔回收计划中...");
      try {
        const data = await post("/api/foreshadow-plan", payload());
        setOutput(data.text, `第${payload().chapter}章伏笔回收计划`);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function roadmap() {
      setOutput("生成后续路线图中...");
      try {
        const data = await post("/api/roadmap", payload());
        setOutput(data.text, "后续路线图");
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function diagnoseProject() {
      setOutput("诊断项目中...");
      try {
        const data = await post("/api/diagnose", payload());
        setOutput(data.text, "项目诊断");
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function listBackups() {
      setOutput("读取备份中...");
      try {
        const data = await post("/api/backups", payload());
        document.getElementById("title").textContent = "备份管理";
        state.copyText = data.text;
        renderBackups(data.backups || []);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function searchProject() {
      const query = document.getElementById("searchQuery").value.trim();
      if (!query) {
        setOutput("请输入要检索的关键词。", "全文检索");
        return;
      }
      setOutput("检索中...");
      try {
        const data = await post("/api/search", payload({ query }));
        document.getElementById("title").textContent = "全文检索";
        state.copyText = data.text;
        renderSearchResults(data.results || []);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function relationshipGraph() {
      activateTab("relationships");
      await loadRelationshipGraphTab({ scope: state.graphScope });
    }

    async function restoreBackup(path, target) {
      if (!target) {
        setOutput("无法识别这个备份对应的目标文件，已取消恢复。", "备份管理");
        return;
      }
      const ok = confirm(`将把备份恢复到目标文件：\n${target}\n\n恢复前会自动备份当前目标文件。继续吗？`);
      if (!ok) return;
      try {
        const data = await post("/api/restore-backup", payload({ backupPath: path }));
        await scan();
        setOutput(`已恢复备份。\n目标：${data.targetPath}\n恢复前备份：${data.preRestoreBackup || "目标文件原本不存在"}\n来源：${data.backupPath}`, "备份恢复");
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function promptPack() {
      setOutput("生成提示词中...");
      try {
        const data = await post("/api/prompt", payload());
        setOutput(data.text, `第${payload().chapter}章提示词`);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function auditChapter() {
      setOutput("审查中...");
      try {
        syncChapterFromSelectedFile();
        const data = await post("/api/audit", payload());
        if (data.analysis) await scan();
        setOutput(
          (data.auditPath ? `已保存审查：${data.auditPath}` : "") +
          formatAssistantSync(data.analysis?.assistantSync) +
          "\n\n" + data.text,
          "审查报告"
        );
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function reviseChapter() {
      syncChapterFromSelectedFile();
      const file = document.getElementById("auditFile").value;
      const name = file ? file.split(/[\\\\/]/).pop() : `第${payload().chapter}章`;
      const ok = confirm(`将根据审查报告自动修改：${name}\\n\\n会先保存备份，再覆盖原章节正文。继续吗？`);
      if (!ok) return;
      setOutput("正在审查并自动修改正文...");
      try {
        const data = await post("/api/revise", reviewPayload());
        await scan();
        document.getElementById("auditFile").value = data.chapterPath;
        setOutput(
          `已自动修改：${data.chapterPath}\n备份文件：${data.backupPath}\n审查报告：${data.auditPath}${formatAssistantSync(data.analysis?.assistantSync)}\n\n` + data.auditText,
          "自动修改完成",
          data.text || data.auditText
        );
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function rewriteChapter() {
      syncChapterFromSelectedFile();
      const chapter = Number(document.getElementById("chapter").value) || payload().chapter;
      const file = document.getElementById("auditFile").value;
      const name = file ? file.split(/[\\\\/]/).pop() : `第${chapter}章`;
      if (!file) {
        showToast("请先在章节列表选中要重写的章节");
        return;
      }
      const note = prompt(
        `将用 ${reviewApiLabel()} 重写：${name}\\n\\n` +
        "会保留剧情与大纲方向，主要改善文笔、去 AI 味。\\n" +
        "原文件会先备份再覆盖。\\n\\n" +
        "可输入补充要求（留空则使用默认反 AI 规则）：",
        ""
      );
      if (note === null) return;
      setLoading(true, `正在重写第${chapter}章...`);
      try {
        const res = await fetch("/api/rewrite", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(reviewPayload({
            file,
            chapter,
            rewriteNote: note.trim(),
          })),
        });
        const data = await res.json();
        setLoading(false);
        if (!res.ok) throw new Error(data.error || "重写失败");
        await scan();
        document.getElementById("auditFile").value = data.chapterPath;
        const pipelineNote = formatPipelineSummary(data.pipeline);
        let qualityNote = "";
        if (data.qualityWarnings?.length) {
          qualityNote = `\\n\\n## 质量提醒\\n- ${data.qualityWarnings.join("\\n- ")}`;
        }
        setOutput(
          `已重写：${data.chapterPath}\\n` +
          `备份文件：${data.backupPath}\\n` +
          `审查报告：${data.auditPath}\\n` +
          `使用模型温度：${data.temperatureUsed}${pipelineNote ? "\\n" + pipelineNote : ""}` +
          `${qualityNote}\\n\\n## 审查结果\\n${data.auditText || ""}\\n\\n## 重写后正文\\n${data.text}`,
          `第${chapter}章重写完成`,
          data.text
        );
        showToast(`第${chapter}章已重写`);
      } catch (err) {
        setLoading(false);
        setOutput(String(err.message || err), "错误");
      }
    }

    async function openChapter(path) {
      setOutput("读取章节中...", "章节正文");
      try {
        const data = await post("/api/read-file", { path });
        document.getElementById("auditFile").value = path;
        const chapter = path.match(/第\s*0*(\d+)\s*章/);
        if (chapter) document.getElementById("chapter").value = chapter[1];
        setOutput(data.text, data.name, data.text);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    function currentChapterFile() {
      const chapter = Number(document.getElementById("chapter").value) || payload().chapter;
      return (state.scan?.chapters || []).find(item => Number(item.number) === chapter) || null;
    }

    async function regenerateChapter() {
      const chapter = Number(document.getElementById("chapter").value) || payload().chapter;
      if (!state.scan) await scan();

      const existing = currentChapterFile();
      if (existing?.path) {
        const overwriteOk = confirm(
          `第${chapter}章正文已存在：${existing.name}\n\n重新生成将覆盖该文件。继续吗？`
        );
        if (!overwriteOk) return;
      }

      setOutput(`正在检查第${chapter}章...`, `第${chapter}章生成前检查`);
      try {
        const preflight = await post("/api/preflight", payload());
        state.lastPreflight = preflight;

        const notices = [];
        if (preflight.blockers?.length) {
          notices.push(`【阻断项】\n${preflight.blockers.join("\n")}`);
        }
        if (preflight.warnings?.length) {
          notices.push(`【风险提醒】\n${preflight.warnings.slice(0, 6).join("\n")}`);
        }
        const needForce = !preflight.canProceed;
        if (notices.length) {
          const proceed = confirm(
            `${notices.join("\n\n")}\n\n仍要继续重新生成第${chapter}章吗？`
          );
          if (!proceed) {
            setOutput(preflight.text, `第${chapter}章生成前检查`);
            return;
          }
        }

        let syncedBeforeDraft = false;
        if (preflight.autoSyncRecommended) {
          setOutput("检测到章节资料未同步，正在自动同步...");
          await post("/api/sync-state", payload());
          await scan();
          syncedBeforeDraft = true;
        }

        setLoading(true, `正在重新生成第${chapter}章正文...`);
        const res = await fetch("/api/draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload({
            force: needForce || !!notices.length,
            autoSync: !syncedBeforeDraft,
          })),
        });
        const data = await res.json();
        setLoading(false);
        if (!res.ok) {
          if (res.status === 409 && data.preflight) {
            setOutput(`${data.text || data.error}\n\n【已取消重新生成】`, `第${chapter}章生成前检查未通过`);
            return;
          }
          throw new Error(data.error || "重新生成失败");
        }

        await scan();
        document.getElementById("auditFile").value = data.chapterPath;
        const pipelineNote = formatPipelineSummary(data.pipeline);
        let qualityNote = "";
        if (data.qualityWarnings?.length) {
          qualityNote = `\n\n## 质量提醒\n- ${data.qualityWarnings.join("\n- ")}\n可到「问题总览」继续处理剩余问题。`;
        } else if (data.pipeline?.fixed) {
          qualityNote = "\n\n## 质量提醒\n- 定点修后未检测到剩余可修复问题。";
        }
        setOutput(
          `已重新生成并保存：${data.chapterPath}\n${pipelineNote || "已自动审查"}\n审查报告：${data.auditPath}\n生成温度：${data.temperatureUsed}\n资料状态已更新：人物 ${data.analysis?.characters?.length || 0} 个，关系 ${data.analysis?.relationships?.length || 0} 条，伏笔命中 ${(data.analysis?.foreshadows || []).filter(f => f.hit).length} 个。${formatAssistantSync(data.analysis?.assistantSync)}${qualityNote}\n\n## 审查结果\n${data.auditText || "审查报告已保存。"}\n\n## 章节正文\n${data.text}`,
          `第${chapter}章正文`,
          data.text
        );
        if (data.pipeline?.fixed) {
          showToast(`第${chapter}章已重新生成：审计 → 定点修 → 再审计`);
        } else if (data.suggestedFix) {
          showToast(`第${chapter}章已重新生成，仍有 ${data.qualityWarnings.length} 项待处理`);
        } else {
          showToast(`第${chapter}章已重新生成并完成审计`);
        }
      } catch (err) {
        setLoading(false);
        setOutput(String(err.message || err), "错误");
      }
    }

    async function exportProject() {
      setOutput("导出中...");
      try {
        const data = await post("/api/export", payload());
        setOutput(data.text, "项目资料导出");
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function exportManuscript() {
      setOutput("导出正文合集...");
      try {
        const data = await post("/api/export-manuscript", payload());
        setOutput(`已导出正文合集：${data.path}\n章节数：${data.count}\n\n${data.text}`, "正文合集", data.text);
      } catch (err) { setOutput(String(err.message || err), "错误"); }
    }

    async function copyOutput() {
      await navigator.clipboard.writeText(state.copyText || document.getElementById("output").textContent);
      showToast("已复制到剪贴板");
    }

    loadWorkspaceSettings();
    loadApiSettings();
    loadWritingRules();
    updateHeaderMeta();
    loadProject({ silent: true });
  </script>
</body>
</html>
"""


def chapter_number_from_path(path: str) -> int | None:
    match = re.search(r"第\s*0*(\d+)\s*章", Path(path).name)
    return int(match.group(1)) if match else None


def to_json(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def parse_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise ValueError("请求体格式错误")
    return data


def append_writing_rules(prompt: str, body: dict[str, Any]) -> str:
    rules = str(body.get("writingRules") or "").strip()
    if not rules:
        return prompt
    return f"{prompt}\n\n## 用户自定义写作规则\n{rules}\n"


def append_writing_extras(prompt: str, body: dict[str, Any], root: Path) -> str:
    return append_style_reference(append_writing_rules(prompt, body), root)


def custom_writing_rules_section(body: dict[str, Any]) -> str:
    rules = str(body.get("writingRules") or "").strip()
    if not rules:
        return ""
    return f"## 用户自定义写作规则\n{rules}\n\n"


def build_quality_items(data) -> list[dict[str, Any]]:
    items = []
    for path in data.chapters:
        chapter = chapter_number_from_path(str(path))
        if not chapter:
            continue
        text = read_text(path)
        stats = audit_stats(data, text, chapter)
        items.append(quality_item_from_stats(stats, chapter, path.name, str(path)))
    return sorted(items, key=lambda item: int(item["chapter"]))


def build_project_issues(data) -> dict[str, Any]:
    from .cli import check_character_consistency, check_foreshadow_health, check_outline_deviation, chapter_number_from_name
    chapter_numbers = sorted(ch for ch in (chapter_number_from_name(p) for p in data.chapters) if ch)
    latest = chapter_numbers[-1] if chapter_numbers else 0
    return {
        "characterIssues": check_character_consistency(data),
        "foreshadowIssues": check_foreshadow_health(data, latest),
        "outlineIssues": check_outline_deviation(data),
    }


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def infer_backup_target(data, backup_path: Path) -> Path | None:
    name = backup_path.name
    if ".bak-" in backup_path.stem:
        target_name = re.sub(r"\.bak-\d{8}-\d{6}$", "", backup_path.stem) + backup_path.suffix
        return backup_path.with_name(target_name)
    if backup_path.parent == data.root / ".novelbuddy" / "backups" and name.startswith("outlines-"):
        return data.outline_source or data.root / ".novel-assistant" / "data" / "outlines.json"
    return None


def list_project_backups(data) -> list[dict[str, Any]]:
    candidates = [
        path
        for path in data.root.rglob("*")
        if path.is_file()
        and (
            ".bak-" in path.stem
            or is_within(path, data.root / ".novelbuddy" / "backups")
        )
    ]
    items = []
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        target = infer_backup_target(data, path)
        kind = "章节备份" if ".bak-" in path.stem else "资料备份"
        items.append(
            {
                "kind": kind,
                "name": path.name,
                "path": str(path),
                "target": str(target) if target else "",
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return items


class NovelBuddyHandler(BaseHTTPRequestHandler):
    server_version = "NovelBuddy/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            data = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            body = parse_body(self)
            route = urllib.parse.urlparse(self.path).path
            if route == "/api/scan":
                return self.handle_scan(body)
            if route == "/api/sync-state":
                return self.handle_sync_state(body)
            if route == "/api/context":
                return self.handle_context(body)
            if route == "/api/plan":
                return self.handle_plan(body)
            if route == "/api/preflight":
                return self.handle_preflight(body)
            if route == "/api/foreshadow-plan":
                return self.handle_foreshadow_plan(body)
            if route == "/api/roadmap":
                return self.handle_roadmap(body)
            if route == "/api/diagnose":
                return self.handle_diagnose(body)
            if route == "/api/backups":
                return self.handle_backups(body)
            if route == "/api/restore-backup":
                return self.handle_restore_backup(body)
            if route == "/api/search":
                return self.handle_search(body)
            if route == "/api/relationship-graph":
                return self.handle_relationship_graph(body)
            if route == "/api/prompt":
                return self.handle_prompt(body)
            if route == "/api/outline":
                return self.handle_outline(body)
            if route == "/api/audit":
                return self.handle_audit(body)
            if route == "/api/revise":
                return self.handle_revise(body)
            if route == "/api/rewrite":
                return self.handle_rewrite(body)
            if route == "/api/fix-chapter":
                return self.handle_fix_chapter(body)
            if route == "/api/export":
                return self.handle_export(body)
            if route == "/api/export-manuscript":
                return self.handle_export_manuscript(body)
            if route == "/api/draft":
                return self.handle_draft(body)
            if route == "/api/read-file":
                return self.handle_read_file(body)
            if route == "/api/test-connection":
                return self.handle_test_connection(body)
            if route == "/api/save-entity":
                return self.handle_save_entity(body)
            if route == "/api/delete-entity":
                return self.handle_delete_entity(body)
            if route == "/api/batch-analyze":
                return self.handle_batch_analyze(body)
            if route == "/api/self-check":
                return self.handle_self_check(body)
            if route == "/api/refine-templates":
                return self.handle_refine_templates(body)
            if route == "/api/style-reference":
                return self.handle_style_reference(body)
            if route == "/api/style-reference/extract":
                return self.handle_style_reference_extract(body)
            if route == "/api/style-reference/search":
                return self.handle_style_reference_search(body)
            if route == "/api/style-reference/save":
                return self.handle_style_reference_save(body)
            if route == "/api/style-reference/clear":
                return self.handle_style_reference_clear(body)
            if route == "/api/refresh-outline":
                return self.handle_refresh_outline(body)
            if route == "/api/build-vector-index":
                return self.handle_build_vector_index(body)
            to_json(self, 404, {"error": "未知接口"})
        except Exception as exc:
            to_json(self, 500, {"error": str(exc)})

    def project_data(self, body: dict[str, Any]):
        project = str(body.get("project") or DEFAULT_PROJECT)
        return load_project(project, require_outline_md=True)

    def handle_scan(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        novelbuddy_state = load_novelbuddy_state(data.root)
        quality = build_quality_items(data)
        chapters = [
            {"name": p.name, "path": str(p), "number": chapter_number_from_path(str(p))}
            for p in data.chapters
        ]
        chapter_numbers = sorted(int(ch["number"]) for ch in chapters if ch.get("number"))
        latest_chapter = chapter_numbers[-1] if chapter_numbers else 0
        next_chapter = latest_chapter + 1 if latest_chapter else 1
        characters = [
            decorate_entity_for_ui(
                "character",
                {
                    "id": c.get("id", ""),
                    "name": c.get("name", ""),
                    "role": c.get("role", ""),
                    "description": c.get("description", ""),
                    "personality": c.get("personality", ""),
                    "background": c.get("background", ""),
                },
            )
            for c in data.characters
        ]
        relationships = [relationship_display(data, rel) for rel in data.relationships]
        organizations = [
            decorate_entity_for_ui("organization", org)
            for org in load_organizations(data.root)
        ]
        world = normalize_world_for_ui(data.world)
        foreshadows = [
            decorate_entity_for_ui(
                "foreshadow",
                {
                    "id": f.get("id", ""),
                    "keyword": f.get("keyword", ""),
                    "description": f.get("description", ""),
                    "status": f.get("status", ""),
                    "importance": f.get("importance", ""),
                    "plantedChapter": f.get("plantedChapter", ""),
                    "invalidAfter": f.get("invalidAfter") or f.get("invalidAfterChapter", ""),
                },
            )
            for f in data.foreshadows
        ]
        summary = (
            f"项目: {data.root}\n"
            f"人物: {len(data.characters)}\n"
            f"关系: {len(data.relationships)}\n"
            f"大纲: {len(data.outlines)}\n"
            f"摘要: {len(data.summaries)}\n"
            f"伏笔: {len(data.foreshadows)}\n"
            f"章节文件: {len(data.chapters)}\n"
            f"已写到: 第{latest_chapter}章\n"
            f"下一章: 第{next_chapter}章\n"
            f"世界观: {'有' if data.world else '无'}\n"
            f"大纲来源: {data.outline_source or '无'}\n"
            f"大纲文件: {data.outline_md_source.name if data.outline_md_source else '无'}"
        )
        to_json(
            self,
            200,
            {
                "summary": summary,
                "counts": {
                    "characters": len(data.characters),
                    "relationships": len(data.relationships),
                    "outlines": len(data.outlines),
                    "summaries": len(data.summaries),
                    "foreshadows": len(data.foreshadows),
                    "organizations": len(organizations),
                    "chapters": len(data.chapters),
                },
                "progress": {
                    "latestChapter": latest_chapter,
                    "nextChapter": next_chapter,
                },
                "chapters": chapters,
                "characters": characters,
                "relationships": relationships,
                "outlines": [
                    {
                        "chapterNumber": o.get("chapterNumber", ""),
                        "title": o.get("title", ""),
                        "content": o.get("content", ""),
                    }
                    for o in data.outlines
                ],
                "foreshadows": foreshadows,
                "organizations": organizations,
                "world": world,
                "quality": quality,
                "projectIssues": build_project_issues(data),
                "volumes": data.volumes or [],
                "novelbuddyState": novelbuddy_state,
                "outlineMdSource": str(data.outline_md_source) if data.outline_md_source else None,
            },
        )

    def handle_sync_state(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        result = sync_project_state(data)
        to_json(self, 200, result)

    def handle_refresh_outline(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        config = self.api_config_from_body(body)
        if not config.get("api_key"):
            to_json(self, 400, {"error": "缺少 API Key。请在页面填写 API Key，或设置 NOVELBUDDY_API_KEY 环境变量。"})
            return
        result = generate_outline_data(data, config)
        if "error" in result:
            to_json(self, 400, result)
            return
        to_json(self, 200, {"text": f"大纲解析完成：人物 {result['characters']} 个，关系 {result['relationships']} 条，组织 {result['organizations']} 个，世界观 {'已生成' if result['worldview'] else '未提取到'}", **result})

    def handle_build_vector_index(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        from .vector_search import build_chapter_vector_index
        result = build_chapter_vector_index(data.root)
        if "error" in result:
            to_json(self, 400, result)
            return
        to_json(self, 200, {"text": f"向量索引构建完成：新增 {result['new']} 条，跳过 {result['skipped']} 条已存在，共 {result['total']} 条（{result['chapters']} 个章节文件）", **result})

    def handle_context(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        to_json(self, 200, {"text": build_context(data, chapter)})

    def handle_plan(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        words = int(body.get("words") or 3000)
        to_json(self, 200, {"text": build_chapter_plan(data, chapter, words)})

    def handle_preflight(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        words = int(body.get("words") or 3000)
        config = self.api_config_from_body(body)
        base_temperature = float(config.get("temperature") or 0.6)
        result = run_writing_preflight(
            data,
            chapter,
            words=words,
            api_key=str(config.get("api_key") or ""),
            api_base=str(config.get("api_base") or ""),
            model=str(config.get("model") or ""),
            writing_rules=str(body.get("writingRules") or ""),
            base_temperature=base_temperature,
        )
        prompt = append_writing_extras(build_prompt(data, chapter, words, 4500), body, data.root)
        result["promptLength"] = len(prompt)
        to_json(self, 200, result)

    def handle_foreshadow_plan(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        outline = find_outline(data, chapter)
        outline_text = f"{outline.get('title', '')}\n{outline.get('content', '')}" if outline else ""
        selected = select_foreshadows(data, chapter, limit=20, include_expired=True)

        buckets: dict[str, list[dict[str, Any]]] = {
            "已过期": [],
            "临近失效": [],
            "拖延较久": [],
            "本章关注": [],
        }
        for item in selected:
            urgency = foreshadow_urgency(item, chapter)
            buckets.setdefault(urgency, []).append(item)

        def relevance(item: dict[str, Any]) -> str:
            keyword = str(item.get("keyword") or "").strip()
            description = str(item.get("description") or "")
            if keyword and keyword in outline_text:
                return "大纲直接相关"
            words = [part for part in re.split(r"[，。；、\s]+", description) if len(part) >= 2]
            if any(part in outline_text for part in words[:8]):
                return "大纲间接相关"
            return "按优先级关注"

        lines = [f"# 第{chapter}章伏笔回收计划", ""]
        if outline:
            lines.append(f"本章大纲：{outline.get('title', '') or f'第{chapter}章'}")
        else:
            lines.append("本章大纲：缺失")
        lines.append(f"待关注伏笔：{len(selected)} 条")
        lines.append("")

        if not selected:
            lines.append("当前没有需要本章关注的未回收伏笔。")
        else:
            for title in ("已过期", "临近失效", "拖延较久", "本章关注"):
                items = buckets.get(title) or []
                if not items:
                    continue
                lines.append(f"## {title}")
                for item in items:
                    planted = item.get("plantedChapter", "")
                    invalid_after = item.get("invalidAfter") or item.get("invalidAfterChapter") or ""
                    deadline = f"｜有效至第{invalid_after}章" if invalid_after else ""
                    strategy = "补救解释或呈现后果" if title == "已过期" else "自然推进或回收"
                    if title == "本章关注":
                        strategy = "相关则推进，不相关只轻触"
                    lines.append(
                        f"- {item.get('id', '')} [{item.get('importance', '')}] {item.get('keyword', '')}"
                        f"｜第{planted}章埋入{deadline}｜{relevance(item)}｜建议：{strategy}"
                    )
                    lines.append(f"  {truncate(str(item.get('description', '')), 140)}")
                lines.append("")

        lines.append("## 写作提醒")
        lines.append("- 不要为了回收伏笔打断本章主线。")
        lines.append("- 临近失效的伏笔优先给出新信息、代价或选择。")
        lines.append("- 已过期伏笔不要强行当作按时回收，只能补救解释、制造后果或转成新悬念。")
        lines.append("- 回收不是重复关键词，要让人物行动、物证或场景状态发生变化。")

        to_json(
            self,
            200,
            {
                "chapter": chapter,
                "items": selected,
                "text": "\n".join(lines).strip() + "\n",
            },
        )

    def handle_roadmap(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapters = [chapter_number_from_path(str(path)) for path in data.chapters]
        chapter_numbers = sorted(int(num) for num in chapters if num)
        latest = chapter_numbers[-1] if chapter_numbers else 0
        start = int(body.get("chapter") or 0) or latest + 1 or 1
        if start <= latest:
            start = latest + 1
        count = int(body.get("count") or 5)
        count = max(1, min(count, 10))

        lines = ["# 后续路线图", f"已写到：第{latest}章", f"路线起点：第{start}章", ""]
        for chapter in range(start, start + count):
            outline = find_outline(data, chapter)
            existing = find_chapter_file(data, chapter)
            title = str(outline.get("title", "")) if outline else ""
            content = str(outline.get("content", "")) if outline else ""
            foreshadows = select_foreshadows(data, chapter, limit=5)
            lines.append(f"## 第{chapter}章 {title or '未命名'}")
            lines.append(f"- 状态：{'已生成' if existing else '未生成'}")
            if existing:
                lines.append(f"- 文件：{existing}")
            if outline:
                lines.append(f"- 大纲：{truncate(content, 180)}")
            else:
                lines.append("- 大纲：缺失")
            if foreshadows:
                lines.append("- 伏笔关注：" + "；".join(
                    f"{fw.get('keyword', '')}({fw.get('importance', '')})" for fw in foreshadows if fw.get("keyword")
                ))
            else:
                lines.append("- 伏笔关注：无")
            lines.append("")

        to_json(
            self,
            200,
            {
                "latestChapter": latest,
                "startChapter": start,
                "count": count,
                "text": "\n".join(lines).strip() + "\n",
            },
        )

    def handle_diagnose(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        state = load_novelbuddy_state(data.root)
        chapter_numbers = sorted(
            int(num)
            for num in (chapter_number_from_path(str(path)) for path in data.chapters)
            if num
        )
        latest = chapter_numbers[-1] if chapter_numbers else 0
        expected = set(range(1, latest + 1)) if latest else set()
        actual = set(chapter_numbers)
        missing_chapters = sorted(expected - actual)
        outline_numbers = {int(item.get("chapterNumber") or 0) for item in data.outlines if item.get("chapterNumber")}
        missing_outlines = [chapter for chapter in range(1, latest + 6) if chapter not in outline_numbers]
        state_numbers = {int(key) for key in state.get("chapters", {}).keys() if str(key).isdigit()}
        stale_state = sorted(actual - state_numbers)
        local_summary_numbers = {int(key) for key in state.get("localSummaries", {}).keys() if str(key).isdigit()}
        stale_local_summaries = sorted(actual - local_summary_numbers)
        formal_summary_numbers = {int(item.get("chapterNumber") or 0) for item in data.summaries if item.get("chapterNumber")}
        formal_summary_latest = max(formal_summary_numbers) if formal_summary_numbers else 0

        quality = build_quality_items(data)
        risky_quality = [
            item for item in quality
            if item.get("aiRiskCount") or item.get("formatRiskCount") or item.get("forbiddenCount")
        ]
        overdue_foreshadows = []
        aging_foreshadows = []
        for fw in data.foreshadows:
            if fw.get("status") == "resolved":
                continue
            planted = int(fw.get("plantedChapter") or 0)
            invalid_after = int(fw.get("invalidAfter") or fw.get("invalidAfterChapter") or 999999)
            if latest and invalid_after < latest:
                overdue_foreshadows.append(fw)
            elif latest and planted and latest - planted >= 8:
                aging_foreshadows.append(fw)

        issues: list[str] = []
        warnings: list[str] = []
        ok: list[str] = []
        if missing_chapters:
            issues.append("章节缺口：" + "、".join(f"第{chapter}章" for chapter in missing_chapters))
        else:
            ok.append("已生成章节编号连续。")
        if missing_outlines:
            warnings.append("近期待写大纲缺失：" + "、".join(f"第{chapter}章" for chapter in missing_outlines[:10]))
        else:
            ok.append("已写进度后 5 章大纲齐全。")
        if stale_state or stale_local_summaries:
            warnings.append("本地资料状态落后，建议点“同步章节资料”。")
        else:
            ok.append("本地章节资料已覆盖现有正文。")
        if formal_summary_latest < latest:
            warnings.append(f"原插件摘要只到第{formal_summary_latest}章，NovelBuddy 会使用本地摘要补齐。")
        if overdue_foreshadows:
            issues.append("已过期未回收伏笔：" + "、".join(str(fw.get("keyword", "")) for fw in overdue_foreshadows[:8]))
        if aging_foreshadows:
            warnings.append("拖延较久伏笔：" + "、".join(str(fw.get("keyword", "")) for fw in aging_foreshadows[:8]))
        if risky_quality:
            warnings.append(f"有 {len(risky_quality)} 章存在文本质量风险，可到“问题总览”逐章处理。")
        else:
            ok.append("已生成章节未发现明显文本质量风险。")

        status = "需要处理" if issues else "基本可继续"
        lines = ["# 项目诊断", f"结论：{status}", f"已写到：第{latest}章", ""]
        if issues:
            lines.append("## 需要优先处理")
            lines.extend(f"- {item}" for item in issues)
            lines.append("")
        if warnings:
            lines.append("## 风险提醒")
            lines.extend(f"- {item}" for item in warnings)
            lines.append("")
        if ok:
            lines.append("## 正常项")
            lines.extend(f"- {item}" for item in ok)
            lines.append("")
        lines.append("## 统计")
        lines.append(f"- 正文文件：{len(data.chapters)}")
        lines.append(f"- 大纲：{len(data.outlines)}")
        lines.append(f"- 原插件摘要：{len(data.summaries)}")
        lines.append(f"- NovelBuddy 本地摘要：{len(state.get('localSummaries', {}))}")
        lines.append(f"- 伏笔：{len(data.foreshadows)}")
        lines.append(f"- 文本质量风险章节：{len(risky_quality)}")
        to_json(
            self,
            200,
            {
                "status": status,
                "issues": issues,
                "warnings": warnings,
                "ready": ok,
                "text": "\n".join(lines).strip() + "\n",
            },
        )

    def handle_backups(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        backups = list_project_backups(data)
        lines = ["# 备份管理", f"备份数量：{len(backups)}", ""]
        for item in backups[:80]:
            lines.append(f"- [{item['kind']}] {item['name']}")
            lines.append(f"  目标：{item['target'] or '无法自动识别'}")
            lines.append(f"  时间：{item['modified']}｜大小：{item['size']} 字节")
        to_json(self, 200, {"backups": backups, "text": "\n".join(lines).strip() + "\n"})

    def handle_restore_backup(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        backup_path = Path(str(body.get("backupPath") or "")).resolve()
        if not backup_path.exists() or not backup_path.is_file():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")
        if not is_within(backup_path, data.root):
            raise ValueError("只能恢复当前项目目录内的备份。")
        target = infer_backup_target(data, backup_path)
        if not target:
            raise ValueError("无法识别备份对应的目标文件。")
        target = target.resolve()
        if not is_within(target, data.root):
            raise ValueError("目标文件不在当前项目目录内。")
        pre_restore_backup = ""
        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            pre_path = target.with_name(f"{target.stem}.pre-restore-{stamp}{target.suffix}")
            pre_path.write_text(target.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            pre_restore_backup = str(pre_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(backup_path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        to_json(
            self,
            200,
            {
                "backupPath": str(backup_path),
                "targetPath": str(target),
                "preRestoreBackup": pre_restore_backup,
            },
        )

    def handle_search(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        query = str(body.get("query") or "").strip()
        if not query:
            raise ValueError("检索关键词不能为空。")
        results = hybrid_search_project(data, query, limit=80)
        if results:
            mode = "混合检索（向量+BM25）" if any(item.get("searchMethod") == "hybrid" for item in results) else "检索"
            lines = [f"# 全文检索（{mode}）", f"关键词：{query}", f"结果：{len(results)}", ""]
            for item in results:
                score = f"｜相关度 {item.get('score', '-')}" if item.get("score") is not None else ""
                method = item.get("searchMethod")
                method_text = f"｜{method}" if method else ""
                lines.append(f"- [{item['kind']}] {item['title']}{score}{method_text}｜{item['location']}")
                lines.append(f"  {item['snippet']}")
            to_json(self, 200, {"query": query, "results": results, "text": "\n".join(lines).strip() + "\n"})
            return

        results_legacy: list[dict[str, Any]] = []

        def snippet(text: str, limit: int = 160) -> str:
            clean = re.sub(r"\s+", " ", text).strip()
            index = clean.find(query)
            if index < 0:
                return truncate(clean, limit)
            start = max(0, index - 55)
            end = min(len(clean), index + len(query) + 85)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(clean) else ""
            return prefix + clean[start:end] + suffix

        for path in data.chapters:
            text = read_text(path)
            count = text.count(query)
            if count:
                chapter = chapter_number_from_path(str(path)) or ""
                results_legacy.append(
                    {
                        "kind": "正文",
                        "title": path.name,
                        "location": f"第{chapter}章｜{count} 处",
                        "snippet": snippet(text),
                        "path": str(path),
                    }
                )

        for outline in data.outlines:
            content = f"{outline.get('title', '')}\n{outline.get('content', '')}"
            if query in content:
                chapter = outline.get("chapterNumber", "")
                results_legacy.append(
                    {
                        "kind": "大纲",
                        "title": f"第{chapter}章 {outline.get('title', '')}",
                        "location": "大纲",
                        "snippet": snippet(content),
                        "path": "",
                    }
                )

        for char in data.characters:
            content = json.dumps(char, ensure_ascii=False)
            if query in content:
                results_legacy.append(
                    {
                        "kind": "人物",
                        "title": str(char.get("name", "") or char.get("id", "")),
                        "location": str(char.get("role", "")),
                        "snippet": snippet(content),
                        "path": "",
                    }
                )

        for fw in data.foreshadows:
            content = json.dumps(fw, ensure_ascii=False)
            if query in content:
                results_legacy.append(
                    {
                        "kind": "伏笔",
                        "title": str(fw.get("keyword", "") or fw.get("id", "")),
                        "location": f"第{fw.get('plantedChapter', '')}章｜{fw.get('status', '')}",
                        "snippet": snippet(content),
                        "path": "",
                    }
                )

        results = results_legacy[:80]
        lines = ["# 全文检索", f"关键词：{query}", f"结果：{len(results)}", ""]
        for item in results:
            lines.append(f"- [{item['kind']}] {item['title']}｜{item['location']}")
            lines.append(f"  {item['snippet']}")
        to_json(self, 200, {"query": query, "results": results, "text": "\n".join(lines).strip() + "\n"})

    def handle_relationship_graph(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 0)
        scope = str(body.get("scope") or "window").strip().lower()
        if scope not in {"full", "window"}:
            scope = "window"
        result = build_relationship_graph(data, chapter, scope=scope)
        to_json(self, 200, result)

    def handle_prompt(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        words = int(body.get("words") or 3000)
        prompt = append_writing_extras(build_prompt(data, chapter, words, 4500), body, data.root)
        to_json(self, 200, {"text": prompt})

    def handle_outline(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        title = str(body.get("outlineTitle") or "").strip()
        content = str(body.get("outlineContent") or "").strip()
        if not content:
            raise ValueError("大纲内容不能为空。")
        path, backup_path, outline = save_outline(data, chapter, title, content)
        to_json(
            self,
            200,
            {
                "path": str(path),
                "backupPath": str(backup_path) if backup_path else "",
                "outline": {
                    "chapterNumber": outline.get("chapterNumber", ""),
                    "title": outline.get("title", ""),
                    "content": outline.get("content", ""),
                },
            },
        )

    def handle_audit(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 0)
        file_path = Path(str(body.get("file") or ""))
        if (not file_path.exists() or not file_path.is_file()) and chapter:
            file_path = find_chapter_file(data, chapter) or file_path
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"审查文件不存在: {file_path}")
        chapter = int(chapter or chapter_number_from_path(str(file_path)) or 0) or None
        text = read_text(file_path)
        analysis = update_chapter_state(data, chapter, text) if chapter else None
        report = audit_text(data, text, chapter)
        audit_path = file_path.with_name(file_path.stem + "-审查.md")
        audit_path.write_text(report, encoding="utf-8")
        to_json(self, 200, {"text": report, "auditPath": str(audit_path), "analysis": analysis})

    def resolve_chapter_file(self, data, body: dict[str, Any]) -> tuple[int, Path]:
        chapter = int(body.get("chapter") or 0)
        file_path = Path(str(body.get("file") or ""))
        expected = find_chapter_file(data, chapter) if chapter else None
        if chapter and expected:
            file_chapter = chapter_number_from_path(str(file_path)) if file_path.exists() else None
            if not file_path.exists() or not file_path.is_file() or file_chapter != chapter:
                file_path = expected
        elif (not file_path.exists() or not file_path.is_file()) and chapter:
            file_path = expected or file_path
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"章节文件不存在: {file_path}")
        chapter = int(chapter or chapter_number_from_path(str(file_path)) or 0)
        if not chapter:
            raise ValueError("无法识别章节号。")
        return chapter, file_path

    def api_config_from_body(self, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "api_key": str(body.get("apiKey") or os.environ.get("NOVELBUDDY_API_KEY", "")).strip(),
            "api_base": str(body.get("apiBase") or os.environ.get("NOVELBUDDY_API_BASE", "https://api.openai.com/v1")).rstrip("/"),
            "model": str(body.get("model") or os.environ.get("NOVELBUDDY_MODEL", "gpt-4o-mini")),
            "temperature": float(body.get("temperature") or os.environ.get("NOVELBUDDY_TEMPERATURE", "0.6")),
        }

    def _has_review_api_override(self, body: dict[str, Any]) -> bool:
        if any(str(body.get(key) or "").strip() for key in ("reviewApiKey", "reviewApiBase", "reviewModel")):
            return True
        review_temp = body.get("reviewTemperature")
        return review_temp is not None and str(review_temp).strip() != ""

    def review_api_config_from_body(self, body: dict[str, Any]) -> dict[str, Any]:
        default = self.api_config_from_body(body)
        if not self._has_review_api_override(body):
            review_temp = body.get("reviewTemperature")
            if review_temp is None or str(review_temp).strip() == "":
                return default
        review_temp = body.get("reviewTemperature")
        temperature = default["temperature"]
        if review_temp is not None and str(review_temp).strip() != "":
            temperature = float(review_temp)
        return {
            "api_key": str(body.get("reviewApiKey") or default["api_key"]).strip(),
            "api_base": str(body.get("reviewApiBase") or default["api_base"]).strip().rstrip("/"),
            "model": str(body.get("reviewModel") or default["model"]).strip(),
            "temperature": temperature,
        }

    def handle_save_entity(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        entity_type = str(body.get("entityType") or "").strip()
        entity = body.get("entity") or {}
        if not isinstance(entity, dict):
            raise ValueError("实体数据格式无效。")
        result = save_entity(data.root, entity_type, entity)
        to_json(self, 200, result)

    def handle_delete_entity(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        entity_type = str(body.get("entityType") or "").strip()
        item_id = str(body.get("id") or "").strip()
        if not item_id:
            raise ValueError("缺少要删除的实体 ID。")
        result = delete_entity(data.root, entity_type, item_id)
        to_json(self, 200, result)

    def handle_batch_analyze(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapters = body.get("chapters")
        chapter_numbers = [int(num) for num in chapters] if isinstance(chapters, list) else None
        result = batch_analyze_chapters(data, chapter_numbers)
        to_json(self, 200, result)

    def handle_self_check(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        result = self_check_report(data)
        to_json(self, 200, result)

    def handle_refine_templates(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        templates = load_refine_templates(data.root)
        lines = ["# 精修模板", f"数量：{len(templates)}", ""]
        for item in templates[:40]:
            lines.append(f"- {item.get('name', item.get('id', '模板'))}")
            content = str(item.get("content", "") or item.get("prompt", ""))
            if content:
                lines.append(f"  {truncate(content, 120)}")
        to_json(self, 200, {"templates": templates, "text": "\n".join(lines).strip() + "\n"})

    def handle_style_reference(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        reference = load_style_reference(data.root)
        to_json(self, 200, {"reference": reference})

    def handle_style_reference_extract(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        config = self.api_config_from_body(body)
        if not config["api_key"]:
            raise ValueError("缺少 API Key。请先在「API 设置」填写。")
        sample_text = str(body.get("sampleText") or "")
        novel_name = str(body.get("novelName") or "").strip()
        extracted = extract_style_from_text(sample_text, config, novel_name=novel_name)
        reference = save_style_reference(data.root, extracted)
        to_json(self, 200, {"reference": reference})

    def handle_style_reference_search(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        config = self.api_config_from_body(body)
        if not config["api_key"]:
            raise ValueError("缺少 API Key。请先在「API 设置」填写。")
        novel_name = str(body.get("novelName") or "").strip()
        extracted = search_novel_style(novel_name, config)
        reference = save_style_reference(data.root, extracted)
        to_json(self, 200, {"reference": reference})

    def handle_style_reference_save(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        style_guide = str(body.get("styleGuide") or "").strip()
        if not style_guide:
            raise ValueError("文风指南不能为空。")
        reference = save_style_reference(
            data.root,
            {
                "enabled": bool(body.get("enabled")),
                "styleGuide": style_guide,
                "novelName": str(body.get("novelName") or "").strip(),
                "source": str(body.get("source") or "manual").strip() or "manual",
            },
        )
        to_json(self, 200, {"reference": reference})

    def handle_style_reference_clear(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        reference = clear_style_reference(data.root)
        to_json(self, 200, {"reference": reference})

    def handle_test_connection(self, body: dict[str, Any]) -> None:
        if self._has_review_api_override(body) or (
            body.get("reviewTemperature") is not None and str(body.get("reviewTemperature", "")).strip() != ""
        ):
            config = self.review_api_config_from_body(body)
        else:
            config = self.api_config_from_body(body)
        result = test_api_connection(config)
        to_json(self, 200, result)

    def build_ai_revise_prompt(
        self,
        data,
        chapter: int,
        original: str,
        body: dict[str, Any],
        source_text: str | None = None,
    ) -> str:
        return build_ai_revise_prompt(
            data,
            chapter,
            original,
            writing_rules=str(body.get("writingRules") or ""),
            source_text=source_text,
        )

    def handle_revise(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter, file_path = self.resolve_chapter_file(data, body)
        config = self.review_api_config_from_body(body)
        if not config["api_key"]:
            raise ValueError("缺少 API Key。请先在「审查 API」或默认「API 设置」里填写。")
        original = read_text(file_path)
        prompt = append_style_reference(self.build_ai_revise_prompt(data, chapter, original, body), data.root)
        revised = normalize_chapter_text(call_openai_compatible(prompt, config, 0.35))
        if not revised:
            raise ValueError("AI 没有返回修改后的正文。")
        result = save_fixed_chapter(data, chapter, file_path, original, revised)
        result["mode"] = "ai"
        result["fixesApplied"] = ["AI 自动改写"]
        to_json(self, 200, result)

    def handle_rewrite(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter, file_path = self.resolve_chapter_file(data, body)
        config = self.review_api_config_from_body(body)
        if not config["api_key"]:
            raise ValueError("缺少 API Key。请先在「审查 API」或默认「API 设置」里填写。")
        original = read_text(file_path)
        outline = find_outline(data, chapter)
        outline_text = str(outline.get("content", "")) if outline else ""
        base_temperature = float(config.get("temperature") or 0.6)
        temperature = min(
            suggest_chapter_temperature(outline_text, base_temperature),
            0.55,
        )
        prompt = append_style_reference(
            build_rewrite_prompt(
                data,
                chapter,
                original,
                writing_rules=str(body.get("writingRules") or ""),
                rewrite_note=str(body.get("rewriteNote") or ""),
            ),
            data.root,
        )
        rewritten = normalize_chapter_text(call_openai_compatible(prompt, config, temperature))
        if not rewritten:
            raise ValueError("AI 没有返回重写后的正文。")

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = file_path.with_name(f"{file_path.stem}.bak-{stamp}{file_path.suffix}")
        backup_path.write_text(original, encoding="utf-8")
        file_path.write_text(rewritten, encoding="utf-8")

        auto_fix = body.get("autoFix", True) is not False
        pipeline = run_post_generation_pipeline(
            data,
            chapter,
            file_path,
            rewritten,
            config=config,
            writing_rules=str(body.get("writingRules") or ""),
            auto_fix=auto_fix,
            fix_mode=str(body.get("fixMode") or "auto"),
        )
        pipeline["stages"] = ["rewrite", *pipeline.get("stages", [])]
        pipeline["backupPath"] = str(backup_path)

        to_json(
            self,
            200,
            {
                "text": pipeline.get("text", rewritten),
                "chapterPath": str(file_path),
                "backupPath": str(backup_path),
                "auditPath": pipeline.get("auditPath", ""),
                "auditText": pipeline.get("auditText", ""),
                "analysis": pipeline.get("analysis"),
                "qualityWarnings": pipeline.get("qualityWarnings", []),
                "suggestedFix": bool(pipeline.get("suggestedFix")),
                "temperatureUsed": temperature,
                "pipeline": {
                    "stages": pipeline.get("stages", []),
                    "fixed": bool(pipeline.get("fixed")),
                    "fixesApplied": pipeline.get("fixesApplied", []),
                    "backupPath": pipeline.get("backupPath", ""),
                    "initialStats": pipeline.get("initialStats"),
                    "finalStats": pipeline.get("finalStats"),
                    "beforeStats": pipeline.get("beforeStats"),
                },
            },
        )

    def handle_fix_chapter(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter, file_path = self.resolve_chapter_file(data, body)
        mode = str(body.get("mode") or "auto").strip().lower()
        original = read_text(file_path)
        fix_result = auto_fix_chapter_content(
            data,
            chapter,
            original,
            mode=mode,
            config=self.api_config_from_body(body),
            writing_rules=str(body.get("writingRules") or ""),
        )
        if fix_result.get("unchanged"):
            to_json(
                self,
                200,
                {
                    "unchanged": True,
                    "chapter": chapter,
                    "chapterPath": str(file_path),
                    "mode": mode,
                    "fixesApplied": fix_result.get("fixesApplied", []),
                    "message": "未发现可自动修复的问题，或修复后内容无变化。",
                    "beforeStats": fix_result.get("beforeStats"),
                    "afterStats": fix_result.get("afterStats"),
                },
            )
            return

        result = save_fixed_chapter(data, chapter, file_path, original, fix_result["text"])
        result["mode"] = mode
        result["fixesApplied"] = fix_result.get("fixesApplied", [])
        result["unchanged"] = False
        to_json(self, 200, result)

    def handle_export(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        to_json(self, 200, {"text": export_markdown(data)})

    def handle_export_manuscript(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        text = export_manuscript(data)
        out_path = data.root / ".novelbuddy" / "正文合集.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        to_json(self, 200, {"text": text, "path": str(out_path), "count": len(data.chapters)})

    def handle_read_file(self, body: dict[str, Any]) -> None:
        path = Path(str(body.get("path") or ""))
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"文件不存在: {path}")
        to_json(self, 200, {"name": path.name, "path": str(path), "text": read_text(path)})

    def handle_draft(self, body: dict[str, Any]) -> None:
        data = self.project_data(body)
        chapter = int(body.get("chapter") or 1)
        words = int(body.get("words") or 3000)
        force = bool(body.get("force"))
        config = self.api_config_from_body(body)
        base_temperature = float(config.get("temperature") or 0.6)
        preflight = run_writing_preflight(
            data,
            chapter,
            words=words,
            api_key=str(config.get("api_key") or ""),
            api_base=str(config.get("api_base") or ""),
            model=str(config.get("model") or ""),
            writing_rules=str(body.get("writingRules") or ""),
            base_temperature=base_temperature,
        )
        if not preflight.get("canProceed") and not force:
            to_json(
                self,
                409,
                {
                    "error": "生成前检查未通过，已暂停重新生成。",
                    "preflight": preflight,
                    "text": preflight.get("text", ""),
                },
            )
            return

        if preflight.get("autoSyncRecommended") and body.get("autoSync", True):
            sync_project_state(data)
            data = load_project(str(data.root))

        prompt = append_writing_extras(build_prompt(data, chapter, words, 4500), body, data.root)
        if not config["api_key"]:
            raise ValueError("缺少 API Key。请在页面填写 API Key，或设置 NOVELBUDDY_API_KEY 环境变量后重启服务。")
        outline = find_outline(data, chapter)
        outline_text = str(outline.get("content", "")) if outline else ""
        temperature = float(
            preflight.get("suggestedTemperature")
            or suggest_chapter_temperature(outline_text, float(config.get("temperature") or 0.6))
        )
        draft = normalize_chapter_text(call_openai_compatible(prompt, config, temperature))
        title = str(outline.get("title", "")) if outline else f"第{chapter}章"
        chapter_path = chapter_output_path(data, chapter, title)
        chapter_path.write_text(draft, encoding="utf-8")
        auto_fix = body.get("autoFix", True) is not False
        pipeline = run_post_generation_pipeline(
            data,
            chapter,
            chapter_path,
            draft,
            config=config,
            writing_rules=str(body.get("writingRules") or ""),
            auto_fix=auto_fix,
            fix_mode=str(body.get("fixMode") or "auto"),
        )
        to_json(
            self,
            200,
            {
                "text": pipeline.get("text", draft),
                "chapterPath": str(chapter_path),
                "auditPath": pipeline.get("auditPath", ""),
                "auditText": pipeline.get("auditText", ""),
                "analysis": pipeline.get("analysis"),
                "preflight": preflight,
                "qualityWarnings": pipeline.get("qualityWarnings", []),
                "suggestedFix": bool(pipeline.get("suggestedFix")),
                "temperatureUsed": temperature,
                "pipeline": {
                    "stages": pipeline.get("stages", []),
                    "fixed": bool(pipeline.get("fixed")),
                    "fixesApplied": pipeline.get("fixesApplied", []),
                    "backupPath": pipeline.get("backupPath", ""),
                    "initialStats": pipeline.get("initialStats"),
                    "finalStats": pipeline.get("finalStats"),
                    "beforeStats": pipeline.get("beforeStats"),
                },
            },
        )


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    host = "127.0.0.1"
    port = 8765
    if "--port" in argv:
        idx = argv.index("--port")
        port = int(argv[idx + 1])
    server = ThreadingHTTPServer((host, port), NovelBuddyHandler)
    print(f"NovelBuddy Web 已启动: http://{host}:{port}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
