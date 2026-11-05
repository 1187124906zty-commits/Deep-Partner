"""Deliver independently checked native Code artifacts through the published Dify flow."""
import json
from pathlib import Path
import re
import urllib.request
import uuid

import verify_intensive as v

ROOT=Path('/srv/dify-research')


def main():
    report=json.loads((ROOT/'reports/code-chain-live.json').read_text())
    assert report['verified'] and report['independent_validation']['passed']
    account=json.loads(Path('/srv/deeptutor/migration/admin-login.json').read_text())
    request=urllib.request.Request('http://127.0.0.1:8008/api/auth/login',method='POST',headers={'Content-Type':'application/json'},data=json.dumps(account).encode())
    v.login.open(request,timeout=20).close();v.cookie='; '.join(c.name+'='+c.value for c in v.jar)
    project=next(p for p in v.call('GET','/research/api/projects')['projects'] if p['name']=='Dify 部署与交付验证')
    assert project['native_id']==report['workspace_id']
    task=report['worker']['task'];physical=task['project']
    assert re.fullmatch(r'[A-Za-z0-9_-]{1,120}',physical)
    source_root=Path('/srv/deeptutor/workspaces/coder/projects')/physical
    assert source_root.resolve().is_relative_to(Path('/srv/deeptutor/workspaces/coder/projects').resolve())
    targets=[('src/diffusion_conservation.py','src/diffusion_conservation.py'),
        ('results/diffusion.json','results/diffusion.json'),('verification.json','docs/code-verification.json')]
    context=v.call('GET','/research/dify/api/context?project_id='+project['id']+'&task=code')
    receipts=[]
    for source,target in targets:
        content=(source_root/source).read_text()
        if source.endswith('.py'):compile(content,source,'exec')
        else:json.loads(content)
        metadata=v.call('GET','/research/api/projects/'+project['id']+'/files?path='+str(Path(target).parent))
        existing=next((i for i in metadata['items'] if i['path']==target),None)
        artifact={'type':'file','path':target,'content':content,'summary':'登记实际 Code 产物与独立数值核验依据',
            'source_paths':['coder-task:'+task['id']+'/'+source]}
        if existing:artifact['expected_modified']=existing['modified']
        body={'request_id':'code-chain-'+uuid.uuid4().hex,'project_id':project['id'],'workspace_id':project['native_id'],
            'session_id':report['session_id'],'task':'code','standard_version':context['standard_version'],
            'artifact':artifact,'validation':[{'check':'independent_face_flux_reference','result':'passed',
                'evidence':'reports/code-chain-live.json independent_validation; max field error 2.220446049250313e-16'}],
            'limitations':['软件集成与所声明的数值不变量验证；没有据此完成新材料模型或实验验证。']}
        saved=v.call('POST','/research/dify/api/deliver',body)
        assert saved['status']=='saved' and saved['workflow_status']=='succeeded' and saved['processing_history_verified']
        assert v.call('GET','/research/api/projects/'+project['id']+'/file?path='+target,as_text=True)==content
        receipts.append({k:saved[k] for k in ('run_id','workflow_run_id','status','workflow_status','artifact','history_event_id')})
    result={'verified':True,'task_id':task['id'],'tutor_session':report['session_id'],
        'project_id':project['id'],'deliveries':receipts,'independent_validation':report['independent_validation'],
        'scope':'真实 Tutor→Code 编写与执行；验收脚本将其实际产物提交 Dify→工作台保存与回读。'}
    (ROOT/'reports/code-delivery-live.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'verified':True,'task_id':task['id'],'deliveries':receipts},ensure_ascii=False))


if __name__=='__main__':main()
