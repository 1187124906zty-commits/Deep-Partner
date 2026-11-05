"""Admin-only operational quota changes via the actual API, with optimistic revisions."""
import argparse
import json
from pathlib import Path
import urllib.request

import verify_intensive as v


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--owner',required=True)
    parser.add_argument('--quota-gib',type=float)
    parser.add_argument('--cache-mib',type=float,default=512)
    parser.add_argument('--archive-gib',type=float,default=0)
    parser.add_argument('--expected-revision',type=int)
    parser.add_argument('--reason',default='')
    args=parser.parse_args()
    account=json.loads(Path('/srv/deeptutor/migration/admin-login.json').read_text())
    request=urllib.request.Request('http://127.0.0.1:8008/api/auth/login',method='POST',
        headers={'Content-Type':'application/json'},data=json.dumps(account).encode())
    v.login.open(request,timeout=20).close();v.cookie='; '.join(c.name+'='+c.value for c in v.jar)
    route='/research/api/admin/storage/'+args.owner
    current=v.call('GET',route)
    if args.quota_gib is None:
        print(json.dumps(current,ensure_ascii=False,indent=2));return
    if args.expected_revision is None or len(args.reason.strip())<5:
        raise SystemExit('Changing quota requires --expected-revision and a concrete --reason')
    value=v.call('PUT',route,{'expected_revision':args.expected_revision,
        'quota_bytes':int(args.quota_gib*1024**3),'cache_limit_bytes':int(args.cache_mib*1024**2),
        'archive_quota_bytes':int(args.archive_gib*1024**3),'reason':args.reason})
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
