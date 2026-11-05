"""Exercise the research view on real records, preserving scientific project data."""
from pathlib import Path
from urllib.parse import unquote,urlparse
import argparse,json,mimetypes,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
OUT=ROOT/'reports/agentic-product';ORIGIN='https://tutor.example.invalid'
PID='2f8ed851ef2744d9a248a4dca6e9133e';WS='ws_adf57dc14a824d72aedc6eb241cd4758'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');parser.add_argument('--live-turn',action='store_true');parser.add_argument('--evidence-only',action='store_true');args=parser.parse_args()
    mode='live' if args.published else 'candidate'
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,timeout=35))
    report={'checks':{},'errors':[],'mode':mode,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1000})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        if not args.published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/(name or 'index.html');assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        sent=[];received=[]
        def observe(socket):
            def frame(data,target):
                try:
                    value=json.loads(data)
                    if isinstance(value,dict):target.append(value)
                except (ValueError,TypeError):pass
            socket.on('framesent',lambda data:frame(data,sent));socket.on('framereceived',lambda data:frame(data,received))
        page.on('websocket',observe)
        url=ORIGIN+'/research/?project='+PID+'&dt_workspace='+WS
        try:
            page.goto(url,wait_until='domcontentloaded');page.get_by_role('tab',name='研究记录与证据').click(timeout=60000);page.locator('.research-strand-findings [data-research-node]').first.wait_for(timeout=60000)
            view=ctx.request.get(ORIGIN+'/research/api/projects/'+PID+'/research-overview').json()
            report['checks']['project_defaults_to_overview']=page.locator('.research-overview').is_visible() and not page.locator('.dp-chat-pane').is_visible()
            report['checks']['actual_findings_visible']=next(s['count'] for s in view['sections'] if s['id']=='findings')>0
            report['checks']['author_questions_prioritized']=all(j['status']=='waiting_input' for j in view['attention'][:2])
            page.screenshot(path=str(OUT/f'research-overview-{mode}-desktop.png'))
            row=page.locator('.research-strand-findings [data-research-node]').first;node_id=row.get_attribute('data-research-node');row.click()
            dialog=page.get_by_role('dialog',name='研究记录详情');dialog.wait_for()
            record=next(n for s in view['sections'] for n in s['items'] if n['id']==node_id)
            report['checks']['detail_has_actual_record']=record['label'] in dialog.inner_text()
            link=dialog.locator('a').first;source=ctx.request.get(ORIGIN+link.get_attribute('href'))
            report['checks']['record_source_opens']=source.ok
            report['checks']['record_relationship_visible']=dialog.locator('.research-related button').count()>0
            page.screenshot(path=str(OUT/f'research-overview-{mode}-evidence.png'))
            dialog.get_by_role('button',name='带着这条记录继续讨论').click()
            draft=page.get_by_placeholder('继续当前研究任务…',exact=True);draft.wait_for(timeout=30000)
            report['checks']['overview_stays_beside_discussion']=page.locator('.research-overview').is_visible() and page.locator('.dp-chat-pane').is_visible()
            report['checks']['selected_record_in_discussion']=record['label'] in page.locator('.dp-dito-location').inner_text()
            page.wait_for_timeout(600)
            pane=page.locator('.dp-chat-pane').bounding_box();panel=page.locator('.dp-chat-pane .dt-viewer-panel').bounding_box()
            report['checks']['discussion_fills_assistant_pane']=abs(panel['x']-pane['x'])<3 and abs(panel['width']-pane['width'])<3
            page.screenshot(path=str(OUT/f'research-overview-{mode}-discussion.png'))
            if args.live_turn:
                prompt='请只依据随附的这条研究记录及其已标明的来源，说明它支持什么、还不能支持什么，最多150字。不执行工具，不修改或归档项目材料。'
                draft.fill(prompt);page.get_by_placeholder('继续当前研究任务…',exact=True).press('Enter')
                deadline=time.time()+240
                while time.time()<deadline:
                    page.wait_for_timeout(1000)
                    if any(x.get('type') in ('turn_complete','turn_completed','done','completed') for x in received):break
                    if any(x.get('type') in ('protocol_error','error') for x in received):break
                report['live_turn']={'session_id':next((x.get('session_id') for x in received if x.get('session_id')),None),'turn_id':next((x.get('turn_id') for x in received if x.get('turn_id')),None),'sent_types':list(dict.fromkeys(x.get('type','') for x in sent)),'received_types':list(dict.fromkeys(x.get('type','') for x in received)),'visible_reply':page.locator('.dp-chat-pane').inner_text()[-3000:]}
                report['live_turn']['request_contains_record']=any(record['id'] in json.dumps(x,ensure_ascii=False) or '当前位置.md' in json.dumps(x,ensure_ascii=False) for x in sent)
                report['checks']['actual_research_reply_received']=any(x.get('type')=='done' and x.get('metadata',{}).get('status')=='completed' for x in received) and not any(x.get('type') in ('protocol_error','error') for x in received)
                page.screenshot(path=str(OUT/'research-overview-live-response.png'))
            page.get_by_role('button',name='收起助手',exact=True).click()
            page.get_by_role('button',name='记下问题',exact=True).click();page.get_by_role('textbox',name='研究问题',exact=True).fill('仅检查编辑入口，不保存研究问题')
            page.locator('.research-focus').get_by_role('button',name='取消',exact=True).click()
            report['checks']['question_edit_can_cancel']='仅检查编辑入口' not in page.locator('.research-focus').inner_text()
            for width,height in [(1100,850),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.locator('.research-overview').evaluate('(e)=>e.scrollTop=0');page.wait_for_timeout(300)
                report['checks'][f'no_horizontal_overflow_{width}']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1') and page.locator('.research-overview').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                page.screenshot(path=str(OUT/f'research-overview-{mode}-{width}.png'))
            page.set_viewport_size({'width':1440,'height':1000})
            for theme in ['dark','snow','glass']:
                page.evaluate('(theme)=>localStorage.setItem("deeptutor-theme",theme)',theme);page.reload(wait_until='domcontentloaded');page.get_by_role('tab',name='研究记录与证据').click(timeout=30000);page.locator('.research-strand-findings [data-research-node]').first.wait_for(timeout=30000)
                report['checks']['theme_'+theme]=page.locator('.research-overview').is_visible()
                page.screenshot(path=str(OUT/f'research-overview-{mode}-{theme}.png'))
            if not args.evidence_only:
                outline_pid='1ea03384007d4bb9b88d43e3368099f3';outline_ws='ws_0e6fc7aba58a4b258e25e1195702fde3'
                outline_url=ORIGIN+'/research/?project='+outline_pid+'&dt_workspace='+outline_ws
                page.evaluate('localStorage.setItem("deeptutor-theme","light")')
                page.goto(outline_url,wait_until='domcontentloaded');page.locator('.outline-mainline h2').wait_for(timeout=60000)
                outline_state=ctx.request.get(ORIGIN+'/research/api/projects/'+outline_pid+'/research-outline').json();proposal=outline_state['draft'] or outline_state['active']
                report['checks']['mainline_matches_actual_synthesis']=page.locator('.outline-mainline h2').inner_text()==proposal['mainline']['title']
                report['checks']['hierarchy_has_actual_main_tasks']=page.locator('[data-main-task]').count()==len(proposal['outline'])
                report['checks']['actual_rag_retrieval_used']=any(r.get('knowledge_base') and r['status']=='completed' and r['source_count']>0 for r in proposal['retrieval'])
                report['checks']['actual_conversation_context_used']=len(proposal['coverage']['conversations'])>0
                page.screenshot(path=str(OUT/f'research-outline-{mode}-desktop.png'))
                first=proposal['outline'][0]['tasks'][0]
                page.locator('[data-research-task="'+first['id']+'"]').click()
                detail=page.get_by_role('complementary',name='细节任务与进展');detail.wait_for()
                report['checks']['task_purpose_and_next_step']=first['why'] in detail.inner_text() and first['next_step'] in detail.inner_text()
                page.screenshot(path=str(OUT/f'research-outline-{mode}-task.png'))
                detail.get_by_role('button',name='带着这个任务继续研究').click();page.get_by_placeholder('继续当前研究任务…',exact=True).wait_for(timeout=30000)
                report['checks']['mainline_and_task_carried_to_discussion']=first['title'] in page.get_by_placeholder('继续当前研究任务…',exact=True).input_value()
                page.wait_for_timeout(600);pane=page.locator('.dp-chat-pane').bounding_box();panel=page.locator('.dp-chat-pane .dt-viewer-panel').bounding_box()
                report['checks']['one_native_research_composer']=page.locator('.dp-chat-pane .dt-viewer-panel textarea:visible').count()==1 and not page.locator('.dp-chat-pane .dt-viewer-panel .dp-writing-toolbar').is_visible()
                report['checks']['hierarchy_discussion_fills_pane']=abs(panel['x']-pane['x'])<3 and abs(panel['width']-pane['width'])<3
                page.screenshot(path=str(OUT/f'research-outline-{mode}-discussion.png'))
                page.get_by_role('button',name='收起助手',exact=True).click()
                page.locator('.outline-mainline .outline-source-chips button').first.click();source_dialog=page.get_by_role('dialog',name='大纲依据');source_dialog.wait_for()
                report['checks']['outline_source_excerpt_available']=len(source_dialog.locator('.outline-source-text').inner_text())>40
                report['checks']['outline_source_link_available']=source_dialog.locator('a').count()>0
                page.screenshot(path=str(OUT/f'research-outline-{mode}-source.png'));page.get_by_role('button',name='关闭大纲依据').click()
                for width,height in [(1100,850),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height});page.locator('.research-overview').evaluate('(e)=>e.scrollTop=0');page.wait_for_timeout(200)
                    report['checks'][f'outline_no_overflow_{width}']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1') and page.locator('.research-overview').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                    page.screenshot(path=str(OUT/f'research-outline-{mode}-{width}.png'))
                after=ctx.request.get(ORIGIN+'/research/api/projects/'+outline_pid+'/research-outline').json()
                report['checks']['proposal_not_adopted_by_inspection']=after['revision']==outline_state['revision'] and bool(after['active'])==bool(outline_state['active'])
                page.set_viewport_size({'width':1440,'height':1000})
            page.goto(url+'&view=workflow',wait_until='domcontentloaded');page.get_by_role('main',name='项目工作流').wait_for(timeout=30000)
            report['checks']['workflow_remains_accessible']=page.get_by_role('main',name='项目工作流').is_visible()
            page.goto(url+'&view=chat',wait_until='domcontentloaded');page.locator('.dp-chat-pane').wait_for(timeout=30000)
            report['checks']['explicit_chat_route']=page.locator('.dp-chat-pane').is_visible() and page.locator('.research-overview').count()==0
        except Exception as error:
            report['errors'].append(str(error));page.screenshot(path=str(OUT/f'research-overview-{mode}-failure.png'))
        report['passed']=all(report['checks'].values()) and not report['errors']
        (OUT/f'research-overview-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False));browser.close();assert report['passed'],report


if __name__=='__main__':main()
