"""Durable community membership, reviewed publications and delivery intents."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid


class CommunityError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _text(value, maximum=12000):
    value = str(value or '').strip()
    if not value or len(value) > maximum:
        raise CommunityError(f'内容不能为空，且不能超过{maximum}字。')
    return value


class CommunityStore:
    """All operations name both the community and the authenticated human."""

    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] not in {0,1}:
                raise CommunityError('社区数据版本超出当前模块支持范围，请使用对应版本。', 409)
            db.executescript('''
            CREATE TABLE IF NOT EXISTS communities(
              id TEXT PRIMARY KEY,title TEXT NOT NULL,owner_id TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS members(
              community_id TEXT NOT NULL,user_id TEXT NOT NULL,label TEXT NOT NULL,role TEXT NOT NULL,
              status TEXT NOT NULL,joined REAL NOT NULL,PRIMARY KEY(community_id,user_id),
              FOREIGN KEY(community_id) REFERENCES communities(id));
            CREATE TABLE IF NOT EXISTS invites(
              token_digest TEXT PRIMARY KEY,community_id TEXT NOT NULL,created_by TEXT NOT NULL,
              expires REAL NOT NULL,used_by TEXT,FOREIGN KEY(community_id) REFERENCES communities(id));
            CREATE TABLE IF NOT EXISTS drafts(
              id TEXT PRIMARY KEY,community_id TEXT NOT NULL,author_id TEXT NOT NULL,content TEXT NOT NULL,
              source_json TEXT NOT NULL,expires REAL NOT NULL,post_id TEXT);
            CREATE TABLE IF NOT EXISTS posts(
              id TEXT PRIMARY KEY,community_id TEXT NOT NULL,author_id TEXT NOT NULL,author_label TEXT NOT NULL,
              content TEXT NOT NULL,source_json TEXT NOT NULL,created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS community_feed ON posts(community_id,created,id);
            CREATE TABLE IF NOT EXISTS publications(
              command_id TEXT NOT NULL,user_id TEXT NOT NULL,draft_id TEXT NOT NULL,post_id TEXT NOT NULL,
              notify INTEGER NOT NULL,
              PRIMARY KEY(command_id,user_id));
            CREATE TABLE IF NOT EXISTS subscriptions(
              community_id TEXT NOT NULL,user_id TEXT NOT NULL,connector_id TEXT NOT NULL,
              channel TEXT NOT NULL,sender_id TEXT NOT NULL,enabled INTEGER NOT NULL,
              PRIMARY KEY(community_id,user_id,connector_id,channel,sender_id));
            CREATE TABLE IF NOT EXISTS peer_receipts(
              connector_id TEXT NOT NULL,channel TEXT NOT NULL,sender_id TEXT NOT NULL,
              message_id TEXT NOT NULL,received REAL NOT NULL,replies_used INTEGER NOT NULL,
              PRIMARY KEY(connector_id,channel,sender_id));
            CREATE TABLE IF NOT EXISTS deliveries(
              id TEXT PRIMARY KEY,post_id TEXT NOT NULL,community_id TEXT NOT NULL,user_id TEXT NOT NULL,
              connector_id TEXT NOT NULL,channel TEXT NOT NULL,sender_id TEXT NOT NULL,
              status TEXT NOT NULL,attempt_id TEXT,updated REAL NOT NULL,detail TEXT NOT NULL DEFAULT '',
              UNIQUE(post_id,user_id,connector_id,channel,sender_id));
            CREATE INDEX IF NOT EXISTS delivery_queue ON deliveries(status,updated);
            PRAGMA user_version=1;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    def exists(self, community_id):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM communities WHERE id=?', (community_id,)).fetchone() is not None

    def info(self, community_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM communities WHERE id=?', (community_id,)).fetchone()
            return dict(row) if row else None

    def create(self, community_id, title, owner_id, label):
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM communities WHERE id=?', (community_id,)).fetchone():
                raise CommunityError('该Partner已经有社区。', 409)
            db.execute('INSERT INTO communities VALUES(?,?,?,?)',
                       (community_id, _text(title, 100), owner_id, self.clock()))
            db.execute('INSERT INTO members VALUES(?,?,?,?,?,?)',
                       (community_id, owner_id, label, 'owner', 'pending_link', self.clock()))

    def member(self, community_id, user_id, *, db=None):
        if db is None:
            with self.connect() as connection:
                return self.member(community_id, user_id, db=connection)
        row = db.execute('SELECT * FROM members WHERE community_id=? AND user_id=?',
                         (community_id, user_id)).fetchone()
        return dict(row) if row else None

    def require_member(self, community_id, user_id, *, db=None, active=True):
        member = self.member(community_id, user_id, db=db)
        if not member or member['status'] == 'revoked':
            raise CommunityError('需要有效社区邀请。', 403)
        if active and member['status'] != 'active':
            raise CommunityError('请先绑定本人微信或QQ账号。', 403)
        return member

    def set_bound(self, community_id, user_id, bound):
        with self.transaction() as db:
            self.require_member(community_id, user_id, db=db, active=False)
            db.execute("UPDATE members SET status=? WHERE community_id=? AND user_id=?",
                       ('active' if bound else 'pending_link', community_id, user_id))

    def memberships(self, user_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT c.*,m.role,m.status FROM communities c
                 JOIN members m ON c.id=m.community_id WHERE m.user_id=? AND m.status!='revoked'
                 ORDER BY c.created''', (user_id,))]

    def members(self, community_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT user_id,label,role,status,joined FROM members WHERE community_id=? ORDER BY joined', (community_id,))]

    def invite(self, community_id, user_id):
        token = secrets.token_urlsafe(24)
        expires = self.clock() + 7 * 86400
        with self.transaction() as db:
            member = self.require_member(community_id, user_id, db=db, active=False)
            if member['role'] != 'owner':
                raise CommunityError('只有社区创建者可以邀请成员。', 403)
            db.execute('INSERT INTO invites VALUES(?,?,?,?,NULL)',
                       (hashlib.sha256(token.encode()).hexdigest(), community_id, user_id, expires))
        return {'token': token, 'expires_at': expires}

    def accept(self, token, user_id, label):
        digest = hashlib.sha256(str(token).encode()).hexdigest()
        with self.transaction() as db:
            row = db.execute('SELECT * FROM invites WHERE token_digest=?', (digest,)).fetchone()
            if not row or row['used_by'] is not None or row['expires'] <= self.clock():
                raise CommunityError('邀请已使用或过期。', 409)
            community_id = row['community_id']
            old = self.member(community_id, user_id, db=db)
            role = old['role'] if old and old['role'] == 'owner' else 'member'
            db.execute('''INSERT INTO members VALUES(?,?,?,?,?,?) ON CONFLICT(community_id,user_id)
                      DO UPDATE SET label=excluded.label,status='pending_link',role=excluded.role''',
                       (community_id, user_id, label, role, 'pending_link', self.clock()))
            db.execute('UPDATE invites SET used_by=? WHERE token_digest=?', (user_id, digest))
        return community_id

    def revoke(self, community_id, owner_id, user_id):
        with self.transaction() as db:
            owner = self.require_member(community_id, owner_id, db=db, active=False)
            if owner['role'] != 'owner' or owner_id == user_id:
                raise CommunityError('只有社区创建者可以移除其他成员。', 403)
            db.execute("UPDATE members SET status='revoked' WHERE community_id=? AND user_id=?", (community_id, user_id))
            db.execute('UPDATE subscriptions SET enabled=0 WHERE community_id=? AND user_id=?', (community_id, user_id))
            db.execute("UPDATE deliveries SET status='revoked',updated=? WHERE community_id=? AND user_id=? AND status IN ('pending','awaiting_context')",
                       (self.clock(), community_id, user_id))

    def draft(self, community_id, user_id, content, source=None):
        content = _text(content)
        with self.transaction() as db:
            self.require_member(community_id, user_id, db=db)
            draft_id = uuid.uuid4().hex
            db.execute('INSERT INTO drafts VALUES(?,?,?,?,?,?,NULL)',
                       (draft_id, community_id, user_id, content, json.dumps(source or {}, ensure_ascii=False), self.clock()+1800))
        return {'id': draft_id, 'content': content, 'source': source or {}, 'expires_in': 1800}

    def publish(self, community_id, user_id, draft_id, command_id, *, notify=False):
        if not command_id or len(command_id) > 160:
            raise CommunityError('需要稳定的发布请求编号。')
        with self.transaction() as db:
            member = self.require_member(community_id, user_id, db=db)
            previous = db.execute('SELECT * FROM publications WHERE command_id=? AND user_id=?', (command_id, user_id)).fetchone()
            draft = db.execute('SELECT * FROM drafts WHERE id=? AND community_id=? AND author_id=?',
                               (draft_id, community_id, user_id)).fetchone()
            if previous:
                original = db.execute('SELECT * FROM drafts WHERE id=?', (previous['draft_id'],)).fetchone()
                if not draft or not original or bool(previous['notify']) != bool(notify) or any(
                    draft[key] != original[key] for key in ('community_id','author_id','content','source_json')):
                    raise CommunityError('同一发布编号不能用于不同内容。', 409)
                return {'id': previous['post_id'], 'deduplicated': True}
            if not draft or draft['expires'] <= self.clock():
                raise CommunityError('预览已过期，请重新预览。', 409)
            post_id = draft['post_id'] or uuid.uuid4().hex
            if not draft['post_id']:
                db.execute('INSERT INTO posts VALUES(?,?,?,?,?,?,?)',
                           (post_id, community_id, user_id, member['label'], draft['content'], draft['source_json'], self.clock()))
                db.execute('UPDATE drafts SET post_id=? WHERE id=?', (post_id, draft_id))
                if notify:
                    for subscription in db.execute('''SELECT s.* FROM subscriptions s JOIN members m
                         ON s.community_id=m.community_id AND s.user_id=m.user_id
                         WHERE s.community_id=? AND s.enabled=1 AND m.status='active' ''', (community_id,)).fetchall():
                        db.execute('''INSERT OR IGNORE INTO deliveries
                          (id,post_id,community_id,user_id,connector_id,channel,sender_id,status,updated)
                          VALUES(?,?,?,?,?,?,?,'pending',?)''',
                          (uuid.uuid4().hex, post_id, community_id, subscription['user_id'],
                           subscription['connector_id'], subscription['channel'], subscription['sender_id'], self.clock()))
            db.execute('INSERT INTO publications VALUES(?,?,?,?,?)', (command_id, user_id, draft_id, post_id, int(notify)))
        return {'id': post_id, 'deduplicated': bool(draft['post_id'])}

    def feed(self, community_id, user_id, limit=30):
        with self.connect() as db:
            self.require_member(community_id, user_id, db=db)
            rows = [dict(row) for row in db.execute('SELECT * FROM posts WHERE community_id=? ORDER BY created DESC,id DESC LIMIT ?',
                                                    (community_id, min(50, max(1, int(limit)))))]
        for row in rows:
            row['source'] = json.loads(row.pop('source_json'))
        return rows

    def subscribe(self, community_id, user_id, connector_id, channel, sender_id, enabled):
        if channel not in {'weixin', 'qq'} or not connector_id or not sender_id:
            raise CommunityError('请选择已验证的微信或QQ连接。')
        with self.transaction() as db:
            self.require_member(community_id, user_id, db=db)
            db.execute('''INSERT INTO subscriptions VALUES(?,?,?,?,?,?) ON CONFLICT
              (community_id,user_id,connector_id,channel,sender_id) DO UPDATE SET enabled=excluded.enabled''',
                       (community_id, user_id, connector_id, channel, sender_id, int(enabled)))
            if not enabled:
                db.execute("UPDATE deliveries SET status='revoked',updated=? WHERE community_id=? AND user_id=? AND connector_id=? AND channel=? AND sender_id=? AND status IN ('pending','awaiting_context')",
                           (self.clock(), community_id, user_id, connector_id, channel, sender_id))

    def subscriptions(self, community_id, user_id):
        with self.connect() as db:
            self.require_member(community_id, user_id, db=db, active=False)
            return [dict(row) for row in db.execute('SELECT connector_id,channel,sender_id,enabled FROM subscriptions WHERE community_id=? AND user_id=?', (community_id, user_id))]

    def record_peer(self, connector_id, channel, sender_id, message_id):
        with self.transaction() as db:
            db.execute('''INSERT INTO peer_receipts VALUES(?,?,?,?,?,0) ON CONFLICT(connector_id,channel,sender_id)
               DO UPDATE SET replies_used=CASE WHEN peer_receipts.message_id!=excluded.message_id
                 THEN 0 ELSE peer_receipts.replies_used END,
                 received=CASE WHEN peer_receipts.message_id!=excluded.message_id
                 THEN excluded.received ELSE peer_receipts.received END,
                 message_id=excluded.message_id''',
                       (connector_id, channel, sender_id, message_id or '', self.clock()))
            db.execute("UPDATE deliveries SET status='pending',updated=? WHERE connector_id=? AND channel=? AND sender_id=? AND status='awaiting_context'",
                       (self.clock(), connector_id, channel, sender_id))

    def delivery_rows(self, user_id, *, limit=50):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,post_id,community_id,connector_id,channel,status,detail,updated FROM deliveries WHERE user_id=? ORDER BY updated DESC LIMIT ?', (user_id, limit))]

    def claim_delivery(self):
        with self.transaction() as db:
            # The provider may have accepted a send before a process died.
            db.execute("UPDATE deliveries SET status='unknown',detail='进程中断，平台是否接收尚未确认。',updated=? WHERE status='sending' AND updated<?", (self.clock(), self.clock()-180))
            row = db.execute("SELECT d.*,p.content,p.author_label,c.title FROM deliveries d JOIN posts p ON p.id=d.post_id JOIN communities c ON c.id=d.community_id WHERE d.status='pending' ORDER BY d.updated,d.id LIMIT 1").fetchone()
            if row is None:
                return None
            receipt = db.execute('SELECT * FROM peer_receipts WHERE connector_id=? AND channel=? AND sender_id=?',
                                 (row['connector_id'], row['channel'], row['sender_id'])).fetchone()
            if (receipt is None or self.clock()-receipt['received'] > 240
                    or (row['channel']=='qq' and (not receipt['message_id'] or receipt['replies_used']>=2))):
                db.execute("UPDATE deliveries SET status='awaiting_context',detail='请先在对应微信/QQ私聊给Bot发一条消息。',updated=? WHERE id=?", (self.clock(), row['id']))
                return {'waiting': True}
            attempt = uuid.uuid4().hex
            db.execute("UPDATE deliveries SET status='sending',attempt_id=?,updated=? WHERE id=? AND status='pending'", (attempt, self.clock(), row['id']))
            db.execute('UPDATE peer_receipts SET replies_used=replies_used+1 WHERE connector_id=? AND channel=? AND sender_id=?',
                       (row['connector_id'],row['channel'],row['sender_id']))
            result = dict(row)
            result['attempt_id'] = attempt
            result['message_id'] = receipt['message_id']
            return result

    def finish_delivery(self, delivery_id, attempt_id, status, detail=''):
        if status not in {'accepted', 'unknown', 'failed', 'awaiting_context', 'revoked'}:
            raise CommunityError('无效的投递状态。')
        with self.transaction() as db:
            db.execute("UPDATE deliveries SET status=?,detail=?,updated=? WHERE id=? AND attempt_id=? AND status='sending'",
                       (status, str(detail)[:180], self.clock(), delivery_id, attempt_id))

    def delivery_authorized(self, row):
        with self.connect() as db:
            member = self.member(row['community_id'], row['user_id'], db=db)
            subscription = db.execute('''SELECT enabled FROM subscriptions WHERE community_id=? AND user_id=?
              AND connector_id=? AND channel=? AND sender_id=?''',
                                      (row['community_id'], row['user_id'], row['connector_id'], row['channel'], row['sender_id'])).fetchone()
            return bool(member and member['status']=='active' and subscription and subscription['enabled'])
