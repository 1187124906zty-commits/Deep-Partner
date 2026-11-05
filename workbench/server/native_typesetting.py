"""Use journal classes without substituting a homemade page header or title."""
from .cas_typesetting import document_tex as cas_document,clean_label
from .references import text
import re


def document_tex(root,document,journal,columns):
    from .journals import escape,inline
    source,report=cas_document(root,document,journal,columns)
    preamble,body=source.split('\\maketitle\n',1);body=body.rsplit('\\end{document}',1)[0]
    body=re.sub(r'\\begin\{(table\*?)\}\[width=[^]]+\]',lambda m:'\\begin{'+m[1]+'}[tbp]\n\\centering',body).replace('\\tblwidth','\\linewidth')
    blocks=document['content']['content'];front=[];abstract=[];keywords=[]
    for i,node in enumerate(blocks[:12]):
        if node.get('type')=='heading' and re.fullmatch(r'Abstract|摘要',text(node),re.I):
            front=[n for n in blocks[:i] if n.get('type')=='paragraph']
            for following in blocks[i+1:]:
                if following.get('type')!='paragraph':break
                value=text(following);key=re.match(r'^(?:Keywords?|关键词)\s*[:：]\s*(.*)',value,re.I)
                if key:keywords=[escape(k.strip()) for k in re.split('[;；]',key[1])]
                else:abstract.append(inline(following.get('content',[])))
            break
    names=[n.strip() for n in re.split(r'[，,、]|\s+and\s+',text(front[0]) if front else '') if n.strip()]
    names=[escape(re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰*]+','',n)) for n in names];affiliations=[escape(re.sub(r'^[¹²³⁴⁵⁶⁷⁸⁹⁰\d\s]+','',text(n))) for n in front[1:]]
    family=journal['template']['family'];title=escape(document['title']);abstract_text='\n\n'.join(abstract);keys=', '.join(keywords)
    if family=='ieee':
        cls=r'\documentclass[journal'+(',onecolumn' if columns==1 else '')+r']{IEEEtran}'
        fm=r'\title{'+title+'}\n'+r'\author{'+', '.join(names)+(r'\thanks{'+('; '.join(affiliations))+'}' if affiliations else '')+'}\n'+r'\maketitle'+'\n'
        if abstract_text:fm+=r'\begin{abstract}'+abstract_text+r'\end{abstract}'+'\n'
        if keys:fm+=r'\begin{IEEEkeywords}'+keys+r'\end{IEEEkeywords}'+'\n'
    elif family=='springer':
        cls=r'\documentclass['+('iicol,' if columns==2 else '')+r'pdflatex,sn-mathphys-num]{sn-jnl}'
        fm=r'\title{'+title+'}\n'+'\n'.join(r'\author[1]{'+n+'}' for n in names)+'\n'+'\n'.join(r'\affil[1]{\orgname{'+a+'}}' for a in affiliations)+'\n'
        if abstract_text:fm+=r'\abstract{'+abstract_text+'}\n'
        if keys:fm+=r'\keywords{'+keys+'}\n'
        fm+=r'\maketitle'+'\n'
    elif family=='wiley':
        profile=journal['template']['journal_profile'];font=profile.get('font','times').lower()
        options={'stix':'STIX','stixtwotext':'STIX','times':'Times','lato':'LATO','arial':'Arial','garamond':'Garamond','minion':'Minion','utopia':'Utopia','century':'Century'}.get(font,'Times')+str(columns)+'COL'
        style=profile.get('reference_style','');ref='VANCOUVER' if 'Vancouver' in style else 'APA' if 'Psychological' in style else 'AMA' if 'Medical' in style else 'MPS' if 'Mathemat' in style else 'AMA'
        cls=r'\documentclass['+ref+','+options+r']{WileyNJDv5}'+'\n'+r'\articletype{RESEARCH ARTICLE}\received{}\revised{}\accepted{}\journal{'+escape(journal['name'])+'}'
        fm=r'\title{'+title+'}\n'+'\n'.join(r'\author[1]{'+n+'}' for n in names)+'\n'+'\n'.join(r'\address[1]{\orgname{'+a+'}}' for a in affiliations)+'\n'
        if abstract_text:fm+=r'\abstract[Abstract]{'+abstract_text+'}\n'
        if keys:fm+=r'\keywords{'+keys+'}\n'
        fm+=r'\maketitle'+'\n'
    else:raise ValueError('尚无该刊类的排版适配器')
    # All class-owned front matter remains native. Shared text and math are explicit.
    common=preamble[preamble.index('\\usepackage{xeCJK,xurl}'):preamble.index('\\begin{document}')]
    if family!='wiley':common=r'\usepackage{amsmath,amssymb,booktabs,array,multirow,graphicx,etoolbox}'+'\n'+common
    return cls+'\n'+common+'\n'+r'\begin{document}'+'\n'+fm+body+'\n'+r'\end{document}'+'\n',report
