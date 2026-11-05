"""Read-only probes of the deployed search endpoints; never print credentials."""
from concurrent.futures import ThreadPoolExecutor
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode


def main():
    origin = 'https://tutor.example.invalid'
    account = json.loads(Path('/srv/deeptutor/migration/admin-login.json').read_text())
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
    login = urllib.request.Request('http://127.0.0.1:8008/api/auth/login',
        data=json.dumps(account).encode(), headers={'Content-Type':'application/json', 'Origin':origin})
    with opener.open(login, timeout=20) as response:
        response.read()
    headers = {'Authorization':'Bearer ' + next(cookie.value for cookie in jar if cookie.name == 'dt_token'), 'Origin':origin}

    def get(path):
        started = time.monotonic()
        status, error = None, None
        try:
            request = urllib.request.Request(origin + path, headers=headers)
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=65) as response:
                status = response.status
                value = json.load(response)
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                value = json.loads(exc.read())
            except ValueError:
                value = {}
            error = str(value.get('detail', 'HTTP request failed'))[:900]
        except Exception as exc:
            value = {}
            error = type(exc).__name__
        items = value.get('items', value.get('results', []))
        return {'http_status':status, 'elapsed_seconds':round(time.monotonic()-started, 2),
            'status':value.get('status'), 'source':value.get('source'), 'count':len(items) if isinstance(items,list) else None,
            'titles':[row.get('title') for row in items[:2]] if isinstance(items,list) else [],
            'message':value.get('message'), 'warnings':value.get('warnings'), 'error':error or value.get('error'),
            'cached':value.get('cached'),
            'keys':list(value), 'provider_status':value.get('provider_status'), 'diagnostics':value.get('diagnostics')}

    projects_request = urllib.request.Request(origin + '/research/api/projects', headers=headers)
    with opener.open(projects_request, timeout=20) as response:
        projects = json.load(response)['projects']
    project = next(p for p in projects if p['name'] == '计算验证能力验收')
    tasks = {
        'web': '/research/api/search/web?' + urlencode({'q':'Anthropic building effective agents', 'kind':'all'}),
        'scholar_mcp': '/research/api/projects/' + project['id'] + '/literature/search?' + urlencode({
            'q':'"Fourier Neural Operator"', 'source':'scholar_mcp', 'years':0, 'page':1, 'limit':2}),
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {name:pool.submit(get, path) for name,path in tasks.items()}
        result = {name:future.result() for name,future in futures.items()}
    print(json.dumps({'project_id':project['id'], 'probes':result}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
