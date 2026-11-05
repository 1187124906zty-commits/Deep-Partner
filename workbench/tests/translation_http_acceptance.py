"""Exercise the queued API translation route against an OpenAI-compatible fixture."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import HTTPServer,BaseHTTPRequestHandler
import json,time,os
from fastapi.testclient import TestClient
from server import app as module
from server.storage import Store

requests=[];invalid=False
class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert self.path=='/v1/chat/completions' and value['model']=='translation-fixture'
        assert self.headers['Authorization']=='Bearer fixture-only'
        rows=json.loads(value['messages'][1]['content'])['items'];requests.append(len(rows))
        answer={'items':[] if invalid else [{'id':x['id'],'text':'译文：'+x['text']} for x in rows]}
        data=json.dumps({'choices':[{'message':{'content':json.dumps(answer,ensure_ascii=False)}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

server=HTTPServer(('127.0.0.1',0),Fixture);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with TemporaryDirectory() as temp:
        root=Path(temp);module.store=Store(root/'store');module.api_path=lambda owner:root/'settings.json'
        module.api_path('fixture').write_text(json.dumps({'base_url':'http://127.0.0.1:'+str(server.server_port)+'/v1','api_key':'fixture-only','model':'translation-fixture'}))
        module.app.dependency_overrides[module.actor]=lambda:{'id':'fixture','username':'Translation fixture'}
        p=module.store.create('fixture','API translation');pid=p['id'];path='/research/api/projects/'+pid
        doc=module.store.manuscript('fixture',pid);doc.update(title='Flux',content={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'The flux is conserved [1].'}]},{'type':'blockMath','attrs':{'latex':'J=-D\\nabla c'}}]});module.store.save_manuscript('fixture',pid,doc)
        with TestClient(module.app) as client:
            def run(source='source',target='zh-CN'):
                response=client.post(path+'/manuscript/translate',json={'target':target,'use_native':False,'source':source});assert response.status_code==200,response.text;jid=response.json()['job_id']
                for _ in range(100):
                    job=next(j for j in client.get(path+'/jobs').json()['jobs'] if j['id']==jid)
                    if job['status'] in ('completed','failed'):return job
                    time.sleep(.03)
                raise AssertionError('Translation fixture did not complete')
            job=run();assert job['status']=='completed',job
            saved=client.get(path+'/manuscript').json();assert saved['translation']['title']=='译文：Flux' and saved['title']=='Flux'
            assert saved['translation']['content']['content'][1]==saved['content']['content'][1]
            job=run('translation','en');assert job['status']=='completed',job
            reverse=client.get(path+'/manuscript').json();assert reverse['translation']['title']=='译文：译文：Flux' and reverse['title']=='Flux'
            assert reverse['translation']['source_pane']=='translation' and reverse['translation']['language']=='en'
            original=reverse['translation'];invalid=True;job=run();assert job['status']=='failed'
            assert client.get(path+'/manuscript').json()['translation']==original
        report={'passed':True,'checks':['queued translation uses the configured OpenAI-compatible HTTP transport','source and editable math survive translation','edited translation can be translated back through the same real HTTP route','invalid provider IDs fail and keep the previous translation'],'local_http_calls':len(requests),'external_model_calls':0}
        output=Path(os.environ.get('WORKBENCH_TEST_OUTPUT','verification'));output.mkdir(parents=True,exist_ok=True);(output/'translation-http-acceptance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
finally:server.shutdown();server.server_close()
