"""Install beside the existing Tutor and DeepCode; preserve their core images."""
from pathlib import Path
import http.cookiejar
import json
import os
import secrets
import shutil
import subprocess
import urllib.request
import urllib.error

ROOT = Path('/srv/tutor-research-compute')
APP = ROOT / 'app'
PRIVATE = ROOT / 'private'
AUTH_COOKIE = ''


def call_json(client, path, value=None):
    data = json.dumps(value).encode() if value is not None else None
    request = urllib.request.Request('http://127.0.0.1:8008' + path, data=data,
                                     headers={'Content-Type': 'application/json', 'Cookie': AUTH_COOKIE,
                                              'Origin': 'https://tutor.example.invalid'})
    with client.open(request, timeout=30) as response:
        return json.load(response)


def main():
    global AUTH_COOKIE
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
    account = json.loads(Path('/srv/deeptutor/migration/admin-login.json').read_text())
    call_json(client, '/api/auth/login', account)
    AUTH_COOKIE = '; '.join(cookie.name + '=' + cookie.value for cookie in jar)
    profile = call_json(client, '/api/auth/profile')
    assert profile['role'] == 'admin'
    owner = profile['id']
    token_file = PRIVATE / 'token'
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(36))
        token_file.chmod(0o600)
    ssh_config = '''Host tutor-compute-cluster
    HostName xh5.hpccube.com
    Port 65061
    User cluster_user
    IdentityFile /run/compute-secrets/cluster_ed25519
    UserKnownHostsFile /run/compute-secrets/known_hosts
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
    ConnectTimeout 15
'''
    (PRIVATE / 'ssh-config').write_text(ssh_config)
    shutil.copyfile('/srv/deeptutor/coder-home/.ssh/known_hosts', PRIVATE / 'known_hosts')
    image = json.loads(subprocess.check_output(['docker', 'inspect', 'deeptutor-coder']))[0]['Image']
    service = {'image': image, 'pull_policy': 'never', 'container_name': 'research-compute',
        'restart': 'unless-stopped', 'user': '1000:1000', 'entrypoint': ['python'],
        'command': ['-m', 'uvicorn', 'compute_mcp:app', '--app-dir', '/opt/research-compute', '--host', '0.0.0.0', '--port', '47920'],
        'networks': ['tutor'], 'ports': ['127.0.0.1:47920:47920'],
        'environment': {'COMPUTE_OWNER_ID': owner, 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1'},
        'volumes': [str(APP) + ':/opt/research-compute:ro', str(PRIVATE) + ':/run/compute-secrets:ro'],
        'mem_limit': '192m', 'cpus': 0.5,
        'logging': {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}}}
    compose = ROOT / 'compose.json'
    compose.write_text(json.dumps({'name': 'tutor-research-compute', 'services': {'compute': service},
        'networks': {'tutor': {'external': True, 'name': 'deeptutor_default'}}}, indent=2))
    subprocess.run(['docker', 'compose', '-f', str(compose), 'up', '-d'], check=True)

    # Reuse the already mounted, approved Python-extension directory.
    extension = Path('/srv/dify-research/tutor-extension')
    shutil.copyfile(APP / 'tutor_compute.py', extension / 'tutor_compute.py')
    shutil.copyfile(APP / 'research_delegate.py', extension / 'research_delegate.py')
    shutil.copyfile(token_file, extension / 'compute-token')
    (extension / 'compute-token').chmod(0o600)
    dist = extension / 'deeptutor_research_compute-0.1.0.dist-info'
    dist.mkdir(exist_ok=True)
    (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: deeptutor-research-compute\nVersion: 0.1.0\n')
    (dist / 'entry_points.txt').write_text('[deeptutor.tools]\nresearch_code = research_delegate:ResearchCodeTool\n\n[deeptutor.extensions]\nresearch_delegation = research_delegate:ResearchDelegation\n')
    (dist / 'RECORD').write_text('')
    skill = (APP / 'skills/research-compute-validation/SKILL.md').read_text()
    detail = None
    try:
        detail = call_json(client, '/api/skills/research-compute-validation')
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    if detail is None:
        call_json(client, '/api/skills/create', {'name': 'research-compute-validation',
            'description': '用真实Slurm计算、openPASO和预先判据检验研究方法与程序，回读原始证据并反馈工作台。',
            'content': skill.split('---', 2)[2].strip(), 'tags': ['research', 'compute']})

    home = Path('/srv/deeptutor/coder-home')
    config_path = home / '.deepcode/deepcode_config.json'
    config = json.loads(config_path.read_text())
    original = PRIVATE / 'deepcode-config.before.json'
    if not original.exists():
        shutil.copyfile(config_path, original)
        original.chmod(0o600)
    proxy = home / 'research-context/tools/research-compute-mcp.py'
    proxy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(APP / 'deepcode_proxy.py', proxy)
    shutil.copyfile(token_file, home / '.deepcode/compute-token')
    (home / '.deepcode/compute-token').chmod(0o600)
    config.setdefault('mcpServers', {})['research-compute'] = {
        'type': 'stdio', 'command': 'python', 'args': ['/home/coder/research-context/tools/research-compute-mcp.py'],
        'enabled': True, 'toolTimeoutSeconds': 90, 'startupTimeoutSeconds': 30}
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    skill_path = home / '.agents/skills/research-compute-validation'
    skill_path.mkdir(exist_ok=True)
    (skill_path / 'SKILL.md').write_text(skill)
    subprocess.run(['docker', 'restart', 'deeptutor'], check=True)
    (ROOT / 'installation.json').write_text(json.dumps({'owner_id': owner, 'mcp_url': 'http://research-compute:47920/mcp',
        'tutor_tool': 'research_code', 'deepcode_mcp': 'research-compute', 'skill': 'research-compute-validation',
        'image': image, 'cluster_root': '/work/home/cluster_user/research-projects/tutor-compute'}, indent=2))
    print('Research Compute installed for the existing administrator, native Tutor and DeepCode.')


if __name__ == '__main__':
    main()
