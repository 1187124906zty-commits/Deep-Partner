"""Read-only live checks for authenticated capability/version discovery."""
from pathlib import Path
import json
import subprocess
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://tutor.example.invalid'


def main():
    endpoint = ORIGIN + '/research/api/desktop/manifest?frontend_version=0.4.0&protocol_version=2.0'
    try:
        urllib.request.urlopen(endpoint, timeout=15)
        raise AssertionError('Unauthenticated manifest was exposed')
    except urllib.error.HTTPError as error:
        assert error.code == 401
    account = json.loads(subprocess.run(['ssh', '-o', 'BatchMode=yes', 'papers-research',
        'sudo -n cat /srv/deeptutor/migration/admin-login.json'], capture_output=True,
        text=True, check=True).stdout)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    request = urllib.request.Request(ORIGIN + '/api/auth/login',
        data=json.dumps(account).encode(), headers={'Content-Type': 'application/json', 'Origin': ORIGIN})
    with opener.open(request, timeout=20) as response:
        assert response.status == 200
    with opener.open(endpoint, timeout=25) as response:
        manifest = json.load(response)
        etag = response.headers['ETag']
    assert manifest['compatibility']['compatible'] is True
    assert manifest['frontend']['update_policy'] == 'manual'
    assert manifest['capabilities']['status'] == 'available'
    try:
        opener.open(urllib.request.Request(endpoint, headers={'If-None-Match': etag}), timeout=25)
        raise AssertionError('Unchanged catalog did not honor ETag')
    except urllib.error.HTTPError as error:
        assert error.code == 304
    with opener.open(endpoint.replace('0.4.0', '0.3.0'), timeout=25) as response:
        old = json.load(response)
    assert old['compatibility']['upgrade_required'] is True and old['compatibility']['compatible'] is False
    report = {'unauthenticated_status': 401, 'compatible_current_client': True,
        'etag_unchanged_status': 304, 'old_client_upgrade_required': True,
        'frontend_policy': manifest['frontend']['update_policy'],
        'protocol': manifest['protocol'], 'standards': manifest['standards'],
        'native_capabilities': len(manifest['capabilities']['items']),
        'workflows': [{k: row[k] for k in ('id', 'name', 'availability', 'publication')}
                      for row in manifest['workflows']]}
    (ROOT / 'reports/desktop-manifest-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
