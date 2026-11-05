"""Shared typography must stay shared after saving and rerunning a plot."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from server.figure_artists import apply_changes,artists
from server.figures import merge_styles

fig,ax=plt.subplots();ax.plot([0,1],[0,1]);ax.set(title='Title',xlabel='Time',ylabel='Value')
old={'figure':{'font_size':10,'title_size':16},'objects':{'ax0-title':{'font_size':18,'color':'#bb2200'},'ax0-line0':{'color':'#116699'}}}
new={'figure':{'font_size':12,'text_color':'#222222'},'objects':{}}
merged=merge_styles(old,new,artists(fig));apply_changes(fig,old);apply_changes(fig,new)
assert fig._workbench_typography.get('title_size') is None
assert 'title_size' not in merged['figure'] and 'font_size' not in merged['objects']['ax0-title']
assert 'color' not in merged['objects']['ax0-title'] and merged['objects']['ax0-line0']['color']=='#116699'
apply_changes(fig,merged);assert ax.title.get_fontsize()==ax.xaxis.label.get_fontsize()==12
explicit=merge_styles(old,{'figure':{'font_size':12},'objects':{'ax0-title':{'font_size':15}}},artists(fig));apply_changes(fig,explicit)
assert ax.title.get_fontsize()==15 and ax.xaxis.label.get_fontsize()==12
roles=merge_styles(old,{'figure':{'title_size':14},'objects':{}},artists(fig));apply_changes(fig,roles)
assert ax.title.get_fontsize()==14
plt.close(fig)
print('{"passed":6,"scientific_data_changed":false}')
