"""Matplotlib Artist properties shared by the web editor and saved plot scripts."""
from pathlib import Path
import functools,json,math,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_hex,BoundaryNorm
from matplotlib.text import Text
from matplotlib.collections import QuadMesh,PathCollection
from matplotlib.transforms import Bbox
from matplotlib.ticker import MaxNLocator
from matplotlib.artist import ArtistInspector
from matplotlib.colors import is_color_like


def number(value,low,high):
    value=float(value)
    if not math.isfinite(value) or not low<=value<=high:raise ValueError('图形属性超出可用范围')
    return value


def axes_hierarchy(figure):
    """Find geometric inset/overlay ownership without modifying any artists."""
    bars={id(a) for a in figure.axes if getattr(a,'_colorbar',None) is not None}
    positions={i:a.get_position(original=True) for i,a in enumerate(figure.axes) if id(a) not in bars}
    parents={};roles={}
    for i,pos in positions.items():
        same=[j for j,other in positions.items() if j<i and max(abs(a-b) for a,b in zip(pos.bounds,other.bounds))<1e-5]
        if same:parents[i]=min(same);roles[i]='overlay';continue
        containers=[(other.width*other.height,j) for j,other in positions.items() if j!=i and other.width*other.height>pos.width*pos.height*1.15 and pos.x0>=other.x0-1e-5 and pos.x1<=other.x1+1e-5 and pos.y0>=other.y0-1e-5 and pos.y1<=other.y1+1e-5]
        if containers:parents[i]=min(containers)[1];roles[i]='inset'
    return parents,roles


def panel_labels(figure):
    cached=getattr(figure,'_workbench_panel_labels',None)
    if cached is None:
        parents,_=axes_hierarchy(figure);main=[i for i,ax in enumerate(figure.axes) if i not in parents and getattr(ax,'_colorbar',None) is None];cached={}
        for index,label in enumerate(figure.texts):
            if not re.fullmatch(r'\s*\(?[A-Za-z]\)?[.)]?\s*',label.get_text()):continue
            point=figure.transFigure.inverted().transform(label.get_transform().transform(label.get_position()))
            distances=[((point[0]-figure.axes[i].get_position().x0)**2+(point[1]-figure.axes[i].get_position().y1)**2,i) for i in main]
            if distances and min(distances)[0]<.04:cached[index]=min(distances)[1]
        figure._workbench_panel_labels=cached
    return [(figure.texts[j],figure.axes[i]) for j,i in cached.items() if j<len(figure.texts) and i<len(figure.axes)]


def artists(figure):
    result={};colorbars={}
    def add(key,kind,label,obj,**extra):
        if hasattr(obj,'set_gid'):obj.set_gid('wb-'+key)
        ax=extra.get('axes')
        result[key]={'kind':kind,'label':label,'object':obj,
          'parent':('axes-'+str(figure.axes.index(ax))) if ax in figure.axes else '',**extra}
    for i,ax in enumerate(figure.axes):
        if getattr(ax,'_colorbar',None) is not None:
            colorbars[id(ax)]=(ax._colorbar,ax._colorbar.mappable)
        for image in [*ax.images,*ax.collections]:
            if getattr(image,'colorbar',None) is not None:colorbars[id(image.colorbar.ax)]=(image.colorbar,image)
    for i,ax in enumerate(figure.axes):
        if id(ax) in colorbars:
            cb,mappable=colorbars[id(ax)];add('colorbar-'+str(i),'colorbar','色条',cb,mappable=mappable,axes=ax);ax.set_gid('wb-colorbar-'+str(i))
            parent='axes-'+str(figure.axes.index(mappable.axes)) if getattr(mappable,'axes',None) in figure.axes else ''
            result['colorbar-'+str(i)]['parent']=parent
            label=ax.yaxis.label if cb.orientation=='vertical' else ax.xaxis.label
            add(f'colorbar-{i}-label','text','色条标题',label,axes=ax,role='colorbar-label',parent=parent)
            tick_axis=ax.yaxis if cb.orientation=='vertical' else ax.xaxis
            texts=tick_axis.get_ticklabels()
            if texts:add(f'colorbar-{i}-ticks','ticks','色条刻度文字',texts,axes=ax,role='colorbar-ticks',parent=parent)
            continue
        add('axes-'+str(i),'axes','子图 '+str(i+1),ax,axes=ax)
        for name,text,label in [('title',ax.title,'标题'),('xlabel',ax.xaxis.label,'横轴标题'),('ylabel',ax.yaxis.label,'纵轴标题')]:
            add(f'ax{i}-{name}','text',label+(' · '+text.get_text()[:26] if text.get_text() else ''),text,axes=ax,role=name)
        for name,label in [('top','上轴'),('bottom','下轴'),('left','左轴'),('right','右轴')]:
            if name in ax.spines:add(f'ax{i}-spine-{name}','spine',label,ax.spines[name],axes=ax,role=name)
        for name,axis,label in [('x',ax.xaxis,'横轴刻度'),('y',ax.yaxis,'纵轴刻度')]:
            texts=axis.get_ticklabels()
            if texts:
                add(f'ax{i}-{name}ticks','ticks',label,texts,axes=ax,role=name)
                for text in texts:text.set_gid('wb-'+f'ax{i}-{name}ticks')
        for j,line in enumerate(ax.lines):add(f'ax{i}-line{j}','line',line.get_label() if not line.get_label().startswith('_') else f'曲线 {j+1}',line,axes=ax)
        for j,image in enumerate(ax.images):add(f'ax{i}-image{j}','field','云图 · 子图 '+str(i+1),image,axes=ax)
        for j,collection in enumerate(ax.collections):
            if isinstance(collection,QuadMesh) or type(collection).__name__ in ('QuadContourSet','TriContourSet'):
                add(f'ax{i}-mesh{j}','field','云图 · 子图 '+str(i+1),collection,axes=ax)
            elif isinstance(collection,PathCollection):add(f'ax{i}-scatter{j}','scatter','散点 · 子图 '+str(i+1),collection,axes=ax)
            else:add(f'ax{i}-collection{j}','collection',type(collection).__name__+' · 子图 '+str(i+1),collection,axes=ax)
        for j,patch in enumerate(ax.patches):
            add(f'ax{i}-patch{j}','patch',('柱形' if type(patch).__name__=='Rectangle' else type(patch).__name__)+f' {j+1}',patch,axes=ax)
        for j,text in enumerate(ax.texts):
            if text.get_text():add(f'ax{i}-text{j}','text',text.get_text()[:32],text,axes=ax,role='annotation')
        for j,table in enumerate(ax.tables):
            for (row,col),cell in sorted(table.get_celld().items()):
                prefix=f'ax{i}-table{j}-{row}-{col}'
                add(prefix,'patch',f'表格 {j+1} · 单元格 {row},{col}',cell,axes=ax)
                add(prefix+'-text','text',f'表格文字 · {cell.get_text().get_text()[:24]}',cell.get_text(),axes=ax,role='table-text')
        for j,obj in enumerate(ax.artists):
            if id(obj) not in {id(e['object']) for e in result.values()}:add(f'ax{i}-artist{j}','artist',type(obj).__name__,obj,axes=ax)
        if hasattr(ax,'zaxis'):
            add(f'ax{i}-zlabel','text','Z 轴标题',ax.zaxis.label,axes=ax,role='zlabel')
            texts=ax.zaxis.get_ticklabels()
            if texts:add(f'ax{i}-zticks','ticks','Z 轴刻度文字',texts,axes=ax,role='z')
        legend=ax.get_legend()
        if legend:
            add(f'ax{i}-legend','legend','图例 · 子图 '+str(i+1),legend,axes=ax)
            for j,text in enumerate(legend.get_texts()):add(f'ax{i}-legend-text{j}','text','图例文字 · '+text.get_text()[:24],text,axes=ax,role='legend-text')
    parents,roles=axes_hierarchy(figure)
    for i,ax in enumerate(figure.axes):
        key='axes-'+str(i)
        if key in result:
            result[key]['parent']='axes-'+str(parents[i]) if i in parents else ''
            result[key]['role']=roles.get(i,'subplot')
            if i in parents:result[key]['label']=('内嵌图 ' if roles[i]=='inset' else '叠加坐标系 ')+str(i+1)
    labels={id(label):ax for label,ax in panel_labels(figure)}
    for i,text in enumerate(figure.texts):
        ax=labels.get(id(text));add('figure-text'+str(i),'text',text.get_text()[:32],text,role='panel-label' if ax is not None else 'figure-text',parent='axes-'+str(figure.axes.index(ax)) if ax is not None else '')
    for i,obj in enumerate(figure.artists):add('figure-artist'+str(i),'artist',type(obj).__name__,obj)
    return result


