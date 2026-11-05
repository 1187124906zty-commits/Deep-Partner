"""Tutor delegates implementation; Code returns organized project artifacts."""
import asyncio
import base64
from contextlib import suppress
import json
from pathlib import Path
import uuid

import httpx

from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.services.auth import create_token
from deeptutor.multi_user.context import get_current_user_or_none
from tutor_deepcode.tutor_adapter import CoderTool, _TutorTurn, _bind, _snapshot
from tutor_deepcode.protocol import digest, safe_relative, validate_task
from dify_delivery import ResearchWorkbenchTool, authority as delivery_authority

ORIGIN = 'https://tutor.example.invalid'
WORKBENCH = ORIGIN + '/research/api/projects/'
BRIDGE = ORIGIN + '/research/dify'
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.json', '.csv', '.tsv', '.yaml', '.yml', '.toml', '.c', '.cpp', '.h', '.sh', '.sbatch', '.m', '.r'}


async def inventory(client, base):
    files, todo = [], ['']
    while todo and len(files) < 250:
        path = todo.pop(0)
        response = await client.get(base + '/files', params={'path': path})
        response.raise_for_status()
        for row in response.json()['items']:
            relative = row['path']
            if any(part.startswith('.') for part in relative.split('/')):
                continue
            kind = str(row.get('type') or row.get('kind') or '')
            if kind in {'directory', 'dir', 'folder'} or row.get('is_dir'):
                if relative.count('/') < 5:
                    todo.append(relative)
            else:
                files.append(row)
    return files


