"""Make a text/script-only bundle of selected, actually installed coding skills."""
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import tarfile
import tempfile

source=Path(__file__).resolve().parent
selected={name:Path('C:/Users/DEVELOPER/.agents/skills')/name for name in [
    'remote-research-cluster','openpaso-simulation','focused-research-engineering',
    'scientific-stage-acceptance','stop-that-shit','diagnosing-bugs','codebase-design','tdd','writing-for-agents','grilling']}
selected.update({name:Path('C:/Users/DEVELOPER/.codex/skills')/name for name in [
    'simulation-tool-execution','simulation-result-validation','simulation-evidence-preparation','simulation-project-orchestrator']})
archive=Path(tempfile.gettempdir())/'deeptutor-coding-context.tar.gz'
provenance=[]
with tarfile.open(archive,'w:gz') as tar:
    for name,root in selected.items():
        if not (root/'SKILL.md').exists():raise FileNotFoundError(root)
        files=[]
        for file in root.rglob('*'):
            rel=file.relative_to(root)
            if not file.is_file() or file.is_symlink() or file.suffix.lower() not in {'.md','.py','.sh','.json','.toml','.yaml','.yml'}:continue
            if any(x.startswith('.') or x in {'__pycache__','node_modules'} for x in rel.parts):continue
            if file.stat().st_size>1_000_000:continue
            tar.add(file,'coder-home/.agents/skills/'+name+'/'+rel.as_posix())
            files.append({'path':rel.as_posix(),'bytes':file.stat().st_size})
        provenance.append({'skill':name,'source':str(root),'target':'/home/coder/.agents/skills/'+name,'files':files})
    tar.add(source/'coder-AGENTS.md','coder-home/.deepcode/AGENTS.md')
    tar.add(source/'coder-AGENTS.md','workspaces/coder/AGENTS.md')
    rules=Path('D:/Development/AGENTS.md')
    if rules.exists():tar.add(rules,'coder-home/research-context/LOCAL_PROJECT_RULES.md')
    data={'copied_at':datetime.now(timezone.utc).isoformat(),'skills':provenance,
          'effective_rules':'/home/coder/.deepcode/AGENTS.md',
          'original_project_rules':'/home/coder/research-context/LOCAL_PROJECT_RULES.md',
          'guard_hooks_installed':False,
          'note':'Selected actual skills, source documents and scripts; no credentials, virtualenvs or browser sessions.'}
    raw=json.dumps(data,ensure_ascii=False,indent=2).encode()
    info=tarfile.TarInfo('coder-home/research-context/SKILL_SOURCES.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
print(json.dumps({'archive':str(archive),'skills':list(selected),'files':sum(len(x['files']) for x in provenance)},ensure_ascii=False))
