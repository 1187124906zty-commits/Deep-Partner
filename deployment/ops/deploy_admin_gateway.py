"""Publish /admin/ without changing the original account or workbench behavior."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]

DEPLOY = r"""
from pathlib import Path
import json,os,shutil,subprocess,time,urllib.request

root=Path('/srv/deep-partner-admin');root.mkdir(exist_ok=True)
private=root/'private';private.mkdir(mode=0o700,exist_ok=True)
credentials=private/'login.json'
shutil.copyfile('/srv/deeptutor/migration/admin-login.json',credentials)
credentials.chmod(0o600);os.chown(credentials,1000,1000)
native=json.loads(subprocess.check_output(['docker','inspect','deeptutor'],text=True))[0]
assert json.loads(Path('/srv/deeptutor/data/user/settings/auth.json').read_text())['enabled'] is True
compile((root/'admin_gateway.py').read_text(),str(root/'admin_gateway.py'),'exec')

name='deep-partner-admin'
existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
if existing.returncode==0:
    subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)
command=['docker','run','-d','--name',name,'--restart','unless-stopped','--network','host',
         '--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges',
         '--read-only','--tmpfs','/tmp:rw,size=64m','--memory','512m','--cpus','0.5',
         '-e','PYTHONDONTWRITEBYTECODE=1',
         '-v',str(root/'admin_gateway.py')+':/srv/admin/admin_gateway.py:ro',
         '-v',str(root/'architecture.md')+':/srv/admin/architecture.md:ro',
         '-v',str(root/'review')+':/srv/admin/review:ro',
         '-v',str(credentials)+':/run/secrets/admin-login.json:ro',
         '-v','/srv/research-workbench/source/static:/srv/admin-static:ro',
         '--workdir','/srv/admin','--entrypoint','python',native['Image'],
         '-m','uvicorn','admin_gateway:app','--host','127.0.0.1','--port','47918',
         '--no-access-log','--ws-max-size','43341141']
subprocess.run(command,check=True,capture_output=True)
for _ in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:47918/health',timeout=2) as response:
            if json.load(response).get('scope')=='/admin':break
    except OSError:pass
    time.sleep(.5)
else:
    raise RuntimeError(subprocess.check_output(['docker','logs',name],text=True)[-4000:])

with urllib.request.urlopen('http://127.0.0.1:47918/admin/research/api/bootstrap',timeout=20) as response:
    bootstrap=json.load(response)
assert bootstrap['user']['role']=='admin'
assert bootstrap['auth']['enabled'] is True and bootstrap['auth']['authenticated'] is True
assert any(p['id']=='c37b9168a0db40e3b258c9c03cd56697' for p in bootstrap['projects'])

route=Path('/etc/caddy/deep-partner-admin.caddy')
route.write_text('''# Separate anonymous administrator entrance; original routes remain in place.
handle /admin {
    reverse_proxy 127.0.0.1:47918
}
handle /admin/* {
    reverse_proxy 127.0.0.1:47918 {
        flush_interval -1
    }
}
''')
caddy=Path('/etc/caddy/deeptutor.caddy');prior=caddy.read_text()
line='    import /etc/caddy/deep-partner-admin.caddy\n'
if line not in prior:
    assert '    encode gzip\n' in prior
    caddy.write_text(prior.replace('    encode gzip\n','    encode gzip\n'+line,1))
try:
    subprocess.run(['caddy','validate','--config',str(caddy),'--adapter','caddyfile'],check=True,capture_output=True)
except Exception:
    caddy.write_text(prior)
    raise
subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
print(json.dumps({'deployed':True,'entry':'https://tutor.example.invalid/admin/',
                  'architecture':'https://tutor.example.invalid/admin/architecture',
                  'schema':'https://tutor.example.invalid/admin/research/api/schema',
                  'original_auth_enabled':True,'project_count':len(bootstrap['projects']),
                  'container':name,'port':47918,'original_services_restarted':False},ensure_ascii=False))
"""


def main():
    subprocess.run(['ssh','papers-research','sudo -n mkdir -p /srv/deep-partner-admin; sudo -n chown ubuntu:ubuntu /srv/deep-partner-admin'],check=True)
    for source,name in [(ROOT/'ops/admin_gateway.py','admin_gateway.py'),
                        (ROOT/'docs/DeepPartner管理员入口架构.md','architecture.md')]:
        subprocess.run(['scp','-q',str(source),'papers-research:/srv/deep-partner-admin/'+name],check=True)
    review=ROOT/'reports/admin-review'
    if (review/'manifest.json').is_file():
        subprocess.run(['ssh','papers-research','mkdir -p /srv/deep-partner-admin/review'],check=True)
        sources=[str(source) for source in review.iterdir() if source.suffix in ('.png','.json')]
        subprocess.run(['scp','-q',*sources,'papers-research:/srv/deep-partner-admin/review/'],check=True)
    result=subprocess.run(['ssh','papers-research','sudo -n python3 -'],input=DEPLOY,
                          text=True,encoding='utf8',capture_output=True,timeout=80)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:]+result.stdout[-2000:])
    report=json.loads(result.stdout.splitlines()[-1])
    (ROOT/'reports/admin-gateway-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
