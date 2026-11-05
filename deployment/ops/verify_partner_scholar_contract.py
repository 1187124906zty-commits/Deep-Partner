"""Real Scholar MCP tools and cursor propagation through project workflows."""
from pathlib import Path
import json, subprocess, sys
from verify_partner_workflow import ROOT, STAGE, client, task

PROJECT = 'c37b9168a0db40e3b258c9c03cd56697'
DP = Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')


def main():
    cases = [
        {'search_tool': 'search_papers_by_topic', 'query': 'phase field reactive transport dissolution',
         'min_year': 2020, 'max_year': 2026},
        {'search_tool': 'get_author_papers', 'author': 'Haim Waisman',
         'min_year': 2018, 'max_year': 2026}
    ]
    report = {'project_id': PROJECT, 'calls': [], 'backend_contract_tests': 19}
    report_path = ROOT / 'reports/partner-scholar-contract-live.json'
    with client() as connection:
        for index in range(3):
            if index == 2:
                cursor = report['calls'][0]['result'].get('next_cursor')
                assert cursor is not None, 'Real topic response returned no next_cursor'
                payload = {**cases[0], 'cursor': cursor}
            else:
                payload = cases[index]
            payload = {'kind': 'search', 'limit': 2, 'allow_search_fallback': False,
                       'request_id': 'scholar-contract-authorized-' + str(index), **payload}
            path = STAGE / ('scholar-authorized-' + str(index) + '.json')
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf8')
            result = subprocess.run([str(DP), 'workflow', 'run', '--project', PROJECT, '--file', str(path)],
                                    capture_output=True, encoding='utf8', timeout=90)
            if result.returncode:
                raise RuntimeError(result.stderr[-1200:] + result.stdout[-1200:])
            started = json.loads(result.stdout)
            row = task(connection, PROJECT, started['id'], maximum=180)
            evidence = {'request': payload, **{k: row[k] for k in ('id', 'status', 'result', 'error')}}
            report['calls'].append(evidence)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            assert row['status'] == 'completed', row.get('error') or row['result']
            searches = row['result']['searches']
            assert len(searches) == 1 and searches[0]['provider'] == 'scholar_mcp'
            assert searches[0]['tool'] == payload['search_tool']
            assert row['result']['sources'], 'No actual records returned'
    report['actual_tools_and_pagination_passed'] = True
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'passed': True, 'calls': [{'id': row['id'], 'tool': row['request']['search_tool'],
        'count': len(row['result']['sources']), 'cursor_in': row['request'].get('cursor'),
        'cursor_out': row['result'].get('next_cursor')} for row in report['calls']]}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
