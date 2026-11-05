import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

try:
    import deeptutor_registration_gate as gate
except ModuleNotFoundError:
    import registration_gate as gate
    sys.modules['deeptutor_registration_gate']=gate

import registration_admin as admin
import trusted_devices as devices
import coder_bridge as coder
from deeptutor.services import auth


@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setattr(gate,'DB',tmp_path/'requests.sqlite3')
    monkeypatch.setattr(gate.identity,'USERS_FILE',tmp_path/'users.json')
    monkeypatch.setattr(gate.identity,'LEGACY_USERS_FILE',tmp_path/'absent.json')
    monkeypatch.setattr(gate.identity,'_env_bootstrap_admin',lambda:('',''))
    monkeypatch.setattr(auth,'AUTH_SECRET','workbench-test-secret-long-enough')
    gate.identity._write_users({'tutor':{'id':'local-admin','hash':auth.hash_password('test-admin-password'),
        'role':'admin','disabled':False,'preset':'standard'}})
    return tmp_path


def signup():
    return gate.Signup(username='candidate',password='candidate-test-password',
                       email='candidate@example.org',reason='我是科研用户，申请用于学习')


def authority():
    return admin.OwnerAuthority('known-owner','让这个申请人先补充研究用途，语气友善一些','owner-session')


def test_registration_requires_explanation_and_email():
    for reason in ['', '    ', 'test']:
        with pytest.raises(ValidationError):
            gate.Signup(username='person',password='password123',email='user@example.org',reason=reason)
    for email in ['invalid','a@host','a\nb@example.org']:
        with pytest.raises(ValidationError):
            gate.Signup(username='person',password='password123',email=email,reason='我是用户，需要科研学习')


@pytest.mark.asyncio
async def test_request_for_more_information_emails_without_approving(store,monkeypatch):
    send=AsyncMock()
    monkeypatch.setattr(admin,'send_smtp',lambda *args: None)
    request=gate.create_request(signup(),'192.0.2.1')
    result=await admin.manage('reply',request['request_id'],'请补充使用说明','您好，感谢您的申请。请您补充具体研究用途，以便我们继续审核。',authority())
    assert result['account_status']=='pending' and result['mail_status']=='sent'
    assert gate.identity.get_user('candidate') is None
    with admin.outbox_connection() as conn:
        row=conn.execute('SELECT * FROM registration_mail').fetchone()
    assert row['recipient']=='candidate@example.org'
    assert row['owner_message']==authority().user_message
    assert '仍在审核中' in row['body'] and 'candidate-test-password' not in row['body']


@pytest.mark.asyncio
async def test_approval_and_mail_failure_report_separate_outcomes(store,monkeypatch):
    def fail(*args):raise OSError('private-provider-error')
    monkeypatch.setattr(admin,'send_smtp',fail)
    request=gate.create_request(signup(),'192.0.2.2')
    result=await admin.manage('approve',request['request_id'],'欢迎使用 DeepTutor','您好，感谢您的申请，欢迎使用 DeepTutor 开展研究与学习。',authority())
    assert result['account_status']=='approved' and result['mail_status']=='failed'
    assert result['mail_error']=='OSError'
    assert gate.identity.get_user('candidate')['role']=='user'


@pytest.mark.asyncio
async def test_model_cannot_forge_owner_authority(store):
    request=gate.create_request(signup(),'192.0.2.3')
    with pytest.raises(PermissionError):
        await admin.manage('approve',request['request_id'],'批准申请','欢迎您使用本站进行研究与学习。',{'sender_id':'known-owner'})
    assert gate.identity.get_user('candidate') is None


def test_owner_tool_is_only_mounted_for_bound_transport_sender(store,monkeypatch):
    from deeptutor.services.partners import manager
    config=SimpleNamespace(owner_id='local-admin',channels={'weixin':{'allow_from':['known-owner']}})
    monkeypatch.setattr(manager,'get_partner_manager',lambda:SimpleNamespace(load_config=lambda _:config))
    base={'source':'partner','partner_id':'gg','channel':'weixin','sender_id':'known-owner'}
    ctx=SimpleNamespace(metadata=base,user_message='我同意',session_id='abc')
    assert admin.owner_authority(ctx) is not None
    for key,value in [('sender_id','stranger'),('channel','web'),('partner_id','other')]:
        assert admin.owner_authority(SimpleNamespace(metadata={**base,key:value})) is None
    config.channels['weixin']['allow_from']=['*']
    assert admin.owner_authority(ctx) is None


def test_browser_metadata_does_not_grant_login(store):
    pairing,secret=devices.new_pair('相同电脑','same-browser','192.0.2.4')
    assert devices.pairing_by_secret(secret)['status']=='pending'
    with pytest.raises(HTTPException):devices.trusted_record('same-browser')
    with pytest.raises(HTTPException):devices.pairing_by_secret(pairing['id'])
    assert 'token_hash' not in pairing


