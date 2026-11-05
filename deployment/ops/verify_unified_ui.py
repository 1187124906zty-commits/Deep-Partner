"""Exercise the actual shared UI against its authenticated production APIs.

Before publication, only static UI requests are fulfilled from the local Slurm
artifact. API/WebSocket traffic uses the existing domain and native runtime.
"""
from pathlib import Path
from urllib.parse import urlparse, unquote
import argparse
import json
import mimetypes
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.local/browser-qa'))
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = Path('D:/Development/research-workbench/unified-ui/dist')
ORIGIN = 'https://tutor.example.invalid'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--published', action='store_true')
    parser.add_argument('--project-id')
    parser.add_argument('--stream', action='store_true')
    parser.add_argument('--feedback', action='store_true')
    parser.add_argument('--resume-session')
    args = parser.parse_args()
    account = json.loads(subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', 'papers-research',
         'sudo -n cat /srv/deeptutor/migration/admin-login.json'],
        capture_output=True, text=True, check=True).stdout)
    output = ROOT / 'reports/screenshots'
    output.mkdir(exist_ok=True)
    report = {'mode': 'published' if args.published else 'local-artifact-real-backend',
              'new_model_turn': False, 'page_errors': [], 'failed_resources': [],
              'screenshots': [], 'checks': {}}
    if (DIST / 'build-info.json').is_file():
        report['frontend_job_id'] = json.loads((DIST / 'build-info.json').read_text())['slurm_job_id']
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
                                    headless=True)
        context = browser.new_context(viewport={'width': 1540, 'height': 1000})
        login = context.request.post(ORIGIN + '/api/auth/login',
            data={'username': account['username'], 'password': account['password']},
            headers={'Origin': ORIGIN})
        assert login.ok, 'Native login failed'
        response = context.request.get(ORIGIN + '/research/api/projects')
        assert response.ok, 'Project list failed'
        projects = response.json()['projects']
        project = (next(x for x in projects if x['id'] == args.project_id) if args.project_id else
                   next((x for x in projects if 'Dify 部署' in x['name']),
                        next((x for x in projects if '验收' in x['name']), projects[0])))
        report['project_id'] = project['id']
        if not args.published:
            def static(route):
                relative = unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not relative:
                    target = DIST / 'index.html'
                elif relative.startswith(('assets/', 'fonts/')):
                    target = (DIST / relative).resolve()
                    if not target.is_relative_to(DIST.resolve()):
                        route.abort()
                        return
                else:
                    route.continue_()
                    return
                if target.is_file():
                    route.fulfill(status=200, body=target.read_bytes(),
                        content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:
                    route.fulfill(status=404, body='missing static asset')
            context.route(ORIGIN + '/research/**', static)
        page = context.new_page()
        frames = []
        def socket_opened(socket):
            def received(raw):
                try:
                    event = json.loads(raw)
                    frames.append(event)
                except (ValueError, TypeError):
                    pass
            socket.on('framereceived', received)
        page.on('websocket', socket_opened)
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)[:1000]))
        page.on('response', lambda r: report['failed_resources'].append(
            {'url': r.url.split('?')[0], 'status': r.status}) if r.status >= 400 else None)
        page.goto(ORIGIN + '/research/?project=' + project['id'] + '&dt_workspace=' + project['native_id']
                  + ('&session=' + args.resume_session if args.resume_session else ''),
                  wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(3500)
        report['body'] = page.locator('body').inner_text()[:12000]
        report['checks']['desktop_overflow'] = page.evaluate('document.documentElement.scrollWidth > innerWidth')
        report['checks']['fonts'] = page.evaluate('''async () => {
          await document.fonts.ready;
          return {body: getComputedStyle(document.body).fontFamily,
            loaded: Array.from(document.fonts).filter(f => /Geist|Lora/.test(f.family)).map(f => ({family:f.family,status:f.status}))};
        }''')
        shot = output / ('unified-published-desktop.png' if args.published else 'unified-candidate-desktop.png')
        page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(500)
        report['checks']['mobile_overflow'] = page.evaluate('document.documentElement.scrollWidth > innerWidth')
        shot = output / ('unified-published-mobile.png' if args.published else 'unified-candidate-mobile.png')
        page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
        page.set_viewport_size({'width': 1540, 'height': 1000})
        page.get_by_role('navigation', name='工作视图').get_by_role('button', name='成果', exact=True).click()
        panel_results = {}
        for label in ['文献', '程序', '论文', 'PPT', '修改记录']:
            page.get_by_role('navigation', name='研究成果').get_by_role('button', name=label, exact=True).click()
            page.wait_for_timeout(900)
            panel_results[label] = {'visible': page.locator('.dp-artifacts').is_visible(),
                                    'overflow': page.evaluate('document.documentElement.scrollWidth > innerWidth')}
            if label == '论文':
                shot = output / ('unified-published-paper.png' if args.published else 'unified-candidate-paper.png')
                page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
        report['checks']['artifact_panels'] = panel_results
        page.get_by_role('navigation', name='工作视图').get_by_role('button', name='对话', exact=True).click()
        if args.stream or args.resume_session:
            if not args.resume_session:
                prompt = '本次仅验证软件会话链路。不要读取文件、调用工具或创建产物。只回复 DEEP_PARTNER_STREAM_OK。'
                editor = page.locator('.dp-chat-pane textarea:visible').first
                editor.fill(prompt)
                editor.press('Enter')
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    if any(e.get('type') == 'done' for e in frames):
                        break
                    page.wait_for_timeout(600)
                else:
                    raise RuntimeError('Native streaming turn did not complete within the bounded window')
            session_id = page.evaluate('new URL(location.href).searchParams.get("session")')
            assert session_id, 'The actual native session was not retained in the shared host route'
            saved = context.request.get(ORIGIN + '/api/sessions/' + session_id + '?dt_workspace=' + project['native_id'])
            assert saved.ok, 'Native persisted session read failed'
            messages = saved.json().get('messages', [])
            assistants = [m for m in messages if m.get('role') == 'assistant']
            stream_assistant = next((m for m in assistants if 'DEEP_PARTNER_STREAM_OK' in str(m.get('content', ''))), None)
            assert stream_assistant, 'Provider response missing from persisted assistant message'
            report['new_model_turn'] = not bool(args.resume_session)
            event_source = 'websocket'
            if args.resume_session:
                trace = context.request.get(ORIGIN + '/api/sessions/' + session_id + '/messages/'
                    + str(stream_assistant['id']) + '/events?after_seq=0&limit=500&dt_workspace=' + project['native_id'])
                assert trace.ok
                frames = trace.json().get('events', [])
                event_source = 'persisted_native_trace_from_prior_actual_ui_turn'
            report['stream'] = {'session_id': session_id, 'turn_ids': sorted({e['turn_id'] for e in frames if e.get('turn_id')}),
                'event_source': event_source,
                'event_types': sorted({e.get('type', '') for e in frames}),
                'content_event_count': sum(e.get('type') == 'content' for e in frames),
                'persisted_marker': True}
            page.reload(wait_until='domcontentloaded')
            page.wait_for_timeout(1500)
            assert page.evaluate('new URL(location.href).searchParams.get("session")') == session_id
            try:
                page.locator('.dp-chat-pane').get_by_text('DEEP_PARTNER_STREAM_OK', exact=False).first.wait_for(state='visible', timeout=30000)
            except Exception:
                (ROOT / 'reports/unified-ui-failure-body.txt').write_text(page.locator('body').inner_text(), encoding='utf8')
                page.screenshot(path=str(output / 'unified-ui-last-failure.png'))
                raise
            report['stream']['reload_recovered'] = True
            (ROOT / 'reports/unified-stream-live.json').write_text(json.dumps(report['stream'], ensure_ascii=False, indent=2), encoding='utf8')
            if args.resume_session and not args.feedback:
                previous_feedback = ROOT / 'reports/unified-feedback-live.json'
                if previous_feedback.is_file():
                    recovered_feedback = json.loads(previous_feedback.read_text(encoding='utf8'))
                    if recovered_feedback.get('session_id') == session_id:
                        report['feedback'] = recovered_feedback
                        report['feedback_recovered_from_prior_actual_ui_turn'] = True
                page.get_by_role('navigation', name='工作视图').get_by_role('button', name='并排', exact=True).click()
                feedback_body = page.locator('[data-workbench-feedback="annotations"]').first
                feedback_body.wait_for(state='attached', timeout=15000)
                assert 'DEEP_PARTNER_FEEDBACK_OK' in feedback_body.locator('.dp-feedback-request').inner_text()
                assert feedback_body.locator('details').evaluate('element => !element.open')
                bounds = page.locator('.dp-chat-pane').evaluate('''pane => {
                  const p=pane.getBoundingClientRect();
                  const bubbles=Array.from(pane.querySelectorAll('[data-turn-bubble]')).map(e=>e.getBoundingClientRect());
                  return {pane_scroll_overflow:pane.scrollWidth>pane.clientWidth+1,
                    bubbles_within_pane:bubbles.every(b=>b.left>=p.left-1&&b.right<=p.right+1)};
                }''')
                assert bounds['bubbles_within_pane'] and not bounds['pane_scroll_overflow'], bounds
                feedback_body.locator('summary').click()
                assert '# 工作台输出标准' in feedback_body.locator('pre').inner_text()
                feedback_body.locator('summary').click()
                report['feedback_context_display'] = {**bounds, 'request_preserved': True,
                    'full_context_expandable': True, 'context_default_collapsed': True}
                page.get_by_role('navigation', name='研究成果').get_by_role('button', name='论文', exact=True).click()
                page.wait_for_timeout(400)
                shot = output / 'unified-feedback-same-session.png'
                page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
            if args.feedback:
                page.get_by_role('navigation', name='工作视图').get_by_role('button', name='成果', exact=True).click()
                page.get_by_role('navigation', name='研究成果').get_by_role('button', name='论文', exact=True).click()
                page.get_by_role('button', name='问 Agent', exact=True).click()
                page.get_by_label('发送到项目会话的问题', exact=True).fill('这是软件反馈联调，禁止读取或修改文件，不调用工具。请只回复 DEEP_PARTNER_FEEDBACK_OK。')
                with page.expect_response(lambda r: '/annotations/submit' in r.url and r.request.method == 'POST', timeout=60000) as submitted:
                    page.get_by_role('button', name='发送到当前会话', exact=True).click()
                receipt = submitted.value.json()
                assert submitted.value.ok and receipt.get('session_id') == session_id and receipt.get('turn_id'), receipt
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    saved = context.request.get(ORIGIN + '/api/sessions/' + session_id + '?dt_workspace=' + project['native_id'])
                    assistants = [m for m in saved.json().get('messages', []) if m.get('role') == 'assistant']
                    if assistants and 'DEEP_PARTNER_FEEDBACK_OK' in str(assistants[-1].get('content', '')):
                        break
                    page.wait_for_timeout(1200)
                else:
                    raise RuntimeError('Feedback native turn did not finish in the same session')
                page.wait_for_timeout(800)
                report['feedback'] = {'annotation_ids': submitted.value.request.post_data_json['ids'], **receipt,
                    'same_session': True, 'persisted_response_marker': True,
                    'host_session_id': page.evaluate('new URL(location.href).searchParams.get("session")')}
                assert report['feedback']['host_session_id'] == session_id
                (ROOT / 'reports/unified-feedback-live.json').write_text(json.dumps(report['feedback'], ensure_ascii=False, indent=2), encoding='utf8')
                shot = output / 'unified-feedback-same-session.png'
                page.screenshot(path=str(shot)); report['screenshots'].append(str(shot))
        browser.close()
    report['passed'] = (not report['page_errors'] and not report['checks']['desktop_overflow']
                         and not report['checks']['mobile_overflow'])
    target = ROOT / 'reports' / ('unified-ui-published.json' if args.published else 'unified-ui-candidate.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        (ROOT / 'reports/unified-ui-last-error.txt').write_text(type(error).__name__ + ': ' + str(error), encoding='utf8')
        raise
