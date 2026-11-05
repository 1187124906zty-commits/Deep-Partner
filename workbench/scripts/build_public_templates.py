from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.presentation_catalog import catalog,create_public_template
for spec in catalog()['templates']:
    path=ROOT/'templates/presentations'/(spec['id']+'.pptx');create_public_template(spec['id'],path);print(json.dumps({'template':spec['id'],'bytes':path.stat().st_size,'source':spec['source']}),flush=True)
