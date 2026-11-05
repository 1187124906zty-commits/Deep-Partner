"""Verify the compiled Tauri application's actual WebView2 via local CDP."""
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path('D:/Development/电脑答疑/deeptutor-desktop')
PROFILE = NATIVE / 'verification/native-0.4-profile'
sys.path.insert(0, str(ROOT / '.local/browser-qa'))
from playwright.sync_api import sync_playwright


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def main():
    executable = NATIVE / 'dist/Deep partner.exe'
    assert executable.is_file(), 'Packaged native executable missing'
    PROFILE.mkdir(exist_ok=True)
    config = {'server_url': 'https://tutor.example.invalid', 'workspace': str(PROFILE / 'workspace'),
              'bridge_port': free_port(), 'browser_port': free_port(), 'cpu_workers': 2,
              'theme': 'light'}
    (PROFILE / 'config.json').write_text(json.dumps(config), encoding='utf8')
    account = json.loads(subprocess.run(['ssh', '-o', 'BatchMode=yes', 'papers-research',
        'sudo -n cat /srv/deeptutor/migration/admin-login.json'], capture_output=True,
        text=True, check=True).stdout)
    output = ROOT / 'reports/screenshots'
    output.mkdir(exist_ok=True)
    report = {'runtime': 'actual-compiled-tauri-webview2', 'page_errors': [], 'screenshots': []}

    def launch(p):
        debug_port = free_port()
        env = dict(os.environ, DEEP_PARTNER_HOME=str(PROFILE),
            WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=' + str(debug_port))
        child = subprocess.Popen([str(executable)], cwd=NATIVE / 'dist', env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('Native shell exited before WebView was ready')
            try:
                with urllib.request.urlopen('http://127.0.0.1:' + str(debug_port) + '/json/version', timeout=1) as response:
                    version = json.load(response)
                break
            except OSError:
                time.sleep(.3)
        else:
            child.terminate()
            raise RuntimeError('WebView2 CDP did not become ready')
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:' + str(debug_port))
        context = browser.contexts[0]
        deadline = time.monotonic() + 20
        while not context.pages and time.monotonic() < deadline:
            time.sleep(.2)
        page = context.pages[0]
        page.on('pageerror', lambda error: report['page_errors'].append(str(error)[:1000]))
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(1500)
        origin = page.evaluate('location.origin')
        assert origin.startswith('http://127.0.0.1:'), 'Native frontend did not stay local'
        return child, browser, context, page, origin, version

    with sync_playwright() as p:
        child = None
        try:
            child, browser, context, page, origin, version = launch(p)
            report['webview_version'] = version.get('Browser')
            report['frontend_local'] = True
            assert page.get_by_role('heading', name='登录研究空间', exact=True).is_visible()
            login = context.request.post(origin + '/api/auth/login', headers={'Origin': origin},
                data={'username': account['username'], 'password': account['password']})
            assert login.ok, 'Actual native proxy login failed'
            assert all(cookie['name'] not in ('dt_token', '__Host-dt_trusted', '__Host-dt_pair')
                       for cookie in context.cookies()), 'Native credential leaked into WebView cookie storage'
            report['native_cookie_private'] = True
            status = context.request.get(origin + '/desktop/status', headers={'Origin': origin})
            assert status.ok
            native = status.json()
            report['engines'] = native.get('engines')
            report['persisted_jobs'] = len(native.get('jobs', []))
            projects = context.request.get(origin + '/research/api/projects', headers={'Origin': origin}).json()['projects']
            project = next(x for x in projects if 'Dify 部署' in x['name'])
            page.goto(origin + '/?project=' + project['id'] + '&dt_workspace=' + project['native_id'], wait_until='domcontentloaded')
            page.wait_for_timeout(2200)
            assert page.locator('.dp-shell').is_visible()
            report['no_horizontal_overflow'] = not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            shot = output / 'native-webview-research.png'
            page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
            page.get_by_role('button', name='本机任务', exact=True).click()
            page.wait_for_timeout(600)
            assert page.get_by_role('heading', name='本机任务', exact=True).is_visible()
            completed = next((job for job in native.get('jobs', []) if job.get('status') == 'completed'), None)
            if completed:
                page.get_by_label('本机任务记录', exact=True).select_option(completed['id'])
                page.locator('.dp-native-output').get_by_text('DEEP_PARTNER_CLI_OK', exact=False).first.wait_for(state='visible', timeout=15000)
                report['persisted_cli_response_rendered'] = True
                page.locator('.dp-native-output').scroll_into_view_if_needed()
            shot = output / 'native-webview-local-tasks.png'
            page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
            page.get_by_role('button', name='设置', exact=True).last.click()
            page.get_by_role('button', name='深色', exact=True).click()
            page.wait_for_timeout(500)
            preferences = context.request.get(origin + '/desktop/preferences', headers={'Origin': origin}).json()
            assert preferences.get('theme') == 'dark', preferences
            report['theme_saved_natively'] = True
            browser.close()
            child.terminate(); child.wait(timeout=10); child = None
            child, browser, context, page, origin, _ = launch(p)
            assert page.evaluate('document.documentElement.classList.contains("dark")'), 'Theme did not survive new loopback origin'
            report['theme_survived_native_restart'] = True
            shot = output / 'native-webview-restart-dark.png'
            page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
            browser.close()
        finally:
            if child is not None and child.poll() is None:
                child.terminate(); child.wait(timeout=10)
    report['passed'] = not report['page_errors'] and report['no_horizontal_overflow']
    (ROOT / 'reports/native-webview-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
