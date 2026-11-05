"""Shift the default research loop to Tutor -> Code -> project handoff."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/srv/tutor-research-compute')
EXTENSION = Path('/srv/dify-research/tutor-extension')

shutil.copyfile(ROOT / 'app/research_delegate.py', EXTENSION / 'research_delegate.py')
dist = EXTENSION / 'deeptutor_research_compute-0.1.0.dist-info'
(dist / 'entry_points.txt').write_text('''[deeptutor.tools]
research_code = research_delegate:ResearchCodeTool

[deeptutor.extensions]
research_delegation = research_delegate:ResearchDelegation
''')
skill = (ROOT / 'app/skills/research-compute-validation/SKILL.md').read_text()
shutil.copyfile(ROOT / 'app/skills/research-compute-validation/SKILL.md', Path('/srv/deeptutor/coder-home/.agents/skills/research-compute-validation/SKILL.md'))
for target in Path('/srv/deeptutor/data').glob('**/research-compute-validation/SKILL.md'):
    old = target.read_text()
    header = old.split('---', 2)[:2]
    if len(header) == 2:
        target.write_text('---' + header[1] + '---\n\n' + skill.split('---', 2)[2].strip() + '\n')
subprocess.run(['docker', 'restart', 'deeptutor'], check=True)
print('Default research delegation enabled. Compute MCP remains assigned to Code.')
