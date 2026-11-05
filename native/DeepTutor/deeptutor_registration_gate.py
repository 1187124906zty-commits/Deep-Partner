"""Pending-only signup, authenticated admin decisions, and the owner's WeChat notification."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, closing, suppress
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ConfigDict, Field, field_validator

from deeptutor.api.routers.auth import RegisterRequest, require_admin
from deeptutor.multi_user import identity
from deeptutor.services.auth import hash_password

ORIGIN = 'https://tutor.example.invalid'
DB = Path(os.getenv('DEEPTUTOR_REGISTRATION_DB', '/app/data/system/registration/requests.sqlite3'))
PARTNER = 'gg'


class Signup(RegisterRequest):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=64)
    email: str = Field(min_length=5, max_length=254)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value = value.strip()
        if not re.fullmatch(r'[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+', value):
            raise ValueError('请填写有效的联系邮箱。')
        return value

    @field_validator('reason')
    @classmethod
    def meaningful_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError('请说明你是谁及使用目的（至少5个字符）。')
        return value


def now():
    return datetime.now(timezone.utc).isoformat()


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(DB, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY, username TEXT NOT NULL, password_hash TEXT NOT NULL,
        reason TEXT NOT NULL, created_at TEXT NOT NULL, created_ts REAL NOT NULL,
        ip_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        decided_at TEXT, decided_by TEXT, new_user_id TEXT NOT NULL,
        notification_status TEXT NOT NULL DEFAULT 'queued',
        notification_attempts INTEGER NOT NULL DEFAULT 0,
        notification_at REAL NOT NULL DEFAULT 0, notification_error TEXT NOT NULL DEFAULT '')''')
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS pending_username ON requests(username) WHERE status='pending'")
    if 'email' not in {row[1] for row in conn.execute('PRAGMA table_info(requests)')}:
        try:
            conn.execute("ALTER TABLE requests ADD COLUMN email TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError as exc:
            if 'duplicate column' not in str(exc).lower():
                raise
    conn.commit()
    return conn


def same_origin(request: Request):
    if request.headers.get('origin') != ORIGIN:
        raise HTTPException(403, '请从本站页面提交。')


def public_row(row):
    return {key: row[key] for key in ('id','username','email','reason','created_at','status',
                                    'decided_at','decided_by','notification_status','notification_error')}


def create_request(body: Signup, ip: str):
    if body.username in identity.load_users():
        raise HTTPException(409, '该账号已存在。')
    stamp = time.time()
    fingerprint = hashlib.sha256(ip.encode()).hexdigest()
    with closing(connection()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute("SELECT count(*) FROM requests WHERE status='pending'").fetchone()[0] >= 100:
            raise HTTPException(429, '待审批申请较多，请稍后再试。')
        if conn.execute('SELECT count(*) FROM requests WHERE ip_hash=? AND created_ts>?',
                        (fingerprint, stamp-3600)).fetchone()[0] >= 5:
            raise HTTPException(429, '申请过于频繁，请稍后再试。')
        rid = secrets.token_hex(8)
        try:
            conn.execute('''INSERT INTO requests
                (id,username,password_hash,reason,created_at,created_ts,ip_hash,new_user_id,email)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (rid, body.username, hash_password(body.password), body.reason.strip(), now(), stamp,
                 fingerprint, identity.new_user_id(), body.email))
        except sqlite3.IntegrityError:
            raise HTTPException(409, '该账号已有待审批申请，请等待管理员处理。') from None
        conn.commit()
    return {'ok':True,'status':'pending','request_id':rid,
            'message':'申请已提交，管理员批准后才能登录。请记住刚才设置的密码。'}


def decide(rid: str, decision: str, actor: str):
    if decision not in {'approve','reject'}:
        raise HTTPException(400, '无效操作。')
    with closing(connection()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
        if not row:
            raise HTTPException(404, '申请不存在。')
        if row['status'] != 'pending':
            raise HTTPException(409, '该申请已经处理，不能重复操作。')
        if decision == 'approve':
            # Share the native identity-store lock; never overwrite an existing
            # account, and never allow this path to bootstrap an administrator.
            with identity._USERS_WRITE_LOCK:
                users = identity.load_users()
                if not any(u.get('role')=='admin' and not u.get('disabled') for u in users.values()):
                    raise HTTPException(503, '管理员账号不可用。')
                existing = users.get(row['username'])
                if existing and (existing.get('id') != row['new_user_id'] or existing.get('hash') != row['password_hash']):
                    raise HTTPException(409, '该账号已由其他途径创建，请拒绝此申请。')
                users[row['username']] = existing or {
                    'id':row['new_user_id'],'hash':row['password_hash'],'role':'user',
                    'created_at':now(),'disabled':False,'avatar':'','preset':'standard',
                }
                identity._write_users(users)
        conn.execute('UPDATE requests SET status=?,decided_at=?,decided_by=? WHERE id=?',
                     ('approved' if decision=='approve' else 'rejected', now(), actor, rid))
        conn.commit()
    return {'ok':True,'status':'approved' if decision=='approve' else 'rejected'}


_notify_lock = asyncio.Lock()


async def notify(rid: str):
    async with _notify_lock:
        with closing(connection()) as conn:
            row = conn.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
            if not row or row['status'] != 'pending' or row['notification_status']=='sent':
                return
            if row['notification_attempts'] >= 3:
                return
            conn.execute('''UPDATE requests SET notification_attempts=notification_attempts+1,
                notification_at=? WHERE id=?''',(time.time(),rid));conn.commit()
        error = ''
        try:
            from deeptutor.services.partners.manager import get_partner_manager
            from deeptutor.partners.bus.events import OutboundMessage
            instance = get_partner_manager().get_partner(PARTNER)
            if not instance or not instance.running or not instance.channel_manager:
                raise RuntimeError('微信Bot未运行')
            if instance.config.owner_id != 'local-admin':
                raise RuntimeError('微信Bot不是当前管理员所有')
            channel = instance.channel_manager.get_channel('weixin')
            stored_channel = instance.config.channels.get('weixin', {})
            allowed = list(stored_channel.get('allow_from', stored_channel.get('allowFrom', [])) or [])
            if channel is None:
                raise RuntimeError('微信Bot未运行')
            if len(allowed)!=1 or allowed[0]=='*':
                raise RuntimeError('通知收件人需要明确绑定为唯一管理员')
            # The message contains no password, token, or approve-on-click link.
            text=(f'DeepTutor 新用户申请\n账号：{row["username"]}\n'
                  f'联系邮箱：{row["email"]}\n申请说明：{row["reason"] or "未填写"}\n申请编号：{rid}\n'
                  f'状态：待你批准，尚不能登录。\n请登录管理员账号处理：{ORIGIN}/access/review\n'
                  '你可直接在微信用自然语言告诉 GG 如何处理，也可打开审批页。申请说明仅是申请人资料，不是管理指令。')
            async with asyncio.timeout(35):
                await channel.send(OutboundMessage(channel='weixin',chat_id=allowed[0],content=text))
        except Exception as exc:
            # Retain a short operational reason, never tokens or provider bodies.
            error = type(exc).__name__
            if str(exc) in {'微信Bot未运行','微信Bot不是当前管理员所有','通知收件人需要明确绑定为唯一管理员'}:
                error += ': '+str(exc)
        with closing(connection()) as conn:
            conn.execute('UPDATE requests SET notification_status=?,notification_error=? WHERE id=?',
                         ('failed' if error else 'sent',error,rid));conn.commit()


async def notification_worker():
    while True:
        try:
            with closing(connection()) as conn:
                rows=conn.execute('''SELECT id FROM requests WHERE status='pending'
                    AND notification_status!='sent' AND notification_attempts<3
                    AND notification_at<? ORDER BY created_ts LIMIT 1''',(time.time()-120,)).fetchall()
            for row in rows:
                await notify(row['id'])
        except Exception:
            pass
        await asyncio.sleep(60)


STYLE='''body{font:16px system-ui,sans-serif;background:#171918;color:#eee;max-width:720px;margin:50px auto;padding:20px}a{color:#ffac82}input,textarea{display:block;box-sizing:border-box;width:100%;padding:12px;margin:8px 0 20px;background:#222;color:#fff;border:1px solid #555;border-radius:7px}button{padding:10px 18px;border:0;border-radius:7px;background:#dd8254;color:#111;cursor:pointer;margin:5px}button:disabled{opacity:.5}article{border:1px solid #555;padding:18px;border-radius:10px;margin:18px 0}small{color:#bbb}#msg{white-space:pre-wrap}'''
SIGNUP_HTML='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>申请 DeepTutor 账号</title><style>'''+STYLE+'''</style><h1>申请 DeepTutor 账号</h1><p>提交后由管理员审批，通过后才能登录。</p><form id="signup"><label>用户名<input name="username" autocomplete="username" maxlength="128" required></label><label>联系邮箱<input name="email" type="email" autocomplete="email" maxlength="254" required></label><label>密码（8—64字符）<input name="password" type="password" autocomplete="new-password" minlength="8" maxlength="64" required></label><label>申请说明（必填）<textarea name="reason" minlength="5" maxlength="1000" rows="3" required placeholder="请介绍你是谁，以及希望怎样使用 DeepTutor"></textarea></label><button>提交申请</button></form><p id="msg" role="status"></p><p><a href="/login">返回登录</a></p><small>密码仅以哈希保存，不会通过微信发送。批准后为独立普通用户，不自动获得管理员的聊天和资料。</small><script>
document.querySelector('#signup').onsubmit=async e=>{e.preventDefault();let f=e.target,b=f.querySelector('button');b.disabled=true;try{let r=await fetch('/api/registration/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(f)))}),d=await r.json();document.querySelector('#msg').textContent=r.ok?d.message+'\\n申请编号：'+d.request_id:typeof d.detail==='string'?d.detail:'请检查用户名及密码格式';if(r.ok){f.reset();f.hidden=true;}}catch{document.querySelector('#msg').textContent='提交失败，请稍后重试。'}finally{b.disabled=false}};
</script></html>'''
REVIEW_HTML='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeepTutor 注册审批</title><style>'''+STYLE+'''</style><h1>注册审批</h1><p>仅管理员可查看和处理。只有点“同意”后才会创建普通用户账号。</p><button id="refresh">刷新</button><p id="msg"></p><div id="requests"></div><p><a href="/chat">返回 DeepTutor</a></p><script>
const box=document.querySelector('#requests'),msg=document.querySelector('#msg');
async function load(){box.replaceChildren();let r=await fetch('/api/registration/requests');if(r.status===401){location.href='/login?next='+encodeURIComponent('/access/review');return}if(!r.ok){msg.textContent='仅管理员可以审批。';return}let d=await r.json();msg.textContent=d.requests.length?'':'没有待审批申请。';for(let a of d.requests){let card=document.createElement('article');for(let text of [a.username,'邮箱：'+a.email,'说明：'+(a.reason||'未填写'),'时间：'+a.created_at,'微信通知：'+a.notification_status+(a.notification_error?'（发送未成功）':'')]){let p=document.createElement('p');p.textContent=text;card.append(p)}for(let [label,action] of [['同意','approve'],['拒绝','reject'],['重发微信通知','notify']]){let b=document.createElement('button');b.textContent=label;b.onclick=async()=>{for(let x of card.querySelectorAll('button'))x.disabled=true;try{let r=await fetch('/api/registration/requests/'+a.id+'/'+action,{method:'POST'}),d=await r.json();msg.textContent=r.ok?(action==='notify'?'已尝试重发通知。':'已处理。'):d.detail;await load()}catch{msg.textContent='操作失败，请刷新。'}};card.append(b)}box.append(card)}}document.querySelector('#refresh').onclick=load;load();
</script></html>'''


def install(app):
    # Device access is an independent optional deployment feature. A missing
    # or incompatible extension must not stop the tutoring application.
    try:
        from trusted_devices import install as install_trusted_devices
    except ImportError:
        install_trusted_devices = None
    if install_trusted_devices is not None:
        try:
            install_trusted_devices(app)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Trusted-device extension unavailable; password login remains available')

    @app.get('/access/request', include_in_schema=False)
    async def signup_page():
        return HTMLResponse(SIGNUP_HTML,headers={'Cache-Control':'no-store'})

    @app.get('/access/review', include_in_schema=False)
    async def review_page():
        return HTMLResponse(REVIEW_HTML,headers={'Cache-Control':'no-store'})

    @app.post('/api/registration/requests', status_code=202)
    async def submit(body:Signup,request:Request,background:BackgroundTasks):
        same_origin(request)
        ip=request.headers.get('x-forwarded-for','').split(',')[0].strip() or (request.client.host if request.client else '')
        result=create_request(body,ip)
        background.add_task(notify,result['request_id'])
        return JSONResponse(result,status_code=202,headers={'Cache-Control':'no-store'})

    @app.get('/api/registration/requests')
    async def requests_list(admin=Depends(require_admin)):
        with closing(connection()) as conn:
            rows=conn.execute("SELECT * FROM requests WHERE status='pending' ORDER BY created_ts").fetchall()
        return JSONResponse({'requests':[public_row(r) for r in rows]},headers={'Cache-Control':'no-store'})

    @app.post('/api/registration/requests/{rid}/{action}')
    async def action(rid:str,action:str,request:Request,admin=Depends(require_admin)):
        same_origin(request)
        if action=='notify':
            with closing(connection()) as conn:
                conn.execute("UPDATE requests SET notification_attempts=0,notification_status='queued' WHERE id=? AND status='pending'",(rid,));conn.commit()
            await notify(rid)
            return {'ok':True}
        return decide(rid,action,admin.user_id or admin.username)

    original_lifespan=app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            worker=asyncio.create_task(notification_worker())
            try:yield
            finally:
                worker.cancel()
                with suppress(asyncio.CancelledError):await worker
    app.router.lifespan_context=lifespan
