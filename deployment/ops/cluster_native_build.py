"""Build and package the Windows application in the existing Slurm project."""
from pathlib import Path
import argparse,hashlib,json,shlex,shutil,subprocess,sys,tarfile,textwrap
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1]
LOCAL=Path('D:/Development/电脑答疑/deeptutor-desktop')
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration/desktop'
PARENT='/work/home/cluster_user/research-projects/deeptutor-integration'
CONTAINER='/work/home/cluster_user/opensource/openpaso/containers/fourc-runtime'
REPORT=ROOT/'reports/cluster-native-build.json'


def ssh(command,timeout=60):
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','research-cluster-xh5',command],capture_output=True,text=True,encoding='utf8',timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr[-3000:]+result.stdout[-3000:])
    return result.stdout.strip()


def send(path,target):
    subprocess.run(['scp','-q',str(path),'research-cluster-xh5:'+target],check=True,timeout=180)


def submit():
    ssh('test -s '+REMOTE+'/cache/xwin/xwin/crt/lib/x86_64/msvcrt.lib && test -s '+REMOTE+'/cache/xwin/xwin/sdk/lib/ucrt/x86_64/ucrt.lib && test -s '+REMOTE+'/cache/xwin/xwin/sdk/include/ucrt/stdio.h')
    ssh('mkdir -p '+REMOTE+'/{source,tools,cache,target,logs,artifacts,jobs,tmp}')
    stage=ROOT/'.local/cluster-native';stage.mkdir(exist_ok=True)
    archive=stage/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in ['src','assets','icons','scripts','licenses','gen','tests','Cargo.toml','Cargo.lock','build.rs','tauri.conf.json']:
            path=LOCAL/name
            if path.is_file():tar.add(path,arcname=name)
            else:
                for file in path.rglob('*'):
                    if file.is_file() and '__pycache__' not in file.parts:tar.add(file,arcname=file.relative_to(LOCAL))
    send(archive,REMOTE+'/source.tar.gz')
    script=textwrap.dedent(r'''
    #!/bin/bash
    set -euo pipefail
    root=REMOTE_ROOT
    exec 9>"$root/native-build.lock"
    flock 9
    export CARGO_HOME="$root/tools/cargo"
    export RUSTUP_HOME="$root/tools/rustup"
    export XWIN_CACHE_DIR="$root/cache/xwin"
    export CARGO_TARGET_DIR="$root/target"
    export CARGO_INCREMENTAL=0
    export CARGO_BUILD_JOBS=8
    export TMPDIR="$root/tmp"
    export LANG=C.UTF-8 LC_ALL=C.UTF-8
    export PYTHONPATH="$root/tools/python"
    export PATH="$root/tools/cargo/bin:$root/tools/python/bin:$root/tools/sysroot/usr/lib/llvm-18/bin:$root/tools/sysroot/usr/bin:/usr/bin:/bin"
    export LD_LIBRARY_PATH="$root/tools/sysroot/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
    cd "$root"
    tar -xzf source.tar.gz -C source
    mkdir -p source/ui-dist
    tar -xzf PARENT_ROOT/research-workbench/artifacts/unified-ui-runtime.tar.gz -C source/ui-dist
    test -x "$root/tools/python/bin/cargo-xwin"
    test -x "$root/tools/sysroot/usr/lib/llvm-18/bin/clang"
    export NSISDIR="$root/tools/sysroot/usr/share/nsis"
    export RC=llvm-rc
    if ! command -v clang-cl >/dev/null; then ln -s "$root/tools/sysroot/usr/lib/llvm-18/bin/clang" "$root/tools/sysroot/usr/lib/llvm-18/bin/clang-cl"; fi
    sdk="$XWIN_CACHE_DIR/xwin"
    export TARGET_CC=clang-cl TARGET_CXX=clang-cl TARGET_AR=llvm-lib
    export CC_x86_64_pc_windows_msvc=clang-cl CXX_x86_64_pc_windows_msvc=clang-cl AR_x86_64_pc_windows_msvc=llvm-lib
    export CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=lld-link
    export CC_SHELL_ESCAPED_FLAGS=1
    export CFLAGS_x86_64_pc_windows_msvc="--target=x86_64-pc-windows-msvc -fuse-ld=lld-link /imsvc $sdk/crt/include /imsvc $sdk/sdk/include/ucrt /imsvc $sdk/sdk/include/um /imsvc $sdk/sdk/include/shared /imsvc $sdk/sdk/include/winrt"
    export CXXFLAGS_x86_64_pc_windows_msvc="$CFLAGS_x86_64_pc_windows_msvc /EHsc"
    export RCFLAGS="-I$sdk/crt/include -I$sdk/sdk/include/ucrt -I$sdk/sdk/include/um -I$sdk/sdk/include/shared -I$sdk/sdk/include/winrt"
    windows_sdk="$root/cache/windows-sdk-10.0.26100.0/um/x86_64"
    test -s "$windows_sdk/kernel32.lib"
    export LIB="$sdk/crt/lib/x86_64;$windows_sdk;$sdk/sdk/lib/um/x86_64;$sdk/sdk/lib/ucrt/x86_64"
    export RUSTFLAGS="-C linker-flavor=lld-link -Lnative=$sdk/crt/lib/x86_64 -Lnative=$windows_sdk -Lnative=$sdk/sdk/lib/um/x86_64 -Lnative=$sdk/sdk/lib/ucrt/x86_64"
    rustc --version
    cargo-xwin --version
    clang --version | head -1
    cd source
    cargo build --offline --locked --release --target x86_64-pc-windows-msvc --features desktop-web --bin deep-partner
    cargo build --offline --locked --release --target x86_64-pc-windows-msvc --no-default-features --bin dp
    cargo test --offline --locked --release --target x86_64-pc-windows-msvc --features desktop-web --lib --no-run --message-format=json > "$root/logs/test-binaries-$SLURM_JOB_ID.jsonl"
    mkdir -p "$root/artifacts/$SLURM_JOB_ID" dist target/release
    cp "$root/target/x86_64-pc-windows-msvc/release/deep-partner.exe" target/release/
    cp "$root/target/x86_64-pc-windows-msvc/release/dp.exe" target/release/
    cp target/release/deep-partner.exe "$root/artifacts/$SLURM_JOB_ID/Deep partner.exe"
    cp target/release/dp.exe "$root/artifacts/$SLURM_JOB_ID/dp.exe"
    python3 - <<'PY'
    from pathlib import Path
    import re
    text=Path('scripts/package-native.ps1').read_text(encoding='utf8')
    guide=Path('assets/usage-zh.txt').read_text(encoding='utf8')
    Path('dist/使用说明.txt').write_text(guide,encoding='utf8')
    # Unix makensis accepts native paths in the same custom installer script.
    script=Path('scripts/installer.nsi').read_text(encoding='utf8')
    Path('scripts/installer-cluster.nsi').write_text(script,encoding='utf8')
    PY
    makensis -V2 -WX -INPUTCHARSET UTF8 -DAPP_ROOT="$PWD" scripts/installer-cluster.nsi
    cp "dist/Deep partner Setup.exe" "$root/artifacts/$SLURM_JOB_ID/"
    cp dist/使用说明.txt "$root/artifacts/$SLURM_JOB_ID/"
    python3 - <<'PY'
    from pathlib import Path
    import json,os,shutil
    root=Path(os.environ['CARGO_TARGET_DIR']).parent
    rows=[json.loads(line) for line in (root/'logs'/('test-binaries-'+os.environ['SLURM_JOB_ID']+'.jsonl')).read_text().splitlines()]
    tests=[r['executable'] for r in rows if r.get('reason')=='compiler-artifact' and r.get('profile',{}).get('test') and r.get('executable')]
    assert len(tests)==1,tests
    shutil.copyfile(tests[0],root/'artifacts'/os.environ['SLURM_JOB_ID']/'native-tests.exe')
    PY
    python3 - <<'PY'
    import hashlib,json,os
    from pathlib import Path
    root=Path(os.environ['CARGO_TARGET_DIR']).parent;out=root/'artifacts'/os.environ['SLURM_JOB_ID']
    report={'job_id':os.environ['SLURM_JOB_ID'],'frontend':json.loads(Path('ui-dist/build-info.json').read_text()),'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file()],'target':'x86_64-pc-windows-msvc','build_host':os.uname().nodename,'cargo_target_dir':str(root/'target')}
    (out/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False),flush=True)
    PY
    tar -czf "$root/artifacts/native-runtime-$SLURM_JOB_ID.tar.gz" -C "$root/artifacts/$SLURM_JOB_ID" .
    echo CLUSTER_NATIVE_BUILD_PASSED
    ''').lstrip('\n').replace('REMOTE_ROOT',REMOTE).replace('PARENT_ROOT',PARENT)
    batch=textwrap.dedent(f'''\
    #!/bin/bash
    #SBATCH --job-name=partner-windows
    #SBATCH --partition=xhacnormalb
    #SBATCH --account=cluster_user
    #SBATCH --qos=user_cluster_user
    #SBATCH --nodes=1
    #SBATCH --ntasks=1
    #SBATCH --cpus-per-task=8
    #SBATCH --mem=16G
    #SBATCH --time=01:00:00
    #SBATCH --output={REMOTE}/logs/native-%j.log
    set -euo pipefail
    module purge
    module load apps/apptainer/1.3.4
    export APPTAINERENV_SLURM_JOB_ID="$SLURM_JOB_ID"
    apptainer exec --writable --cleanenv --bind /work --home /work/home/cluster_user:/work/home/cluster_user {CONTAINER} /bin/bash {REMOTE}/jobs/build-native.sh
    ''')
    for name,content in [('build-native.sh',script),('build-native.sbatch',batch)]:
        path=stage/name;path.write_text(content,encoding='utf8',newline='\n');send(path,REMOTE+'/jobs/'+name)
    job=ssh('sbatch --parsable '+REMOTE+'/jobs/build-native.sbatch').split(';')[0]
    report={'job_id':job,'state':'submitted','remote_root':REMOTE,'log':REMOTE+'/logs/native-'+job+'.log','artifacts':REMOTE+'/artifacts/'+job,'local_build':False}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))


