"""Account-scoped retrieval over project literature and bound knowledge bases."""
from urllib.parse import quote
import asyncio,json,re,sys
from pathlib import Path
from fastapi import Depends,Request,HTTPException
from .native import actor,call,text_call
from .literature import read_index
from .storage import child,now


def snippets(content,query,limit=2):
    tokens=list(dict.fromkeys(re.findall(r'[\w\u4e00-\u9fff]+',query.casefold())))
    if not tokens:return []
    chunks=re.split(r'\n\s*\n|(?<=\.)\s+(?=[A-Z])',content)
    scored=[]
    for index,chunk in enumerate(chunks):
        lower=chunk.casefold();score=sum(min(lower.count(t),4) for t in tokens)
        if not score:continue
        if all(t in lower for t in tokens):score+=len(tokens)*2
        exact=lower.find(query.casefold().strip())
        first=exact if exact>=0 else min((lower.find(t) for t in tokens if t in lower),default=0);start=max(0,first-160)
        scored.append({'excerpt':chunk[start:start+1000].strip(),'score':score,'chunk':index+1})
    return sorted(scored,key=lambda v:v['score'],reverse=True)[:limit]


def local_text(path):
    import fitz
    with fitz.open(path) as pdf:
        pages=min(len(pdf),300);text='\n\n'.join(pdf[i].get_text() for i in range(pages))[:2_000_000]
        return text,{'pages_scanned':pages,'total_pages':len(pdf),'truncated':len(pdf)>pages or len(text)>=2_000_000}


async def semantic(query,kb,owner,workspace,limit):
    params={'query':query,'knowledge_base':kb,'owner':{k:owner.get(k) for k in ('id','username','role')},'workspace':workspace,'limit':limit}
    helper=Path(__file__).with_name('native_rag.py')
    process=await asyncio.create_subprocess_exec(sys.executable,str(helper),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:out,err=await asyncio.wait_for(process.communicate(json.dumps(params).encode()),timeout=120)
    except TimeoutError:process.kill();await process.wait();raise ValueError('知识库语义检索超时，请检查该知识库的索引和检索配置') from None
    try:value=json.loads(out.decode('utf8').strip().splitlines()[-1])
    except (ValueError,IndexError):raise ValueError('原生知识库检索未返回可用结果，请检查索引与配置') from None
    if not value.get('ok'):raise ValueError(value.get('error') or '原生知识库语义检索未完成')
    return value['result']


def install(app,store):
    @app.post('/research/api/projects/{pid}/knowledge/search')
    async def search(request:Request,pid:str,payload:dict,user=Depends(actor)):
        project=store.get(user['id'],pid);query=str(payload.get('query','')).strip()[:600];limit=int(payload.get('limit',8));mode=payload.get('mode','fulltext-keyword');kb=str(payload.get('knowledge_base') or '')
        if len(query)<2 or not 1<=limit<=20:raise ValueError('请填写检索词，返回数量为 1 至 20')
        bound=project['config'].get('knowledge_bases',[])
        if kb and kb not in bound:raise HTTPException(403,'知识库未绑定到当前项目')
        if mode=='semantic':
            if not kb:raise ValueError('语义检索需要选择项目已绑定的知识库')
            # Resolve native visibility with the authenticated HTTP session before
            # invoking the same upstream account/workspace-aware RAG function.
            await call(request,'GET','/api/knowledge-bases/'+quote(kb,safe='')+'?dt_workspace='+quote(project['native_id']))
            result=await semantic(query,kb,user,project['native_id'],limit)
            from .project_canvas import record_retrieval
            return record_retrieval(store,user['id'],pid,{'mode':'semantic','query':query,'knowledge_base':kb,'result':result,'source':'DeepTutor 原生 RAG','checked':now()})
        if mode!='fulltext-keyword':raise ValueError('检索方式请选择 fulltext-keyword 或 semantic')
        hits=[];coverage=[];errors=[];root=store.path(user['id'],pid)
        if not kb:
            for asset,metadata in list(read_index(root).items())[:60]:
                path=child(root/'literature',asset)
                if not path.is_file() or path.suffix.lower()!='.pdf':continue
                try:
                    text,report=await asyncio.to_thread(local_text,path);coverage.append({'library':'workspace','asset':asset,'basis':'PDF text layer',**report})
                    for hit in snippets(text,query):hits.append({**hit,'title':metadata.get('title') or path.name,'library':'workspace','asset':asset,'url':'/research/api/projects/'+pid+'/literature/file?asset='+quote(asset),'evidence':'source-text'})
                except Exception:errors.append({'library':'workspace','asset':asset,'message':'PDF 文本层未取得'})
        if not kb:
            path=root/'.workbench/chat-materials.json'
            for material in (json.loads(path.read_text()).values() if path.exists() else []):
                if not material.get('searchable') or material.get('literature_asset'):continue
                source=child(root,material['text_path'])
                if not source.is_file():continue
                content=source.read_text(encoding='utf8')
                coverage.append({'library':'attachments','asset':material['path'],'basis':'uploaded source text','characters':len(content)})
                for hit in snippets(content,query):hits.append({**hit,'title':material['name'],'library':'attachments','asset':material['path'],'url':'/research/api/projects/'+pid+'/file?path='+quote(material['path']),'evidence':'source-text'})
        for library in ([kb] if kb else bound):
            try:
                rows=await call(request,'GET','/api/knowledge-bases/'+quote(library,safe='')+'/files?dt_workspace='+quote(project['native_id']))
                for file in rows.get('files',[])[:60]:
                    if file.get('type')=='folder':continue
                    asset=file['name']
                    try:
                        direct=Path(asset).suffix.lower() in {'.md','.markdown','.txt'}
                        route='/files/' if direct else '/file-preview-text/'
                        text=await text_call(request,'/api/knowledge-bases/'+quote(library,safe='')+route+quote(asset,safe='/')+'?dt_workspace='+quote(project['native_id']))
                        total=len(text);text=text[:2_000_000]
                        basis='native Markdown/text source' if direct else 'native text preview'
                        coverage.append({'library':library,'asset':asset,'basis':basis,'characters':len(text),'total_characters':total,'truncated':total>len(text)})
                        for hit in snippets(text,query):hits.append({**hit,'title':Path(asset).name,'library':library,'asset':asset,'url':'/api/knowledge-bases/'+quote(library,safe='')+'/files/'+quote(asset,safe='/')+'?dt_workspace='+quote(project['native_id']),'evidence':'source-text' if direct else 'source-preview-text'})
                    except HTTPException:errors.append({'library':library,'asset':asset,'message':'原生文本预览暂不可用'})
            except HTTPException:errors.append({'library':library,'message':'知识库当前不可访问'})
        hits.sort(key=lambda v:v['score'],reverse=True)
        from .project_canvas import record_retrieval
        return record_retrieval(store,user['id'],pid,{'mode':mode,'query':query,'items':hits[:limit],'documents_scanned':len(coverage),'coverage':coverage,'errors':errors,'source':'项目全文关键词检索','checked':now(),'scope':'仅当前账户项目文献与已绑定知识库；项目PDF文本层至多300页，原生Markdown/文本读取源文件、每份至多200万字符，其他格式按原生预览范围；实际覆盖与截断单独记录。语义检索使用单独的原生RAG模式。'})
