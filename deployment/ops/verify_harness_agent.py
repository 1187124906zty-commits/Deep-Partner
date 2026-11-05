"""Real Tutor turn: parallel evidence, native project rules, and Dify delivery."""
import asyncio
import json
from pathlib import Path
import time
from urllib.parse import quote

import httpx
import websockets


async def main():
    origin='https://tutor.example.invalid'
    account=json.loads(Path('/migration/admin-login.json').read_text())
    async with httpx.AsyncClient(timeout=120,trust_env=False) as client:
        login=await client.post('http://127.0.0.1:8001/api/auth/login',json=account);login.raise_for_status()
        token=login.cookies.get('dt_token');headers={'Authorization':'Bearer '+token,'Origin':origin}
        rows=await client.get(origin+'/research/api/projects',headers=headers);rows.raise_for_status()
        project=next(p for p in rows.json()['projects'] if p['name']=='Dify 部署与交付验证')
        options=await client.get('http://127.0.0.1:8001/api/settings/llm-options',headers=headers);options.raise_for_status()
        selection=next(({'profile_id':p['profile_id'],'model_id':p['model_id']} for p in options.json()['options'] if p.get('profile_id') and p.get('model_id')),None)
        prompt=('这是独立验证项目的软件联调。请实际用 research_workbench evidence，query="chloride diffusion sulfate"，'
            'evidence_sources=["knowledge","papers"]，limit=2，取得项目已绑定知识库和学术题录的真实分支状态。'
            '接着 context(task=review) 读取当前项目规范，再用 deliver 将一段简短的联调记录保存到 docs/agent-harness-check.md。'
            '记录实际检索run_id、coverage和来源，明确片段/题录不能证明科学结论。保留任何实际失败。'
            '这不是研究论文写作，不改变正式稿件，不委派Code，不运行计算。最后给实际保存位置与状态。')
        payload={'type':'start_turn','protocol_version':'2.0','capability':'chat','language':'zh','tools':[],
            'workspace_id':project['native_id'],'content':prompt}
        if selection:payload['llm_selection']=selection
        events=[];session='';response='';started=time.monotonic()
        async with asyncio.timeout(300):
            async with websockets.connect('ws://127.0.0.1:8001/ws?dt_workspace='+quote(project['native_id']),
                additional_headers={'Cookie':'dt_token='+token,'Origin':origin},max_size=20000000) as socket:
                await socket.send(json.dumps(payload,ensure_ascii=False))
                async for raw in socket:
                    event=json.loads(raw);events.append(event)
                    session=event.get('session_id') or event.get('metadata',{}).get('session_id') or session
                    if event['type'] in {'error','protocol_error'}:raise RuntimeError(str(event)[:800])
                    if event['type']=='result':response=event.get('metadata',{}).get('response','')
                    if event['type']=='done':
                        assert event['metadata']['status']=='completed';break
        values=[];calls=[]
        for event in events:
            if event['type']=='tool_call':calls.append(event.get('metadata',{}).get('tool_name'))
            if event['type']=='tool_result' and event.get('metadata',{}).get('tool_name')=='research_workbench':
                try:values.append(json.loads(event.get('content') or ''))
                except ValueError:pass
        evidence=next((v for v in values if 'coverage' in v and v.get('run_id')),None)
        saved=next((v for v in values if v.get('status')=='saved' and v.get('processing_history_verified')),None)
        assert evidence and saved,[(v.get('status'),v.get('error')) for v in values]
        document=await client.get(origin+'/research/api/projects/'+project['id']+'/file?path=docs/agent-harness-check.md',headers=headers)
        document.raise_for_status();assert evidence['run_id'] in document.text
        report={'verified':True,'session_id':session,'workspace_id':project['native_id'],'project_id':project['id'],
            'session_url':origin+'/chat/'+session+'?dt_workspace='+project['native_id'],
            'elapsed_seconds':round(time.monotonic()-started,2),'tool_calls':calls,'evidence_run_id':evidence['run_id'],
            'coverage':evidence['coverage'],'delivery_run_id':saved['run_id'],'workflow_run_id':saved.get('workflow_run_id'),
            'artifact':saved['artifact'],'response':response}
        Path('/migration/harness-agent-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':asyncio.run(main())
