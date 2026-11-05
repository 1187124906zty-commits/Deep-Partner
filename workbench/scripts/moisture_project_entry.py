"""Redraw supplied Mois-Net data tables; this entry never trains a network."""
from pathlib import Path
import argparse,importlib,sys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figures',type=int,nargs='+',default=list(range(2,17)))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();project=Path(__file__).resolve().parents[1]
    plots=project/'src/plots';sys.path.insert(0,str(plots));output=args.output or project/'results'
    if any(n not in range(2,17) for n in args.figures):parser.error('Figure 1 is retained as an authored AI/PDF/PNG schematic. Select figures 2–16.')
    for number in args.figures:
        name=f'plot_figure{number:02d}';module=importlib.import_module(name)
        getattr(module,name)(project/'data/tables'/f'figure{number:02d}.csv',output)
        print(f'Redrawn {number:02d}: supplied CSV/spec only',flush=True)

if __name__=='__main__':main()
