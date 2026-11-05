"""Probe this uvicorn process, not the parent image's unrelated API port."""
from pathlib import Path
import json
import urllib.request


def main():
    arguments=Path('/proc/1/cmdline').read_bytes().decode().split('\0')
    if '--port' not in arguments:raise RuntimeError('Service has no explicit uvicorn port')
    port=int(arguments[arguments.index('--port')+1])
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with client.open(f'http://127.0.0.1:{port}/health',timeout=5) as response:
        if response.status!=200 or json.load(response).get('ok') is not True:
            raise RuntimeError('Service health response is not ready')


if __name__=='__main__':main()
