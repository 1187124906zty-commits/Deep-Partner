"""Exercise the deployed APIs through the existing isolated QA session proxy."""
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import argparse,json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/network-live.json'
BASE='http://127.0.0.1:47901/research/api'

def call(path,payload=None,method=None):
    request=Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'},method=method or ('POST' if payload is not None else 'GET'))
    with urlopen(request,timeout=180) as response:return json.load(response)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','inspect','templates']);args=parser.parse_args()
    result=json.loads(OUT.read_text()) if OUT.exists() else {}
    if args.action=='prepare':
        if result.get('project'):raise RuntimeError('Reuse the existing verification project')
        sources=call('/search/sources');result['sources']=sources
        project=call('/projects',{'name':'文献传输与模板验收 · 独立测试'});pid=project['id'];result['project']=pid
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        papers=[{'title':'Fourier Neural Operator for Parametric Partial Differential Equations','arxiv':'2010.08895','year':2020,'venue':'arXiv','url':'https://arxiv.org/abs/2010.08895'},{'title':'Physics-Informed Neural Operator for Learning Partial Differential Equations','arxiv':'2111.03794','year':2021,'venue':'arXiv','url':'https://arxiv.org/abs/2111.03794'}]
        result['batch']=call('/projects/'+pid+'/literature/download-batch',{'entries':papers,'folder':'methods'})
        result['paper_search']=call('/projects/'+pid+'/literature/search?'+urlencode({'q':'moisture transport cement','years':5,'newest':'false','limit':5}))
        result['web_search']=call('/search/web?'+urlencode({'q':'Cement and Concrete Research official author guidelines','kind':'journal'}))
        result['institutions']=call('/author-profile/institutions?'+urlencode({'q':'Hohai University'}))
    if args.action in ('inspect','templates'):
        pid=result['project'];result['downloads']=call('/projects/'+pid+'/literature/downloads');result['library']=call('/projects/'+pid+'/literature/items')
    if args.action=='templates':
        result['templates']=call('/projects/'+pid+'/journal-templates/search',{'journal':'issn-0008-8846'})
        item=next((v for v in result['templates']['items'] if v['downloadable'] and 'els-cas' in v['url']),None)
        if item:result['template_download']=call('/projects/'+pid+'/journal-templates/download',{'journal':'issn-0008-8846','template':item['id']})
        result['journal_metrics']=call('/journals/issn-0008-8846')
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'project':result.get('project'),'queued':result.get('batch',{}).get('queued'),'paper_count':len(result.get('paper_search',{}).get('items',[])),'web_count':len(result.get('web_search',{}).get('items',[])),'institutions':len(result.get('institutions',{}).get('items',[])),'downloads':[(v['identifier'],v['status'],v.get('stage'),v.get('error')) for v in result.get('downloads',{}).get('items',[])],'template_bytes':result.get('template_download',{}).get('bytes')},ensure_ascii=False))

if __name__=='__main__':main()
