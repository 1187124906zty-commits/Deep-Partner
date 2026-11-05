"""Bounded official MCP session; stdout contains only the response envelope."""
from pathlib import Path
import asyncio
import json
import logging
import sys

TOOLS = ('search_papers_by_topic', 'get_author_papers')


def failure(code, message, retryable=False, details=None, tool=None):
    return {'ok': False, 'tool': tool, 'error': {'code': code, 'message': message,
            'retryable': retryable, 'details': details or {}}}


def request(value):
    if not isinstance(value, dict):
        raise ValueError('Request must be an object')
    tool = value.get('tool', TOOLS[0])
    arguments = value.get('arguments', value if 'tool' not in value else {})
    if tool not in TOOLS or not isinstance(arguments, dict):
        raise ValueError('Unsupported Scholar tool or arguments')
    allowed = {'query', 'author', 'page_size', 'cursor', 'year_min', 'year_max'}
    key = 'query' if tool == TOOLS[0] else 'author'
    if set(arguments) - allowed or not isinstance(arguments.get(key), str) or not 2 <= len(arguments[key]) <= 900:
        raise ValueError('Invalid query/author arguments')
    if not isinstance(arguments.get('page_size', 10), int) or not 1 <= arguments.get('page_size', 10) <= 10:
        raise ValueError('page_size must be between 1 and 10')
    if arguments.get('cursor') is not None and not isinstance(arguments['cursor'], str):
        raise ValueError('cursor must be a string')
    for year in ('year_min', 'year_max'):
        if arguments.get(year) is not None and type(arguments[year]) is not int:
            raise ValueError('year must be an integer')
    if arguments.get('year_min') is not None and arguments.get('year_max') is not None and arguments['year_min'] > arguments['year_max']:
        raise ValueError('Invalid year range')
    return tool, dict(arguments)


async def dispatch(session, value):
    await session.initialize()
    listed = await session.list_tools()
    tools = {t.name: t for t in listed.tools}
    if value.get('operation') == 'diagnostics':
        return {'ok': True, 'handshake': True, 'tools': list(tools)}
    tool, arguments = request(value)
    if tool not in tools:
        return failure('mcp_tool_missing', 'Installed MCP does not expose the requested tool', tool=tool)
    schema = tools[tool].inputSchema or {}
    properties = schema.get('properties', {})
    if tool == TOOLS[1] and 'author' not in properties:
        alias = next((k for k in ('author_name', 'author_id') if k in properties), None)
        if alias:
            arguments[alias] = arguments.pop('author')
    # Do not silently discard pagination/year constraints unsupported by an installation.
    if properties and schema.get('additionalProperties') is False and set(arguments) - set(properties):
        return failure('mcp_schema_mismatch', 'Installed tool schema does not support requested arguments',
                       details={'unsupported': sorted(set(arguments) - set(properties))}, tool=tool)
    result = await session.call_tool(tool, arguments)
    value = getattr(result, 'structuredContent', None)
    if value is None:
        for content in result.content:
            if content.type == 'text':
                try:
                    value = json.loads(content.text)
                    break
                except ValueError:
                    continue
    if not isinstance(value, dict):
        return failure('mcp_protocol_error', 'MCP returned no structured response', tool=tool)
    if getattr(result, 'isError', False) and value.get('ok') is not False:
        return failure('mcp_tool_error', 'MCP tool returned an error', details=value, tool=tool)
    value['tool'] = tool
    return value


async def run(value):
    import importlib.util
    missing = [name for name in ('mcp', 'scholar_mcp') if importlib.util.find_spec(name) is None]
    if missing:
        return failure('python_module_missing', 'Configured interpreter is missing required MCP modules',
                       details={'modules': missing}, tool=value.get('tool', TOOLS[0]))
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    server = StdioServerParameters(command=sys.executable,
        args=['-X', 'utf8', str(Path(__file__).with_name('scholar_mcp_gateway.py'))],
        env={'PYTHONUNBUFFERED': '1', 'SCHOLAR_TIMEOUT': '18', 'SCHOLAR_MAX_RETRIES': '0', 'SCHOLAR_MIN_DELAY': '1.3'})
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            return await dispatch(session, value)


async def main():
    sys.stdout.reconfigure(encoding='utf8')
    logging.basicConfig(level=logging.WARNING)
    value = json.loads(sys.stdin.read())
    try:
        if value.get('operation') != 'diagnostics':
            request(value)
        result = await asyncio.wait_for(run(value), 35)
    except ValueError:
        result = failure('invalid_arguments', 'Invalid Scholar tool arguments', tool=value.get('tool', TOOLS[0]))
    except ModuleNotFoundError as error:
        result = failure('python_module_missing', 'Scholar interpreter is missing a required module',
                         details={'module': error.name}, tool=value.get('tool', TOOLS[0]))
    except Exception:
        result = failure('mcp_transport_error', 'MCP initialize/list_tools/call_tool transport failed',
                         True, tool=value.get('tool', TOOLS[0]))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
