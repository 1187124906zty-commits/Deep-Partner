"""Independent process guardian for the installed research tools, with real health."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
import argparse,asyncio,json,os,secrets,socket,sys,threading,time,uuid
from runtime_connection import http_json,spawn

ROOT=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'deep-partner/tool-runtime'
PORT=47908
LOCK=threading.Lock()
STATE={'ok':True,'version':1,'services':{},'pid':os.getpid(),'instance_id':uuid.uuid4().hex,'started':time.time()}


def check_native():
    from deepcode_native import rpc
    asyncio.run(rpc('thread/list',{'limit':1}))
    return {'ready':True,'protocol':'official native RPC'}


def recover_all(kind='all'):
    from tool_runtime import ensure as tools
    from search_runtime import restore as scholar
    from download_runtime import restore as scansci
    actions={'tools':tools,'scholar':scholar,'scansci':scansci,'deepcode':check_native}
    if kind not in ('all','search','survey','download','analyze','code','slides','simulate'):raise ValueError('Unknown tool route')
    selected=list(actions) if kind=='all' else ['tools']+(['scholar'] if kind in ('search','survey') else [])+(['scansci'] if kind in ('download','survey') else [])+(['deepcode'] if kind=='code' else [])
    def one(name):
        try:return name,actions[name]()
        except Exception as error:return name,{'ready':False,'reason':type(error).__name__,'retryable':True}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=dict(pool.map(one,selected))
    with LOCK:
        STATE['services'].update(results);STATE['updated']=time.time();STATE['ready']=all(row.get('ready') for row in STATE['services'].values())
        ROOT.mkdir(parents=True,exist_ok=True)
        temporary=ROOT/'supervisor-status.pending';temporary.write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(ROOT/'supervisor-status.json')
    return results


def ensure():
    try:
        health=http_json(f'http://127.0.0.1:{PORT}/health')
        if health.get('version')==1:return {'ready':True,'pid':health.get('pid'),'reused':True}
    except (OSError,ValueError):pass
    ROOT.mkdir(parents=True,exist_ok=True)
    python=Path(sys.executable)
    if os.name=='nt' and python.with_name('pythonw.exe').is_file():python=python.with_name('pythonw.exe')
    process=spawn([str(python),'-X','utf8',__file__,'--watch'],ROOT,'supervisor')
    (ROOT/'supervisor-process.json').write_text(json.dumps({'pid':process.pid}),encoding='utf8')
    for _ in range(30):
        try:
            value=http_json(f'http://127.0.0.1:{PORT}/health')
            return {'ready':True,'pid':value.get('pid'),'reused':False}
        except (OSError,ValueError):time.sleep(.1)
    return {'ready':False,'reason':'supervisor_start_pending'}


def watch():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path!='/health':self.send_error(404);return
            with LOCK:data=json.dumps(STATE).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError:return # The original guardian still owns its listener.
    threading.Thread(target=server.serve_forever,daemon=True).start()
    while True:
        recover_all();time.sleep(20)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--ensure',action='store_true');p.add_argument('--kind',default='all');args=p.parse_args()
    if args.watch:watch()
    elif args.ensure:print(json.dumps(ensure()))
    else:print(json.dumps({'supervisor':ensure(),'services':recover_all(args.kind)},ensure_ascii=False))
