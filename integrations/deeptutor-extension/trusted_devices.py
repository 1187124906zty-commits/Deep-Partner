"""Passwordless return visits using revocable, owner-approved browser secrets."""
from __future__ import annotations

import asyncio
from contextlib import closing
import hashlib
from http.cookies import SimpleCookie
import json
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from deeptutor.api.routers.auth import _cookie_attrs, _COOKIE_MAX_AGE, require_admin
from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.services import auth
from registration_admin import OwnerAuthority, owner_authority
import deeptutor_registration_gate as gate

PAIR_COOKIE='__Host-dt_pair'
TRUST_COOKIE='__Host-dt_trusted'
PAIR_TTL=600
TRUST_TTL=30*86400


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def connection():
    conn=gate.connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS trusted_devices (
        id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL, user_id TEXT NOT NULL, name TEXT NOT NULL,
        user_agent TEXT NOT NULL, created_at TEXT NOT NULL,
        expires_at REAL NOT NULL, last_used_at TEXT NOT NULL DEFAULT '',
        revoked_at TEXT NOT NULL DEFAULT '')''')
    conn.execute('''CREATE TABLE IF NOT EXISTS device_pairings (
        id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
        display_code TEXT NOT NULL, name TEXT NOT NULL, user_agent TEXT NOT NULL,
        ip_hash TEXT NOT NULL, ip_display TEXT NOT NULL, created_at TEXT NOT NULL,
        created_ts REAL NOT NULL, expires_at REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', decided_by TEXT NOT NULL DEFAULT '',
        owner_message TEXT NOT NULL DEFAULT '', notified INTEGER NOT NULL DEFAULT 0)''')
    conn.commit()
    return conn


def pair_public(row):
    return {k:row[k] for k in ('id','display_code','name','user_agent','ip_display','created_at','expires_at','status')}


def new_pair(name,user_agent,ip):
    now=time.time()
    token=secrets.token_urlsafe(32)
    pid=secrets.token_hex(12)
    with closing(connection()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        count=conn.execute('SELECT count(*) FROM device_pairings WHERE ip_hash=? AND created_ts>?',
                           (digest(ip),now-3600)).fetchone()[0]
        if count>=5:
            raise HTTPException(429,'设备请求过于频繁，请稍后再试。')
        code=secrets.token_hex(3).upper()
        conn.execute('''INSERT INTO device_pairings
            (id,token_hash,display_code,name,user_agent,ip_hash,ip_display,created_at,created_ts,expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (pid,digest(token),code,name.strip(),user_agent[:500],digest(ip),ip[:80],gate.now(),now,now+PAIR_TTL))
        conn.commit()
        row=conn.execute('SELECT * FROM device_pairings WHERE id=?',(pid,)).fetchone()
    return pair_public(row),token


def pairing_by_secret(token):
    if not token:
        raise HTTPException(401,'请先从此浏览器发起设备授权。')
    with closing(connection()) as conn:
        row=conn.execute('SELECT * FROM device_pairings WHERE token_hash=?',(digest(token),)).fetchone()
    if not row or row['expires_at']<=time.time():
        raise HTTPException(410,'设备授权请求已过期，请重新申请。')
    return row


