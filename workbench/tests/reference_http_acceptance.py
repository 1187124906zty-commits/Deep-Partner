"""Verify the Agent proposal / apply boundary over the real HTTP adapters."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import HTTPServer,BaseHTTPRequestHandler
import json,os
from fastapi.testclient import TestClient
from server import app as module
from server import references
from server.storage import Store

received=[]
candidate={'title':'Related source','authors':['A. Author'],'year':2025,'doi':'10.1000/fixture','verified':True,'source':'fixture metadata'}
class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])));received.append(value)
        assert self.headers['Authorization']=='Bearer fixture-only'
        answer={'selected':0,'reason':'Fixture recommendation based on supplied metadata.','paragraph':'A narrower comparison [1] follows the supplied evidence.'}
        data=json.dumps({'choices':[{'message':{'content':json.dumps(answer)}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=HTTPServer(('127.0.0.1',0),Fixture);Thread(target=server.serve_forever,daemon=True).start();checks=[]
async def search(*a,**k):return [candidate]
references.search=search
try:
    with TemporaryDirectory() as folder:
        root=Path(folder);module.store=Store(root/'state');module.api_path=lambda owner:root/'settings.json'
        module.api_path('qa').write_text(json.dumps({'base_url':'http://127.0.0.1:'+str(server.server_port)+'/v1','api_key':'fixture-only','model':'fixture'}))
        module.app.dependency_overrides[module.actor]=lambda:{'id':'qa','username':'QA'}
        p=module.store.create('qa','Reference fixture');pid=p['id'];path='/research/api/projects/'+pid
        doc=module.store.manuscript('qa',pid);doc['references']=[{'id':'ref-1','number':1,'title':'Original source','raw':'Original source.'}]
        doc['content']={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'An initial claim '},{'type':'citation','attrs':{'refId':'ref-1','number':1}},{'type':'text','text':'.'}]}]}
        saved=module.store.save_manuscript('qa',pid,doc)
        with TestClient(module.app) as client:
            reply=client.post(path+'/references/recommend',json={'id':'ref-1','instruction':'Find a more relevant comparison'})
            assert reply.status_code==200,reply.text;proposal=reply.json()
            context=json.loads(received[-1]['messages'][-1]['content']);assert context['paragraph']=='An initial claim [1].' and context['candidates']==[candidate];checks.append('Agent receives the actual cited paragraph and the searched candidate metadata')
            assert client.get(path+'/manuscript').json()==saved;checks.append('A recommendation remains a reviewable proposal without silently saving a replacement')
            result=client.post(path+'/references/replace',json={'id':'ref-1','entry':proposal['entry'],'revision':proposal['revision'],'paragraph':proposal['proposal']['paragraph'],'expected_text':proposal['expected_text']})
            assert result.status_code==200,result.text;final=result.json()
            assert final['references'][0]['doi']==candidate['doi'] and references.text(final['content']['content'][0])==proposal['proposal']['paragraph'];checks.append('Applying the Agent proposal synchronizes the cited paragraph and reference library')
            assert references.text(final['content']['content'][-1]).startswith('[1] A. Author. Related source');checks.append('The bibliographic entry is rebuilt from the selected source metadata')
    report={'passed':len(checks),'checks':checks,'local_model_http_calls':len(received),'external_model_calls':0}
    output=Path(os.environ.get('WORKBENCH_TEST_OUTPUT','verification'));output.mkdir(parents=True,exist_ok=True);(output/'reference-http-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
finally:server.shutdown();server.server_close()
