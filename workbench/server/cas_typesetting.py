"""Elsevier CAS 2.4 adapter, preserving the supplied class and float rules."""
from pathlib import Path
import math,re,unicodedata
from .equation_layout import is_equation_table
from .references import text


def clean_label(value,kind):
    pattern=r'^\s*(?:图|Fig(?:ure)?\.?)\s*(\d+)\s*[:：.、]?\s*' if kind=='figure' else r'^\s*(?:表|Table\.?)\s*(\d+)\s*[:：.、]?\s*'
    match=re.match(pattern,value,re.I)
    return (int(match[1]),value[match.end():]) if match else (None,value)


def visual_length(value):
    return sum(2 if unicodedata.east_asian_width(c) in ('W','F') else .55 if c.isspace() else 1 for c in value)


def table_header_rows(node):
    """Keep a header's rowspans inside one Pandoc table-head row group."""
    rows=node.get('content',[]);count=0
    for index,row in enumerate(rows):
        cells=row.get('content',[])
        if index>=count and not any(c.get('type')=='tableHeader' for c in cells):break
        count=max(count,index+1)
        for cell in cells:count=min(len(rows),max(count,index+max(1,int(cell.get('attrs',{}).get('rowspan',1)))))
    return count


def table_layout(node):
    """Expand table spans and keep explicit authored column widths."""
    rows=node.get('content',[]);occupied={};grid=[];columns=0
    for ri,row in enumerate(rows):
        line=[];ci=0
        for cell in row.get('content',[]):
            while occupied.get((ri,ci)):ci+=1
            attrs=cell.get('attrs',{});span=max(1,int(attrs.get('colspan',1)));down=max(1,int(attrs.get('rowspan',1)))
            line.append({'cell':cell,'column':ci,'colspan':span,'rowspan':down})
            for r in range(ri,ri+down):
                for c in range(ci,ci+span):occupied[(r,c)]=True
            ci+=span
        columns=max(columns,ci);grid.append(line)
    explicit=[0.]*columns;weights=[4.]*columns;aligns=['left']*columns
    for line in grid:
        for item in line:
            cell=item['cell'];ci=item['column'];span=item['colspan'];attrs=cell.get('attrs',{});raw=text(cell)
            size=min(65,max(4,math.sqrt(max(1,visual_length(raw)))*2.2))/span
            for offset in range(span):
                weights[ci+offset]=max(weights[ci+offset],size)
                widths=attrs.get('colwidth') or []
                if offset<len(widths) and widths[offset]:explicit[ci+offset]=max(explicit[ci+offset],float(widths[offset]))
                if attrs.get('align') in ('left','right','center'):aligns[ci+offset]=attrs['align']
    chosen=explicit if all(explicit) else weights;total=sum(chosen)
    return grid,columns,[v/total for v in chosen],aligns,bool(all(explicit))


def native_multiline_math(value):
    """Use AMS multiline spacing owned by the class for the reflowed group."""
    from .math_layout import split_rows
    start=value.find(r'\begin{array}{l}');end=value.rfind(r'\end{array}')
    if start<0 or end<start:return value
    marker=r'\begin{array}{l}';rows=split_rows(value[start+len(marker):end])
    return value[:start]+r'\begin{aligned}& '+(r' \\ & ').join(rows)+r'\end{aligned}'+value[end+len(r'\end{array}'):]


