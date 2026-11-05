"""Real workbench routes/storage with the native WS/HTTP boundary replaced."""
import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs,urlsplit

import httpx
import pytest
from fastapi import FastAPI,HTTPException

from server import native,reviews
from server.annotations import history,list_annotations,save_annotation
from server.storage import Store


@pytest.fixture
def api(tmp_path_factory,monkeypatch):
    # Figure session filenames add UUIDs; keep the Windows test root bounded.
    tmp_path=tmp_path_factory.mktemp('du')
    monkeypatch.setenv('WORKBENCH_DATA',str(tmp_path/'import-state'))
    module=importlib.import_module('server.app')
    store=Store(tmp_path/'state');project=store.create('owner-a','Shared research')
    project=store.update('owner-a',project['id'],native_id='ws-a')
    item=save_annotation(store,'owner-a',project['id'],{
        'area':'paper','asset':'manuscript/main.json','quote':'Measured value','body':'Clarify the condition',
        'locator':{'page':2,'paragraph':3}})
    user={'id':'owner-a'};http_calls=[];sent=[];new_sessions=[];submissions={}

    async def native_call(request,method,path,**kwargs):
        http_calls.append((method,path))
        assert request.headers['authorization']=='Bearer owner-a'
        parsed=urlsplit(path);sid=parsed.path.rsplit('/',1)[-1]
        assert parse_qs(parsed.query)=={'dt_workspace':['ws-a']}
        if sid=='session-other':
            return {'id':sid,'preferences':{'workspace_id':'ws-b'},'messages':[]}
        if sid!='session-a':raise HTTPException(404,'Session not found')
        return {'id':sid,'preferences':{'workspace_id':'ws-a'},
                'messages':[{'role':'user','metadata':{'turn_id':'turn-existing'}}],
                'active_turns':[{'id':'turn-active'}]}
    monkeypatch.setattr(native,'call',native_call)
    monkeypatch.setattr(module,'store',store)
    async def configured(request):return None
    monkeypatch.setattr(module,'ensure_native_model',configured)

    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def send(self,raw):
            payload=json.loads(raw);sent.append(payload)
            causal=payload['client_submission_id']
            if causal in submissions:
                prior=submissions[causal]
                assert prior['content']==payload['content'],'retry changed the causal prompt'
                self.sid,self.tid=prior['sid'],prior['tid']
            else:
                self.sid=payload.get('session_id')
                if not self.sid:
                    self.sid='created-session';new_sessions.append(self.sid)
                self.tid='native-turn-'+str(len(submissions)+1)
                submissions[causal]={'content':payload['content'],'sid':self.sid,'tid':self.tid}
            self.frames=[{'type':'session','session_id':self.sid},
                         {'type':'progress','session_id':self.sid,'turn_id':self.tid}]
        async def recv(self):return json.dumps(self.frames.pop(0))
    def connect(url,**kwargs):
        query=parse_qs(urlsplit(url).query)
        assert query=={'dt_workspace':['ws-a']}
        assert kwargs['additional_headers']['Cookie']=='dt_token=owner-a'
        assert 'Authorization' not in kwargs.get('additional_headers',{})
        return Socket()
    monkeypatch.setattr('websockets.asyncio.client.connect',connect)

    application=FastAPI();application.dependency_overrides[native.actor]=lambda:user
    application.add_exception_handler(KeyError,module.missing)
    application.add_exception_handler(ValueError,module.invalid)
    prefix='/research/api/projects/{pid}'
    application.add_api_route(prefix+'/annotations/submit',module.annotations_submit,methods=['POST'])
    application.add_api_route(prefix+'/agent-receipt',module.agent_receipt,methods=['POST'])
    application.add_api_route(prefix+'/native-session',module.native_session_identity,methods=['GET'])
    application.add_api_route(prefix+'/figure/chat',module.figure_chat,methods=['POST'])
    def request(suffix,payload=None,pid=None,method='POST'):
        async def send_request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application),base_url='http://test',
                    headers={'Authorization':'Bearer owner-a'}) as client:
                return await client.request(method,'/research/api/projects/'+(pid or project['id'])+suffix,json=payload)
        return asyncio.run(send_request())
    return SimpleNamespace(request=request,store=store,project=project,item=item,user=user,
                           calls=http_calls,sent=sent,new_sessions=new_sessions,submissions=submissions)


