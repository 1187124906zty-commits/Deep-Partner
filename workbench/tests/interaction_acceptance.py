"""Regression checks for authoring controls on real Matplotlib objects."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from server.figure_artists import artists,describe,apply_changes
from server.figures import register,inspect,preview,save
from server.storage import Store

checks=[];failures=[]
def check(value,label):
    (checks if value else failures).append(label)

with TemporaryDirectory() as temp:
    store=Store(Path(temp)/'store');p=store.create('authoring-test','Figure authoring');pid=p['id'];root=store.path('authoring-test',pid)
    path=root/'project/results/chart.png';path.parent.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(8,3))
    data=np.arange(25).reshape(5,5)
    field=axes[0].imshow(data,origin='lower');cb=fig.colorbar(field,ax=axes[0],label='Concentration')
    axes[0].spines['top'].set_visible(False);bars=axes[1].bar([0,1],[2,3]);axes[1].bar_label(bars)
    fig.savefig(path);entry=register(root,'results/chart.png',fig)
    info=inspect(store,'authoring-test',pid,'results/chart.png');known={o['id']:o for o in info['objects']}
    check('ax0-spine-top' in known,'A hidden top axis has an addressable control before it is visible')
    check('ax0-xlabel' in known,'An empty axis label can be created from the property template')
    check(any(o['kind']=='patch' for o in known.values()),'Bar rectangles expose style properties as real Artists')
    check(any(o['kind']=='text' and o.get('role')=='colorbar-label' for o in known.values()),'Colorbar text has its own font and text control')
    check(any(o.get('schema') for o in known.values()),'Objects publish typed native Matplotlib properties for the inspector')
    before=axes[0].get_position().frozen();before_cb=cb.ax.get_position().frozen()
    apply_changes(fig,{'figure':{'dpi':360},'objects':{'axes-0':{'move':{'dx':.04,'dy':.02}}}})
    check(abs(axes[0].get_position().x0-before.x0-.04)<1e-7,'A field subplot moves as a subplot')
    check(abs(cb.ax.get_position().x0-before_cb.x0-.04)<1e-7,'The colorbar follows a moved field subplot')
    save(store,'authoring-test',pid,'results/chart.png',{'figure':{'dpi':360}},entry['revision'],'Set export resolution')
    with Image.open(path) as image:check(image.width==2880 and image.height==1080,'PNG exports use the configured DPI rather than a fixed 180 DPI')
    check(np.array_equal(field.get_array(),data),'Authoring preserves the original field data')
    plt.close('all')

report={'passed':len(checks),'checks':checks,'failed':len(failures),'failures':failures,'matplotlib':matplotlib.__version__}
output=Path(sys.argv[1] if len(sys.argv)>1 else 'verification/interaction-acceptance.json');output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False));sys.exit(bool(failures))
