from server.app import store
from server.figures import read_registry,read_figure,svg
from server.figure_artists import describe
from server.storage import atomic_json
import json,matplotlib,gc
import matplotlib.pyplot as plt
pid='10ac79bb0e5c478eaec07d022e05126d'
with store.db() as c:owner=c.execute('SELECT owner FROM projects WHERE id=?',(pid,)).fetchone()['owner']
root=store.path(owner,pid);checks=[]
for asset in read_registry(root):
 try:
  f,e=read_figure(root,asset);objects=describe(f);vector=svg(f);assert '<svg' in vector and objects
  checks.append({'asset':asset,'passed':True,'objects':len(objects),'source_matplotlib':e['matplotlib']});plt.close(f);del f,vector,objects;gc.collect()
 except Exception as error:checks.append({'asset':asset,'passed':False,'error':type(error).__name__+': '+str(error)})
report={'runtime_matplotlib':matplotlib.__version__,'figures':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'source_project':pid,'scientific_scope':'Runtime deserialization and SVG rendering; no numerical training or model validation'}
atomic_json(root/'project/docs/runtime-figure-test.json',report);print(json.dumps(report,ensure_ascii=False))
