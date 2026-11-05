"""Authenticated community pages; platform and account authorization remain native."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import __version__, native
from .service import CommunityService, schedule_delivery
from .store import CommunityError

router = APIRouter()


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Create(Payload):
    partner_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-z0-9][a-z0-9_-]*$')
    title: str = Field(min_length=1, max_length=100)
    create_partner: bool = False


class Accept(Payload):
    token: str = Field(min_length=8, max_length=160)


class Link(Payload):
    connector_id: str = Field(min_length=1, max_length=64)


class Preview(Payload):
    text: str = Field(default='', max_length=12000)
    workspace_id: str = Field(default='', max_length=240)
    session_id: str = Field(default='', max_length=240)
    message_ids: list[str] = Field(default_factory=list, max_length=20)


class Publish(Payload):
    draft_id: str = Field(min_length=1, max_length=64)
    command_id: str = Field(min_length=1, max_length=160)
    notify: bool = False


class Subscription(Payload):
    connector_id: str = Field(min_length=1, max_length=64)
    channel: str
    sender_id: str = Field(min_length=1, max_length=240)
    enabled: bool


@router.get('/app', response_class=HTMLResponse)
async def page():
    return HTMLResponse(Path(__file__).with_name('static').joinpath('community.html').read_text('utf-8'),
                        headers={'Cache-Control':'no-store','Referrer-Policy':'same-origin'})


@router.get('/status')
async def home():
    result = {'version':__version__, **CommunityService().home()}
    # Resume only previously consented pending intents after a server restart.
    schedule_delivery()
    return result


@router.get('/capability')
async def capability():
    return {'available':True, 'version':__version__, 'membership':'invitation_and_verified_channel'}


@router.post('/communities')
async def create(payload: Create):
    return await CommunityService().create(payload.partner_id, payload.title, payload.create_partner)


@router.post('/accept')
async def accept(payload: Accept):
    return CommunityService().accept(payload.token)


@router.post('/link-code')
async def link_code(payload: Link):
    return CommunityService().link_code(payload.connector_id)


@router.get('/sources')
async def sources(workspace_id: str = Query(default='', max_length=240), session_id: str = Query(default='', max_length=240)):
    return {'items':await native.source_messages(workspace_id, session_id)}


@router.get('/workspaces')
async def workspaces():
    return {'items':native.source_workspaces()}


@router.delete('/bindings')
async def unlink(connector_id: str = Query(max_length=64), key: str = Query(max_length=300)):
    return native.unlink(connector_id, native.actor().id, key)


@router.get('/communities/{community_id}')
async def detail(community_id: str):
    return CommunityService().detail(community_id)


@router.post('/communities/{community_id}/invites')
async def invite(community_id: str):
    return CommunityService().invite(community_id)


@router.delete('/communities/{community_id}/members/{user_id}')
async def revoke(community_id: str, user_id: str):
    service = CommunityService()
    service.membership(community_id, active=False)
    service.store.revoke(community_id, service.user().id, user_id)
    return {'ok':True}


@router.post('/communities/{community_id}/preview')
async def preview(community_id: str, payload: Preview):
    return await CommunityService().preview(community_id, **payload.model_dump())


@router.post('/communities/{community_id}/publish')
async def publish(community_id: str, payload: Publish):
    result = CommunityService().publish(community_id, **payload.model_dump())
    if payload.notify:
        schedule_delivery()
    return result


@router.post('/communities/{community_id}/subscription')
async def subscribe(community_id: str, payload: Subscription):
    return CommunityService().subscribe(community_id, payload.model_dump(exclude={'enabled'}), payload.enabled)


async def enabled():
    from deeptutor.modules.catalog import module_enabled
    from deeptutor.__version__ import __version__ as tutor_version
    if not tutor_version.startswith('1.7.'):
        raise CommunityError('当前Tutor版本尚未通过社区模块兼容验收。', 503)
    if not module_enabled('partners'):
        raise CommunityError('当前部署未启用Partner模块。', 404)


def install(app: FastAPI):
    """One idempotent HTTP seam, with the original native authentication policy."""
    if getattr(app.state, 'partner_community_installed', False):
        return
    from deeptutor.api.routers.auth import require_auth
    app.include_router(router, prefix='/api/community', tags=['partner-community'],
                       dependencies=[Depends(require_auth), Depends(enabled)])
    async def error_handler(_request, error):
        return JSONResponse(status_code=error.status, content={'detail':str(error)})
    app.add_exception_handler(CommunityError, error_handler)
    app.state.partner_community_installed = True
