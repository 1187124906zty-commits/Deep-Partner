"""Exercise paper maps through the authenticated product API and reading UI."""
from pathlib import Path
import argparse,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/paper-map-live.json'
ORIGIN='https://tutor.example.invalid'
NATIVE='ws_0e6fc7aba58a4b258e25e1195702fde3'

def main():
    sys.stdout.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['inspect','start','status','qa','backfill']);args=parser.parse_args()
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','-o','ProxyJump=research-cluster-xh5','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,encoding='utf8',check=True).stdout)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(viewport={'width':1540,'height':1000})
        response=context.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN});assert response.ok,'Native login failed'
        def get(path):
            response=context.request.get(ORIGIN+path);assert response.ok,str(response.status)+' '+response.text()[:500];return response.json()
        def post(path,payload):
            response=context.request.post(ORIGIN+path,data=payload,headers={'Origin':ORIGIN});assert response.ok,str(response.status)+' '+response.text()[:500];return response.json()
        projects=get('/research/api/projects')['projects'];project=next(x for x in projects if x['native_id']==NATIVE);base='/research/api/projects/'+project['id']
        files=get(base+'/literature/items')['files']
        previous=json.loads(REPORT.read_text(encoding='utf8')) if REPORT.is_file() else {}
        report={**previous,'project_id':project['id'],'native_id':NATIVE,'project_name':project['name'],'pdf_count':sum(str(f.get('name','')).lower().endswith('.pdf') for f in files)}
        if args.action=='inspect':print(json.dumps({'project':project['name'],'id':project['id'],'pdf_count':report['pdf_count'],'files':[{'library':x['library'],'name':x['name']} for x in files]},ensure_ascii=False))
        if args.action=='start':
            file=next(x for x in files if x['name']=='reading/10.1016_j.cemconres.2020.106048.pdf')
            report['sample']={**post(base+'/literature/content-map',{'asset':file['name'],'library':file['library']}),'asset':file['name'],'library':file['library']}
            print(json.dumps(report,ensure_ascii=False))
        if args.action=='status':
            file=report['sample'];value=get(base+'/literature/content-map?asset='+__import__('urllib.parse',fromlist=['quote']).quote(file['asset'])+'&library='+file['library'])
            report['sample']={**file,**{k:v for k,v in value.items() if k!='map'}}
            graph=value.get('map')
            if graph:
                path=ROOT/'reports/氯硫框架具体化/paper-maps-20261104/qin2020/automatic-map.json';path.write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf8')
                report['sample_quality']={'nodes':len(graph['nodes']),'edges':len(graph['edges']),'abstract_chars':len(graph['abstract']['text']),'abstract_complete':graph['abstract']['complete'],'coverage':graph['coverage'],'map_file':str(path)}
            print(json.dumps({'sample':report['sample'],'quality':report.get('sample_quality')},ensure_ascii=False))
        if args.action=='backfill':
            value=post(base+'/literature/content-maps/backfill',{});report['backfill']={k:v for k,v in value.items() if k!='items'};report['backfill']['job_ids']=[x['job_id'] for x in value['items']]
            print(json.dumps(report['backfill'],ensure_ascii=False))
        if args.action=='qa':
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+NATIVE,wait_until='domcontentloaded',timeout=60000)
            page.get_by_role('navigation',name='工作视图').get_by_role('button',name='成果',exact=True).click()
            page.get_by_role('navigation',name='研究成果').get_by_role('button',name='文献',exact=True).click()
            page.wait_for_selector('.bibliography-table',timeout=30000)
            row=page.locator('.bibliography-table tbody tr').filter(has_text='A chemo-transport-damage model for concrete under external sulfate attack').first
            if not row.count():row=page.locator('.bibliography-table tbody tr').filter(has_text='106048').first
            row.click();page.locator('.bibliography-detail').get_by_role('button',name='内容图谱',exact=True).click()
            page.wait_for_selector('.paper-content-map',timeout=15000);page.wait_for_timeout(1800)
            out=ROOT/'reports/screenshots';out.mkdir(exist_ok=True)
            report['qa']={'page_errors':errors,'views':{},'desktop_overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth')}
            for tab in ['完整摘要','思维导图','内容关系','问题与论证']:
                page.get_by_role('navigation',name='图谱视图').get_by_role('button',name=tab,exact=True).click();page.wait_for_timeout(350)
                name={'完整摘要':'abstract','思维导图':'tree','内容关系':'relations','问题与论证':'story'}[tab]
                path=out/('paper-map-'+name+'.png');page.screenshot(path=str(path));report['qa']['views'][name]={'screenshot':str(path),'text':page.locator('.paper-content-map').inner_text()[:12000]}
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
            report['qa']['mobile_overflow']=page.evaluate('document.documentElement.scrollWidth>innerWidth');path=out/'paper-map-mobile.png';page.screenshot(path=str(path));report['qa']['mobile_screenshot']=str(path)
            report['qa']['passed']=not errors and not report['qa']['desktop_overflow'] and not report['qa']['mobile_overflow']
            print(json.dumps(report['qa'],ensure_ascii=False))
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        browser.close()

if __name__=='__main__':main()
