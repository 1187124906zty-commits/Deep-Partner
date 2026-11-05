"""Token protected loopback bridge. Recovery only uses explicitly configured commands."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import os
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from server.scholar_mcp_client import request, failure, TOOLS


def invoke(config, payload):
    try:
        result = subprocess.run([config['python'], '-X', 'utf8', str(ROOT/'server/scholar_mcp_client.py')],
            input=json.dumps(payload), text=True, encoding='utf8', capture_output=True, timeout=40)
        value = json.loads(result.stdout.strip().splitlines()[-1])
        if not isinstance(value, dict):
            raise ValueError('Invalid envelope')
        return value
    except (FileNotFoundError, KeyError):
        return failure('interpreter_missing', 'Configured Scholar interpreter does not exist')
    except subprocess.TimeoutExpired:
        return failure('mcp_transport_error', 'Scholar MCP subprocess timed out', True)
    except (ValueError, IndexError, OSError):
        return failure('mcp_protocol_error', 'Scholar subprocess did not return a JSON envelope')


def diagnostics(config):
    # This runs inside the configured interpreter, not the bridge interpreter.
    probe = """import importlib.util,json,os,urllib.request
modules={name:importlib.util.find_spec(name) is not None for name in ('mcp','scholar_mcp')}
proxy=bool(urllib.request.getproxies())
try:
 with urllib.request.urlopen('https://scholar.google.com/',timeout=8) as response:
  body=response.read(100000).decode('utf8',errors='replace').lower()
  status=response.status
  if '/sorry/' in response.url or any(text in body for text in ('gs_captcha','g-recaptcha','unusual traffic','verify you are human')):
   status='verification_required'
except Exception as error:
 status=getattr(error,'code',type(error).__name__)
print(json.dumps({'modules':modules,'proxy_configured':proxy,'network_status':status}))
"""
    try:
        result = subprocess.run([config['python'], '-X', 'utf8', '-c', probe], capture_output=True,
                                text=True, encoding='utf8', timeout=12)
        environment = json.loads(result.stdout.strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        environment = {'error': 'interpreter_probe_failed'}
    handshake = invoke(config, {'operation': 'diagnostics'})
    status = environment.get('network_status')
    missing = [name for name, present in environment.get('modules', {}).items() if not present]
    reason = ('interpreter_missing' if not Path(config.get('python', '')).is_file() else
              'python_module_missing' if missing else
              'verification_required' if status == 'verification_required' else
              'rate_limited' if status == 429 else 'blocked' if status == 403 else
              'network_error' if status is not None and not isinstance(status, int) else None)
    if reason is None and not handshake.get('ok'):
        reason = (handshake.get('error') or {}).get('code', 'mcp_protocol_error')
    actions = {
        'interpreter_missing': 'Restore the configured interpreter path; no interpreter was installed.',
        'python_module_missing': 'Restore mcp/scholar_mcp in the configured interpreter; no packages were installed.',
        'mcp_protocol_error': 'Check MCP initialize/list_tools response and installed package compatibility.',
        'mcp_transport_error': 'Check the configured MCP service; only configured recovery is permitted.',
        'network_error': 'Check network and the configured proxy; only configured proxy recovery is permitted.',
        'verification_required': 'Complete verification manually in the provider browser.',
        'blocked': 'Provider blocked access; wait or review access manually.',
        'rate_limited': 'Provider rate limit; wait before a later explicit request.',
    }
    return {'ok': handshake.get('ok', False), 'environment': environment,
            'mcp': handshake, 'reason': reason, 'bridge': 'reachable',
            'missing_modules': missing,
            'action': actions.get(reason, 'Inspect the returned MCP handshake and network status.'),
            'configured_recovery': sorted(config.get('repair_commands', {}))}


def repair(config, payload):
    reason = payload.get('code')
    # No package installation, challenge handling, or arbitrary client supplied command.
    target = {'bridge_transport_error': 'tunnel', 'network_error': 'proxy',
              'proxy_error': 'proxy', 'mcp_transport_error': 'service'}.get(reason)
    command = config.get('repair_commands', {}).get(target)
    if not target or not command:
        return {'ok': False, 'attempted': False, 'reason': 'no_configured_recovery'}
    if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
        return {'ok': False, 'attempted': False, 'reason': 'invalid_recovery_config'}
    try:
        result = subprocess.run(command, capture_output=True, timeout=15)
        return {'ok': result.returncode == 0, 'attempted': True, 'target': target}
    except (OSError, subprocess.TimeoutExpired):
        return {'ok': False, 'attempted': True, 'target': target}


def health(config):
    """Cheap readiness probe; no MCP call, Scholar HTTP query, or recovery action."""
    probe = """import importlib.util,json,socket,urllib.request,urllib.parse
modules=all(importlib.util.find_spec(name) is not None for name in ('mcp','scholar_mcp'))
proxies=urllib.request.getproxies()
proxy=proxies.get('https') or proxies.get('all')
target=urllib.parse.urlsplit(proxy if '://' in (proxy or '') else 'http://'+proxy) if proxy else None
try:
 connection=socket.create_connection((target.hostname,target.port or 80) if target else ('scholar.google.com',443),timeout=2)
 connection.close()
 network=True
except (OSError,ValueError):network=False
print(json.dumps({'modules_ready':modules,'network_ready':network,'proxy_configured':bool(proxy)}))
"""
    try:
        result = subprocess.run([config['python'], '-X', 'utf8', '-c', probe],
            capture_output=True, text=True, encoding='utf8', timeout=4)
        checks = json.loads(result.stdout.strip().splitlines()[-1])
        return {'ok': True, 'ready': checks.get('modules_ready') is True and checks.get('network_ready') is True,
                'checks': checks, 'source': 'Google Scholar · MCP'}
    except (OSError,KeyError,ValueError,IndexError,subprocess.TimeoutExpired):
        return {'ok': True, 'ready': False, 'reason': 'runtime_probe_unavailable'}


def handler_for(config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, value):
            data = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/health':
                self.reply(200, health(config))
            elif self.path == '/capabilities':
                self.reply(200, {'ok': True, 'tools': list(TOOLS), 'envelope': True,
                                 'diagnostics': True, 'repair': True})
            else:
                self.reply(404, {'ok': False})

        def do_POST(self):
            if self.path not in ('/scholar', '/diagnostics', '/repair'):
                self.reply(404, {'ok': False})
                return
            token = config.get('token', '')
            if not token or not secrets.compare_digest(self.headers.get('x-workbench-search', ''), token):
                self.reply(403, {'ok': False})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 1 <= size <= 10000:
                    raise ValueError('Invalid request size')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Request must be an object')
                if self.path == '/scholar':
                    tool, arguments = request(payload)
                    value = invoke(config, {'tool': tool, 'arguments': arguments})
                elif self.path == '/diagnostics':
                    value = diagnostics(config)
                else:
                    value = repair(config, payload)
                self.reply(200, value)
            except (ValueError, TypeError):
                self.reply(400, failure('invalid_arguments', 'Invalid Scholar request parameters'))
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    ThreadingHTTPServer(('127.0.0.1', int(config.get('port', 47903))), handler_for(config)).serve_forever()


if __name__ == '__main__':
    main()
