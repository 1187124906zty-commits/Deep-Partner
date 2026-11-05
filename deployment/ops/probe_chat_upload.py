from pathlib import Path
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

def main():
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    with sync_playwright() as p:
        request=p.request.new_context(base_url='https://tutor.example.invalid',extra_http_headers={'Origin':'https://tutor.example.invalid'})
        assert request.post('/api/auth/login',data=account).ok
        state=ROOT/'.local/onboarding-test-project.json'
        project=json.loads(state.read_text()) if state.exists() else request.post('/research/api/projects',data={'name':'附件与预览验收（临时）'}).json()
        state.write_text(json.dumps(project,ensure_ascii=False),encoding='utf8')
        prefix='/research/api/projects/'+project['id']
        result=request.post(prefix+'/attachments',multipart={'files':{'name':'upload-workflow-check.md','mimeType':'text/markdown','buffer':b'# Upload workflow check\n\nChloride sulfate attachment retrieval marker UPLOAD_RETRIEVAL_20261102.\n'}},timeout=120000)
        data=result.json();print(json.dumps({'status':result.status,'result':data},ensure_ascii=False))
        report={'project':project,'upload':data,'http_status':result.status}
        (ROOT/'reports/chat-upload-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        assert result.ok
        query=request.post(prefix+'/knowledge/search',data={'query':'UPLOAD_RETRIEVAL_20261102','limit':5,'mode':'fulltext-keyword'}).json()
        report['retrieval']=query;assert query['items']
        (ROOT/'reports/chat-upload-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
