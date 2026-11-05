---
name: workbench-literature
description: 按项目问题组织论文、书籍和方法资料，选择适合的全文解析与 RAG 流程并核对索引状态。
---

先读项目问题、已有稿件和资料元数据，再阅读支撑分类的摘要或全文段落。文献类型、主题概念和研究用途分别标注；参考 W3C SKOS 的概念、上下位和相关关系来维护主题词。合并同义主题，避免用文章标题作为类别；少量资料以平铺和用途标签为主，不为每篇文献建一个目录。分类需要简明的内容依据，允许资料属于多个用途。

复用原生知识库、ScanSci、MinerU 与已有 RAG 配置。按格式选择解析器；已有可用解析不重复消耗模型。原始 PDF/EPUB 保留，派生文本、公式和图表能够回到原页。分别记录下载身份、解析覆盖、索引完成和可检索状态。类别调整不破坏引文、原文件路径或历史批注。

用户要求整理当前文献库时，调用 `research_workbench(action="library", library_action="list")` 读取真实文献和当前文件夹，再用 `library_action="organize"` 提交 `organization_json`，包含当前 `expected_revision`、文件夹 `folders`（id/name/kind）和文献键到文件夹 ID 的 `memberships`。文献键必须使用列表返回的 `library/name`，可以有多个主题归属。用途标签仍独立保留。收到 `status=saved` 与 `verified=true` 后回读确认，再报告文献库更新。分类表、输出目录或压缩包不会更新文献库；不能用它们替代用户要求的库内整理。此操作保存稳定文献身份的文件夹映射，不移动原 PDF，不破坏已有引用与批注。

分类参考：https://www.w3.org/TR/skos-primer/ 。与本项目有关的分类方案是 AI 基于材料的整理结果，不能包装成上述标准规定的唯一分类。
