"""Community actions; no model loop and no platform credentials are owned here."""
from __future__ import annotations

import asyncio
import logging

from . import native
from .store import CommunityError

logger = logging.getLogger(__name__)
_tasks = set()


class CommunityService:
    def __init__(self, store=None, integration=native):
        self.native = integration
        self.store = store if store is not None else integration.repository()

    def user(self):
        return self.native.actor()

    def membership(self, community_id, *, active=True):
        user = self.user()
        self.store.require_member(community_id, user.id, active=False)
        links = self.native.bindings(user.id, self.store)
        self.store.set_bound(community_id, user.id, bool(links))
        return self.store.require_member(community_id, user.id, active=active)

    async def create(self, partner_id, title, create_partner=False):
        user = self.user()
        if create_partner and not self.native.exists(partner_id):
            await self.native.create_partner(partner_id, title)
        if not self.native.can_manage(partner_id):
            raise CommunityError('需要该Partner的管理权限。', 403)
        if not self.native.profile_safe(partner_id):
            raise CommunityError('请使用独立社区Partner：不绑定私人工作区，关闭通用执行工具和MCP。', 409)
        self.store.create(partner_id, title, user.id, user.username)
        self.membership(partner_id, active=False)
        return {'id': partner_id}

    def home(self):
        user = self.user()
        memberships = self.store.memberships(user.id)
        for member in memberships:
            self.membership(member['id'], active=False)
        return {'communities': self.store.memberships(user.id),
                'bindings': self.native.bindings(user.id, self.store),
                'connectors': self.native.connectors(user.id, self.store),
                'deliveries': self.store.delivery_rows(user.id)}

    def detail(self, community_id):
        user = self.user()
        member = self.membership(community_id, active=False)
        active = member['status'] == 'active'
        return {'community':self.store.info(community_id), 'membership':member,
                'posts':self.store.feed(community_id, user.id) if active else [],
                'members':self.store.members(community_id) if member['role']=='owner' else [],
                'subscriptions':self.store.subscriptions(community_id, user.id)}

    def invite(self, community_id):
        user = self.user()
        self.membership(community_id, active=False)
        return self.store.invite(community_id, user.id)

    def accept(self, token):
        user = self.user()
        community_id = self.store.accept(token, user.id, user.username)
        self.membership(community_id, active=False)
        return {'id':community_id, 'membership':self.store.member(community_id, user.id)}

    def link_code(self, connector_id):
        user = self.user()
        return self.native.issue_code(connector_id, user.id, self.store)

    def subscribe(self, community_id, binding, enabled):
        user = self.user()
        self.membership(community_id)
        match = next((row for row in self.native.bindings(user.id, self.store)
                      if all(row.get(key)==binding.get(key) for key in ('connector_id','channel','sender_id'))), None)
        if match is None:
            raise CommunityError('只能订阅本人已验证的通道。', 403)
        self.store.subscribe(community_id, user.id, match['connector_id'], match['channel'], match['sender_id'], enabled)
        return {'ok':True}

    async def preview(self, community_id, text='', *, workspace_id='', session_id='', message_ids=None):
        user = self.user()
        self.membership(community_id)
        source = {'kind':'manual'}
        if session_id:
            selected = await self.native.source_messages(workspace_id, session_id, message_ids)
            text, source = selected['content'], selected['source']
        return self.store.draft(community_id, user.id, text, source)

    def publish(self, community_id, draft_id, command_id, notify=False):
        user = self.user()
        self.membership(community_id)
        return self.store.publish(community_id, user.id, draft_id, command_id, notify=notify)

    async def drain(self, budget=4):
        examined = 0
        for _ in range(budget):
            row = self.store.claim_delivery()
            if row is None:
                break
            examined += 1
            if row.get('waiting'):
                continue
            status, detail = 'revoked', '订阅或成员权限已撤销。'
            try:
                with self.native.as_user(row['user_id']):
                    links = self.native.bindings(row['user_id'], self.store)
                    linked = any(all(link.get(key)==row.get(key) for key in ('connector_id','channel','sender_id')) for link in links)
                    if self.store.delivery_authorized(row) and linked:
                        text = '【'+row['title']+'】'+row['author_label']+'分享：\n'+row['content'][:1500]
                        if len(row['content'])>1500:
                            text += '\n（全文请在社区页面查看）'
                        await asyncio.wait_for(self.native.send(row, text), timeout=45)
                        status, detail = 'accepted', '平台发送接口已返回成功；不代表对方已阅读。'
            except CommunityError as exc:
                status, detail = 'awaiting_context', str(exc)
            except asyncio.CancelledError:
                self.store.finish_delivery(row['id'], row['attempt_id'], 'unknown', '发送中断，平台是否接收尚未确认；不会自动重发。')
                raise
            except asyncio.TimeoutError:
                self.store.finish_delivery(row['id'], row['attempt_id'], 'unknown', '发送超时，平台是否接收尚未确认；不会自动重发。')
                continue
            except Exception:
                # Provider exceptions may contain credentials; do not export them to a receipt.
                logger.warning('Community delivery failed (%s).', row['id'])
                status, detail = 'unknown', '平台响应未能确认；请先核对接收端，系统不会自动重发。'
            self.store.finish_delivery(row['id'], row['attempt_id'], status, detail)
        return examined


def schedule_delivery():
    # Explicitly consented pending intents also resume when the page is opened.
    if _tasks:
        return
    async def pump():
        service = CommunityService()
        while await service.drain(budget=16) == 16:
            await asyncio.sleep(0)
    task = asyncio.create_task(pump())
    _tasks.add(task)
    def done(completed):
        _tasks.discard(completed)
        if not completed.cancelled() and completed.exception() is not None:
            logger.warning('Community delivery queue needs attention.')
    task.add_done_callback(done)
