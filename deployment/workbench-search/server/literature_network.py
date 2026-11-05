"""Searchable paper results with stable selection identities and source status."""
from datetime import date
import asyncio,hashlib,json,re
import httpx
from fastapi import Depends
from .native import actor
from .references import search
from .literature_providers import available,resolve,PROVIDERS,doi_key,title_key
from .storage import now
from .search_errors import SearchProviderError


def install(app,store,api_path):
    @app.get('/research/api/projects/{pid}/literature/search')
    async def papers(pid:str,q:str,source:str='auto',years:int=0,newest:bool=False,page:int=1,limit:int=20,user=Depends(actor)):
        store.get(user['id'],pid)
        if years not in (0,5,10) or not 1<=page<=50 or not 1<=limit<=20:raise ValueError('检索范围或页码无效')
        settings=json.loads(api_path(user['id']).read_text()) if api_path(user['id']).exists() else {};provider=resolve(settings,source)
        if provider=='scholar_mcp':limit=min(limit,10)
        if not 3<=len(q.strip())<=600:raise ValueError('请输入3至600字的 DOI、标题或关键词')
        if provider in {'scholar_mcp','academic_web'} and re.fullmatch(r'10\.\d{4,9}/\S+',doi_key(q)):
            provider='crossref'
        options={'limit':limit,'min_year':date.today().year-years+1 if years else None,'offset':(page-1)*limit}
        warnings=[]
        try:
            rows=await search(q,newest,settings,source=provider,**options)
        except (SearchProviderError,httpx.HTTPError,ValueError) as failure:
            if isinstance(failure,SearchProviderError):error=failure
            else:
                timeout=isinstance(failure,httpx.TimeoutException)
                status=failure.response.status_code if isinstance(failure,httpx.HTTPStatusError) else None
                error=SearchProviderError('timeout' if timeout else ('rate_limited' if status==429 else 'provider_unavailable'),
                    '文献检索超时' if timeout else '文献检索来源暂不可用',provider=PROVIDERS[provider][0],
                    retryable=isinstance(failure,httpx.HTTPError),next_action='稍后重试，或明确切换检索来源')
            # Only auto permits a named fallback; an explicit source is never silently substituted.
            if source=='auto' and provider!='crossref':
                try:
                    rows=await asyncio.wait_for(search(q,newest,settings,source='crossref',**options),timeout=12)
                except (httpx.HTTPError,ValueError,TimeoutError):
                    return {**error.result(),'provider':provider,'requested_source':source,'query':q,'page':page,'limit':limit,'has_more':False}
                warnings.append(error.result()['error']);provider='crossref'
            else:
                return {**error.result(),'provider':provider,'requested_source':source,'query':q,'page':page,'limit':limit,'has_more':False}
        for row in rows:row['key']=hashlib.sha256((doi_key(row.get('doi')) or row.get('arxiv') or title_key(row.get('title'))).encode()).hexdigest()[:24]
        diagnostics=getattr(rows,'diagnostics',{})
        if diagnostics.get('metadata_unverified'):
            warnings.append({'code':'metadata_partial','message':'部分题录未完成 Crossref 核验，保留原检索结果及来源；不表示已读全文。'})
        return {'items':rows,'status':'degraded' if warnings else 'ready','outcome':'results' if rows else 'empty',
            'source':PROVIDERS[provider][0],'provider':provider,'requested_source':source,'providers':available(settings),
            'warnings':warnings,'diagnostics':diagnostics,'page':page,'limit':limit,
            'has_more':bool(rows.next_cursor) if hasattr(rows,'next_cursor') else len(rows)==limit,'checked':now(),'query':q}

    @app.get('/research/api/search/sources')
    async def sources(user=Depends(actor)):
        settings=json.loads(api_path(user['id']).read_text()) if api_path(user['id']).exists() else {}
        return {'papers':available(settings),'web':{'name':'Google · SerpApi' if settings.get('web_search_api_key') or settings.get('scholar_api_key') else 'DuckDuckGo · 公共网页检索','configured':True},'journal_metrics':{'name':'Clarivate Journals API','configured':bool(settings.get('jcr_api_key'))},'institutions':{'name':'ROR','configured':True}}

    @app.get('/research/api/search/web')
    async def web(q:str,kind:str='all',user=Depends(actor)):
        if not 3<=len(q.strip())<=600:raise ValueError('请输入检索关键词')
        from .network_sources import web_search,PUBLISHER_DOMAINS
        settings=json.loads(api_path(user['id']).read_text()) if api_path(user['id']).exists() else {}
        return await web_search(q,settings,domains=PUBLISHER_DOMAINS if kind in ('journal','template') else None)

    @app.get('/research/api/author-profile/institutions')
    async def institutions(q:str,user=Depends(actor)):
        from .network_sources import institution_search
        return await institution_search(q[:300])
