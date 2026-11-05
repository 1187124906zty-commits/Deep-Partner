"""Repair the observed first-binding 403 without changing native visibility rules."""
from pathlib import Path


def main():
    path=Path('/srv/research-workbench/source/server/app.py')
    before=path.read_text()
    old="visible=await call(request,'GET','/api/knowledge-bases?resource_library=true&dt_workspace='+quote(project['native_id']))"
    new=("# Bind from the authenticated account library; a workspace-filtered list only contains already-bound resources.\n"
         "        visible=await call(request,'GET','/api/knowledge-bases?resource_library=true')")
    if new in before:
        print('Current binding scope already correct');return
    if before.count(old)!=1:raise RuntimeError('Project binding code changed; inspect before applying the repair')
    path.write_text(before.replace(old,new,1))
    print('Binding reads the authenticated account resource library; native registration still validates resource access')


if __name__=='__main__':main()
