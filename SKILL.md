---
name: patent-disclosure-skill
description: "从一段概念想法直接设计可专利化创新点并生成中国专利技术交底书。Use when the user provides an invention idea, product concept, technical direction, rough需求, or asks for patent innovation design, patent disclosure drafting, prior-art search, or iterative revision of an existing disclosure; also supports optional project/document scanning when the user supplies files."
---

# 概念想法到专利交底书生成

本技能覆盖 **概念理解** → **创新点设计** → **查新与差异化** → **交底书生成** → **自检完善** 全流程。默认输入是一段想法，不要求用户提供项目代码或设计文档；如用户同时提供项目路径、附件或已有材料，再按可选扫描补充事实。

分步指令在 **`prompts/`**，每步执行前 **`Read`** 对应文件，与步骤的对照见「Prompt 文件映射」。

## 环境与约定

- **语言**：默认与用户语种一致；专利与法律术语采用行业常用表述。
- **默认输入**：一段概念想法、产品设想、技术方向、业务痛点或零散需求均可。信息不足时主动提出少量关键澄清；若用户希望直接生成，则合理假设并在草稿中标注「可调整假设」。
- **设计边界**：可以基于概念做技术合理推演，但不得把未经用户确认的商业事实、实验数据、性能指标或真实部署情况写成既成事实。
- **图示定稿（Step 7）**：**3.2**/**3.4** 用 fenced **mermaid**；执行方式、**`mmdc`** 安装与降级规则见下表「交底书定稿交付」行及 **`tools/README.md`**。

---

## 触发条件

在用户使用以下任一方式时启用本技能：

- 明确提及：专利挖掘、专利点、技术交底书、交底书、专利交底书、查新、现有技术对比等
- 只给出一段想法或需求，并要求「帮我设计创新点」「看看能不能写专利」「生成交底书」「包装成专利方案」等
- 斜杠或简短指令：如 `/patent-disclosure-skill`、`/patent-disclosure`、`/交底书`
- **迭代模式（按意图识别）**：当用户意图明显是在**已有交底书或上一轮输出**上继续工作（如改章节、补实施例、补材料、修正参数/事实、调整表述等），**无需**用户写出「迭代」等固定词，也**不必**询问是否进入迭代——Agent 应 **`Read`** **`prompts/iteration_context.md`**，再 **`Read`** `prompts/merger.md`（侧重**新材料、扩展合并**）或 `prompts/correction_handler.md`（侧重**纠错、与事实或风格不符**），**严格按该文件开头的「执行门禁」**（优先执行，不可跳过）**做完合并或纠正**，**另存为新文件**：**`{案件名}_{YYYYMMDDHHmmss}.md`** 与同名 **`.docx`**（与首次定稿同一命名规则，见 **`disclosure_builder.md` §7.3 第 5 点**），**不覆盖**旧稿（除非用户明确要求）。**禁止**在迭代意图已成立时默认回到 Step 3–4 专利点全文分析（除非用户明确要求重新挖掘专利点）。对话中**已出现**交底书路径、附件或上文刚交付的草稿时，优先按迭代处理。

---

## 工具与数据来源

按任务选用能力；具体工具名称以当前 Agent 环境为准。

若用户提供扫描范围且其中含 **Word（.docx）** 或 **PowerPoint（.pptx）**，须在可选扫描阶段纳入阅读前用本仓库 **`docx_to_md.py`** / **`pptx_to_md.py`** 转为 Markdown；依赖 **`pip install -r requirements.txt`**，命令与说明见下表对应行。

## 硬性渲染与联网约束（优先级高）

- **联网查新不要安装或调用 Playwright**。需要浏览网页时，优先使用当前环境提供的 **CDP / 浏览器调试协议**能力；国知局公布公告站优先用 `tools/cnipa_epub_search.py`（已改为 CDP 入口）检索并解析 `EPUB_HITS_JSON`。没有 CDP 或站点不可用时，改用公开可访问的 Web/Google Patents 页面检索与核验。Playwright 链路仅作为历史工具说明，Agent 不应主动执行 `python -m playwright install chromium` 或 Playwright 脚本。
- **图示必须先做版面自检**：图片采用黑白框线风格，避免彩色填充、彩色线条和装饰性配色；框与线不得重叠；线不得穿过框体、标题、节点文字或菱形判断框；反馈线/回路线优先走外侧空白区；箭头只从框边缘进出。重复画图时，交互中的解释性文字（如“说明：”“我会…”“注意…”）**不得渲染进图片**，只可写在正文图下的普通段落。
- **公式交付规则**：Markdown 保留 LaTeX；Word 中公式必须是 Word 公式编辑器可识别的 **OMML/原生公式对象**或等效公式格式，**不得用公式图片**，也不得让用户打开 Word 后看到 `\theta`、`\mathrm`、`\[`、`\(` 等反斜杠源码。生成 Word 时优先用 `tools/docx_omml_equations.py`；若无法生成 OMML，必须明确说明并修复，不得把公式图片版当最终稿。

### 常见任务与建议方式

| 任务 | 建议方式 |
|------|----------|
| 加载分步指令 | **`Read`** → `${CLAUDE_SKILL_DIR}/prompts/*.md`，见下表 |
| 从概念想法设计创新点 | **`Read`** `prompts/concept_design.md`，把原始想法扩展为问题链、技术方案、候选创新点、可实施模块与待确认假设 |
| 读代码、设计文档、PDF、图片 | 文件读取工具；大仓库先用搜索/语义检索定位再精读 |
| Word（.docx）→ Markdown + 抽取图片（扫描前） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/docx_to_md.py --input {path}.docx --output {dir}/{name}.md`；图片默认写入与 `.md` 同级的 `{name}_media/`；需 `pip install -r requirements.txt`（含 mammoth）；复杂版式可改由所内导出 PDF/MD 再扫 |
| PowerPoint（.pptx）→ Markdown + 抽取图片（扫描前） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/pptx_to_md.py --input {path}.pptx --output {dir}/{name}.md`；默认 `{name}_media/`；需 `pip install -r requirements.txt`（含 python-pptx）；**旧版 .ppt 不支持**，请先另存为 `.pptx`；图表/SmartArt 等若未以图片形状嵌入则可能仅能从备注或另行导出补全 |
| 罗列目录、按名找文件 | 目录列举 / 按文件名搜索 |
| 联网查新（Step 5） | 执行前 **`Read`** `prompts/prior_art_search.md`。优先用国知局公布公告站的 **CDP 入口** `python3 ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py ...` 检索并解析 `EPUB_HITS_JSON`；**不要安装或调用 Playwright**。按该 prompt 归纳 **2～8 个相关语义块**并分轮检索；无法走 CDP 或结果不足时改用 Google Patents / 公开网页并写明公开 URL。 |
| 交底书定稿交付（**须同时** .md + .docx） | **3.2** 系统框图与 **3.4** 流程图可用 fenced ``mermaid`` 作为源，但定稿图必须使用黑白框线风格，并先检查框线关系，必要时重绘为 PNG；图片中不得包含对话式说明文字。含公式时，Markdown 保留 LaTeX，Word 用 **`tools/docx_omml_equations.py`** 或等价流程生成原生公式对象；禁止公式图片。详见 **`tools/README.md`** |
| 保存交底书路径 | 写入用户指定路径；未指定时可建议 `./outputs/{案件标识}/`；**凡交付的** `.md` / `.docx` 须为 **`{案件名}_{YYYYMMDDHHmmss}`**（§7.3 第 5 点，**含首次定稿与迭代**），勿默认覆盖旧稿；`outputs/` 整目录默认由 `.gitignore` 忽略 |
| 迭代对话留档 | 每轮 **merger / correction** 交付后，在案件目录追加 **`交底书修订对话记录.md`**（**`tools/iteration_dialog_log.py`** 或等价手工），见 **`prompts/iteration_context.md`** |

---

## Prompt 文件映射

| 步骤 | 文件 | 用途 |
|------|------|------|
| Step 1 | `prompts/intake.md` | 边界与输入问题 |
| Step 2 | `prompts/concept_design.md` | 根据概念想法设计技术方案、候选创新点、可实施模块与假设边界 |
| 可选补充 | `prompts/project_scan.md` | 仅当用户提供项目路径/附件/已有资料时扫描；**须**对 `.docx`/`.pptx` 先转换再读（见该文件「Office 文档」节）；独立图片目录可跳过 |
| Step 3–4 | `prompts/patent_points_analyzer.md` | 候选专利点、融合与选定；默认基于概念设计稿而非项目扫描结果 |
| Step 5 | `prompts/prior_art_search.md` | 联网查新与分析要求 |
| Step 6 | `prompts/disclosure_preview.md` | 全文前的摘要预览 |
| Step 7 | `prompts/disclosure_builder.md` + `prompts/template_reference.md` | 交底书结构、脱敏、**符号与公式体例（§7.7）**与图示规范；**mermaid 与 3.4.1 符号/公式范例在 template_reference** |
| Step 8 | `prompts/disclosure_self_check.md` | 内部自检，不写入正文 |
| 迭代 | `prompts/iteration_context.md` | 迭代意图、落盘命名、**修订对话记录 md**（含对话/记录时间） |
| 迭代 | `prompts/merger.md` | 新材料增量合并；**文首含门禁**；输出 `{案件名}_{时间戳}.md`/`.docx` |
| 迭代 | `prompts/correction_handler.md` | 对话纠正；**文首含门禁**；输出 `{案件名}_{时间戳}.md`/`.docx` |

---

## 主流程（执行顺序）

1. **`Read`** `intake.md` → 执行 Step 1
2. **`Read`** `concept_design.md` → 执行 Step 2，从用户概念生成可专利化方案底稿
3. **可选**：用户提供项目路径、附件、已有交底书、设计文档或代码时，**`Read`** `project_scan.md` → 用事实材料校准 Step 2；未提供材料则跳过，不向用户索要项目
4. **`Read`** `patent_points_analyzer.md` → 执行 Step 3–4
5. **`Read`** `prior_art_search.md` → 执行 Step 5
6. **`Read`** `disclosure_preview.md` → 执行 Step 6；用户可跳过
7. **`Read`** `disclosure_builder.md` 与 **`Read`** `template_reference.md` → 执行 Step 7（**首次交付**的 `.md`/`.docx` 亦须 **`{案件名}_{YYYYMMDDHHmmss}`**，§7.3 第 5 点）；交付对话中**须**按 **`disclosure_builder.md` §7.6** 补充「权利要求偏向点」建议交互（**仅对话**，不入正文）
8. **`Read`** `disclosure_self_check.md` → 内部执行 Step 8，修订后交付

**禁止**：交底书正文中包含「自检清单」章节；自检仅内部使用。

---

## 迭代模式（摘要）

**启用方式**：根据用户**自然语言意图**判断（见上文「触发条件」），**不要求**固定关键词，**默认不**为「是否迭代」打断用户。

- **补充材料 / 扩展章节**或 **§7.6 第五章权利要求书式强化（用户已声明侧重点）**：`Read` → `iteration_context.md` → `merger.md`；合并结果**另存为**带时间戳的 `.md`/`.docx`（§7.3 第 5 点）；**追加** `交底书修订对话记录.md`（`iteration_dialog_log.py` 或手工）；完成后**必须**输出「合并摘要」留档；若本轮亦为定稿交付，**仍建议**简短附带 §7.6 类引导  
- **指出错误 / 与事实或参数不符**：`Read` → `iteration_context.md` → `correction_handler.md`；纠正结果**另存为**带时间戳的 `.md`/`.docx`；**追加**对话记录；完成后**必须**输出「纠正摘要」留档；定稿交付时**还须**按 **`disclosure_builder.md` §7.6** 附「权利要求偏向点」引导（见 **`correction_handler.md`** 末尾）  

主流程 Step 7→8 的 **`disclosure_self_check.md`** 仍在新稿定稿路径上内部执行。

---

## Agent 自用工作流检查清单

```
□ 已按步骤 Read 对应 prompts；Step 2 若目录含 Office，已执行 docx_to_md / pptx_to_md 并读了产出 `.md`
□ 默认已基于用户概念执行 `concept_design.md`；除非用户提供项目/附件，否则未把项目扫描作为前置条件
□ 概念推演中把「事实」「假设」「可调整设计」分清，未把未确认指标或部署事实写成确定事实
□ 识别到「在已有交底书上修改」类意图时，已 Read `iteration_context.md` 并选用 merger 或 correction_handler（而非从头跑扫描）；交付为**新** `{案件名}_{时间戳}.md`/`.docx`，未无故覆盖旧稿
□ 执行 merger / correction_handler 后，已在对话中输出该文件要求的留档摘要（合并摘要 / 纠正摘要）；案件目录已追加 **`交底书修订对话记录.md`**（或等价日志）
□ 查新完成且写入 1.1 与区别论述（符合 `prior_art_search.md`：**未安装/调用 Playwright**；优先国知局公布公告站 CDP 入口 `cnipa_epub_search.py`，结果不足再降级公开网页/Google Patents；每条现有技术均有可访问 URL；有摘要时已充分理解后再概括）
□ 除用户明确跳过外，完成摘要预览
□ 脱敏、图示、章节引用符合 template_reference；图为黑白框线风格，图中框线无重叠、无穿框、无对话说明文字；含公式时 **3.4.1 符号表、§7.7 体例**（维度下标、无字母多义、LaTeX 分隔符统一）及 **3.5 符号列同形** 已满足，且 **Word 中公式为原生公式对象而非图片/反斜杠源码**；**已交付 .md 与 .docx**，且**文件名符合 §7.3 第 5 点**（**凡交付均含**时间戳后缀）；**正文无**技能/示例仓库类文末脚注
□ 定稿类对话已含 **`disclosure_builder.md` §7.6**「权利要求偏向点」建议交互（**不入正文**、**不捏造**未在稿内出现的保护取向）；迭代再走 merger 时见 **`iteration_context.md`** 表格补充行
□ 自检在后台完成，正文无自检清单章节；含公式时已按 **`disclosure_self_check.md` §8.2** 复核**公式正确性与公式逻辑**（有误已在 Step 8 直接改稿）
```
