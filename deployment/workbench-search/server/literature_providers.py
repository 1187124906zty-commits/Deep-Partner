"""Explicit literature sources; provider credentials never leave account settings."""
from datetime import date
from urllib.parse import unquote
import re

PROVIDERS = {
    'scholar_mcp': ('Google Scholar · MCP', None),
    'academic_web': ('学术网页 · 多源搜索', None),
    'crossref': ('Crossref', None),
    'semantic': ('Semantic Scholar', 'literature_token'),
    'scholar': ('Google Scholar · SerpApi', 'scholar_api_key'),
    'wos': ('Web of Science · Starter API', 'wos_api_key'),
}


def available(settings=None):
    settings = settings or {}
    from .search_mcp import ready
    return [{'id': key, 'name': name, 'configured': ready() if key=='scholar_mcp' else not secret or bool(settings.get(secret))}
            for key, (name, secret) in PROVIDERS.items()]


def resolve(settings=None, source=None):
    settings = settings or {}
    source = source or settings.get('literature_provider', 'auto')
    if source == 'auto':
        from .search_mcp import ready
        source = next((p for p in ('wos', 'scholar', 'semantic') if settings.get(PROVIDERS[p][1])), 'scholar_mcp' if ready() else 'academic_web')
    if source not in PROVIDERS:
        raise ValueError('未知的文献检索来源')
    name, secret = PROVIDERS[source]
    if source=='scholar_mcp':
        from .search_mcp import ready
        if not ready():raise ValueError('Google Scholar MCP 尚未安装')
    if secret and not settings.get(secret):
        raise ValueError(name + ' 尚未配置 API Key，请在工作台设置中填写')
    return source


def title_key(value):
    return re.sub(r'[\W_]+', '', value or '').casefold()


def doi_key(value):
    return re.sub(r'^https?://(?:dx\.)?doi.org/', '', unquote(value or '').strip(), flags=re.I).casefold()


def eligible(row, reference=None, min_year=None):
    if min_year is not None:
        try:
            if not min_year <= int(row.get('year') or 0) <= date.today().year:
                return False
        except (ValueError, TypeError):
            return False
    if reference:
        if doi_key(reference.get('doi')) and doi_key(row.get('doi')) == doi_key(reference.get('doi')):
            return False
        if title_key(row.get('title')) == title_key(reference.get('title')):
            return False
    return bool(row.get('title'))


async def wos_search(client, query, settings, limit, venue=None, min_year=None, newest=False, journal_only=False,offset=0):
    # Use the topic field documented by the current Starter API client.
    query = re.sub(r'["\r\n]', ' ', query)
    expression = 'TS=(' + ' AND '.join('"' + word + '"' for word in query.split()[:14]) + ')'
    if re.fullmatch(r'10\.\d{4,9}/\S+', doi_key(query)):
        expression = 'DO=("' + doi_key(query) + '")'
    if min_year:
        expression += f' AND PY=({min_year}-{date.today().year})'
    if venue:
        expression += ' AND SO=("' + re.sub(r'["\r\n]', ' ', venue) + '")'
    if journal_only:
        expression += ' AND DT=(Article OR Review)'
    response = await client.get('https://api.clarivate.com/apis/wos-starter/v1/documents',
        params={'q': expression, 'db': 'WOS', 'limit': min(limit, 50), 'page': 1+offset//max(1,limit),
                **({'sortField': 'PY+D'} if newest else {})}, headers={'X-ApiKey': settings['wos_api_key']})
    response.raise_for_status()
    values = []
    for item in response.json().get('hits', []):
        source = item.get('source') or {}; identifiers = item.get('identifiers') or {}
        links = item.get('links') or {}; doi = identifiers.get('doi', '')
        values.append({'title': item.get('title', ''),
            'authors': [a.get('displayName') or a.get('wosStandard', '') for a in (item.get('names') or {}).get('authors', [])],
            'year': source.get('publishYear',source.get('publish_year')), 'venue': source.get('sourceTitle') or source.get('source_title', ''),
            'doi': doi, 'url': links.get('record') or ('https://doi.org/' + doi if doi else ''),
            'abstract': '', 'publication_type': 'journal-article' if 'Journal' in item.get('sourceTypes', item.get('source_types', [])) else '',
            'verified': True, 'source': PROVIDERS['wos'][0], 'wos_uid': item.get('uid', '')})
    return values


async def scholar_search(client, query, settings, limit, venue=None, min_year=None, newest=False,offset=0):
    response = await client.get('https://serpapi.com/search.json', params={
        'engine': 'google_scholar', 'q': query + (' "' + venue + '"' if venue else ''),
        'api_key': settings['scholar_api_key'], 'num': min(limit, 20), 'start':offset,'hl': 'en',
        **({'as_ylo': min_year, 'as_yhi': date.today().year} if min_year else {}),
        **({'scisbd': 1} if newest else {})})
    response.raise_for_status(); payload = response.json()
    if payload.get('error'):
        raise ValueError('Google Scholar 检索未完成，请检查 SerpApi 配额与密钥')
    values = []
    for item in payload.get('organic_results', []):
        info = item.get('publication_info') or {}; summary = info.get('summary', '')
        year = re.search(r'\b(?:19|20)\d{2}\b', summary)
        link = item.get('link', ''); doi = re.search(r'10\.\d{4,9}/[^\s?#]+', unquote(link))
        values.append({'title': item.get('title', ''), 'authors': [a['name'] for a in info.get('authors', [])],
            'year': int(year[0]) if year else None, 'venue': '', 'doi': doi[0] if doi else '',
            'url': link, 'abstract': '', 'search_snippet': item.get('snippet', ''),
            'publication_summary': summary, 'verified': False, 'source': PROVIDERS['scholar'][0]})
    return values
