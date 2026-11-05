"""Publish the built /dify frontend through the existing TLS virtual host."""
from pathlib import Path
import subprocess

ROOT = Path('/srv/dify-research')
ORIGIN = 'https://tutor.example.invalid'
PREFIX = ORIGIN + '/dify'
IMAGE = 'codex/dify-web:1.18.0-dify'


def run(*args):
    subprocess.run(args, check=True)


def main():
    run('docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}')
    override = ROOT / 'compose.override.yaml'
    text = override.read_text()
    lines = text.splitlines()
    inside_web = False
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith('  ') and not line.startswith('    ') and line.endswith(':'):
            inside_web = line.strip() == 'web:'
        if inside_web and line.startswith('    image:'):
            current = line.split(': ', 1)[1]
            if not (current.startswith('langgenius/dify-web:1.18.0@sha256:') or current == IMAGE):
                raise SystemExit('Inspect the changed frontend image before publishing.')
            lines[index] = '    image: ' + IMAGE
            replaced = True
    if not replaced:
        raise SystemExit('Existing web service not found')
    override.write_text('\n'.join(lines) + '\n')

    env = ROOT / 'upstream/docker/.env'
    updates = {key: PREFIX for key in ('CONSOLE_API_URL', 'CONSOLE_WEB_URL', 'SERVICE_API_URL',
                                      'APP_API_URL', 'APP_WEB_URL', 'FILES_URL', 'TRIGGER_URL')}
    updates.update(NEXT_PUBLIC_BASE_PATH='/dify', INTERNAL_FILES_URL='http://api:5001',
                   SERVER_CONSOLE_API_URL='http://api:5001',
                   NEXT_PUBLIC_SOCKET_URL='wss://tutor.example.invalid/dify',
                   WEB_API_CORS_ALLOW_ORIGINS=ORIGIN, CONSOLE_CORS_ALLOW_ORIGINS=ORIGIN)
    lines = []
    pending = dict(updates)
    for line in env.read_text().splitlines():
        key = line.split('=', 1)[0]
        lines.append(key + '=' + pending.pop(key) if key in pending else line)
    lines.extend(key + '=' + value for key, value in pending.items())
    env.write_text('\n'.join(lines) + '\n')
    env.chmod(0o600)

    compose = ['docker', 'compose', '--project-directory', str(ROOT / 'upstream/docker'),
               '-f', str(ROOT / 'upstream/docker/docker-compose.yaml'), '-f', str(override)]
    run(*compose, 'config', '--quiet')
    run(*compose, 'up', '-d', '--no-deps', 'api', 'worker', 'worker_beat', 'web')

    route = ROOT / 'dify-workbench.caddy'
    route.write_text('''handle /research/dify/* {
    reverse_proxy 127.0.0.1:47910
}
handle /dify {
    redir /dify/apps 308
}
handle /dify/* {
    route {
        @dify_api path /dify/console/api/* /dify/api/* /dify/v1/* /dify/openapi/* /dify/files/* /dify/e/* /dify/mcp /dify/mcp/* /dify/triggers/* /dify/socket.io/*
        handle @dify_api {
            uri strip_prefix /dify
            reverse_proxy 127.0.0.1:8088
        }
        handle {
            reverse_proxy 127.0.0.1:8088
        }
    }
}
''')
    run('sudo', '-n', 'install', '-m', '644', str(route), '/etc/caddy/dify-workbench.caddy')
    run('sudo', '-n', 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
    run('sudo', '-n', 'systemctl', 'reload', 'caddy')
    print('Dify console published at ' + PREFIX + '/apps')


if __name__ == '__main__':
    main()
