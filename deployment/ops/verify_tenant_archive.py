"""Real SSH archive acceptance, using isolated test owners and no live user data."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

PYTHON='/public/software/apps/anaconda3/2023.09/bin/python'
RECEIVER='/work/home/cluster_user/.cache/pi-research/tenant-storage-receiver.py'


def request(header,data=b'',ok=True):
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','research-cluster-xh5',PYTHON,RECEIVER],
        input=json.dumps(header,ensure_ascii=False).encode()+b'\n'+data,capture_output=True,timeout=45)
    value=json.loads(result.stdout.decode('utf-8').splitlines()[-1])
    assert value['ok']==ok,{'code':result.returncode,'result':value}
    return value


def main():
    marker=uuid.uuid4().hex[:10];alice='storage-proof-a-'+marker;bob='storage-proof-b-'+marker
    project=uuid.uuid4().hex;data='隔离的租户归档测试：原文、程序与版本都要可回查。\n'.encode()
    digest=hashlib.sha256(data).hexdigest();checks={}
    for owner in (alice,bob):request({'action':'configure','owner_id':owner,'expected_revision':0,'quota_bytes':len(data)+8})
    header={'action':'put','owner_id':alice,'project_id':project,'logical_path':'project/docs/测试说明.md','sha256':digest,'bytes':len(data)}
    saved=request(header,data)['result'];again=request(header,data)['result']
    checks['binary_transfer_and_repeat']=saved['sha256']==digest and again['deduplicated']
    verify=request({**header,'action':'verify'})['result'];checks['remote_readback_verified']=verify['verified']
    checks['other_owner_cannot_read_same_object']=not request({**header,'action':'verify','owner_id':bob},ok=False)['ok']
    checks['path_traversal_rejected']=not request({**header,'logical_path':'../other-user.txt'},data,ok=False)['ok']
    mismatch=request({**header,'owner_id':bob,'sha256':'0'*64},data,ok=False)
    checks['digest_mismatch_rejected']='digest mismatch' in mismatch['error']
    truncated=request({**header,'owner_id':bob,'project_id':uuid.uuid4().hex},data[:-1],ok=False)
    checks['truncated_transfer_rejected']='ended before' in truncated['error']
    too_big=data+b'123456789';checks['quota_rejected']=not request({**header,'sha256':hashlib.sha256(too_big).hexdigest(),'bytes':len(too_big)},too_big,ok=False)['ok']
    checks['stale_quota_update_rejected']=not request({'action':'configure','owner_id':alice,'expected_revision':0,'quota_bytes':1000},ok=False)['ok']
    status=request({'action':'status','owner_id':alice})['result'];checks['failed_transfers_not_counted']=status['used_bytes']==len(data)
    request({'action':'configure','owner_id':alice,'expected_revision':1,'quota_bytes':0})
    checks['quota_reduction_keeps_data']=request({**header,'action':'verify'})['result']['verified']
    report={'verified':all(checks.values()),'checks':checks,'receipt':saved,'test_owners':[alice,bob],
        'scope':'SSH-only immutable archive proof; no native KB, account database, memory or live workspace was migrated; no local files were deleted.',
        'backend':'ParaStor shared filesystem; no database daemon was started'}
    path=Path(__file__).resolve().parents[1]/'reports/tenant-archive-live.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
