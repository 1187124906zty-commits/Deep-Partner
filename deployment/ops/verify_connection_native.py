"""Open the owner's real desktop, check login connections and a real short turn."""
from pathlib import Path
import json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1];NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from verify_connection_previews import exercise

def main():
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe')],cwd=NATIVE/'dist',env=dict(os.environ,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9257'))
    report={'checks':{},'errors':[],'desktop_pid':child.pid,'model_calls':0}
    with sync_playwright() as p:
        for _ in range(80):
            try:urllib.request.urlopen('http://127.0.0.1:9257/json/version',timeout=1).close();break
            except OSError:time.sleep(.25)
        browser=p.chromium.connect_over_cdp('http://127.0.0.1:9257');ctx=browser.contexts[0];page=ctx.pages[0]
        try:
            page.wait_for_url('http://127.0.0.1:*/**');origin='/'.join(page.url.split('/')[:3]);headers={'Origin':origin}
            assert ctx.request.post(origin+'/api/auth/login',data=account,headers=headers).ok
            projects=ctx.request.get(origin+'/research/api/projects',headers=headers).json()['projects']
            water=next(x for x in projects if x['name']=='水分扩散')
            href=origin+'/?project='+water['id']+'&dt_workspace='+water['native_id']
            page.goto(href,wait_until='domcontentloaded');page.locator('.dp-composer-policy textarea').wait_for(timeout=30000)
            report['build']=ctx.request.get(origin+'/build-info.json',headers=headers).json()
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                status=ctx.request.get(origin+'/desktop/status',headers=headers).json()
                if status.get('connections',{}).get('cluster',{}).get('connected') and status['bridge'].get('connected'):break
                page.wait_for_timeout(600)
            report['connections']=status.get('connections',{});report['bridge']=status['bridge']
            report['checks']['login_autoloads_models']=report['connections'].get('models_loaded') is True
            report['checks']['login_restores_computer_bridge']=status['bridge'].get('connected') is True
            report['checks']['login_connects_configured_cluster']=report['connections'].get('cluster',{}).get('connected') is True
            print(json.dumps({'connections_ready':report['connections'],'bridge':report['bridge']},ensure_ascii=False),flush=True)
            assert all(report['checks'].values()),report
            page.on('pageerror',lambda e:report['errors'].append(str(e)))
            exercise(ctx,page,origin,projects,report,'native')
            page.goto(href,wait_until='domcontentloaded');page.locator('.dp-composer-policy textarea').wait_for(timeout=30000)
            page.get_by_role('button',name='新会话',exact=True).first.click()
            frames=[];sent=[]
            def socket_opened(socket):
                def received(raw):
                    try:
                        event=json.loads(raw);frames.append({'type':event.get('type'),'turn_id':event.get('turn_id'),'session_id':event.get('session_id'),'error':event.get('content') if event.get('type')=='error' else None})
                    except (ValueError,TypeError):pass
                def sent_frame(raw):
                    try:
                        event=json.loads(raw)
                        if event.get('type')=='start_turn':sent.append({k:event.get(k) for k in ['type','workspace_id','llm_selection']})
                    except (ValueError,TypeError):pass
                socket.on('framereceived',received);socket.on('framesent',sent_frame)
            # Recreate the socket after attaching its observer.
            page.on('websocket',socket_opened);page.reload(wait_until='domcontentloaded');page.locator('.dp-composer-policy textarea').wait_for(timeout=30000)
            marker='DP_CONNECTION_OK_20261102'
            page.locator('.dp-composer-policy textarea').fill('本次只验证软件连接。不要调用工具，不读写文件。请原样回复以下两行，中间保留空行：\n'+marker+'\n\n[项目说明](/research/api/projects/'+water['id']+'/file?path=README.md)')
            page.locator('.dp-composer-policy').get_by_role('button',name='发送',exact=True).click();report['model_calls']=1
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                if any(e['type']=='done' for e in frames):break
                if any(e['type']=='error' for e in frames):raise RuntimeError('Real turn failed: '+str([e for e in frames if e['type']=='error']))
                page.wait_for_timeout(700)
            else:raise RuntimeError('The real desktop turn did not finish within 240 seconds')
            session=page.evaluate("new URL(location.href).searchParams.get('session')")
            assert session,'A successful first turn must become a recoverable session'
            saved=ctx.request.get(origin+'/api/sessions/'+session+'?dt_workspace='+water['native_id'],headers=headers);assert saved.ok
            assistant=next((m for m in saved.json().get('messages',[]) if m.get('role')=='assistant' and marker in str(m.get('content',''))),None)
            assert assistant,'Assistant marker missing from the saved conversation'
            report['checks']['real_model_reply_saved']=True
            report['checks']['turn_uses_project_scope']=bool(sent) and sent[-1]['workspace_id']==water['native_id']
            report['checks']['turn_uses_account_model']=bool(sent) and bool(sent[-1]['llm_selection'] or ctx.request.get(origin+'/api/settings/llm-options',headers=headers).json().get('active'))
            report['stream']={'session_id':session,'events':frames,'request':sent,'marker':marker}
            ctx.request.patch(origin+'/api/sessions/'+session+'?dt_workspace='+water['native_id'],data={'title':'连接验证 · 可删除'},headers=headers)
            page.reload(wait_until='domcontentloaded');page.locator('.dp-chat-pane').get_by_text(marker,exact=True).first.wait_for(timeout=30000)
            report['checks']['reloaded_session_keeps_reply']=True
            page.locator('.dp-chat-pane').get_by_role('link',name='项目说明',exact=True).click()
            page.wait_for_function("() => document.querySelector('.dt-viewer-panel')?.textContent.includes('Mois-Net 水分扩散测试项目')",timeout=20000)
            report['checks']['actual_assistant_file_link_opens_sidebar']=True
            page.screenshot(path=str(ROOT/'reports/screenshots/connection-native-generated-file.png'))
            page.locator('.dt-viewer-panel[data-open="true"]').get_by_role('button',name='关闭查看器',exact=True).click()
            page.get_by_role('button',name='新会话',exact=True).first.click();page.wait_for_timeout(400)
            report['checks']['new_session_after_real_turn_is_empty']=page.get_by_text(marker,exact=True).count()==0
            report['checks']['no_script_errors']=not report['errors']
            report['passed']=all(report['checks'].values())
            page.screenshot(path=str(ROOT/'reports/screenshots/connection-native-ready.png'))
            assert report['passed']
        except Exception as e:
            report['passed']=False;report['failure']=str(e)
            page.screenshot(path=str(ROOT/'reports/screenshots/connection-native-failure.png'))
            (ROOT/'reports/connection-native-body.txt').write_text(page.locator('body').inner_text(),encoding='utf8')
            raise
        finally:
            (ROOT/'reports/connection-previews-native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(report,ensure_ascii=False),flush=True)
    # Keep the repaired app open for its owner.

if __name__=='__main__':main()
