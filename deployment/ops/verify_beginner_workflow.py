"""Exercise chat drop/paste uploads, image/web preview and unified navigation."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import argparse,base64,io,json,mimetypes,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from PIL import Image
ORIGIN='https://tutor.example.invalid'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args();mode='published' if args.published else 'candidate'
    project=json.loads((ROOT/'.local/onboarding-test-project.json').read_text())
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    report={'mode':mode,'checks':{},'errors':[],'new_model_turn':False,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':960});assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        if not args.published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/('index.html' if not name else name);assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        turns=[]
        def socket_route(socket):
            upstream=socket.connect_to_server()
            def send(message):
                event=json.loads(message)
                if event.get('type')=='start_turn':turns.append(event)
                else:upstream.send(message)
            socket.on_message(send)
        ctx.route_web_socket('**',socket_route)
        page=ctx.new_page();page.on('pageerror',lambda error:report['errors'].append(str(error)))
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id'],wait_until='domcontentloaded')
        sidebar=page.locator('.dp-native-shell aside').first;sidebar.get_by_role('button',name='研究对话',exact=True).wait_for(timeout=30000)
        report['checks']['new_project_starts_in_chat']=page.locator('.dp-chat-pane').is_visible()
        report['checks']['no_complex_import_entry']=sidebar.get_by_role('button',name='导入项目',exact=True).count()==0
        report['checks']['only_creation_group']=sidebar.get_by_role('heading',name='创作',exact=True).count()==1 and sidebar.get_by_role('heading',name='资料',exact=True).count()==0
        report['checks']['merged_library_at_bottom']=sidebar.locator('.dp-sidebar-footer').get_by_role('button',name='文献与知识库',exact=True).count()==1
        # Drop over the chat pane, outside the small composer drop target.
        data=page.evaluate_handle("""()=>{const transfer=new DataTransfer();transfer.items.add(new File(['# Drop check\\nDROP_WORKFLOW_MARKER_20261102'],'drag-upload-check.md',{type:'text/markdown'}));return transfer}""")
        with page.expect_response(lambda response:'/attachments' in response.url and response.request.method=='POST',timeout=120000) as upload:
            page.locator('.dp-chat-pane').dispatch_event('drop',{'dataTransfer':data})
        assert upload.value.ok,upload.value.text();report['checks']['drop_anywhere_in_chat_saves_material']=True
        page.locator('.dp-attachment-hint').get_by_text('已保存',exact=False).wait_for(timeout=30000)
        canvas=Image.new('RGB',(180,100),(55,98,158));stream=io.BytesIO();canvas.save(stream,format='PNG');encoded=base64.b64encode(stream.getvalue()).decode()
        with page.expect_response(lambda response:'/attachments' in response.url and response.request.method=='POST',timeout=120000) as image_upload:
            page.evaluate("""encoded=>{const data=Uint8Array.from(atob(encoded),char=>char.charCodeAt(0));const transfer=new DataTransfer();transfer.items.add(new File([data],'paste-image-check.png',{type:'image/png'}));document.querySelector('.dp-chat-pane textarea').dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:transfer}))}""",encoded)
        assert image_upload.value.ok
        page.locator('.dp-composer-policy').get_by_text('paste-image-check.png',exact=False).first.wait_for()
        report['checks']['pasted_image_preview']=page.locator('.dp-composer-policy img').count()>0
        page.screenshot(path=str(ROOT/f'reports/screenshots/beginner-{mode}-uploads.png'))
        page.locator('.dp-composer-policy textarea').first.fill('查看这份图片和材料（界面发送验证，未送达服务器）')
        page.locator('.dp-composer-policy').get_by_role('button',name='发送',exact=True).click()
        page.locator('.dp-chat-image-previews img').wait_for(timeout=15000)
        report['checks']['sent_image_displays_inline']=True
        for _ in range(80):
            if turns:break
            page.wait_for_timeout(100)
        report['checks']['turn_contains_uploaded_knowledge_base']=bool(turns) and bool(turns[0].get('kb_names') or turns[0].get('knowledge_bases'))
        report['turn_payload_keys']=list(turns[0]) if turns else []
        page.screenshot(path=str(ROOT/f'reports/screenshots/beginner-{mode}-inline-image.png'))
        page.get_by_role('button',name='查看网页',exact=True).click();page.get_by_label('网页地址',exact=True).fill('https://example.com')
        page.locator('.dp-web-address').get_by_role('button',name='打开',exact=True).click()
        preview=page.get_by_role('region',name='网页预览');preview.wait_for()
        report['checks']['web_page_opens_in_chat']=preview.locator('iframe').get_attribute('src')=='https://example.com/'
        preview.get_by_role('button',name='阅读正文',exact=True).click()
        page.wait_for_function("document.querySelector('.dp-web-preview article')?.textContent.includes('Example Domain')",timeout=60000)
        report['checks']['public_web_text_reading']=True
        page.screenshot(path=str(ROOT/f'reports/screenshots/beginner-{mode}-web.png'))
        page.locator('.dt-viewer-panel[data-open="true"]').get_by_role('button',name='关闭查看器',exact=True).click()
        sidebar.get_by_role('button',name='文献与知识库',exact=True).click();page.locator('.knowledge-sources').wait_for()
        report['checks']['library_contains_kb_management']=True
        prefix='/research/api/projects/'+project['id']
        search=ctx.request.post(ORIGIN+prefix+'/knowledge/search',data={'query':'DROP_WORKFLOW_MARKER_20261102','mode':'fulltext-keyword','limit':3}).json()
        report['checks']['dropped_document_is_searchable']=bool(search['items'])
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(250)
        report['checks']['mobile_no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        report['checks']['no_script_errors']=not report['errors'];report['passed']=all(report['checks'].values())
        browser.close()
    (ROOT/f'reports/beginner-workflow-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));assert report['passed']

if __name__=='__main__':main()
