"""Install the reviewed release only when deployed source still matches its baseline."""
from pathlib import Path
import json
import shutil
import tarfile

ROOT=Path('/srv/dify-research')
STAGE=ROOT/'staging/research-extension'
STAGE.mkdir(parents=True,exist_ok=True)
with tarfile.open(ROOT/'optimization-release.tar.gz') as archive:
    for member in archive.getmembers():
        if not (STAGE/member.name).resolve().is_relative_to(STAGE.resolve()) or member.issym() or member.islnk():
            raise ValueError('Unexpected release member')
    archive.extractall(STAGE)

pairs=[]
for name in ('delivery.py','mcp_server.py','workbench_mcp/client.py','workbench_mcp/tools/workspace_api.py'):
    pairs.append((STAGE/'bridge'/name,ROOT/'bridge'/name,STAGE/'.local/optimization-baseline/bridge'/name))
for name in ('search_mcp.py','network_sources.py','literature_network.py','references.py','search_errors.py'):
    pairs.append((STAGE/'workbench-search/server'/name,Path('/srv/research-workbench/source/server')/name,
        STAGE/'.local/optimization-baseline/search'/name))
for source,target,baseline in pairs:
    if target.exists() and target.read_bytes()!=source.read_bytes():
        if not baseline.is_file() or target.read_bytes()!=baseline.read_bytes():
            raise RuntimeError('Deployed file changed after review; merge before installing: '+str(target))
for source,target,baseline in pairs:
    shutil.copyfile(source,target)
for folder in ('ops','docs','tests'):
    for source in (STAGE/folder).glob('*'):
        if source.is_file():
            target=ROOT/folder/source.name;target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source,target)
# Retire the former root-level 11-node builder while preserving its command entry point.
(ROOT/'configure_mcp_workflow.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).parent/"ops"))\nfrom optimize_workflow import main\nif __name__=="__main__":main()\n')
print(json.dumps({'installed':True,'changed_modules':[str(target) for _,target,_ in pairs],
    'services_not_restarted':True},ensure_ascii=False))
