"""Verify the public TLS route, real console login, and built frontend assets."""
import base64
import http.cookiejar
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin

ROOT = Path('/srv/dify-research')
BASE = 'https://tutor.example.invalid/dify'
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))


def request(path, body=None):
    headers = {'Content-Type': 'application/json', 'Origin': 'https://tutor.example.invalid'}
    csrf = next((cookie.value for cookie in jar if 'csrf' in cookie.name), '')
    if csrf:
        headers['X-CSRF-Token'] = csrf
    data = json.dumps(body).encode() if body is not None else None
    with client.open(urllib.request.Request(BASE + path, data=data, headers=headers), timeout=60) as response:
        return response.read(), response.geturl()


def main():
    deadline = time.monotonic() + 150
    while True:
        try:
            setup = json.loads(request('/console/api/setup')[0])
            break
        except urllib.error.HTTPError as error:
            if error.code not in {502, 503} or time.monotonic() > deadline:
                raise
            time.sleep(3)
    assert setup['step'] == 'finished', setup
    content, page_url = request('/signin')
    html = content.decode()
    paths = list(dict.fromkeys(re.findall(r'(?:src|href)="([^"<>]+\.(?:js|css)(?:\?[^"<>]*)?)"', html)))
    assert paths and all(path.startswith('/dify/') for path in paths), paths[:10]
    for path in paths[:6]:
        with client.open(urljoin(page_url, path), timeout=60) as response:
            assert response.status == 200
            assert len(response.read()) > 0

    account = json.loads((ROOT / 'private/admin-login.json').read_text())
    login = json.loads(request('/console/api/login', {
        'email': account['email'], 'password': base64.b64encode(account['password'].encode()).decode(),
        'remember_me': True,
    })[0])
    assert login.get('result') == 'success', login
    cookies = [cookie for cookie in jar if 'access_token' in cookie.name]
    assert cookies and all(cookie.secure and cookie.name.startswith('__Host-') for cookie in cookies)
    apps = json.loads(request('/console/api/apps?page=1&limit=20')[0])
    app_id = json.loads((ROOT / 'app.json').read_text())['app_id']
    assert any(app['id'] == app_id for app in apps['data']), 'Published research workflow not visible'
    results = {'console_url': BASE + '/apps', 'https_verified': True, 'setup_finished': True,
               'frontend_base_path': '/dify', 'static_assets_checked': len(paths[:6]),
               'console_login_succeeded': True, 'secure_host_cookies': True,
               'published_workflow_visible': True, 'app_id': app_id}
    (ROOT / 'domain-verification.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
