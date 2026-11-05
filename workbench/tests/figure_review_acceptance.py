"""Meaningful figure editing checks: data integrity, scope, exports and history."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,pickle,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from server.storage import Store,Conflict
from server.figures import register,inspect,preview,save,read_figure
from server.annotations import save_annotation,history,list_annotations
from server.reader_processor import parse
from server.neoreader import rewrite_text
from server.standards import context,instructions,catalog

checks=[]
def check(condition,label):
    assert condition,label
    checks.append(label)

with TemporaryDirectory() as temp:
    state=Store(Path(temp)/'store');p=state.create('figure-a','Figure verification');pid=p['id'];root=state.path('figure-a',pid)
    path=root/'project/results/chart.png';path.parent.mkdir(parents=True,exist_ok=True)
    program=root/'project/src/plot.py';program.parent.mkdir(parents=True,exist_ok=True)
    program.write_text('"""A real plot script."""\nfrom pathlib import Path\nimport matplotlib.pyplot as plt\nfig,ax=plt.subplots()\nax.plot([0,1],[0,1])\n',encoding='utf8')
    fig,axes=plt.subplots(1,2,figsize=(8,3),layout='constrained')
    image=axes[0].imshow(np.arange(16).reshape(4,4),cmap='viridis');fig.colorbar(image,ax=axes[0],label='Value')
    axes[0].set(title='Field',xlabel='x',ylabel='y');line,=axes[1].plot([0,1,2],[2,1,3],label='Reference');axes[1].legend(frameon=False);axes[1].set(title='Curve',xlabel='Time',ylabel='Value')
    fig.savefig(path,dpi=180);original=path.read_bytes();alias=root/'manuscript/assets/chart.png';alias.parent.mkdir(parents=True,exist_ok=True);alias.write_bytes(original)
    doc=state.manuscript('figure-a',pid);doc['content']={'type':'doc','content':[{'type':'image','attrs':{'src':f'/research/api/projects/{pid}/manuscript/assets/chart.png'}}]};state.save_manuscript('figure-a',pid,doc)
    entry=register(root,'results/chart.png',fig,'src/plot.py')
    info=inspect(state,'figure-a',pid,'results/chart.png')
    check({'field','colorbar','line','legend','text','ticks','axes'}<={o['kind'] for o in info['objects']},'Actual editable artists exposed')
    check('<svg' in info['svg'] and 'wb-ax0-title' in info['svg'],'Object-addressable SVG retains editable text')
    patch={'figure':{'font_family':'DejaVu Sans','font_size':11,'wspace':.25},'objects':{
      'ax0-title':{'font_size':15,'color':'#b0501e'},'ax0-image0':{'cmap':'plasma','levels':8,'vmin':0,'vmax':15},
      'ax1-line0':{'line_style':'None','marker':'o','marker_size':6,'color':'#2277aa'},'ax1-legend':{'columns':1,'move':{'dx':.02,'dy':.03}},
      'colorbar-2':{'tick_font_size':9,'tick_count':5}}}
    patch['layout']={'rows':2,'cols':1,'gap_y':.03,'cells':{'axes-0':{'row':0,'col':0,'x':.15,'y':.12,'width':.68,'height':.68},'axes-1':{'row':1,'col':0,'x':.16,'y':.12,'width':.68,'height':.68}}}
    edited=preview(state,'figure-a',pid,'results/chart.png',patch,entry['revision'])
    check(next(x for x in edited['objects'] if x['id']=='ax1-line0')['properties']['marker']=='o','Line-to-points change renders through Matplotlib')
    check(next(x for x in edited['objects'] if x['kind']=='field')['properties']['levels']==8,'Discrete field color levels applied')
    check(edited['layout']['rows']==2 and edited['layout']['cols']==1 and edited['layout']['cells']['axes-1']['row']==1,'Subplots occupy independent grid cells with saved relative positions')
    check(path.read_bytes()==original and alias.read_bytes()==original,'Live preview leaves saved source images intact')
    result=save(state,'figure-a',pid,'results/chart.png',patch,entry['revision'],'调整字体、云图色阶和曲线点型')
    saved,entry=read_figure(root,'results/chart.png')
    check(np.array_equal(saved.axes[0].images[0].get_array(),np.arange(16).reshape(4,4)) and np.array_equal(saved.axes[1].lines[0].get_ydata(),[2,1,3]),'Data values remain unchanged by style edits')
    check(path.read_bytes()!=original and alias.read_bytes()==path.read_bytes(),'Workspace plot and manuscript reference update together')
    check(all(path.with_suffix('.'+ext).is_file() for ext in ('png','pdf','svg')),'Current PNG PDF SVG exported')
    check(any(x['original']=='project/results/chart.png' and x['reason']=='调整字体、云图色阶和曲线点型' for x in state.trash('figure-a',pid)),'Previous plot retained in trash with reason and timestamp')
    check('# research-workbench: figure styles' in program.read_text() and (root/'.workbench/figure_runtime.py').exists(),'Source plotting program reuses saved style runtime')
    from server.figure_artists import install
    from matplotlib.figure import Figure
    original_save=Figure.savefig
    try:
        regenerated=pickle.loads((root/'.workbench/figures'/entry['id']/'source.pkl').read_bytes())
        install(root,plot_program='src/plot.py')
        regenerated.savefig(path,dpi=180)
        check(regenerated.axes[1].lines[0].get_marker()=='o' and regenerated.axes[0].images[0].get_cmap().name=='plasma','Rerunning the plotting program retains saved point and color styles')
        current,entry=read_figure(root,'results/chart.png')
        check(current.axes[1].lines[0].get_marker()=='o','Regenerated figure exposes its updated objects back to the editor')
        check(current._workbench_layout['rows']==2 and abs(current._workbench_layout['cells']['axes-1']['y']-.12)<1e-8,'Regenerated plotting program preserves subplot grid and cell offsets')
    finally:Figure.savefig=original_save
    try:save(state,'figure-a',pid,'results/chart.png',patch,entry['revision']-1);raise AssertionError('stale save accepted')
    except Conflict:checks.append('Stale editor cannot overwrite a newer saved figure')
    try:inspect(state,'figure-b',pid,'results/chart.png');raise AssertionError('owner leak')
    except KeyError:checks.append('Figure state is owner scoped')
    a=save_annotation(state,'figure-a',pid,{'area':'code','asset':'src/plot.py','title':'Plot program','body':'Change label','quote':'ax.plot','locator':{'line_start':4,'line_end':4}})
    b=save_annotation(state,'figure-a',pid,{'area':'slides','asset':'slides/second','title':'Second slide','body':'Move legend','locator':{'page':2}})
    save_annotation(state,'figure-a',pid,{'status':'resolved'},a['id'])
    check(len(list_annotations(state,'figure-a',pid,'code','src/plot.py'))==1 and len(list_annotations(state,'figure-a',pid,'slides','slides/second'))==1,'Annotations stay attached to their own file or page')
    journal=history(state,'figure-a',pid)
    check(any(x['payload'].get('before',{}).get('body')=='Change label' for x in journal['events'] if x['kind']=='annotation.updated'),'Annotation edits retain original question history')
    package=context(state,'figure-a',pid,'code')
    check(any(x['id']=='mattpocock/codebase-design' for x in package['skills']) and Path(package['standard_path']).exists(),'External API gets product-owned original skills and output contract')
    check('当前操作协议与具体任务' in instructions('translation','RETURN JSONL'),'Task protocol stays after common output standards')
    prefix='/research/reader/'+pid
    text=rewrite_text('return"/"+e;fetch("/api/documents");"/pub/private/doc/original.pdf"',prefix,'private')
    check('return"'+prefix+'/"+e' in text and '/pub/private/' not in text,'Native reader root-relative assets and private capability rewritten')
    layout=parse(path.with_suffix('.pdf'),root/'.workbench/parser-test')
    check(layout['pages']==1 and len(layout['blocks'])>2 and all(0<=b['bounds']['x']<=1 for b in layout['blocks']),'Native reader worker extracts real PDF text with normalized coordinates')
    check('Field' in (root/'.workbench/parser-test/paper.md').read_text(encoding='utf8'),'Native parser publishes the Markdown required by reparse and translation')
    plt.close('all')

output=Path(sys.argv[1] if len(sys.argv)>1 else 'verification/figure-review-acceptance.json')
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'passed':len(checks),'checks':checks,'matplotlib':matplotlib.__version__},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False),flush=True)
