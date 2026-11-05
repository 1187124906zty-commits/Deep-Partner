"""Exercise search and the Dify page reader in a real authenticated Tutor turn."""
import asyncio,json,time
from pathlib import Path
from urllib.parse import quote

import httpx
import websockets


async def main():
    origin='https://tutor.example.invalid'
    account=json.loads(Path('/migration/admin-login.json').read_text())
    async with httpx.AsyncClient(timeout=100,trust_env=False) as client:
        login=await client.post('http://127.0.0.1:8001/api/auth/login',json=account);login.raise_for_status()
        token=login.cookies.get('dt_token');headers={'Authorization':'Bearer '+token,'Origin':origin}
        projects=await client.get(origin+'/research/api/projects',headers=headers);projects.raise_for_status()
        project=next(p for p in projects.json()['projects'] if p['name']=='计算验证能力验收')
        options=await client.get('http://127.0.0.1:8001/api/settings/llm-options',headers=headers);options.raise_for_status()
        selection=next(({'profile_id':p['profile_id'],'model_id':p['model_id']} for p in options.json()['options']
            if p.get('profile_id') and p.get('model_id')),None)
        prompt=('这是研究扩展的只读验收。请实际使用 research_workbench 的 search 动作完成两项：'
            '1）search_kind=papers，source=scholar_mcp，query="Fourier Neural Operator"，limit=2，读取两条真实题录；'
            '2）search_kind=page，query=https://www.anthropic.com/research/building-effective-agents，读取公开网页证据。'
            '这是独立检索和读取，不启动成果交付、不保存文件、不委派 Code、不运行计算。'
            '最后用中文简要说明各项实际状态、来源、两篇题录标题，并根据取得的网页正文解释一条对本系统有用的原则。'
            '如失败，保留实际错误与恢复建议，不把失败说成没有文献，不虚构读取成功。')
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
                    session=event.get('session_id') or session
                    if event['type'] in {'error','protocol_error'}:raise RuntimeError(str(event)[:1000])
                    if event['type']=='result':response=event.get('metadata',{}).get('response','')
                    if event['type']=='done':
                        assert event['metadata']['status']=='completed';break
        names=[e.get('metadata',{}).get('tool_name') for e in events if e['type']=='tool_call']
        results=[]
        for event in events:
            if event['type']=='tool_result' and event.get('metadata',{}).get('tool_name')=='research_workbench':
                try:results.append(json.loads(event.get('content') or ''))
                except ValueError:pass
        paper=next((r for r in results if r.get('provider')=='scholar_mcp' and r.get('items')),None)
        page=next((r for r in results if r.get('source')=='Dify WebScraper' and r.get('content')),None)
        assert paper is not None and page is not None,[(r.get('status'),r.get('error')) for r in results]
        assert not any(name in names for name in ('research_code','exec','research_compute')),names
        result={'verified':True,'session_id':session,'workspace_id':project['native_id'],
            'session_url':origin+'/chat/'+session+'?dt_workspace='+project['native_id'],
            'elapsed_seconds':round(time.monotonic()-started,2),'tool_calls':names,
            'paper_source':paper['source'],'paper_titles':[r['title'] for r in paper['items']],
            'page_source':page['source'],'page_url':page['source_url'],'page_content_chars':page.get('content_chars'),
            'page_workflow_run_id':page['workflow_run_id'],'response':response}
        Path('/migration/extension-optimization-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':asyncio.run(main())
