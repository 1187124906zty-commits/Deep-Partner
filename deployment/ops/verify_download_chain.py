"""Verify the user's actual selected paper reaches a readable owned PDF."""
from pathlib import Path
import json,subprocess
import httpx
ROOT=Path(__file__).resolve().parents[1]
PID='638495c5ba024a93a305ff69b4658811'
JID='82dcdef5fe5e4cf6bed78ba84f5e0b84'

def main():
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    with httpx.Client(base_url='https://tutor.example.invalid',headers={'Origin':'https://tutor.example.invalid'},timeout=40) as client:
        client.post('/api/auth/login',json=account).raise_for_status()
        worker=client.get('/research/api/download-worker/status');worker.raise_for_status()
        rows=client.get('/research/api/projects/'+PID+'/jobs');rows.raise_for_status()
        job=next(j for j in rows.json()['jobs'] if j['id']==JID)
        result=job.get('result',{});entry=result.get('entry',{})
        report={'project_id':PID,'job_id':JID,'status':job['status'],'stage':job['stage'],'error':job['error'],'worker':worker.json(),'identifier':result.get('identifier'),'title':entry.get('title'),'timeline':result.get('timeline',[]),'receipt':result.get('receipt'),'transfer':result.get('transfer'),'passed':False}
        if job['status']=='completed':
            name=result.get('receipt',{}).get('name');assert name,'Completed task must name its owned attachment'
            pdf=client.get('/research/api/projects/'+PID+'/literature/file',params={'asset':name});pdf.raise_for_status()
            import fitz
            with fitz.open(stream=pdf.content,filetype='pdf') as doc:
                assert len(doc)>0;report['pdf']={'bytes':len(pdf.content),'pages':len(doc),'first_page':doc[0].get_text()[:800]}
            assert result.get('transfer',{}).get('cluster_verified'),'The cluster copy must have a verification receipt'
            report['passed']=True
        (ROOT/'reports/download-chain-current.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False))
        assert report['passed'],'Selected paper has not completed its download-to-library chain'

if __name__=='__main__':main()