# Native setters supply the long tail without executing expressions or changing data.
NATIVE_EXCLUDED={'figure','axes','transform','data_transform','clip_box','clip_path','path','paths','verts','vertices',
 'data','xdata','ydata','offsets','array','sizes','urls','url','gid','picker','contains','agg_filter','sketch_params','mouseover',
 'position','x','y','xy','xyann','xlim','ylim','bounds','height','width','data_interval','view_interval','figure','label1','label2',
 'ticklabels','xticklabels','yticklabels','xticks','yticks','colorbar','norm','cmap','clim','fontproperties','unit','units'}
NATIVE_LABELS={'visible':'显示','alpha':'不透明度','zorder':'层级','linewidth':'线宽','linestyle':'线型','edgecolor':'边线颜色',
 'facecolor':'填充颜色','hatch':'填充纹理','antialiased':'抗锯齿','rasterized':'栅格化','snap':'像素对齐','clip_on':'裁切到子图',
 'marker':'点型','markersize':'点大小','markeredgecolor':'点边线颜色','markeredgewidth':'点边线宽','markerfacecolor':'点填充颜色',
 'drawstyle':'连接方式','horizontalalignment':'水平对齐','verticalalignment':'垂直对齐','rotation_mode':'旋转基准','wrap':'自动换行',
 'linespacing':'行距','fontstretch':'字宽','fontvariant':'字体变体','usetex':'TeX 排版','interpolation':'插值','interpolation_stage':'插值阶段',
 'origin':'数据原点','resample':'重采样','filternorm':'插值归一化','filterrad':'插值半径','capstyle':'端点样式','joinstyle':'连接样式',
 'fill':'填充','label':'图例标签','color':'颜色','fontsize':'字号','fontfamily':'字体','fontweight':'字重','fontstyle':'字形'}


def native_properties(entry):
    obj=entry['object'];obj=obj[0] if isinstance(obj,list) and obj else obj
    if not hasattr(obj,'properties') or entry['kind']=='colorbar':return {},[]
    covered={'text':{'text','fontfamily','fontsize','fontweight','fontstyle','color','rotation'},
      'ticks':{'text','fontfamily','fontsize','fontweight','fontstyle','color','rotation'},
      'line':{'color','linewidth','linestyle','marker','markersize','alpha','label'},
      'patch':{'facecolor','edgecolor','linewidth','hatch'},'spine':{'visible','edgecolor','linewidth','linestyle'},
      'axes':{'facecolor','aspect','xscale','yscale'}}.get(entry['kind'],set())
    inspector=ArtistInspector(obj);values={};schema=[]
    try:names=inspector.get_setters()
    except Exception:return {},[]
    for name in names:
        if name in NATIVE_EXCLUDED or name in covered:continue
        getter=getattr(obj,'get_'+name,None)
        if not callable(getter):continue
        try:value=getter()
        except Exception:continue
        if isinstance(value,np.generic):value=value.item()
        if isinstance(value,np.ndarray) and value.size<=16:value=value.tolist()
        choices=[]
        try:
            accepted=inspector.get_valid_values(name)
            if len(accepted)<500 and accepted.lstrip().startswith('{'):
                choices=__import__('re').findall(r"['\"]([^'\"]+)['\"]",accepted.split('}')[0])
        except Exception:pass
        if 'color' in name and value is not None and is_color_like(value):value=to_hex(value,keep_alpha=True);kind='color'
        elif isinstance(value,bool):kind='boolean'
        elif isinstance(value,(int,float)) and math.isfinite(value):kind='number'
        elif isinstance(value,str) and len(value)<1500:kind='select' if choices else 'text'
        elif value is None and name in ('alpha','hatch'):value=1 if name=='alpha' else '';kind='number' if name=='alpha' else 'text'
        elif isinstance(value,(list,tuple)) and len(value)<=4 and all(isinstance(x,str) for x in value):value=','.join(value);kind='text'
        elif isinstance(value,(list,tuple)) and len(value)<=16:
            try:
                if np.asarray(value).size>16 or not np.isfinite(np.asarray(value,dtype=float)).all():continue
                value=list(value);kind='json'
            except (ValueError,TypeError):continue
        else:continue
        values[name]=value;schema.append({'name':name,'label':NATIVE_LABELS.get(name,name),'type':kind,'choices':choices})
    return values,schema


