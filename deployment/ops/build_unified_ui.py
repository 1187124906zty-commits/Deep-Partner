"""Build the shared, bundled research UI using the existing Slurm/Node runtime."""
from pathlib import Path
import argparse
import json
import subprocess
import shutil
import shlex
from concurrent.futures import ThreadPoolExecutor,as_completed
import tarfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/Development/research-workbench')
REMOTE = '/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench'
CANONICAL = '/work/home/cluster_user/research-projects/deeptutor-integration/frontend/src/web'
REPORT = ROOT / 'reports/unified-ui-build.json'


def ssh(command, timeout=40):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'IPQoS=none', '-o', 'ConnectTimeout=12',
                             'research-cluster-xh5', command], capture_output=True,
                            text=True, encoding='utf8', timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:] or result.stdout[-3000:])
    return result.stdout.strip()


def scp(local, remote):
    incoming=remote+'.upload'
    subprocess.run(['scp', '-q', '-o', 'IPQoS=none', str(local), 'research-cluster-xh5:' + incoming],
                   check=True, timeout=600)
    assert int(ssh('stat -c %s -- '+shlex.quote(incoming)))==Path(local).stat().st_size
    ssh('mv -- '+shlex.quote(incoming)+' '+shlex.quote(remote))


def submit(preview=False):
    cache = ROOT / '.local/unified-build'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'source.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for folder in ['unified-ui', 'web/src']:
            for path in (SOURCE / folder).rglob('*'):
                if path.is_file() and not any(part in ('node_modules', 'dist', '__pycache__', '.git')
                                              for part in path.parts):
                    bundle.add(path, arcname=str(path.relative_to(SOURCE)).replace('\\', '/'))
        bundle.add(SOURCE/'web/vite.config.ts',arcname='web/vite.config.ts')
        bundle.add(SOURCE/'web/package.json',arcname='web/package.json')
    scp(archive, REMOTE + '/unified-source.tar.gz')
    inner = textwrap.dedent(f'''\
        #!/bin/bash
        set -euo pipefail
        root={REMOTE}
        exec 9>"$root/unified-build.lock"
        flock 9
        export PATH=/work/home/cluster_user/.pi-desktop/pi-host/current/bin:$PATH
        export TMPDIR="$root/tmp"
        export NODE_OPTIONS=--max-old-space-size=4096
        export npm_config_cache=/work/home/cluster_user/research-projects/deeptutor-integration/frontend/npm-cache
        export DEEPTUTOR_WEB_SOURCE={CANONICAL}
        export WORKBENCH_WEB_SOURCE="$root/src/web"
        cd "$root/src"
        tar -xzf "$root/unified-source.tar.gz"
        python3 - <<'PY'
        import json
        from pathlib import Path
        package=json.loads(Path('unified-ui/package.json').read_text())
        names=['@assistant-ui/react','@tanstack/react-table','@radix-ui/react-dropdown-menu','@radix-ui/react-slot','class-variance-authority']
        dependencies={{name:package['dependencies'][name] for name in names}}
        dependencies.update({{name:package['dependencies'][name] for name in ['react','react-dom']}})
        target=Path('../interaction-deps');target.mkdir(exist_ok=True)
        wanted=json.dumps({{'private':True,'dependencies':dependencies}},sort_keys=True)
        manifest=target/'package.json'
        if not manifest.exists() or manifest.read_text()!=wanted:manifest.write_text(wanted)
        PY
        test -f "$root/interaction-deps/node_modules/@assistant-ui/react/package.json" || {{ echo "Stage the pinned interaction dependencies before building"; exit 1; }}
        python3 - <<'PY'
        from pathlib import Path
        import json,shutil
        origin=Path('../interaction-deps/node_modules').resolve()
        canonical=Path('{CANONICAL}/node_modules')
        # These trees are generated dependency caches. A React peer must resolve
        # to the same physical package in externalized tests as in the bundle.
        for modules in [origin,Path('web/node_modules').resolve()]:
          for name in ['react','react-dom']:
            destination=modules/name
            source=canonical/name
            if destination.resolve()==source.resolve():continue
            assert modules.name=='node_modules' and name in ['react','react-dom']
            if destination.exists():
              assert json.loads((source/'package.json').read_text())['version']==json.loads(Path('unified-ui/package.json').read_text())['dependencies'][name],'Canonical React differs from declared runtime'
              assert json.loads((destination/'package.json').read_text())['version'] in ['19.0.0','19.2.3'],'Unexpected cached React version'
              if destination.is_symlink():destination.unlink()
              else:shutil.rmtree(destination)
            destination.symlink_to(source,target_is_directory=True)
        for target in [Path('unified-ui/node_modules'),Path('web/node_modules')]:
          target.mkdir(exist_ok=True)
          for package in origin.iterdir():
            if package.name.startswith('.'):continue
            if package.name.startswith('@'):
              scope=target/package.name;scope.mkdir(exist_ok=True)
              pairs=[(p,scope/p.name) for p in package.iterdir()]
            else:pairs=[(package,target/package.name)]
            for source,destination in pairs:
              if not destination.exists():destination.symlink_to(source,target_is_directory=True)
        for name in ['tailwind-merge','clsx']:
          destination=Path('web/node_modules')/name
          if not destination.exists():destination.symlink_to(canonical/name,target_is_directory=True)
        PY
        if [ -f web/src/paper-content-map.test.tsx ]; then
          cd web
          node node_modules/vitest/vitest.mjs run src/paper-content-map-data.test.ts src/paper-content-map.test.tsx src/library-content-map.test.tsx --maxWorkers=1 --minWorkers=1 --pool=forks
          cd ..
        fi
        cd unified-ui
        python3 - <<'PY'
        import json
        from pathlib import Path
        target=Path('node_modules');target.mkdir(exist_ok=True)
        canonical=Path('{CANONICAL}/node_modules')
        workbench=Path('{REMOTE}/src/web/node_modules')
        for origin in [canonical,workbench]:
          for package in origin.iterdir():
            if package.name.startswith('.'):
              continue
            if package.name.startswith('@'):
              scope=target/package.name;scope.mkdir(exist_ok=True)
              pairs=[(child,scope/child.name) for child in package.iterdir()]
            else:
              pairs=[(package,target/package.name)]
            for source,destination in pairs:
              if not destination.exists():destination.symlink_to(source,target_is_directory=True)
          binary_target=target/'.bin';binary_target.mkdir(exist_ok=True)
          for command in (origin/'.bin').iterdir():
            destination=binary_target/command.name
            if not destination.exists():destination.symlink_to(command.resolve())
        inventory={{}}
        for name in json.loads(Path('package.json').read_text()).get('dependencies',{{}}):
          metadata=target/name/'package.json'
          if metadata.is_file():inventory[name]=json.loads(metadata.read_text())['version']
        Path('dependency-inventory.json').write_text(json.dumps(inventory,indent=2))
        print('Reused existing dependency packages:',len(inventory),flush=True)
        PY
        if [ -f scripts/typecheck.mjs ]; then
          node scripts/typecheck.mjs
        fi
        node /work/home/cluster_user/research-projects/deeptutor-integration/frontend/tools/npm/bin/npm-cli.js run build
        if [ -f node_modules/vitest/vitest.mjs ]; then
          node node_modules/vitest/vitest.mjs run --passWithNoTests --maxWorkers=1 --pool=threads
        fi
        test -s dist/index.html
        python3 - <<'PY'
        import json,os
        from pathlib import Path
        Path('dist/build-info.json').write_text(json.dumps({{'product':'DeepPartner','version':'0.4.2','slurm_job_id':os.environ.get('SLURM_JOB_ID')}}))
        PY
        tar -czf "$root/artifacts/unified-ui-runtime.tar.gz" -C dist .
        cp dependency-inventory.json "$root/artifacts/unified-ui-dependency-inventory.json"
        echo UNIFIED_UI_BUILD_PASSED
        ''')
    if preview:
        review='''mkdir -p "$root/tmp/paper-map-preview"
tar -xzf "$root/paper-map-review-source.tar.gz" -C "$root/tmp/paper-map-preview"
node "$root/tmp/paper-map-preview/build.mjs"
'''
        inner=inner.replace('test -s dist/index.html','test -s dist/index.html\n'+review)
    batch = textwrap.dedent(f'''\
        #!/bin/bash
        #SBATCH --job-name=deep-partner-ui
        #SBATCH --partition=xhacnormalb
        #SBATCH --account=cluster_user
        #SBATCH --qos=user_cluster_user
        #SBATCH --nodes=1
        #SBATCH --ntasks=1
        #SBATCH --cpus-per-task=2
        #SBATCH --mem=6G
        #SBATCH --time=00:15:00
        #SBATCH --output={REMOTE}/logs/unified-ui-%j.log
        set -euo pipefail
        module purge
        module load apps/apptainer/1.3.4
        export APPTAINERENV_SLURM_JOB_ID="$SLURM_JOB_ID"
        apptainer exec --writable --cleanenv --bind /work --home /work/home/cluster_user:/work/home/cluster_user /work/home/cluster_user/opensource/openpaso/containers/python-runtime /bin/bash {REMOTE}/run-unified-build.sh
        ''')
    for name, value in [('run-unified-build.sh', inner), ('unified-build.sbatch', batch)]:
        path = cache / name
        path.write_text(value, encoding='utf8', newline='\n')
        scp(path, REMOTE + '/' + name)
    job = ssh('sbatch --parsable ' + REMOTE + '/unified-build.sbatch').split(';')[0]
    report = {'job_id': job, 'state': 'submitted', 'connection': 'research-cluster-xh5',
              'canonical_source': CANONICAL, 'source_root': REMOTE + '/src/unified-ui',
              'log': REMOTE + '/logs/unified-ui-' + job + '.log',
              'artifact': REMOTE + '/artifacts/unified-ui-runtime.tar.gz',
              'local_source': str(SOURCE / 'unified-ui')}
    if preview:report['paper_map_review_artifact']=REMOTE+'/artifacts/paper-map-review.html'
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False))


