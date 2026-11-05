"""Create a dedicated service identity; never import workstation private keys."""
from pathlib import Path
import os
import subprocess

root=Path('/srv/deeptutor/coder-home/.ssh')
root.mkdir(exist_ok=True,mode=0o700)
key=root/'cluster_ed25519'
if not key.exists():
    subprocess.run(['ssh-keygen','-t','ed25519','-N','','-C','deeptutor-coder@zty123.me','-f',str(key)],check=True,stdout=subprocess.DEVNULL)
known=root/'known_hosts'
known.write_text('''[xh5.hpccube.com]:65061 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF+ThZGQ3zJE7FdVxHHSCYT0GTZD+HfkyYzbMjwSKwcA
[xh5.hpccube.com]:65061 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBMNkV9dUeJaw3LpBWucbdkUhxWzaDb8h4lEN2aMGyFjP4rc3aOV//Q31aaFGlnjOeUArAvZ6J+dE8lg3WcPY6o8=
''')
config=root/'config'
config.write_text('''Host research-cluster-xh5
    HostName xh5.hpccube.com
    Port 65061
    User cluster_user
    IdentityFile /home/coder/.ssh/cluster_ed25519
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
    UserKnownHostsFile /home/coder/.ssh/known_hosts
    ConnectTimeout 15
    ServerAliveInterval 30
    ServerAliveCountMax 3
''')
for path in root.iterdir():
    os.chown(path,1000,1000);os.chmod(path,0o600)
os.chown(root,1000,1000);os.chmod(root,0o700)
print(key.with_suffix('.pub').read_text().strip())
