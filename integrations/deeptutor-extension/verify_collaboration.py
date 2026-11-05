"""Exercise a native Code-mode question card and its normal reply path."""
import asyncio
import json
from pathlib import Path
import sys
import uuid
import httpx
import websockets
from verify_code_mode import SELECTION

OUT=Path('/migration/collaboration-verification.json')


async def main():
    login=json.loads(Path('/migration/admin-login.json').read_text())
    result={'tool_calls':[],'question_cards':[],'reply_accepted':False}
    async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
        r=await client.post('http://127.0.0.1:8001/api/auth/login',json=login);r.raise_for_status()
        token=r.cookies['dt_token']
    payload={'type':'start_turn','protocol_version':'2.0','capability':'code',
        'content':'这是协作交互验收。这轮只讨论，不实施。Grill me：我想把零散CSV里的自由氯和总氯画在同一张图里，但还没确定它们的计量基准是否一致。先通过原生提问确认最关键的判断，给你的推荐意见。不要替我假定单位，也不要读取其他会话。',
        'language':'zh','tools':[],'llm_selection':SELECTION,'workspace_id':''}
    submitted=False;turn_id=''
    if len(sys.argv)>1:
        turn_id=sys.argv[1]
        payload={'type':'subscribe_turn','protocol_version':'2.0','turn_id':turn_id,'after_seq':0}
        result['reused_existing_turn']=True
    async with asyncio.timeout(420):
        async with websockets.connect('ws://127.0.0.1:8001/ws',
                additional_headers={'Cookie':'dt_token='+token},max_size=20000000) as ws:
            await ws.send(json.dumps(payload,ensure_ascii=False))
            async for raw in ws:
                event=json.loads(raw);kind=event.get('type');meta=event.get('metadata') or {}
                turn_id=event.get('turn_id') or meta.get('turn_id') or turn_id
                result['session_id']=event.get('session_id') or result.get('session_id','')
                result['turn_id']=turn_id
                if kind in {'error','protocol_error'}:raise RuntimeError(str(event)[:1200])
                if kind=='tool_call':
                    result['tool_calls'].append(event.get('tool_name') or meta.get('tool_name'))
                card=(meta.get('tool_metadata') or {}).get('ask_user')
                if kind=='tool_result' and card and not submitted:
                    result['question_cards'].append(card)
                    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
                    # The executor transitions to waiting_input immediately after
                    # publishing the card. Allow that native state to settle.
                    await asyncio.sleep(.2)
                    await ws.send(json.dumps({'type':'submit_user_reply','protocol_version':'2.0',
                        'turn_id':turn_id,'command_id':'verify-'+uuid.uuid4().hex,
                        'text':'按推荐先统一计量基准。现在两类CSV单位还未知，不能直接叠图；先保留原始数据，确认单位和测量定义后再做换算。这轮验收已完成，请只用三句话归纳这个决定，不继续提问，也不实施程序。'},ensure_ascii=False))
                    submitted=True
                if kind=='command_ack' and event.get('command_type')=='submit_user_reply':
                    assert event.get('accepted'),event
                    result['reply_accepted']=True
                if kind=='result':result['response']=meta.get('response') or event.get('content','')
                if kind=='done':
                    result['status']=meta.get('status')
                    assert result['status']=='completed',event
                    break
    result['verified']=bool(result['question_cards']) and submitted and result['reply_accepted'] and 'coder_run' not in result['tool_calls']
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)
    assert result['verified'],'Native discussion did not ask, accept feedback and finish without coding'


if __name__=='__main__':asyncio.run(main())
