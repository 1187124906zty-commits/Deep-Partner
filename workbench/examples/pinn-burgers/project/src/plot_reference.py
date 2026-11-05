"""Visualize the authors' supplied Burgers reference data; no PINN training."""
from pathlib import Path
import json
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
data=loadmat(root/'data/burgers_shock.mat')
x=data['x'].ravel();t=data['t'].ravel();u=np.real(data['usol'])
assert u.shape==(len(x),len(t)) and np.isfinite(u).all()
initial_error=float(np.max(np.abs(u[:,0]+np.sin(np.pi*x))))
assert initial_error<1e-8
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained',gridspec_kw={'width_ratios':[1.15,1]})
image=axes[0].pcolormesh(t,x,u,cmap='RdBu_r',vmin=-1,vmax=1,rasterized=True,shading='auto')
fig.colorbar(image,ax=axes[0],label='$u(x,t)$',pad=.025)
axes[0].set(xlabel='$t$',ylabel='$x$',title='(a) Supplied reference solution')
for moment,color in zip([.0,.25,.5,.75],['#3a6c87','#6a9767','#c89952','#ae5c62']):
 i=int(np.argmin(abs(t-moment)));axes[1].plot(x,u[:,i],color=color,lw=1.7,label=f'$t={t[i]:.2f}$')
axes[1].set(xlabel='$x$',ylabel='$u(x,t)$',title='(b) Time slices',xlim=(-1,1),ylim=(-1.1,1.1));axes[1].legend(frameon=False,ncol=2,fontsize=8);axes[1].grid(alpha=.13)
out=root/'results';out.mkdir(exist_ok=True)
fig.savefig(out/'burgers-reference.png');fig.savefig(out/'burgers-reference.pdf');plt.close(fig)
report={'scope':'Visualization of the authors supplied reference data; not a trained PINN prediction.','shape':list(u.shape),'x_range':[float(x.min()),float(x.max())],'t_range':[float(t.min()),float(t.max())],'initial_max_error':initial_error,'u_range':[float(u.min()),float(u.max())],'all_finite':True,'figure':'results/burgers-reference.png','plot_program':'src/plot_reference.py','compute_program':'src/Burgers.py'}
(out/'reference-summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