def document_tex(root,document,journal,columns):
    from .journals import inline,escape
    from .manuscripts import PandocDocument
    from .math_layout import fold_math,typographic_math
    root=Path(root);assets=PandocDocument(root,[],False,True);blocks=document['content'].get('content',[])
    output=[];report=[];skip=set();abstract=[];keywords=[];front=[]
    chinese=bool(re.search(r'[\u4e00-\u9fff]',document.get('title','')))
    for i,node in enumerate(blocks[:12]):
        if node.get('type')=='heading' and re.fullmatch(r'摘要|Abstract',text(node).strip(),re.I):
            skip.add(i)
            for j in range(i):
                if blocks[j].get('type')=='paragraph':front.append(blocks[j]);skip.add(j)
            for j in range(i+1,len(blocks)):
                n=blocks[j]
                if n.get('type')!='paragraph':break
                raw=text(n).strip();key=re.match(r'^(?:关键词|Keywords?)\s*[:：]\s*(.*)',raw,re.I)
                if key:keywords=[escape(k.strip()) for k in re.split(r'[;；]',key[1]) if k.strip()]
                elif raw:abstract.append(inline(n.get('content',[])))
                skip.add(j)
            break

    def heading_tex(node):
        value=inline(node.get('content',[]));command={1:'section',2:'subsection',3:'subsubsection'}.get(node.get('attrs',{}).get('level',1),'subsubsection')
        number=re.match(r'^\s*(\d+(?:\.\d+)*)[.、]?\s+(.+)',text(node),re.S)
        if number:
            parts=[int(v) for v in number[1].split('.')];depth=min(3,len(parts));command=['section','subsection','subsubsection'][depth-1]
            prefix=''.join('\\setcounter{'+['section','subsection','subsubsection'][j]+'}{'+str(n if j<depth-1 else n-1)+'}\n' for j,n in enumerate(parts[:3]))
            return prefix+'\\'+command+'{'+escape(number[2])+'}\n'
        return '\\'+command+'*{'+value+'}\n'

    def blocks_tex(nodes):
        result=[]
        for n in nodes:
            kind=n.get('type');attrs=n.get('attrs',{});children=n.get('content',[])
            if kind=='heading':result.append(heading_tex(n))
            elif kind=='paragraph':
                value=inline(children)
                if value.strip():result.append(value+'\n\n')
            elif kind=='blockMath':result.append('\\[\n\\wbfitmath{'+native_multiline_math(fold_math(typographic_math(attrs.get('latex','')),18 if columns==2 else 38))+'}\n\\]\n')
            elif kind in ('bulletList','orderedList'):
                env='enumerate' if kind=='orderedList' else 'itemize';result.append('\\begin{'+env+'}\n'+''.join('\\item '+blocks_tex(c.get('content',[])) for c in children)+'\\end{'+env+'}\n')
            elif kind=='blockquote':result.append('\\begin{quote}'+blocks_tex(children)+'\\end{quote}\n')
            elif kind=='codeBlock':result.append('\\begin{quote}\\ttfamily '+escape(text(n))+'\\end{quote}\n')
            else:result.append(blocks_tex(children))
        return ''.join(result)

    captions={}
    for i,n in enumerate(blocks):
        if n.get('type')!='table' or is_equation_table(n):continue
        for j in [i-1,i+1]:
            if j<0 or j>=len(blocks) or blocks[j].get('type')!='paragraph':continue
            number,value=clean_label(text(blocks[j]),'table')
            if number is not None:captions[i]=(number,value);skip.add(j);break

    bibliography=False
    for i,node in enumerate(blocks):
        if i in skip:continue
        kind=node.get('type');attrs=node.get('attrs',{})
        if kind=='heading' and re.fullmatch(r'(?:\d+[ .、]*)?(?:参考文献|References|Bibliography)',text(node).strip(),re.I):
            bibliography=True;output.append('\\begin{thebibliography}{99}\n');continue
        if bibliography:
            raw=text(node);match=re.match(r'^\[(\d+)\]\s*(.*)',raw,re.S)
            if match:output.append('\\bibitem{ref-'+match[1]+'} '+inline([{'type':'text','text':match[2]}])+'\n');continue
            if kind=='heading':output.append('\\end{thebibliography}\n');bibliography=False
        if is_equation_table(node):
            formulas=[]
            def collect(n):
                if n.get('type') in ('inlineMath','blockMath'):formulas.append(n['attrs']['latex'])
                for c in n.get('content',[]):collect(c)
            collect(node);latex=''.join(c for c in r'\quad '.join(formulas) if c in '\n\r\t' or not (ord(c)<32 or 127<=ord(c)<160));match=re.search(r'[（(]\s*(\d+[a-z]?)\s*[)）]',text(node))
            # Native equation numbering stays in the text flow. Very wide imported
            # Word expressions fit the column without becoming figure floats.
            fitted=native_multiline_math(fold_math(typographic_math(latex),18 if columns==2 else 38))
            output.append('\\begin{equation}\n\\wbfitmath{'+fitted+'}'+('\\tag{'+match[1]+'}' if match else '')+'\n\\end{equation}\n')
            report.append({'block':i,'kind':'equation','number':match[1] if match else None,'environment':'equation','floating':False,'columns':1,'reflowed':fitted!=latex})
        elif kind=='table':
            grid,count,widths,aligns,explicit=table_layout(node);wide=columns==2 and (count>=5 or sum(max((visual_length(text(item['cell'])) for item in line),default=0) for line in grid[:1])>90)
            env='table*' if wide else 'table';options='width=\\textwidth' if wide else 'width=\\linewidth'
            number,caption=captions.get(i,(None,''));result='\\begin{'+env+'}['+options+',cols='+str(count)+',pos=tbp]\n'
            if number is not None:result+='\\setcounter{table}{'+str(number-1)+'}\n'
            if caption:result+='\\caption{'+escape(caption)+'}\\label{wb-table-'+str(i)+'}\n'
            # CAS owns caption typography and float spacing. Column widths follow
            # authored widths when available, otherwise bounded content weights.
            specs=[]
            for fraction,align in zip(widths,aligns):
                command={'left':r'\raggedright','center':r'\centering','right':r'\raggedleft'}[align]
                specs.append('>{'+command+r'\arraybackslash}p{\dimexpr '+f'{fraction:.6f}'+r'\wbtablewidth-'+f'{fraction*2*(count-1):.6f}'+r'\tabcolsep\relax}')
            result+='\\setlength{\\wbtablewidth}{\\tblwidth}\n\\begin{tabular*}{\\tblwidth}{@{}'+''.join(specs)+'@{}}\n\\toprule\n';header_rows=max([1]+[item['rowspan'] for item in grid[0]])
            while header_rows<len(grid) and any(item['cell'].get('type')=='tableHeader' for item in grid[header_rows]):header_rows+=1
            for ri,line in enumerate(grid):
                by_column={item['column']:item for item in line};cells=[];ci=0
                while ci<count:
                    item=by_column.get(ci)
                    if item is None:cells.append('');ci+=1;continue
                    cell=item['cell'];span=item['colspan'];down=item['rowspan'];value=inline(cell.get('content',[])).strip()
                    if down>1:value='\\multirow{'+str(down)+'}{=}{'+value+'}'
                    if span>1:
                        fraction=sum(widths[ci:ci+span]);spec=('@{}' if ci==0 else '')+r'>{\raggedright\arraybackslash}p{\dimexpr '+f'{fraction:.6f}'+r'\wbtablewidth-'+f'{fraction*2*(count-1):.6f}'+r'\tabcolsep+'+str(2*(span-1))+r'\tabcolsep\relax}'+('@{}' if ci+span==count else '');value='\\multicolumn{'+str(span)+'}{'+spec+'}{'+value+'}'
                    cells.append(value);ci+=span
                result+=' & '.join(cells)+r' \\'+'\n'
                if ri==header_rows-1:result+='\\midrule\n'
            result+='\\bottomrule\n\\end{tabular*}\n\\end{'+env+'}\n';output.append(result)
            report.append({'block':i,'kind':'table','wide':wide,'columns':count,'column_widths':widths,'width_source':'authored' if explicit else 'content fit','colspans':[r['colspan'] for line in grid for r in line],'rowspans':[r['rowspan'] for line in grid for r in line],'environment':env,'tabular':'tabular*','caption':caption})
        elif kind=='image':
            source=assets.asset(attrs.get('src',''));caption=attrs.get('title','')
            if i+1<len(blocks) and blocks[i+1].get('type')=='paragraph' and clean_label(text(blocks[i+1]),'figure')[0] is not None:caption=text(blocks[i+1]);skip.add(i+1)
            number,caption=clean_label(caption,'figure')
            from PIL import Image
            with Image.open(source) as image:wide=columns==2 and image.width/image.height>1.5
            env='figure*' if wide else 'figure';width=max(.1,min(1,float(attrs.get('width') or 90)/100));result='\\begin{'+env+'}\n\\centering\n'
            result+='\\includegraphics[width='+str(width)+r'\linewidth]{\detokenize{'+str(source)+'}}\n'
            if number is not None:result+='\\setcounter{figure}{'+str(number-1)+'}\n'
            if caption:result+='\\caption{'+escape(caption)+'}\\label{wb-figure-'+str(i)+'}\n'
            output.append(result+'\\end{'+env+'}\n');report.append({'block':i,'kind':'image','wide':wide,'source':str(source),'environment':env})
        else:output.append(blocks_tex([node]))

    if bibliography:output.append('\\end{thebibliography}\n')
    cls='cas-dc' if columns==2 else 'cas-sc';title=escape(document['title']);author_line=text(front[0]) if front else ''
    author_names=[v.strip() for v in re.split(r'[，,、]|\s+and\s+',author_line) if v.strip()]
    authors='\n'.join(r'\author[1]{'+escape(re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰*]+','',name))+'}' for name in author_names)
    affiliations='\n'.join(r'\affiliation[1]{organization={'+escape(re.sub(r'^[¹²³⁴⁵⁶⁷⁸⁹⁰\d\s]+','',text(n)))+'}}' for n in front[1:] if text(n).strip())
    preamble='\\documentclass[a4paper,fleqn]{'+cls+'}\n'+r'''\usepackage[numbers]{natbib}
\usepackage{xeCJK,xurl}
% The CAS legacy stix negations predate unicode-math's XeTeX definitions.
\ExplSyntaxOn\cs_undefine:c{not=}\cs_undefine:c{not<}\cs_undefine:c{not>}\ExplSyntaxOff
\usepackage{unicode-math}
\setmathfont[Path=/usr/share/fonts/truetype/research-workbench/]{STIXTwoMath-Regular.otf}
% Imported Word vector symbols need a math alphabet, including bold Greek.
\setmainfont[Path=/usr/share/fonts/truetype/research-workbench/,BoldFont=STIX-Bold.otf,ItalicFont=STIX-Italic.otf,BoldItalicFont=STIX-BoldItalic.otf]{STIX-Regular.otf}
\setCJKmainfont[Path=/usr/share/fonts/truetype/research-workbench/,BoldFont=simhei.ttf]{simsun.ttc}
\setCJKsansfont[Path=/usr/share/fonts/truetype/research-workbench/]{simhei.ttf}
\setCJKmonofont[Path=/usr/share/fonts/truetype/research-workbench/]{simsun.ttc}
\newlength{\wbtablewidth}
\newsavebox{\wbequationbox}
\newcommand{\wbfitmath}[1]{\sbox{\wbequationbox}{$\displaystyle #1$}\typeout{WB-MATH=\the\wd\wbequationbox;\the\dimexpr\linewidth-3em\relax}\vcenter{\hbox{\ifdim\wd\wbequationbox>\dimexpr\linewidth-3em\relax\resizebox{\dimexpr\linewidth-3em\relax}{!}{\usebox{\wbequationbox}}\else\usebox{\wbequationbox}\fi}}}
\begin{document}
\let\WriteBookmarks\relax
\def\floatpagepagefraction{1}
\def\textpagefraction{.001}
'''
    if chinese:preamble+=r'\renewcommand{\figurename}{图}'+'\n'+r'\renewcommand{\tablename}{表}'+'\n'
    preamble+=r'\shorttitle{'+escape(journal['name'])+'}\n'+r'\shortauthors{'+escape(re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰*]+','',author_names[0]) if author_names else '')+'}\n'
    preamble+=r'\title[mode=title]{'+title+'}\n'+authors+'\n'+affiliations+'\n'
    if abstract:preamble+='\\begin{abstract}\n'+'\n\n'.join(abstract)+'\n\\end{abstract}\n'
    if keywords:preamble+='\\begin{keywords}\n'+r' \sep '.join(keywords)+'\n\\end{keywords}\n'
    preamble+='\\maketitle\n'
    return (preamble+''.join(output)+'\n\\end{document}\n').replace(r'\mathbf',r'\symbfit'),report
