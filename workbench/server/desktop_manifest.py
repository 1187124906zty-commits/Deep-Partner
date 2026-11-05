"""Authenticated, data-only discovery for the bundled DeepPartner frontend.

An optional operator-owned WORKBENCH_DESKTOP_WORKFLOWS_FILE records observed
Dify publication identities. It contains no credentials or executable UI code:
{"workflows": [{"app_id": "...", "published_version": "...",
                "source": "dify-runtime", "observed_at": "ISO timestamp"}]}.
Without that evidence, installed workflow declarations remain explicitly unknown.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from fastapi import Depends, Request
from fastapi.responses import JSONResponse, Response

from . import standards

SCHEMA_VERSION = 'desktop-manifest.v1'
FRONTEND_MINIMUM = '0.4.0'
FRONTEND_CURRENT = '0.4.1'
PROTOCOL_MINIMUM = PROTOCOL_MAXIMUM = '2.0'

# Stable application identities from the maintained Dify deployment. A declaration
# is not a live health or publication claim; publication evidence is separate.
WORKFLOWS = (
    {'id':'artifact_delivery', 'name':'研究成果交付',
     'app_id':'5c9d68ae-3847-4774-8e94-ecbfa9543e25',
     'entrypoint':'/research/dify/api/deliver'},
    {'id':'web_evidence', 'name':'公开网页证据读取',
     'app_id':'2f0d0b10-0d03-4a92-89b5-f8f07a51769a',
     'entrypoint':'/research/dify/api/web-evidence'},
    {'id':'delivery_events', 'name':'交付事件处理',
     'app_id':'587c5e8f-5df8-4b54-866d-598a582dccb4', 'entrypoint':None},
    {'id':'delivery_reconciliation', 'name':'交付协调与健康检查',
     'app_id':'185575c4-6eda-4f00-b01b-0b0f7093c018', 'entrypoint':None},
)


def _version(value, parts):
    if not isinstance(value,str) or not re.fullmatch(r'\d+(?:\.\d+){'+str(parts-1)+'}',value):
        return None
    return tuple(int(piece) for piece in value.split('.'))


def compatibility(frontend_version=None, protocol_version=None):
    frontend = protocol = None
    reasons=[]
    if frontend_version is not None:
        parsed=_version(frontend_version,3)
        frontend=parsed is not None and parsed>=_version(FRONTEND_MINIMUM,3)
        if not frontend:reasons.append('frontend_upgrade_required')
    if protocol_version is not None:
        parsed=_version(protocol_version,2)
        protocol=parsed is not None and _version(PROTOCOL_MINIMUM,2)<=parsed<=_version(PROTOCOL_MAXIMUM,2)
        if not protocol:reasons.append('protocol_unsupported')
    evaluated=[item for item in (frontend,protocol) if item is not None]
    return {'compatible':all(evaluated) if evaluated else None,
      'frontend_supported':frontend,'protocol_supported':protocol,
      'upgrade_required':bool(reasons),'reasons':reasons}


def workflow_catalog(evidence_path):
    try:
        snapshot=json.loads(Path(evidence_path).read_text(encoding='utf8'))
        observations=snapshot.get('workflows',[]) if isinstance(snapshot,dict) else []
    except (OSError,ValueError,TypeError):observations=[]
    by_app={row['app_id']:row for row in observations
            if isinstance(row,dict) and isinstance(row.get('app_id'),str)} if isinstance(observations,list) else {}
    rows=[]
    for declared in WORKFLOWS:
        observed=by_app.get(declared['app_id'],{})
        version=observed.get('published_version')
        source=observed.get('source')
        stamp=observed.get('observed_at')
        verified=(isinstance(version,str) and 0<len(version)<=160
                  and isinstance(source,str) and 0<len(source)<=160
                  and isinstance(stamp,str) and 0<len(stamp)<=80)
        publication={'status':'published' if verified else 'unknown',
                     'version':version if verified else None,
                     'evidence':{'source':source,'observed_at':stamp} if verified else None}
        rows.append({**declared,'declared':True,'availability':'unknown',
                     'availability_reason':'runtime_not_probed','publication':publication})
    return rows


async def manifest(request,native_call,evidence_path,frontend_version=None,protocol_version=None):
    try:
        catalog=await native_call(request,'GET','/api/capabilities/registered')
        descriptors=catalog.get('capabilities')
        if not isinstance(descriptors,list):raise ValueError('invalid native capability catalog')
        capabilities={'status':'available','endpoint':'/api/capabilities/registered','items':descriptors}
    except Exception:
        # Keep native error bodies, upstream URLs and credentials out of discovery.
        capabilities={'status':'unavailable','endpoint':'/api/capabilities/registered','items':[],
                      'error':'native_catalog_unavailable'}
    return {'schema_version':SCHEMA_VERSION,'product':'DeepPartner',
      'protocol':{'minimum':PROTOCOL_MINIMUM,'maximum':PROTOCOL_MAXIMUM,'current':PROTOCOL_MAXIMUM},
      'frontend':{'minimum':FRONTEND_MINIMUM,'current':FRONTEND_CURRENT,'update_policy':'manual'},
      'standards':{'version':standards.VERSION,'endpoint':'/research/api/standards'},
      'compatibility':compatibility(frontend_version,protocol_version),
      'capabilities':capabilities,'workflows':workflow_catalog(evidence_path),
      'endpoints':{'sessions':'/api/sessions','stream':'/ws','projects':'/research/api/projects',
                   'annotations_submit':'/research/api/projects/{pid}/annotations/submit',
                   'receipt':'/research/api/projects/{pid}/agent-receipt'},
      'updates':{'server':'new_tasks','frontend':'manual','remote_code_execution':False}}


def install(app,actor,native_call,data_root):
    @app.get('/research/api/desktop/manifest')
    async def desktop_manifest(request:Request,frontend_version:str|None=None,protocol_version:str|None=None,
                               user=Depends(actor)):
        evidence_path=os.environ.get('WORKBENCH_DESKTOP_WORKFLOWS_FILE') or Path(data_root)/'desktop-workflows.json'
        value=await manifest(request,native_call,evidence_path,frontend_version,protocol_version)
        raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        etag='"'+hashlib.sha256(raw).hexdigest()+'"'
        headers={'ETag':etag,'Cache-Control':'private, max-age=0, must-revalidate',
                 'Vary':'Cookie, Authorization','X-Content-Type-Options':'nosniff'}
        candidates=[piece.strip().removeprefix('W/') for piece in request.headers.get('if-none-match','').split(',')]
        if etag in candidates or '*' in candidates:return Response(status_code=304,headers=headers)
        return JSONResponse(value,headers=headers)
