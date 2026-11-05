"""Log into the updated native host and run one existing bibliography download."""
from pathlib import Path
import argparse,json,os,socket,subprocess,sys,time
import httpx
ROOT=Path(__file__).resolve().parents[1];NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
PID='638495c5ba024a93a305ff69b4658811'

def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--login-only',action='store_true');args=parser.parse_args()
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    config=json.loads((Path(os.environ['LOCALAPPDATA'])/'DeepPartner/config.json').read_text(encoding='utf8'))
    # Keep the user's active MCP bridge untouched: the real app already owns this port.
    with socket.create_connection(('127.0.0.1',config['bridge_port']),timeout=2):pass
    profile=NATIVE/'verification/download-autostart';profile.mkdir(exist_ok=True)
    config['workspace']=str(profile/'workspace');config['browser_port']=free_port()
    (profile/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf8')
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe'),'--headless-ui'],cwd=NATIVE/'dist',env=dict(os.environ,DEEP_PARTNER_HOME=str(profile)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',creationflags=0x08000000)
    report={'checks':{},'model_calls':0,'test_paper':None if args.login_only else 'Existing project reference: Adam: A method for stochastic optimization','new_job_id':None}
    try:
        line=child.stdout.readline()
        if not line:raise RuntimeError(child.stderr.read()[:700])
        bootstrap=json.loads(line)['url'];origin='/'.join(bootstrap.split('/')[:3]);headers={'Origin':origin}
        with httpx.Client(base_url=origin,headers=headers,timeout=80,follow_redirects=True) as client:
            client.get(bootstrap).raise_for_status();client.post('/api/auth/login',json=account).raise_for_status()
            before=client.get('/desktop/status').json();assert not before['bridge']['listening'],'The probe must not replace the active MCP bridge'
            report['worker_before_login']=before['downloads']
            started=client.post('/desktop/connect',json={});started.raise_for_status();connections=started.json();report['connections']=connections
            assert connections['downloads'].get('running'),connections
            report['checks']['login_starts_paired_download_worker']=True
            status_path=Path(config['download_worker']['device_config']).with_suffix('.status.json')
            for _ in range(60):
                health=json.loads(status_path.read_text()) if status_path.exists() else {}
                if health.get('state')=='idle':break
                time.sleep(.5)
            assert health.get('state')=='idle',health
            report['worker_pid']=health['pid'];report['checks']['local_worker_heartbeat']=True
            again=client.post('/desktop/connect',json={});again.raise_for_status()
            report['repeated_connection']=again.json()['downloads']
            report['checks']['repeated_login_keeps_same_worker']=again.json()['downloads'].get('pid')==health['pid']
            assert report['checks']['repeated_login_keeps_same_worker'],'Repeated login returned a different worker PID'
            if args.login_only:
                report['checks']['cold_start_after_worker_stopped']=not before['downloads'].get('running') and connections['downloads'].get('state')=='starting'
                report['passed']=all(report['checks'].values());assert report['passed'];return
            references=client.get('/research/api/projects/'+PID+'/literature/items').json()['references']
            entry=next(e for e in references if e.get('arxiv')=='1412.6980')
            queued=client.post('/research/api/projects/'+PID+'/literature/download-batch',json={'entries':[entry],'folder':'references'});queued.raise_for_status();batch=queued.json()
            if batch['items']:jid=batch['items'][0]['id']
            else:
                jobs=client.get('/research/api/projects/'+PID+'/jobs').json()['jobs'];jid=next(j['id'] for j in jobs if j['kind']=='literature-download' and j.get('result',{}).get('identifier')=='arXiv:1412.6980')
            report['new_job_id']=jid;report['download_was_newly_enqueued']=bool(batch['items']);print(json.dumps({'automatic_worker_pid':health['pid'],'download_job':jid},ensure_ascii=False),flush=True)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                jobs=client.get('/research/api/projects/'+PID+'/jobs').json()['jobs'];job=next(j for j in jobs if j['id']==jid)
                if job['status']=='completed':break
                if job['status']=='failed':raise RuntimeError(job['error'])
                time.sleep(2)
            else:raise RuntimeError('Automatic download did not finish within 180 seconds')
            result=job['result'];pdf=client.get('/research/api/projects/'+PID+'/literature/file',params={'asset':result['receipt']['name']});pdf.raise_for_status()
            import fitz
            with fitz.open(stream=pdf.content,filetype='pdf') as doc:pages=len(doc);assert pages>0
            assert result['transfer']['cluster_verified']
            report['checks']['completed_download_cluster_and_library_delivery']=True
            report['checks']['owned_pdf_readable']=True
            report['job']={'id':jid,'status':job['status'],'timeline':result['timeline'],'transfer':result['transfer'],'asset':result['receipt']['name'],'bytes':len(pdf.content),'pages':pages}
            report['passed']=all(report['checks'].values());assert report['passed']
    except Exception as e:report['passed']=False;report['failure']=str(e);raise
    finally:
        child.terminate();child.wait(timeout=10)
        path=ROOT/('reports/download-worker-reconnect.json' if args.login_only else 'reports/download-autostart.json')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
