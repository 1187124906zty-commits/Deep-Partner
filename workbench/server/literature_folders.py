"""Project library folders point to stable document identities, not PDF copies."""
from copy import deepcopy
import json,re
from urllib.parse import quote
from fastapi import Depends,Request
from .native import actor,call
from .storage import Conflict,atomic_json,now

PURPOSES={'references','methods','validation','reading'}


def read(store,owner,pid):
    store.get(owner,pid)
    path=store.path(owner,pid)/'.workbench/literature-folders.json'
    value=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    return {**value,'revision':int(value.get('revision',0)),'assignments':value.get('assignments',{}),
            'folders':value.get('folders',[]),'memberships':value.get('memberships',{})}


async def assets(request,store,owner,pid):
    from .literature import read_index
    from .storage import child
    project=store.get(owner,pid);root=store.path(owner,pid)
    found={'workspace/'+key for key in read_index(root) if child(root/'literature',key).is_file()}
    for kid in project['config'].get('knowledge_bases',[]):
        rows=await call(request,'GET','/api/knowledge-bases/'+quote(kid,safe='')+'/files?dt_workspace='+quote(project['native_id']))
        found.update(kid+'/'+row['name'] for row in rows.get('files',[]) if row.get('type')!='folder')
    return found


def save(store,owner,pid,payload,available):
    """Validate the complete batch before changing any folder or membership."""
    with store.lock(pid):
        current=read(store,owner,pid)
        if payload.get('expected_revision')!=current['revision']:
            raise Conflict('文献分类已更新，请先读取当前 folders revision 再提交')
        value=deepcopy(current);folders={row['id']:row for row in value['folders']}
        changes=payload.get('folders',[]);members=payload.get('memberships',{})
        if not isinstance(changes,list) or not isinstance(members,dict) or not changes and not members:
            raise ValueError('请提供 folders 或 memberships')
        if len(changes)>100 or len(members)>3000:raise ValueError('文献分类批次过大，请分批保存')
        for row in changes:
            identifier=str(row.get('id',''));name=str(row.get('name','')).strip();kind=row.get('kind','topic')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',identifier):raise ValueError('文件夹 ID 仅使用字母、数字、下划线或连字符')
            if not 1<=len(name)<=120 or any(ord(c)<32 for c in name):raise ValueError('文件夹名称为1至120个字符')
            if kind not in ('topic','status'):raise ValueError('文件夹类型应为 topic 或 status')
            folders[identifier]={'id':identifier,'name':name,'kind':kind}
        names=[row['name'] for row in folders.values()]
        if len(names)!=len(set(names)):raise ValueError('文件夹名称不能重复')
        normalized={}
        for asset,ids in members.items():
            if asset not in available:raise ValueError('文献不在当前项目文献库：'+str(asset)[:200])
            if not isinstance(ids,list) or not all(isinstance(i,str) for i in ids):raise ValueError('文献文件夹归属必须是 ID 列表')
            ids=list(dict.fromkeys(ids))
            if set(ids)-folders.keys():raise ValueError('文献归属中存在未创建的文件夹')
            normalized[asset]=ids
        value['folders']=list(folders.values());value['memberships'].update(normalized)
        if value==current:return {**current,'status':'saved','changed':False,'verified':True}
        value.update(revision=current['revision']+1,updated=now())
        reason=str(payload.get('reason') or '整理文献库文件夹')[:300]
        path=store.path(owner,pid)/'.workbench/literature-folders.json';atomic_json(path,value)
        confirmed=read(store,owner,pid)
        if confirmed!=value:raise RuntimeError('文献分类回读不一致')
        from .annotations import event
        event(store,owner,pid,'literature.organized',{'revision':value['revision'],'previous_revision':current['revision'],
            'folders':len(value['folders']),'assigned':len(normalized),'reason':reason,'source_path':str(payload.get('source_path',''))[:1500]})
        return {**confirmed,'status':'saved','changed':True,'verified':True,'assigned':len(normalized),
                'source_paths_preserved':True}


def install(app,store):
    @app.get('/research/api/projects/{pid}/literature/folders')
    async def folders(pid:str,user=Depends(actor)):
        return read(store,user['id'],pid)

    @app.patch('/research/api/projects/{pid}/literature/folders')
    async def organize(request:Request,pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];store.get(owner,pid)
        available=await assets(request,store,owner,pid)
        return save(store,owner,pid,payload,available)

    @app.put('/research/api/projects/{pid}/literature/folders')
    async def purpose(request:Request,pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];store.get(owner,pid)
        if payload.get('category') not in PURPOSES:raise ValueError('文献用途无效')
        asset=str(payload.get('asset',''))
        if asset not in await assets(request,store,owner,pid):raise ValueError('文献不在当前项目文献库')
        with store.lock(pid):
            value=read(store,owner,pid);value['assignments'][asset]=payload['category']
            value.update(revision=value['revision']+1,updated=now())
            atomic_json(store.path(owner,pid)/'.workbench/literature-folders.json',value)
        return value
