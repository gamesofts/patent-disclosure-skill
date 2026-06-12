# 概念想法到专利交底书技能 — 产品说明（PRD 摘要）

## 1. 产品概述

本仓库为符合 Codex Skills / Agent Skills 习惯的 **Skill**：通过 `SKILL.md` 编排流程，`agents/openai.yaml` 提供 Codex 产品形态元数据，`prompts/` 存放可引用的指令模板，`tools/` 预留可执行脚本扩展。

**目标**：从一段概念想法完成创新点设计 → 查新 → 技术交底书（脱敏模版）→ 内部自检与迭代修订。用户提供项目路径或附件时，再执行可选扫描校准事实。

## 2. 用户流程

```
用户触发（自然语言 / 斜杠指令）
        ↓
Step 1  边界与输入（prompts/intake.md）
        ↓
Step 2  概念拆解与创新方案设计（concept_design.md）
        ↓
可选    项目/附件扫描（project_scan.md：.docx/.pptx 先转 MD；裸图目录可跳过）
        ↓
Step 3–4 候选专利点 + 融合选定（prompts/patent_points_analyzer.md）
        ↓
Step 5  联网查新（prior_art_search.md：**优先** tools 中国知局 epub 爬虫，失败再 WebSearch）
        ↓
Step 6  摘要预览与确认（prompts/disclosure_preview.md）
        ↓
Step 7  全文交底书（prompts/disclosure_builder.md + template_reference.md）
        ↓
Step 8  内部自检（prompts/disclosure_self_check.md）→ 修订后交付
        ↓
交付   用户产出目录下的 .md/.docx：**案件名 + 本地时间戳**（§7.3 第 5 点），**含首次定稿与每次迭代**，勿默认覆盖
        ↓
持续   意图为改已有稿时：补充材料（merger.md）/ 对话纠正（correction_handler.md）；规则同上；案件目录 **`交底书修订对话记录.md`** 逐条追加（含时间、用户说明摘要），见 `iteration_context.md`
```

## 3. 目录约定

| 路径 | 说明 |
|------|------|
| `SKILL.md` | 唯一入口：触发条件、工具映射、步骤与 prompts 引用 |
| `agents/openai.yaml` | Codex 产品形态元数据：展示名、短描述、默认调用提示 |
| `prompts/` | 分步脚本化说明，由 Agent `Read` 后执行 |
| `tools/` | 可选脚本；含 `md_to_docx.py`、`docx_to_md.py`、`pptx_to_md.py`、`cnipa_epub_search.py`（查新一步；另 `cnipa_epub_crawler.py` / `cnipa_epub_parse.py`），见 `tools/README.md` |
| `docs/` | PRD、架构学习笔记等 |
| `outputs/` | 用户定稿导出目录；整目录由 `.gitignore` 忽略；可提交的脱敏范例放在 **`examples/`** |
| `examples/` | 随仓库提交的**原材料**示例（如 `example_batch_job_scheduler/knowledge/`）；流程产出在 `outputs/` |

## 4. 约束

- 默认不要求项目材料；只有用户提供项目、附件或已有交底书时才扫描。
- Office 原材料（Word/PPT）：使用本仓库 `tools/docx_to_md.py`、`tools/pptx_to_md.py` 转换后再扫描（见 `SKILL.md`）。
- 交底书正文**不得**包含「自检清单」章节。
- 脱敏要求见 `disclosure_builder.md` / `template_reference.md`。
- 查新结论须写入第一章并与技术问题、方案呼应；渠道与著录细则见 `prompts/prior_art_search.md`。
- 交底书定稿须**同时**交付 Markdown 与 Word；文件名 **`{案件名}_{YYYYMMDDHHmmss}`**（§7.3 第 5 点，含首次与迭代）；`tools/mermaid_render.py` 默认调用 `md_to_docx.py`；Word 失败时允许人工补转（见 `tools/README.md`）。

## 5. 环境变量

在 Codex 中通常按 skill 根目录解析相对路径。兼容 Claude Code、OpenClaw 等环境时，平台可能使用 **`CLAUDE_SKILL_DIR`** 指向包含 `SKILL.md` 的目录；使用 Cursor 打开本仓库时，该目录即仓库根目录。
