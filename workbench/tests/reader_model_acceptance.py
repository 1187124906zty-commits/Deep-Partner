"""Exercise the real HTTP model adapters with deterministic local responses."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import HTTPServer,BaseHTTPRequestHandler
import asyncio,json,os
import httpx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from server import app as module
from server.storage import Store
from server.figures import register
from server.neoreader import instances

received=[]
class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));received.append(body)
        assert self.headers['Authorization']=='Bearer fixture-only'
        assert body['model']=='fixture'
        user=body['messages'][-1]['content']
        try:input_data=json.loads(user) if isinstance(user,str) else {}
        except Exception:input_data={}
        result=json.dumps({'message':'标题已调为 14 pt。','changes':{'objects':{'ax0-title':{'font_size':14}}}},ensure_ascii=False) if 'request' in input_data else '{"id":"p1-b1","text":"守恒通量"}'
        if body.get('stream'):
            data=('data: '+json.dumps({'choices':[{'delta':{'content':result}}]},ensure_ascii=False)+'\n\ndata: [DONE]\n\n').encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
        else:
            data=json.dumps({'choices':[{'message':{'content':result}}]},ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

server=HTTPServer(('127.0.0.1',0),Fixture);Thread(target=server.serve_forever,daemon=True).start();checks=[]
try:
    with TemporaryDirectory() as temp:
        root=Path(temp);module.store=Store(root/'store');module.api_path=lambda owner:root/'settings.json';module.schedule_review_summary=lambda *a:None
        module.api_path('fixture').write_text(json.dumps({'base_url':'http://127.0.0.1:'+str(server.server_port)+'/v1','api_key':'fixture-only','model':'fixture'}))
        module.app.dependency_overrides[module.actor]=lambda:{'id':'fixture','username':'fixture'}
        p=module.store.create('fixture','HTTP fixture');pid=p['id'];project=module.store.path('fixture',pid);out=project/'project/results/sample.png';out.parent.mkdir(parents=True,exist_ok=True)
        fig,ax=plt.subplots();ax.plot([1,2],[3,4]);ax.set_title('Title');fig.savefig(out);entry=register(project,'results/sample.png',fig);original=out.read_bytes()
        instances[pid]={'owner':'fixture','token':'local-fixture'}
        async def exercise():
            transport=httpx.ASGITransport(app=module.app,client=('127.0.0.1',12345))
            async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1') as client:
                route='/internal/reader-model/'+pid+'/v1/chat/completions';headers={'Authorization':'Bearer local-fixture'}
                original_messages=[{'role':'system','content':'Return translation JSONL.'},{'role':'user','content':[{'type':'text','text':'Conserved flux'},{'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}}]}]
                reply=await client.post(route,headers=headers,json={'model':'workbench','messages':original_messages})
                assert reply.status_code==200,reply.text
                assert received[-1]['messages'][1:]==original_messages
                assert '工作台输出标准' in received[-1]['messages'][0]['content'];checks.append('Native NeoRead messages and multimodal input preserved with product standards')
                reply=await client.post(route,headers=headers,json={'model':'workbench','messages':original_messages,'stream':True})
                assert reply.status_code==200 and 'data: [DONE]' in reply.text;checks.append('Native reader streaming protocol passes through configured HTTP provider')
                denied=await client.post(route,headers={'Authorization':'Bearer wrong'},json={})
                assert denied.status_code==403;checks.append('Internal reader model gateway requires its private engine authorization')
                reply=await client.post('/research/api/projects/'+pid+'/figure/chat',json={'path':'results/sample.png','message':'标题字号设为 14','revision':entry['revision'],'selection':['ax0-title'],'changes':{}})
                assert reply.status_code==200,reply.text
                changes=reply.json()['changes'];assert changes['objects']['ax0-title']['font_size']==14
                assert out.read_bytes()==original;checks.append('Natural-language figure edit creates a real preview without silently saving the source image')
                assert '图形对象' in received[-1]['messages'][0]['content'] or '科研图形' in received[-1]['messages'][0]['content'];checks.append('Figure API receives the built-in scientific output standard')
                reply=await client.post('/research/api/projects/'+pid+'/review-chat',json={'area':'slides','asset':'slides/third','title':'Results','locator':{'page':3},'quote':'Observed result','message':'Check this slide'})
                assert reply.status_code==200,reply.text
                context=json.loads(received[-1]['messages'][-1]['content'])
                assert context['current']['locator']['page']==3 and context['current']['asset']=='slides/third';checks.append('Inline review Agent receives the current slide and material context')
                log=(await client.get('/research/api/projects/'+pid+'/review-chat?area=slides')).json()['messages']
                assert len(log)==2 and log[0]['context']['locator']['page']==3;checks.append('Agent discussion persists across slide navigation independently of annotations')
                notes=(await client.get('/research/api/projects/'+pid+'/annotations?area=slides')).json()['items']
                assert notes==[];checks.append('Chat messages do not become page annotations')
        asyncio.run(exercise());instances.pop(pid,None);plt.close('all')
    report={'passed':len(checks),'checks':checks,'local_http_calls':len(received),'external_model_calls':0}
    output=Path(os.environ.get('WORKBENCH_TEST_OUTPUT','verification'));output.mkdir(parents=True,exist_ok=True);(output/'reader-model-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
finally:server.shutdown();server.server_close()
