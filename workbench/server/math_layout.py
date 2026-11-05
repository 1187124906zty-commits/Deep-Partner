"""Reflow displayed mathematics at syntactically safe boundaries in one column.

Only export copies are changed. Operators, operands and condition labels retain
their order; extra rows and alignment marks are presentation, not new equations.
"""
from copy import deepcopy
from functools import lru_cache
import re

TOKEN=re.compile(r'\\[A-Za-z]+|\\.|[^\\]')
ENV=re.compile(r'\\begin\{(matrix|bmatrix|pmatrix|Bmatrix|vmatrix|Vmatrix|aligned|cases|gathered|array)\}(?:\{[rcl]+\})?')


def boundaries(value):
    """Break only outside groups, delimiters and mathematical environments."""
    braces=parens=brackets=left=environment=0;result=[]
    for token in TOKEN.finditer(value):
        part=token[0]
        safe=not (braces or parens or brackets or left or environment)
        if safe:
            if part in ('+','-','='):result.append((token.start(),token.start()))
            elif part==',':result.append((token.end(),token.end()))
            elif part in (r'\quad',r'\qquad'):result.append((token.start(),token.end()))
        if part=='{':braces+=1
        elif part=='}':braces=max(0,braces-1)
        elif not braces:
            if part==r'\begin':environment+=1
            elif part==r'\end':environment=max(0,environment-1)
            elif part==r'\left':left+=1
            elif part==r'\right':left=max(0,left-1)
            elif not left:
                if part=='(':parens+=1
                elif part==')':parens=max(0,parens-1)
                elif part=='[':brackets+=1
                elif part==']':brackets=max(0,brackets-1)
    return result


@lru_cache(maxsize=2048)
def width_em(value):
    """Use installed math font metrics; structured rows are measured separately."""
    value=value.strip()
    if not value:return 0.
    match=ENV.search(value)
    if match:
        ending=r'\end{'+match[1]+'}';end=value.rfind(ending)
        if end>match.end():
            rows=split_rows(value[match.end():end]);inside=max((sum(width_em(c) for c in split_cells(row)) for row in rows),default=0)
            return width_em(value[:match.start()].replace(r'\left\{',''))+inside+width_em(value[end+len(ending):].replace(r'\right.',''))+.6
    try:
        from matplotlib.mathtext import MathTextParser
        from matplotlib.font_manager import FontProperties
        normalized=value.replace(r'\lbrack','[').replace(r'\rbrack',']').replace(r'\text{',r'\mathrm{').replace(r'\displaystyle','')
        normalized=re.sub(r'[\u4e00-\u9fff]','M',normalized)
        return float(MathTextParser('path').parse('$'+normalized+'$',dpi=72,prop=FontProperties(size=10,math_fontfamily='stix')).width)/10
    except (ValueError,RuntimeError):
        normalized=re.sub(r'\\(?:left|right|mathbf|mathcal|mathrm|text|hat|bar|overline|tilde|underset|overset)\b','',value)
        normalized=re.sub(r'\\[A-Za-z]+','x',normalized)
        return sum(1 if '\u4e00'<=c<='\u9fff' else .5 for c in normalized if c not in '{}^_&' and not c.isspace())


def split_cells(value):
    return split_rows(value,'&')


def split_rows(value,separator=r'\\'):
    rows=[];start=0;braces=environment=0
    for token in TOKEN.finditer(value):
        part=token[0]
        if part==separator and not braces and not environment:
            rows.append(value[start:token.start()].strip());start=token.end()
        if part=='{':braces+=1
        elif part=='}':braces=max(0,braces-1)
        elif not braces:
            if part==r'\begin':environment+=1
            elif part==r'\end':environment=max(0,environment-1)
    rows.append(value[start:].strip())
    return [r for r in rows if r]


def lines(value,limit):
    result=[];value=value.strip()
    while width_em(value)>limit:
        candidates=[(before,after) for before,after in boundaries(value) if before>0 and value[:before].strip() and value[after:].strip()]
        fitting=[c for c in candidates if width_em(value[:c[0]])<=limit]
        if not fitting:break
        annotations=[c for c in fitting if value[c[0]:c[1]] in (r'\quad',r'\qquad')]
        before,after=annotations[0] if annotations else fitting[-1]
        result.append(value[:before].strip());value=re.sub(r'^(?:\\quad|\\qquad)\s*','',value[after:].strip())
    return result+[value]


def aligned_rows(rows):
    return rows[:1]+[r"\quad "+row for row in rows[1:]]


def left_array(rows):
    return r'\begin{array}{l}'+(' '+r'\\'+'\n').join(r'\displaystyle '+row for row in rows)+r'\end{array}'


