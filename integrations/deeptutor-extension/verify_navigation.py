"""Check persisted results of browser-driven navigation/reload scenarios.

The UI actions are performed in the real browser; this script independently
checks the same native session records. It does not start replacement turns.
"""
import asyncio
import json
from pathlib import Path
import httpx

API='http://127.0.0.1:8001'
WORKSPACE='ws_ec13521c0efa498eb30ae811d4ed0adb'
OUT=Path('/migration/navigation-verification.json')
CASES=[
    {'name':'navigate_during_thinking','session_id':'unified_1793282673889_c14d3221',
     'workspace_id':'','marker':'NAV-20261029-A-COMPLETE',
     'ui_action':'Chat -> Calendar while exploring -> same session'},
    {'name':'immediate_navigation_in_research_workspace','session_id':'unified_1793282880663_9f38bfe0',
     'workspace_id':WORKSPACE,'marker':'NAV-20261029-B-COMPLETE',
     'ui_action':'First submit -> immediate Calendar navigation -> same session'},
    {'name':'reload_during_thinking','session_id':'unified_1793282880663_9f38bfe0',
     'workspace_id':WORKSPACE,'marker':'NAV-20261029-C-COMPLETE',
     'ui_action':'Native retry of unsent draft -> server confirms running -> full reload'},
]


async def main():
    login=json.loads(Path('/migration/admin-login.json').read_text())
    result={'cases':[],'scope':'Current deployment; not proof of all historical navigation failures',
        'pre_admission_reload_observation':{
            'observed_in_real_browser':True,'result':'Unsent draft restored with explicit retry action',
            'server_messages_before_retry':2,
            'accepted_turn_before_second_reload':'turn_1793283283177_f759fb07f4',
            'accepted_status_before_second_reload':'running'}}
    async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
        r=await client.post(API+'/api/auth/login',json=login);r.raise_for_status()
        headers={'Cookie':'dt_token='+r.cookies['dt_token']}
        for case in CASES:
            r=await client.get(API+'/api/sessions/'+case['session_id'],
                params={'dt_workspace':case['workspace_id']},headers=headers)
            r.raise_for_status();data=r.json()
            messages=data.get('messages',[])
            found=[m for m in messages if m.get('role')=='assistant' and case['marker'] in m.get('content','')]
            row={**case,'persisted_message_count':len(messages),
                 'result_persisted':bool(found),'active_turns':data.get('active_turns',[])}
            result['cases'].append(row)
        # Inspect status only: do not copy the user's research content to test logs.
        r=await client.get(API+'/api/sessions/unified_1793203370310_e0eb2e6c',
            params={'dt_workspace':WORKSPACE},headers=headers);r.raise_for_status()
        data=r.json()
        result['original_session']={'session_id':data.get('id'),
            'message_count':len(data.get('messages',[])),
            'active_turns':data.get('active_turns',[]),
            'recent_message_status':[
                {'id':m.get('id'),'role':m.get('role'),'created_at':m.get('created_at'),
                 'status':m.get('status'),'metadata_keys':list((m.get('metadata') or {}).keys())}
                for m in data.get('messages',[])[-4:]]}
    result['verified']=all(c['result_persisted'] for c in result['cases'])
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)
    assert result['verified'],'A browser navigation/reload result was not persisted'


if __name__=='__main__':asyncio.run(main())
