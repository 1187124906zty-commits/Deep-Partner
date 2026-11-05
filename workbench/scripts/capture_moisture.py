"""Bounded plotting test on source CSVs, with reusable editable figure objects."""
from pathlib import Path
import importlib,json,os,pickle,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
workspace=Path(sys.argv[1]).resolve();project=workspace/'project';plots=project/'src/plots'
sys.path.insert(0,str(plots))
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
for font in (ROOT.parent/'fonts').glob('*.ttf'):font_manager.fontManager.addfont(str(font))
assert font_manager.findfont('Times New Roman',fallback_to_default=False)
assert font_manager.findfont('Arial',fallback_to_default=False)
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from server.figures import register,read_registry,read_figure
import cloudpickle
import server.figures as figure_runtime
# Retain authored formatter functions in the captured object itself.
figure_runtime.serialize_figure=lambda figure:cloudpickle.dumps(figure,protocol=pickle.HIGHEST_PROTOCOL)
checks=[];captured=[];original=Figure.savefig
def save(figure,filename,*args,**kwargs):
    if isinstance(filename,(str,Path)) and Path(filename).suffix.lower() in ('.tif','.tiff'):return
    result=original(figure,filename,*args,**kwargs)
    if isinstance(filename,(str,Path)):
        path=Path(filename).resolve()
        if path.is_relative_to(project) and path.suffix=='.png':
            for module in list(sys.modules.values()):
                filename=getattr(module,'__file__',None)
                if filename and Path(filename).resolve().is_relative_to(plots):cloudpickle.register_pickle_by_value(module)
            n=active_plot;entry=register(workspace,path.relative_to(project).as_posix(),figure,'src/plots/plot_figure%02d.py'%n)
            captured.append(entry['asset'])
    return result
Figure.savefig=save
for n in range(1,17):
    active_plot=n
    if n==1:
        print('SCHEMATIC retained final authored vector source; no Matplotlib canvas',flush=True);continue
    name='plot_figure%02d'%n;module=importlib.import_module(name);fn=getattr(module,name)
    print('PLOT',name,flush=True);fn(project/'data/tables'/('figure%02d.csv'%n),project/'results');plt.close('all')
for asset in captured:
    figure,entry=read_figure(workspace,asset);assert figure is not None;plt.close(figure)
checks.append('Figure 1 is an authored vector schematic; its latest AI/PDF/PNG source is retained separately without Matplotlib registration')
checks.append('All captured figures deserialize and retain their native Matplotlib objects')
sources=list((project/'src').rglob('*.py'))
for source in sources:compile(source.read_text(encoding='utf-8-sig'),str(source),'exec')
checks.append('Imported model and plotting source files compile without running training')
report={'captured':captured,'python':sys.version.split()[0],'matplotlib':matplotlib.__version__,'compiled_sources':len(sources),'checks':checks,'training_performed':False,'scientific_scope':'Replot existing supplied numerical tables. No new predictions, parameter identification or model validation.'}
(project/'docs/import-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
archive=workspace.parent/'moisture-workbench.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    for p in workspace.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.tiff','.tif'):z.write(p,p.relative_to(workspace).as_posix())
print(json.dumps({**report,'archive':str(archive),'bytes':archive.stat().st_size}),flush=True)