def test_device_approval_is_one_time_and_requires_owner(store):
    pairing,secret=devices.new_pair('我的电脑','test-browser','192.0.2.5')
    with pytest.raises(PermissionError):devices.decide_pair(pairing['id'],'approve',{})
    devices.decide_pair(pairing['id'],'approve',authority())
    assert devices.pairing_by_secret(secret)['status']=='approved'
    with pytest.raises(ValueError):devices.decide_pair(pairing['id'],'approve',authority())


def test_revoking_device_invalidates_http_session(store):
    did,secret=devices.remember_device('tutor','test-device','browser')
    response=devices.device_response(did,secret)
    from http.cookies import SimpleCookie
    cookies=SimpleCookie()
    for header in response.headers.getlist('set-cookie'):cookies.load(header)
    app=FastAPI()
    app.add_middleware(devices.DeviceSessionMiddleware)
    @app.get('/api/protected')
    async def protected():return {'ok':True}
    client=TestClient(app)
    headers={'Authorization':'Bearer '+cookies['dt_token'].value}
    assert client.get('/api/protected',headers=headers).status_code==200
    with devices.connection() as conn:
        conn.execute('UPDATE trusted_devices SET revoked_at=? WHERE id=?',(gate.now(),did))
    assert client.get('/api/protected',headers=headers).status_code==401
    with pytest.raises(HTTPException):devices.trusted_record(secret)


def test_revoked_device_cannot_use_websocket_query_token(store):
    from starlette.websockets import WebSocketDisconnect
    did,secret=devices.remember_device('tutor','test-device','browser')
    response=devices.device_response(did,secret)
    from http.cookies import SimpleCookie
    cookie=SimpleCookie()
    for header in response.headers.getlist('set-cookie'):cookie.load(header)
    token=cookie['dt_token'].value
    app=FastAPI();app.add_middleware(devices.DeviceSessionMiddleware)
    from fastapi import WebSocket
    @app.websocket('/ws')
    async def websocket(ws:WebSocket):
        await ws.accept();await ws.receive_text();await ws.send_text('ok')
    with devices.connection() as conn:
        conn.execute('UPDATE trusted_devices SET revoked_at=? WHERE id=?',(gate.now(),did))
    with pytest.raises(WebSocketDisconnect):
        with TestClient(app).websocket_connect('/ws?token='+token):pass


@pytest.mark.asyncio
async def test_coder_tool_requires_server_owned_authority():
    result=await coder.CoderTool().execute(action='code',task='change files',_coder_authority={'role':'admin'})
    assert result.success is False


def test_coder_task_project_cannot_escape_workspace():
    with pytest.raises(ValidationError):coder.TaskRequest(task='test',project='../../secrets')


def test_code_tools_do_not_mount_in_other_modes(monkeypatch):
    monkeypatch.setattr(coder,'coder_authority',lambda _:coder.CoderAuthority('session','',(),'task'))
    extension=coder.CoderCapability()
    for mode in ['chat','deep_solve','deep_research','deep_question','visualize']:
        assert extension.is_active(SimpleNamespace(active_capability=mode)) is False
    assert extension.is_active(SimpleNamespace(active_capability='code')) is True


@pytest.mark.asyncio
async def test_code_mode_reuses_exact_session_and_history(monkeypatch):
    import code_mode
    monkeypatch.setattr(code_mode,'get_current_user_or_none',lambda:SimpleNamespace(role='admin'))
    seen=[]
    class Pipeline:
        def __init__(self,**kwargs):pass
        async def run(self,context,stream):seen.append(context)
    monkeypatch.setattr(code_mode,'AgenticChatPipeline',Pipeline)
    history=[{'role':'user','content':'我之前确认的研究路线'}]
    context=SimpleNamespace(session_id='same-session',active_capability='code',language='zh',conversation_history=history)
    await code_mode.CodeMode().run(context,None)
    assert seen==[context] and context.session_id=='same-session'
    assert context.conversation_history is history


@pytest.mark.asyncio
async def test_stopping_native_turn_cancels_its_worker_task(monkeypatch):
    calls=[]
    async def worker(method,path,value=None):
        calls.append((method,path))
        if method=='POST' and path=='/tasks':return {'id':'a'*24,'status':'queued'}
        if method=='GET':raise asyncio.CancelledError
        return {'cancelled':True}
    monkeypatch.setattr(coder,'worker_request',worker)
    with pytest.raises(asyncio.CancelledError):
        await coder.CoderTool().execute(action='code',task='test',
            _coder_authority=coder.CoderAuthority('session','',(),'test'))
    assert ('POST','/tasks/'+'a'*24+'/cancel') in calls


