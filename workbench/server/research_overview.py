"""A source-linked research view; execution state never establishes a finding."""
from collections import Counter
from urllib.parse import quote, urlencode
from fastapi import Depends
from .storage import child, now

SECTIONS = [
    ('questions', '研究问题', {'question'}),
    ('approaches', '思路与方法', {'method', 'idea', 'decision'}),
    ('findings', '已有发现', {'finding'}),
    ('open_questions', '待解决问题', {'gap', 'limitation'}),
    ('materials', '研究材料', {'paper', 'implementation', 'memo'}),
]
STATE_LABELS = {'known': '已有依据', 'partial': '部分明确', 'proposed': '待验证的提议',
                'unknown': '尚未明确', 'not_found_in_scope': '本次检索未找到', 'recorded': '已记录'}


def source_link(root, pid, native_id, ref):
    """Resolve recorded locators without pretending missing files are available."""
    base = '/research/api/projects/' + pid
    result = {**ref, 'available': False}
    try:
        if ref.get('asset'):
            result['label'] = ref['asset'].split('/')[-1]
            if child(root / 'literature', ref['asset']).is_file():
                result.update(available=True, url=base+'/literature/file?asset='+quote(ref['asset'], safe=''))
        elif ref.get('path'):
            result['label'] = ref['path'].split('/')[-1]
            if child(root / 'project', ref['path']).is_file():
                result.update(available=True, url=base+'/file?path='+quote(ref['path'], safe=''))
        elif ref.get('session_id'):
            result.update(available=True, label='相关研究对话', url='/research/?'+urlencode(
                {'project': pid, 'dt_workspace': native_id, 'session': ref['session_id']}))
        elif str(ref.get('url', '')).startswith(('https://', 'http://')):
            result.update(available=True, label='原始来源')
        else:
            result['label'] = '研究记录 ' + str(ref.get('record_id', ''))
    except (ValueError, OSError):
        result['label'] = str(ref.get('path') or ref.get('asset') or '来源')
    if ref.get('pages'):
        result['label'] += ' · 第 ' + '、'.join(map(str, ref['pages'])) + ' 页'
        if result['available'] and ref.get('asset'):
            result['url'] += '#page=' + str(ref['pages'][0])
    return result


def snapshot(store, owner, pid, per_section=24):
    from .research_flow import graph
    from .project_progress import ROUTE_NAMES
    project = store.get(owner, pid)
    root = store.path(owner, pid)
    # Graph records precede unreviewed library entries. One bounded read is enough
    # for this view; disclose coverage instead of representing it as exhaustive.
    data = graph(store, owner, pid, limit=2000)
    nodes = data['nodes']
    connected = {e[k] for e in data['edges'] for k in ('source', 'target')}
    sections = []
    for sid, label, kinds in SECTIONS:
        matches = sorted((n for n in nodes if n['kind'] in kinds),
                         key=lambda n: ((n['kind'] in ('method', 'idea'), n['id'] in connected)
                                        if sid == 'approaches' else (False, False),
                                        n.get('updated', '')), reverse=True)
        items = []
        for node in matches[:per_section]:
            items.append({**node, 'detail': str(node.get('detail', ''))[:6000],
                'status_label': STATE_LABELS.get(node.get('status'), '状态待说明'),
                'sources': [source_link(root, pid, project.get('native_id', ''), ref)
                            for ref in node.get('evidence_refs', [])]})
        sections.append({'id': sid, 'label': label, 'count': len(matches), 'items': items})
    selected = {n['id'] for section in sections for n in section['items']}
    jobs = store.jobs(owner, pid)
    attention = []
    for job in jobs:
        if job['status'] not in ('running', 'queued', 'waiting_input', 'waiting_service', 'paused', 'failed', 'interrupted'):
            continue
        task = job.get('task') or {}
        attention.append({'id': job['id'], 'status': job['status'],
            'type_label': ROUTE_NAMES.get((job.get('result') or {}).get('kind'), task.get('type_label') or '项目任务'),
            'title': task.get('subject') or task.get('title') or job.get('stage') or '项目任务',
            'detail': task.get('summary') or job.get('error') or '', 'updated': job.get('updated')})
    priority = {'waiting_input': 5, 'paused': 4, 'running': 3, 'queued': 3, 'waiting_service': 2, 'failed': 1, 'interrupted': 1}
    attention.sort(key=lambda j: (priority[j['status']], j.get('updated') or ''), reverse=True)
    counts = Counter(n['kind'] for n in nodes)
    return {'project': {'id': pid, 'name': project['name']}, 'observed_at': now(),
        'revision': data['revision'], 'sections': sections,
        'edges': [e for e in data['edges'] if e['source'] in selected and e['target'] in selected],
        'counts': dict(counts), 'attention': attention[:5],
        'coverage': {'loaded': len(nodes), 'total': data['total'], 'per_section': per_section},
        'interpretation': '这里呈现项目已保存的研究记录及来源。历史局限可能仍需更新；已完成任务不等于科学验证通过。'}


def agent_brief(store, owner, pid):
    from .research_outline import read_state
    from .research_updates import history
    view = snapshot(store, owner, pid, per_section=3)
    hierarchy = read_state(store, owner, pid)
    active = hierarchy.get('active')
    return {'overview_api': '/research/api/projects/'+pid+'/research-overview',
        'research_outline':{'read_api':'/research/api/projects/'+pid+'/research-outline',
            'propose_update_api':'/research/api/projects/'+pid+'/research-outline/generate',
            'revision':hierarchy['revision'],'active_mainline':active['mainline'] if active else None,
            'active_outline':active['outline'] if active else [],'has_proposal':bool(hierarchy.get('draft')),
            'meaning':'主线来自前人工作和作者讨论，主任务服务于主线，细节任务解决具体疑问。已有主线优先沿用；新认识改变范围时提议修订，由作者在页面采用。不要把未确认提案当成当前任务指令。'},
        'meaning': view['interpretation'],
        'sections': [{**s, 'items': [{k: n[k] for k in ('id', 'kind', 'label', 'status', 'sources')}
                                    for n in s['items']]} for s in view['sections']],
        'record_api': '/research/api/projects/'+pid+'/research-flow/records',
        'updates_api':'/research/api/projects/'+pid+'/research-updates',
        'recent_updates':[{'id':u['id'],'reason':u['reason'],'path':u['path'],
            'changes':[{'kind':c['kind'],'title':c['title'],'after':c['after']} for c in u['changes']]} for u in history(store,owner,pid)['updates'][:3]],
        'correction_tool':{'tool':'research_workbench','action':'research','operations':['overview','inspect','update','outline'],
            'purpose':'回查原始依据后更新已有认识、关系和任务下一步；变更及原依据可回读。主线与科学选择变化仍由作者决定。'},
        'guidance': '围绕当前请求引用具体问题、方法、发现和局限，携带来源。研究问题是要回答的科学问题；思路与方法是候选解释或求解路线；发现需区分文献结果、当前计算与验证范围。记录新认识时保留稳定节点ID、证据和有依据的关系，旧认识有更新时说明原因。不要由任务完成、文件数量或软件检查推断科学结论。按需要选文献、编程、仿真或写作工具；说明要解决什么，再报告得到什么、依据与缺口。'}


def install(app, store, actor):
    @app.get('/research/api/projects/{pid}/research-overview')
    def overview(pid: str, user=Depends(actor)):
        return snapshot(store, user['id'], pid)
