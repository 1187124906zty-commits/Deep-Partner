"""Exercise the deployed service through the loopback preview's QA session."""
from pathlib import Path
from urllib.parse import quote,urlencode
import json,urllib.request,urllib.error,uuid,time

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:47901'
checks=[]

def request(path,method='GET',value=None,fields=None,files=None):
    headers={};body=None
    if fields is not None or files:
        boundary='workbench-'+uuid.uuid4().hex;parts=[]
        for key,val in (fields or {}).items():parts.extend([('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n').encode(),str(val).encode(),b'\r\n'])
        for key,name,data,kind in files or []:parts.extend([('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"; filename="'+name+'"\r\nContent-Type: '+kind+'\r\n\r\n').encode(),data,b'\r\n'])
        parts.append(('--'+boundary+'--\r\n').encode());body=b''.join(parts);headers['Content-Type']='multipart/form-data; boundary='+boundary
    elif value is not None:body=json.dumps(value,ensure_ascii=False).encode();headers['Content-Type']='application/json'
    req=urllib.request.Request(BASE+path,data=body,headers=headers,method=method)
    try:response=urllib.request.urlopen(req,timeout=90)
    except urllib.error.HTTPError as error:
        raise AssertionError(str(error.code)+' '+path+' '+error.read().decode(errors='replace')[:900]) from error
    data=response.read()
    return json.loads(data) if 'json' in response.headers.get('Content-Type','') else data

def wait_job(path,jid):
    for _ in range(60):
        job=next(x for x in request(path+'/jobs')['jobs'] if x['id']==jid)
        if job['status']=='completed':return job['result']
        if job['status'] in ['failed','interrupted']:raise AssertionError(job['error'])
        time.sleep(1)
    raise TimeoutError('Job did not complete')

me=request('/research/api/me');assert me['username']=='workbench_ui_qa_20261031'
p=request('/research/api/projects')['projects'][0];pid=p['id'];path='/research/api/projects/'+pid
assert p['native_id'] and '/workspaces/' in p['root'];checks.append('real account sign-in and project-native workspace binding')
for name,content in [('src/diffusion.py','"""A small formatting fixture; not a research solver."""\nD = 1e-12\n'),('configs/model.toml','[model]\nname = "format-example"\n'),('results/example.csv','time,normalized_value\n0,0\n1,0.5\n2,1\n')]:request(path+'/file','PUT',{'path':name,'content':content})
inv=request(path+'/files')['items'];assert next(x for x in inv if x['name']=='src')['types']['PY']==1;checks.append('actual API file inventory and extension counts')
request(path+'/file','PUT',{'path':'src/recovery-check.txt','content':'first'})
request(path+'/file','PUT',{'path':'src/recovery-check.txt','content':'second'})
old=next(x for x in request(path+'/trash')['items'] if x['original']=='project/src/recovery-check.txt')
request(path+'/trash/'+old['id']+'/restore','POST')
assert request(path+'/file?path=src/recovery-check.txt')==b'first';request(path+'/file?path=src/recovery-check.txt','DELETE');checks.append('replace and recover previous file through actual HTTP')
data=(ROOT/'verification/manuscript-example.docx').read_bytes()
doc=request(path+'/manuscript/import','POST',fields={},files=[('file','draft.docx',data,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')])
assert 'blockMath' in json.dumps(doc['content']) and 'image' in json.dumps(doc['content']);doc.update(title='多孔介质中的传输过程',template='chinese')
doc=request(path+'/manuscript','PUT',doc);checks.append('Word multipart import keeps native editable math and image')
for format in ['docx','pdf','tex']:
    result=wait_job(path,request(path+'/manuscript/export','POST',{'format':format,'review':True})['job_id'])
    exported=request(result['url']);assert len(exported)>1000;checks.append('actual queued '+format+' export and authenticated download')
native='/api/knowledge-bases';scope='?'+urlencode({'resource_library':'true','dt_workspace':p['native_id']})
libraries=request(native+scope)
if not isinstance(libraries,list):raise AssertionError('Native knowledge-base list returned unexpected content')
item=next((k for k in libraries if k['name']=='项目文献'),None)
if not item:
    item=request(native+'?dt_workspace='+p['native_id'],'POST',fields={'name':'项目文献','rag_provider':'llamaindex','storage_workspace_id':p['native_id']})
    libraries=request(native+scope);item=next(k for k in libraries if k['name']=='项目文献')
request(path,'PATCH',{'knowledge_bases':[item['id']]});kb=native+'/'+quote(item['id'],safe='')
request(kb+'/folders?dt_workspace='+p['native_id'],'POST',{'path':'理论与方法'})
listing=request(kb+'/files?dt_workspace='+p['native_id']);assert any(x['name']=='理论与方法' and x['type']=='folder' for x in listing['files']);checks.append('native DeepTutor KB create, bind and folder organisation')
plan={'title':'研究汇报','sections':[{'id':'cover','title':'多孔介质中的传输过程','content':'研究问题与数值方法\n组会汇报','role':'cover'},{'id':'methods','title':'方程与证据相互对照','content':'控制方程给出变量之间的关系。\n数值计算核对守恒和边界条件。\n图表展示相同条件下的比较。','role':'content'},{'id':'summary','title':'讨论','content':'计算结果与适用条件应当一起呈现。','role':'ending'}]}
request(path+'/slides','PUT',plan);t=request(path+'/slide-templates');assert len(t['templates'])>=2
result=wait_job(path,request(path+'/slides/export','POST')['job_id']);assert result['all_template_parts_preserved']
ppt=request(result['url']);assert ppt.startswith(b'PK');assert request(path+'/slide-preview?kind=deck&page=2').startswith(b'\x89PNG');checks.append('actual template-based editable PPT export and rendered preview')
report={'passed':True,'checks':checks,'live_http':True,'project':pid,'model_calls':0}
(ROOT/'verification/http-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
