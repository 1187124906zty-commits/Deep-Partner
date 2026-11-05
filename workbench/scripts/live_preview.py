"""Loopback preview of the deployed app using an isolated QA workspace.

The page, API and exports are the real workbench. This proxy holds only the
disposable QA account's session; real-account browser cookies are never read.
"""
from pathlib import Path
import mimetypes
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookiejar import CookieJar
import argparse,json,urllib.request,urllib.error,re

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--port',type=int,default=47901);args=p.parse_args()
config=json.loads(Path(args.config).read_text(encoding='utf8'))
ORIGIN='https://tutor.example.invalid'
jar=CookieJar();opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))
login=urllib.request.Request(ORIGIN+'/api/auth/login',data=json.dumps({'username':config['username'],'password':config['password']}).encode(),headers={'Origin':ORIGIN,'Content-Type':'application/json'})
with opener.open(login,timeout=30) as response:
    assert response.status==200,'QA account sign-in failed'

RELOAD="""<script>
let previewRevision='',previewInput=0;
document.addEventListener('input',()=>previewInput=Date.now());
document.addEventListener('pointerdown',()=>previewInput=Date.now());
setInterval(async()=>{try{const v=await(await fetch('/__preview/revision',{cache:'no-store'})).text();
const active=document.activeElement;const editing=document.querySelector('[role=dialog],.figure-studio')||active?.isContentEditable||['INPUT','TEXTAREA'].includes(active?.tagName);
if(previewRevision&&v!==previewRevision&&Date.now()-previewInput>8000&&!editing)location.reload();
else if(!previewRevision)previewRevision=v;}catch{}},2200);
</script>"""

class Proxy(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.forward()
    def do_POST(self):self.forward()
    def do_PUT(self):self.forward()
    def do_PATCH(self):self.forward()
    def do_DELETE(self):self.forward()
    def forward(self):
        if self.path=='/__preview/revision':
            marker=ROOT/'build/preview-revision.json'
            data=str(marker.stat().st_mtime_ns if marker.exists() else 0).encode()
            self.send_response(200);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data);return
        path=self.path.split('?',1)[0]
        reader_asset=re.fullmatch(r'/research/reader/([a-f0-9]{32})/(assets/.*|pdf-assets/.*|samples/.*)',path)
        if self.command=='GET' and reader_asset:
            root=ROOT/'vendor/neoread-web';file=(root/reader_asset[2]).resolve()
            if not file.is_relative_to(root.resolve()) or not file.is_file():self.send_error(404);return
            data=file.read_bytes();kind=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            if any(t in kind for t in ('javascript','text/','json','svg')):
                prefix='/research/reader/'+reader_asset[1]
                text=data.decode('utf8').replace('return"/"+','return"'+prefix+'/"+')
                text=text.replace('this.links.setViewer(this.viewer)','window.__workbenchReader=this,this.links.setViewer(this.viewer)')
                text=text.replace('maxCanvasPixels:4*1024*1024,maxCanvasDim:4096','maxCanvasPixels:16*1024*1024,maxCanvasDim:8192')
                data=re.sub(r'(?P<q>[\"\'`(])/(?P<part>api/|pub/|assets/|pdf-assets/|samples/)',lambda m:m['q']+prefix+'/'+m['part'],text).encode('utf8')
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data);return
        if self.command=='GET' and (path in ['/research','/research/'] or path.startswith('/research/assets/')):
            assets=ROOT/'build/preview-static'
            relative='index.html' if path in ['/research','/research/'] else path.removeprefix('/research/')
            file=(assets/relative).resolve()
            if not file.is_relative_to(assets.resolve()) or not file.is_file():self.send_error(404);return
            data=file.read_bytes()
            if relative=='index.html':data=data.replace(b'</head>',RELOAD.encode()+b'</head>')
            self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data);return
        if self.path=='/':
            self.send_response(302);self.send_header('Location','/research/');self.end_headers();return
        if not self.path.startswith(('/research','/api/knowledge-bases')):
            self.send_response(302);self.send_header('Location',ORIGIN+self.path);self.end_headers();return
        size=int(self.headers.get('Content-Length','0'))
        if size>256*1024*1024:self.send_error(413);return
        body=self.rfile.read(size) if size else None
        headers={'Origin':ORIGIN,'Accept-Encoding':'identity','Cookie':'; '.join(c.name+'='+c.value for c in jar)}
        for name in ['Content-Type','Range','If-Range']:
            if self.headers.get(name):headers[name]=self.headers[name]
        request=urllib.request.Request(ORIGIN+self.path,data=body,headers=headers,method=self.command)
        try:
            for attempt in range(3 if self.command=='GET' else 1):
                try:
                    try:response=opener.open(request,timeout=35)
                    except urllib.error.HTTPError as error:response=error
                    if response.headers.get('Content-Type','').startswith('text/event-stream'):
                        self.send_response(response.status);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.end_headers()
                        try:
                            while True:
                                line=response.readline()
                                if not line:break
                                self.wfile.write(line);self.wfile.flush()
                        except (BrokenPipeError,ConnectionResetError):pass
                        finally:response.close()
                        return
                    data=response.read();break
                except (OSError,TimeoutError):
                    if attempt==(2 if self.command=='GET' else 0):raise
            kind=response.headers.get('Content-Type','')
            if kind.startswith('text/html') and self.path.rstrip('/')=='/research':data=data.replace(b'</head>',RELOAD.encode()+b'</head>')
            self.send_response(response.status)
            for name in ['Content-Type','Content-Disposition','Content-Range','Accept-Ranges']:
                if response.headers.get(name):self.send_header(name,response.headers[name])
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        except (OSError,TimeoutError):self.send_error(502,'Preview upstream unavailable')

print('Live research workbench preview: http://127.0.0.1:'+str(args.port)+'/research/',flush=True)
ThreadingHTTPServer(('127.0.0.1',args.port),Proxy).serve_forever()