def test_annotation_reuses_validated_session_and_persists_actual_turn(api):
    body={'ids':[api.item['id']],'session_id':'session-a','operation_id':'desktop-feedback-1'}
    first=api.request('/annotations/submit',body)
    assert first.status_code==200,first.text
    value=first.json()
    assert value['session_id']=='session-a' and value['turn_id']=='native-turn-1'
    assert value['operation_id']=='desktop-feedback-1' and 'token' not in value['url']
    assert api.sent[0]['session_id']=='session-a' and api.sent[0]['workspace_id']=='ws-a'
    assert api.sent[0]['client_submission_id']=='workbench-review-desktop-feedback-1'
    from server.standards import contract
    handed_off=api.sent[0]['content']
    assert handed_off.count(contract())==1
    assert handed_off.count('# 工作台输出标准')==1
    assert handed_off.count('当前操作协议与具体任务：')==1
    assert api.item['body'] in handed_off and '项目根目录：' in handed_off
    note=list_annotations(api.store,'owner-a',api.project['id'])[0]
    assert note['status']=='submitted'
    assert note['locator']['native_session_id']=='session-a'
    assert note['locator']['native_turn_id']==value['turn_id']
    assert note['locator']['operation_id']==value['operation_id']
    assert note['locator']['page']==2
    repeated=api.request('/annotations/submit',body)
    assert repeated.json()==value and len(api.submissions)==1 and api.new_sessions==[]
    event=history(api.store,'owner-a',api.project['id'])['events'][0]
    assert event['kind']=='questions.submitted' and event['payload']['turn_id']==value['turn_id']


def test_annotation_legacy_client_can_create_native_session(api):
    response=api.request('/annotations/submit',{'ids':[api.item['id']]})
    assert response.status_code==200,response.text
    assert response.json()['session_id']=='created-session'
    assert response.json()['turn_id'] and response.json()['operation_id']
    assert 'session_id' not in api.sent[0] and api.new_sessions==['created-session']


def test_question_attachment_reaches_original_native_turn(api):
    attachment={'type':'file','filename':'notes.txt','mime_type':'text/plain','base64':'Zml4dHVyZQ=='}
    response=api.request('/annotations/submit',{'ids':[api.item['id']],'session_id':'session-a',
        'operation_id':'native-attachment','attachments':[attachment]})
    assert response.status_code==200,response.text
    assert api.sent[0]['attachments']==[attachment]
    assert api.sent[0]['session_id']=='session-a'


@pytest.mark.parametrize('sid',['missing-session','session-other'])
def test_annotation_rejects_wrong_workspace_session_before_execution(api,sid):
    response=api.request('/annotations/submit',{'ids':[api.item['id']],'session_id':sid})
    assert response.status_code==404 and api.sent==[]
    assert list_annotations(api.store,'owner-a',api.project['id'])[0]['status']=='open'


def test_project_owner_cannot_be_forged(api):
    api.user['id']='owner-b'
    response=api.request('/annotations/submit',{'ids':[api.item['id']],'session_id':'session-a'})
    assert response.status_code==404 and api.calls==[] and api.sent==[]


def test_project_native_identity_endpoint_checks_turn_and_owner(api):
    suffix='/native-session?session_id=session-a&turn_id=turn-existing'
    response=api.request(suffix,method='GET')
    assert response.status_code==200
    assert response.json()=={'session_id':'session-a','turn_id':'turn-existing','native_workspace_id':'ws-a'}
    assert api.request('/native-session?session_id=session-a&turn_id=foreign',method='GET').status_code==404
    api.user['id']='owner-b'
    assert api.request(suffix,method='GET').status_code==404


def test_receipt_preserves_verified_identity_and_legacy_compatibility(api):
    payload={'session_id':'session-a','turn_id':'turn-existing','operation_id':'desktop-receipt-1',
             'question_ids':[api.item['id']],'artifacts':[],'validation':[]}
    response=api.request('/agent-receipt',payload)
    assert response.status_code==200,response.text
    for key in ('session_id','turn_id','operation_id'):assert response.json()[key]==payload[key]
    saved=history(api.store,'owner-a',api.project['id'])['events'][0]
    assert saved['kind']=='agent.receipt' and saved['payload']['turn_id']=='turn-existing'
    legacy=api.request('/agent-receipt',{'artifacts':[]})
    assert legacy.status_code==200 and 'session_id' not in legacy.json()
    assert legacy.json()['quality']['status']=='not_reviewed'


