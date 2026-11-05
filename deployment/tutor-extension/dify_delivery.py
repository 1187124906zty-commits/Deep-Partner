"""Native DeepTutor extension: retain the turn, skills, account, and workspace."""
from dataclasses import dataclass
import json
import os
import uuid

import httpx

from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.multi_user.context import get_current_user_or_none
from deeptutor.services.auth import create_token
from deeptutor.services.workspace.context import current_workspace_id

BASE = os.environ.get("DIFY_WORKBENCH_BRIDGE_URL", "https://tutor.example.invalid/research/dify")


@dataclass(frozen=True)
class Authority:
    user_id: str
    username: str
    role: str
    workspace_id: str
    session_id: str
    turn_id: str


def authority(context):
    user = get_current_user_or_none()
    if user is None:
        return None
    return Authority(user.id, user.username, user.role, current_workspace_id(),
                     context.session_id, str(getattr(context, "turn_id", "") or context.metadata.get("turn_id", "")))


class ResearchWorkbenchTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            "research_workbench",
            "连接当前账户的研究工作台。projects 列出项目；context 读取当前项目规范、按需技能目录及读取入口、写入协议与稿件版本；"
            "search 按需检索网页或项目论文题录，或查看来源配置，无需先创建成果交付任务；"
            "deliver 通过 Dify 工作流校验并保存一个成果，回读后记录回执；status 查询同一交付任务；"
            "activity 查看当前项目的近期交付、自动回调与服务检查状态。"
            "evidence 并行查询知识库、网页和论文，保留每路来源状态与片段；evidence_status 回读原检索。"
            "library 读取或整理项目真实文献库：list 返回文献与文件夹，organize 保存主题文件夹与文献归属并回读。"
            "research 读取研究主线、回查受影响记录的原始材料、保存范围内的纠正，或提出大纲修订。"
            "当前会话、账户和工作区由服务器绑定。正式内容只在 status=saved 后视为已保存。",
            parameters=[
                ToolParameter("action", "string", enum=["projects", "context", "search", "evidence", "evidence_status", "deliver", "status", "activity", "library", "research"]),
                ToolParameter('research_operation','string','overview读主线/记录/修订历史；inspect回查记录及关联原始材料；update保存已回查的纠正；outline提出主线或大纲修订',enum=['overview','inspect','update','outline'],required=False,default='overview'),
                ToolParameter('research_json','string','inspect: {request:本次作者要求,record_ids:[已有ID],paths:[当前项目文件路径]}；update: {inspection_id,reason,source_ids:[实际read来源ID],record_updates:[{id,label/detail/status}],task_updates:[{id,understanding/next_step}],remove_relation_ids:[],relations:[{source,target,relation}],conflicts:[],scope_change:false}。主线/科学选择变化使用outline: {revision,instruction}；不自动采用。',required=False,default=''),
                ToolParameter('library_action','string','list读取真实文献库；organize保存主题文件夹及归属',enum=['list','organize'],required=False,default='list'),
                ToolParameter('organization_json','string','organize JSON：{"expected_revision":0,"folders":[{"id":"topic-1","name":"主题名称","kind":"topic"}],"memberships":{"workspace/reading/paper.pdf":["topic-1"]},"reason":"用户要求"}。先list取得实际文献键和revision；不移动原文。',required=False,default=''),
                ToolParameter("project_id", "string", "默认从当前工作区解析；根聊天先 projects，再选择用户所指项目", required=False, default=""),
                ToolParameter("task", "string", enum=["code", "code-review", "test", "paper", "translation", "literature", "slides", "review", "figure"], required=False, default="review"),
                ToolParameter("standard_version", "string", "context 返回的 standard_version，deliver 必填", required=False, default=""),
                ToolParameter("artifact_json", "string", '一个成果的JSON。文本例：{"type":"file","path":"docs/研究说明.md",'
                              '"content":"正文","summary":"修改说明"}，替换现有文件还需expected_modified。'
                              '稿件用{"type":"manuscript","document":完整工作台文档含当前revision,"summary":"修改说明"}；'
                              '已生成的project/文件用{"type":"existing","path":"results/figure.png","summary":"说明"}。'
                              'PPT、图和二进制先用原生能力生成。', required=False, default=""),
                ToolParameter("question_ids", "array", "本项目已存在的问题ID", required=False, default=[], items={"type": "string"}),
                ToolParameter("validation", "array", "实际进行的验证，含check/result/evidence；未运行须写not_run", required=False, default=[], items={"type": "object"}),
                ToolParameter("limitations", "array", "仍存在的限制", required=False, default=[], items={"type": "string"}),
                ToolParameter("run_id", "string", "status 使用实际返回的run_id", required=False, default=""),
                ToolParameter('query','string','search 的真实检索式，3至600字；sources 无需填写',required=False,default=''),
                ToolParameter('search_kind','string','web 查公开网页；papers 查论文题录；page 读取已知公开 HTTPS 网页正文；sources 查看来源配置',
                    enum=['web','papers','page','sources'],required=False,default='papers'),
                ToolParameter('source','string','papers 的来源；明确选 Scholar 时不暗中切换，auto 可返回标明来源的降级结果',
                    enum=['auto','scholar_mcp','academic_web','crossref','semantic','scholar','wos'],required=False,default='auto'),
                ToolParameter('page','integer','papers 的结果页，1至50',required=False,default=1),
                ToolParameter('limit','integer','papers 每页1至20项，Scholar MCP最多10项',required=False,default=10),
                ToolParameter('knowledge_base','string','evidence 可指定当前项目已绑定的知识库；默认前两个绑定库',required=False,default=''),
                ToolParameter('evidence_sources','array','evidence 选用 knowledge/web/papers，默认三路',required=False,
                    default=['knowledge','web','papers'],items={'type':'string'}),
            ],
        )

    async def execute(self, action, project_id="", task="review", standard_version="", artifact_json="",
                      question_ids=None, validation=None, limitations=None, run_id="", query='', search_kind='papers',
                      source='auto', page=1, limit=10, knowledge_base='', evidence_sources=None, library_action='list',organization_json='', research_operation='overview',research_json='',_authority=None, **kwargs):
        if not isinstance(_authority, Authority):
            return ToolResult(content="缺少当前账户的服务器身份。", success=False)
        auth = _authority
        token = create_token(auth.username, auth.role, auth.user_id)
        try:
            async with httpx.AsyncClient(timeout=150, trust_env=False) as client:
                headers = {"Authorization": "Bearer " + token}
                if action == "projects":
                    response = await client.get(BASE + "/api/projects", headers=headers)
                elif action == "context":
                    response = await client.get(BASE + "/api/context", headers=headers,
                        params={"project_id": project_id, "task": task, "workspace_id": auth.workspace_id})
                elif action == 'activity':
                    response = await client.get(BASE + '/api/activity', headers=headers,
                        params={'project_id': project_id, 'workspace_id': auth.workspace_id})
                elif action == 'evidence':
                    response = await client.post(BASE + '/api/evidence', headers=headers,json={
                        'project_id':project_id,'workspace_id':auth.workspace_id,'query':query,
                        'sources':evidence_sources or ['knowledge','web','papers'],
                        'knowledge_base':knowledge_base,'paper_source':source,'limit':min(limit,10)})
                elif action == 'evidence_status':
                    if not run_id:raise ValueError('需要实际返回的检索 run_id')
                    response = await client.get(BASE + '/api/evidence/' + run_id, headers=headers)
                elif action == 'research':
                    context=await client.get(BASE+'/api/context',headers=headers,
                        params={'project_id':project_id,'task':'review','workspace_id':auth.workspace_id})
                    context.raise_for_status();pid=context.json()['project']['id']
                    prefix=BASE.split('/research/dify',1)[0]+'/research/api/projects/'+pid
                    if research_operation=='overview':
                        value={'project_id':pid}
                        for key,path in [('outline','research-outline'),('records','research-flow/graph?limit=2000'),('updates','research-updates')]:
                            item=await client.get(prefix+'/'+path,headers=headers);item.raise_for_status();value[key]=item.json()
                        for version in ('active','draft'):
                            document=value['outline'].get(version)
                            if document:document['sources']=[{k:v for k,v in source.items() if k!='text'} for source in document['sources']]
                        value['updates']['updates']=value['updates']['updates'][:12]
                        return ToolResult(content=json.dumps(value,ensure_ascii=False),success=True)
                    paths={'inspect':'research-updates/inspect','update':'research-updates/apply','outline':'research-outline/generate'}
                    if research_operation not in paths:raise ValueError('未知的研究操作')
                    response=await client.post(prefix+'/'+paths[research_operation],headers=headers,json=json.loads(research_json or '{}'))
                elif action == 'library':
                    context=await client.get(BASE+'/api/context',headers=headers,
                        params={'project_id':project_id,'task':'literature','workspace_id':auth.workspace_id})
                    context.raise_for_status();pid=context.json()['project']['id']
                    origin=BASE.split('/research/dify',1)[0];prefix=origin+'/research/api/projects/'+pid+'/literature'
                    if library_action=='list':
                        docs=await client.get(prefix+'/items',headers=headers);docs.raise_for_status()
                        folders=await client.get(prefix+'/folders',headers=headers);folders.raise_for_status()
                        data=docs.json();data['organization']=folders.json();data['project_id']=pid
                        return ToolResult(content=json.dumps(data,ensure_ascii=False),success=True)
                    if library_action!='organize':raise ValueError('library_action 应为 list 或 organize')
                    response=await client.patch(prefix+'/folders',headers=headers,json=json.loads(organization_json))
                elif action == 'search':
                    origin=BASE.split('/research/dify',1)[0]
                    if search_kind=='sources':
                        response=await client.get(origin+'/research/api/search/sources',headers=headers)
                    elif search_kind=='page':
                        response=await client.get(BASE+'/api/web-evidence',headers=headers,params={'url':query})
                    elif search_kind=='web':
                        if not 3<=len(query.strip())<=600:raise ValueError('检索式应为3至600字')
                        response=await client.get(origin+'/research/api/search/web',headers=headers,params={'q':query})
                    elif search_kind=='papers':
                        if not 3<=len(query.strip())<=600 or not 1<=page<=50 or not 1<=limit<=20:
                            raise ValueError('请检查检索式、页码和结果数量')
                        context=await client.get(BASE+'/api/context',headers=headers,
                            params={'project_id':project_id,'task':'literature','workspace_id':auth.workspace_id})
                        context.raise_for_status()
                        project_id=context.json()['project']['id']
                        response=await client.get(origin+'/research/api/projects/'+project_id+'/literature/search',
                            headers=headers,params={'q':query,'source':source,'page':page,'limit':limit})
                    else:raise ValueError('请选择 web、papers、page 或 sources')
                elif action == "status":
                    if not run_id:
                        raise ValueError("需要上次交付返回的 run_id")
                    response = await client.get(BASE + "/api/runs/" + run_id, headers=headers)
                elif action == "deliver":
                    if not project_id:
                        context = await client.get(BASE + "/api/context", headers=headers,
                            params={"task": task, "workspace_id": auth.workspace_id})
                        context.raise_for_status()
                        project_id = context.json()["project"]["id"]
                    body = {"project_id": project_id, "workspace_id": auth.workspace_id,
                            "session_id": auth.session_id, "task": task, "standard_version": standard_version,
                            "artifact": json.loads(artifact_json) if artifact_json else {}, "question_ids": question_ids or [],
                            "validation": validation or [], "limitations": limitations or []}
                    identity = auth.user_id + ":" + auth.session_id + ":" + auth.turn_id + ":" + json.dumps(body, sort_keys=True, ensure_ascii=False)
                    body["request_id"] = "dt-" + uuid.uuid5(uuid.NAMESPACE_URL, identity).hex
                    response = await client.post(BASE + "/api/deliver", headers=headers, json=body)
                else:
                    raise ValueError("不支持的操作")
                if not response.is_success:
                    raise ValueError(str(response.json().get("detail", "工作台暂不可用")))
                result = response.json()
            return ToolResult(content=json.dumps(result, ensure_ascii=False),
                success=result.get('status') not in {'failed','unavailable'} and not result.get('error'))
        except (httpx.HTTPError, ValueError) as exc:
            return ToolResult(content="工作台交付未确认：" + str(exc), success=False)


