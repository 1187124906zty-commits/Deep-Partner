"""Install the reviewed account budgets and device isolation into the current workbench."""
from pathlib import Path
import shutil

ROOT=Path('/srv/dify-research')
SOURCE=ROOT/'tenant-storage/server'
TARGET=Path('/srv/research-workbench/source/server')


def main():
    for name in ('workspace_files.py','download_bridge.py'):
        current=(TARGET/name).read_bytes();baseline=(ROOT/'staging/tenant-baseline'/name).read_bytes()
        if current not in (baseline,(SOURCE/name).read_bytes()):
            raise RuntimeError('Workbench changed since review; merge before installing '+name)
    for name in ('account_policy.py','workspace_files.py','download_bridge.py'):
        shutil.copyfile(SOURCE/name,TARGET/name)
    path=TARGET/'app.py';text=path.read_text()
    install="\nfrom .account_policy import install as install_account_policy\ninstall_account_policy(app,store,actor)\n"
    text=text.replace(install,'')
    marker="app=FastAPI(title='Research Workbench',version='0.1.0',lifespan=lifespan)"
    if text.count(marker)!=1:raise RuntimeError('App initialization changed; inspect the route order')
    path.write_text(text.replace(marker,marker+'\n'+install,1))
    print('Installed versioned workbench quota and owner-scoped revocable download device support; no data moved')


if __name__=='__main__':main()
