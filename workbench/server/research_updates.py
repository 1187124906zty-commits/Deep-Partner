"""Source reads and versioned corrections within an existing research scope.

The native agent chooses what to investigate. This module preserves what it read,
applies bounded edits, and exposes their before/after evidence to the researcher.
"""
from copy import deepcopy
from pathlib import Path
import json,uuid
from fastapi import Depends
from .native import actor
from .storage import atomic_json,child,now,Conflict
from .research_flow import graph,graph_path,read_json,save_record,RELATIONS,STATUSES
from .research_outline import read_state,location


def folder(store,owner,pid):
    store.get(owner,pid)
    return store.path(owner,pid)/'.workbench/research-updates'


def history(store,owner,pid):
    return read_json(folder(store,owner,pid)/'history.json',{'updates':[]})


def inspect(store,owner,pid,payload):
    """Read the actual local evidence of selected records, including code/results."""
    data=graph(store,owner,pid,limit=2000);outline=read_state(store,owner,pid)
    ids=payload.get('record_ids') or []
    by_id={n['id']:n for n in data['nodes']}
    if not isinstance(ids,list) or any(i not in by_id for i in ids):raise ValueError('请选择当前项目实际存在的研究记录')
    selected=[by_id[i] for i in ids] if ids else sorted(data['nodes'],key=lambda n:n.get('updated',''),reverse=True)[:40]
    selected_ids={n['id'] for n in selected};edges=[e for e in data['edges'] if e['source'] in selected_ids or e['target'] in selected_ids]
    related={e[k] for e in edges for k in ('source','target')}-selected_ids
    selected+=[by_id[i] for i in sorted(related) if i in by_id][:20]
    sources=[];seen=set();root=store.path(owner,pid)
    paths=payload.get('paths') or []
    if not isinstance(paths,list) or len(paths)>12 or any(not isinstance(p,str) for p in paths):raise ValueError('最多选择12个当前项目材料路径')
    for path in paths:child(root/'project',path)
    source_records=selected+[{'evidence_refs':[{'path':p} for p in paths]}]
    for node in source_records:
        for ref in node.get('evidence_refs',[]):
            key=json.dumps(ref,sort_keys=True)
            if key in seen:continue
            seen.add(key)
            if len(sources)>=24:break
            source={'id':'source-'+str(len(sources)+1),'ref':ref,'record_ids':[n['id'] for n in selected if ref in n.get('evidence_refs',[])],
                    'text':'','status':'locator_only','coverage':'仅有定位，尚未读取原始内容'}
            try:
                path=child(root/'project',ref['path']) if ref.get('path') else child(root/'literature',ref['asset']) if ref.get('asset') else None
                if path and path.is_file():
                    source['modified']=path.stat().st_mtime
                    if path.suffix.lower()=='.pdf':
                        import fitz
                        with fitz.open(path) as pdf:
                            pages=ref.get('pages') or list(range(1,min(3,len(pdf))+1))
                            pages=[p for p in pages[:8] if isinstance(p,int) and 1<=p<=len(pdf)]
                            source.update(text='\n\n'.join('第 '+str(p)+' 页\n'+pdf[p-1].get_text()[:6500] for p in pages),coverage='实际读取原文页：'+','.join(map(str,pages)))
                    elif path.suffix.lower() in ('.md','.txt','.json','.csv','.py','.m','.r','.f90','.yaml','.yml','.toml','.log'):
                        source.update(text=path.read_text(encoding='utf8',errors='replace')[:12000],coverage='实际读取文件开头，最多12000字；数值与结论仍需结合适用条件')
                    if source['text']:source['status']='read'
            except (OSError,ValueError) as error:source['error']=str(error)[:300]
            sources.append(source)
    value={'id':uuid.uuid4().hex,'project_id':pid,'created':now(),'graph_revision':data['revision'],'outline_revision':outline['revision'],
           'request':str(payload.get('request') or '')[:6000],'records':selected,'relations':edges,'sources':sources,
           'outline':{k:({field:outline[k].get(field) for field in ('id','status','mainline','outline','author_decisions')} if outline.get(k) else None) for k in ('active','draft')},
           'guidance':'先比较作者更正与原始依据。区分方法名称、计算机制和领域贡献；必要时继续检索全文或代码。update可修订已有记录、关系和任务认识/下一步；主线、方法选择或资源范围变化用outline提出修订。存在证据冲突时保留争议，不自动覆盖科学选择。'}
    atomic_json(folder(store,owner,pid)/'inspections'/ (value['id']+'.json'),value)
    return value


