import asyncio
import json
from pathlib import Path
import secrets
import time

import httpx

ROOT='https://tutor.example.invalid'
OUT=Path('/migration/workbench-verification.json')
LESSON='unified_1793203370310_e0eb2e6c'
WID='ws_ec13521c0efa498eb30ae811d4ed0adb'


async def main():
    result={}
    credentials=json.loads(Path('/migration/admin-login.json').read_text())
    async with httpx.AsyncClient(timeout=40,trust_env=False) as client:
        r=await client.get(ROOT+'/api/coder/sessions')
        assert r.status_code==401,r.text[:100]
        result['anonymous_coder_blocked']=True
        r=await client.post(ROOT+'/api/auth/login',json=credentials);r.raise_for_status()
        token=r.cookies.get('dt_token');assert token
        headers={'Cookie':'dt_token='+token,'Origin':ROOT}
        r=await client.get(ROOT+'/api/coder/health',headers=headers);r.raise_for_status()
        result['worker']=r.json()
        r=await client.get(ROOT+'/api/coder/sessions',headers=headers);r.raise_for_status()
        sessions=r.json()['sessions']
        lesson=next(x for x in sessions if x['session_id']==LESSON)
        assert lesson['workspace_id']==WID
        result['lesson_visible_for_explicit_selection']=lesson
        r=await client.post(ROOT+'/api/coder/tasks',headers=headers,json={
            'task':'部署验证：先读取本次选中的第一课会话。只需回答这节课的标题、会话里讨论的氯—硫酸盐神经算子问题，以及仿真应在哪类机器上运行。不要修改源文件或调用外网。',
            'project':'integration-check','mode':'plan',
            'sources':[{'session_id':LESSON,'workspace_id':WID}],
        });assert r.status_code==202,r.text[:200]
        result['plan_task']=r.json()['id']
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False),flush=True)
        for _ in range(180):
            r=await client.get(ROOT+'/api/coder/tasks/'+result['plan_task'],headers=headers);r.raise_for_status()
            task=r.json()
            if task['status'] in {'completed','failed'}:break
            await asyncio.sleep(2)
        result['plan_outcome']={k:v for k,v in task.items() if k!='events'}
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result['plan_outcome'],ensure_ascii=False),flush=True)
        assert task['status']=='completed',task.get('error','')
        assert '氯' in task['result'] and '硫' in task['result']
    print('Independent Coder planning check passed.',flush=True)


asyncio.run(main())
