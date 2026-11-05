"""Regressions for actual subplot cells and clipped selection geometry."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from server.figure_artists import layout_description, describe, apply_layout, artists, apply_changes

failures=[]
def check(value,message):
    if not value:failures.append(message)

fig,axes=plt.subplots(2,2,figsize=(8,6))
layout=layout_description(fig)
check((layout['rows'],layout['cols'])==(2,2),'A 2 by 2 GridSpec must produce 2 by 2 cells')
for key,cell in layout['cells'].items():
    check(cell['x']+cell['width']<=1+1e-7 and cell['y']+cell['height']<=1+1e-7,'Subplot '+key+' crosses its assigned cell')
plt.close(fig)
fig=plt.figure(figsize=(8,6));grid=fig.add_gridspec(2,2)
fig.add_subplot(grid[0,:]);fig.add_subplot(grid[1,0]);fig.add_subplot(grid[1,1])
layout=layout_description(fig)
check(layout['cells']['axes-0'].get('colspan')==2,'A spanning subplot must retain its actual GridSpec span')
before=[a.get_position().bounds for a in fig.axes]
apply_layout(fig,layout)
check(all(all(abs(a-b)<1e-7 for a,b in zip(before[i],ax.get_position().bounds)) for i,ax in enumerate(fig.axes)),'Unchanged layout must preserve positions of spanning subplots')
plt.close(fig)
fig=plt.figure(figsize=(8,6));fig.add_axes([.08,.60,.40,.30]);fig.add_axes([.57,.60,.35,.30]);fig.add_axes([.08,.10,.40,.30]);fig.add_axes([.57,.10,.35,.30])
before=[a.get_position().bounds for a in fig.axes];layout=layout_description(fig)
check(before==[a.get_position().bounds for a in fig.axes],'Inspecting layout must not rearrange authored axes')
for key,cell in layout['cells'].items():
    check(cell['x']+cell['width']<=1+1e-7 and cell['y']+cell['height']<=1+1e-7,'Manual subplot '+key+' crosses its assigned cell')
fig.text(-.1,1.08,'An annotation outside the exported canvas')
for obj in describe(fig):
    x,y,w,h=obj['bounds']
    check(x>=0 and y>=0 and x+w<=1+1e-7 and y+h<=1+1e-7,'Selection '+obj['id']+' extends beyond the canvas')
plt.close(fig)
fig=plt.figure(figsize=(8,6));large=fig.add_axes([.06,.12,.4,.7]);small=fig.add_axes([.1,.2,.12,.2]);right=fig.add_axes([.56,.12,.4,.7])
layout=layout_description(fig)
check(len(layout['cells'])==2 and layout['nested'].get('axes-1',{}).get('parent')=='axes-0','Inset axes belong to their parent instead of cutting its cell')
before=[a.get_position().bounds for a in fig.axes];apply_layout(fig,layout)
check(all(all(abs(x-y)<1e-7 for x,y in zip(before[i],ax.get_position().bounds)) for i,ax in enumerate(fig.axes)),'Inspect and unchanged layout preserve inset geometry')
plt.close(fig)
fig=plt.figure(figsize=(8,6))
for row,count in [(0,3),(1,4)]:
    for col in range(count):fig.add_axes([.05+col*.9/count,.58 if row==0 else .1,.75/count,.28])
layout=layout_description(fig)
check((layout['rows'],layout['cols'])==(2,4) and len(layout['cells'])==7,'Rows with three and four authored subplots retain seven actual cells')
check(all(cell['x']>=0 and cell['x']+cell['width']<=1+1e-7 for cell in layout['cells'].values()),'Unequal row layouts must not be cut by invented global columns')
plt.close(fig)
fig,ax=plt.subplots();ax.plot([0,1],[2,3]);ax.set(xlabel='x',ylabel='y',title='Title');ax.legend(['Curve'])
from matplotlib.cm import ScalarMappable
colorax=fig.add_axes([.2,.02,.6,.03]);fig.colorbar(ScalarMappable(cmap='viridis'),cax=colorax,orientation='horizontal')
check(sum(e['kind']=='axes' for e in artists(fig).values())==1,'A detached scalar-mappable colorbar must not become another subplot')
apply_changes(fig,{'figure':{'font_family':'DejaVu Sans','font_size':12,'title_size':16},'objects':{'axes-0':{'x_label':'Time','y_label':'Humidity','axis_color':'#2764a4','spines':{'top':False,'right':False}}}})
check(ax.get_xlabel()=='Time' and ax.get_ylabel()=='Humidity','Axis group must update both direction titles')
check(ax.xaxis.label.get_fontsize()==12 and ax.yaxis.label.get_fontsize()==12 and ax.title.get_fontsize()==16,'Global typography applies to axis labels while preserving the selected title hierarchy')
check(not ax.spines['top'].get_visible() and not ax.spines['right'].get_visible(),'Axis group controls optional top and right spines without extra selection objects')
check(list(ax.lines[0].get_ydata())==[2,3],'Changing axis and font styles must not alter numerical data')
plt.close(fig)
report={'passed':not failures,'failures':failures}
print(json.dumps(report,ensure_ascii=False))
assert not failures,'; '.join(failures)
