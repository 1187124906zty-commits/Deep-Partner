"""Exercise the real Paper2Slides planner against a local API contract fixture."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json,tempfile,threading
from server.slides import plan_with_paper2slides

seen=[];response_mode=['valid']
class Model(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append(value)
        content=json.dumps({'slides':[{'title':'研究问题','content':'输入稿件中的问题。'},{'title':'方法与证据','content':'输入稿件中的方法和条件。'},{'title':'讨论','content':'仅陈述输入稿件支持的结论。'}]},ensure_ascii=False) if response_mode[0]=='valid' else 'not a plan'
        data=json.dumps({'id':'local-fixture','object':'chat.completion','created':1,'model':'fixture','choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

service=ThreadingHTTPServer(('127.0.0.1',0),Model);thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
try:
    with tempfile.TemporaryDirectory() as folder:
        doc={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'用于接口验收的合成稿件，包含控制方程、边界条件、数值结果和适用范围。'}]}]}
        api={'api_key':'local-fixture-only','model':'fixture','base_url':'http://127.0.0.1:'+str(service.server_port)+'/v1'}
        plan=plan_with_paper2slides(doc,'规划验收',Path(folder),api)
        assert len(plan['sections'])==3 and plan['sections'][0]['role']=='cover' and plan['sections'][-1]['role']=='ending'
        assert seen and 'messages' in seen[0] and 'Paper2Slides' in plan['planner']
        response_mode[0]='invalid'
        try:plan_with_paper2slides(doc,'规划验收',Path(folder),api);raise AssertionError('Invalid provider output was reported as a success')
        except ValueError:pass
        print(json.dumps({'passed':True,'real_paper2slides':True,'local_api_calls':len(seen),'external_model_calls':0,'invalid_model_output_rejected':True}))
finally:service.shutdown();service.server_close()
