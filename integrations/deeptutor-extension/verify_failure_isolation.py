"""Run on deployment host: stop only the Coder container and probe Tutor."""
import json
from pathlib import Path
import subprocess

root=Path('/srv/deeptutor/migration')
result={}
try:
    subprocess.run(['docker','stop','deeptutor-coder'],check=True)
    result['coder_stopped']=True
    subprocess.run(['docker','exec','--user','1000:1000','-e','PYTHONPATH=/app',
                    'deeptutor','python','/migration/verify_application.py'],check=True)
    app=json.loads((root/'application-verification.json').read_text())
    result['tutor_works_without_coder']={
        'health':app['health'],'original_session':app['original_session'],
        'knowledge_bases_http':app['knowledge_bases_http'],'live_chat':app['live_chat'],
    }
finally:
    subprocess.run(['docker','start','deeptutor-coder'],check=True)
    result['coder_restarted']=True
    (root/'failure-isolation-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False),flush=True)
