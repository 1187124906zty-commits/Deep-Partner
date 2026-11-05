"""Reuse the completed model planning after repairing its nested score evidence."""
from pathlib import Path
import json
import sys

from run_journal_synthesis_regression import remote, REMOTE_ROOT, STATE, LIVE, REPORT


def main():
    sys.stdout.reconfigure(encoding='utf8')
    rid=json.loads(STATE.read_text(encoding='utf8'))['run_id']
    code='RID='+repr(rid)+'\nROOT='+repr(REMOTE_ROOT)+r'''
from pathlib import Path
import json
from server.storage import atomic_json,now
from server.literature import read_index
from server.writing import decode_json
from server.writing_scores import normalize_score
from server.writing_synthesis import reference_manifest
from server.writing_prompts import VERSION
from server import writing_tools

root=Path(ROOT);folder=root/'.workbench/writing/runs'/RID
state=json.loads((folder/'state.json').read_text())
assert state['status']=='failed' and state['stage']=='alignment'
assert state['error']=='评分需要给出依据：precision'
raw=(folder/'agentic/alignment/output.txt').read_text()
# Keep the returned model output unchanged; only its already explicit evidence
# is normalized and two genuinely read library sources receive stable IDs.
result=decode_json(raw)
result['editorial_assessment']=normalize_score(result['editorial_assessment'],use_baseline=True)
existing={r['doi'].lower() for r in state['source_manifest'] if r.get('doi')}
library=read_index(root);added=[]
for row in result['reference_registry']:
 doi=row.get('doi','').lower()
 if doi in existing:continue
 match=next(((key,value) for key,value in library.items() if value.get('doi','').lower()==doi),None)
 assert match,'Source was not registered in the real project library: '+doi
 key,value=match
 assert row['source_path']=='literature/'+key and (root/row['source_path']).is_file()
 added.append({**value,'source_path':row['source_path'],'access_scope':'actual alignment agent read the primary PDF for response learning evidence; see raw stage tool receipts','evidence_locations':['agentic/alignment read_project_source tool result'],
               'evidence_excerpt':row['title']})
manifest=reference_manifest(state['source_document'],supplied=state['source_manifest']+added)
by_doi={r['doi'].lower():r for r in manifest if r.get('doi')}
for row in result['reference_registry']:row['registered_id']=by_doi[row['doi'].lower()]['id']
record={'time':now(),'reason':'评分理由实际保存在locations[].reason；保留全部原文定位、例句、理由和分数，兼容接回，不重新生成规划',
        'raw_output':'agentic/alignment/output.txt','original_score':result['editorial_assessment']['total_score'],
        'library_sources_added':[r['source_path'] for r in added],'source_manifest_count':len(manifest),'prompt_version_after_repair':VERSION,'model_output_rewritten':False}
state['source_manifest']=manifest;state['l2']=result
state['retrieved_evidence']=json.loads((folder/'retrieved-evidence.json').read_text())
state['tool_results']['intrinsic_scientific_rigor_auditor']=writing_tools.intrinsic_scientific_rigor_auditor(state['asset_index']['selected_assets'],{})
state.update(status='interrupted',stage='wide',error='')
state['stage_history'].append({'stage':'alignment','completed':now(),'output':'alignment.json','prompt_version':'1111-20261104.2','integration_repair':'alignment-integration-repair.json'})
atomic_json(folder/'alignment-integration-repair.json',record)
atomic_json(folder/'alignment.json',result)
atomic_json(root/'.workbench/writing/L2_Manuscript_Alignment_State.json',result)
atomic_json(root/'project/docs/writing/regression/journal-synthesis-20261104/source-manifest-expanded.json',manifest)
atomic_json(folder/'state.json',state)
print(json.dumps({'record':record,'manifest':manifest,'alignment':result},ensure_ascii=True))
'''
    value=json.loads(remote(code))
    for name,data in [('source-manifest-expanded.json',value['manifest'])]:
        (REPORT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    for name,data in [('alignment.json',value['alignment']),('alignment-integration-repair.json',value['record'])]:
        (LIVE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value['record'],ensure_ascii=False))


if __name__=='__main__':main()