def apply_native(entry,patch):
    if not patch:return
    values,schema=native_properties(entry);allowed={item['name'] for item in schema}
    obj=entry['object'];targets=obj if isinstance(obj,list) else [obj]
    for name,value in patch.items():
        if name not in allowed:raise ValueError('此对象不支持属性 '+name)
        if isinstance(value,list):
            try:
                numeric=np.asarray(value,dtype=float)
                if numeric.size>16 or not np.isfinite(numeric).all():raise ValueError('数组参数无效')
            except (ValueError,TypeError):raise ValueError('数组参数应为至多16个有限数值')
        elif not isinstance(value,(str,bool,int,float,type(None))):raise ValueError('图形属性值无效')
        if isinstance(value,(int,float)) and not math.isfinite(value):raise ValueError('图形参数必须是有限数值')
        for target in targets:
            getattr(target,'set_'+name)(value)


def attached_colorbars(figure,ax):
    return [a for a in figure.axes if getattr(a,'_colorbar',None) is not None and getattr(a._colorbar.mappable,'axes',None) is ax]


def position_axes(figure,ax,bounds):
    labels=[(label,figure.transFigure.inverted().transform(label.get_transform().transform(label.get_position()))) for label,owner in panel_labels(figure) if owner is ax]
    before=ax.get_position().frozen();bars=[(bar,bar.get_position().frozen()) for bar in attached_colorbars(figure,ax)]
    figure.set_layout_engine(None);ax.set_axes_locator(None);ax.set_position(bounds);ax.apply_aspect();after=ax.get_position()
    sx=after.width/before.width;sy=after.height/before.height
    for label,point in labels:
        target=figure.transFigure.transform([after.x0+(point[0]-before.x0)*sx,after.y0+(point[1]-before.y0)*sy]);label.set_position(label.get_transform().inverted().transform(target))
    for bar,pos in bars:
        bar.set_axes_locator(None)
        bar.set_position([after.x0+(pos.x0-before.x0)*sx,after.y0+(pos.y0-before.y0)*sy,pos.width*sx,pos.height*sy])


def field_properties(image):
    lo,hi=image.get_clim();norm=image.norm;alpha=getattr(image,'get_alpha',lambda:None)()
    return {'cmap':image.get_cmap().name,'vmin':float(lo if lo is not None else 0),'vmax':float(hi if hi is not None else 1),
      'levels':len(norm.boundaries)-1 if isinstance(norm,BoundaryNorm) else 0,'alpha':float(alpha if alpha is not None else 1)}


