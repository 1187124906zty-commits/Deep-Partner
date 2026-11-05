"""Durable delivery events; Dify owns routing and the periodic reconciliation."""
import asyncio
import json
import logging
import shutil
import os
from pathlib import Path
import secrets
import time
import uuid

import httpx
from fastapi import HTTPException

log = logging.getLogger(__name__)


class DeliveryAutomation:
    def __init__(self, service, config: Path):
        self.service, self.config = service, config
        with service.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS automation_events(
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                token TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                error TEXT, result TEXT, UNIQUE(run_id,fingerprint))""")
            db.execute("CREATE TABLE IF NOT EXISTS automation_checks(id INTEGER PRIMARY KEY, created REAL NOT NULL, result TEXT NOT NULL)")
            columns={r['name'] for r in db.execute('PRAGMA table_info(automation_events)')}
            if 'acknowledged' not in columns:
                db.execute('ALTER TABLE automation_events ADD COLUMN acknowledged REAL')
                db.execute('ALTER TABLE automation_events ADD COLUMN acknowledgement TEXT')

    @staticmethod
    def fingerprint(row):
        receipt = json.loads(row['receipt']) if row['receipt'] else {}
        return json.dumps([row['state'], row['workflow_run_id'], receipt.get('workflow_status'), row['error']], ensure_ascii=False)

    def enqueue(self, run_id):
        row = self.service.row(run_id)
        if row['state'] not in {'saved', 'failed', 'interrupted'}:
            return
        now = time.time()
        with self.service.db() as db:
            db.execute("""INSERT OR IGNORE INTO automation_events
                (id,run_id,fingerprint,token,state,next_attempt,created,updated)
                VALUES(?,?,?,?,'queued',?,?,?)""",
                (uuid.uuid4().hex, run_id, self.fingerprint(row), secrets.token_urlsafe(24), now, now, now))

    def event(self, event_id, token):
        with self.service.db() as db:
            row = db.execute('SELECT * FROM automation_events WHERE id=?', (event_id,)).fetchone()
        if not row or not secrets.compare_digest(row['token'], token):
            raise HTTPException(404, '交付事件不存在或凭证不匹配')
        return dict(row)

    def inspect(self, event_id, token):
        event = self.event(event_id, token)
        row = self.service.row(event['run_id'])
        receipt = json.loads(row['receipt']) if row['receipt'] else {}
        if self.fingerprint(row) != event['fingerprint']:
            outcome, message = 'superseded', '该事件已被同一任务的新状态取代'
        elif (row['state'] == 'saved' and receipt.get('workflow_status') == 'succeeded'
                and receipt.get('processing_history_verified') is True):
            outcome, message = 'delivered', '成果保存、版本与原生处理记录已核验'
        else:
            outcome = 'attention_required'
            message = row['error'] or receipt.get('workflow_error') or '交付尚未取得完整的最终核验'
        return {'event_id': event_id, 'run_id': row['id'], 'project_id': row['project_id'],
            'outcome': outcome, 'ready': outcome == 'delivered', 'message': message,
            'artifact': receipt.get('artifact', {}).get('path', ''),
            'next_action': '' if outcome != 'attention_required' else '查询同一交付任务，刷新项目版本或检查服务后处理；不要重复覆盖成果',
            'scope': '成果交付；科学结论和计算质量以实际验证证据为准'}

    def settle(self, event_id, token, route):
        value = self.inspect(event_id, token)
        expected = 'success' if value['ready'] else 'attention'
        if route != expected:
            raise HTTPException(409, '事件分支与服务端实际状态不一致')
        now = time.time()
        with self.service.db() as db:
            db.execute("UPDATE automation_events SET state='completed',result=?,error=NULL,updated=? WHERE id=?",
                (json.dumps(value, ensure_ascii=False), now, event_id))
        return value

    def summary(self, run_id):
        with self.service.db() as db:
            row = db.execute('SELECT id,state,attempts,error,result,acknowledged,acknowledgement FROM automation_events WHERE run_id=? ORDER BY created DESC LIMIT 1', (run_id,)).fetchone()
        if not row:
            return {'state': 'not_queued'}
        return {**{k: row[k] for k in ('id','state', 'attempts', 'error','acknowledged','acknowledgement')},
            'result': json.loads(row['result']) if row['result'] else None}

    async def acknowledge(self,auth,run_id,reason):
        reason=reason.strip()
        if not 5<=len(reason)<=1000:raise HTTPException(400,'请说明已处理原因，5至1000字')
        row=self.service.row(run_id)
        if (await self.service.profile(auth))['id']!=row['owner']:raise HTTPException(404,'交付任务不存在')
        now=time.time()
        with self.service.db() as db:
            db.execute("UPDATE automation_events SET acknowledged=?,acknowledgement=? WHERE run_id=? AND (state='attention_required' OR json_extract(result,'$.outcome')='attention_required')",
                (now,reason,run_id))
        return {'run_id':run_id,'acknowledged':True,'reason':reason,'scope':'已记录问题的技术处理说明，不修改原始失败证据或批准科学结论'}

    async def dispatch(self):
        if not self.config.is_file():
            return
        endpoint = json.loads(self.config.read_text())['webhook_url']
        now = time.time()
        with self.service.db() as db:
            rows = db.execute("SELECT * FROM automation_events WHERE state IN ('queued','dispatched') AND next_attempt<=? ORDER BY created LIMIT 10", (now,)).fetchall()
        for event in rows:
            attempts = event['attempts'] + 1
            if attempts > 5:
                with self.service.db() as db:
                    db.execute("UPDATE automation_events SET state='attention_required',error='事件回调连续未完成，请检查 Dify 触发器运行日志',updated=? WHERE id=? AND state!='completed'", (now, event['id']))
                continue
            error = None
            try:
                async with httpx.AsyncClient(timeout=8, trust_env=False, transport=self.service.transport) as client:
                    response = await client.post(endpoint, json={'event_id': event['id'], 'event_token': event['token']})
                    response.raise_for_status()
                state = 'dispatched'  # HTTP acceptance is not workflow completion.
            except httpx.HTTPError as exc:
                state, error = 'queued', type(exc).__name__
            with self.service.db() as db:
                db.execute("UPDATE automation_events SET state=?,attempts=?,next_attempt=?,error=?,updated=? WHERE id=? AND state!='completed'",
                    (state, attempts, now + min(300, 15 * 2 ** attempts), error, now, event['id']))

    async def worker(self):
        while True:
            try:
                await self.dispatch()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('Delivery event dispatch failed; durable queue retained')
            await asyncio.sleep(2)

    async def reconcile(self):
        """Read terminal Dify state and flag interrupted work; never replay writes."""
        now = time.time()
        with self.service.db() as db:
            terminal=[r['id'] for r in db.execute("SELECT d.id FROM deliveries d WHERE d.state IN ('saved','failed','interrupted') AND NOT EXISTS (SELECT 1 FROM automation_events a WHERE a.run_id=d.id AND a.created>=d.updated) ORDER BY d.updated LIMIT 100")]
            rows = [dict(r) for r in db.execute("SELECT * FROM deliveries WHERE (state IN ('pending','prepared','written') AND updated<?) OR (state='saved' AND workflow_run_id IS NOT NULL) ORDER BY updated DESC LIMIT 50", (now - 600,))]
        for run_id in terminal:self.enqueue(run_id)
        reconciled, interrupted = 0, 0
        from delivery import workflow_receipt
        for row in rows:
            if row['receipt']:
                receipt = json.loads(row['receipt'])
                if receipt.get('workflow_status') not in {'unknown', None}:
                    continue
                try:
                    response = await self.service.request(self.service.dify_url, 'GET', '/v1/workflows/run/' + row['workflow_run_id'],
                        {'Authorization': 'Bearer ' + self.service.dify_key.read_text().strip()})
                    run = response.json()
                    if run.get('status') in {'succeeded','failed','stopped'}:
                        value = workflow_receipt(receipt, {'workflow_run_id': row['workflow_run_id'], 'data': run})
                        self.service.update(row['id'], receipt=json.dumps(value, ensure_ascii=False))
                        self.enqueue(row['id'])
                        reconciled += 1
                except (httpx.HTTPError, HTTPException, OSError):
                    pass  # Health and outstanding counts expose persistent failure below.
            else:
                self.service.update(row['id'], state='interrupted', error='交付超过十分钟仍无最终回执，请查询原任务；未自动重复写入')
                self.enqueue(row['id'])
                interrupted += 1

        async def probe(name, url):
            try:
                async with httpx.AsyncClient(timeout=5, trust_env=False, transport=self.service.transport) as client:
                    response = await client.get(url)
                return {'service': name, 'ready': response.status_code == 200, 'http_status': response.status_code}
            except httpx.HTTPError as exc:
                return {'service': name, 'ready': False, 'error': type(exc).__name__}
        health = await asyncio.gather(probe('workbench', self.service.workbench_url + '/health'),
            probe('tutor', self.service.native_url + '/health/ready'), probe('dify', self.service.dify_url + '/console/api/ping'))
        disk=shutil.disk_usage(self.service.state.parent)
        disk_reserve=int(os.environ.get('WORKBENCH_DISK_RESERVE_BYTES',str(2*1024**3)))
        capacity={'free_bytes':disk.free,'reserve_bytes':disk_reserve,'accepting_writes':disk.free>disk_reserve,
            'scope':'公网服务器所在文件系统；集群账户可分配总额尚未核定'}
        with self.service.db() as db:
            pending = db.execute("SELECT COUNT(*) FROM automation_events WHERE state!='completed'").fetchone()[0]
            attention = db.execute("SELECT COUNT(*) FROM automation_events a WHERE acknowledged IS NULL AND (state='attention_required' OR (state='completed' AND json_extract(result,'$.outcome')='attention_required')) AND NOT EXISTS (SELECT 1 FROM automation_events b WHERE b.run_id=a.run_id AND b.created>a.created)").fetchone()[0]
        value = {'checked_at': now, 'reconciled': reconciled, 'interrupted': interrupted,
            'pending_events': pending, 'attention_events': attention, 'health': health,
            'needs_attention': attention > 0 or interrupted > 0 or not all(p['ready'] for p in health) or not capacity['accepting_writes'],
            'storage_capacity':capacity,
            'scope': '交付状态与服务可达性；不证明外部搜索源或全部业务功能稳定'}
        with self.service.db() as db:
            db.execute('INSERT INTO automation_checks(created,result) VALUES(?,?)', (now,json.dumps(value,ensure_ascii=False)))
        return value

    async def activity(self, auth, project_id, workspace_id=''):
        project = await self.service.project(auth, project_id, workspace_id)
        owner = (await self.service.profile(auth))['id']
        with self.service.db() as db:
            rows = db.execute('SELECT id,state,updated,error FROM deliveries WHERE owner=? AND project_id=? ORDER BY updated DESC LIMIT 20', (owner,project['id'])).fetchall()
            check = db.execute('SELECT result FROM automation_checks ORDER BY created DESC LIMIT 1').fetchone()
        return {'project_id': project['id'], 'deliveries': [{**dict(row),'automation':self.summary(row['id'])} for row in rows],
            'last_service_check': json.loads(check[0]) if check else None}
