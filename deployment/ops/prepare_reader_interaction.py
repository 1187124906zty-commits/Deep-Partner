"""Prepare one bounded, real PDF translation for browser/native acceptance."""
import json,time
import httpx
from workspace_interactions_fixture import login,CACHE,STATE,ROOT,ORIGIN

def main():
    state=json.loads(STATE.read_text(encoding='utf8'));project=state['project'];prefix='/research/api/projects/'+project['id'];report={'document_fixture':'reader-synchronized-fixture.pdf','test_source':'Synthetic software interaction fixture','translation_target':'zh-CN','new_document_translation_requests':0}
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},trust_env=False,timeout=150) as client:
        login(client)
        rows=client.get(prefix+'/literature/items').json()['files']
        file=next((row for row in rows if row.get('metadata',{}).get('title')=='Reader synchronized reading verification'),None)
        if file is None:
            path=CACHE/'reader-synchronized-fixture.pdf'
            response=client.post(prefix+'/attachments',files={'files':(path.name,path.read_bytes(),'application/pdf')});response.raise_for_status()
            rows=client.get(prefix+'/literature/items').json()['files'];file=next(row for row in rows if row.get('metadata',{}).get('title')=='Reader synchronized reading verification')
        response=client.post(prefix+'/reader',json={'area':'literature','library':file['library'],'asset':file['name'],'title':file['metadata']['title'],'width':1540,'theme':'light'});response.raise_for_status();reader=response.json();report['reader']=reader
        route='/research/reader/'+project['id']+'/api/documents/'+reader['document_id'];deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            response=client.get(route+'/blocks');blocks=response.json() if response.is_success else []
            if blocks:break
            time.sleep(1)
        else:raise RuntimeError('PDF parser did not return blocks')
        response=client.put(route+'/translation-options',json={'targetLanguage':'zh-CN'});response.raise_for_status()
        translations=client.get(route+'/translations').json()
        if not translations or any(row.get('status')!='complete' for row in translations):
            response=client.post(route+'/assistance',json={'action':'start'});response.raise_for_status();response=client.post(route+'/translations',json={'blockId':''});response.raise_for_status();report['new_document_translation_requests']=1
            print('Real PDF translation requested for '+str(len(blocks))+' parsed blocks',flush=True)
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                translations=client.get(route+'/translations').json()
                if translations and all(row.get('status')=='complete' for row in translations):break
                time.sleep(1.5)
            else:raise RuntimeError('Real translation did not complete within the bounded check')
        report.update(completed_translation_blocks=len(translations),source_blocks=len(blocks),translated_text='\n'.join(sentence.get('target','') for row in translations for sentence in row.get('sentences',[])),passed=True)
        assert '扩散' in report['translated_text']
    (ROOT/'reports/workspace-interactions-real-translation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k not in ('reader','translated_text')},ensure_ascii=False))

if __name__=='__main__':main()
