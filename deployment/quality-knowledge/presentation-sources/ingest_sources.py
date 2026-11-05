"""Fetch the bounded presentation-source list; keep original bytes and access logs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
SOURCE_NOTES=ROOT.parent/'ppt-purpose-source-notes.json'
USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'
ALTERNATIVES={
    'S04':['https://www.darpa.mil/about-us/heilmeier-catechism'],
    'S05':['https://grants.nih.gov/grants/rppr/index.htm'],
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def fetch(source):
    folder=ROOT/source['id'];folder.mkdir(parents=True,exist_ok=True)
    row={'source_id':source['id'],'title':source['title'],'publisher':source['publisher'],
         'canonical_url':source['url'],'started_at':utcnow(),'attempts':[],
         'distribution':'private_local_library_only','public_deployment_allowed':False,
         'rule_synthesis_included':False}
    urls=[source['url'],source['url']]+ALTERNATIVES.get(source['id'],[])
    for number,url in enumerate(urls,1):
        result={'attempt':number,'url':url,'started_at':utcnow()}
        try:
            response=requests.get(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html,application/pdf;q=0.9,*/*;q=0.8'},timeout=(12,35))
            result.update(status_code=response.status_code,final_url=response.url,bytes=len(response.content),
                          content_type=response.headers.get('Content-Type',''),
                          last_modified=response.headers.get('Last-Modified'),etag=response.headers.get('ETag'))
            pdf=response.content.startswith(b'%PDF-')
            soup=None if pdf else BeautifulSoup(response.content,'html.parser')
            title='' if pdf else soup.title.get_text(' ',strip=True) if soup.title else ''
            result['document_title']=title
            blocked=bool(re.search(r'just a moment|access denied|request rejected|attention required',title,re.I))
            usable=response.status_code==200 and not blocked and len(response.content)>100 and (pdf or soup is not None)
            if usable:
                suffix='pdf' if pdf else 'html'
                path=folder/('original.'+suffix);path.write_bytes(response.content)
                row.update(status='downloaded',original_path=path.relative_to(ROOT).as_posix(),
                           original_format=suffix,final_url=response.url,downloaded_at=utcnow(),
                           original_bytes=len(response.content),content_type=result['content_type'])
                result['saved_as']=row['original_path'];row['attempts'].append(result)
                break
            result['error']='http_error' if response.status_code!=200 else 'blocker_or_unusable_response'
            if response.content:
                diagnostic=folder/f'access-response-{number}.html'
                diagnostic.write_bytes(response.content)
                result['diagnostic_path']=diagnostic.relative_to(ROOT).as_posix()
        except requests.RequestException as error:
            result['error']=type(error).__name__+': '+str(error)[:300]
        row['attempts'].append(result)
        if number==1:time.sleep(.4)
    row.setdefault('status','not_retrieved')
    row['finished_at']=utcnow()
    (folder/'fetch.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return row


def main():
    sources=json.loads(SOURCE_NOTES.read_text(encoding='utf8'))['sources']
    results=list(ThreadPoolExecutor(max_workers=5).map(fetch,sources))
    (ROOT/'fetch-manifest.json').write_text(json.dumps({'created_at':utcnow(),'sources':results},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for row in results:
        print(json.dumps({'id':row['source_id'],'status':row['status'],'format':row.get('original_format'),
                          'bytes':row.get('original_bytes'),'attempts':len(row['attempts'])},ensure_ascii=False))


if __name__=='__main__':main()
