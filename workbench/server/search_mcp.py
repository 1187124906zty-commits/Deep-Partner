"""Scholar discovery over actual MCP; Crossref only reconciles record identity."""
from pathlib import Path
from datetime import date
from urllib.parse import unquote
import asyncio,json,os,re

ROOT=Path(__file__).resolve().parents[1]


def interpreter():return Path(os.environ.get('WORKBENCH_SCHOLAR_MCP_PYTHON') or str(Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/search-mcp/env/bin/python'))
def bridge_config():
    path=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/search-mcp/bridge.json'
    return json.loads(path.read_text()) if path.is_file() else None
def ready():return interpreter().is_file() or bool(bridge_config())


class PaperRows(list):
    def __init__(self, rows, next_cursor=None, diagnostics=None):
        super().__init__(rows)
        self.next_cursor = next_cursor
        self.diagnostics = diagnostics or []


class ScholarMCPError(ValueError):
    def __init__(self, error, diagnostics=None, tool=None):
        self.error = dict(error)
        self.code = error.get('code', 'unavailable')
        self.retryable = error.get('retryable', False)
        self.details = error.get('details', {})
        self.detail = error.get('message', self.code)
        self.diagnostics = diagnostics or []
        self.tool = tool
        super().__init__(self.detail)


async def _bridge_post(bridge, path, payload):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(bridge['url'].rstrip('/') + path,
                headers={'x-workbench-search': bridge['token']}, json=payload)
            response.raise_for_status()
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError('Invalid envelope')
            return value
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        try:
            value = error.response.json()
            if isinstance(value, dict) and isinstance(value.get('error'), dict):
                return value
        except ValueError:
            pass
        transient = status in (502, 503, 504)
        return {'ok': False, 'error': {'code': 'bridge_transport_error' if transient else 'bridge_http_error',
                'retryable': transient, 'message': 'Scholar bridge HTTP request failed', 'details': {'status': status}}}
    except httpx.HTTPError:
        return {'ok': False, 'error': {'code': 'bridge_transport_error', 'retryable': True,
                'message': 'Scholar bridge or configured tunnel is unreachable', 'details': {}}}
    except ValueError:
        return {'ok': False, 'error': {'code': 'mcp_protocol_error', 'retryable': False,
                'message': 'Scholar bridge returned an invalid envelope', 'details': {}}}


async def _local_call(payload):
    from scripts.local_search_bridge import invoke
    return await asyncio.to_thread(invoke, {'python': str(interpreter())}, payload)


async def _diagnose(bridge):
    if bridge:
        return await _bridge_post(bridge, '/diagnostics', {})
    from scripts.local_search_bridge import diagnostics
    return await asyncio.to_thread(diagnostics, {'python': str(interpreter())})


async def _repair(bridge, error, diagnosis):
    if bridge:
        reason = diagnosis.get('reason') or error.get('code')
        if reason in ('interpreter_missing', 'python_module_missing', 'mcp_protocol_error',
                      'mcp_schema_mismatch', 'mcp_tool_missing'):
            return {'ok': False, 'attempted': False, 'reason': reason}
        return await _bridge_post(bridge, '/repair', {'code': reason})
    return {'ok': False, 'attempted': False, 'reason': 'no_configured_recovery'}


async def discover(query, limit=10, min_year=None, offset=0, *, tool='search_papers_by_topic',
                   author=None, cursor=None, year_max=None):
    from .scholar_mcp_client import request
    arguments = {'page_size': min(10, limit), 'cursor': str(offset) if cursor is None else cursor,
                 'year_min': min_year, 'year_max': date.today().year if year_max is None else year_max}
    arguments['author' if tool == 'get_author_papers' else 'query'] = author or query if tool == 'get_author_papers' else query
    payload = {'tool': tool, 'arguments': arguments}
    try:
        request(payload)
    except ValueError as error:
        raise ScholarMCPError({'code': 'invalid_arguments', 'message': str(error),
                              'retryable': False, 'details': {}}, tool=tool) from None
    bridge = bridge_config()
    diagnostics = []
    async def call():
        return await _bridge_post(bridge, '/scholar', payload) if bridge else await _local_call(payload)
    value = await call()
    error = value.get('error') or {}
    recoverable = {'bridge_transport_error', 'mcp_transport_error', 'network_error', 'proxy_error', 'local_mcp_unavailable'}
    if not value.get('ok'):
        challenges = {'verification_required', 'blocked', 'rate_limited'}
        diagnosis = ({'reason': error['code'], 'action': 'manual_verification_or_wait',
                      'bridge': 'response_received'} if error.get('code') in challenges
                     else await _diagnose(bridge))
        diagnostics.append({'stage': 'diagnostics', 'result': diagnosis})
        if bridge and (diagnosis.get('error') or {}).get('code') == 'bridge_transport_error':
            # A disconnected bridge cannot repair its own control channel.
            # The persistent workflow scheduler waits for the independent local
            # guardian, then repeats this exact tool request on the same run.
            diagnostics.append({'stage': 'wait_for_guardian', 'tool': tool,
                                'reason': 'bridge_or_tunnel_unreachable'})
            raise ScholarMCPError(error, diagnostics, tool)
        blocked = diagnosis.get('reason') in challenges | {'interpreter_missing', 'python_module_missing',
                    'mcp_protocol_error', 'mcp_schema_mismatch', 'mcp_tool_missing'}
        if error.get('code') in recoverable and error.get('retryable', True) and not blocked:
            recovery = await _repair(bridge, error, diagnosis)
            diagnostics.append({'stage': 'repair', 'result': recovery})
            # One retry, preserving exactly the same tool and arguments. No fallback.
            value = await call()
            diagnostics.append({'stage': 'retry', 'tool': tool, 'ok': bool(value.get('ok'))})
        if not value.get('ok'):
            raise ScholarMCPError(value.get('error') or error, diagnostics, tool)
    data=value.get('data') or {};rows=[]
    for raw in data.get('results',[]):
        url=raw.get('url') or '';decoded=unquote(url);doi=re.search(r'10\.\d{4,9}/[^?#\s]+',decoded,re.I);arxiv=re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})',url)
        title=re.sub(r'^(?:\[(?:PDF|HTML|BOOK|CITATION)\]\s*)+','',raw['title'],flags=re.I)
        rows.append({'title':title,'authors':raw.get('authors') or [],'year':raw.get('year'),'venue':'','doi':doi[0].rstrip('.,;)') if doi else '','arxiv':arxiv[1] if arxiv else '','url':url,'abstract':'','search_snippet':raw.get('snippet') or '','cited_by':raw.get('cited_by'),'source':'Google Scholar · MCP','verified':False,'evidence':'search-result','discovery_record':raw})
    return PaperRows(rows,data.get('next_cursor', value.get('next_cursor')),diagnostics)


async def reconcile(rows,journal_only=False):
    from .references import search
    from .literature_providers import title_key
    semaphore=asyncio.Semaphore(4)
    async def one(row):
        async with semaphore:
            if row.get('arxiv'):return None if journal_only else row
            try:
                metadata=await search(row.get('doi') or row['title'],settings={},source='crossref',limit=3)
                matches=[v for v in metadata if title_key(v['title'])==title_key(row['title'])]
                # Identical titles can describe a preprint and the published
                # article. Prefer the journal record for a publisher result.
                matches.sort(key=lambda v:v.get('publication_type')=='journal-article',reverse=True)
                match=next(iter(matches),None)
                if match:
                    if journal_only and match.get('publication_type')!='journal-article':return None
                    return {**row,**match,'search_snippet':row.get('search_snippet',''),'discovery_record':row.get('discovery_record'),'source':row['source']+' · Crossref 题录核验','evidence':'metadata' if not match.get('abstract') else 'metadata-and-abstract'}
            except Exception:pass
            return None if journal_only else row
    verified=await asyncio.gather(*(one(row) for row in rows))
    return PaperRows([row for row in verified if row],getattr(rows,'next_cursor',None),getattr(rows,'diagnostics',[]))
