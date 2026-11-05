"""Source-bound web lookup used by journal, template and author workflows."""
from html.parser import HTMLParser
from urllib.parse import urlparse,urljoin
from datetime import datetime,timezone
import asyncio,json,re,time
import httpx
from .search_errors import SearchProviderError
_PUBLIC_WEB_CACHE={}
PUBLIC_CACHE_SECONDS=120
_PUBLIC_WEB_GATE=asyncio.Semaphore(1)
PUBLIC_WEB_SOURCE='DDGS · 公共网页检索'


async def public_web_values(query,limit):
    """Serialize this unkeyed upstream; retry a fast engine failure once."""
    from ddgs import DDGS
    async with _PUBLIC_WEB_GATE:
        for attempt in (1,2):
            try:
                values=await asyncio.to_thread(lambda:list(DDGS(timeout=8).text(query,max_results=min(limit,10))))
                return values,attempt
            except Exception as error:
                kind=type(error).__name__.lower()
                if attempt==2 or 'ratelimit' in kind or 'timeout' in kind:raise
                await asyncio.sleep(0.6)

PUBLISHER_DOMAINS=('sciencedirect.com','elsevier.com','springer.com','springernature.com','cms-resources.apps.public.k8s.springernature.io','nature.com','wiley.com','tandfonline.com','ieee.org','acs.org','rsc.org','science.org','pnas.org','oup.com','academic.oup.com','cambridge.org','iop.org','sagepub.com','cirp.net','engineering.org.cn','journal.hep.com.cn','iapjournals.ac.cn','journals.nwpu.edu.cn','cstam.org.cn','ctan.org','ctan.math.illinois.edu','mirrors.ibiblio.org')


def official_url(url):
    parsed=urlparse(url);host=(parsed.hostname or '').lower()
    return parsed.scheme=='https' and not parsed.username and not parsed.password and (parsed.port in (None,443)) and any(host==domain or host.endswith('.'+domain) for domain in PUBLISHER_DOMAINS)


class Page(HTMLParser):
    def __init__(self,base):super().__init__();self.base=base;self.links=[];self.parts=[];self.anchor=None;self.skip=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'):self.skip+=1
        if tag=='a' and attrs.get('href'):self.anchor={'url':urljoin(self.base,attrs['href']),'text':''}
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
        if tag=='a' and self.anchor:self.links.append(self.anchor);self.anchor=None
    def handle_data(self,value):
        if not self.skip:
            self.parts.append(value)
            if self.anchor:self.anchor['text']+=value


async def fetch_official(url,max_bytes=4*1024**2):
    if not official_url(url):raise ValueError('仅从出版社、期刊或已登记模板来源获取此文件')
    async with httpx.AsyncClient(timeout=20,trust_env=False,headers={'User-Agent':'ResearchWorkbench/1.0 (journal author guidance)'}) as client:
        for _ in range(5):
            async with client.stream('GET',url) as response:
                if response.is_redirect:
                    url=urljoin(url,response.headers['location'])
                    if not official_url(url):raise ValueError('来源跳转到未登记的下载域名，请在原始来源页面查看')
                    continue
                if response.status_code in (401,403):raise ValueError('官方来源要求登录或机构访问，未绕过认证')
                response.raise_for_status();chunks=[];size=0
                async for chunk in response.aiter_bytes():
                    size+=len(chunk)
                    if size>max_bytes:raise ValueError('来源文件超过本次获取大小限制')
                    chunks.append(chunk)
                return {'url':str(response.url),'content':b''.join(chunks),'content_type':response.headers.get('content-type',''),'checked':datetime.now(timezone.utc).isoformat()}
    raise ValueError('官方来源重定向次数过多')


