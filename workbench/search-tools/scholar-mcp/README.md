# Scholar MCP

Local MCP server that searches Google Scholar. Scrapes results with `requests` + `BeautifulSoup` -- no API keys, no paid services.

## Tools

- **`search_papers_by_topic`** -- search by keywords, optional year range, paginated
- **`get_author_papers`** -- find papers by author name, paginated

## Install

Clone and install:

```bash
git clone https://github.com/ProPriyam/Scholar-MCP.git
cd Scholar-MCP
pip install -e .
```

Or run directly without cloning (needs [uv](https://docs.astral.sh/uv/)):

```bash
uvx --from git+https://github.com/ProPriyam/Scholar-MCP scholar-mcp
```

## Client setup

All configs use `python -m scholar_mcp.server` to start the server. This avoids PATH issues that `pip install` can cause on Windows.


### VS Code

Add to `.vscode/mcp.json`:

```json
{
	"servers": {
		"scholarMcp": {
			"type": "stdio",
			"command": "python",
			"args": ["-m", "scholar_mcp.server"],
			"env": {
				"PYTHONUNBUFFERED": "1"
			}
		}
	}
}
```

### OpenCode

Add to `opencode.json` in your project root:

```json
{
	"$schema": "https://opencode.ai/config.json",
	"mcp": {
		"scholar_mcp": {
			"type": "local",
			"command": ["python", "-m", "scholar_mcp.server"],
			"enabled": true,
			"environment": {
				"PYTHONUNBUFFERED": "1"
			}
		}
	}
}
```

### Claude Code

```bash
claude mcp add --transport stdio --scope project scholar-mcp -- python -m scholar_mcp.server
```

## Configuration

All optional. Set as environment variables.

| Variable                | Default        | Description                              |
| ----------------------- | -------------- | ---------------------------------------- |
| `SCHOLAR_USER_AGENT`    | Chrome-like UA | User-Agent header for requests           |
| `SCHOLAR_TIMEOUT`       | `20`           | HTTP timeout in seconds                  |
| `SCHOLAR_MIN_DELAY`     | `1.2`          | Minimum delay between requests (seconds) |
| `SCHOLAR_MAX_RETRIES`   | `2`            | Retry attempts on failure                |
| `SCHOLAR_RETRY_BACKOFF` | `1.5`          | Backoff multiplier between retries       |
| `SCHOLAR_PROXY_URL`     | none           | HTTP/HTTPS proxy URL                     |
| `SCHOLAR_MAX_PAGE_SIZE` | `20`           | Max results per request                  |

## Notes

- This scrapes Google Scholar HTML. It can break if Google changes their markup or blocks requests.
