"""Citation replacement must preserve identity, context and recoverable originals."""
from pathlib import Path
from copy import deepcopy
from tempfile import TemporaryDirectory
import json
from server.storage import Store
from server.references import prepare,replace,text

checks=[]
def node(kind,value):return {'type':kind,'content':[{'type':'text','text':value}],**({'attrs':{'level':1}} if kind=='heading' else {})}
with TemporaryDirectory() as folder:
    store=Store(Path(folder));p=store.create('qa','Citation test');pid=p['id'];doc=store.manuscript('qa',pid)
    doc['content']={'type':'doc','content':[node('paragraph','Existing numerical evidence [1] supports the comparison.'),node('heading','References'),node('paragraph','[1] Original paper, arXiv:2010.08895.')]}
    doc['translation']={'title':'Translation','language':'en','content':deepcopy(doc['content']),'comments':[],'source_revision':0,'template':'elsevier'}
    saved=store.save_manuscript('qa',pid,doc);ref=saved['references'][0];citation=saved['content']['content'][0]['content'][1]
    assert citation['type']=='citation' and citation['attrs']['refId']==ref['id'];checks.append('Existing numeric citations acquire a stable library identity')
    original=text(saved['content']['content'][0]);entry={'title':'Verified replacement','doi':'10.1000/example','authors':['A Researcher'],'year':2025,'verified':True}
    updated=replace(store,'qa',pid,ref['id'],entry,saved['revision'],'Revised numerical evidence [1] supports a limited comparison.',original)
    assert updated['references'][0]['id']==ref['id'] and updated['references'][0]['number']==1
    assert 'Verified replacement' in text(updated['content']) and 'Revised numerical' in text(updated['content']);checks.append('Replacement synchronizes the paragraph and bibliography while keeping citation identity')
    assert 'Verified replacement' in text(updated['translation']['content']) and updated['translation']['content']['content'][0]['content'][1]['attrs']['refId']==ref['id'];checks.append('The translation uses the same citation identity and current bibliography')
    assert store.trash('qa',pid);checks.append('The prior manuscript remains recoverable in trash')
    try:replace(store,'qa',pid,ref['id'],entry,saved['revision']);raise AssertionError('stale replacement accepted')
    except ValueError:checks.append('Stale replacement cannot overwrite newer text')
    try:replace(store,'qa',pid,ref['id'],entry,updated['revision'],'Wrong numbering [9].',text(updated['content']['content'][0]));raise AssertionError('number corruption accepted')
    except ValueError:checks.append('Agent suggestions cannot invent or discard citation numbers')
    assert prepare(updated)==prepare(prepare(updated));checks.append('Repeated loading does not duplicate bibliography or citation markers')
    legacy=prepare({'content':{'type':'doc','content':[node('heading','References'),node('paragraph','[1] Lu et al. DeepONet, arXiv:1910.03193.')]}})
    assert 'year' not in legacy['references'][0];checks.append('An arXiv identifier is not misread as a publication year')
report={'passed':len(checks),'checks':checks,'external_model_calls':0}
Path('verification/reference-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
