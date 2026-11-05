# 质量知识来源目录

本目录保存工作台质量规则的来源、教材页段与本批解析文件定位。六种PPT用途的生效规则已进入生产 `templates/presentations/purpose-rules.json`，规划与阶段评分读取同一记录；本目录的来源索引与样例不直接覆盖运行时规范。

`source-registry.json` 记录已定位的来源、实际读到的范围与MinerU/原生提取路径。`presentation-sources/`保留六用途资料的实际原件和处理层。三本教材的本地Markdown、页JSON和接收回执位于 `../reports/mineru-books/`；具体完成状态读取各书映射。`rule-seeds.json`仍是带来源的指导样例，未自动升级为强制规则。全部教材完成转换也不代表所有页已被审读或完成语义索引。

运行时应先按任务、用户/项目、模板/期刊/文章类型和版本枚举全部适用硬约束，再按当前表达或设计问题检索指导与例文。技能负责选择与执行，结构化条件交给程序检查，语义与视觉问题由模型结合证据判断，结果绑定实际产物与规则版本。

现有权威入口优先复用：工作台 `templates/presentations/catalog.json`、`server/presentation_catalog.py`、`vendor/workbench-skills/OUTPUT_STANDARD.md`、稿件模板与 provenance，以及已有 corpus rulebook。后续整合时由统一记录服务生成各工具需要的 profile；本目录的样例不会自动覆盖这些现有入口。

书籍原件和连续语境保留在原有授权位置，目录保存定位与释义。项目术语记录应说明对象、义项、符号/单位、允许变体、易混项和例文上下文，不能简化成只按单词替换的禁用词表。

本批首选阅读层已进入当前作者的Tutor私人参考项目（69c79a679648428aae6d8e06f4006f70），14项输入的索引与实际检索回执见 `../reports/native-quality-library.json`。用途硬规则仍取生产canonical JSON，全文索引不把教材或机构指导升级为强制要求。
