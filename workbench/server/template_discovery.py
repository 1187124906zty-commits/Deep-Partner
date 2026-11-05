"""Look up official author guidance on demand and retain actual template downloads."""
from pathlib import Path
from urllib.parse import urlparse,quote
import asyncio,hashlib,json,re
from fastapi import Depends
from fastapi.responses import FileResponse
from .native import actor
from .network_sources import Page,fetch_official,web_search,official_url,PUBLISHER_DOMAINS
from .storage import atomic_json,now,child

ROOT=Path(__file__).resolve().parents[1]
KNOWN={
 'elsevier':[('Elsevier CAS 作者模板 2.4','https://ctan.math.illinois.edu/macros/latex/contrib/els-cas-templates.zip')],
}


def downloadable(url):return bool(re.search(r'\.(?:docx?|zip|cls|tex)(?:$|[?#])',url,re.I))


async def discover(journal,settings):
    candidates=[];guides=[];errors=[];family=journal.get('template',{}).get('family','')
    for label,url in KNOWN.get(family,[]):candidates.append({'title':label,'url':url,'source':'CTAN 官方模板仓库','kind':'author-template'})
    template_id=journal.get('template',{}).get('word_template')
    provenance=json.loads((ROOT/'templates/manuscripts/source/provenance.json').read_text())
    key={'cirp':'CIRP','springer':'springer-aas'}.get(template_id,template_id)
    if key in provenance and str(provenance[key].get('source','')).startswith('https://'):
        value=provenance[key];candidates.append({'title':journal['name']+' · 官方作者模板','url':value['source'],'source':value.get('guide') or value['source'],'kind':'author-template'})
    urls=[journal.get('template',{}).get('source',''),journal.get('homepage','')]
    lookup=await web_search(journal['name']+' official journal instructions for authors manuscript Word LaTeX template',settings,limit=6,domains=PUBLISHER_DOMAINS)
    for row in lookup.get('items',[]):
        if official_url(row['url']):urls.append(row['url'])
    async def inspect(url):
        try:
            result=await fetch_official(url)
            if downloadable(result['url']):return {'guide':None,'links':[{'title':Path(urlparse(result['url']).path).name,'url':result['url'],'source':url,'kind':'author-template'}]}
            page=Page(result['url']);page.feed(result['content'].decode('utf8',errors='replace'));body=re.sub(r'\s+',' ',' '.join(page.parts)).strip()
            links=[{'title':v['text'].strip()[:200] or Path(urlparse(v['url']).path).name,'url':v['url'],'source':result['url'],'kind':'author-template'} for v in page.links if official_url(v['url']) and (downloadable(v['url']) or re.search(r'template|模板',v['text'],re.I)) and re.search(r'template|模板|\.docx?|\.zip',v['text']+' '+v['url'],re.I)]
            return {'guide':{'url':result['url'],'checked':result['checked'],'excerpt':body[:1400]},'links':links[:15]}
        except Exception as error:return {'error':str(error)[:180],'url':url}
    targets=list(dict.fromkeys(url for url in urls if official_url(url)))[:4]
    for value in await asyncio.gather(*(inspect(url) for url in targets)):
        if value.get('guide'):guides.append(value['guide'])
        candidates.extend(value.get('links',[]))
        if value.get('error'):errors.append({'url':value['url'],'message':value['error']})
    unique={v['url']:v for v in candidates}
    return {'journal':journal['id'],'items':[{**v,'id':hashlib.sha256(v['url'].encode()).hexdigest()[:24],'downloadable':downloadable(v['url'])} for v in unique.values()],'guides':guides,'search':lookup,'errors':errors,'checked':now(),'scope':'官方作者投稿模板；出版社出版后的卷期、页码和成品排版另行处理。'}


def install(app,store,api_path):
    def cache(owner,pid,journal):return store.path(owner,pid)/'.workbench/template-search'/(hashlib.sha256(journal.encode()).hexdigest()[:24]+'.json')

    @app.post('/research/api/projects/{pid}/journal-templates/search')
    async def search(pid:str,payload:dict,user=Depends(actor)):
        from .journals import lookup
        store.get(user['id'],pid);journal=await lookup(str(payload.get('journal','')))
        settings=json.loads(api_path(user['id']).read_text()) if api_path(user['id']).exists() else {}
        result=await discover(journal,settings);atomic_json(cache(user['id'],pid,journal['id']),result)
        return result

    @app.post('/research/api/projects/{pid}/journal-templates/download')
    async def download(pid:str,payload:dict,user=Depends(actor)):
        store.get(user['id'],pid);path=cache(user['id'],pid,str(payload.get('journal','')))
        if not path.is_file():raise ValueError('请先检索期刊的官方模板')
        result=json.loads(path.read_text());item=next((v for v in result['items'] if v['id']==payload.get('template')),None)
        if not item or not item['downloadable']:raise ValueError('请选择已检索到的模板文件')
        value=await fetch_official(item['url'],max_bytes=25*1024**2);data=value['content']
        if 'html' in value['content_type'] or data.lstrip().lower().startswith((b'<!doctype html',b'<html')):raise ValueError('官方来源返回网页而不是模板文件，请打开来源查看')
        suffix=next(iter(re.findall(r'\.(docx?|zip|cls|tex)(?:$|[?#])',value['url'],re.I)),'bin').lower()
        if suffix in ('zip','docx') and not data.startswith(b'PK'):raise ValueError('模板压缩包内容无效')
        name=item['id']+'.'+suffix;target=store.path(user['id'],pid)/'manuscript/templates'/name
        store.replace(user['id'],pid,target,data,'下载官方期刊作者模板')
        receipt={'journal':result['journal'],'title':item['title'],'source':value['url'],'guide':item['source'],'checked':value['checked'],'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'name':name}
        atomic_json(target.with_suffix(target.suffix+'.json'),receipt)
        return {**receipt,'url':'/research/api/projects/'+pid+'/journal-templates/file?name='+quote(name),'adaptation':'原包已保存。新模板的排版适配需按其格式验证；已支持的模板可直接生成预览。'}

    @app.get('/research/api/projects/{pid}/journal-templates/file')
    async def file(pid:str,name:str,user=Depends(actor)):
        store.get(user['id'],pid);target=child(store.path(user['id'],pid)/'manuscript/templates',name)
        if not target.is_file():raise KeyError('模板文件不存在')
        return FileResponse(target,filename=name)