@pytest.mark.parametrize('identity',[
    {'session_id':'session-a','turn_id':'foreign-turn'},
    {'session_id':'session-other','turn_id':'turn-existing'},
    {'turn_id':'turn-existing'},
])
def test_receipt_rejects_unowned_turn_without_recording(api,identity):
    before=len(history(api.store,'owner-a',api.project['id'])['events'])
    response=api.request('/agent-receipt',{'artifacts':[],**identity})
    assert response.status_code in (400,404)
    assert len(history(api.store,'owner-a',api.project['id'])['events'])==before


def figure_fixture(api):
    import matplotlib.pyplot as plt
    from server.figures import register,edit_session
    root=api.store.path('owner-a',api.project['id']);asset='results/chart.png'
    figure,axis=plt.subplots(figsize=(3,2));axis.plot([0,1],[1,2],label='Measured')
    figure.savefig(root/'project'/asset)
    register(root,asset,figure);plt.close(figure)
    info=edit_session(api.store,'owner-a',api.project['id'],asset)
    selected=next(row['id'] for row in info['objects'] if row['kind']=='line')
    return root,asset,info,selected


def test_embedded_figure_keeps_snapshot_draft_and_same_native_session(api,monkeypatch):
    import base64
    from server import models
    monkeypatch.setattr(models,'complete',lambda *a,**k:pytest.fail('embedded figure must use native turn'))
    root,asset,info,selected=figure_fixture(api)
    snapshot=base64.b64encode((root/'project'/asset).read_bytes()).decode()
    changes={'objects':{selected:{'color':'#a10a10'}}}
    payload={'path':asset,'message':'Increase contrast for the selected curve','selection':[selected],
             'revision':info['revision'],'changes':changes,'edit_session':info['edit_session'],
             'image':'data:image/png;base64,'+snapshot,'include_context':True,
             'session_id':'session-a','operation_id':'embedded-figure-1','embedded':True}
    response=api.request('/figure/chat',payload)
    assert response.status_code==200,response.text
    value=response.json()
    assert value['session_id']=='session-a' and value['turn_id']=='native-turn-1'
    assert value['operation_id']=='embedded-figure-1' and value['mode']=='code'
    assert api.sent[0]['session_id']=='session-a' and api.sent[0]['attachments'][0]['base64']==snapshot
    assert selected in api.sent[0]['content'] and '#a10a10' in api.sent[0]['content']
    assert info['edit_session'] in api.sent[0]['content']
    notes=[row for row in list_annotations(api.store,'owner-a',api.project['id']) if row['area']=='image']
    assert len(notes)==1 and notes[0]['id']==value['question_id']
    assert notes[0]['locator']['changes']==changes
    assert notes[0]['locator']['native_turn_id']==value['turn_id']
    prepared=json.loads((root/'review/request.json').read_text(encoding='utf8'))
    assert prepared['annotations'][0]['edit_session']==info['edit_session']
    assert not (root/'.workbench/figure-chats').exists()
    assert api.new_sessions==[]
    repeated=api.request('/figure/chat',payload)
    assert repeated.json()==value and len(api.submissions)==1
    assert len([row for row in list_annotations(api.store,'owner-a',api.project['id']) if row['area']=='image'])==1


def test_embedded_figure_removed_context_sends_no_snapshot_or_draft(api):
    response=api.request('/figure/chat',{'path':'results/not-sent.png','message':'Explain the previous answer',
        'changes':{'figure':{'width':123}},'selection':['not-sent-object'],'edit_session':'not-sent-session',
        'include_context':False,'session_id':'session-a','operation_id':'embedded-contextless-1','embedded':True})
    assert response.status_code==200,response.text
    assert response.json()['session_id']=='session-a' and response.json()['turn_id']
    assert response.json()['mode']=='conversation'
    assert api.sent[0]['attachments']==[] and api.sent[0]['capability']=='chat'
    assert 'not-sent' not in api.sent[0]['content'] and '123' not in api.sent[0]['content']
    root=api.store.path('owner-a',api.project['id'])
    assert not (root/'.workbench/figure-chats').exists() and not (root/'review').exists()


def test_embedded_figure_rejects_foreign_session_and_stale_revision_before_evidence(api):
    payload={'path':'results/chart.png','message':'Adjust this figure','embedded':True,'session_id':'session-other'}
    response=api.request('/figure/chat',payload)
    assert response.status_code==404 and api.sent==[]
    root,asset,info,selected=figure_fixture(api)
    payload.update(session_id='session-a',revision=info['revision']-1,edit_session=info['edit_session'])
    response=api.request('/figure/chat',payload)
    assert response.status_code==409 and api.sent==[]
    assert not (root/'review').exists()
    assert all(row['area']!='image' for row in list_annotations(api.store,'owner-a',api.project['id']))
