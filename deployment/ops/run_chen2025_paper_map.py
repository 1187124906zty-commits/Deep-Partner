"""Run the existing, deployed content-map workflow on the author's Chen PDF."""
from pathlib import Path
import argparse
import base64
import gzip
import json
import os
import sys

import httpx
from workspace_interactions_fixture import login, ORIGIN

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/Chen2025论文内容解析'
STATE = OUT / 'workflow-run.json'
PID = '1ea03384007d4bb9b88d43e3368099f3'
PDF = Path('C:/Users/ADMINI~1/AppData/Local/Temp/Zotero/drag/Chen 等 - 2025 - Experiment and simulation on the coupled effects of calcium leaching and chloride transport in concr.pdf')


def main():
    sys.stdout.reconfigure(encoding='utf8')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'status', 'fetch', 'collect', 'prefill'])
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    os.environ['WORKBENCH_PROXY_JUMP'] = 'research-cluster-xh5'
    state = json.loads(STATE.read_text(encoding='utf8')) if STATE.is_file() else {}
    if args.action == 'prefill':
        # The original worker is sequential. These two independent, not-yet-
        # reached groups use its exact prompt, source packet and model service.
        # Only absent part files are saved; original state and parts stay owned
        # by the running worker. Distinct trace names prevent in-flight clashes.
        from run_journal_synthesis_regression import remote, REMOTE_ROOT
        code = 'ROOT=' + repr(REMOTE_ROOT) + '\nJID=' + repr(state['job_id']) + r'''
from pathlib import Path
import asyncio,json
from server.app import store
from server.paper_maps import PaperMaps
from server.paper_map_core import build_prompt
from server.storage import atomic_json
folder=Path(ROOT)/'.workbench/paper-maps/jobs'/JID
state=json.loads(folder.with_suffix('.json').read_text())
source=json.loads((folder/'source.json').read_text())
groups=[];current=[];size=0
for unit in source['units']:
 if current and size+len(unit['text'])>state['group_chars']:
  groups.append(current);current=[];size=0
 current.append(unit);size+=len(unit['text'])
if current:groups.append(current)
service=PaperMaps(store)
async def one(index):
 path=folder/('part-'+str(index)+'.json')
 if path.exists():return {'index':index,'status':'already_saved'}
 group=groups[index]
 part={'unit_ids':[u['id'] for u in group],'section_ids':list(dict.fromkeys(u.get('section_id') for u in group))}
 prompt,payload=build_prompt(source,part=part)
 result=await service.call_model(state,prompt,payload,'prefill-section-'+str(index+1))
 if not path.exists():atomic_json(path,result)
 return {'index':index,'status':'saved','nodes':len(result.get('nodes',[]))}
async def main():
 results=await asyncio.gather(*(one(i) for i in [3,4]),return_exceptions=True)
 print(json.dumps([{'error':str(r)} if isinstance(r,BaseException) else r for r in results]))
asyncio.run(main())
'''
        print(remote(code, timeout=1200))
        return
    if args.action == 'collect':
        from run_journal_synthesis_regression import remote, REMOTE_ROOT
        code = 'ROOT=' + repr(REMOTE_ROOT) + '\nJID=' + repr(state['job_id']) + r'''
from pathlib import Path
import json,gzip,base64
folder=Path(ROOT)/'.workbench/paper-maps/jobs'/JID
state=json.loads(folder.with_suffix('.json').read_text())
files={p.name:p.read_text() for p in folder.glob('*.json')}
files.update({'model-traces/'+p.name:p.read_text() for p in (folder/'model-traces').glob('*-receipt.json')})
print(json.dumps({'state':{k:state.get(k) for k in ['status','stage','phase','parts','part_count','group_chars','error','model_selection']},'files':base64.b64encode(gzip.compress(json.dumps(files).encode())).decode()}))
'''
        value = json.loads(remote(code))
        files = json.loads(gzip.decompress(base64.b64decode(value['files'])))
        for name, content in files.items():
            path = OUT / 'run-details' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf8')
        (OUT / 'run-details/progress.json').write_text(json.dumps(value['state'], ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'progress': value['state'], 'saved_files': list(files)}, ensure_ascii=False))
        return
    with httpx.Client(base_url=ORIGIN, headers={'Origin': ORIGIN}, timeout=240, trust_env=False) as client:
        login(client)
        base = '/research/api/projects/' + PID
        if args.action == 'start':
            if not state.get('asset'):
                with PDF.open('rb') as source:
                    response = client.post(base + '/literature/upload', data={'folder': 'reading'},
                        files={'files': ('Chen2025_HydraulicLeachingChloride.pdf', source, 'application/pdf')})
                response.raise_for_status()
                receipt = response.json()
                (OUT / 'upload-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf8')
                item = receipt['items'][0]
                state.update(project_id=PID, asset=item.get('asset') or item.get('name'), library='workspace')
                assert state['asset'], str(item)[:1000]
                STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
            response = client.post(base + '/literature/content-map', json={'asset': state['asset'], 'library': 'workspace'})
            response.raise_for_status()
            state.update(response.json())
        else:
            response = client.get(base + '/literature/content-map', params={'asset': state['asset'], 'library': 'workspace'})
            response.raise_for_status()
            value = response.json()
            state.update({k: v for k, v in value.items() if k != 'map'})
            graph = value.get('map')
            if graph:
                (OUT / 'automatic-map.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf8')
                state['quality'] = {'nodes': len(graph['nodes']), 'edges': len(graph['edges']),
                    'coverage': graph['coverage'], 'evaluation': graph.get('evaluation'),
                    'story': graph.get('story')}
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
        display = {k: v for k, v in state.items() if k != 'quality'}
        if state.get('quality'):
            quality = state['quality']
            display['quality'] = {'nodes': quality['nodes'], 'edges': quality['edges'],
                'coverage_status': quality['coverage'].get('status'),
                'mapped_units': quality['coverage'].get('mapped_units'),
                'content_score': (quality.get('evaluation') or {}).get('content_score')}
        print(json.dumps(display, ensure_ascii=False))


if __name__ == '__main__':
    main()
