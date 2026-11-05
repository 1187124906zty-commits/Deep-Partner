"""Bounded source checks; preserve raw cloud output and select a reading layer."""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import unicodedata

from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
PROBES={
    'S01':['feedback from your colleagues','explicitly tell your audience','main takeaway'],
    'S02':['leave the details for publication','28-pt font','16:9 horizontal','Upload your finished presentation'],
    'S03':['methods you used','results that went wrong','Show procedures'],
    'S06':['feasibility and merit','Include a timeline','Initial experiments'],
    'S07':['planned contributions','constructive interactions','you may or may not have gotten results'],
    'S08':['specific approach','background','results','conclusion'],
    'S09':['Many theses','discrete chapters','limitations of your work'],
    'S10':['not obliged to present every figure','central claim','moderate the discussion'],
    'S11':['Is the study design appropriate','Are the results valid','Effect sizes and confidence intervals','Confounding'],
    'S12':['independent research','creditable standard','results coherently'],
    'S05-ALT':['scientific progress','significant changes','Final RPPR','Interim RPPR'],
}


def norm(value):
    return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKC',value).casefold()).strip()


def main():
    manifest=json.loads((ROOT.parents[1]/'reports/mineru-purpose-results.json').read_text(encoding='utf8'))
    rows=[]
    for entry in manifest['sources']:
        sid=entry['source_id'];path=Path(entry['actual_local_markdown']);body=path.read_text(encoding='utf8')
        input_path=Path(entry['local_input_path']);job=Path(entry['local_job_path'])
        identity=hashlib.sha256(input_path.read_bytes()).hexdigest()==entry['summary']['source_sha256']
        html_source=entry['model_version']=='MinerU-HTML'
        original=norm(BeautifulSoup(input_path.read_bytes(),'html.parser').get_text(' ',strip=True)) if html_source else norm((ROOT/'S02/native.md').read_text(encoding='utf8'))
        checks=[{'text_anchor':probe,'in_original_scope':norm(probe) in original,
                 'in_mineru_markdown':norm(probe) in norm(body)} for probe in PROBES[sid]]
        source_headings=[];missing=[];format_changes=[]
        if html_source:
            map_path=input_path.parent/('official-era-overview.heading-map.json' if sid=='S05-ALT' else 'heading-map.json')
            expected=json.loads(map_path.read_text(encoding='utf8'))['headings']
            actual=json.loads(Path(entry['local_heading_index']).read_text(encoding='utf8'))['headings']
            found={norm(x['title']) for x in actual};counts=Counter();lines=body.splitlines()
            for heading in expected:
                title=heading['heading'];key=norm(title);counts[key]+=1
                candidates=[i+1 for i,line in enumerate(lines) if norm(re.sub(r'^#{1,6}\s+','',line))==key]
                line=candidates[counts[key]-1] if len(candidates)>=counts[key] else None
                represented='markdown_heading' if key in found else 'plain_text_label' if line else 'missing'
                record={'source_heading':title,'source_locator':heading.get('original_locator'),
                        'source_url':heading.get('source_url',entry['source_url']),
                        'markdown_line':line,'representation':represented}
                source_headings.append(record)
                if represented=='missing':missing.append(title)
                elif represented!='markdown_heading':format_changes.append(record)
            (job/'source-heading-crosswalk.json').write_text(json.dumps({'source_id':sid,'source_url':entry['source_url'],
                'markdown_path':'derived/document.md','headings':source_headings},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        page_ok=entry['summary'].get('represented_pages')==[1,2] if sid=='S02' else None
        probe_failures=[p for p in checks if not (p['in_original_scope'] and p['in_mineru_markdown'])]
        passed=identity and not missing and not probe_failures and page_ok is not False
        if sid=='S02':
            reading=job/'reading.md'
            header=('# S02 · Preparing Your Presentation for #AGU20\n\n> source_id: S02\n> URL: '+entry['source_url']+
                    '\n> Parser: actual MinerU cloud, requested model_version=vlm.\n> Scope: both physical PDF pages; historical AGU20 guidance.\n'+
                    '> Original PDF: [original.pdf](../original.pdf)\n> Page mapping: [page-map.json](page-map.json)\n'+
                    '> Unmodified derived output: [page-faithful.md](derived/page-faithful.md)\n'+
                    '> Review scope: source identity, page coverage and bounded text anchors; no full accuracy certification.\n'+
                    '> Private user library only.\n\n')
            reading.write_text(header+body,encoding='utf8')
            recommended=reading;recommended_remote=entry['remote_job']+'/reading.md'
        elif passed:
            recommended=path;recommended_remote=entry['actual_markdown']
        else:
            recommended=input_path.parent/('official-era-overview.native.md' if sid=='S05-ALT' else 'native.md')
            # Native reading files were already uploaded with the acquired originals.
            recommended_remote=str(PurePosixPath(entry['input_path']).parent/recommended.name)
        row={'source_id':sid,'status':'bounded_source_checks_passed' if passed else 'native_primary_due_to_mineru_omission',
             'actual_local_markdown':str(path),'actual_remote_markdown':entry['actual_markdown'],
             'model_version':entry['model_version'],'submitted_input_matches_local_scope':identity,
             'heading_checks':source_headings,'missing_headings':missing,'heading_format_changes':format_changes,
             'bounded_text_probes':checks,'probe_failures':probe_failures,'represented_pdf_pages_match':page_ok,
             'actual_cloud_conversion':True,'recommended_reading_path':str(recommended),
             'recommended_remote_reading_path':recommended_remote,
             'recommended_reading_method':'native_html' if not passed else 'mineru_cloud',
             'whole_document_accuracy_claimed':False,'human_review_performed':False,
             'visual_examples_exhaustively_reviewed':False}
        if sid=='S11':row['disposition']='MinerU-HTML omitted interactive-panel body under Typical Journal Club Structure; use the native_html source copy for design/validity/results/limitations claims. Raw cloud output is preserved.'
        rows.append(row)
        print(sid,row['status'],'format_changes',len(format_changes),'missing',len(missing),'probe_failures',len(probe_failures))
    report={'created_at':datetime.now(timezone.utc).isoformat(),'review_kind':'bounded_source_identity_headings_and_text_anchor_check',
            'source_count':len(rows),'sources':rows,'limitations':[
                'Not a complete word-by-word or figure-by-figure transcription accuracy assessment.',
                'HTML cloud inputs were source-derived scoped subtrees; untouched full HTML remains separately archived.',
                'Historical/local institutional requirements retain their original scope.',
                'S09 three Lessons learned headings survive as plain labels; a source-heading crosswalk supplies their positions.']}
    (ROOT/'mineru-source-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
