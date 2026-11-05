"""Account-owned display names leave native KB IDs and indexing paths stable."""
from urllib.parse import quote
import json
from fastapi import Depends,HTTPException,Request
from .native import actor,call
from .storage import atomic_json


def install(app,store,api_path):
    def labels(owner):
        path=api_path(owner).with_name('knowledge-names.json')
        return path,json.loads(path.read_text()) if path.exists() else {}

    @app.get('/research/api/projects/{pid}/knowledge/sources')
    async def sources(request:Request,pid:str,user=Depends(actor)):
        project=store.get(user['id'],pid)
        rows=await call(request,'GET','/api/knowledge-bases?resource_library=true&dt_workspace='+quote(project['native_id']))
        _,names=labels(user['id'])
        return {'items':[{**row,'name':names.get(row.get('id') or row['name'],row['name'])} for row in rows]}

    @app.patch('/research/api/projects/{pid}/knowledge/sources/{kid}')
    async def rename(request:Request,pid:str,kid:str,payload:dict,user=Depends(actor)):
        project=store.get(user['id'],pid)
        rows=await call(request,'GET','/api/knowledge-bases?resource_library=true&dt_workspace='+quote(project['native_id']))
        item=next((r for r in rows if (r.get('id') or r['name'])==kid),None)
        if item is None or item.get('read_only'):raise HTTPException(403,'无法修改此知识库')
        name=str(payload.get('name') or '').strip()
        if not 1<=len(name)<=100 or any(ord(c)<32 for c in name):raise ValueError('知识库名称为1至100个字符')
        with store.lock('knowledge-names:'+user['id']):
            path,names=labels(user['id']);names[kid]=name;atomic_json(path,names)
        return {'id':kid,'name':name}
