"""Two unchanged upstream MCP contracts plus the dedicated native workflow."""
from typing import Literal
import contextlib,sys
from mcp.server.fastmcp import FastMCP
from deepcode_native import mcp_call,workflow

mcp=FastMCP('DeepCode with native workflows',instructions='Use the coding tools for ordinary implementation. For source-grounded Paper2Code use deepcode_workflow; it invokes the installed native workflow service, preserving stages, plan review, retries and artifacts.')

@mcp.tool()
async def deepcode(prompt:str,workspace:str='',model:str='')->dict:
    args={'prompt':prompt}
    if workspace:args['workspace']=workspace
    if model:args['model']=model
    return await mcp_call('deepcode',args)

@mcp.tool(name='deepcode-reply')
async def deepcode_reply(session_id:str,prompt:str)->dict:
    return await mcp_call('deepcode-reply',{'session_id':session_id,'prompt':prompt})

@mcp.tool()
async def deepcode_workflow(action:Literal['capabilities','start','read','respond','retry','interrupt','artifacts','verify'],workspace:str='',run_id:str='',source:str='',source_type:Literal['requirement','local','url','repository']='requirement',options:dict|None=None,interaction_id:str='',response:dict|None=None,thread_id:str='')->dict:
    """Invoke the actual installed Paper2Code lifecycle, review and artifact methods.
    Start uses source and workspace. Read/retry/interrupt use run_id. Respond
    uses the live interaction_id and response supplied by the author.
    """
    # The legacy workflow prints ordinary progress. Keep MCP stdout exclusively
    # for protocol frames while the original workflow writes diagnostics.
    with contextlib.redirect_stdout(sys.stderr):
        return await workflow(action,workspace,run_id,source,source_type,options,interaction_id,response,thread_id)

if __name__=='__main__':mcp.run()
