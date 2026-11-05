"""Run the existing PDF layout parser on a Slurm compute node, then OCR sparse pages."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys

def run(source,output,parser):
    import importlib.util,fitz
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    spec=importlib.util.spec_from_file_location('existing_reader_processor',parser);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest=module.parse(str(source),output)
    pages=[]
    for number in range(1,manifest['pages']+1):
        blocks=[b for b in manifest['blocks'] if b['page']==number]
        text='\n\n'.join(b.get('text','') for b in blocks if b.get('label') not in ('header','footer'))
        pages.append({'page':number,'text':text,'method':'existing PDF layout parser','needs_ocr':len(text.strip())<30})
    sparse=[p['page'] for p in pages if p['needs_ocr']]
    attempts=[]
    if sparse:
        # A separate OCR input preserves a one-to-one mapping to original PDF pages.
        ocr_source=output/'ocr-input.pdf'
        with fitz.open(source) as pdf,fitz.open() as selected:
            for number in sparse:selected.insert_pdf(pdf,from_page=number-1,to_page=number-1)
            selected.save(ocr_source)
        command=[sys.executable,'-m','mineru.cli.client','-p',str(ocr_source),'-o',str(output/'ocr'),'-b','pipeline','-m','ocr']
        with (output/'ocr.log').open('wb') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        attempts.append({'tool':'MinerU','method':'ocr','exit_code':result.returncode,'original_pages':sparse})
        candidates=list((output/'ocr').rglob('*_content_list.json'))
        if result.returncode or not candidates:raise RuntimeError('MinerU OCR did not produce a content list; inspect the retained cluster OCR log')
        content=json.loads(candidates[0].read_text(encoding='utf8'));texts={}
        for block in content:
            index=block.get('page_idx')
            if not isinstance(index,int) or not 0<=index<len(sparse):continue
            text=str(block.get('text') or block.get('table_body') or '')
            if text:texts.setdefault(sparse[index],[]).append(text)
        for p in pages:
            if p['page'] in texts:
                p.update(text='\n\n'.join(texts[p['page']]),method='MinerU OCR',needs_ocr=False)
    packet={'sha256':digest,'pages':pages,'page_count':manifest['pages'],'cluster_job_id':os.environ.get('SLURM_JOB_ID'),
            'host':os.uname().nodename,'parser':'existing NeoRead reader_processor; MinerU for sparse pages',
            'source':str(source),'attempts':attempts,'original_pdf_preserved':True}
    (output/'pages.json').write_text(json.dumps(packet,ensure_ascii=False),encoding='utf8')
    markdown='\n\n---\n\n'.join('<!-- pdf_page:'+str(p['page'])+' -->\n\n'+p['text'] for p in pages)
    (output/'paper.md').write_text(markdown,encoding='utf8')
    (output/'receipt.json').write_text(json.dumps({k:v for k,v in packet.items() if k!='pages'},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'completed':True,'pages':len(pages),'cluster_job_id':packet['cluster_job_id'],'host':packet['host']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--parser',required=True);a=p.parse_args();run(a.source,a.output,a.parser)
