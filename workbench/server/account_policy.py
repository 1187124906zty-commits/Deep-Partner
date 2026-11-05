"""Versioned per-account storage budgets, separate from the physical backend."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import shutil
import time

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

GIB=1024**3


def ensure(store):
    with store.db() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS account_storage_policies(
            owner TEXT PRIMARY KEY, quota_bytes INTEGER NOT NULL, cache_limit_bytes INTEGER NOT NULL,
            archive_quota_bytes INTEGER NOT NULL, revision INTEGER NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS account_storage_policy_events(
            id INTEGER PRIMARY KEY, owner TEXT NOT NULL, actor TEXT NOT NULL, created REAL NOT NULL,
            before_value TEXT NOT NULL, after_value TEXT NOT NULL, reason TEXT NOT NULL);''')


def policy(store,owner):
    ensure(store)
    with store.db() as db:row=db.execute('SELECT * FROM account_storage_policies WHERE owner=?',(owner,)).fetchone()
    return dict(row) if row else {'owner':owner,'quota_bytes':2*GIB,'cache_limit_bytes':512*1024**2,
        'archive_quota_bytes':0,'revision':0,'updated':None}


class PolicyUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=0)
    quota_bytes:int=Field(ge=0,le=1024**4)
    cache_limit_bytes:int=Field(ge=0,le=1024**4)
    archive_quota_bytes:int=Field(default=0,ge=0,le=1024**4)
    reason:str=Field(min_length=5,max_length=1000)


def update_policy(store,owner,actor,body):
    ensure(store)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM account_storage_policies WHERE owner=?',(owner,)).fetchone()
        before=dict(row) if row else {'owner':owner,'quota_bytes':2*GIB,'cache_limit_bytes':512*1024**2,
            'archive_quota_bytes':0,'revision':0,'updated':None}
        if before['revision']!=body.expected_revision:raise HTTPException(409,'配额已被更新，请刷新后再提交')
        value={'owner':owner,'quota_bytes':body.quota_bytes,'cache_limit_bytes':body.cache_limit_bytes,
            'archive_quota_bytes':body.archive_quota_bytes,'revision':before['revision']+1,'updated':time.time()}
        db.execute('INSERT OR REPLACE INTO account_storage_policies VALUES(?,?,?,?,?,?)',tuple(value.values()))
        db.execute('INSERT INTO account_storage_policy_events(owner,actor,created,before_value,after_value,reason) VALUES(?,?,?,?,?,?)',
            (owner,actor,time.time(),json.dumps(before),json.dumps(value),body.reason))
    return value


def physical_capacity(store):
    disk=shutil.disk_usage(store.root)
    reserve=int(os.environ.get('WORKBENCH_DISK_RESERVE_BYTES',str(2*GIB)))
    return {'total_bytes':disk.total,'free_bytes':disk.free,'reserve_bytes':reserve,
        'writable_bytes':max(0,disk.free-reserve),'accepting_writes':disk.free>reserve}


def check_write(store,owner,additional):
    from .workspace_files import usage
    value=usage(store,owner)
    amount=max(0,int(additional))
    if value['used']+amount>value['quota']:
        raise HTTPException(507,'当前账户工作台配额不足；已有文件可继续读取，请整理历史或申请扩容')
    if amount>physical_capacity(store)['writable_bytes']:
        raise HTTPException(507,'存储后端可用空间不足，已停止新增写入；已有文件保留')


def install(app,store,actor):
    ensure(store)

    @app.get('/research/api/storage/policy')
    async def own_policy(user=Depends(actor)):
        return {'policy':policy(store,user['id']),
            'enforcement_scope':'工作台经 require_space/Store.replace 保存的项目文件、稿件及历史；原生KB、Code与缓存全局硬配额尚未切换',
            'archive_state':'prepared_only','quota_update':'管理员按 revision 更新；下一次工作台写入立即生效'}

    async def administrator(user=Depends(actor)):
        if user.get('role')!='admin':raise HTTPException(403,'仅管理员可以分配存储配额')
        return user

    @app.get('/research/api/admin/storage/{owner}')
    async def inspect(owner:str,user=Depends(administrator)):
        return {'policy':policy(store,owner),'capacity':physical_capacity(store)}

    @app.put('/research/api/admin/storage/{owner}')
    async def assign(request:Request,owner:str,body:PolicyUpdate,user=Depends(administrator)):
        if not owner or len(owner)>120 or any(c in owner for c in '/\\\x00'):
            raise HTTPException(400,'账户标识无效')
        # Resolve against the authenticated native account list; no orphan allocations.
        from .native import call
        users=await call(request,'GET','/api/auth/users')
        if owner not in {str(row.get('id') or '') for row in users} | {str(user['id'])}:
            raise HTTPException(404,'账户不存在，请先完成账户创建')
        return update_policy(store,owner,user['id'],body)

    @app.get('/research/api/admin/storage/{owner}/history')
    async def history(owner:str,user=Depends(administrator)):
        with store.db() as db:
            rows=db.execute('SELECT id,actor,created,after_value,reason FROM account_storage_policy_events WHERE owner=? ORDER BY id DESC LIMIT 30',(owner,)).fetchall()
        return {'events':[{**dict(r),'after_value':json.loads(r['after_value'])} for r in rows]}
