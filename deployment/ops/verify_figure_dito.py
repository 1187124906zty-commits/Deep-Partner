"""Real element editing plus native Dito context, with model sends intercepted."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import argparse,base64,json,mimetypes,re,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
ORIGIN='https://tutor.example.invalid'


def exercise(ctx,page,origin,project,report,mode):
    turns=[]
    def intercept(socket):
        upstream=socket.connect_to_server()
        def send(message):
            try:event=json.loads(message)
            except (ValueError,TypeError):upstream.send(message);return
            if event.get('type')=='start_turn':turns.append(event)
            else:upstream.send(message)
        socket.on_message(send)
    ctx.route_web_socket(re.compile(r'.*'),intercept)
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    scenes=[];report['figure_responses']=[]
    page.on('response',lambda r:report['figure_responses'].append({'path':urlparse(r.url).path,'status':r.status}) if '/figure/' in r.url else None)
    def scene(response):
        if '/figure?edit_session=true' in response.url and response.ok:
            try:scenes.append(response.json())
            except Exception:pass
    page.on('response',scene)
    href=origin+('/research/' if origin==ORIGIN else '/')+'?project='+project['id']+'&dt_workspace='+project['native_id']+'&area=figures&file=results%2Ffigure02.png'
    page.goto(href,wait_until='domcontentloaded')
    canvas=page.get_by_role('region',name='图形工作区');canvas.wait_for(timeout=60000)
    page.wait_for_function("() => document.querySelector('.figure-paper svg')!==null")
    assert scenes
    report['edit_session_present']=bool(scenes[-1].get('edit_session'))
    obj=next(o for o in scenes[-1]['objects'] if o['kind']=='text' and o.get('role')=='panel-label' and o['properties'].get('text'))
    original=obj['properties']['text'];updated=original+' [edit check]'
    def save():
        page.wait_for_function("() => !['正在更新…','正在保存…'].includes(document.querySelector('.figure-status-label')?.textContent)",timeout=60000)
        button=page.get_by_role('region',name='图形工作区').get_by_role('button',name='保存图形',exact=True)
        if button.is_enabled():button.click()
        page.wait_for_function("() => document.querySelector('.figure-status-label')?.textContent==='已保存'",timeout=60000)
    def click_object():
        paper=page.locator('.figure-paper').bounding_box();x,y,w,h=obj['bounds']
        page.mouse.click(paper['x']+(x+w/2)*paper['width'],paper['y']+(y+h/2)*paper['height'])
    click_object()
    inspector=page.get_by_role('complementary',name='图形属性')
    inspector.get_by_role('textbox',name='内容',exact=True).wait_for()
    assert inspector.get_by_role('textbox',name='内容',exact=True).input_value()==original
    assert inspector.get_by_role('spinbutton',name='字号',exact=True).is_visible()
    report['checks']['click_element_opens_its_editable_properties']=True
    inspector.get_by_role('textbox',name='内容',exact=True).fill(updated)
    save()
    report['checks']['element_change_saved']=True
    canvas.get_by_role('button',name='撤销',exact=True).click()
    report['undo_probe']={'before':original,'edited':updated,'after':inspector.get_by_role('textbox',name='内容',exact=True).input_value()}
    page.wait_for_function("expected=>document.querySelector('input[name=text]')?.value===expected",arg=original,timeout=30000)
    canvas.get_by_role('button',name='重做',exact=True).click()
    page.wait_for_function("expected=>document.querySelector('input[name=text]')?.value===expected",arg=updated,timeout=30000)
    report['checks']['element_undo_redo']=True
    # Choosing an object from the layers returns directly to its style controls.
    canvas.get_by_role('toolbar',name='图形工具').get_by_role('button',name='图层',exact=True).click()
    inspector.locator('.figure-layer-row').filter(has_text=obj['label']).first.click()
    assert inspector.get_by_role('textbox',name='内容',exact=True).is_visible()
    report['checks']['layers_open_element_style']=True
    save()
    page.reload(wait_until='domcontentloaded')
    page.get_by_role('region',name='图形工作区').wait_for(timeout=60000)
    click_object()
    inspector=page.get_by_role('complementary',name='图形属性')
    assert inspector.get_by_role('textbox',name='内容',exact=True).input_value()==updated
    report['checks']['edited_element_survives_reload']=True
    # Restore the temporary fixture's label for subsequent runs.
    inspector.get_by_role('textbox',name='内容',exact=True).fill(original)
    save()
    assert canvas.get_by_role('button',name='AI 修改',exact=True).count()==0
    assert page.locator('.figure-conversation').count()==0
    report['checks']['no_separate_figure_ai_panel']=True
    page.screenshot(path=str(ROOT/f'reports/screenshots/figure-dito-{mode}-editor.png'))
    canvas.get_by_role('button',name='问 Dito',exact=True).click()
    location=page.locator('.dp-dito-location');location.wait_for(timeout=30000)
    assert 'figure02.png' in location.inner_text()
    assert page.locator('.dt-viewer-panel[data-open="true"]').is_visible()
    report['checks']['figure_opens_native_dito_with_current_location']=True
    # An unsaved preview and selected object are read at the moment of send.
    inspector.get_by_role('textbox',name='内容',exact=True).fill(original+' [context check]')
    page.wait_for_timeout(1000)
    panel=page.locator('.dt-viewer-panel[data-open="true"]')
    panel.locator('textarea').first.fill('核对当前选中的图形对象（界面验收，不送达模型）')
    panel.get_by_role('button',name='发送',exact=True).click()
    for _ in range(120):
        if turns:break
        page.wait_for_timeout(100)
    assert turns,'Native Dito did not emit a start_turn'
    sent=turns[-1]
    quotes=[base64.b64decode(a['base64']).decode('utf8') for a in sent.get('attachments',[]) if a.get('type')=='quote' and a.get('base64')]
    quote='\n'.join(quotes)
    report['checks']['dito_payload_contains_current_figure_and_selected_object']='figure02.png' in quote and obj['id'] in quote and 'context check' in quote
    report['checks']['dito_payload_contains_actual_current_image']=any(a.get('type')=='image' and a.get('base64') for a in sent.get('attachments',[]))
    report['checks']['dito_workspace_scope_is_project']=sent.get('workspace_id')==project['native_id']
    report['checks']['dito_knowledge_scope_is_project']=set(sent.get('knowledge_bases',[]))==set(project['config'].get('knowledge_bases',[]))
    report['captured_request']={'workspace_id':sent.get('workspace_id'),'knowledge_bases':sent.get('knowledge_bases'),
                                'attachment_types':[a.get('type') for a in sent.get('attachments',[])],
                                'location_quote':quote,'delivered_to_model':False}
    # Keep the same Dito tab open while changing the viewed content and line.
    sidebar=page.locator('.dp-native-shell aside').first
    sidebar.get_by_role('button',name='程序',exact=True).click()
    page.get_by_role('button',name='项目程序',exact=True).click()
    page.locator('.file-table tbody tr').filter(has_text='README.md').first.click()
    page.get_by_role('button',name='选择第3行',exact=True).wait_for(timeout=30000)
    page.get_by_role('button',name='选择第3行',exact=True).click()
    page.wait_for_function("() => document.querySelector('.dp-dito-location')?.textContent.includes('README.md')&&document.querySelector('.dp-dito-location')?.textContent.includes('3–3')")
    report['checks']['existing_dito_follows_new_file_and_line']=True
    page.screenshot(path=str(ROOT/f'reports/screenshots/figure-dito-{mode}-context.png'))
    report['checks']['no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args()
    mode='published' if args.published else 'candidate'
    project=json.loads((ROOT/'.local/onboarding-test-project.json').read_text())
    account=json.loads(subprocess.run(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    report={'mode':mode,'checks':{},'errors':[],'new_model_turn':False,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1600,'height':1000})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        project=next(row for row in ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'] if row['id']==project['id'])
        if not args.published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/('index.html' if not name else name);assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page()
        completed=False
        try:
            exercise(ctx,page,ORIGIN,project,report,mode);completed=True
        finally:
            report['passed']=completed and bool(report['checks']) and all(report['checks'].values()) and not report['errors']
            (ROOT/f'reports/figure-dito-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            page.screenshot(path=str(ROOT/f'reports/screenshots/figure-dito-{mode}-last.png'))
        browser.close()
    print(json.dumps(report,ensure_ascii=False));assert report['passed']


if __name__=='__main__':main()
