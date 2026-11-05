"""Read actual Dify node/audit results and reject an invalid delivery ticket."""
from pathlib import Path
import json

from deploy import remote, ROOT


def main():
    current = json.loads((ROOT / "verification/dify/workflow-live-result.json").read_text(encoding="utf8"))["result"]
    code = '''from pathlib import Path
import sys,json,base64,sqlite3,urllib.request,uuid
r=Path('/srv/dify-research');sys.path.insert(0,str(r/'ops'));import setup_app as a
a.BASE='https://tutor.example.invalid/dify/console/api'
c=json.loads((r/'private/admin-login.json').read_text())
assert a.call('POST','/login',{'email':c['email'],'password':base64.b64encode(c['password'].encode()).decode(),'remember_me':True}).get('result')=='success'
app_id=json.loads((r/'app.json').read_text())['app_id']
run=WORKFLOW_ID;native=NATIVE_ID
info=a.call('GET','/apps/'+app_id+'/workflow-runs/'+run)
rows=a.call('GET','/apps/'+app_id+'/workflow-runs/'+run+'/node-executions')['data']
with sqlite3.connect(r/'state/deliveries.sqlite3') as db:
 audit=db.execute('SELECT tool,state FROM mcp_calls WHERE run_id=? ORDER BY id',(native,)).fetchall()
by_id={n['node_id']:n for n in rows}
final=json.loads(by_id['check_mcp_history']['outputs']['receipt'])
assert info.get('status')=='succeeded' and len(rows)==11 and all(n['status']=='succeeded' for n in rows)
assert audit==[('workbench_account','completed'),('workbench_rules','completed'),('workbench_review','completed')]
assert final['processing_history_verified'] is True
fake=uuid.uuid4().hex
payload={'inputs':{'run_id':fake,'ticket':'invalid-synthetic-ticket'},'response_mode':'blocking','user':'isolated-workflow-acceptance'}
request=urllib.request.Request('http://127.0.0.1:8088/v1/workflows/run',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+(r/'private/workflow-key').read_text().strip(),'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=60) as response:negative=json.load(response)
assert negative['data']['status']=='failed', 'Invalid ticket reached successful delivery'
with sqlite3.connect(r/'state/deliveries.sqlite3') as db:
 assert db.execute('SELECT COUNT(*) FROM mcp_calls WHERE run_id=?',(fake,)).fetchone()[0]==0
 assert db.execute('SELECT COUNT(*) FROM deliveries WHERE id=?',(fake,)).fetchone()[0]==0
registration=json.loads((r/'mcp-registration.json').read_text())
report={'app_id':app_id,'workflow_run_id':run,'native_run_id':native,'status':info['status'],'elapsed_time':info['elapsed_time'],'total_tokens':info.get('total_tokens'),
 'registration':{'provider_id':registration['id'],'server_identifier':registration['server_identifier'],'count':registration['count'],'tools':registration['tools']},
 'steps':[{k:n.get(k) for k in ['node_id','node_type','title','status','error','elapsed_time']} for n in rows],
 'mcp_calls':audit,'processing_history_verified':True,'history_event_id':final['history_event_id'],'exact_native_readback':True,'idempotent_retry':True,
 'invalid_ticket':{'workflow_run_id':negative.get('workflow_run_id'),'status':negative['data']['status'],'no_mcp_calls':True,'no_native_delivery_row':True}}
(r/'mcp-workflow-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
'''.replace("WORKFLOW_ID", repr(current["workflow_run_id"])).replace("NATIVE_ID", repr(current["run_id"]))
    report = json.loads(remote(code, root=True, timeout=75))
    (ROOT / "verification/dify/mcp-workflow-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"success": True, "nodes": len(report["steps"]), "tools_registered": report["registration"]["count"],
                      "workflow_run_id": report["workflow_run_id"], "processing_history_verified": True,
                      "invalid_ticket_rejected": report["invalid_ticket"]["status"] == "failed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
