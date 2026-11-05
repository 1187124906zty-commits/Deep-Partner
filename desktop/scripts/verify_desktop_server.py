"""Read-only acceptance of native-client APIs and Terra's real Windows tool call."""
import asyncio
import json
import time
from pathlib import Path
import httpx
import websockets

async def main():
    credentials=json.loads(Path('/migration/admin-login.json').read_text())
    async with httpx.AsyncClient(trust_env=False,timeout=30) as client:
        login=await client.post('http://127.0.0.1:8001/api/auth/login',json=credentials)
        login.raise_for_status()
        token=login.cookies.get('dt_token')
        headers={'Cookie':'dt_token='+token}
        models=(await client.get('http://127.0.0.1:8001/api/settings/llm-options',headers=headers)).json()
        terra=next(m for m in models['options'] if m['model']=='gpt-6.1-terra')
        sessions=await client.get('http://127.0.0.1:8001/api/sessions?all_workspaces=true&limit=100',headers=headers)
        knowledge=await client.get('http://127.0.0.1:8001/api/knowledge-bases/list?resource_library=true',headers=headers)
        sessions.raise_for_status();knowledge.raise_for_status()
        report={'login':login.status_code,'models_http':200,'sessions_http':sessions.status_code,'sessions':len(sessions.json()['sessions']),'knowledge_http':knowledge.status_code,'computer_model':terra['model'],'learning_default':models['active']}
    command={'type':'start_turn','protocol_version':'2.0','content':'请加载 windows-desktop MCP 的 system_info 工具，读取这台 Windows 电脑的 CPU 型号和逻辑核心数，然后用一句中文报告真实结果。不要使用鼠标、键盘、截图或浏览器。','capability':'chat','language':'zh','tools':[],'mcp':['deployment:windows-desktop'],'llm_selection':{'profile_id':terra['profile_id'],'model_id':terra['model_id']}}
    begin=time.monotonic();text='';events=[];tool_events=[]
    async with asyncio.timeout(180):
        async with websockets.connect('ws://127.0.0.1:8001/ws',additional_headers=headers,max_size=20000000) as ws:
            await ws.send(json.dumps(command,ensure_ascii=False))
            async for raw in ws:
                event=json.loads(raw);kind=event.get('type');events.append(kind)
                if kind in ('error','protocol_error'):raise RuntimeError(str(event)[:500])
                if kind=='content':text+=event.get('content','')
                if kind=='result':text=event.get('metadata',{}).get('response') or text
                if kind in ('tool_call','tool_result'):tool_events.append({'type':kind,'source':event.get('source'),'content':event.get('content','')[:1000],'metadata':{k:v for k,v in event.get('metadata',{}).items() if k in ('tool','name','tool_name','tool_id','trace_kind')}})
                if kind=='done':
                    assert event.get('metadata',{}).get('status')=='completed',event
                    break
    assert any('system_info' in json.dumps(e) for e in tool_events),tool_events
    assert 'tool_result' in events,events
    report.update(terra_windows_tool_call=True,response=text,elapsed_seconds=round(time.monotonic()-begin,2),tool_events=tool_events,passed=True)
    Path('/migration/desktop-native-client-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))

asyncio.run(main())
