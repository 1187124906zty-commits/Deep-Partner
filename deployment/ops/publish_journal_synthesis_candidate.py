"""Save the corrected, visually checked author candidate beside the raw run."""
import base64
import json
import sys

from run_journal_synthesis_regression import REPORT,LIVE,STATE,REMOTE_ROOT,PID,remote


def main():
    sys.stdout.reconfigure(encoding='utf8')
    rid=json.loads(STATE.read_text(encoding='utf8'))['run_id']
    final=json.loads((LIVE/'final-candidate-document.json').read_text(encoding='utf8'))
    finalization=json.loads((LIVE/'finalization.json').read_text(encoding='utf8'))
    finalization['run_status']='completed'
    finalization['raw_model_review_score']=87
    finalization['final_rescored']=False
    finalization['review_findings_disposition']={'N01':'corrected third author to Dinghui Chen','N02':'unified formal volume year to 2013','N04':'narrowed feedback comparison wording; no new scientific objective added','N03':'potential expression improvement retained for author feedback','N05':'potential sentence density improvement retained for author feedback'}
    files={'author-review-candidate.json':json.dumps(final,ensure_ascii=False,indent=2).encode(),
        'author-review-introduction.docx':(REPORT/'氯硫引言_研究群体综合候选.docx').read_bytes(),
        'author-review-introduction.md':(REPORT/'氯硫引言_研究群体综合候选.md').read_bytes(),
        'author-review-disposition.json':json.dumps(finalization,ensure_ascii=False,indent=2).encode()}
    encoded={k:base64.b64encode(v).decode() for k,v in files.items()}
    code='RID='+repr(rid)+'\nROOT='+repr(REMOTE_ROOT)+'\nPID='+repr(PID)+'\nFILES='+repr(encoded)+r'''
from pathlib import Path
import os,base64,json
from server.storage import Store,atomic_json
from server.writing_revision import difference
root=Path(ROOT);folder=root/'.workbench/writing/runs'/RID
state=json.loads((folder/'state.json').read_text());assert state['status']=='completed'
store=Store(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))
target=root/Path(state['outputs']['path']).parent
for name,encoded in FILES.items():
 data=base64.b64decode(encoded);path=target/name
 store.replace('local-admin',PID,path,data,'作者指定期刊引言重组的审读修正候选')
 assert path.read_bytes()==data
final=json.loads((target/'author-review-candidate.json').read_text())
diff=difference(state['source_document'],final,'本轮最终引言候选')
store.replace('local-admin',PID,target/'author-review-changes.html',diff.encode(),'最终候选与原稿差异')
state['outputs']['author_review_candidate']={name:str((target/name).relative_to(root)) for name in FILES}
state['outputs']['author_review_candidate']['diff_path']=str((target/'author-review-changes.html').relative_to(root))
atomic_json(folder/'state.json',state)
print(json.dumps({'paths':state['outputs']['author_review_candidate'],'readback_matches':True,'formal_revision':json.loads((root/'manuscript/main.json').read_text())['revision'],'diff':diff},ensure_ascii=True))
'''
    result=json.loads(remote(code))
    (LIVE/'final-diff.html').write_text(result.pop('diff'),encoding='utf8')
    (LIVE/'finalization.json').write_text(json.dumps(finalization,ensure_ascii=False,indent=2),encoding='utf8')
    (LIVE/'project-delivery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
