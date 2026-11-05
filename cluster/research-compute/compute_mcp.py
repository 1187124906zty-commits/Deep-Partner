"""MCP transport over an existing runtime; cluster execution uses a forced key."""
import asyncio
import hmac
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP('Research Compute', stateless_http=True, json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=['research-compute:47920', '127.0.0.1:47920', 'localhost:47920'],
        allowed_origins=['http://research-compute:47920', 'http://127.0.0.1:47920']))


@mcp.tool()
async def research_compute(action: str, payload: dict) -> dict:
    """Run one research-compute action: inventory, prepare, submit, status, cancel,
    read, assess or openpaso_schema. prepare takes a spec with question, runtime,
    files [{path,content}], entrypoint, criteria [{name,metric,op,threshold,unit}],
    reference, limitations, resources {cpus,memory_mb,minutes}. It locks inputs
    and criteria before submission. Runtime: python/paso/torch/openpaso/catalog.
    Other actions use the returned experiment_id. Programs write numeric values
    to outputs/metrics.json as {"metrics":{...}}. assess reads real Slurm state,
    process exit and metrics, then applies those declared criteria; it does not
    certify experimental truth. read returns a bounded experiment-relative text
    file, including outputs/assessment.md. openpaso_schema reads the real catalog
    saved by a runtime=openpaso_catalog job, optionally selecting tool by name.
    Every call carries application-supplied identity.owner_id. On uncertain
    submission keep the same experiment_id; never submit a replacement blindly.
    """
    allowed = {'inventory', 'prepare', 'submit', 'status', 'read', 'assess', 'cancel', 'openpaso_schema'}
    if action not in allowed:
        raise ValueError('Unsupported compute action')
    payload = dict(payload)
    identity = dict(payload.get('identity') or {})
    owner = os.environ['COMPUTE_OWNER_ID']
    if identity.get('owner_id') not in {None, '', owner}:
        raise ValueError('This compute endpoint is assigned to a different account')
    identity['owner_id'] = owner
    payload['identity'] = identity
    program = await asyncio.create_subprocess_exec('ssh', '-T', '-F', '/run/compute-secrets/ssh-config', 'tutor-compute-cluster',
        '/public/software/apps/anaconda3/2023.09/bin/python',
        '/work/home/cluster_user/.local/share/tutor-research-compute/cluster_dispatch.py',
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    encoded = json.dumps({'action': action, 'payload': payload}, ensure_ascii=False).encode()
    try:
        stdout, stderr = await asyncio.wait_for(program.communicate(encoded), timeout=65)
    except TimeoutError:
        program.kill()
        await program.wait()
        raise RuntimeError('Cluster control timed out. Query the same experiment before retrying submission.') from None
    try:
        result = json.loads(stdout)
    except ValueError:
        raise RuntimeError('Cluster returned no JSON: ' + stderr.decode(errors='replace')[-1500:]) from None
    if not result.get('ok'):
        raise ValueError(result.get('error', 'Cluster request failed'))
    return result['result']


class BearerAuth:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = dict(scope.get('headers', []))
            token = Path(os.environ.get('COMPUTE_TOKEN_FILE', '/run/compute-secrets/token')).read_text().strip()
            if not hmac.compare_digest(headers.get(b'authorization', b'').decode(), 'Bearer ' + token):
                await send({'type': 'http.response.start', 'status': 401, 'headers': [(b'content-type', b'application/json')]})
                await send({'type': 'http.response.body', 'body': b'{"error":"authentication_required"}'})
                return
        await self.inner(scope, receive, send)


app = BearerAuth(mcp.streamable_http_app())