def status():
    report=json.loads(REPORT.read_text(encoding='utf8'))
    print(ssh('sacct -j '+report['job_id']+' --format=JobID,State,ExitCode,Elapsed --noheader'))
    print(ssh('if test -f '+report['log']+'; then tail -35 '+report['log']+'; fi'))


def package():
    previous=json.loads(REPORT.read_text(encoding='utf8'))
    compiled=previous.get('compiled_job_id',previous['job_id']);assert compiled.isdecimal()
    ssh('test -s '+REMOTE+'/logs/test-binaries-'+compiled+'.jsonl && test -s '+REMOTE+'/target/x86_64-pc-windows-msvc/release/deep-partner.exe')
    stage=ROOT/'.local/cluster-native'
    marker='mkdir -p "$root/artifacts/$SLURM_JOB_ID" dist target/release'
    body=marker+(stage/'build-native.sh').read_text(encoding='utf8').split(marker,1)[1]
    body=body.replace("'test-binaries-'+os.environ['SLURM_JOB_ID']","'test-binaries-'+os.environ['COMPILED_JOB_ID']")
    script=textwrap.dedent(f'''\
    #!/bin/bash
    set -euo pipefail
    root={REMOTE}
    exec 9>"$root/native-build.lock"
    flock 9
    export LANG=C.UTF-8 LC_ALL=C.UTF-8
    export PATH="$root/tools/sysroot/usr/bin:/usr/bin:/bin"
    export LD_LIBRARY_PATH="$root/tools/sysroot/usr/lib/x86_64-linux-gnu:${{LD_LIBRARY_PATH:-}}"
    export NSISDIR="$root/tools/sysroot/usr/share/nsis"
    export CARGO_TARGET_DIR="$root/target"
    export COMPILED_JOB_ID={compiled}
    cd "$root/source"
    ''')+body
    batch=(stage/'build-native.sbatch').read_text(encoding='utf8').replace('partner-windows','partner-package').replace('/jobs/build-native.sh','/jobs/package-native.sh').replace('--time=01:00:00','--time=00:10:00').replace('--cpus-per-task=8','--cpus-per-task=2').replace('--mem=16G','--mem=4G')
    for name,content in [('package-native.sh',script),('package-native.sbatch',batch)]:
        path=stage/name;path.write_text(content,encoding='utf8',newline='\n');send(path,REMOTE+'/jobs/'+name)
    job=ssh('sbatch --parsable '+REMOTE+'/jobs/package-native.sbatch').split(';')[0]
    report={'job_id':job,'compiled_job_id':compiled,'state':'submitted','remote_root':REMOTE,'log':REMOTE+'/logs/native-'+job+'.log','artifacts':REMOTE+'/artifacts/'+job,'local_build':False,'package_only':True}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))


