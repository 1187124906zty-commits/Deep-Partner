"""Check explicit new drafts, native file tabs and PDF first paint on real APIs."""
from pathlib import Path
from urllib.parse import urlparse,unquote,quote
import argparse,json,mimetypes,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
ORIGIN='https://tutor.example.invalid'

def exercise(ctx,page,origin,projects,report,mode):
    project=next(p for p in projects if p['name']=='水分扩散')
    entry='/research/' if origin==ORIGIN else '/'
    href=origin+entry+'?project='+project['id']+'&dt_workspace='+project['native_id']
    page.goto(href,wait_until='domcontentloaded')
    page.locator('.dp-composer-policy textarea').wait_for(timeout=30000)
    report['checks']['no_intrusive_idle_row']=page.locator('.dp-attachment-hint,.dp-web-address').count()==0 and page.get_by_role('button',name='查看网页',exact=True).count()==0
    profile=ctx.request.get(origin+'/api/auth/profile',headers={'Origin':origin}).json()
    scope='draft:'+project['native_id'];marker='RECOVERED_DRAFT_CHECK_20261102'
    key='deeptutor.failedSubmissions.owner.'+quote('user:'+profile['id'],safe='')+'.record.'+quote(scope,safe='')+':connection-check'
    page.evaluate('''({key,marker})=>localStorage.setItem(key,JSON.stringify({content:marker,capability:'chat',submissionId:'connection-check',savedAt:Date.now(),requestSnapshot:{content:marker,capability:'chat',language:'zh',enabledTools:[],knowledgeBases:[]}}))''',{'key':key,'marker':marker})
    page.reload(wait_until='domcontentloaded');page.locator('.dp-composer-policy textarea').wait_for(timeout=30000)
    page.get_by_text(marker,exact=True).first.wait_for(timeout=15000)
    report['checks']['previous_failed_draft_can_recover']=True
    # Put a test anchor in the actual message scroll root, using its delegated click.
    target='/research/api/projects/'+project['id']+'/file?path=README.md'
    def click_message_link(href,label):
        page.evaluate('''({href,label})=>{const a=document.createElement('a');a.href=href;a.textContent=label;a.id='connection-preview-probe';document.querySelector('[data-chat-scroll-root]').append(a)}''',{'href':href,'label':label})
        page.locator('#connection-preview-probe').click()
        page.locator('#connection-preview-probe').evaluate('(node)=>node.remove()')
    click_message_link(target,'生成文件预览验证')
    panel=page.locator('.dt-viewer-panel[data-open="true"]');panel.wait_for(timeout=10000)
    panel.get_by_text('README.md',exact=True).first.wait_for()
    page.wait_for_function("() => document.querySelector('.dt-viewer-panel')?.textContent.includes('Mois-Net 水分扩散测试项目')",timeout=20000)
    report['checks']['protected_output_opens_native_sidebar']=True
    report['checks']['file_keeps_conversation_open']=page.locator('.dp-composer-policy textarea').is_visible() and page.url==href
    page.screenshot(path=str(ROOT/f'reports/screenshots/connection-file-{mode}.png'))
    click_message_link('https://example.com','会话来源网页验证')
    preview=page.get_by_role('region',name='网页预览');preview.wait_for()
    report['checks']['message_web_link_reuses_sidebar']=preview.locator('iframe').get_attribute('src')=='https://example.com/'
    panel.get_by_role('button',name='关闭查看器',exact=True).click()
    page.get_by_role('button',name='新会话',exact=True).first.click();page.wait_for_timeout(400)
    report['checks']['explicit_new_session_is_empty']=page.get_by_text(marker,exact=True).count()==0 and page.locator('.dp-composer-policy textarea').input_value()==''
    report['checks']['recovery_record_preserved']=page.evaluate('(key)=>localStorage.getItem(key)!==null',key)
    page.evaluate('(key)=>localStorage.removeItem(key)',key)
    # Delay only semantic preparation: the original PDF must still paint.
    micro=next(p for p in projects if p['name']=='硫酸盐侵蚀微观建模')
    items=ctx.request.get(origin+'/research/api/projects/'+micro['id']+'/literature/items',headers={'Origin':origin}).json()
    report['literature_names']=[f['name'] for f in items['files']]
    page.goto(origin+entry+'?project='+micro['id']+'&dt_workspace='+micro['native_id']+'&area=literature',wait_until='domcontentloaded')
    page.locator('.bibliography-list tbody tr').first.wait_for(timeout=30000)
    def defer_semantics(route):
        route.fulfill(status=503,content_type='application/json',body='{"detail":"Semantic preparation paused for first-paint check"}')
    pattern='**/research/api/projects/'+micro['id']+'/reader'
    ctx.route(pattern,defer_semantics)
    rows=page.locator('.bibliography-list tbody tr')
    chosen=next((rows.nth(i) for i in range(rows.count()) if 'Feng2014' in rows.nth(i).inner_text()),rows.first)
    chosen.click();page.get_by_role('button',name='阅读与翻译',exact=True).click()
    start=time.perf_counter()
    page.wait_for_function("() => [...document.querySelectorAll('.pdfViewer canvas')].some(c=>c.width>100&&c.height>100)",timeout=20000)
    report['pdf_first_paint_semantic_unavailable_seconds']=round(time.perf_counter()-start,3)
    report['checks']['pdf_displays_without_waiting_for_semantic_parse']=True
    page.screenshot(path=str(ROOT/f'reports/screenshots/connection-pdf-{mode}.png'))
    ctx.unroute(pattern,defer_semantics)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args();mode='published' if args.published else 'candidate'
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    report={'checks':{},'errors':[],'mode':mode,'model_calls':0,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            ctx=browser.new_context(viewport={'width':1480,'height':980});assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
            if not args.published:
                def static(route):
                    name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                    if not name or name.startswith(('assets/','fonts/')):
                        target=DIST/('index.html' if not name else name)
                        assert target.resolve().is_relative_to(DIST.resolve())
                        route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                    else:route.continue_()
                ctx.route(ORIGIN+'/research/**',static)
            page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)));page.on('response',lambda r:report.setdefault('file_responses',[]).append({'url':r.url,'status':r.status}) if '/file?' in r.url else None)
            exercise(ctx,page,ORIGIN,ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'],report,mode)
            report['checks']['no_script_errors']=not report['errors'];report['passed']=all(report['checks'].values())
            browser.close()
    except Exception as e:
        report['failure']=str(e);report['passed']=False
        try:report['panel_text']=page.locator('.dt-viewer-panel').inner_text();page.screenshot(path=str(ROOT/f'reports/screenshots/connection-failure-{mode}.png'))
        except Exception:pass
        raise
    finally:(ROOT/f'reports/connection-previews-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
    assert report['passed']

if __name__=='__main__':main()