async def web_search(query,settings,limit=8,domains=None):
    key=settings.get('web_search_api_key') or settings.get('scholar_api_key')
    q=query+(' ('+' OR '.join('site:'+d for d in domains)+')' if domains and len(domains)<=5 else '')
    if not key:
        cache_key=(query,limit,tuple(domains or ()))
        cached=_PUBLIC_WEB_CACHE.get(cache_key)
        if cached and time.monotonic()-cached[0]<PUBLIC_CACHE_SECONDS:
            return {**cached[1],'cached':True}
        try:
            values,attempts=await asyncio.wait_for(public_web_values(q,limit),timeout=22)
            rows=[{'title':v.get('title',''),'url':v.get('href',''),'snippet':v.get('body',''),'source':PUBLIC_WEB_SOURCE,'evidence':'search-result'} for v in values if v.get('href')]
            if domains:rows=[r for r in rows if any((urlparse(r['url']).hostname or '')==d or (urlparse(r['url']).hostname or '').endswith('.'+d) for d in domains)]
            result={'items':rows[:limit],'source':PUBLIC_WEB_SOURCE,'status':'ready','query':query,'attempts':attempts,
                'outcome':'results' if rows else 'empty','cached':False,'checked':datetime.now(timezone.utc).isoformat()}
            if rows:
                if len(_PUBLIC_WEB_CACHE)>=64:_PUBLIC_WEB_CACHE.pop(next(iter(_PUBLIC_WEB_CACHE)))
                _PUBLIC_WEB_CACHE[cache_key]=(time.monotonic(),result)
            return result
        except Exception as error:
            timeout=isinstance(error,(TimeoutError,httpx.TimeoutException)) or 'timeout' in type(error).__name__.lower()
            limited='ratelimit' in type(error).__name__.lower()
            failure=SearchProviderError('timeout' if timeout else ('rate_limited' if limited else 'provider_unavailable'),
                '公共网页检索超时' if timeout else ('公共网页检索暂时限流' if limited else '公共网页检索暂不可用'),provider=PUBLIC_WEB_SOURCE,retryable=True,
                next_action='等待限流解除后重试' if limited else '稍后重试；持续失败时检查网络或配置 SerpApi')
            return {**failure.result(),'query':query,'diagnostics':{'exception_type':type(error).__name__,'engine_mode':'auto'}}
    try:
        async with httpx.AsyncClient(timeout=35,trust_env=False) as client:
            r=await client.get('https://serpapi.com/search.json',params={'engine':'google','q':q[:1000],'num':min(limit,10),'api_key':key,'hl':'en'});r.raise_for_status();value=r.json()
        if value.get('error'):
            return {**SearchProviderError('provider_error','网页检索服务拒绝请求，请检查密钥与配额',provider='Google · SerpApi',next_action='检查 SerpApi 配置和剩余配额').result(),'query':query}
    except httpx.HTTPStatusError as error:
        status=error.response.status_code
        return {**SearchProviderError('rate_limited' if status==429 else 'provider_http_error',
            '网页检索服务返回 HTTP '+str(status),provider='Google · SerpApi',retryable=status==429 or status>=500,
            next_action='等待限流解除后重试' if status==429 else '检查检索服务配置或切换来源').result(),'query':query}
    except httpx.HTTPError as error:
        return {**SearchProviderError('timeout' if isinstance(error,httpx.TimeoutException) else 'connection_error',
            '网页检索连接未完成',provider='Google · SerpApi',retryable=True,next_action='稍后重试或检查检索网络').result(),'query':query}
    except ValueError:
        return {**SearchProviderError('invalid_response','网页检索服务返回格式无效',provider='Google · SerpApi',next_action='检查服务响应与版本').result(),'query':query}
    rows=[{'title':v.get('title',''),'url':v.get('link',''),'snippet':v.get('snippet',''),'source':'Google · SerpApi','evidence':'search-result'} for v in value.get('organic_results',[]) if v.get('link')]
    if domains:rows=[r for r in rows if any((urlparse(r['url']).hostname or '')==d or (urlparse(r['url']).hostname or '').endswith('.'+d) for d in domains)]
    return {'items':rows[:limit],'source':'Google · SerpApi','status':'ready','query':query,'outcome':'results' if rows else 'empty'}


async def institution_search(affiliation):
    if not affiliation:return {'status':'missing','items':[]}
    chinese=re.search(r'[\u4e00-\u9fff]{2,15}?(?:大学|研究院|研究所)',affiliation) or re.search(r'[\u4e00-\u9fff]{2,15}?学院',affiliation)
    query=chinese[0] if chinese else affiliation[:180]
    try:
        async with httpx.AsyncClient(timeout=20,trust_env=False) as client:
            response=await client.get('https://api.ror.org/v2/organizations',params={'query':query});response.raise_for_status()
        rows=[]
        for v in response.json().get('items',[])[:5]:
            rows.append({'id':v['id'],'names':[n['value'] for n in v.get('names',[])],'websites':[link['value'] for link in v.get('links',[]) if link.get('type')=='website'],'source':v['id']})
        return {'status':'ready','query':query,'items':rows,'source':'https://api.ror.org/v2/organizations'}
    except httpx.HTTPError:return {'status':'unavailable','query':query,'items':[],'message':'机构名录暂未取得，保留作者提供的单位信息'}