def fetch():
    report=json.loads(REPORT.read_text(encoding='utf8'));job=report['job_id']
    assert job.isdecimal()
    state=ssh('sacct -j '+job+' --format=State,ExitCode -X --noheader --parsable2')
    assert 'COMPLETED|0:0' in state,'Native build has not completed: '+state
    remote_path=REMOTE+'/artifacts/native-runtime-'+job+'.tar.gz'
    size=int(ssh('stat -c %s -- '+shlex.quote(remote_path)))
    cache=ROOT/'.local/cluster-native'/('parts-'+job);cache.mkdir(exist_ok=True)
    block=1024*1024;count=(size+block-1)//block
    def receive(index):
        target=cache/(str(index)+'.bin');expected=min(block,size-index*block)
        if target.is_file() and target.stat().st_size==expected:return
        temporary=target.with_suffix('.part')
        with temporary.open('wb') as output:
            subprocess.run(['ssh','-T','-o','BatchMode=yes','research-cluster-xh5','dd if='+shlex.quote(remote_path)+' bs=1048576 skip='+str(index)+' count=1 status=none'],stdout=output,stderr=subprocess.PIPE,check=True,timeout=180)
        assert temporary.stat().st_size==expected
        temporary.replace(target);print('Received native range '+str(index+1)+'/'+str(count),flush=True)
    with ThreadPoolExecutor(max_workers=3) as workers:
        for future in as_completed([workers.submit(receive,index) for index in range(count)]):future.result()
    archive=cache.parent/('native-'+job+'.tar.gz')
    with archive.open('wb') as output:
        for index in range(count):
            with (cache/(str(index)+'.bin')).open('rb') as chunk:shutil.copyfileobj(chunk,output)
    release=cache.parent/'releases'/job;release.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive) as bundle:
        assert all((release/m.name).resolve().is_relative_to(release.resolve()) for m in bundle.getmembers())
        bundle.extractall(release,filter='data')
    native=json.loads((release/'build.json').read_text(encoding='utf8'));assert native['job_id']==job
    for row in native['files']:
        path=release/row['name'];assert path.parent==release and path.stat().st_size==row['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    report.update(state='COMPLETED',exit_code='0:0',local_release=str(release),build=native)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','status','fetch','package']);args=parser.parse_args()
    {'submit':submit,'status':status,'fetch':fetch,'package':package}[args.action]()
