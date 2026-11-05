"""Verify the cluster-built Windows client with its actual system proxy rules."""
from pathlib import Path
import argparse,json,os,socket,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login
from verify_workspace_interactions import geometry


def port():
    with socket.socket() as listener:listener.bind(('127.0.0.1',0));return listener.getsockname()[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--window',action='store_true');parser.add_argument('--build-report',type=Path,default=ROOT/'reports/cluster-native-build.json');args=parser.parse_args()
    build=json.loads(args.build_report.read_text(encoding='utf8'))
    release=Path(build['local_release']);executable=release/'Deep partner.exe';assert executable.is_file()
    profile=NATIVE/'verification/remote-native-latency';profile.mkdir(exist_ok=True)
    config={'server_url':'https://tutor.example.invalid','workspace':str(profile/'workspace'),'bridge_port':port(),'browser_port':port(),'cpu_workers':2,'ssh_host':'isolated-ui-qa.invalid','cluster_host':'','desktop_control':False}
    (profile/'config.json').write_text(json.dumps(config),encoding='utf8')
    debug=port()
    environment={key:value for key,value in os.environ.items() if key.lower() not in ('http_proxy','https_proxy','all_proxy','no_proxy')}
    environment['DEEP_PARTNER_HOME']=str(profile)
    if args.window:environment['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']='--remote-debugging-port='+str(debug)
    child=subprocess.Popen([str(executable)]+([] if args.window else ['--headless-ui']),cwd=release,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
    report={'mode':'cluster_built_windows_binary_real_system_proxy','checks':{},'process_proxy_environment_removed':True,'model_calls':0,'native_job_id':build['job_id'],'frontend_job_id':build['build']['frontend']['slurm_job_id'],'errors':[]}
    try:
        if not args.window:
            info=json.loads(child.stdout.readline());url=info['url'];origin='/'.join(url.split('/')[:3]);report['origin']=origin
        else:
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                try:
                    with urllib.request.urlopen('http://127.0.0.1:'+str(debug)+'/json/version',timeout=1) as response:json.load(response)
                    break
                except OSError:time.sleep(.25)
            else:raise RuntimeError('Packaged WebView2 did not expose its verification endpoint')
        with sync_playwright() as p:
            if args.window:
                browser=p.chromium.connect_over_cdp('http://127.0.0.1:'+str(debug));context=browser.contexts[0];page=context.pages[0];page.wait_for_function("() => location.hostname==='127.0.0.1'",timeout=45000);origin=page.evaluate('location.origin');report['origin']=origin;report['actual_packaged_webview2']=True
            else:
                browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
                context=browser.new_context(viewport={'width':1280,'height':850},extra_http_headers={'Origin':origin});context.request.get(url);page=context.new_page()
            class Client:
                def post(self,path,json=None):
                    start=time.perf_counter();response=context.request.post(origin+path,data=json,headers={'Origin':origin},timeout=45000);report['login_ms']=round((time.perf_counter()-start)*1000,1)
                    class Result:
                        def raise_for_status(self):assert response.ok,response.text()[:200]
                    return Result()
            login(Client());report['checks']['http_works_using_existing_system_proxy_without_process_override']=True
            start=time.perf_counter();response=context.request.get(origin+'/research/api/bootstrap',headers={'Origin':origin},timeout=30000);assert response.ok,response.text()[:200];bootstrap=response.json();report['bootstrap_ms']=round((time.perf_counter()-start)*1000,1)
            project=next(p for p in bootstrap['projects'] if p['name']=='水分扩散');base=origin+'/?project='+project['id']+'&dt_workspace='+project['native_id']
            report['checks']['same_cluster_frontend_is_bundled']=context.request.get(origin+'/build-info.json',headers={'Origin':origin}).json()['slurm_job_id']==report['frontend_job_id']
            report['checks']['credentials_are_not_webview_cookies']=all(cookie['name'] not in ('dt_token','__Host-dt_trusted','__Host-dt_pair') for cookie in context.cookies())
            page.on('pageerror',lambda error:report['errors'].append(str(error)))
            start=time.perf_counter();page.goto(base+'&area=literature',wait_until='domcontentloaded');page.locator('.bibliography-table tbody tr').first.wait_for(timeout=45000);report['library_ready_ms']=round((time.perf_counter()-start)*1000,1)
            websocket=page.evaluate("""workspace=>new Promise(resolve=>{const url=new URL('/ws',location.href);url.protocol='ws:';url.searchParams.set('dt_workspace',workspace);const start=performance.now(),socket=new WebSocket(url);let opened=false;socket.onopen=()=>{opened=true;setTimeout(()=>{const value={opened,readyState:socket.readyState,openMs:Math.round(performance.now()-start-600)};socket.close();resolve(value)},600)};socket.onerror=()=>{};socket.onclose=event=>{if(!opened)resolve({opened:false,code:event.code})};setTimeout(()=>{if(!opened){socket.close();resolve({opened:false,timeout:true})}},15000)})""",project['native_id'])
            report['websocket']=websocket;report['checks']['authenticated_realtime_websocket_uses_existing_proxy']=websocket.get('opened') and websocket.get('readyState')==1
            stream=page.evaluate("""pid=>new Promise(resolve=>{const start=performance.now(),source=new EventSource('/research/api/projects/'+pid+'/jobs/events');source.addEventListener('jobs',event=>{const value=JSON.parse(event.data);source.close();resolve({milliseconds:Math.round(performance.now()-start),count:value.jobs.length})});setTimeout(()=>{source.close();resolve({timeout:true})},12000)})""",project['id'])
            report['progress_stream']=stream;report['checks']['live_progress_is_forwarded_without_proxy_buffering']=not stream.get('timeout') and stream.get('count',0)>0
            report['geometry']=[]
            for area in ['literature','paper','figures','code','slides','questions']:
                page.goto(base+'&area='+area,wait_until='domcontentloaded');page.locator('.dp-artifacts').wait_for(timeout=45000);page.wait_for_timeout(500);value=geometry(page);value['area']=area;report['geometry'].append(value)
            report['checks']['six_native_pages_keep_layout']=all(not value['horizontal_page_overflow'] and not value['toolbar_overlaps'] for value in report['geometry'])
            if args.window:
                page.goto(base+'&area=literature',wait_until='domcontentloaded');page.locator('.bibliography-table tbody tr').first.wait_for(timeout=45000);page.screenshot(path=str(ROOT/'reports/screenshots/restored-native-window.png'))
            report['checks']['no_native_page_errors']=not report['errors'];report['passed']=all(report['checks'].values());browser.close()
    except Exception as error:
        report['passed']=False;report['failure']=type(error).__name__+': '+str(error);raise
    finally:
        (ROOT/'reports'/('native-responsiveness-window.json' if args.window else 'native-responsiveness.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
        if child.poll() is None:child.terminate();child.wait(timeout=10)


if __name__=='__main__':main()
