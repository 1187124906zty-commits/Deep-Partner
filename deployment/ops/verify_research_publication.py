"""Verify installed UI and persisted live acceptance session without rerunning it."""
import json
from verify_research_overview import OUT,ORIGIN,DIST
from verify_partner_workflow import account
from playwright.sync_api import sync_playwright

qa=json.loads((OUT/'research-interaction-ui-candidate.json').read_text(encoding='utf8'))
fixture=json.loads((OUT/'research-path-fixtures.json').read_text(encoding='utf8'))['hydration']
report={'build':qa['build'],'checks':{},'errors':[],'live_execution_evidence':'research-interaction-ui-candidate.json'}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    ctx=browser.new_context(viewport={'width':1440,'height':1000})
    assert ctx.request.post(ORIGIN+'/api/auth/login',data=account(),headers={'Origin':ORIGIN}).ok
    page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.goto(ORIGIN+'/research/?project=1ea03384007d4bb9b88d43e3368099f3&dt_workspace=ws_0e6fc7aba58a4b258e25e1195702fde3&area=literature',wait_until='domcontentloaded')
    page.locator('.library-data-table tbody tr').first.wait_for(timeout=60000)
    expected=__import__('re').findall(r'(?:src|href)="(\./assets/[^" ]+)"',(DIST/'index.html').read_text())
    actual=page.content();report['checks']['served_current_built_assets']=bool(expected) and all(v in actual for v in expected)
    report['checks']['published_library_rows']=page.locator('.library-data-table tbody tr').count()==136
    report['checks']['published_compact_filters']=page.locator('.library-list-toolbar').bounding_box()['height']<60
    page.screenshot(path=str(OUT/'library-components-published-desktop.png'))
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150)
    report['checks']['published_mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=str(OUT/'library-components-published-390.png'));page.set_viewport_size({'width':1440,'height':1000})
    saved={'sessionId':qa['session_id'],'anchor':{'area':'research-outline','asset':'interpret-3d','title':'界定三维相场起裂结果的支持范围','locator':{},'quote':''}}
    ctx.add_init_script('sessionStorage.setItem('+json.dumps('deeppartner.research-side.'+fixture['id'])+','+json.dumps(json.dumps(saved,ensure_ascii=False))+')')
    page.goto(ORIGIN+'/research/?project='+fixture['id']+'&dt_workspace='+fixture['native_id']+'&research_session='+qa['session_id'],wait_until='domcontentloaded')
    page.locator('.research-thread .research-user-message').first.wait_for(timeout=60000)
    page.get_by_text('执行端已确认停止',exact=True).wait_for(timeout=30000)
    report['checks']['published_saved_conversation_restores']=page.locator('.research-user-message').count()==2
    report['checks']['published_terminal_cancel_survives_reload']=page.get_by_text('执行端已确认停止',exact=True).is_visible()
    page.screenshot(path=str(OUT/'research-assistant-published-restored.png'))
    page.goto(ORIGIN+'/research/?project=1ea03384007d4bb9b88d43e3368099f3&dt_workspace=ws_0e6fc7aba58a4b258e25e1195702fde3',wait_until='domcontentloaded')
    page.locator('.outline-mainline').wait_for(timeout=60000)
    report['checks']['published_mainline_and_hierarchy']=page.locator('[data-main-task]').count()==4
    page.screenshot(path=str(OUT/'research-outline-published-desktop.png'))
    report['passed']=all(report['checks'].values()) and not report['errors'];browser.close()
(OUT/'research-publication.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False));assert report['passed'],report
