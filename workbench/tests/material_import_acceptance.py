"""A trusted figure import preserves source artwork until an explicit save."""
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import hashlib,json,sys,zipfile
sys.path.insert(0,'/workbench')
from docx import Document
from PIL import Image,PngImagePlugin
import matplotlib.pyplot as plt
from server.storage import Store,atomic_json
from server.figures import register,save,manuscript_links
from server.material_import import import_bundle

checks=[]
with TemporaryDirectory() as folder:
    state=Store(Path(folder)/'state');project=state.create('qa','Private fixture');pid=project['id'];root=state.path('qa',pid)
    source=Path(folder)/'source';asset=source/'project/results/chart.png';asset.parent.mkdir(parents=True)
    fig,ax=plt.subplots(figsize=(5,3));ax.plot([0,1,2],[0,1,4]);ax.set(xlabel='Time',ylabel='Value');fig.savefig(asset,dpi=150);register(source,'results/chart.png',fig);plt.close(fig)
    embedded=Path(folder)/'embedded.png';metadata=PngImagePlugin.PngInfo();metadata.add_text('source','author artwork')
    with Image.open(asset) as im:im.save(embedded,pnginfo=metadata)
    original=embedded.read_bytes();doc=Document();doc.add_paragraph('Import fixture');doc.add_picture(str(embedded));word=BytesIO();doc.save(word);archive=BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('workbench-import.json',json.dumps({'title':'Import fixture','manuscript':'manuscript/source.docx'}));z.writestr('manuscript/source.docx',word.getvalue())
        for file in source.rglob('*'):
            if file.is_file():z.write(file,file.relative_to(source).as_posix())
    data=archive.getvalue()
    try:import_bundle(state,'qa',pid,data);raise AssertionError('Unregistered serialized state accepted')
    except ValueError as error:assert '图形对象' in str(error);checks.append('Serialized state requires a project-bound receipt from the authorized compute channel')
    digest=hashlib.sha256(data).hexdigest();receipt=state.root/'trusted-figure-imports'/(digest+'.json');atomic_json(receipt,{'owner':'qa','project':pid})
    result=import_bundle(state,'qa',pid,data);checks.append('The exact trusted archive imports into its selected owner project')
    assert len(result['linked_figures'])==1
    image=root/'manuscript/assets'/result['linked_figures'][0]['image'];assert image.read_bytes()==original;checks.append('Import preserves the author embedded image bytes')
    assert image.name in manuscript_links(root,'results/chart.png');checks.append('An explicit source connection does not depend on equal image bytes')
    assert not (root/'slides/plan.json').exists() and not state.get('qa',pid)['config'].get('slides_confirmation');checks.append('Import creates neither a presentation nor a generation confirmation')
    result=save(state,'qa',pid,'results/chart.png',{'objects':{'ax0-line0':{'line_width':2.5}}},1,'Synthetic canvas save')
    assert image.read_bytes()==(root/'project/results/chart.png').read_bytes() and result['updated_references'];checks.append('An explicit canvas save updates the connected manuscript image and records it')
    assert any(item['original']==image.relative_to(root).as_posix() for item in state.trash('qa',pid));checks.append('The embedded source remains recoverable in project history')
print(json.dumps({'passed':len(checks),'checks':checks,'external_model_calls':0},ensure_ascii=False))
