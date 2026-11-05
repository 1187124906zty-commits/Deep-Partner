"""One ordinary HTTPS attempt per missing official source, on the private host."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import urllib.request
import urllib.error
import re

root=Path(__file__).resolve().parent
sources={
    'S04':'https://www.darpa.mil/about/heilmeier-catechism',
    'S05':'https://www.grants.nih.gov/grants-process/post-award-monitoring-and-reporting/reporting-requirements/research-performance-progress-report-rppr',
}


def fetch(item):
    sid,url=item
    row={'source_id':sid,'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),
         'method':'ordinary_https_from_existing_private_container','status':'not_retrieved'}
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            content=response.read();row.update(http_status=response.status,final_url=response.url,bytes=len(content))
        title=re.search(b'<title[^>]*>(.*?)</title>',content,re.I|re.S)
        value=title.group(1).decode('utf8','replace') if title else ''
        row['title']=value
        if row['http_status']==200 and not re.search('just a moment|access denied|error',value,re.I):
            target=root/sid/'original-remote.html';target.write_bytes(content)
            row.update(status='downloaded',original_path=target.relative_to(root).as_posix())
    except (urllib.error.URLError,TimeoutError,OSError) as error:
        row['error']=str(error)[:400]
        if isinstance(error,urllib.error.HTTPError):row['http_status']=error.code
    (root/sid/'fetch-remote.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return row


results=list(ThreadPoolExecutor(max_workers=2).map(fetch,sources.items()))
(root/'remote-missing-fetch-results.json').write_text(json.dumps({'sources':results},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for row in results:print(json.dumps(row,ensure_ascii=False))
