"""Compute-node simulation execution and declared result checks, without an LLM."""
from pathlib import Path
import argparse,asyncio,json,math,os,subprocess,sys,time

def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def inside(root,value):
    path=(root/value).resolve()
    if not path.is_relative_to(root) or path==root:raise ValueError('Simulation path is outside the run directory')
    return path

def checks(summary,spec):
    rows=[]
    for check in spec.get('checks',[]):
        value=summary
        for part in check['field'].split('.'):
            if not isinstance(value,dict) or part not in value:raise ValueError('Missing simulation observable: '+check['field'])
            value=value[part]
        op=check['op'];target=check.get('value');tolerance=check.get('atol',0)
        if op=='finite':passed=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
        elif op=='true':passed=value is True
        else:
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):passed=False
            elif op=='le':passed=value<=target
            elif op=='ge':passed=value>=target
            elif op=='close':passed=abs(value-target)<=tolerance
            else:raise ValueError('Unsupported simulation check')
        rows.append({'field':check['field'],'op':op,'observed':value,'expected':target,'atol':tolerance,'passed':passed,'unit':check.get('unit',''),'basis':check.get('basis','')})
    return rows

async def mcp_steps(root,spec):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    responses=[]
    parameters=StdioServerParameters(command=sys.executable,args=['-c','import openpaso;openpaso.main()'],env=os.environ.copy())
    async with stdio_client(parameters) as (read,write_stream):
        async with ClientSession(read,write_stream) as session:
            initialized=await session.initialize();catalog=await session.list_tools();tools={tool.name:tool for tool in catalog.tools}
            write(root/'results/tool-capabilities.json',{'server':initialized.serverInfo.model_dump(mode='json'),'tools':list(tools)})
            for index,step in enumerate(spec['tool_steps']):
                if step['tool'] not in tools:raise ValueError('Solver tool is not installed: '+step['tool'])
                result=await session.call_tool(step['tool'],step.get('arguments',{}));raw=result.model_dump(mode='json')
                write(root/'results'/f'tool-{index+1}.json',{'tool':step['tool'],'arguments':step.get('arguments',{}),'result':raw})
                if result.isError:raise RuntimeError('Solver MCP rejected '+step['tool']+': '+str(raw)[-1500:])
                structured=result.structuredContent
                if structured is None:
                    text=''.join(c.text for c in result.content if c.type=='text')
                    try:structured=json.loads(text)
                    except ValueError:structured={'text':text}
                if isinstance(structured,dict) and structured.get('status') in ('error','failed','rejected'):raise RuntimeError('Solver returned a non-success result: '+json.dumps(structured,ensure_ascii=False)[-1500:])
                responses.append({'tool':step['tool'],'result':structured})
    if spec.get('summary_path')=='results/summary.json':write(root/'results/summary.json',{'tool_results':responses})

def run(request):
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Simulation requires a Slurm compute allocation')
    request=Path(request).resolve();root=request.parent;spec=json.loads(request.read_text(encoding='utf8'))['simulation'];started=time.time();result_dir=root/'results';result_dir.mkdir(exist_ok=True)
    outcome={'schema_version':1,'job_id':os.environ['SLURM_JOB_ID'],'host':os.uname().nodename,'engine':spec['engine'],'started':started,'run_directory':str(root),'inputs':spec.get('input_paths',[]),'physics':spec.get('physics',{}),'validation_basis':spec.get('validation_basis','unspecified')}
    try:
        if spec['engine']=='python':
            script=inside(root,spec['entrypoint'])
            with (result_dir/'stdout.log').open('wb') as stdout,(result_dir/'stderr.log').open('wb') as stderr:
                executed=subprocess.run([sys.executable,str(script),*spec.get('arguments',[])],cwd=root,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
            outcome['execution_exit_code']=executed.returncode
            if executed.returncode:raise RuntimeError('Simulation returned exit code '+str(executed.returncode)+'; raw stdout and stderr are retained')
        else:asyncio.run(mcp_steps(root,spec));outcome['execution_exit_code']=0
        missing=[name for name in spec.get('expected_outputs',[]) if not inside(root,name).is_file()]
        if missing:raise ValueError('Simulation outputs are missing: '+', '.join(missing))
        summary_path=inside(root,spec['summary_path']);summary=json.loads(summary_path.read_text(encoding='utf8'))
        comparison=checks(summary,spec);passed=all(row['passed'] for row in comparison)
        outcome.update(summary=summary,checks=comparison,status='completed' if passed else 'failed',
                       evidence_states=['EXECUTED']+(['NUMERICALLY_CHECKED'] if comparison and passed else []),
                       error='' if passed else 'Declared numerical result checks did not pass')
    except Exception as error:outcome.update(status='failed',error=str(error)[-1800:])
    outcome['finished']=time.time();outcome['artifacts']=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size} for p in result_dir.iterdir() if p.is_file()]
    write(result_dir/'workflow-result.json',outcome);print(json.dumps({k:outcome.get(k) for k in ['status','job_id','host','error']}))
    return 0 if outcome['status']=='completed' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args();raise SystemExit(run(a.request))
