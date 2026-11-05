"""Use the compute MCP from a server-bound DeepTutor admin turn."""
import json
import os
from pathlib import Path
import uuid

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.multi_user.context import get_current_user_or_none
from deeptutor.services.workspace.context import current_workspace_id


def authority(context):
    user = get_current_user_or_none()
    if user is None or user.role != 'admin':
        return None
    return {'owner_id': user.id, 'workspace_id': current_workspace_id(),
            'session_id': str(context.session_id),
            'turn_id': str(getattr(context, 'turn_id', '') or context.metadata.get('turn_id', ''))}


class ComputeAuthority:
    def __init__(self, identity):
        self.identity = identity


class ResearchComputeTool(BaseTool):
    def get_definition(self):
        return ToolDefinition('research_compute',
            '在真实Slurm集群准备、提交、查询计算，读取原始结果，并按运行前锁定的数值判据评估。'
            '先inventory。prepare用spec_json传question、runtime(python/paso/torch/openpaso/openpaso_catalog)、'
            'files[{path,content}]、entrypoint、criteria[{name,metric,op(lt/le/gt/ge/eq),threshold,unit}]、'
            'reference、limitations、resources{cpus,memory_mb,minutes}。程序将实测数值写入outputs/metrics.json的metrics对象。'
            'prepare后submit，稍后status；COMPLETED和exit 0只代表执行成功，再assess/read评价数值。'
            'read读取实验相对路径；openpaso_schema读取catalog作业的真实工具schema。'
            '资源上限4CPU/8GB/15分钟，异步作业不占登录节点计算。', parameters=[
                ToolParameter('action', 'string', enum=['inventory', 'prepare', 'submit', 'status', 'read', 'assess', 'cancel', 'openpaso_schema']),
                ToolParameter('spec_json', 'string', 'prepare的实验输入；其他动作留空', required=False, default=''),
                ToolParameter('experiment_id', 'string', 'prepare返回的实际实验ID', required=False, default=''),
                ToolParameter('path', 'string', 'read的实验相对文件路径', required=False, default=''),
                ToolParameter('tool', 'string', 'openpaso_schema的真实工具名', required=False, default=''),
            ])

    async def execute(self, action, spec_json='', experiment_id='', path='', tool='', _compute_authority=None, **kwargs):
        if not isinstance(_compute_authority, ComputeAuthority):
            return ToolResult(content='计算工具需要当前管理员会话的服务器身份。', success=False)
        identity = _compute_authority.identity
        payload = {'identity': identity, 'experiment_id': experiment_id, 'path': path, 'tool': tool}
        try:
            if action == 'prepare':
                payload['spec'] = json.loads(spec_json)
                stable = json.dumps([identity, payload['spec']], sort_keys=True, ensure_ascii=False)
                payload['request_id'] = 'dt-' + uuid.uuid5(uuid.NAMESPACE_URL, stable).hex
            token = Path(os.environ.get('RESEARCH_COMPUTE_TOKEN_FILE', '/opt/dify-delivery/compute-token')).read_text().strip()
            url = os.environ.get('RESEARCH_COMPUTE_MCP_URL', 'http://research-compute:47920/mcp')
            async with streamablehttp_client(url, headers={'Authorization': 'Bearer ' + token}, timeout=90) as channels:
                async with ClientSession(channels[0], channels[1]) as session:
                    await session.initialize()
                    result = await session.call_tool('research_compute', {'action': action, 'payload': payload})
            text = '\n'.join(item.text for item in result.content if getattr(item, 'type', '') == 'text')
            return ToolResult(content=text, success=not result.isError)
        except Exception as error:
            return ToolResult(content='计算状态未确认：' + str(error) + '。保留原experiment_id查询，勿重复提交。', success=False)


class ResearchCompute:
    name = 'research_compute'
    owned_tools = ('research_compute',)

    def is_active(self, context):
        return authority(context) is not None

    def system_block(self, context, **kwargs):
        return PromptBlock(self.name,
            '当前管理员已接入真实科研计算MCP research_compute。用户要求通过计算检验方法、程序、数值或研究结论时，'
            '先读取research-compute-validation技能（如可用），明确可证伪问题、基线/解析参照、量纲和判据，'
            '用该工具prepare→submit→status→assess/read形成实测证据。提交成功不代表完成；执行成功不代表物理正确。'
            '小任务可在本轮等待合理时长，大任务返回真实作业ID并在后续同一会话继续。明确负面与未知结果。'
            '持续多文件实现用现有代码模式的DeepCode，它也可调用同一个计算MCP。openPASO求解在Slurm作业内运行。'
            '研究成果通过research_workbench交付到当前项目，保存原始远端路径、作业ID、输入和实际指标；'
            'L3记忆只保存有条件的经验，原始数值证据留在计算记录与项目文件。')

    def augment_kwargs(self, tool_name, kwargs, context):
        if tool_name == 'research_compute':
            return {**kwargs, '_compute_authority': ComputeAuthority(authority(context))}
        return kwargs

    def pre_loop_seed(self, context):
        return ''
