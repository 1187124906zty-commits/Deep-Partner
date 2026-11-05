"""Build honest, relative-path source and pending-parser inventories."""
from __future__ import annotations

from datetime import datetime,timezone
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEPLOYMENT=ROOT.parents[1]
REMOTE_HOST_ROOT='/srv/deeptutor/data/user/mineru-knowledge-ingest-20261102/inputs/presentation-sources'
REMOTE_CONTAINER_ROOT='/app/data/user/mineru-knowledge-ingest-20261102/inputs/presentation-sources'


def main():
    fetch=json.loads((ROOT/'fetch-manifest.json').read_text(encoding='utf8'))
    notes=json.loads((ROOT.parent/'ppt-purpose-source-notes.json').read_text(encoding='utf8'))
    details={s['id']:s for s in notes['sources']}
    rows=[];queue=[]
    for retrieved in fetch['sources']:
        sid=retrieved['source_id'];source=details[sid]
        row={'source_id':sid,'title':source['title'],'publisher':source['publisher'],
             'canonical_url':source['url'],'canonical_access_status':retrieved['status'],
             'fetch_metadata':sid+'/fetch.json','retrieved_at':retrieved.get('downloaded_at'),
             'original_path':retrieved.get('original_path'),'native_markdown_path':None,
             'native_extraction_method':None,'scope':None,'locator_map':None,
             'mineru':{'state':'not_eligible_no_original' if retrieved['status']!='downloaded' else 'queued_not_processed',
                       'processed':False},
             'source_rule_bindings':source['locators'],'prior_research_access_note':source['access_scope'],
             'synthesized_rules_in_source_copy':False,'public_deployment_allowed':False}
        if retrieved['status']=='downloaded':
            if retrieved['original_format']=='html':
                native=json.loads((ROOT/sid/'heading-map.json').read_text(encoding='utf8'))
                parser_input=native['parse_input_path'];model='MinerU-HTML'
                row.update(native_markdown_path=native['native_markdown_path'],native_extraction_method='native_html',
                           scope=native['scope'],locator_map=sid+'/heading-map.json')
            else:
                native=json.loads((ROOT/sid/'native.source.json').read_text(encoding='utf8'))
                parser_input=retrieved['original_path'];model='vlm'
                row.update(native_markdown_path=native['native_markdown_path'],native_extraction_method='native_pdf_text',
                           scope='All two physical PDF pages; source text layer only.',locator_map=sid+'/native.source.json')
            queue.append({'source_id':sid,'input_path':parser_input,'original_path':retrieved['original_path'],
                          'source_url':source['url'],'model_version':model,
                          'derivation':'scoped original-HTML subtree' if model=='MinerU-HTML' else 'original PDF bytes',
                          'local_source_root':str(ROOT),'public_deployment_allowed':False})
        rows.append(row)
    alt_path=ROOT/'S05/alternatives/official-era-overview.heading-map.json'
    alternative=json.loads(alt_path.read_text(encoding='utf8'))
    alternatives=[{'source_id':'S05-ALT','parent_source_id':'S05',
                   'canonical_source_still_unavailable':True,'relationship':'official_alternative_not_original_page',
                   'source_url':alternative['source_url'],'original_path':alternative['original_path'],
                   'native_markdown_path':alternative['native_markdown_path'],
                   'native_extraction_method':'native_html','locator_map':'S05/alternatives/official-era-overview.heading-map.json',
                   'supports':alternative['supports'],'not_supported':alternative['not_supported'],
                   'mineru':{'state':'queued_not_processed','processed':False},'public_deployment_allowed':False}]
    queue.append({'source_id':'S05-ALT','input_path':alternative['parse_input_path'],'original_path':alternative['original_path'],
                  'source_url':alternative['source_url'],'model_version':'MinerU-HTML',
                  'derivation':'scoped original-HTML subtree; distinct official alternative',
                  'local_source_root':str(ROOT),'public_deployment_allowed':False})
    now=datetime.now(timezone.utc).isoformat()
    queued={'schema_version':1,'created_at':now,'state':'queued_not_submitted_by_this_agent',
            'local_source_root':str(ROOT),'path_semantics':'input_path and original_path are relative to source_root; preserve this directory structure when uploading.',
            'remote_host_root':REMOTE_HOST_ROOT,'remote_container_root':REMOTE_CONTAINER_ROOT,
            'dispatch':'Coordinate after the existing three-book serial MinerU batch; no concurrent cloud submission.',
            'credentials':'Reuse original container configuration; do not put keys or signed URLs in this manifest.',
            'items':queue}
    (ROOT/'mineru-queue.json').write_text(json.dumps(queued,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report={'schema_version':1,'created_at':now,'artifact_kind':'private_presentation_source_library_ingest',
            'local_source_root':str(ROOT),'path_semantics':'All artifact paths below are relative to local_source_root unless explicitly named otherwise.',
            'remote_host_root':REMOTE_HOST_ROOT,'remote_container_root':REMOTE_CONTAINER_ROOT,
            'summary':{'requested_original_sources':12,'originals_downloaded':10,'originals_not_retrieved':2,
                       'native_html_originals':9,'native_pdf_originals':1,'official_alternatives_downloaded':1,
                       'mineru_processed_originals':0,'mineru_processed_alternatives':0,'mineru_queued_items':11},
            'distribution':{'private_local_library_only':True,'public_deployment_allowed':False,
                            'note':'University materials retain original notices; do not place originals or full-text derivatives in public static assets or deployment tarballs.'},
            'interpretation':{'raw_sources':'Original response bytes and native source-text derivatives.',
                              'product_rules':'Separate artifacts: ../ppt-purpose-source-notes.json and repository templates/presentations/purpose-rules.json.',
                              'native_fallback':'native_html/native_pdf_text are not MinerU outputs.',
                              'missing':'Failed originals remain unavailable; the NIH eRA alternative is a distinct source with narrower bindings.'},
            'sources':rows,'alternatives':alternatives,'mineru_queue_manifest':'mineru-queue.json',
            'verification':{'original_pdf_identity':'S02 is the two-page official AGU20 file; first page rendered and visually inspected.',
                            'html_scope':'Native extraction uses article/explicit subsection selectors and heading maps; navigation removed.',
                            'source_text_synthesis_separated':True},
            'remaining_work':['Run queued items through the existing MinerU cloud after serial book processing; record actual output paths and parser status.']}
    (ROOT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (DEPLOYMENT/'reports/presentation-source-ingest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report['summary']))


if __name__=='__main__':main()
