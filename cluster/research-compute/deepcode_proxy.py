"""The existing DeepCode MCP client reads credentials outside project config."""
import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

server = Server('research-compute')


async def request(action, *arguments):
    token = (Path.home() / '.deepcode/compute-token').read_text().strip()
    async with streamablehttp_client('http://research-compute:47920/mcp', headers={'Authorization': 'Bearer ' + token}, timeout=90) as channels:
        async with ClientSession(channels[0], channels[1]) as session:
            await session.initialize()
            return await getattr(session, action)(*arguments)


@server.list_tools()
async def tools():
    return (await request('list_tools')).tools


@server.call_tool()
async def call(name, arguments):
    return await request('call_tool', name, arguments)


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == '__main__':
    asyncio.run(main())
