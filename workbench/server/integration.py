"""Human and agent entry points backed by the same current capability map."""
from pathlib import Path
import json
from fastapi import Depends
from fastapi.responses import FileResponse,PlainTextResponse
from .native import actor

ROOT=Path(__file__).resolve().parents[1]
FEATURES=[
 {'id':'account','name':'账户、作者与空间','entry':'工作台设置 → 作者资料；顶部空间用量','input':'当前登录账户、署名、单位和联系邮箱','output':'按账户保存的资料与项目空间统计','steps':['登录当前 DeepTutor 账户，选择自己的项目。','在作者资料中保存单位、邮箱与中英文署名。','空间面板查看文件、译文与历史用量。']},
 {'id':'library','name':'文献与知识库','entry':'文献 → 添加文献 / 查找文献','input':'PDF、所属知识库、关键词和目标文件夹','output':'题录、全文附件、来源片段与可阅读的原文','steps':['上传 PDF，或在学术文献中检索并勾选结果。','将方法框架、验证数据和阅读材料归入相应文件夹。','知识库检索返回实际来源片段；语义模式需要可用索引与检索配置。']},
 {'id':'search','name':'联网检索与相关研究','entry':'文献 → 联网查找；论文 → 引用详情','input':'研究问题、关键词、年份与检索来源','output':'带实际来源、年份和原始链接的候选研究','steps':['默认使用 Google Scholar MCP；可切换已配置的 WoS 或多源网页。','Crossref 用于 DOI 和题录核验，也可明确选择该来源。','相关研究基于引用段落与真实检索候选比较，推荐理由标明证据范围。']},
 {'id':'download','name':'批量下载与上传','entry':'检索结果 / 参考文献 / 相关研究 → 勾选与下载','input':'所选题录、文件夹或本地 PDF','output':'所属用户文献库、题录匹配状态与传输回执','steps':['逐篇勾选或全选本页，批量下载所选文献。','本机 ScanSci 下载后上传集群，验收通过才交付到用户文件夹。','队列可查看阶段、重试失败项；需要机构认证时在 ScanSci 专用窗口完成。']},
 {'id':'reader','name':'原文阅读、批注与翻译','entry':'文献 → 阅读全文；论文 → 预览','input':'项目原文、页码、选中段落与翻译方向','output':'原 PDF、译文、批注、来源定位与可下载译稿','steps':['打开全文，在页内选择文字或定位图表。','按需要翻译当前文档或选中片段，等待任务完成。','原文保持可回读，批注和问题进入处理记录。']},
 {'id':'paper','name':'论文、引用与模板','entry':'论文 → 编辑 / 引用 / 版式与导出 / 稿件预览','input':'当前正文、引用、作者资料与版式选择','output':'可编辑稿、通用预览、Word/PDF/TeX 与修订历史','steps':['编辑正文与引用，使用保存、撤销和可恢复历史。','默认通用学术稿；指定期刊时查官方作者指南与模板。','预览保留原稿作者资料，标注预览日期；导出选择语言、栏数和格式。']},
 {'id':'figures','name':'程序与图形精修','entry':'程序 → 文件 / 图形 → 精修与 Agent','input':'实际程序、原始图像、已选对象与修改要求','output':'当前程序、可编辑图形、原图或矢量导出与来源关系','steps':['先选择当前程序或图形，核对来源和使用位置。','在画布修改对象，或把所选内容交给右侧 Agent。','预览并保存，历史保留修改原因与可恢复原件。']},
 {'id':'slides','name':'研究汇报','entry':'PPT → 模板与汇报设置','input':'确认的研究内容、受众、篇幅和模板','output':'可编辑幻灯片、讲稿、PowerPoint/PDF 与生成记录','steps':['选择模板、受众与本次汇报要求。','确认内容与模板后生成，逐页检查文字、图表和讲稿。','更改内容后重新导出当前版本。']},
 {'id':'records','name':'修改、处理与结果回执','entry':'修改记录；对象批注；顶部任务','input':'对象、页码或位置、问题和任务 ID','output':'可读差异、处理历史、当前产物和验证结果','steps':['按对象与类别定位问题和修改。','查看修改前后差异，必要时恢复旧版。','Agent 回执说明改了哪些产物、做了什么验证及仍有限制。']},
 {'id':'api','name':'API、技能与 MCP','entry':'工作台设置 → 使用与 MCP','input':'当前账户会话、项目 ID 和具体任务参数','output':'工具结果、异步任务 ID、文件 URL 与结构化回执','steps':['MCP 使用当前账户的专用登录会话或 bearer token。','先读任务规则与能力清单，再调用对应工具。','长任务返回 job_id，待 completed 后读取结果和下载文件。']},
]


def install(app):
    @app.get('/research/api/integrations/workbench')
    async def guide(user=Depends(actor)):
        package=ROOT/'dist/research-workbench-mcp.zip';manifest=ROOT/'integrations/workbench-mcp/tool-manifest.json'
        return {'features':FEATURES,'mcp':{'available':package.is_file(),'download':'/research/api/integrations/mcp-package' if package.is_file() else None,'tools':json.loads(manifest.read_text()) if manifest.is_file() else [],'guide':'/research/api/integrations/guide'},'api':{'schema':'/research/api/schema','rules':'/research/api/standards','projects':'/research/api/projects'},'authentication':'使用当前账户；项目、知识库、文件与处理记录保留账户归属。'}

    @app.get('/research/api/integrations/guide')
    async def manual(user=Depends(actor)):
        path=ROOT/'integrations/workbench-mcp/USAGE.md'
        if path.is_file():return PlainTextResponse(path.read_text(encoding='utf8'))
        return PlainTextResponse('\n\n'.join('## '+v['name']+'\n'+v['entry']+'\n'+'\n'.join(v['steps']) for v in FEATURES))

    @app.get('/research/api/integrations/mcp-package')
    async def package(user=Depends(actor)):
        path=ROOT/'dist/research-workbench-mcp.zip'
        if not path.is_file():raise ValueError('MCP 安装包正在准备，尚未发布')
        return FileResponse(path,filename=path.name,media_type='application/zip')