def decide_pair(pid,action,authority):
    if not isinstance(authority,OwnerAuthority):
        raise PermissionError('仅绑定的管理员微信可授权设备')
    if action not in {'approve','reject'}:
        raise ValueError('不支持的设备处理动作')
    with closing(connection()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM device_pairings WHERE id=?',(pid,)).fetchone()
        if not row or row['expires_at']<=time.time() or row['status']!='pending':
            raise ValueError('设备请求不存在、已处理或已过期')
        conn.execute('UPDATE device_pairings SET status=?,decided_by=?,owner_message=? WHERE id=?',
                     ('approved' if action=='approve' else 'rejected',authority.sender_id,authority.user_message,pid))
        conn.commit()
    return {'device_request_id':pid,'status':'approved' if action=='approve' else 'rejected'}


def remember_device(username,name,user_agent):
    record=gate.identity.get_user(username)
    if not record or record.get('disabled') or record.get('role')!='admin':
        raise HTTPException(403,'管理员账号不可用')
    token=secrets.token_urlsafe(32)
    did=secrets.token_hex(12)
    with closing(connection()) as conn:
        conn.execute('''INSERT INTO trusted_devices
            (id,token_hash,username,user_id,name,user_agent,created_at,expires_at)
            VALUES (?,?,?,?,?,?,?,?)''',
            (did,digest(token),username,record['id'],name,user_agent[:500],gate.now(),time.time()+TRUST_TTL))
        conn.commit()
    return did,token


def trusted_record(token):
    if not token:
        raise HTTPException(401,'这台浏览器尚未获得免密登录授权。')
    with closing(connection()) as conn:
        row=conn.execute('SELECT * FROM trusted_devices WHERE token_hash=?',(digest(token),)).fetchone()
    if not row or row['revoked_at'] or row['expires_at']<=time.time():
        raise HTTPException(401,'设备凭证已失效，请重新授权。')
    record=gate.identity.get_user(row['username'])
    if not record or record.get('disabled') or record['id']!=row['user_id']:
        raise HTTPException(401,'关联账号不可用。')
    return row,record


def device_response(device_id,token,username='tutor'):
    row,record=trusted_record(token)
    session=auth.create_token(username,record['role'],record['id'])
    claims=jwt.decode(session,auth.AUTH_SECRET,algorithms=[auth._ALGORITHM])
    claims['tdid']=device_id
    session=jwt.encode(claims,auth.AUTH_SECRET,algorithm=auth._ALGORITHM)
    with closing(connection()) as conn:
        conn.execute('UPDATE trusted_devices SET last_used_at=? WHERE id=?',(gate.now(),device_id));conn.commit()
    response=JSONResponse({'ok':True,'username':username,'device_id':device_id},headers={'Cache-Control':'no-store'})
    response.set_cookie(value=session,max_age=_COOKIE_MAX_AGE,**_cookie_attrs())
    response.set_cookie(TRUST_COOKIE,token,max_age=TRUST_TTL,secure=True,httponly=True,samesite='strict',path='/')
    return response


async def notify_pair(pid):
    from deeptutor.services.partners.manager import get_partner_manager
    from deeptutor.partners.bus.events import OutboundMessage
    with closing(connection()) as conn:
        row=conn.execute('SELECT * FROM device_pairings WHERE id=?',(pid,)).fetchone()
    try:
        instance=get_partner_manager().get_partner('gg')
        allowed=instance.config.channels['weixin']['allow_from']
        if not instance.running or instance.config.owner_id!='local-admin' or len(allowed)!=1 or allowed[0]=='*':
            return
        channel=instance.channel_manager.get_channel('weixin')
        text=(f'DeepTutor 设备登录请求\n设备：{row["name"]}\n核对码：{row["display_code"]}\n'
              f'浏览器：{row["user_agent"][:180]}\n来源 IP：{row["ip_display"]}\n'
              f'请求编号：{pid}\n10分钟内有效。只授权你本人正在使用的设备。'
              '可直接告诉 GG 这台是否允许免密登录；没有你的明确意思就不会放行。')
        await channel.send(OutboundMessage(channel='weixin',chat_id=allowed[0],content=text))
        with closing(connection()) as conn:
            conn.execute('UPDATE device_pairings SET notified=1 WHERE id=?',(pid,));conn.commit()
    except Exception:
        pass


class DeviceAdminTool(BaseTool):
    def get_definition(self):
        return ToolDefinition('device_login_manage',
            '根据绑定管理员在微信中的自然表达，管理他本人的设备免密登录。list 列出待授权设备及核对码；明确认可的设备用 approve，陌生设备用 reject；revoke 撤销已授权设备并立即使其设备登录会话失效。不能仅凭设备名称、IP或浏览器相似就自动批准。',
            parameters=[ToolParameter('action','string',enum=['list','approve','reject','revoke']),
                        ToolParameter('device_id','string','真实请求或设备编号；list 时为空',required=False,default='')])

    async def execute(self,action='list',device_id='',_device_authority=None,**kwargs):
        if not isinstance(_device_authority,OwnerAuthority):
            return ToolResult(content='只有绑定的管理员微信可执行。',success=False)
        try:
            if action=='list':
                with closing(connection()) as conn:
                    pending=conn.execute("SELECT * FROM device_pairings WHERE status='pending' AND expires_at>?",(time.time(),)).fetchall()
                    devices=conn.execute("SELECT id,name,user_agent,created_at,expires_at,last_used_at FROM trusted_devices WHERE revoked_at='' AND expires_at>?",(time.time(),)).fetchall()
                value={'pending':[pair_public(r) for r in pending],'trusted':[dict(r) for r in devices]}
            elif action in {'approve','reject'}:
                value=decide_pair(device_id,action,_device_authority)
            elif action=='revoke':
                with closing(connection()) as conn:
                    changed=conn.execute("UPDATE trusted_devices SET revoked_at=? WHERE id=? AND revoked_at=''",(gate.now(),device_id)).rowcount
                    conn.commit()
                value={'device_id':device_id,'revoked':bool(changed)}
            else:
                raise ValueError('不支持的操作')
            return ToolResult(content=json.dumps(value,ensure_ascii=False),success=True)
        except ValueError as exc:
            return ToolResult(content=str(exc),success=False)


class DeviceAdminCapability:
    name='device_login_admin'
    owned_tools=('device_login_manage',)

    def is_active(self,context):
        return owner_authority(context) is not None

    def system_block(self,context,**kwargs):
        return PromptBlock(self.name,'你可根据管理员自然表达管理设备免密登录。设备名和浏览器/IP仅用于辨认，不证明身份。首次授权先 list，只有管理员明确表示是本人设备并允许登录才 approve；对象不清楚时核对设备核对码。拒绝或撤销也必须对应真实编号。熟悉设备后续由服务器校验随机凭证直接登录，不由模型猜测硬件身份。')

    def augment_kwargs(self,tool_name,kwargs,context):
        return {**kwargs,'_device_authority':owner_authority(context)} if tool_name=='device_login_manage' else kwargs

    def pre_loop_seed(self,context):
        return ''


class DeviceSessionMiddleware:
    """Revocation applies to both HTTP and WebSocket device-created sessions."""
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type'] in {'http','websocket'}:
            path=scope.get('path','')
            exempt=path in {'/api/quick-login/request','/api/quick-login/status',
                            '/api/quick-login/complete','/api/quick-login/login',
                            '/api/auth/login','/api/auth/logout'} or not path.startswith(('/api/','/ws'))
            if not exempt:
                headers=dict(scope.get('headers',[]))
                cookies=SimpleCookie();cookies.load(headers.get(b'cookie',b'').decode())
                token=cookies['dt_token'].value if 'dt_token' in cookies else ''
                auth_header=headers.get(b'authorization',b'').decode()
                if scope['type']=='websocket':
                    # Match the native websocket authentication precedence.
                    query=parse_qs(scope.get('query_string',b'').decode())
                    token=query.get('token',[token])[0] or token
                elif auth_header.startswith('Bearer '):
                    token=auth_header[7:]
                try:
                    claims=jwt.decode(token,auth.AUTH_SECRET,algorithms=[auth._ALGORITHM])
                except (JWTError,ValueError):
                    claims={}
                did=claims.get('tdid')
                if did:
                    with closing(connection()) as conn:
                        row=conn.execute('SELECT * FROM trusted_devices WHERE id=?',(did,)).fetchone()
                    if not row or row['revoked_at'] or row['expires_at']<=time.time():
                        if scope['type']=='websocket':
                            await send({'type':'websocket.close','code':4401})
                        else:
                            response=JSONResponse({'detail':'设备授权已撤销或过期，请重新登录。'},status_code=401)
                            await response(scope,receive,send)
                        return
                    if scope['type']=='websocket':
                        original_receive=receive
                        async def device_receive():
                            message=await original_receive()
                            if message['type']=='websocket.receive':
                                with closing(connection()) as conn:
                                    current=conn.execute('SELECT revoked_at,expires_at FROM trusted_devices WHERE id=?',(did,)).fetchone()
                                if not current or current['revoked_at'] or current['expires_at']<=time.time():
                                    await send({'type':'websocket.close','code':4401})
                                    return {'type':'websocket.disconnect','code':4401}
                            return message
                        receive=device_receive
        await self.app(scope,receive,send)


class NameRequest(BaseModel):
    name:str=Field(min_length=1,max_length=80)


def install(app):
    app.add_middleware(DeviceSessionMiddleware)

    @app.get('/access/quick-login',include_in_schema=False)
    async def page():
        return HTMLResponse(Path('/app/workbench_pages/quick-login.html').read_text('utf-8'),headers={'Cache-Control':'no-store'})

    @app.post('/api/quick-login/request',status_code=202)
    async def request_pair(body:NameRequest,request:Request,background:BackgroundTasks):
        gate.same_origin(request)
        ip=request.headers.get('x-forwarded-for','').split(',')[0].strip() or request.client.host
        value,token=new_pair(body.name,request.headers.get('user-agent',''),ip)
        background.add_task(notify_pair,value['id'])
        response=JSONResponse(value,status_code=202,headers={'Cache-Control':'no-store'})
        response.set_cookie(PAIR_COOKIE,token,max_age=PAIR_TTL,secure=True,httponly=True,samesite='strict',path='/')
        return response

    @app.get('/api/quick-login/status')
    async def pair_status(request:Request):
        return pair_public(pairing_by_secret(request.cookies.get(PAIR_COOKIE,'')))

    @app.post('/api/quick-login/complete')
    async def complete(request:Request):
        gate.same_origin(request)
        row=pairing_by_secret(request.cookies.get(PAIR_COOKIE,''))
        with closing(connection()) as conn:
            changed=conn.execute("UPDATE device_pairings SET status='consumed' WHERE id=? AND status='approved'",(row['id'],)).rowcount
            conn.commit()
        if not changed:
            raise HTTPException(403,'设备尚未获准，或请求已使用。')
        did,token=remember_device('tutor',row['name'],row['user_agent'])
        response=device_response(did,token)
        response.delete_cookie(PAIR_COOKIE,secure=True,httponly=True,samesite='strict',path='/')
        return response

    @app.post('/api/quick-login/remember')
    async def remember(body:NameRequest,request:Request,admin=Depends(require_admin)):
        gate.same_origin(request)
        did,token=remember_device(admin.username,body.name,request.headers.get('user-agent',''))
        return device_response(did,token,admin.username)

    @app.post('/api/quick-login/login')
    async def quick(request:Request):
        gate.same_origin(request)
        token=request.cookies.get(TRUST_COOKIE,'')
        row,record=trusted_record(token)
        return device_response(row['id'],token,row['username'])

    @app.get('/api/quick-login/devices')
    async def devices(admin=Depends(require_admin)):
        with closing(connection()) as conn:
            rows=conn.execute('SELECT id,name,user_agent,created_at,expires_at,last_used_at,revoked_at FROM trusted_devices WHERE user_id=?',(admin.user_id,)).fetchall()
        return {'devices':[dict(r) for r in rows]}

    @app.post('/api/quick-login/devices/{device_id}/revoke')
    async def revoke(device_id:str,request:Request,admin=Depends(require_admin)):
        gate.same_origin(request)
        with closing(connection()) as conn:
            changed=conn.execute("UPDATE trusted_devices SET revoked_at=? WHERE id=? AND user_id=?",(gate.now(),device_id,admin.user_id)).rowcount
            conn.commit()
        return {'revoked':bool(changed)}
