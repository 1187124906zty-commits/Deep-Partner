"""One optional native Partner ingress hook; ordinary partners keep their loop."""
from __future__ import annotations

from . import native
from .service import CommunityService, schedule_delivery
from .store import CommunityError

HELP = ('社区命令（仅在私聊使用）：\n/community list\n/community feed <社区ID>\n'
        '/community post <社区ID> <要分享的正文>\n/community subscribe <社区ID>\n'
        '/community unsubscribe <社区ID>\n'
        '会话片段请在站内社区页面预览后发布。只有已邀请、已绑定的成员能访问内容。')


async def handle_inbound(connector_id, msg):
    """Return a command reply, or None to continue the original native Harness."""
    path = native.store_path()
    if not path.is_file():
        return None
    service = CommunityService()
    own_community = service.store.exists(connector_id)
    text = str(msg.content or '').strip()
    command = text.split(None, 1)[0].lower().split('@', 1)[0] if text else ''
    community_command = command == '/community'
    group = bool((msg.metadata or {}).get('is_group') or (msg.metadata or {}).get('chat_type') == 'group')
    if group:
        return '社区成员身份和收件箱请在Bot私聊中使用；当前群聊尚未绑定为社区目的地。' if own_community or community_command else None
    if msg.channel not in {'weixin', 'qq'}:
        return None
    # The native single-use link command remains the identity proof.
    if command == '/link':
        return None
    user_id = native.sender_user(connector_id, msg.channel, msg.sender_id)
    if not user_id:
        return '请先登录站内社区，接受邀请并领取绑定码，在本私聊发送 /link 绑定码。' if own_community or community_command else None
    try:
        with native.as_user(user_id):
            links = native.bindings(user_id, service.store)
            current = next((row for row in links if row['connector_id']==connector_id and row['channel']==msg.channel and row['sender_id']==msg.sender_id), None)
            if current is None:
                return '此Bot连接尚未获得你的社区访问权限。' if own_community or community_command else None
            service.store.record_peer(connector_id, msg.channel, msg.sender_id, str((msg.metadata or {}).get('message_id') or ''))
            if own_community:
                service.membership(connector_id)
                if not native.profile_safe(connector_id):
                    return '社区Partner配置已改变，请管理员恢复独立社区配置后继续。'
            if not community_command:
                if own_community and command in {'/tool','/model'} and not native.can_manage(connector_id):
                    return '社区成员不能更改Partner的模型或工具配置。'
                schedule_delivery()
                return None
            parts = text.split(None, 3)
            action = parts[1].lower() if len(parts)>1 else 'help'
            if action in {'help','帮助'}:
                return HELP
            if action == 'list':
                home = service.home()
                return '\n'.join(row['id']+' · '+row['title']+' · '+row['status'] for row in home['communities']) or '尚未加入社区，请先接受邀请。'
            if len(parts)<3:
                return HELP
            community_id = parts[2]
            service.membership(community_id)
            if action == 'feed':
                rows = service.store.feed(community_id, user_id, limit=5)
                reply = '\n\n'.join(row['author_label']+'：'+row['content'][:450] for row in reversed(rows)) or '社区还没有共享内容。'
            elif action == 'post':
                if len(parts)<4:
                    return '请在社区ID后写出你要公开给成员的正文。'
                draft = await service.preview(community_id, parts[3])
                message_id = str((msg.metadata or {}).get('message_id') or '')
                if not message_id:
                    return '此通道未提供稳定消息身份，请在站内预览后发布。'
                command_id = 'im:'+connector_id+':'+msg.channel+':'+message_id
                result = service.publish(community_id, draft['id'], command_id, notify=True)
                reply = '已发布到社区，编号 '+result['id']+'。订阅成员的通道状态可在站内查看。'
            elif action in {'subscribe','unsubscribe'}:
                service.subscribe(community_id, current, action=='subscribe')
                reply = '已订阅本私聊的社区更新。' if action=='subscribe' else '已关闭本私聊的社区更新。'
            else:
                return HELP
            schedule_delivery()
            return reply
    except CommunityError as exc:
        return str(exc) if own_community or community_command else None

