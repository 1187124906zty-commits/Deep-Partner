"""Create a heading-bound HTML reading fallback without changing original bytes."""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT=Path(__file__).resolve().parent
SELECTORS={
    'S01':'article#post-195', 'S03':'article#post-43 .entry-content',
    'S06':'article#post-139', 'S07':'article#post-1487', 'S09':'article',
    'S10':'main#main-content', 'S11':'.s-lg-tab-content', 'S12':'.flexPage__body',
}


def read_inline(node,url):
    if isinstance(node,NavigableString):return str(node)
    if not isinstance(node,Tag):return ''
    if node.name=='br':return '\n'
    if node.name=='img':
        label=node.get('alt') or 'Source image'
        return '[Image: '+label+']('+urljoin(url,node.get('src',''))+')' if node.get('src') else label
    text=''.join(read_inline(child,url) for child in node.children)
    if node.name=='a' and node.get('href') and text.strip():return '['+text.strip()+']('+urljoin(url,node['href'])+')'
    if node.name in ('strong','b'):return '**'+text.strip()+'**'
    if node.name in ('em','i'):return '*'+text.strip()+'*'
    return text


def compact(value):
    return re.sub(r'[\t ]+',' ',value).strip()


def render(node,url,headings,level=0):
    if isinstance(node,NavigableString):return ''
    if not isinstance(node,Tag):return ''
    if re.fullmatch('h[1-6]',node.name):
        text=node.get_text(' ',strip=True)
        anchor=node.get('data-native-anchor')
        return '\n<a id="'+anchor+'"></a>\n\n'+'#'*int(node.name[1])+' '+text+'\n\n'
    if node.name in ('p','blockquote'):
        text=compact(read_inline(node,url));return text+'\n\n' if text else ''
    if node.name in ('ul','ol'):
        result=[]
        for index,child in enumerate(node.find_all('li',recursive=False),1):
            marker=str(index)+'. ' if node.name=='ol' else '- '
            result.append('  '*level+marker+compact(read_inline(child,url)))
        return '\n'.join(result)+'\n\n'
    if node.name=='table':
        rows=[]
        for row in node.find_all('tr'):
            cells=[compact(read_inline(cell,url)).replace('|','\\|').replace('\n','<br>') for cell in row.find_all(['td','th'],recursive=False)]
            if cells:rows.append(cells)
        if not rows:return ''
        width=max(map(len,rows));rows=[r+['']*(width-len(r)) for r in rows]
        return '\n'.join(['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*width)+' |']+['| '+' | '.join(r)+' |' for r in rows[1:]])+'\n\n'
    if node.name in ('img','a'):return compact(read_inline(node,url))+'\n\n'
    return ''.join(render(child,url,headings,level) for child in node.children)


def scoped_node(soup,sid):
    if sid=='S08':
        fragment=BeautifulSoup('<article></article>','html.parser');node=fragment.article
        title=next(h for h in soup.find_all('h2') if h.get_text(' ',strip=True)=='Thesis Defense')
        node.append(BeautifulSoup(str(title),'html.parser'))
        paragraph=title.find_next('p');clean=fragment.new_tag('p')
        for child in list(paragraph.children):
            if isinstance(child,Tag) and child.name in ('p','center'):break
            clean.append(BeautifulSoup(str(child),'html.parser'))
        node.append(clean)
        return node,'h2[text="Thesis Defense"] + first following p','Main defense guidance paragraph only; legacy navigation omitted.'
    node=soup.select_one(SELECTORS[sid])
    if node is None:raise ValueError('Missing source selector: '+sid)
    if sid=='S10':
        title=next(h for h in node.find_all(['h1','h2','h3']) if h.get_text(' ',strip=True)=='Journal Club Tips')
        node=title.parent
        return node,'main#main-content heading[text="Journal Club Tips"] parent','Journal Club Tips content block only; department menus omitted.'
    if sid=='S12':
        # A large resources page also contains unrelated academic information.
        title=next(h for h in node.find_all(['h2','h3','h4','h5']) if h.get_text(' ',strip=True)=='Thesis Defense Scheduling')
        fragment=BeautifulSoup('<article></article>','html.parser');picked=fragment.article
        for item in [title,*title.next_siblings]:
            if isinstance(item,Tag) and item.name in ('h2','h3','h4','h5') and item.get_text(' ',strip=True)=='Thesis Extensions':break
            picked.append(BeautifulSoup(str(item),'html.parser'))
        return picked,'.flexPage__body h5[text="Thesis Defense Scheduling"] and following siblings before next heading','Thesis Defense Scheduling subsection only; other graduate resources omitted.'
    return node,SELECTORS[sid],'Article body or journal-club tab; site navigation omitted.'


def extract(meta,source):
    sid=meta['source_id'];folder=ROOT/sid;url=meta['canonical_url']
    soup=BeautifulSoup((ROOT/meta['original_path']).read_bytes(),'html.parser')
    node,selector,scope=scoped_node(soup,sid)
    if sid=='S03':
        for label in node.select('span.collapseomatic'):
            label['data-original-tag']='span';label.name='h2'
        for remove in node.select('.colomat-swap,.watch-action,.wti-clear'):remove.decompose()
        for paragraph in node.find_all('p'):
            if paragraph.get_text(' ',strip=True).startswith('Have you made similar mistakes?'):paragraph.decompose()
    for remove in node.select('script,style,nav,header,footer,form,#ez-toc-container,.ez-toc-container,.post-navigation'):
        remove.decompose()
    headings=[]
    for index,heading in enumerate(node.find_all(re.compile('^h[1-6]$')),1):
        text=heading.get_text(' ',strip=True)
        named=heading.get('id') or next((x.get('id') for x in heading.find_all(attrs={'id':True})),None)
        anchor=sid.lower()+'-h'+str(index).zfill(3)
        headings.append({'source_id':sid,'heading':text,'tag':heading.get('data-original-tag',heading.name),'occurrence':index,
                         'original_html_id':named,'source_url':url+('#'+named if named else ''),
                         'original_locator':{'container_selector':selector,'heading_text':text,'occurrence':index},
                         'native_anchor':anchor})
        heading['data-native-anchor']=anchor
    for link in node.find_all('a',href=True):link['href']=urljoin(url,link['href'])
    for image in node.find_all('img',src=True):image['src']=urljoin(url,image['src'])
    scoped='<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>'+html.escape(source['title'])+'</title></head><body>\n'+str(node)+'\n</body></html>\n'
    (folder/'scoped.html').write_text(scoped,encoding='utf8')
    body=render(node,url,headings)
    body=re.sub(r'\n{3,}','\n\n',body).strip()
    # First-party HTML is preserved separately; this is a derivative reading copy.
    header=('# '+source['title']+'\n\n> source_id: '+sid+'\n> URL: '+url+
            '\n> Retrieved: '+meta['downloaded_at']+'\n> Extraction: native_html (not MinerU)'+
            '\n> Original: [original.html](original.html)\n> Scope: '+scope+
            '\n> Heading map: [heading-map.json](heading-map.json)'+
            '\n> Distribution: private local user library; not for full-text public deployment.'+
            '\n> This file contains source text only; synthesized product rules are stored separately.\n\n')
    (folder/'native.md').write_text(header+body+'\n',encoding='utf8')
    record={'source_id':sid,'method':'native_html','source_url':url,'original_path':meta['original_path'],
            'native_markdown_path':sid+'/native.md','parse_input_path':sid+'/scoped.html',
            'scope_selector':selector,'scope':scope,'headings':headings,'body_characters':len(body),
            'contains_synthesized_rules':False,'mineru_processed':False,
            'created_at':datetime.now(timezone.utc).isoformat()}
    (folder/'heading-map.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return record


def main():
    sources={s['id']:s for s in json.loads((ROOT.parent/'ppt-purpose-source-notes.json').read_text(encoding='utf8'))['sources']}
    manifest=json.loads((ROOT/'fetch-manifest.json').read_text(encoding='utf8'))
    rows=[]
    for meta in manifest['sources']:
        if meta['status']=='downloaded' and meta['original_format']=='html':
            record=extract(meta,sources[meta['source_id']]);rows.append(record)
            print(meta['source_id'],record['body_characters'],len(record['headings']))
    (ROOT/'native-html-manifest.json').write_text(json.dumps({'method':'native_html','sources':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
