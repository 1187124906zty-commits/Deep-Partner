"""Finite real MCP / Slurm checks, including a numerically wrong solver."""
import asyncio
import json
from pathlib import Path
import time

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    token = Path('/run/compute-secrets/token').read_text().strip()
    url = 'http://127.0.0.1:47920/mcp'
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={})
        assert response.status_code == 401
    async with streamablehttp_client(url, headers={'Authorization': 'Bearer ' + token}, timeout=90) as channels:
        async with ClientSession(channels[0], channels[1]) as session:
            info = await session.initialize()
            catalog = await session.list_tools()
            assert [tool.name for tool in catalog.tools] == ['research_compute']

            async def call(action, **payload):
                result = await session.call_tool('research_compute', {'action': action, 'payload': payload})
                text = '\n'.join(item.text for item in result.content if item.type == 'text')
                if result.isError:
                    raise RuntimeError(text)
                return json.loads(text)

            inventory = await call('inventory')
            specs = json.loads(Path('/opt/research-compute/benchmark-specs.json').read_text())
            experiments = {}
            for name, spec in specs.items():
                prepared = await call('prepare', request_id='acceptance-20261101-v1-' + name, spec=spec)
                submitted = await call('submit', experiment_id=prepared['experiment_id'])
                again = await call('submit', experiment_id=prepared['experiment_id'])
                assert again['job_id'] == submitted['job_id'] and again['deduplicated']
                experiments[name] = {'experiment_id': prepared['experiment_id'], 'job_id': submitted['job_id']}
            deadline = time.monotonic() + 240
            while True:
                for item in experiments.values():
                    item['run'] = await call('status', experiment_id=item['experiment_id'])
                if all(item['run'].get('finished') for item in experiments.values()):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError('Finite live check reached its wait budget; existing IDs: ' + json.dumps(experiments))
                await asyncio.sleep(8)
            for name in ('correct', 'wrong'):
                item = experiments[name]
                item['assessment'] = await call('assess', experiment_id=item['experiment_id'])
            assert experiments['correct']['assessment']['status'] == 'NUMERICALLY_CHECKED'
            assert experiments['wrong']['assessment']['status'] == 'FAILED'
            assert experiments['wrong']['assessment']['executed']
            actual_tools = await call('openpaso_schema', experiment_id=experiments['catalog']['experiment_id'])
            schema = await call('openpaso_schema', experiment_id=experiments['catalog']['experiment_id'], tool='run_simulation')
            assert schema['name'] == 'run_simulation' and schema.get('inputSchema')
            report = {'mcp_initialized': True, 'unauthenticated_rejected': True,
                'submission_deduplicated': True, 'correct_numerics_accepted': True,
                'wrong_operator_rejected_despite_exit_zero': True, 'inventory': inventory,
                'openpaso_tools': actual_tools, 'run_simulation_schema': schema, 'experiments': experiments}
            Path('/tmp/compute-live-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
