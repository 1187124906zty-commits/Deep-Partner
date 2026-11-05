"""Year- and category-bound journal metrics from Clarivate or publisher pages."""
from datetime import date
import re
from urllib.parse import quote
import httpx
from .network_sources import fetch_official,Page
from .journal_catalog import normalize
from .storage import now

BASE='https://api.clarivate.com/apis/wos-journals/v1'


def normalize_issn(value):return re.sub(r'[^0-9X]','',str(value).upper())


def report_years(value):
    years=[]
    if isinstance(value,dict):
        years.extend(int(k) for k in value if re.fullmatch(r'(?:19|20)\d{2}',str(k)))
        if str(value.get('year','')).isdigit():years.append(int(value['year']))
        for v in value.values():
            if isinstance(v,(list,dict)):years.extend(report_years(v))
    elif isinstance(value,list):
        for v in value:
            if isinstance(v,(list,dict)):years.extend(report_years(v))
    return list(set(years))


async def clarivate(journal,settings,year=None):
    key=settings.get('jcr_api_key');checked=now()
    if not key:return {'status':'not_configured','message':'尚未配置 Clarivate Journals API Key，可在工作台设置中添加。WoS Starter Key 不包含 JCR 权限。','checked':checked}
    try:
        async with httpx.AsyncClient(timeout=25,trust_env=False,headers={'X-ApiKey':key}) as client:
            found=await client.get(BASE+'/journals',params={'q':next(iter(journal.get('issn',[])),journal['name']),'limit':10});found.raise_for_status()
            hit=None
            for candidate in found.json().get('hits',[]):
                jid=candidate.get('id')
                if not jid:continue
                response=await client.get(BASE+'/journals/'+quote(jid,safe=''));response.raise_for_status();record=response.json()
                expected={normalize_issn(i) for i in journal.get('issn',[]) if i}
                actual={normalize_issn(record.get(k,'')) for k in ('issn','eIssn')}
                if (expected and expected&actual) or (not expected and normalize(record.get('name') or record.get('title',''))==normalize(journal['name'])):hit=record;break
            if not hit:return {'status':'not_found','message':'未在 JCR 中取得与该期刊 ISSN 一致的记录','checked':checked}
            available=hit.get('journalCitationReports',{})
            years=report_years(available)
            chosen=int(year) if year else max(years,default=date.today().year-1)
            source=BASE+'/journals/'+quote(hit['id'],safe='')+'/reports/year/'+str(chosen)
            response=await client.get(source);response.raise_for_status();report=response.json()
        if report.get('suppressed'):return {'status':'suppressed','year':chosen,'source':source,'checked':checked,'message':'该期刊在指定年份的 JCR 报告已被抑制，未显示指标'}
        value=report.get('metrics',{}).get('impactMetrics',{}).get('jif');ranks=report.get('ranks',{}).get('jif') or []
        return {'status':'ready','source':source,'journal_id':hit['id'],'year':int(report.get('year') or chosen),'impact_factor':value,'categories':[{'category':v.get('category'),'edition':v.get('edition'),'rank':v.get('rank'),'quartile':v.get('quartile'),'percentile':v.get('jifPercentile')} for v in ranks],'checked':checked,'available_years':sorted(years,reverse=True)}
    except httpx.HTTPStatusError as e:
        status=e.response.status_code
        return {'status':'authorization_required' if status in (401,403) else 'not_found' if status==404 else 'unavailable','message':'JCR 接口需要有效授权与配额' if status in (401,403) else '该年份报告未取得' if status==404 else 'JCR 接口暂未返回可用数据','checked':checked}
    except (httpx.HTTPError,KeyError,ValueError,TypeError):return {'status':'unavailable','message':'JCR 接口暂未返回可核验数据','checked':checked}


async def publisher_metric(journal):
    url=journal.get('homepage','')
    if not url:return {'status':'no_source','message':'尚未取得官方期刊主页'}
    try:
        result=await fetch_official(url);page=Page(result['url']);page.feed(result['content'].decode('utf8',errors='replace'));raw=re.sub(r'\s+',' ',' '.join(page.parts))
        patterns=[r'(20\d{2})\s*(?:Journal\s+)?Impact\s+Factor\s*[:：]?\s*(\d+(?:\.\d+)?)',r'(\d+(?:\.\d+)?)\s*\(?\s*(20\d{2})\s*\)?\s*(?:Journal\s+)?Impact\s+Factor',r'(?:Journal\s+)?Impact\s+Factor\s*\((20\d{2})\)\s*[:：]?\s*(\d+(?:\.\d+)?)']
        for i,pattern in enumerate(patterns):
            match=re.search(pattern,raw,re.I)
            if match:
                year,value=(match[2],match[1]) if i==1 else (match[1],match[2])
                return {'status':'ready','value':float(value),'year':int(year),'source':result['url'],'checked':result['checked'],'label':'出版社披露 JIF','evidence':match[0]}
        return {'status':'no_year_bound_metric','source':result['url'],'checked':result['checked'],'message':'已查询官方页面，未取得同时带年份和数值的影响因子'}
    except (httpx.HTTPError,ValueError):return {'status':'unavailable','source':url,'checked':now(),'message':'官方页面暂未取得可核验指标'}


async def metrics(journal,settings=None,year=None):
    journal=dict(journal);record=await clarivate(journal,settings or {},year)
    journal['metrics_checked']=now();journal['jcr']=record;journal['cas']={'status':'authorization_required','scheme':'中国科学院期刊分区','message':'需中科院分区表授权数据；与 JCR 学科分区分别列示','source':'https://www.fenqubiao.com/'}
    if record['status']=='ready':
        journal['impact_factor']={'value':record['impact_factor'],'year':record['year'],'source':record['source'],'checked':record['checked'],'label':'JCR Journal Impact Factor'} if record['impact_factor'] is not None else None
        journal['quartiles']=[{**v,'year':record['year'],'scheme':'JCR','source':record['source']} for v in record['categories']]
    else:
        public=await publisher_metric(journal);journal['publisher_metrics']=public
        journal['impact_factor']=public if public['status']=='ready' else None;journal['quartiles']=[]
    journal['quartile']=None
    return journal
