"""Critical regressions from the user's issue document, using isolated files."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from server.storage import Store
from server.workspace_files import usage,revision_diff
from server.equation_layout import is_equation_table,mark_tables
from server import figures
from server.figure_artists import position_axes,panel_labels


with TemporaryDirectory() as temporary:
    store=Store(Path(temporary)/'store');owner='fixture-owner';p=store.create(owner,'Manuscript fixture');pid=p['id'];root=store.path(owner,pid)
    a={'title':'Manuscript','template':'chinese','revision':0,'content':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'First paragraph. Second sentence.'}]},{'type':'paragraph','content':[{'type':'text','text':'Keep this paragraph unchanged.'}]}]},'comments':[]}
    a=store.save_manuscript(owner,pid,a);b=deepcopy(a);b['content']['content'][0]['content'][0]['text']='First paragraph.';b=store.save_manuscript(owner,pid,b)
    old=store.trash(owner,pid)[0];assert old['title']=='论文正文' and old['category']=='paper'
    diff=revision_diff(store,owner,pid,old['id']);assert len(diff['changes'])==1 and 'Second sentence.' in diff['changes'][0]['before']
    store.restore(owner,pid,old['id']);restored=store.manuscript(owner,pid);assert restored['revision']==b['revision']+1 and restored['content']==a['content']
    dest=root/'project/data/small.txt';store.replace(owner,pid,dest,b'original','Fixture initial file');before=usage(store,owner)['used']
    with patch('server.workspace_files.QUOTA',before+2):
        try:store.replace(owner,pid,dest,b'oversized','Quota fixture')
        except ValueError:pass
        else:raise AssertionError('Quota did not stop the write')
    assert dest.read_bytes()==b'original'
    other=store.create('other-owner','Other account');assert usage(store,'other-owner')['used']<usage(store,owner)['used']
    inventory=store.inventory(owner,pid,'data')['items'][0];assert inventory['uploaded'] and inventory['modified']

    # Editing-session snapshots keep absolute changes meaningful after autosave.
    fig,ax=plt.subplots(figsize=(3,2));ax.plot([0,1],[0,1]);ax.set_xlabel('Position');asset='results/fixture.png';fig.savefig(root/'project'/asset,dpi=80);figures.register(root,asset,fig);plt.close(fig)
    scene=figures.edit_session(store,owner,pid,asset);sid=scene['edit_session'];revision=scene['revision'];delta={'figure':{},'objects':{'ax0-xlabel':{'move':{'dx':.03,'dy':0}}}}
    initial=next(o for o in scene['objects'] if o['id']=='ax0-xlabel')['bounds']
    saved=figures.save(store,owner,pid,asset,delta,revision,edit_session=sid)
    once=figures.preview(store,owner,pid,asset,delta,saved['revision'],sid)
    saved_again=figures.save(store,owner,pid,asset,delta,saved['revision'],edit_session=sid)
    twice=figures.preview(store,owner,pid,asset,delta,saved_again['revision'],sid)
    one=next(o for o in once['objects'] if o['id']=='ax0-xlabel')['bounds'];two=next(o for o in twice['objects'] if o['id']=='ax0-xlabel')['bounds'];assert max(abs(x-y) for x,y in zip(one,two))<1e-8,'Autosave accumulated a relative move'
    undone=figures.save(store,owner,pid,asset,{'figure':{},'objects':{}},saved_again['revision'],edit_session=sid)
    original=figures.inspect(store,owner,pid,asset);bounds=next(o for o in original['objects'] if o['id']=='ax0-xlabel')['bounds'];assert max(abs(x-y) for x,y in zip(initial,bounds))<1e-8,'Undo after autosave failed'
    assert len(list((root/'.workbench/figure-edit-sessions').glob('*.pkl')))==1
    image_version=next(r for r in store.trash(owner,pid) if r['original']=='project/'+asset)
    store.restore(owner,pid,image_version['id']);assert figures.inspect(store,owner,pid,asset)['ready'],'Restored image lost its editable source objects'

# A subplot's figure-level letter follows its axes when positions change.
fig,ax=plt.subplots();letter=fig.text(.11,.91,'(a)');assert panel_labels(fig)[0][1] is ax
before=letter.get_position();position=ax.get_position();position_axes(fig,ax,[position.x0+.02,position.y0-.01,position.width,position.height]);assert abs(letter.get_position()[0]-before[0]-.02)<1e-9 and abs(letter.get_position()[1]-before[1]+.01)<1e-9;plt.close(fig)

equation={'type':'table','content':[{'type':'tableRow','content':[{'type':'tableCell','content':[{'type':'paragraph'}]},{'type':'tableCell','content':[{'type':'blockMath','attrs':{'latex':'a=b'}}]},{'type':'tableCell','content':[{'type':'paragraph','content':[{'type':'text','text':'(5)'}]}]}]}]}
assert is_equation_table(equation);mark_tables(equation);assert equation['attrs']['equation']
data=deepcopy(equation);data['content'][0]['content'][2]['content'][0]['content'][0]['text']='Diffusivity / m² s⁻¹';assert not is_equation_table(data)
from server.cas_typesetting import document_tex,table_layout
from server.journals import crossref_journal
table={'type':'table','content':[{'type':'tableRow','content':[{'type':'tableHeader','attrs':{'colspan':2,'colwidth':[120,240]},'content':[{'type':'paragraph','content':[{'type':'text','text':'Merged header'}]}]}]},{'type':'tableRow','content':[{'type':'tableCell','content':[{'type':'paragraph','content':[{'type':'text','text':'Left'}]}]},{'type':'tableCell','content':[{'type':'paragraph','content':[{'type':'text','text':'Longer right column'}]}]}]}]}
grid,count,widths,aligns,authored=table_layout(table);assert count==2 and authored and abs(widths[1]/widths[0]-2)<1e-9
with TemporaryDirectory() as root:
    doc={'title':'Template fixture','content':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'Table 1. Preserve caption and authored widths.'}]},table,equation]}}
    source,layout=document_tex(Path(root),doc,crossref_journal({'title':'Cement and Concrete Research','publisher':'Elsevier','ISSN':['0008-8846']}),2)
    assert r'\documentclass[a4paper,fleqn]{cas-dc}' in source and r'\begin{tabular*}{\tblwidth}' in source and r'\multicolumn{2}' in source
    assert r'\caption{Preserve caption and authored widths.}' in source and r'\tag{5}' in source and 'fancyhdr' not in source and 'elsarticle}' not in source
    assert next(item for item in layout if item['kind']=='equation')['floating'] is False
print(json.dumps({'passed':True,'checks':['readable manuscript diff','monotonic restore revision','quota before replacement','owner isolation','upload/update timestamps','autosave no movement drift','undo after persisted figure','subplot label follows axes','numbered-equation classification']},ensure_ascii=False))
