"""Visualize the current NeuralOperator repository's packaged Darcy test data."""
from pathlib import Path
import json
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
data=torch.load(root/'data/darcy_test_16.pt',map_location='cpu',weights_only=True)
a=data['x'].detach().numpy();u=data['y'].detach().numpy()
print('Stored tensors',a.shape,u.shape,str(a.dtype),str(u.dtype),flush=True)
assert a.shape==u.shape and np.isfinite(a).all() and np.isfinite(u).all()
assert a.dtype==np.bool_ or np.min(a)>0
sample_a=np.squeeze(a[0]);sample_u=np.squeeze(u[0])
assert sample_a.ndim==sample_u.ndim==2
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
fig,axes=plt.subplots(1,2,figsize=(9.8,3.8),layout='constrained')
for ax,array,cmap,label,title in zip(axes,[sample_a,sample_u],['YlGnBu','viridis'],['Stored binary input','Reference $u$'],['(a) Stored coefficient encoding','(b) Supplied solution field']):
 image=ax.imshow(array.T,origin='lower',extent=(0,1,0,1),cmap=cmap,interpolation='nearest');fig.colorbar(image,ax=ax,label=label,pad=.025);ax.set(xlabel='$x_1$',ylabel='$x_2$',title=title)
out=root/'results';out.mkdir(exist_ok=True)
fig.savefig(out/'darcy-reference.png');fig.savefig(out/'darcy-reference.pdf');plt.close(fig)
report={'scope':'Current NeuralOperator packaged reference dataset, first test sample; no FNO training or performance reproduction claimed.','shape':list(a.shape),'a_range':[float(a.min()),float(a.max())],'u_range':[float(u.min()),float(u.max())],'all_finite':True,'figure':'results/darcy-reference.png','plot_program':'src/plot_reference.py','compute_program':'src/plot_FNO_darcy.py','paper_basis':'FNO 2010.08895, Appendix A.3.2. This small current package is not asserted identical to the full original 421x421 benchmark.'}
report.update(input_encoding='torch.bool phase map (0/1); not a raw permeability field. No physical-value mapping reconstructed.')
(out/'reference-summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
