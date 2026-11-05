# 论文内容图谱实现合同

用户要求每篇入库论文提炼内容组织，而非通用摘要。原始摘要全文保留；引言按真实段落建立段内要素和段间关系；方法按小节，结果按实验、比较与分析，讨论按解释与论证，结论按结论项组织。节点是具体内容关键词，关系解释科学内容怎样相接，并连接问题、方法、证据与结论。参照此前1111工作流文档、corpus-assisted-writing、good-story和scientific-expression-review，提炼手段目的、论文主线、比较条件与承诺兑现；不强行将每篇论文改成固定沙漏模板。

## 原文包

`source`含asset、library、title、doi、pages、parser、signature；signature用实际大小与mtime_ns区分现存文件版本。`abstract`含text、source_ids、complete、status。text来自原文解析，模型不得改写或替换为摘要。`units`为有稳定id的原文单元：id、section_id、kind、text、page（可空）、bounds（可空）、section_title。`sections`含id、title、parent_id、order、unit_ids、role（原解析可为空，模型判断补充）。优先复用当前源版本的缓存，GROBID能保留章节与真实段落时使用TEI；失败后按PDF版面提取并保留paragraph_boundary_status，不能将PDF块冒充已核真段落。页/坐标缺失时只提供确有的原文单元，不编页码。

## 最终图谱

JSON含schema_version、source、abstract、keywords、nodes、edges、story、coverage、generated_at、rule_version。

`nodes`为扁平树，每项：id、parent_id（根为空）、kind、section_type、label、content、keywords、source_ids、sentence_ids、source_quotes、order、depth。kind取paper、section、paragraph、element、experiment、comparison、analysis、discussion、conclusion；section_type取abstract、introduction、methods、results、discussion、conclusion、other。label为贴合论文材料、过程、物理量及条件的关键词或简短词组，完整解释放在content中。写作功能和方法类别不能替代论文主题；例如应保留钙溶出、硫酸盐侵蚀、膨胀，而不能只用通用的预测或推断术语概括。

模型从原文单元完整提供的`sentences`中选择`sentence_ids`，程序接回逐字原文为`source_quotes:[{source_id,quote,start_char,end_char}]`。旧版直接提交引句时同样逐字核对；改写、虚构引句不会作为原文显示。原段落另存，支持阅读上下文。算法切出的片段可能受缩写、公式及PDF版面影响，始终保留所在完整原段落，不把提取结果当成作者人工分句。

`edges`每项：id、from、to、relation、explanation、source_ids、basis。basis取explicit或inferred，区分原文明确关系与基于原文的组织解读。层级父子可由parent_id确定，edges用于段内、段间及跨章节内容关系。relation使用准确中文如原因、比较、约束、承接、解释、支持、回应、限定。

`story`含author_question、main_claim、organization_summary、means_ends（数组）、promise_evidence（数组）、learning_points（数组）。承诺兑现给出具体问题、方法、结果及结论的node_ids与原文依据。没有相应证据就注明未找到，不能补造。

`coverage`含实际原文单元数、已挂引单元数、未映射单元id、段落边界状态、需要复核的事项。规则核对来源、边界与粒度；结构完整不代表科学结论已验证。

## 接口约定

GET `/research/api/projects/{pid}/literature/content-map?asset=...&library=workspace` 返回 `{status,job_id,stage,error,map}`，未生成时map为空，status为missing；原文更新后status为stale，保留旧图供回查。生成中返回queued/running，结构不足可为needs_review，完整结果ready。

POST 同路径，body `{asset,library,force?,model_selection?}` 返回同一状态结构，重复请求复用当前任务。GET `/literature/content-maps`返回`{items,auto_enabled}`；POST `/literature/content-maps/backfill`补齐项目已有PDF，返回任务/数量。新PDF入库后登记与排队；没有全文的题录不可生成完整图谱。用户可查看进度、失败原因和重试。

原文定位用map.source_units（等于原文包units）保存以便UI回查；每个节点source_ids必须指向真实unit。摘要不是LLM输出字段，由执行器从原文包接回。

## 界面

沿用当前工作台主题与版式，在文献信息和阅读工具栏提供内容图谱入口。思维导图与内容关系使用可平移、缩放的画布，按主题、章节、段落内容及段内概念展开，不按页组织。节点点击后直接显示核验原句与完整段落上下文；没有引句时明确只有对应段落。页码只作为回到PDF的次级定位。

节点使用固定边界，父子布局保留空列间隙，关系线按边缘端口和空白通道连接，箭头末端位于框外。几何测试核对框与框、线路与框及箭头与目标框；实际清晰度、词组提炼及内容关系仍由作者试读确认。生成状态ready只表示该版生成及结构检查完成，不表示作者已验收。

2026-11-04作者先指出通用术语过泛，后要求关键词/词组画布及点击原句。此前卡片式候选未获认可。当前以Qin引言的真实内容和原文句子制作画布试读候选，等作者查看实际效果后再决定内容验收；未将软件测试或模型输出作为认可。