def fold_math(latex,limit_em=18.):
    """Retain numerical matrices; reflow systems and conditional branches."""
    source=''.join(c for c in latex if c in '\n\r\t' or not (ord(c)<32 or 127<=ord(c)<160))
    source=re.sub(r'\\\s+\Z','',source).strip()
    matrix=re.search(r'\\begin\{matrix\}',source)
    if matrix:
        end=source.rfind(r'\end{matrix}')
        if end>matrix.end():
            prefix=source[:matrix.start()];suffix=source[end+len(r'\end{matrix}'):];rows=split_rows(source[matrix.end():end]);cells=[r.split('&',1) for r in rows]
            equations=all(len(c)==2 and c[1].lstrip().startswith('=') for c in cells)
            conditions=all(len(c)==2 and re.match(r'\s*\\(?:text|mathrm)\{',c[1]) for c in cells) and r'\left\{' in prefix
            if equations:
                output=[]
                for c in cells:output+=aligned_rows(lines(c[0].strip()+' '+c[1].strip(),max(10,limit_em-.8)))
                return prefix+left_array(output)+suffix
            if conditions and width_em(source)<=limit_em:
                body=(' '+r'\\'+'\n').join(r'\displaystyle '+expression.strip()+' & '+label.strip() for expression,label in cells)
                return prefix+r'\begin{array}{ll}'+body+r'\end{array}'+suffix
            if conditions:
                output=[]
                for expression,label in cells:
                    output+=aligned_rows(lines(expression,limit_em-2.))
                    output.append(r'\quad '+label.strip())
                return prefix+left_array(output)+suffix
    if width_em(source)<=limit_em:return source
    output=lines(source,limit_em)
    return left_array(aligned_rows(output)) if len(output)>1 else source


def word_math(latex):
    """Avoid empty operator operands introduced by the Word math importer."""
    # An optimal-value superscript is an annotation, not a multiplication with
    # missing operands. Keep the same star glyph as normal text in that script.
    value=re.sub(r'\^\s*\{\s*\\ast\s*\}|\^\s*\\ast\b',lambda m:r'^{\text{∗}}',typographic_math(latex))
    # Pair bare imported bracket commands before attaching a transpose script.
    # Explicit \left/\right pairs already carry the required equation grouping.
    stack=[];changes=[]
    for match in re.finditer(r'\\(?:lbrack|rbrack)\b',value):
        if match[0]==r'\lbrack':stack.append((match,not re.search(r'\\left\s*$',value[:match.start()])))
        elif stack:
            opening,plain=stack.pop()
            if plain and not re.search(r'\\right\s*$',value[:match.start()]):changes.extend([(opening.start(),opening.end(),r'\left['),(match.start(),match.end(),r'\right]')])
    for start,end,replacement in sorted(changes,reverse=True):value=value[:start]+replacement+value[end:]
    return value.replace(r'\mathbf',r'\boldsymbol')


def typographic_math(latex):
    """Conventional descriptor labels are upright; algebraic indices stay italic."""
    labels={'obs','ref','diff','ini','init','out','phys','min','max','full','data','env'}
    def descriptor(match):
        values=match[2].split(',')
        return match[1]+'{'+','.join(r'\mathrm{'+v+'}' if v in labels else v for v in values)+'}'
    value=re.sub(r'([_^])\{([A-Za-z]+(?:,[A-Za-z]+)*)\}',descriptor,latex)
    value=re.sub(r'(?<!\\mathrm)\{RMSE\}',lambda m:r'\mathrm{RMSE}',value)
    # Imported Word functions often arrive as generic text. Native operators
    # retain upright glyphs and the mathematical spacing before their argument.
    value=re.sub(r'\\text\{(sin|cos|tan|tanh|sinh|cosh|exp|ln|log|max|min)\}',lambda m:'\\'+m[1]+' ',value)
    value=re.sub(r'(?<!\\operatorname)\{arg\s*\\,\s*min\}',lambda m:r'{\operatorname{arg\,min}}',value)
    return value


def export_math_document(content,template,columns=2,available_width=None):
    """Prepare editable Word math without mutating manuscript source objects."""
    from .manuscripts import template_info
    from .equation_layout import is_equation_table
    spec=template_info(template);font=spec['size'];page=173.8 if template=='elsevier' else 170.98
    available_width=available_width or page*72/25.4
    column=(available_width-spec.get('column_gap',18)*(columns-1))/columns
    width=column*.78-3
    result=deepcopy(content)
    def walk(node,equation=False):
        equation=equation or is_equation_table(node)
        if node.get('type') in ('inlineMath','blockMath'):
            node.setdefault('attrs',{})['latex']=word_math(node.get('attrs',{}).get('latex',''))
        if node.get('type')=='blockMath' or equation and node.get('type')=='inlineMath':
            attrs=node.setdefault('attrs',{});value=fold_math(attrs.get('latex',''),width/font);attrs['latex']=value
            scale=min(1.,width/max(width,width_em(value)*font));attrs['_column_font_pt']=round(max(font*.85,font*scale),1)
        for child in node.get('content',[]):walk(child,equation)
    walk(result);return result
