"""Measure repeat file opens against unchanged project source, without edits."""
from pathlib import Path
from urllib.parse import quote
import json,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login,ORIGIN


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(proxy={'server':os.environ.get('WORKBENCH_HTTP_PROXY','http://127.0.0.1:12000')},viewport={'width':1440,'height':950})
        class Client:
            def post(self,path,json=None):
                r=context.request.post(ORIGIN+path,data=json,headers={'Origin':ORIGIN})
                class Result:
                    def raise_for_status(self):assert r.ok
                return Result()
        login(Client());project=next(p for p in context.request.get(ORIGIN+'/research/api/projects').json()['projects'] if p['name']=='水分扩散');prefix='/research/api/projects/'+project['id']
        queue=[''];chosen=None
        while queue and chosen is None:
            directory=queue.pop(0);items=context.request.get(ORIGIN+prefix+'/files?mode=code&path='+quote(directory,safe='')).json()['items']
            for row in items:
                if row['kind']=='folder' and directory.count('/')<3:queue.append(row['path'])
                elif row['kind']=='file' and row['name'].endswith(('.py','.m','.js','.rs','.sh')) and row['size']<100000:chosen=row;break
        assert chosen,'No small program file found'
        page=context.new_page();requests=[];page.on('request',lambda r:requests.append(r.url))
        print(json.dumps({'selected_file':chosen['path']},ensure_ascii=False),flush=True)
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&area=code',wait_until='domcontentloaded',timeout=60000)
        page.locator('.file-table tbody tr').first.wait_for(timeout=45000)
        pieces=chosen['path'].split('/')
        for index,folder in enumerate(pieces[:-1]):
            current='/'.join(pieces[:index+1])
            with page.expect_response(lambda r:'/files?path='+quote(current,safe='')+'&mode=code' in r.url,timeout=30000):
                page.locator('.file-table tbody tr').filter(has=page.get_by_text(folder,exact=True)).first.click()
        row=page.locator('.file-table tbody tr').filter(has_text=chosen['name']).first;row.wait_for(timeout=45000)
        times=[]
        for count in range(2):
            start=time.perf_counter();row.click();page.get_by_label('程序源代码',exact=True).wait_for(timeout=20000);times.append(round((time.perf_counter()-start)*1000,1));page.get_by_role('button',name='关闭查看器',exact=True).click()
        reads=[url for url in requests if '/file?path='+quote(chosen['path'],safe='') in url]
        report={'project':project['id'],'file':chosen['path'],'first_open_ms':times[0],'repeat_open_ms':times[1],'text_file_requests':len(reads),'passed':len(reads)==1 and times[1]<400,'source_unchanged':True,'model_calls':0}
        (ROOT/'reports/file-reopen-latency.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));browser.close()


if __name__=='__main__':main()
