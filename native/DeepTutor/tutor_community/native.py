"""The only module that knows the installed Tutor identity and channel interfaces."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re

from .store import CommunityError, CommunityStore


def store_path():
    from deeptutor.partners.config.paths import get_data_dir
    return get_data_dir() / 'communities.sqlite3'


def repository():
    return CommunityStore(store_path())


def manager():
    from deeptutor.services.partners import get_partner_manager
    return get_partner_manager()


def actor():
    from deeptutor.multi_user.context import get_current_user
    from deeptutor.core.identities import is_partner_user_id
    user = get_current_user()
    if not getattr(user, 'id', '') or is_partner_user_id(user.id):
        raise CommunityError('请先登录自己的DeepTutor账号。', 401)
    return user


@contextmanager
def as_user(user_id):
    from deeptutor.multi_user.paths import user_context
    from deeptutor.services.partners.interaction import actor_for_account
    user = actor_for_account(user_id)
    if user is None:
        raise CommunityError('账号已不可用。', 403)
    with user_context(user):
        yield user


def exists(partner_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', str(partner_id)):
        raise CommunityError('Partner标识无效。')
    return manager().partner_exists(partner_id)


def can_manage(partner_id):
    from deeptutor.multi_user.partner_access import can_manage_partner
    return exists(partner_id) and can_manage_partner(partner_id)


def can_use(partner_id):
    from deeptutor.multi_user.partner_access import can_use_partner
    return exists(partner_id) and can_use_partner(partner_id)


def profile_safe(partner_id):
    config = manager().load_config(partner_id)
    return bool(config and not config.workspace_id and config.enabled_tools == []
                and config.builtin_tools == [] and config.mcp_tools == [])


async def create_partner(partner_id, title):
    # Reuse native validation, ownership and creation; never copy another bot's credentials.
    from deeptutor.api.routers.partners import CreatePartnerRequest, SoulSpec, create_partner as create
    return await create(CreatePartnerRequest(partner_id=partner_id, name=title,
        description='邀请成员的独立社区；只分享主动发布的内容。', workspace_id='',
        enabled_tools=[], builtin_tools=[], mcp_tools=[], channels={}, start=False,
        soul=SoulSpec(source='custom', content=(
            '# 社区伙伴\n你在独立社区空间中交流。只把已明确发布的内容视为社区共有资料。'
            '不读取或代发其他人的私人会话；社区命令由服务器处理。'))))


def link_rows(connector_id, user_id):
    from deeptutor.services.partners.links import list_links
    return [row for row in list_links(connector_id, user_id) if row.get('channel') in {'weixin', 'qq'}]


def sender_user(connector_id, channel, sender_id):
    from deeptutor.services.partners.links import linked_user_id
    return linked_user_id(connector_id, channel, sender_id)


def bindings(user_id, store):
    memberships = {row['id'] for row in store.memberships(user_id)}
    rows = []
    for partner in manager().list_partners():
        connector_id = partner['partner_id']
        # An invite grants community interaction, never management of its parent Partner.
        if not can_use(connector_id) and connector_id not in memberships:
            continue
        for row in link_rows(connector_id, user_id):
            rows.append({'connector_id': connector_id, 'connector_name': partner.get('name') or connector_id,
                         'channel': row['channel'], 'sender_id': row['sender_id'], 'key': row['key']})
    return rows


def issue_code(connector_id, user_id, store):
    member = store.member(connector_id, user_id)
    if not can_use(connector_id) and not (member and member['status'] != 'revoked' and profile_safe(connector_id)):
        raise CommunityError('请使用自己可访问的Partner连接。', 403)
    from deeptutor.services.partners.links import issue_link_code
    issued = issue_link_code(connector_id, user_id)
    return {'connector_id': connector_id, 'command': '/link '+issued.code, 'expires_at': issued.expires_at}


def unlink(connector_id, user_id, key):
    if not exists(connector_id):
        raise CommunityError('连接不存在。', 404)
    from deeptutor.services.partners.links import remove_link
    if not remove_link(connector_id, user_id, key):
        raise CommunityError('本人绑定记录不存在。', 404)
    return {'ok':True}


def source_workspaces():
    from deeptutor.services.workspace import get_content_workspace_service
    catalog = get_content_workspace_service().describe_catalog()
    items = catalog.get('workspaces', [])
    return [{'id':'','name':'默认空间'}] + [
        {'id':row['workspace_id'], 'name':row.get('display_name') or row.get('name') or row['workspace_id']}
        for row in items if row.get('workspace_id')]


def connectors(user_id, store):
    memberships = {row['id'] for row in store.memberships(user_id)}
    output = []
    for partner in manager().list_partners():
        pid = partner['partner_id']
        if not can_use(pid) and pid not in memberships:
            continue
        config = manager().load_config(pid)
        if config is None:
            continue
        channels = config.channels or {}
        output.append({'id': pid, 'name': config.name, 'manageable': can_manage(pid),
            'channels': {name: {'enabled': bool(value.get('enabled')),
                         'configured': bool(value.get('token')) if name == 'weixin'
                         else bool(value.get('app_id') and value.get('secret'))}
                         for name, value in channels.items() if name in {'weixin','qq'} and isinstance(value, dict)}})
    return output


async def source_messages(workspace_id, session_id='', selected_ids=None):
    from deeptutor.services.workspace import WorkspaceError, get_content_workspace_service
    from deeptutor.services.workspace.context import workspace_context
    from deeptutor.services.session import get_session_store
    actor()
    if workspace_id:
        try:
            get_content_workspace_service().validate_chat_binding(workspace_id)
        except WorkspaceError as exc:
            raise CommunityError('所选工作区不可访问，请重新选择。', 403) from exc
    with workspace_context(workspace_id):
        sessions = get_session_store()
        if not session_id:
            return [{'id': item.get('session_id') or item.get('id'), 'title': item.get('title') or ''}
                    for item in await sessions.list_sessions(limit=60)]
        session = await sessions.get_session(session_id)
        if session is None:
            raise CommunityError('会话不存在或不属于当前账户。', 404)
        rows = await sessions.get_messages(session_id)
    visible = []
    for row in rows:
        if row.get('role') in {'user', 'assistant'} and isinstance(row.get('content'), str) and row['content'].strip():
            visible.append({'id': str(row['id']), 'role': row['role'], 'content': row['content']})
    if selected_ids is None:
        return visible
    wanted = [str(value) for value in selected_ids]
    if not wanted or len(wanted) > 20 or len(set(wanted)) != len(wanted):
        raise CommunityError('请选择1至20条不同的可见消息。')
    selected = [row for row in visible if row['id'] in wanted]
    if len(selected) != len(wanted):
        raise CommunityError('所选消息已不可用，请重新选择。', 409)
    # Only these visible fields leave the source; no model state, tools or private reasoning.
    return {'content': '\n\n'.join(('用户' if row['role']=='user' else '助手')+'：'+row['content'] for row in selected),
            'source': {'kind':'conversation_excerpt', 'workspace_id':workspace_id,
                       'session_id':session_id, 'message_ids':[row['id'] for row in selected],
                       'title':str(session.get('title') or '')}}


def channel_instance(connector_id, channel):
    instance = manager().get_partner(connector_id)
    if not instance or not instance.running or not instance.channel_manager:
        return None
    return instance.channel_manager.get_channel(channel)


async def send(row, text):
    from deeptutor.partners.bus.events import OutboundMessage
    channel = channel_instance(row['connector_id'], row['channel'])
    if channel is None or not getattr(channel, '_running', False):
        raise CommunityError('对应Bot连接尚未启动。', 409)
    if row['channel'] == 'qq' and getattr(channel, '_client', None) is None:
        raise CommunityError('QQ应用尚未连接。', 409)
    if row['channel'] == 'weixin' and not getattr(channel, '_context_tokens', {}).get(row['sender_id']):
        raise CommunityError('请先在微信给Bot发一条消息。', 409)
    await channel.send(OutboundMessage(channel=row['channel'], chat_id=row['sender_id'], content=text,
                       metadata={'message_id':row['message_id'], 'community_delivery_id':row['id']}))
