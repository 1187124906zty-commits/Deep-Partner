"""Check source routing, date limits, self exclusion and provider wire formats."""
import asyncio,json
from unittest.mock import patch
import httpx
from server.references import search
from server.literature_providers import eligible,resolve,available

requests=[]
def handler(request):
    requests.append(request)
    if request.url.host=='api.clarivate.com':
        assert request.headers['X-ApiKey']=='test-wos'
        assert '2022-2026' in request.url.params['q']
        return httpx.Response(200,json={'hits':[{'uid':'WOS:fixture','title':'Recent study','source':{'publishYear':2025,'sourceTitle':'Journal of Testing'},'names':{'authors':[{'displayName':'A. Researcher'}]},'identifiers':{'doi':'10.1000/recent'},'sourceTypes':['Journal']}]})
    if request.url.host=='serpapi.com':
        assert request.url.params['as_ylo']=='2022'
        return httpx.Response(200,json={'organic_results':[{'title':'Recent study','link':'https://doi.org/10.1000/recent','snippet':'A search snippet, not a paper abstract.','publication_info':{'summary':'A Researcher - Journal of Testing, 2025','authors':[{'name':'A. Researcher'}]}}]})
    assert request.url.host=='api.crossref.org'
    row={'title':['Recent study'],'author':[{'given':'A.','family':'Researcher'}],'published':{'date-parts':[[2025,4,1]]},'container-title':['Journal of Testing'],'DOI':'10.1000/recent','type':'journal-article'}
    if 'works/10.' in str(request.url) and 'old' in str(request.url):row.update(published={'date-parts':[[1980]]})
    if request.url.path=='/works':
        assert request.url.params.get('sort')!='published'
        assert 'from-pub-date:2022-01-01' in request.url.params['filter']
        return httpx.Response(200,json={'message':{'items':[row,{**row,'DOI':'10.1000/old','published':{'date-parts':[[1980]]}}]}})
    return httpx.Response(200,json={'message':row})

original_client=httpx.AsyncClient
def client(*args,**kwargs):return original_client(*args,**kwargs,transport=httpx.MockTransport(handler))

async def main():
    assert resolve({})=='crossref'
    assert resolve({'wos_api_key':'test-wos'})=='wos'
    assert not next(p for p in available({}) if p['id']=='scholar')['configured']
    try:resolve({},'wos');raise AssertionError('Unconfigured source accepted')
    except ValueError:pass
    ref={'title':'A closed-form equation.','doi':'https://doi.org/10.1000/SELF'}
    assert not eligible({'title':'Different title','doi':'10.1000/self','year':2025},ref,2022)
    assert not eligible({'title':'A Closed Form Equation','year':2025},ref,2022)
    assert not eligible({'title':'Unknown year'},ref,2022)
    with patch('httpx.AsyncClient',client):
        rows=await search('moisture transport',min_year=2022);assert len(rows)==1 and rows[0]['year']==2025
        assert not await search('10.1000/old',min_year=2022)
        rows=await search('moisture transport',settings={'wos_api_key':'test-wos'},source='wos',min_year=2022,journal_only=True)
        assert rows[0]['authors']==['A. Researcher'] and rows[0]['year']==2025 and rows[0]['source'].startswith('Web of Science')
        rows=await search('moisture transport',settings={'scholar_api_key':'test-scholar'},source='scholar',min_year=2022,journal_only=True)
        assert rows[0]['doi']=='10.1000/recent' and rows[0]['abstract']=='' and 'Crossref' in rows[0]['source']
        assert rows[0]['search_snippet'].startswith('A search snippet')
    def denied(request):return httpx.Response(401)
    def denied_client(*args,**kwargs):return original_client(*args,**kwargs,transport=httpx.MockTransport(denied))
    with patch('httpx.AsyncClient',denied_client):
        try:await search('test query',settings={'scholar_api_key':'DO-NOT-EXPOSE'},source='scholar');raise AssertionError('Denied request accepted')
        except ValueError as e:assert 'DO-NOT-EXPOSE' not in str(e) and '401' in str(e)
    print(json.dumps({'passed':True,'external_calls':0,'checks':['explicit source routing','Crossref year filter','exact DOI year filter','WoS camelCase metadata and API header','Scholar snippet distinguished and journal identity resolved','normalized DOI/title self exclusion','unknown year excluded','missing credentials explicit','provider error contains no API key']}))

asyncio.run(main())
