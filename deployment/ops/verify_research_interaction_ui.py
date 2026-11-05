"""Live-data UI acceptance for the library reference page and research-side recovery."""
import json,sys,time,mimetypes
from pathlib import Path
from urllib.parse import unquote,urlparse
from verify_research_overview import ROOT,OUT,DIST,ORIGIN
from verify_partner_workflow import account
from playwright.sync_api import sync_playwright


def main():
    published='--published' in sys.argv;label='published' if published else 'candidate'
    report={'build':json.loads((DIST/'build-info.json').read_text())['slurm_job_id'],'checks':{},'errors':[]}
    fixture=json.loads((OUT/'research-path-fixtures.json').read_text(encoding='utf8'))['hydration']
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1000})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account(),headers={'Origin':ORIGIN}).ok
        if not published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/(name or 'index.html');assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        events=[];sent=[]
        def observe(socket):
            def frame(data,rows):
                try:
                    event=json.loads(data)
                    # Capture public protocol metadata only, not hidden thought content.
                    if event.get('type') not in ('thinking','observation'):rows.append(event)
                except (ValueError,AttributeError):pass
            socket.on('framesent',lambda e:frame(e,sent));socket.on('framereceived',lambda e:frame(e,events))
        page.on('websocket',observe)
        try:
            pid='1ea03384007d4bb9b88d43e3368099f3';ws='ws_0e6fc7aba58a4b258e25e1195702fde3'
            url=ORIGIN+'/research/?project='+pid+'&dt_workspace='+ws+'&area=literature'
            page.goto(url,wait_until='domcontentloaded');page.locator('.library-data-table tbody tr').first.wait_for(timeout=60000)
            count=page.locator('.library-data-table tbody tr').count()
            report['checks']['real_library_rows']=count>0
            report['checks']['no_default_empty_detail']=page.locator('.bibliography-detail').count()==0
            report['checks']['one_heading_one_toolbar']=page.locator('.library-page-heading').count()==1 and page.locator('.library-list-toolbar').count()==1 and page.locator('.literature-folders').count()==0
            report['checks']['desktop_filters_share_one_row']=page.locator('.library-list-toolbar').bounding_box()['height']<60
            report['checks']['authors_are_condensed']=page.locator('.library-data-table .author-names').count()==0
            page.get_by_role('button',name='按年份排序').click()
            direction=page.locator('th[data-column="year"]').get_attribute('aria-sort')
            years=[int(v) if v.isdigit() else 0 for v in page.locator('tbody [data-column="year"]').all_text_contents()]
            report['checks']['table_sorting']=direction in ('ascending','descending') and years==sorted(years,reverse=direction=='descending')
            row=page.locator('.library-data-table tbody tr').first;row.focus();row.press('Enter');page.get_by_role('complementary',name='文献详细信息').wait_for()
            report['checks']['keyboard_opens_detail']=page.locator('.bibliography-detail h2').inner_text() in row.inner_text()
            page.get_by_role('button',name='关闭文献详情').click()
            page.get_by_label('筛选文献',exact=True).fill('NOT_A_PAPER_20261105')
            report['checks']['empty_filter_state']=page.get_by_text('没有匹配的文献',exact=True).is_visible()
            page.get_by_role('button',name='清除筛选',exact=True).first.click()
            page.get_by_role('button',name='文献库操作').click();page.get_by_role('menuitem',name='项目知识库',exact=True).click()
            report['checks']['accessible_library_menu']=page.locator('.knowledge-sources').is_visible()
            page.screenshot(path=str(OUT/f'library-components-{label}-desktop.png'))
            for width,height in [(1100,850),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(150)
                report['checks']['library_no_overflow_'+str(width)]=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1') and page.locator('.bibliography-scroll').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                page.screenshot(path=str(OUT/f'library-components-{label}-{width}.png'))
            page.set_viewport_size({'width':1440,'height':1000})
            # Use the real material copy; only conversational questions are created.
            url=ORIGIN+'/research/?project='+fixture['id']+'&dt_workspace='+fixture['native_id']
            page.goto(url,wait_until='domcontentloaded');page.locator('[data-research-task="interpret-3d"]').wait_for(timeout=60000)
            page.locator('.outline-updates summary').click()
            report['checks']['saved_correction_before_after_visible']=page.locator('.outline-updates').get_by_text('原记录',exact=True).count()>0 and page.locator('.outline-updates').get_by_text('更新为',exact=True).count()>0
            page.screenshot(path=str(OUT/f'research-correction-{label}.png'))
            page.locator('.outline-updates summary').click()
            page.locator('[data-research-task="interpret-3d"]').click();page.get_by_role('button',name='带着这个任务继续研究').click()
            composer=page.get_by_placeholder('继续当前研究任务…',exact=True);composer.wait_for(timeout=30000)
            prompt='这是研究交互验收。请实际调用ask_user，向我询问报告应先展示“原文依据”还是“结果边界”，给这两个选项，等待我的回答后用一句话说明选择。这是界面偏好，不改变研究主线；不要修改材料或提交计算。'
            composer.fill(prompt);composer.press('Enter')
            deadline=time.time()+240
            while time.time()<deadline:
                page.wait_for_timeout(500)
                if any(e.get('type')=='wait_for_input' for e in events) or page.get_by_text('需要你决定，回答后继续当前任务',exact=True).count():break
                if any(e.get('type') in ('error','protocol_error') for e in events):break
            turn=next((e.get('turn_id') for e in events if e.get('turn_id')),None)
            session=next((e.get('session_id') or e.get('metadata',{}).get('session_id') for e in events if e.get('session_id') or e.get('metadata',{}).get('session_id')),None)
            report['session_id']=session;report['turn_id']=turn
            report['checks']['assistant_ui_live_messages']=page.locator('.research-thread .research-user-message').count()>0
            report['checks']['material_quote_collapsed']=page.locator('.research-message-quote:not([open])').count()>0
            report['checks']['real_author_question']=page.get_by_text('需要你决定，回答后继续当前任务',exact=True).count()>0
            page.screenshot(path=str(OUT/f'research-assistant-{label}-waiting.png'))
            before=len([e for e in sent if e.get('type')=='start_turn'])
            page.reload(wait_until='domcontentloaded');page.locator('.research-thread').wait_for(timeout=60000)
            page.get_by_text('需要你决定，回答后继续当前任务',exact=True).wait_for(timeout=60000)
            report['checks']['refresh_resubscribes_same_turn']=any(e.get('type') in ('subscribe_turn','resume_from') and e.get('turn_id')==turn for e in sent) and len([e for e in sent if e.get('type')=='start_turn'])==before
            page.screenshot(path=str(OUT/f'research-assistant-{label}-restored.png'))
            # Native ask-user card controls remain the response authority.
            options=page.get_by_role('button',name='原文依据',exact=True)
            if options.count():options.first.click()
            else:page.get_by_text('原文依据',exact=True).last.click()
            submits=page.get_by_role('button',name='提交',exact=True)
            if submits.count() and submits.last.is_enabled():submits.last.click()
            else:
                for name in ['继续','发送回答','提交回答']:
                    candidate=page.get_by_role('button',name=name,exact=True)
                    if candidate.count() and candidate.last.is_enabled():candidate.last.click();break
            deadline=time.time()+180
            while time.time()<deadline:
                page.wait_for_timeout(500)
                if any(e.get('type')=='done' and e.get('turn_id')==turn for e in events):break
            report['checks']['answer_resumes_original_turn']=any(e.get('type')=='submit_user_reply' and e.get('turn_id')==turn for e in sent) and any(e.get('type')=='done' and e.get('turn_id')==turn and e.get('metadata',{}).get('status')=='completed' for e in events)
            report['checks']['one_composer']=page.locator('.dp-chat-pane .dt-viewer-panel textarea:visible').count()==1
            page.screenshot(path=str(OUT/f'research-assistant-{label}-completed.png'))
            event_start=len(events)
            composer=page.get_by_placeholder('继续当前研究任务…',exact=True)
            composer.fill('仅作停止按钮验收，不调用工具、不修改文件。请逐条写出100条研究记录管理建议，每条约40字。')
            page.locator('.dt-viewer-panel').get_by_role('button',name='发送',exact=True).click()
            deadline=time.time()+60
            cancel_turn=None
            while time.time()<deadline:
                page.wait_for_timeout(200)
                cancel_turn=next((e.get('turn_id') for e in events[event_start:] if e.get('turn_id') and e.get('turn_id')!=turn),None)
                if cancel_turn:break
            stop=page.get_by_role('button',name='停止生成',exact=True)
            if not stop.count():stop=page.get_by_role('button',name='Stop generating',exact=True)
            stop.click()
            deadline=time.time()+60
            while time.time()<deadline:
                page.wait_for_timeout(200)
                if any(e.get('type')=='done' and e.get('turn_id')==cancel_turn for e in events[event_start:]):break
            report['checks']['real_cancel_confirmed_by_execution']=bool(cancel_turn) and any(e.get('type')=='cancel_turn' and e.get('turn_id')==cancel_turn for e in sent) and any(e.get('type')=='done' and e.get('turn_id')==cancel_turn and e.get('metadata',{}).get('status')=='cancelled' for e in events[event_start:])
            report['checks']['cancelled_state_visible']=page.get_by_text('执行端已确认停止',exact=True).count()>0
            page.screenshot(path=str(OUT/f'research-assistant-{label}-cancelled.png'))
        except Exception as error:
            report['error']=str(error)
            report['visible_buttons']=page.locator('.dt-viewer-panel button:visible').evaluate_all('(els)=>els.map(e=>({label:e.getAttribute("aria-label"),text:e.innerText,disabled:e.disabled}))')
            report['sent_types']=[{'type':e.get('type'),'turn_id':e.get('turn_id')} for e in sent]
            report['received_statuses']=[{'type':e.get('type'),'turn_id':e.get('turn_id'),'status':e.get('metadata',{}).get('status'),'content':e.get('content') if e.get('type') in ('error','protocol_error') else None} for e in events if e.get('type') in ('done','error','protocol_error','session','wait_for_input')]
            page.screenshot(path=str(OUT/f'research-interaction-{label}-failure.png'))
        report['passed']=not report.get('error') and not report['errors'] and all(report['checks'].values())
        (OUT/f'research-interaction-ui-{label}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False));browser.close()
        assert report['passed'],report


if __name__=='__main__':main()