@pytest.mark.asyncio
async def test_tutor_can_read_same_session_code_without_executing(tmp_path,monkeypatch):
    monkeypatch.setattr(coder,'PROJECT_ROOT',tmp_path)
    project=coder.session_project('same-session')
    root=tmp_path/project;root.mkdir()
    (root/'exchange.py').write_text('def exchange(f,b,r):\n    return f+r,b-r\n','utf-8')
    auth=coder.CoderAuthority('same-session','',(),'解释方程与实现')
    result=await coder.CodeFilesTool().execute(action='read',path='exchange.py',_coder_authority=auth)
    assert result.success and 'return f+r,b-r' in result.content
    assert (root/'exchange.py').read_text()=='def exchange(f,b,r):\n    return f+r,b-r\n'


@pytest.mark.asyncio
async def test_code_reader_rejects_non_owner_and_hidden_paths(tmp_path,monkeypatch):
    monkeypatch.setattr(coder,'PROJECT_ROOT',tmp_path)
    auth=coder.CoderAuthority('same-session','',(),'read')
    tool=coder.CodeFilesTool()
    assert not (await tool.execute(action='overview',_coder_authority={'role':'admin'})).success
    for path in ['../../outside.py','.ssh/cluster_ed25519','.deeptutor/state.json']:
        assert not (await tool.execute(action='read',path=path,_coder_authority=auth)).success


@pytest.mark.asyncio
async def test_code_reader_lines_are_bounded(tmp_path,monkeypatch):
    monkeypatch.setattr(coder,'PROJECT_ROOT',tmp_path)
    root=tmp_path/coder.session_project('same-session');root.mkdir()
    (root/'solver.py').write_text('\n'.join(str(i) for i in range(1000)),'utf-8')
    result=await coder.CodeFilesTool().execute(action='read',path='solver.py',start_line=10,line_count=900,
        _coder_authority=coder.CoderAuthority('same-session','',(),'read'))
    payload=json.loads(result.content)
    assert payload['truncated'] and len(payload['content'].splitlines())==300


def test_normal_tutor_is_aware_of_real_code_mode(monkeypatch,tmp_path):
    monkeypatch.setattr(coder,'coder_authority',lambda _:coder.CoderAuthority('same','',(),'read'))
    monkeypatch.setattr(coder,'PROJECT_ROOT',tmp_path)
    context=SimpleNamespace(active_capability='chat',session_id='same')
    extension=coder.CodeAwareness()
    assert extension.is_active(context)
    assert extension.owned_tools==('code_files',)
    assert '模式→代码' in extension.system_block(context).content


@pytest.mark.asyncio
async def test_native_preferences_and_current_decisions_reach_deepcode(monkeypatch,tmp_path):
    from deeptutor.core.context import UnifiedContext,TurnRuntimeContext,WorkspaceRuntimeContext
    monkeypatch.setattr(coder,'get_current_user_or_none',lambda:SimpleNamespace(role='admin'))
    monkeypatch.setattr(coder,'current_workspace_id',lambda:'research-workspace')
    monkeypatch.setattr(coder,'PROJECT_ROOT',tmp_path)
    context=UnifiedContext(session_id='same-session',user_message='先按已确认的一维模型实施，详细解释验证',
        conversation_history=[{'role':'user','content':'我已确认先验证一维边界，不扩展二维'}],
        persona_context='用中文，回答要有具体依据',language='zh',
        runtime=TurnRuntimeContext(workspace=WorkspaceRuntimeContext(
            workspace_id='research-workspace',instructions='考虑作者判断；关键取舍先讨论')))
    authority=coder.coder_authority(context)
    calls=[]
    async def worker(method,path,value=None):
        if method=='POST':
            calls.append(value)
            return {'id':'a'*24,'status':'queued'}
        return {'id':'a'*24,'status':'completed','result':'read-only handoff verified'}
    async def snapshots(_):
        return [{'session_id':'same-session','workspace_id':'research-workspace',
                 'messages':[{'role':'user','content':'旧快照'}]}]
    monkeypatch.setattr(coder,'worker_request',worker)
    monkeypatch.setattr(coder,'source_snapshots',snapshots)
    result=await coder.CoderTool().execute(action='code',task='实施已确认方案',
        sources=[{'workspace_id':'research-workspace','session_id':'same-session'}],_coder_authority=authority)
    assert result.success
    actual=calls[0]['sources']
    assert len(actual)==1
    assert actual[0]['workspace_instructions']=='考虑作者判断；关键取舍先讨论'
    assert actual[0]['persona_context']=='用中文，回答要有具体依据'
    assert actual[0]['language']=='zh'
    assert actual[0]['messages']==context.conversation_history+[{'role':'user','content':context.user_message}]
