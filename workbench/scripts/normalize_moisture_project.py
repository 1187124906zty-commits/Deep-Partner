from pathlib import Path
import json,tarfile

def normalize(root):
    root=Path(root);project=root/'project';checks=project/'docs/plot-checks';checks.mkdir(parents=True,exist_ok=True);moved=[]
    for p in (project/'results').iterdir():
        if p.is_file() and (p.suffix=='.json' or p.name.endswith('.alignment.svg') or p.name.endswith('-plotted-statistics.csv')):
            target=checks/p.name;p.replace(target);moved.append(p.name)
    return moved
