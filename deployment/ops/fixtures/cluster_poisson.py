"""Workflow acceptance: dimensionless Poisson equation on the unit square.

-Delta u = 2*pi^2*sin(pi*x)*sin(pi*y), homogeneous Dirichlet boundary.
Exact solution sin(pi*x)*sin(pi*y); this checks the declared theoretical case.
"""
from pathlib import Path
import json,os
import numpy as np
from skfem import MeshTri,ElementTriP1,Basis,asm,solve,condense,LinearForm
from skfem.models.poisson import laplace

if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Run the simulation through Slurm')
root=Path('results');root.mkdir(exist_ok=True)
@LinearForm
def load(v,w):return 2*np.pi**2*np.sin(np.pi*w.x[0])*np.sin(np.pi*w.x[1])*v

mesh=MeshTri().refined(4);basis=Basis(mesh,ElementTriP1());matrix=asm(laplace,basis);rhs=asm(load,basis)
boundary=basis.get_dofs().all();interior=basis.complement_dofs(boundary)
u=solve(*condense(matrix,rhs,D=boundary));exact=np.sin(np.pi*mesh.p[0])*np.sin(np.pi*mesh.p[1])
np.savez_compressed(root/'poisson.npz',coordinates=mesh.p,triangles=mesh.t,u=u,exact=exact)
summary={'solver':'scikit-fem P1 FEM','job_id':os.environ['SLURM_JOB_ID'],'host':os.uname().nodename,
         'dimensionless':True,'vertices':int(mesh.nvertices),'finite':bool(np.isfinite(u).all()),
         'max_nodal_error':float(np.max(np.abs(u-exact))),
         'interior_residual_inf':float(np.max(np.abs((matrix@u-rhs)[interior]))),
         'boundary_error_inf':float(np.max(np.abs(u[boundary]))),
         'reference':'manufactured exact solution, not experimental validation'}
(root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary))
