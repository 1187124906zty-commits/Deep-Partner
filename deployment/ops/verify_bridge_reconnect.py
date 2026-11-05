"""Packaged desktop bridge: inherit, repeat, disconnect, reconnect, prepare only."""
from pathlib import Path
from http.cookiejar import CookieJar
import base64,json,os,subprocess,urllib.request,urllib.error,shutil
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
SOURCE=Path('D:/博士工作/博士项目/水分扩散/2026-11-2/网站项目')

def main():
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe'),'--headless-ui'],stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,text=True,encoding='utf8',creationflags=0x08000000)
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    report={'version':'0.4.2','applied':False,'checks':{}}
    origin=None
    try:
        info=json.loads(child.stdout.readline());origin=info['url'].split('/desktop/bootstrap')[0]
        assert info['version']=='0.4.2'
        client.open(info['url'],timeout=20).read()
        def call(path,body=None):
            return json.load(client.open(urllib.request.Request(origin+path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Origin':origin,'Content-Type':'application/json'}),timeout=100))
        initial=call('/desktop/status')
        assert initial['bridge']['listening']
        first=call('/desktop/bridge/connect',{});assert first['connected'],first
        second=call('/desktop/bridge/connect',{});assert second['connected'],second
        report['checks']['existing_bridge_and_repeated_connect']=True
        approved=call('/desktop/import-source',{'source':str(SOURCE)})
        assert approved['authorized'] and Path(approved['workspace']).resolve()==SOURCE.resolve()
        try:call('/desktop/import-source',{'source':str(SOURCE/'manuscript/main.json')})
        except urllib.error.HTTPError as e:assert e.code==400
        else:raise AssertionError('A file was accepted as a source directory')
        assert call('/desktop/status')['workspace']==approved['workspace']
        report['checks']['typed_directory_authorized_invalid_source_preserves_selection']=True
        token=(Path.home()/'AppData/Local/DeepPartner/bridge-token').read_text().strip()
        code='''import sys,json,socket,http.client
r=json.load(sys.stdin)
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(100);s.connect('/srv/deeptutor/data/system/desktop-bridge.sock')
c=http.client.HTTPConnection('localhost',timeout=100);c.sock=s
payload={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'project_import','arguments':{'action':'prepare','source':r['source']}}}
c.request('POST','/mcp',json.dumps(payload),{'Authorization':'Bearer '+r['token'],'Content-Type':'application/json'})
response=c.getresponse();data=json.load(response);c.close();assert response.status==200
result=data['result'];assert not result.get('isError'),result
print(result['content'][0]['text'])
'''
        encoded=base64.b64encode(code.encode()).decode()
        command="sudo -n python3 -c \"import base64;exec(base64.b64decode('"+encoded+"'))\""
        result=subprocess.run(['ssh','-o','BatchMode=yes','papers-research',command],input=json.dumps({'token':token,'source':str(SOURCE)}),text=True,capture_output=True,encoding='utf8',timeout=140)
        assert result.returncode==0,'Remote authenticated prepare did not finish'
        prepared=json.loads(result.stdout)
        assert prepared['status']=='prepared' and prepared['applied'] is False and prepared['files']==174
        report['checks']['server_to_current_desktop_import_prepare']=True
        report['prepared']={k:prepared[k] for k in ('files','bytes','status','applied')}
        stage=Path(prepared['bundle']).resolve().parent
        imports=(Path.home()/'AppData/Local/DeepPartner/imports').resolve()
        assert stage.parent==imports
        shutil.rmtree(stage)
        call('/desktop/bridge/disconnect',{});assert not call('/desktop/status')['bridge']['connected']
        report['checks']['inherited_bridge_disconnects']=True
        assert call('/desktop/bridge/connect',{})['connected']
        assert call('/desktop/bridge/connect',{})['connected']
        report['checks']['fresh_reconnect_and_repeat']=True
        report['passed']=all(report['checks'].values())
        (ROOT/'reports/bridge-reconnect-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        if origin:
            try:client.open(urllib.request.Request(origin+'/desktop/bridge/disconnect',data=b'{}',headers={'Origin':origin,'Content-Type':'application/json'}),timeout=10).read()
            except OSError:pass
        child.terminate();child.wait(timeout=10)
if __name__=='__main__':main()
