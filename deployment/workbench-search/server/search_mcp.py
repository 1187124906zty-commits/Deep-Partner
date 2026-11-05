"""Scholar discovery over actual MCP; Crossref only reconciles record identity."""
from pathlib import Path
from datetime import date
from urllib.parse import unquote
import asyncio,json,os,re
from .search_errors import SearchProviderError

ROOT=Path(__file__).resolve().parents[1]
PROVIDER='Google Scholar · MCP'
METADATA_TIMEOUT_SECONDS=6
RECONCILE_TIMEOUT_SECONDS=8


def interpreter():return Path(os.environ.get('WORKBENCH_SCHOLAR_MCP_PYTHON') or str(Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/search-mcp/env/bin/python'))
def bridge_config():
    path=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/search-mcp/bridge.json'
    return json.loads(path.read_text()) if path.is_file() else None
def ready():return interpreter().is_file() or bool(bridge_config())


class PaperRows(list):
    def __init__(self,rows,next_cursor=None,diagnostics=None):
        super().__init__(rows);self.next_cursor=next_cursor;self.diagnostics=diagnostics or {}


async def discover(query,limit=10,min_year=None,offset=0):
    if not ready():raise SearchProviderError('not_configured','Google Scholar MCP 尚未配置',provider=PROVIDER,next_action='configure_source')
    payload={'query':query,'page_size':min(10,limit),'cursor':str(offset),'year_min':min_year,'year_max':date.today().year}
    bridge=bridge_config()
    if bridge:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=45,trust_env=False) as client:
                response=await client.post(bridge['url']+'/scholar',headers={'x-workbench-search':bridge['token']},json=payload);response.raise_for_status();value=response.json()
        except httpx.TimeoutException:
            raise SearchProviderError('timeout','Google Scholar MCP 请求超时',provider=PROVIDER,retryable=True,next_action='稍后重试或切换来源') from None
        except httpx.HTTPStatusError as error:
            limited=error.response.status_code==429
            raise SearchProviderError('rate_limited' if limited else 'bridge_http_error',
                'Google Scholar 搜索桥接返回 HTTP '+str(error.response.status_code),provider=PROVIDER,
                retryable=error.response.status_code>=500 or limited,next_action='等待限流解除后重试' if limited else '检查搜索桥接状态或切换来源') from None
        except httpx.HTTPError:
            raise SearchProviderError('bridge_unavailable','Google Scholar 搜索桥接连接中断',provider=PROVIDER,retryable=True,next_action='启动或检查搜索桥接，再重试') from None
        except ValueError:
            raise SearchProviderError('invalid_response','Google Scholar 搜索桥接返回格式无效',provider=PROVIDER,next_action='检查桥接版本与返回格式') from None
    else:
        process=await asyncio.create_subprocess_exec(str(interpreter()),str(ROOT/'server/scholar_mcp_client.py'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:out,err=await asyncio.wait_for(process.communicate(json.dumps(payload).encode()),timeout=40)
        except TimeoutError:
            process.kill();await process.wait()
            raise SearchProviderError('timeout','Google Scholar MCP 检索超时',provider=PROVIDER,retryable=True,next_action='稍后重试或切换来源') from None
        try:value=json.loads(out.decode('utf8').strip().splitlines()[-1])
        except (ValueError,IndexError):
            raise SearchProviderError('invalid_response','Google Scholar MCP 未返回有效响应',provider=PROVIDER,next_action='检查 MCP 进程和版本') from None
    if not isinstance(value,dict):
        raise SearchProviderError('invalid_response','Google Scholar MCP 响应应为对象',provider=PROVIDER,next_action='检查 MCP 返回格式')
    if not value.get('ok'):
        code=value.get('error',{}).get('code','unavailable')
        challenge=code in {'verification_required','captcha_required','consent_required'}
        raise SearchProviderError(code,'Google Scholar 需要人工验证' if challenge else 'Google Scholar MCP 检索未完成',
            provider=PROVIDER,retryable=code in {'timeout','mcp_transport_error','rate_limited','unavailable'},
            next_action='在搜索工具打开的浏览器中完成人工验证，再重试' if challenge else '检查搜索桥接状态，或切换来源')
    data=value.get('data') or {};rows=[]
    for raw in data.get('results',[]):
        url=raw.get('url') or '';decoded=unquote(url);doi=re.search(r'10\.\d{4,9}/[^?#\s]+',decoded,re.I);arxiv=re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})',url)
        title=re.sub(r'^(?:\[(?:PDF|HTML|BOOK|CITATION)\]\s*)+','',raw['title'],flags=re.I)
        rows.append({'title':title,'authors':raw.get('authors') or [],'year':raw.get('year'),'venue':'','doi':doi[0].rstrip('.,;)') if doi else '','arxiv':arxiv[1] if arxiv else '','url':url,'abstract':'','search_snippet':raw.get('snippet') or '','cited_by':raw.get('cited_by'),'source':'Google Scholar · MCP','verified':False,'evidence':'search-result','discovery_record':raw})
    return PaperRows(rows,data.get('next_cursor'))


async def reconcile(rows,journal_only=False):
    from .references import search
    from .literature_providers import title_key
    semaphore=asyncio.Semaphore(4)
    async def one(row):
        async with semaphore:
            if row.get('arxiv'):return None if journal_only else row
            try:
                metadata=await asyncio.wait_for(search(row.get('doi') or row['title'],settings={},source='crossref',limit=3),timeout=METADATA_TIMEOUT_SECONDS)
                matches=[v for v in metadata if title_key(v['title'])==title_key(row['title'])]
                # Identical titles can describe a preprint and the published
                # article. Prefer the journal record for a publisher result.
                matches.sort(key=lambda v:v.get('publication_type')=='journal-article',reverse=True)
                match=next(iter(matches),None)
                if match:
                    if journal_only and match.get('publication_type')!='journal-article':return None
                    return {**row,**match,'search_snippet':row.get('search_snippet',''),'discovery_record':row.get('discovery_record'),'source':row['source']+' · Crossref 题录核验','evidence':'metadata' if not match.get('abstract') else 'metadata-and-abstract'}
            except Exception:
                return None if journal_only else {**row,'metadata_status':'unverified'}
            return None if journal_only else row
    tasks=[asyncio.create_task(one(row)) for row in rows]
    if not tasks:return PaperRows([],getattr(rows,'next_cursor',None))
    done,pending=await asyncio.wait(tasks,timeout=RECONCILE_TIMEOUT_SECONDS)
    for task in pending:task.cancel()
    await asyncio.gather(*pending,return_exceptions=True)
    verified=[(task.result() if task in done else (None if journal_only else {**row,'metadata_status':'unverified'})) for task,row in zip(tasks,rows)]
    return PaperRows([row for row in verified if row],getattr(rows,'next_cursor',None),
        {'metadata_timed_out':len(pending),'metadata_unverified':sum(bool(row and row.get('metadata_status')=='unverified') for row in verified)})
