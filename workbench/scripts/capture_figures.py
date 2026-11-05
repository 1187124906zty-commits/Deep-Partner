"""Execute a specified plotting script and retain its actual Matplotlib objects."""
from pathlib import Path
import argparse,json,runpy,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from server.figures import register

p=argparse.ArgumentParser();p.add_argument('workspace');p.add_argument('program');p.add_argument('--compute',default='');args=p.parse_args()
workspace=Path(args.workspace).resolve();project=workspace/'project';program=(project/args.program).resolve()
assert program.is_relative_to(project) and program.is_file()
original=Figure.savefig


def capture(figure,filename,*a,**kw):
    result=original(figure,filename,*a,**kw)
    if isinstance(filename,(str,Path)):
        image=Path(filename).resolve()
        if image.is_relative_to(project) and image.suffix.lower()=='.png':
            # register's internal SVG export is not another PNG capture.
            entry=register(workspace,image.relative_to(project).as_posix(),figure,args.program,args.compute)
            print(json.dumps({'captured':entry['asset'],'matplotlib':entry['matplotlib'],'revision':entry['revision']}),flush=True)
    return result


Figure.savefig=capture
runpy.run_path(str(program),run_name='__main__')
