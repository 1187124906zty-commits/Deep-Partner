"""Package code and the selected non-secret skill/context files for this deployment."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile
import tempfile

source=Path(__file__).resolve().parent
archive=Path(tempfile.gettempdir())/'deeptutor-workbench-upload.tar.gz'
skills={
    name:Path('C:/Users/DEVELOPER/.agents/skills')/name
    for name in ['remote-research-cluster','openpaso-simulation','focused-research-engineering','scientific-stage-acceptance','stop-that-shit','diagnosing-bugs','codebase-design','tdd','writing-for-agents','grilling']
}
skills.update({name:Path('C:/Users/DEVELOPER/.codex/skills')/name
               for name in ['simulation-tool-execution','simulation-result-validation','simulation-evidence-preparation','simulation-project-orchestrator']})
provenance=[]
count=0
with tarfile.open(archive,'w:gz') as tar:
    for file in source.rglob('*'):
        if file.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in file.relative_to(source).parts):
            tar.add(file,'workbench-src/'+file.relative_to(source).as_posix());count+=1
    gate=Path('D:/Development/skill开发/deeptutor-registration-approval-20261029/registration_gate.py')
    tar.add(gate,'compat/registration_gate.py');count+=1
    for name,root in skills.items():
        files=[]
        if not (root/'SKILL.md').is_file():
            raise FileNotFoundError(root/'SKILL.md')
        for file in root.rglob('*'):
            if not file.is_file() or file.is_symlink() or file.suffix.lower() not in {'.md','.py','.sh','.json','.toml'}:
                continue
            if any(part.startswith('.') or part in {'__pycache__','node_modules','.venv'} for part in file.relative_to(root).parts):
                continue
            if file.stat().st_size>1_000_000:
                continue
            target='coder-home/.agents/skills/'+name+'/'+file.relative_to(root).as_posix()
            tar.add(file,target);files.append(file.relative_to(root).as_posix());count+=1
        provenance.append({'skill':name,'source':str(root),'target':'/home/coder/.agents/skills/'+name,
                           'files':files,'copied_at':datetime.now(timezone.utc).isoformat()})
    context=Path('D:/Development/skill开发')
    for name in ['CLUSTER_DATA.md','CLUSTER_DATA_CATALOG.md','cluster-data-mapping-20261025.tsv']:
        if (context/name).exists():
            tar.add(context/name,'coder-home/research-context/'+name);count+=1
    registry=Path('C:/Users/DEVELOPER/.pi/research-projects.json')
    tar.add(registry,'coder-home/research-context/research-projects.json')
    project=Path('D:/Development/chloride-sulfate-pino-bayes/research')
    for name in ['BRIEF.md','STATE.md','EVIDENCE.md']:
        if (project/name).exists():
            tar.add(project/name,'coder-home/research-context/chloride-sulfate-pino-bayes/'+name)
    raw=json.dumps({'skills':provenance,'note':'Only selected text and scripts; no SSH keys, browser sessions, runtime environments or raw simulation data copied. Historical state must be rechecked before computation.'},ensure_ascii=False,indent=2).encode('utf-8')
    info=tarfile.TarInfo('coder-home/research-context/SKILL_SOURCES.json');info.size=len(raw)
    tar.addfile(info,io.BytesIO(raw))
print(json.dumps({'archive':str(archive),'files':count,'bytes':archive.stat().st_size,'skills':list(skills)},ensure_ascii=False))
