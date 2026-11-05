"""Read-only reproduction: topic folders must appear in the actual project library."""
from pathlib import Path
import argparse,json,os,sys
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ops'))
from workspace_interactions_fixture import login,ORIGIN
PID='1ea03384007d4bb9b88d43e3368099f3'
EXPECTED=['氯硫耦合机理与反应传输','多离子化学、吸附与水力传输','侵蚀损伤、开裂与钢筋腐蚀','PINN与物理约束学习','算子学习、多保真与代理建模','贝叶斯反演、不确定性与主动学习','试验规范与数值方法']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='current');args=parser.parse_args()
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy=os.environ.get('WORKBENCH_HTTP_PROXY','http://127.0.0.1:12000'),timeout=60,trust_env=False) as client:
        login(client)
        response=client.get('/research/api/projects/'+PID+'/literature/folders');response.raise_for_status();folders=response.json()
        response=client.get('/research/api/projects/'+PID+'/literature/items');response.raise_for_status();items=response.json()
    names=[f['name'] for f in folders.get('folders',[])]
    missing=[name for name in EXPECTED if not any(name in label for label in names)]
    report={'project_id':PID,'library_files':len(items['files']),'actual_folder_count':len(names),'folder_names':names,'missing_topics':missing,'memberships':len(folders.get('memberships',{})),'checks':{'all_seven_topics_in_library':not missing,'actual_documents_assigned':bool(folders.get('memberships'))}}
    report['passed']=all(report['checks'].values())
    (ROOT/'reports'/('library-writeback-'+args.label+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