def export_manifest(folder, task_id):
    root = Path(folder).resolve(strict=True)
    manifest_path = root / 'research-handoff.json'
    if not manifest_path.is_file() or manifest_path.stat().st_size > 1000000:
        raise ValueError('Code has not produced research-handoff.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('task_id') != task_id or manifest.get('schema_version') != 1:
        raise ValueError('The Code handoff belongs to a different task')
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 40:
        raise ValueError('Code must explicitly list 1-40 deliverable artifacts')
    selected, seen = [], set()
    for item in artifacts:
        path = safe_relative(item['path'])
        published_path = 'docs/' + path if path in {'verification.json', 'research-handoff.json'} else path
        if published_path in seen or published_path.split('/')[0] not in {'src', 'data', 'results', 'docs'}:
            raise ValueError('Artifacts belong in src/, data/, results/ or docs/')
        seen.add(published_path)
        target = root / path
        cursor = root
        for part in Path(path).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError('Deliverable files cannot be symlinks')
        if not target.is_file() or not target.resolve().is_relative_to(root) or target.stat().st_size > 16000000:
            raise ValueError('Missing, external or oversized artifact: ' + path)
        selected.append((published_path, target, str(item.get('summary') or 'Code research deliverable')))
    if 'docs/code-handoff.md' not in seen:
        raise ValueError('A concise docs/code-handoff.md is required for Tutor')
    return manifest, selected


async def publish_handoff(client, code, project_context, turn):
    pid = project_context['project']['id']
    base = WORKBENCH + pid
    metadata = {row['path']:row for row in project_context['file_inventory']}
    folder = Path('/workspace/coder/projects') / code['project']
    manifest, artifacts = export_manifest(folder, code['id'])
    receipts = []
    for path, source, summary in artifacts:
        data = source.read_bytes()
        previous = metadata.get(path)
        text = None
        if source.suffix.lower() in TEXT_SUFFIXES and len(data) <= 2000000:
            text = data.decode('utf-8')
        if text is not None:
            artifact = {'type':'file', 'path':path, 'content':text, 'summary':summary}
            if previous is not None:
                artifact['expected_modified'] = previous.get('modified') or previous.get('modified_at')
        else:
            if previous is not None:
                raise ValueError('Replacing an existing binary requires the workbench versioned upload interface: ' + path)
            response = await client.post(base + '/files', data={'path':str(Path(path).parent).replace('\\','/')},
                files=[('files', (Path(path).name, data, 'application/octet-stream'))])
            response.raise_for_status()
            artifact = {'type':'existing', 'path':path, 'summary':summary}
        saved = await client.post(BRIDGE + '/api/deliver', json={
            'request_id':'code-' + uuid.uuid5(uuid.NAMESPACE_URL, code['id'] + ':' + path).hex,
            'project_id':pid, 'workspace_id':turn.workspace_id, 'session_id':turn.session_id,
            'task':'code', 'standard_version':project_context['standard_version'], 'artifact':artifact,
            'validation':manifest.get('validation', []), 'limitations':manifest.get('limitations', [])})
        saved.raise_for_status()
        receipt = saved.json()
        if receipt.get('status') != 'saved':
            raise ValueError('Publication did not confirm saved for ' + path)
        receipts.append({'path':path, 'workspace_path':'project/' + path, 'status':'saved', 'run_id':receipt['run_id']})
    summary = (folder / 'docs/code-handoff.md').read_text(encoding='utf-8')
    return ToolResult(content=json.dumps({'status':'completed', 'task_id':code['id'], 'project_id':pid,
        'files':receipts, 'handoff_summary':summary[:10000], 'summary_truncated':len(summary)>10000,
        'source_coverage':project_context['source_coverage'], 'validation':manifest.get('validation', []),
        'limitations':manifest.get('limitations', []), 'verification':code.get('verification'),
        'instruction':'Read the handoff first. When needed, use workspace_read with the returned workspace_path, or workspace_search within project/; do not repeat the complete computation.'}, ensure_ascii=False), success=True)


class ResearchCodeTool(BaseTool):
    def get_definition(self):
        return ToolDefinition('research_code',
            '把当前项目的研究实施交给真实DeepCode。Tutor先给研究问题、理由与必要约束；本工具自动交接当前对话、项目规范、'
            '文件清单及有限相关输入。Code负责编程、数据处理、计算和数值检查，并按src/data/results/docs整理交付。'
            '完成后自动按版本规则写回同一研究工作台，仅向Tutor返回交接摘要、状态与文件位置。'
            'plan只读；code实施；status查询并恢复已完成任务的交接发布；cancel取消。使用返回的任务编号，勿重复实施。'
            'paths可补充明确相关的项目相对文件。', parameters=[
                ToolParameter('action', 'string', enum=['plan', 'code', 'status', 'cancel']),
                ToolParameter('task', 'string', '研究实施目标、为什么做、已知约束及希望回答的问题', required=False, default=''),
                ToolParameter('paths', 'array', '优先交接的当前项目相对文件，最多20项；无须填写物理路径', required=False, default=[], items={'type':'string'}, max_items=20),
                ToolParameter('task_id', 'string', '实际任务编号', required=False, default=''),
            ])

    async def execute(self, action, task='', paths=None, task_id='', _research_turn=None, **kwargs):
        turn = _research_turn
        if not isinstance(turn, _TutorTurn):
            return ToolResult(content='Research Code requires the authenticated research conversation.', success=False)
        if action == 'cancel':
            return await CoderTool().execute(action, task_id=task_id, _coder_turn=turn, **kwargs)
        if action == 'status':
            status = await CoderTool().execute(action, task_id=task_id, _coder_turn=turn, **kwargs)
            if not status.success:
                return status
            code = json.loads(status.content)
            if code.get('status') != 'completed':
                return status
            try:
                snapshot = Path('/workspace/coder/projects') / code['project'] / '.deeptutor/contexts' / (code['id'] + '.json')
                envelope = json.loads(snapshot.read_text(encoding='utf-8'))
                project_context = envelope['context']['research_project']
                user = get_current_user_or_none()
                token = create_token(user.username, user.role, user.id)
                async with httpx.AsyncClient(timeout=120, trust_env=False,
                    headers={'Authorization':'Bearer ' + token, 'Origin':ORIGIN}) as client:
                    return await publish_handoff(client, code, project_context, turn)
            except Exception as error:
                return ToolResult(content=json.dumps({'status':'publication_unconfirmed', 'task_id':task_id,
                    'error':str(error), 'instruction':'Query status with this same task_id to resume publication; do not repeat code execution.'}, ensure_ascii=False), success=False)
        if action not in {'plan', 'code'} or not task.strip():
            return ToolResult(content='Provide an implementation question for plan or code.', success=False)
        collector = asyncio.create_task(turn.collect()) if turn.stream is not None else None
        active_task = ''
        try:
            auth = delivery_authority(turn.context)
            context_result = await ResearchWorkbenchTool().execute('context', task='code', _authority=auth)
            if not context_result.success:
                return context_result
            project_context = json.loads(context_result.content)
            project = project_context['project']
            pid = project['id']
            user = get_current_user_or_none()
            token = create_token(user.username, user.role, user.id)
            headers = {'Authorization': 'Bearer ' + token, 'Origin': ORIGIN}
            async with httpx.AsyncClient(timeout=120, trust_env=False, headers=headers) as client:
                base = WORKBENCH + pid
                rows = await inventory(client, base)
                chosen = [safe_relative(p) for p in (paths or [])]
                eligible = [row['path'] for row in rows if Path(row['path']).suffix.lower() in TEXT_SUFFIXES
                            and int(row.get('size') or row.get('size_bytes') or 0) <= 256000]
                chosen = list(dict.fromkeys(chosen + eligible))[:40]
                inputs, size, omitted = [], 0, []
                for path in chosen:
                    response = await client.get(base + '/file', params={'path': path})
                    if response.status_code != 200:
                        omitted.append({'path': path, 'reason': 'not_readable'})
                        continue
                    data = response.content
                    if size + len(data) > 6000000:
                        omitted.append({'path': path, 'reason': 'input_budget'})
                        continue
                    inputs.append({'path': path, 'content_b64': base64.b64encode(data).decode(),
                                   'source_id': 'workbench:' + pid + ':' + path, 'source_name': path})
                    size += len(data)
                brief = ('Research implementation contract. Tutor owns research dialogue, motivation, route choices and interpretation. '
                    'You are the Code Agent: own implementation, data processing, computational checks, organizing artifacts and factual handoff. '
                    'Read the supplied research_project context and input manifest; preserve equations, units, constraints and relevant dialogue. '
                    'Use the current project skills and research-compute-validation for numerical work; use the configured research-compute MCP '
                    'for Slurm execution rather than the old raw SSH cluster route. No second research lead is needed. '
                    'Arrange formal deliverables in src/, data/, results/, docs/. Keep large raw fields on the cluster and put a source/location '
                    'manifest in data/. Write a concise docs/code-handoff.md for Tutor (about 300-800 Chinese characters or comparable length; '
                    'put lengthy derivations and diagnostics in a separate report): question answered, files, observed metrics, comparison, limitations, '
                    'failures and one decision needing research interpretation. Distinguish theory checks and experimental validation. '
                    'When code mode finishes, write research-handoff.json with schema_version=1, this actual task_id from the native handoff file, '
                    'and artifacts=[{path,summary}] listing actual files to publish, including docs/code-handoff.md. '
                    'The application publishes only this explicit list into the source research project with version conflict checks. '
                    'Do not claim saved before publication returns a receipt. For plan mode return the plan without publishing. '
                    'Implement this finite task: ' + task)
                project_name = 'research_' + pid
                envelope = await _snapshot(turn, brief, action, project_name, None)
                envelope['context']['research_project'] = {key:value for key,value in project_context.items() if key != 'manuscript'}
                envelope['context']['research_project']['file_inventory'] = rows
                envelope['context']['research_project']['source_coverage'] = {'copied': [i['path'] for i in inputs], 'omitted': omitted,
                    'selection': 'explicit paths first; bounded text/code/data files; large files remain at their source'}
                envelope['inputs'].extend(inputs)
                envelope['identity']['source_revision'] = digest(envelope['context'])
                validate_task(envelope)
                turn.envelopes[envelope['identity']['command_id']] = envelope
                result = await CoderTool().execute(action, task=brief, project=project_name, _coder_turn=turn, **kwargs)
                if not result.success or action == 'plan':
                    return result
                code = json.loads(result.content)
                active_task = code.get('id') or ''
                if code.get('status') != 'completed':
                    return result
                return await publish_handoff(client, code, envelope['context']['research_project'], turn)
        except Exception as error:
            return ToolResult(content=json.dumps({'status':'publication_unconfirmed' if active_task else 'handoff_unconfirmed',
                'task_id':active_task, 'error':str(error),
                'instruction':'Query status with the same task_id; do not repeat a completed computation.'}, ensure_ascii=False), success=False)
        finally:
            if collector is not None:
                collector.cancel()
                with suppress(asyncio.CancelledError):
                    await collector


class ResearchDelegation:
    name = 'research_delegation'
    owned_tools = ('research_code',)

    def is_active(self, context):
        user = get_current_user_or_none()
        return user is not None and user.role == 'admin'

    async def pre_loop(self, context, stream, **kwargs):
        _bind(context, stream)
        return None

    def system_block(self, context, **kwargs):
        return PromptBlock(self.name,
            '科研协作分工：你作为Tutor先从对话和资料提出研究思路，解释为什么值得做，明确问题与必要约束。'
            '把编程、数据处理、计算评估和技术产物整理交给research_code；该工具会自动携带当前项目规范、相关对话和输入。'
            'Code Agent按工作台src/data/results/docs整理结果并回交简短说明；你先阅读交接摘要，需要时再定向读取或检索文件。'
            '保存文件的工作区路径为project/加产物路径；用原生workspace_read读取、workspace_search在project/内检索。'
            '你负责结合研究主题解释证据、提出下一步和与用户讨论。按问题复杂程度调整深度：概念问答直接解释；'
            '简单算例可直接说明；需要实际程序、数据或研究计算时委托Code，不默认自己重复跑完整验证。'
            '原始证据保存在项目文件和计算记录；L3只保存带条件的跨会话经验，不能代替来源与运行结果。'
            '科学选择存在关键歧义时与你和用户沟通，常规实施由Code自行完成。')

    def augment_kwargs(self, tool_name, kwargs, context):
        return {**kwargs, '_research_turn':_bind(context)} if tool_name == 'research_code' else kwargs

    def pre_loop_seed(self, context):
        return ''
