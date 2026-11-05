"""Confirm the native Dify ID in the recorded prepare HTTP request, without leaking tickets."""
import json
import sqlite3

from optimize_workflow import ROOT,api,login


def main():
    login();app=json.loads((ROOT/'app.json').read_text())
    recovery=json.loads((ROOT/'reports/recovery-live.json').read_text())
    with sqlite3.connect(ROOT/'state/deliveries.sqlite3') as db:
        identifier=db.execute('SELECT workflow_run_id FROM deliveries WHERE id=?',(recovery['run_id'],)).fetchone()[0]
    trace=api.call('GET','/apps/'+app['app_id']+'/workflow-runs/'+identifier+'/node-executions')
    current=next(n for n in trace['data'] if n.get('node_id')=='prepare')
    fields={field:json.dumps(current.get(field),ensure_ascii=False) for field in ('inputs','process_data','outputs')}
    matches=[field for field,text in fields.items() if identifier in text and 'x-dify-workflow-run-id' in text.lower()]
    result={'workflow_run_id':identifier,'prepare_status':current.get('status'),
        'native_id_header_verified':bool(matches),'matching_trace_fields':matches,
        'trace_field_shapes':{field:list(current[field]) if isinstance(current.get(field),dict) else type(current.get(field)).__name__ for field in fields}}
    (ROOT/'reports/workflow-identity-live.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
    assert matches,'Prepare trace did not preserve a resolved native workflow ID header'


if __name__=='__main__':main()
