"""Owned process restoration with an actual remote HTTP probe."""
from pathlib import Path
import json, os, shlex, subprocess, time, urllib.request


def http_json(url, timeout=2):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as response:
        return json.load(response)


def spawn(command, folder, prefix, env=None):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    with (folder / (prefix + '-stdout.log')).open('ab') as stdout, (folder / (prefix + '-stderr.log')).open('ab') as stderr:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                env=env, creationflags=0x08000000 if os.name == 'nt' else 0)

def pid_alive(pid):
    if not isinstance(pid,int) or pid<=0:return False
    if os.name=='nt':
        import ctypes
        handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
        if not handle:return False
        try:
            code=ctypes.c_ulong();ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code));return code.value==259
        finally:ctypes.windll.kernel32.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except OSError:return False


def stop_owned(pid, command_marker):
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    if os.name == 'nt':
        marker = command_marker.replace("'", "''")
        script = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(pid) + "';if($p -and $p.CommandLine.Contains('" + marker + "')){Stop-Process -Id " + str(pid) + " -ErrorAction Stop;'stopped'}"
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, text=True, timeout=8)
        return result.returncode == 0 and 'stopped' in result.stdout
    try:
        if command_marker not in (Path('/proc') / str(pid) / 'cmdline').read_bytes().decode(errors='replace'):
            return False
        import signal
        os.kill(pid, signal.SIGTERM); return True
    except (OSError, ValueError):
        return False


def remote_http_ready(port, host='papers-research'):
    code = "import json,urllib.request;d=json.load(urllib.request.urlopen('http://127.0.0.1:" + str(port) + "/health',timeout=3));print(1 if d.get('ok') else 0)"
    try:
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host,
                                 'python3', '-c', shlex.quote(code)], capture_output=True,
                                text=True, timeout=15)
        return result.returncode == 0 and result.stdout.strip() == '1'
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_tunnel(folder, port, host='papers-research'):
    folder = Path(folder); state_path = folder / 'tunnel-state.json'
    if remote_http_ready(port, host):
        return {'ready': True, 'port': port, 'tunnel_reused': True, 'remote_verified': True}
    try:
        previous = json.loads(state_path.read_text(encoding='utf8'))
    except (OSError, ValueError):
        previous = {}
    marker = '127.0.0.1:' + str(port) + ':127.0.0.1:' + str(port)
    stop_owned(previous.get('pid'), marker)
    process = spawn(['ssh', '-N', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
                     '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
                     '-R', marker, host], folder, 'tunnel')
    state_path.write_text(json.dumps({'pid': process.pid, 'port': port, 'host': host}), encoding='utf8')
    for _ in range(3):
        time.sleep(.3)
        if process.poll() is not None:
            break
        if remote_http_ready(port, host):
            return {'ready': True, 'port': port, 'tunnel_reused': False, 'remote_verified': True}
    return {'ready': False, 'port': port, 'local_ready': True,
            'diagnosis': 'reverse_tunnel_unreachable', 'retryable': True}