def status():
    report = json.loads(REPORT.read_text(encoding='utf8'))
    state=ssh('sacct -j ' + report['job_id'] + ' --format=JobID,State,ExitCode,Elapsed --noheader')
    print(state)
    if 'PENDING' not in state:print(ssh('tail -28 ' + report['log']))


def fetch():
    report = json.loads(REPORT.read_text(encoding='utf8'))
    state = ssh('sacct -j ' + report['job_id'] + ' --format=State,ExitCode --noheader -X --parsable2')
    if 'COMPLETED|0:0' not in state:
        raise RuntimeError('Build has not succeeded: ' + state)
    target = ROOT / '.local/unified-build/runtime.tar.gz'
    # The observed connection became too slow for one bounded SFTP transfer.
    # Keep completed 1 MiB ranges from a job-specific artifact and resume them.
    assert report['artifact']==REMOTE+'/artifacts/unified-ui-runtime.tar.gz'
    versioned=REMOTE+'/artifacts/unified-ui-runtime-'+report['job_id']+'.tar.gz'
    size=ssh('if test -f '+shlex.quote(versioned)+'; then stat -c %s -- '+shlex.quote(versioned)+'; else echo MISSING; fi')
    if size=='MISSING':
        source_info=json.loads(ssh('tar -xOf '+shlex.quote(report['artifact'])+' ./build-info.json'))
        assert source_info['slurm_job_id']==report['job_id']
        ssh('cp -- '+shlex.quote(report['artifact'])+' '+shlex.quote(versioned))
        size=ssh('stat -c %s -- '+shlex.quote(versioned))
    manifest={'bytes':int(size)}
    part_root=ROOT/'.local/unified-build'/('parts-'+report['job_id']);part_root.mkdir(exist_ok=True)
    block=1024*1024;count=(manifest['bytes']+block-1)//block
    def receive(index):
        path=part_root/(str(index)+'.bin');expected=min(block,manifest['bytes']-index*block)
        if path.is_file() and path.stat().st_size==expected:return path
        temporary=path.with_suffix('.part')
        with temporary.open('wb') as output:
            subprocess.run(['ssh','-T','-o','BatchMode=yes','-o','IPQoS=none','research-cluster-xh5',
                            'dd if='+shlex.quote(versioned)+' bs=1048576 skip='+str(index)+' count=1 status=none'],
                           stdout=output,stderr=subprocess.PIPE,check=True,timeout=180)
        assert temporary.stat().st_size==expected,'Incomplete build range '+str(index)
        temporary.replace(path);print('Received build range '+str(index+1)+'/'+str(count),flush=True);return path
    with ThreadPoolExecutor(max_workers=3) as transfer:
        for future in as_completed([transfer.submit(receive,index) for index in range(count)]):future.result()
    with target.open('wb') as output:
        for index in range(count):
            with (part_root/(str(index)+'.bin')).open('rb') as incoming:shutil.copyfileobj(incoming,output)
    assert target.stat().st_size==manifest['bytes']
    output = SOURCE / 'unified-ui/dist'
    assert output.resolve().parent == (SOURCE / 'unified-ui').resolve() and output.name == 'dist'
    if output.is_dir():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target) as bundle:
        for member in bundle.getmembers():
            if not (output / member.name).resolve().is_relative_to(output.resolve()):
                raise ValueError('Invalid build path')
        bundle.extractall(output, filter='data')
    info_path = output / 'build-info.json'
    info = json.loads(info_path.read_text()) if info_path.is_file() else {'product': 'DeepPartner', 'version': '0.4.2'}
    assert info.get('slurm_job_id') in (None,report['job_id']), 'Received another build artifact'
    if info.get('slurm_job_id') is None:
        # Older cleanenv builds omitted the scheduler variable inside Apptainer.
        # Bind the received artifact to the completed job observed above.
        info.update({'slurm_job_id': report['job_id'], 'job_id_source': 'verified_sacct_fetch'})
        info_path.write_text(json.dumps(info), encoding='utf8')
        with tarfile.open(target, 'w:gz') as bundle:
            for path in output.rglob('*'):
                if path.is_file():
                    bundle.add(path, arcname=path.relative_to(output).as_posix())
    subprocess.run(['scp', '-q', '-o', 'IPQoS=none', 'research-cluster-xh5:' + REMOTE + '/artifacts/unified-ui-dependency-inventory.json',
                    str(SOURCE / 'unified-ui/dependency-inventory.json')], check=True, timeout=90)
    subprocess.run(['scp', '-q', '-o', 'IPQoS=none', 'research-cluster-xh5:' + REMOTE + '/src/unified-ui/upstream-type-diagnostics.txt',
                    str(SOURCE / 'unified-ui/upstream-type-diagnostics.txt')], check=True, timeout=90)
    subprocess.run(['scp', '-q', '-o', 'IPQoS=none', 'research-cluster-xh5:' + report['log'],
                    str(ROOT / ('reports/unified-ui-build-' + report['job_id'] + '.log'))], check=True, timeout=90)
    report.update({'state': 'COMPLETED', 'exit_code': '0:0', 'local_artifact': str(target),
                   'local_dist': str(output)})
    if report.get('paper_map_review_artifact'):
        preview_target=ROOT/'reports/氯硫框架具体化/paper-maps-20261104/Qin引言_内容画布试读.html'
        subprocess.run(['scp','-q','research-cluster-xh5:'+report['paper_map_review_artifact'],str(preview_target)],check=True,timeout=90)
        report['paper_map_review_local']=str(preview_target)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['submit', 'status', 'fetch'])
    parser.add_argument('--paper-map-review',action='store_true')
    args = parser.parse_args()
    {'submit': lambda:submit(args.paper_map_review), 'status': status, 'fetch': fetch}[args.action]()