class WorkbenchDelivery:
    name = "dify_workbench_delivery"
    owned_tools = ("research_workbench",)

    def is_active(self, context):
        return authority(context) is not None

    def system_block(self, context, **kwargs):
        text = (
            "本站研究工作台已连接 Dify 成果交付流程。研究任务涉及工作台项目时，先用 research_workbench context "
            "读取当前项目输出规范；按when_to_use读取本次相关技能，涉及稿件时再读取当前稿件。沿用本轮会话推理与原工具完成任务。"
            "当前请求和明确更正确定任务；项目记忆与历史计划提供背景，不能扩大任务或替换科学方法。"
            "在已确定主线、授权和资源范围内自主接续所需检索、阅读、代码和计算；总览层级用于组织研究，不规定固定研究顺序。"
            "收到作者纠正时，用research/overview找到受影响的记录和任务，再用inspect回读原始材料；必要时用evidence继续调查。"
            "区分方法名称、计算机制和领域贡献。依据一致的日常纠正用update保存记录、关系与下一步，并报告变更；证据冲突、关键科学选择或范围变化用outline提出修订并询问作者。"
            "需要项目论文题录或公开网页证据时用 search；sources只报告配置，本次可用性以实际结果为准。"
            "search不启动成果交付；失败与无匹配分别报告，自动切换来源时说明实际来源。"
            "需要多来源证据时用 evidence 联合检索，查看 coverage 与 missing_sources，再按缺口定向补查。"
            "检索片段和题录不等于全文证据；写作与研究结论仍需回读原文。activity可查看自动交付与故障恢复状态。"
            "整理文献库时用 library/list 读取真实文献与文件夹，library/organize 写回自定义主题及归属，回读verified=true才报告完成。"
            "仅生成分类表、目录副本或ZIP不会更新文献库。文献库使用本站工作台接口；阅读器进程连接失败不代表文献库不可用。"
            "把可复用的研究成果交付到对应的当前程序、稿件或项目文件，保留真实来源和验证范围。"
            "调用 deliver 写回，得到 status=saved 后在回复中给出成果位置；未保存时说明实际状态，"
            "用 status 查询同一 run_id。普通问答无需强行生成文件。代码、图和PPT的执行与导出继续用原生能力，"
            "不能把Dify的保存成功说成科学验证或排版验收成功。"
        )
        return PromptBlock(self.name, text)

    def augment_kwargs(self, tool_name, kwargs, context):
        return {**kwargs, "_authority": authority(context)} if tool_name == "research_workbench" else kwargs

    def pre_loop_seed(self, context):
        return ""
