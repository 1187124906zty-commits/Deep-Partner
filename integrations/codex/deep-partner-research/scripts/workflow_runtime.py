"""On-demand restoration of the concrete tool routes used by dp and MCP."""
import argparse,json
from runtime_supervisor import ensure,recover_all

def restore(kind):
    return {'supervisor':ensure(),**recover_all(kind)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',default='survey');a=p.parse_args()
    print(json.dumps(restore(a.kind),ensure_ascii=False))
