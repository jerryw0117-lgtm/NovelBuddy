# NovelBuddy

本地小说辅助系统。它读取你的小说项目文件，不依赖任何插件授权。

## 当前能力

- 扫描小说项目结构
- 读取 `.novel-assistant` / `.ai-novel` / 手写 Markdown 资料
- 汇总人物、世界观、大纲、摘要、伏笔
- 显示大纲、章节、人物卡片、关系图谱、时间线卡片、伏笔卡片
- 生成可视化人物关系图谱，合并正式关系和最近同章线索，并保留 Mermaid 文本
- 自动识别已写到第几章和下一章
- 编辑/新增本章大纲，保存前自动备份
- 配置本地写作规则，自动带入生成提示词和自动修改
- 生成章节计划、上下文包、写作提示词
- 生成伏笔回收计划，标出临近失效、拖延较久和已过期伏笔
- 生成并保存正文，生成后自动执行审计 → 定点修 → 再审计，并同步本地状态
- 自动回写 `.novel-assistant`：伏笔回收、人物状态、章节摘要
- 一键同步所有章节的人物、关系、伏笔、时间线和本地摘要
- 生成指定章节的上下文包
- 审查章节正文：AI 痕迹、禁用词、解释型句式、字数、伏笔命中
- 审查并自动修改章节，覆盖前自动备份
- 问题总览支持单章/批量快速修复、AI 修复、自动修复
- 项目诊断、生成前检查、后续路线图、全文检索
- 备份管理：查看章节备份并安全恢复
- 导出项目资料和正文合集为 Markdown
- 资料编辑：人物、伏笔、组织势力、世界观（写入 `.novel-assistant` 并自动备份）
- 组织势力 tab、世界观 tab，关系/组织章节有效期过滤进上下文包
- 批量分析章节、自检报告（对标蛙趣批量分析与 F2 诊断）
- 蛙趣同款混合检索：读取 `.novel-assistant/memory/vector_store.json`，bge-small-zh-v1.5 向量 + BM25 + RRF 融合；无向量库时降级为项目资料 BM25
- API 设置：生成温度、按章节类型动态温度
- 联动写作流程：生成前自动检查（大纲/衔接/API/伏笔/资料同步/上章质量）→ 自动同步 → 生成 → 审计 → 定点修 → 再审计
- 伏笔同义词匹配：支持关键词的多种表达方式自动识别
- 角色合并：同名角色自动合并，支持别名匹配
- 大纲一致性检测：自动检测正文与大纲的偏离
- 问题检查：自检报告现在会检测角色冲突、伏笔过期、大纲偏离等问题

## 快速使用

### 网页界面

一键启动：

```powershell
cd E:\obs\novelbuddy
.\start-novelbuddy.ps1
```

启动并打开浏览器：

```powershell
cd E:\obs\novelbuddy
.\start-novelbuddy.ps1 -OpenBrowser
```

停止后台服务：

```powershell
cd E:\obs\novelbuddy
.\stop-novelbuddy.ps1
```

手动启动：

```powershell
cd E:\obs\novelbuddy
uv run novelbuddy-web --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

页面里可以直接扫描项目、生成/审查/修改章节、编辑大纲、设置写作规则、查看伏笔回收计划、同步资料、检索全文、查看备份和导出资料。

### 配置

项目路径可通过以下方式设置：

1. **网页界面**：在"项目目录"输入框中输入路径，会自动保存到浏览器本地存储
2. **环境变量**：设置 `NOVELBUDDY_PROJECT` 环境变量
3. **配置文件**：复制 `.env.example` 为 `.env` 并填入配置

```powershell
# 方式1：设置环境变量
$env:NOVELBUDDY_PROJECT = "E:\obs\xiaoshuo\都市"
.\start-novelbuddy.ps1

# 方式2：使用配置文件
Copy-Item .env.example .env
# 编辑 .env 文件填入你的配置
```

### 自动回写插件资料

生成正文、审查章节、同步章节资料时，会自动写回 `.novel-assistant`：

- `foreshadows.json`：按正文回收伏笔，并备份到 `.novelbuddy\backups`
- `current-story-state.json`：更新人物出场、最近事件、待回收伏笔数
- `summaries.json`：更新或新增对应章节摘要

伏笔回收规则：

- `medium/low`：正文出现关键词 → 标记 `resolved`
- `high`：关键词 + 描述锚点词同时出现 → `resolved`；仅关键词 → 标记推进（`lastContextChapter`），不结案

### 重要数据位置

- NovelBuddy 本地状态：`项目目录\.novelbuddy\state.json`
- 正文合集导出：`项目目录\.novelbuddy\正文合集.md`
- 大纲备份：`项目目录\.novelbuddy\backups`
- 章节自动修改备份：原章节同目录下的 `.bak-时间.md`
- 恢复备份前的安全备份：原章节同目录下的 `.pre-restore-时间.md`

### 命令行

```powershell
cd E:\obs\novelbuddy
uv run novelbuddy scan E:\obs\xiaoshuo\都市
uv run novelbuddy context E:\obs\xiaoshuo\都市 8
uv run novelbuddy prompt E:\obs\xiaoshuo\都市 8 --out E:\obs\xiaoshuo\都市\nb_prompt_ch08.md
uv run novelbuddy audit E:\obs\xiaoshuo\都市 E:\obs\xiaoshuo\都市\AAA\chapters\第7章-前任住户.md
uv run novelbuddy export E:\obs\xiaoshuo\都市 --out E:\obs\xiaoshuo\都市\novelbuddy_export.md
```

## 设计原则

- 只读原项目资料，默认不改你的小说文件。
- 数据格式尽量兼容现有插件产物，但不依赖它运行。
- 上下文包优先短、准、可控，不把全项目一股脑塞给 AI。
