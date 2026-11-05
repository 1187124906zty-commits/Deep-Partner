"""Validate completed real PDF translations against source-bound maths."""
from pathlib import Path
import json,re,collections
from server.app import store
from server.pdf_translation import translation_state
owner='u_731b4f07a23742f0917ac6eb77df5df4';pid='05a893386c09449d88366cf6dfdc825f';did='2a8db6776a110a4f36bd1e36af79cf31'
entry,analysis,manifest,options,translations=translation_state(store,owner,pid,did)
errors=[];used=0;pages=set();samples=[]
for block in manifest['blocks']:
 row=translations.get(block['id'])
 if not row:continue
 value=' '.join(s['target'] for s in row.get('sentences',[]))
 expected=collections.Counter(p['token'] for p in block.get('protected',[]))
 actual=collections.Counter(re.findall(r'__WBM[0-9]+__',value))
 if expected!=actual:errors.append({'block':block['id'],'expected':dict(expected),'actual':dict(actual)})
 used+=sum(actual.values());pages.add(block['page'])
 if len(samples)<5 and len(value)>200:samples.append({'page':block['page'],'source':block.get('protectedText',block.get('text','')),'target':value})
assert not errors,errors
vectors=[part for block in manifest['blocks'] for part in ([block] if block.get('image') else block.get('protected',[]))]
for part in vectors:
 assert (analysis/(part.get('vector') or part['image'])).is_file()
report={'source':entry['title'],'target_language':options['targetLanguage'],'complete_translations':len(translations),'translated_pages':sorted(pages),'source_pages':manifest.get('pages',manifest.get('pageCount')),'inline_math_placeholders_retained':used,'source_vector_assets':len(vectors),'placeholder_errors':errors,'samples':samples}
root=store.path(owner,pid);out=root/'.workbench/pdf-translation';out.mkdir(exist_ok=True)
(out/'real-pdf-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