def layout_description(figure):
    """Describe authored cells, insets and spans. Inspection never reflows a plot."""
    all_axes=[(key,entry) for key,entry in artists(figure).items() if entry['kind']=='axes']
    main=[(key,entry) for key,entry in all_axes if entry.get('role') not in ('inset','overlay')]
    existing=getattr(figure,'_workbench_layout',None)
    if existing and existing.get('version')==2:return existing
    nested={key:{'parent':entry['parent'],'role':entry['role']} for key,entry in all_axes if entry.get('role') in ('inset','overlay')}
    if not main:return {'version':2,'rows':1,'cols':1,'gap_x':0,'gap_y':0,'cells':{},'nested':nested}
    positions={key:entry['object'].get_position(original=True) for key,entry in main}
    specs=[entry['object'].get_subplotspec() for _,entry in main]
    grid=specs[0].get_gridspec() if specs[0] is not None else None
    slots={};rects={};row_tracks=[]
    if grid is not None and all(spec is not None and spec.get_gridspec() is grid for spec in specs):
        rows,cols=grid.nrows,grid.ncols
        bottom,top,left,right=grid.get_grid_positions(figure)
        for (key,_),spec in zip(main,specs):slots[key]={'row':spec.rowspan.start,'col':spec.colspan.start,'rowspan':len(spec.rowspan),'colspan':len(spec.colspan)}
        xe=[0];ye=[0]
        for k in range(1,cols):
            ends=[p.x1 for key,p in positions.items() if slots[key]['col']+slots[key]['colspan']==k]
            starts=[p.x0 for key,p in positions.items() if slots[key]['col']==k]
            xe.append((max(ends)+min(starts))/2 if ends and starts else (float(right[k-1])+float(left[k]))/2)
        for k in range(1,rows):
            ends=[1-p.y0 for key,p in positions.items() if slots[key]['row']+slots[key]['rowspan']==k]
            starts=[1-p.y1 for key,p in positions.items() if slots[key]['row']==k]
            ye.append((max(ends)+min(starts))/2 if ends and starts else 1-(float(bottom[k-1])+float(top[k]))/2)
        xe.append(1);ye.append(1)
        for key,_ in main:
            r,c,rs,cs=(slots[key][name] for name in ('row','col','rowspan','colspan'))
            rects[key]=[xe[c],ye[r],xe[c+cs]-xe[c],ye[r+rs]-ye[r]]
        row_tracks=[list(map(float,xe)) for _ in range(rows)]
    else:
        # Authored rows can have different column counts. Compare intervals within
        # each row instead of mixing centers from unrelated rows into a fake grid.
        groups=[]
        for key,p in sorted(positions.items(),key=lambda item:1-item[1].y1):
            center=1-p.y0-p.height/2
            match=next((group for group in groups if abs(center-group['center'])<=.3*max(p.height,group['height'])),None)
            if match is None:groups.append({'center':center,'height':p.height,'items':[key]})
            else:match['items'].append(key);match['center']=sum(1-positions[k].y0-positions[k].height/2 for k in match['items'])/len(match['items']);match['height']=max(match['height'],p.height)
        groups.sort(key=lambda group:group['center']);rows=len(groups);cols=max(len(g['items']) for g in groups)
        ye=[0]
        for previous,current in zip(groups,groups[1:]):ye.append((max(1-positions[k].y0 for k in previous['items'])+min(1-positions[k].y1 for k in current['items']))/2)
        ye.append(1)
        detached=[a.get_position() for a in figure.axes if getattr(a,'_colorbar',None) is not None and getattr(a._colorbar.mappable,'axes',None) not in figure.axes]
        bottom=max(1-p.y0 for p in positions.values());below=[1-p.y1 for p in detached if 1-p.y1>bottom]
        if below:ye[-1]=(bottom+min(below))/2
        for row,group in enumerate(groups):
            items=sorted(group['items'],key=lambda k:positions[k].x0)
            edges=[0,*[(positions[a].x1+positions[b].x0)/2 for a,b in zip(items,items[1:])],1]
            row_tracks.append(list(map(float,edges)))
            for col,key in enumerate(items):
                slots[key]={'row':row,'col':col,'rowspan':1,'colspan':cols if len(items)==1 else 1}
                rects[key]=[edges[col],ye[row],edges[col+1]-edges[col],ye[row+1]-ye[row]]
        xe=row_tracks[max(range(rows),key=lambda i:len(row_tracks[i]))]
    cells={}
    for key,entry in main:
        slot=slots[key];pos=positions[key];rect=list(map(float,rects[key]))
        if rect[2]<=0 or rect[3]<=0:raise ValueError('原始子图布局存在交叠，无法划分独立单元')
        x=(pos.x0-rect[0])/rect[2];y=(1-pos.y1-rect[1])/rect[3]
        cells[key]={**slot,'rect':rect,'x':float(x),'y':float(y),'width':float(pos.width/rect[2]),'height':float(pos.height/rect[3]),'title':entry['object'].get_title() or entry['label']}
    return {'version':2,'rows':rows,'cols':cols,'gap_x':0,'gap_y':0,'cells':cells,'nested':nested,'x_edges':list(map(float,xe)),'y_edges':list(map(float,ye)),'row_tracks':row_tracks}