def apply_update(store,owner,pid,payload):
    inspection_id=str(payload.get('inspection_id') or '')
    if not inspection_id.isalnum():raise ValueError('需要本项目实际返回的 inspection_id')
    base=folder(store,owner,pid);inspection=read_json(base/'inspections'/(inspection_id+'.json'),None)
    if not inspection:raise ValueError('本项目没有这次来源读取记录')
    reason=str(payload.get('reason') or '').strip();checks=payload.get('source_ids') or []
    if not reason:raise ValueError('请说明修改理由和作者更正的关系')
    sources={s['id']:s for s in inspection['sources']}
    if not checks or any(s not in sources or sources[s]['status']!='read' for s in checks):raise ValueError('修订需要引用本次确实读到的原始材料')
    conflicts=payload.get('conflicts') or []
    if conflicts or payload.get('scope_change'):raise ValueError('存在证据争议或主线变化，请保留原认识并提出待作者决定的修订')
    allowed={'inspection_id','reason','source_ids','record_updates','task_updates','remove_relation_ids','relations','conflicts','scope_change'}
    if set(payload)-allowed:raise ValueError('修订包含不支持的字段')
    with store.lock(pid):
        data=graph(store,owner,pid,limit=2000);state=read_state(store,owner,pid)
        if data['revision']!=inspection['graph_revision'] or state['revision']!=inspection['outline_revision']:raise Conflict('研究记录或大纲已更新，请回读当前依据后再修订')
        root=store.path(owner,pid)
        for sid in checks:
            source=sources[sid];ref=source['ref'];path=child(root/'project',ref['path']) if ref.get('path') else child(root/'literature',ref['asset'])
            if not path.is_file() or path.stat().st_mtime!=source['modified']:raise Conflict('原始材料已更新，请重新读取')
        nodes={n['id']:n for n in data['nodes']};read_ids={n['id'] for n in inspection['records']};changes=[];updated=[]
        for patch in payload.get('record_updates',[]):
            nid=patch.get('id');fields=set(patch)-{'id'}
            if nid not in read_ids or nid=='question:research-mainline' or not fields<= {'label','detail','status'}:raise ValueError('记录修订必须限于本次读取的已有认识；主线另行提议')
            current=nodes[nid]
            if current['kind'] in ('question','decision'):raise ValueError('研究问题和作者决定的变化应先提议确认')
            new={**current,**patch}
            if not isinstance(new['label'],str) or not 1<=len(new['label'])<=300 or not isinstance(new.get('detail',''),str) or len(new.get('detail',''))>30000 or new['status'] not in STATUSES:raise ValueError('研究记录内容无效')
            if new['status']=='not_found_in_scope':raise ValueError('检索缺失判断须使用含检索范围的研究记录接口')
            new['evidence_refs']=list({json.dumps(r,sort_keys=True):r for r in current.get('evidence_refs',[])+[sources[s]['ref'] for s in checks]}.values())[:30]
            updated.append(new);changes.append({'kind':'record','id':nid,'title':new['label'],'before':{k:current.get(k) for k in fields},'after':{k:new[k] for k in fields}})
        revised=deepcopy(state)
        for patch in payload.get('task_updates',[]):
            tid=patch.get('id');fields=set(patch)-{'id'}
            if not fields or not fields<= {'understanding','next_step'} or any(not isinstance(patch[k],str) or len(patch[k])>3000 for k in fields):raise ValueError('日常任务更新只修改已有认识与下一步；大纲结构变化另行提议')
            matches=[(version,t) for version in ('active','draft') if revised.get(version) for g in revised[version]['outline'] for t in g['tasks'] if t['id']==tid]
            if not matches:raise ValueError('细节任务不属于当前研究大纲')
            for version,t in matches:
                changes.append({'kind':'task','version':version,'id':tid,'title':t['title'],'before':{k:t.get(k) for k in fields},'after':{k:patch[k] for k in fields}});t.update({k:patch[k] for k in fields})
        remove=payload.get('remove_relation_ids') or [];known_edges={e['id'] for e in inspection['relations']}
        if any(e not in known_edges for e in remove):raise ValueError('只能修订本次读取的研究关系')
        relations=payload.get('relations') or []
        for edge in relations:
            if edge.get('source') not in read_ids or edge.get('target') not in read_ids or edge.get('relation') not in RELATIONS:raise ValueError('研究关系缺少已读取的端点或关系类型无效')
        if not (changes or remove or relations):raise ValueError('没有需要保存的研究修订')
        uid=uuid.uuid4().hex
        save_record(store,owner,pid,{'id':'update-'+uid,'title':'研究认识修订','content':reason,'nodes':updated,'edges':relations})
        if remove:
            raw=read_json(graph_path(store,owner,pid),{});raw['edges']=[e for e in raw['edges'] if e['id'] not in remove];atomic_json(graph_path(store,owner,pid),raw)
        if payload.get('task_updates'):
            revised['revision']+=1;atomic_json(location(store,owner,pid),revised)
        receipt={'id':uid,'created':now(),'reason':reason,'inspection_id':inspection_id,'source_ids':checks,'sources':[sources[s] for s in checks],
                 'changes':changes,'removed_relations':[e for e in inspection['relations'] if e['id'] in remove],'relations':relations,
                 'path':'docs/research/records/update-'+uid+'.md','status':'applied','scientific_scope_changed':False}
        atomic_json(base/'updates'/(uid+'.json'),receipt)
        log=history(store,owner,pid);log['updates'].insert(0,{k:v for k,v in receipt.items() if k!='sources'});atomic_json(base/'history.json',log)
    return receipt


def install(app,store):
    @app.get('/research/api/projects/{pid}/research-updates')
    def updates(pid:str,user=Depends(actor)):return history(store,user['id'],pid)

    @app.post('/research/api/projects/{pid}/research-updates/inspect')
    def inspect_sources(pid:str,payload:dict,user=Depends(actor)):return inspect(store,user['id'],pid,payload)

    @app.post('/research/api/projects/{pid}/research-updates/apply')
    def apply(pid:str,payload:dict,user=Depends(actor)):return apply_update(store,user['id'],pid,payload)