def apply_layout(figure,value,resize=True):
    original=layout_description(figure);rows=int(number(value.get('rows',original['rows']),1,12));cols=int(number(value.get('cols',original['cols']),1,12))
    main=[(key,entry) for key,entry in artists(figure).items() if key in original['cells']]
    changed=rows!=original['rows'] or cols!=original['cols']
    if changed and rows*cols<len(main):raise ValueError('格子数量少于子图数量')
    if changed and resize:figure.set_size_inches(figure.get_figwidth()/original['cols']*cols,figure.get_figheight()/original['rows']*rows)
    gap_x=number(value.get('gap_x',original.get('gap_x',0)),0,.3);gap_y=number(value.get('gap_y',original.get('gap_y',0)),0,.3)
    cw=(1-gap_x*(cols-1))/cols;ch=(1-gap_y*(rows-1))/rows
    if min(cw,ch)<=.025:raise ValueError('分块间距过大')
    regrid=changed or gap_x!=original.get('gap_x',0) or gap_y!=original.get('gap_y',0)
    cells={};figure.set_layout_engine(None)
    for index,(key,entry) in enumerate(main):
        base=original['cells'][key]
        if changed:base={**base,'row':index//cols,'col':index%cols,'rowspan':1,'colspan':1,'x':.17,'y':.15,'width':.68,'height':.67}
        cell={**base,**value.get('cells',{}).get(key,{})}
        row=int(number(cell['row'],0,rows-1));col=int(number(cell['col'],0,cols-1))
        rs=int(number(cell.get('rowspan',1),1,rows-row));cs=int(number(cell.get('colspan',1),1,cols-col))
        moved=row!=base['row'] or col!=base['col']
        if regrid:rect=[col*(cw+gap_x),row*(ch+gap_y),cs*cw+(cs-1)*gap_x,rs*ch+(rs-1)*gap_y]
        elif moved:
            destination=next((item['rect'] for item in original['cells'].values() if item['row']==row and item['col']==col),None)
            xe=original['x_edges'];ye=original['y_edges'];rect=destination or [xe[col],ye[row],xe[min(cols,col+cs)]-xe[col],ye[row+rs]-ye[row]]
        else:rect=base['rect']
        x=number(cell.get('x',.16),0,.95);y=number(cell.get('y',.15),0,.95)
        w=number(cell.get('width',.68),.01,1-x);h=number(cell.get('height',.67),.01,1-y)
        left=rect[0]+x*rect[2];top=rect[1]+y*rect[3]
        ax=entry['object'];before=ax.get_position().frozen();position_axes(figure,ax,[left,1-top-h*rect[3],w*rect[2],h*rect[3]])
        actual=ax.get_position()
        for nested_key,info in original.get('nested',{}).items():
            if info['parent']!=key:continue
            child_ax=figure.axes[int(nested_key.split('-')[1])];child=child_ax.get_position().frozen()
            if info['role']=='overlay':position_axes(figure,child_ax,actual.bounds)
            else:position_axes(figure,child_ax,[actual.x0+(child.x0-before.x0)*actual.width/before.width,actual.y0+(child.y0-before.y0)*actual.height/before.height,child.width*actual.width/before.width,child.height*actual.height/before.height])
        actual=ax.get_position()
        cells[key]={**cell,'row':row,'col':col,'rowspan':rs,'colspan':cs,'rect':rect,'x':float((actual.x0-rect[0])/rect[2]),'y':float((1-actual.y1-rect[1])/rect[3]),'width':float(actual.width/rect[2]),'height':float(actual.height/rect[3])}
    figure._workbench_layout={'version':2,'rows':rows,'cols':cols,'gap_x':gap_x,'gap_y':gap_y,'cells':cells,'nested':original.get('nested',{}),'row_tracks':original.get('row_tracks',[]),'x_edges':original.get('x_edges',[i/cols for i in range(cols+1)]) if not regrid else [i*(cw+gap_x) for i in range(cols)]+[1],'y_edges':original.get('y_edges',[i/rows for i in range(rows+1)]) if not regrid else [i*(ch+gap_y) for i in range(rows)]+[1]}


def properties(entry):
    obj=entry['object'];kind=entry['kind']
    if kind in ('text','ticks'):
        text=obj[0] if kind=='ticks' else obj
        return {'text':text.get_text(),'font_family':text.get_fontfamily()[0],'font_size':text.get_fontsize(),
          'font_weight':str(text.get_fontweight()),'font_style':text.get_fontstyle(),'color':to_hex(text.get_color()),'rotation':text.get_rotation()}
    if kind=='line':return {'color':to_hex(obj.get_color()),'line_width':obj.get_linewidth(),'line_style':obj.get_linestyle(),
      'marker':str(obj.get_marker()),'marker_size':obj.get_markersize(),'alpha':float(obj.get_alpha() if obj.get_alpha() is not None else 1),'label':obj.get_label()}
    if kind=='scatter':
        colors=obj.get_facecolors();sizes=obj.get_sizes()
        return {'color':to_hex(colors[0]) if len(colors) else '#5483a8','marker_size':float(np.sqrt(sizes[0])) if len(sizes) else 5,'alpha':float(obj.get_alpha() if obj.get_alpha() is not None else 1)}
    if kind=='field':return field_properties(obj)
    if kind=='spine':
        side=entry['role'];axis=entry['axes'].xaxis if side in ('top','bottom') else entry['axes'].yaxis
        ticks=axis.get_major_ticks();second=side in ('top','right')
        return {'visible':obj.get_visible(),'color':to_hex(obj.get_edgecolor()),'line_width':obj.get_linewidth(),
          'line_style':obj.get_linestyle(),'ticks':bool(ticks and (ticks[0].tick2line if second else ticks[0].tick1line).get_visible()),
          'tick_labels':bool(ticks and (ticks[0].label2 if second else ticks[0].label1).get_visible()),
          'label':axis.label.get_text(),'font_size':axis.label.get_fontsize(),'label_position':axis.get_label_position()}
    if kind=='patch':return {'facecolor':to_hex(obj.get_facecolor()),'edgecolor':to_hex(obj.get_edgecolor()),'line_width':obj.get_linewidth(),'hatch':obj.get_hatch() or ''}
    if kind=='colorbar':
        result=field_properties(entry['mappable']);label=obj.ax.yaxis.label if obj.orientation=='vertical' else obj.ax.xaxis.label
        texts=obj.ax.get_yticklabels() if obj.orientation=='vertical' else obj.ax.get_xticklabels()
        return {**result,'label':label.get_text(),'font_size':label.get_fontsize(),'tick_font_size':texts[0].get_fontsize() if texts else 10,'tick_count':len(obj.get_ticks())}
    if kind=='legend':
        texts=obj.get_texts();frame=obj.get_frame()
        return {'font_size':texts[0].get_fontsize() if texts else 10,'font_family':texts[0].get_fontfamily()[0] if texts else 'DejaVu Sans',
          'columns':obj._ncols,'frame':obj.get_frame_on(),'color':to_hex(texts[0].get_color()) if texts else '#222222','background':to_hex(frame.get_facecolor()),'alpha':float(frame.get_alpha() if frame.get_alpha() is not None else 1)}
    if kind=='axes':
        pos=obj.get_position();result={'x':pos.x0,'y':1-pos.y1,'width':pos.width,'height':pos.height,
          'x_min':obj.get_xlim()[0],'x_max':obj.get_xlim()[1],'y_min':obj.get_ylim()[0],'y_max':obj.get_ylim()[1],
          'x_scale':obj.get_xscale(),'y_scale':obj.get_yscale(),'aspect':str(obj.get_aspect()),'facecolor':to_hex(obj.get_facecolor()),
          'x_tick_count':len(obj.get_xticks()),'y_tick_count':len(obj.get_yticks()),
          'grid':any(line.get_visible() for line in [*obj.get_xgridlines(),*obj.get_ygridlines()]),
          'title':obj.get_title(),'axis_color':to_hex(obj.xaxis.label.get_color()),
          'axis_width':next((spine.get_linewidth() for spine in obj.spines.values()),.8),
          'spines':{side:spine.get_visible() for side,spine in obj.spines.items()}}
        for name in ('x','y','z'):
            axis=getattr(obj,name+'axis',None)
            if axis is None:continue
            limits=getattr(obj,'get_'+name+'lim')()
            result.update({name+'_label':axis.label.get_text(),name+'_min':limits[0],name+'_max':limits[1],name+'_scale':getattr(obj,'get_'+name+'scale')(),name+'_tick_count':len(axis.get_ticklocs())})
        return result
    return {}


def describe(figure):
    FigureCanvasAgg(figure);figure.canvas.draw();renderer=figure.canvas.get_renderer();width,height=figure.bbox.width,figure.bbox.height
    output=[]
    for key,entry in artists(figure).items():
        obj=entry['object'];kind=entry['kind']
        try:
            if kind=='ticks':bbox=Bbox.union([t.get_window_extent(renderer) for t in obj if t.get_visible()])
            elif kind=='colorbar':bbox=entry['axes'].get_window_extent(renderer)
            elif kind=='field':bbox=entry['axes'].get_window_extent(renderer)
            else:bbox=obj.get_window_extent(renderer)
            bounds=[bbox.x0/width,1-bbox.y1/height,bbox.width/width,bbox.height/height]
            if not all(math.isfinite(x) for x in bounds):continue
        except Exception:bounds=[0,0,0,0]
        visible=bool(obj.get_visible()) if hasattr(obj,'get_visible') else True
        ghost=not visible or kind=='text' and not obj.get_text()
        if ghost and entry.get('axes') is not None:
            axbox=entry['axes'].get_position();role=entry.get('role')
            if role in ('top','bottom','left','right'):
                if role in ('top','bottom'):bounds=[axbox.x0,1-(axbox.y1 if role=='top' else axbox.y0)-.008,axbox.width,.016]
                else:bounds=[(axbox.x0 if role=='left' else axbox.x1)-.008,1-axbox.y1,.016,axbox.height]
            elif role=='title':bounds=[axbox.x0,1-axbox.y1-.045,axbox.width,.035]
            elif role=='xlabel':bounds=[axbox.x0,1-axbox.y0+.035,axbox.width,.035]
            elif role=='ylabel':bounds=[axbox.x0-.08,1-axbox.y1,.035,axbox.height]
        native,schema=native_properties(entry)
        raw_bounds=bounds
        x0=max(0,min(1,bounds[0]));y0=max(0,min(1,bounds[1]));x1=max(x0,min(1,bounds[0]+bounds[2]));y1=max(y0,min(1,bounds[1]+bounds[3]))
        bounds=[x0,y0,x1-x0,y1-y0]
        output.append({'id':key,'kind':kind,'label':entry['label'],'properties':{**properties(entry),'matplotlib':native},'schema':schema,
          'parent':entry.get('parent',''),'role':entry.get('role',''),'visible':visible,'ghost':ghost,'bounds':bounds,
          'raw_bounds':raw_bounds,'draggable':kind in ('text','legend','axes','colorbar') and entry.get('role')!='legend-text'})
    return output


def update_field(image,patch):
    if 'cmap' in patch:image.set_cmap(patch['cmap'])
    low,high=image.get_clim();low=number(patch.get('vmin',low),-1e30,1e30);high=number(patch.get('vmax',high),-1e30,1e30)
    if low>=high:raise ValueError('色阶最小值应小于最大值')
    if 'levels' in patch:
        count=int(number(patch['levels'],0,50))
        if count>=2:image.set_norm(BoundaryNorm(np.linspace(low,high,count+1),image.get_cmap().N))
        else:image.set_norm(matplotlib.colors.Normalize(low,high))
    else:image.set_clim(low,high)
    if 'alpha' in patch:image.set_alpha(number(patch['alpha'],0,1))
    if getattr(image,'colorbar',None):image.colorbar.update_normal(image)


def apply_changes(figure,changes):
    overall=changes.get('figure',{})
    typography=dict(getattr(figure,'_workbench_typography',{}))
    if 'font_size' in overall:
        for key in ('title_size','label_size','tick_size','legend_size'):typography.pop(key,None)
    figure._workbench_typography={**typography,**{key:overall[key] for key in ('font_family','font_size','font_weight','font_style','text_color','title_size','label_size','tick_size','legend_size') if key in overall}}
    if 'dpi' in overall:figure._workbench_export_dpi=int(number(overall['dpi'],72,1200))
    if 'facecolor' in overall:figure.set_facecolor(overall['facecolor'])
    if 'transparent' in overall:figure._workbench_transparent=bool(overall['transparent'])
    if 'width' in overall or 'height' in overall:figure.set_size_inches(number(overall.get('width',figure.get_figwidth()),1,40),number(overall.get('height',figure.get_figheight()),1,40))
    if any(key in overall for key in ('font_family','font_size','font_weight','font_style','text_color')):
        for text in figure.findobj(Text):
            if overall.get('font_family'):text.set_fontfamily(overall['font_family'])
            if 'font_size' in overall:text.set_fontsize(number(overall['font_size'],4,100))
            if 'font_weight' in overall:text.set_fontweight(overall['font_weight'])
            if 'font_style' in overall:text.set_fontstyle(overall['font_style'])
            if 'text_color' in overall:text.set_color(overall['text_color'])
    for entry in artists(figure).values():
        role=entry.get('role');kind=entry['kind'];size_key='title_size' if role=='title' else 'label_size' if role in ('xlabel','ylabel','zlabel','colorbar-label') else 'tick_size' if kind=='ticks' else 'legend_size' if role=='legend-text' else ''
        if size_key and size_key in overall:
            for target in entry['object'] if isinstance(entry['object'],list) else [entry['object']]:target.set_fontsize(number(overall[size_key],4,100))
    spacing={k:number(overall[k],0,2) for k in ('wspace','hspace') if k in overall}
    if spacing:
        layout=figure.get_layout_engine()
        if layout is not None and hasattr(layout,'set'):layout.set(**spacing)
        else:figure.subplots_adjust(**spacing)
    if changes.get('layout'):apply_layout(figure,changes['layout'],resize=not ('width' in overall or 'height' in overall))
    FigureCanvasAgg(figure);figure.canvas.draw()
    known=artists(figure)
    order={'axes':0,'field':1,'collection':1,'colorbar':2,'line':3,'scatter':3,'patch':3,'spine':4,'legend':5,'ticks':6,'text':7}
    ordered=sorted(changes.get('objects',{}).items(),key=lambda pair:order.get(known.get(pair[0],{}).get('kind'),3))
    for key,patch in ordered:
        if key not in known:raise ValueError('图形对象已变化，请重新打开')
        entry=known[key];obj=entry['object'];kind=entry['kind']
        if kind in ('text','ticks'):
            texts=obj if kind=='ticks' else [obj]
            for text in texts:
                if 'text' in patch and kind=='text':text.set_text(str(patch['text'])[:2000])
                if 'font_family' in patch:text.set_fontfamily(str(patch['font_family']))
                if 'font_size' in patch:text.set_fontsize(number(patch['font_size'],4,100))
                if 'font_weight' in patch:text.set_fontweight(patch['font_weight'])
                if 'font_style' in patch:text.set_fontstyle(patch['font_style'])
                if 'color' in patch:text.set_color(patch['color'])
                if 'rotation' in patch:text.set_rotation(number(patch['rotation'],-360,360))
        elif kind=='line':
            prior_label=obj.get_label()
            for name,setter in [('color',obj.set_color),('line_style',obj.set_linestyle),('marker',obj.set_marker),('label',obj.set_label)]:
                if name in patch:setter(patch[name])
            for name,setter,low,high in [('line_width',obj.set_linewidth,.1,15),('marker_size',obj.set_markersize,.1,35),('alpha',obj.set_alpha,0,1)]:
                if name in patch:setter(number(patch[name],low,high))
            legend=entry['axes'].get_legend()
            if legend:
                for handle,text in zip(legend.legend_handles,legend.get_texts()):
                    if text.get_text()==prior_label:
                        text.set_text(obj.get_label())
                        for attr in ('color','linestyle','linewidth','marker','markersize'):
                            if hasattr(handle,'set_'+attr):getattr(handle,'set_'+attr)(getattr(obj,'get_'+attr)())
        elif kind=='scatter':
            if 'color' in patch:obj.set_color(patch['color'])
            if 'marker_size' in patch:obj.set_sizes([number(patch['marker_size'],.1,40)**2])
            if 'alpha' in patch:obj.set_alpha(number(patch['alpha'],0,1))
        elif kind=='field':update_field(obj,patch)
        elif kind=='patch':
            for name,setter in [('facecolor',obj.set_facecolor),('edgecolor',obj.set_edgecolor),('hatch',obj.set_hatch),('line_width',obj.set_linewidth)]:
                if name in patch:setter(patch[name])
        elif kind=='spine':
            side=entry['role'];ax=entry['axes'];axis=ax.xaxis if side in ('top','bottom') else ax.yaxis
            for name,setter in [('visible',obj.set_visible),('color',obj.set_edgecolor),('line_width',obj.set_linewidth),('line_style',obj.set_linestyle)]:
                if name in patch:setter(patch[name])
            args={}
            if 'ticks' in patch:args[side]=bool(patch['ticks'])
            if 'tick_labels' in patch:args['label'+side]=bool(patch['tick_labels'])
            if args:axis.set_tick_params(**args)
            if 'label' in patch:axis.label.set_text(str(patch['label']));axis.set_label_position(side)
            if 'font_size' in patch:axis.label.set_fontsize(number(patch['font_size'],4,100))
        elif kind=='colorbar':
            update_field(entry['mappable'],patch)
            if 'label' in patch:obj.set_label(str(patch['label']))
            label=obj.ax.yaxis.label if obj.orientation=='vertical' else obj.ax.xaxis.label
            if 'font_size' in patch:label.set_fontsize(number(patch['font_size'],4,100))
            if 'tick_font_size' in patch:obj.ax.tick_params(labelsize=number(patch['tick_font_size'],4,100))
            if 'tick_count' in patch:obj.locator=MaxNLocator(nbins=int(number(patch['tick_count'],2,25)));obj.update_ticks()
        elif kind=='legend':
            if 'columns' in patch:
                prior=obj;axes=entry['axes'];texts=prior.get_texts()
                obj=axes.legend(prior.legend_handles,[t.get_text() for t in texts],ncols=int(number(patch['columns'],1,12)),
                  loc=patch.get('location',prior._loc),frameon=prior.get_frame_on(),
                  prop={'family':texts[0].get_fontfamily() if texts else ['DejaVu Sans'],'size':texts[0].get_fontsize() if texts else 10})
                obj.set_gid('wb-'+key);entry['object']=obj
            if 'location' in patch:obj.set_bbox_to_anchor(None);obj.set_loc(patch['location'])
            for text in obj.get_texts():
                if 'font_family' in patch:text.set_fontfamily(patch['font_family'])
                if 'font_size' in patch:text.set_fontsize(number(patch['font_size'],4,100))
                if 'color' in patch:text.set_color(patch['color'])
            if 'columns' in patch:obj.set_ncols(int(number(patch['columns'],1,12)))
            if 'frame' in patch:obj.set_frame_on(bool(patch['frame']))
            if 'background' in patch:obj.get_frame().set_facecolor(patch['background'])
            if 'alpha' in patch:obj.get_frame().set_alpha(number(patch['alpha'],0,1))
        elif kind=='axes':
            if 'grid' in patch:obj.grid(bool(patch['grid']))
            if 'facecolor' in patch:obj.set_facecolor(patch['facecolor'])
            if 'title' in patch:obj.set_title(str(patch['title']))
            for side,visible in patch.get('spines',{}).items():
                if side in obj.spines:obj.spines[side].set_visible(bool(visible))
            for spine in obj.spines.values():
                if 'axis_color' in patch:spine.set_edgecolor(patch['axis_color'])
                if 'axis_width' in patch:spine.set_linewidth(number(patch['axis_width'],0,15))
            for name in ('x','y','z'):
                if not hasattr(obj,name+'axis'):continue
                axis=getattr(obj,name+'axis')
                if name+'_label' in patch:axis.label.set_text(str(patch[name+'_label']))
                if 'axis_color' in patch:obj.tick_params(axis=name,colors=patch['axis_color']);axis.label.set_color(patch['axis_color'])
                if name+'_scale' in patch:getattr(obj,'set_'+name+'scale')(patch[name+'_scale'])
                if name+'_min' in patch or name+'_max' in patch:
                    lo,hi=getattr(obj,'get_'+name+'lim')();getattr(obj,'set_'+name+'lim')(number(patch.get(name+'_min',lo),-1e30,1e30),number(patch.get(name+'_max',hi),-1e30,1e30))
                if name+'_tick_count' in patch:getattr(obj,name+'axis').set_major_locator(MaxNLocator(nbins=int(number(patch[name+'_tick_count'],2,40))))
            if 'aspect' in patch:obj.set_aspect(patch['aspect'] if patch['aspect'] in ('auto','equal') else number(patch['aspect'],.001,1000))
            if any(k in patch for k in ('x','y','width','height')):
                pos=obj.get_position();x=number(patch.get('x',pos.x0),-.2,1.2);y=number(patch.get('y',1-pos.y1),-.2,1.2)
                width=number(patch.get('width',pos.width),.02,1.3);height=number(patch.get('height',pos.height),.02,1.3);position_axes(figure,obj,[x,1-y-height,width,height])
        apply_native(entry,patch.get('matplotlib',{}))
        move=patch.get('move')
        if move:
            dx=number(move.get('dx',0),-1,1);dy=number(move.get('dy',0),-1,1)
            if kind in ('axes','colorbar'):
                ax=obj if kind=='axes' else obj.ax;pos=ax.get_position();position_axes(figure,ax,[pos.x0+dx,pos.y0-dy,pos.width,pos.height])
            elif kind=='legend':
                bbox=obj.get_window_extent(figure.canvas.get_renderer());point=figure.transFigure.inverted().transform([(bbox.x0+bbox.x1)/2,(bbox.y0+bbox.y1)/2]);obj.set_loc('center');obj.set_bbox_to_anchor((point[0]+dx,point[1]-dy),transform=figure.transFigure)
            elif kind=='text' and entry.get('role')!='legend-text':
                current=obj.get_transform().transform(obj.get_position());nextpos=obj.get_transform().inverted().transform(current+[dx*figure.bbox.width,-dy*figure.bbox.height]);obj.set_position(nextpos)
                if entry.get('role') in ('xlabel','ylabel'):
                    axis=entry['axes'].xaxis if entry['role']=='xlabel' else entry['axes'].yaxis;axis.set_label_coords(*nextpos,transform=obj.get_transform())
                if entry.get('role')=='title':entry['axes']._autotitlepos=False
    return figure


def install(workspace,plot_program='',compute_program='',overrides=None):
    """Apply saved styles when the original plotting program next exports a figure."""
    from matplotlib.figure import Figure
    import pickle,uuid,sys,hashlib
    workspace=Path(workspace);original=Figure.savefig
    @functools.wraps(original)
    def save(figure,fname,*args,**kwargs):
        try:
            path=Path(fname).resolve();project=workspace/'project';asset=path.relative_to(project).as_posix()
            registry=workspace/'.workbench/figures/registry.json'
            entries=json.loads(registry.read_text()) if registry.exists() else {}
            entry=entries.get(asset) or next((v for k,v in entries.items() if Path(k).with_suffix('')==Path(asset).with_suffix('')),None)
            if entry:
                style=workspace/'.workbench/figures'/entry['id']/'style.json'
                value=json.loads(style.read_text()) if style.exists() else {}
                if overrides and entry.get('asset') in overrides:value['changes']=overrides[entry['asset']]
                stamp=(str(style),value.get('revision',0))
                if getattr(figure,'_workbench_style',None)!=stamp:
                    apply_changes(figure,value.get('changes',{}));figure._workbench_style=stamp
        except (ValueError,FileNotFoundError,TypeError):pass
        if hasattr(figure,'_workbench_export_dpi'):kwargs['dpi']=figure._workbench_export_dpi
        if hasattr(figure,'_workbench_transparent'):kwargs['transparent']=figure._workbench_transparent
        result=original(figure,fname,*args,**kwargs)
        if isinstance(fname,(str,Path)):
            path=Path(fname).resolve()
            if path.suffix.lower()=='.png' and path.is_relative_to(workspace/'project'):
                asset=path.relative_to(workspace/'project').as_posix();registry=workspace/'.workbench/figures/registry.json'
                entries=json.loads(registry.read_text()) if registry.exists() else {};entry=entries.get(asset,{'id':uuid.uuid4().hex,'revision':0})
                folder=workspace/'.workbench/figures'/entry['id'];folder.mkdir(parents=True,exist_ok=True)
                describe(figure)
                try:data=pickle.dumps(figure,protocol=pickle.HIGHEST_PROTOCOL)
                except (AttributeError,pickle.PicklingError):
                    import cloudpickle
                    data=cloudpickle.dumps(figure,protocol=pickle.HIGHEST_PROTOCOL)
                if not (folder/'source.pkl').exists():(folder/'source.pkl').write_bytes(data)
                (folder/'current.pkl').write_bytes(data)
                program=plot_program or entry.get('plot_program','')
                if not program:
                    candidate=Path(sys.argv[0]).resolve()
                    if candidate.is_relative_to(workspace/'project'):program=candidate.relative_to(workspace/'project').as_posix()
                from datetime import datetime,timezone
                entry.update(asset=asset,revision=entry['revision']+1,matplotlib=matplotlib.__version__,plot_program=program,
                  compute_program=compute_program or entry.get('compute_program',''),updated=datetime.now(timezone.utc).isoformat(),bound_modified=path.stat().st_mtime_ns,image_digest=hashlib.sha256(path.read_bytes()).hexdigest())
                entries[asset]=entry;registry.parent.mkdir(parents=True,exist_ok=True)
                pending=registry.with_suffix('.pending');pending.write_text(json.dumps(entries,ensure_ascii=False),encoding='utf8');pending.replace(registry)
        return result
    Figure.savefig=save
