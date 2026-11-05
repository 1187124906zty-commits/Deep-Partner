# Google Scholar MCP for the research workbench

The installed discovery tool is [ProPriyam/Scholar-MCP](https://github.com/ProPriyam/Scholar-MCP), version **0.1.0**, upstream commit **c7bc58a730c44ddc6446690ca039b9d7f32d455a** (2026-02-22), under the **MIT license**. The upstream source is unmodified. It uses ordinary HTTP requests and BeautifulSoup to search Google Scholar and serves tools over MCP stdio. It requires no API key.

On 2026-11-01, real stdio MCP calls successfully returned five Google Scholar results for each of:

- `moisture transport cementitious materials`
- `physics informed neural operator porous media transport`

Actual protocol evidence and both complete result payloads are saved in `../verification/search-mcp/scholar-live-results.json`. The actual `tools/list` response is `../verification/search-mcp/scholar-list-tools.json`.

## Start the original MCP server

Working directory:

```text
D:/Development/research-workbench/search-tools/scholar-mcp
```

Executable and arguments:

```powershell
& 'D:/Development/research-workbench/search-tools/scholar-env/Scripts/python.exe' -m scholar_mcp.server
```

The project-local configuration is `scholar-mcp.config.json`. No global Codex configuration was changed. No API credential is required. Verification used `PYTHONUNBUFFERED=1`, `SCHOLAR_TIMEOUT=15`, and `SCHOLAR_MAX_RETRIES=0`; the supplied integration configuration uses a 20-second timeout. All other upstream settings remain at their defaults.

The default package install pulled MCP SDK 2.3.0, which has removed `mcp.server.fastmcp` and caused startup failure. The isolated environment was corrected to **MCP SDK 1.30.0**. `scholar-constraints.txt` constrains the SDK to 1.x, and `scholar-requirements.lock.txt` records the actual local environment. When reproducing on the service, install `mcp[cli]==1.30.0` before, or together with, the original package under this constraint. The original source declares Python >=3.10; the local validation used Python 3.12.13. Python 3.11 deployment still requires its own startup and live-call validation.

```powershell
& 'path/to/isolated/python.exe' -m pip install -c 'scholar-constraints.txt' -e 'scholar-mcp'
```

## Tool contracts

`search_papers_by_topic` accepts an object with required `query: string` and optional `page_size: integer = 10`, `cursor: string | null = null`, `year_min: integer | null = null`, and `year_max: integer | null = null`.

`get_author_papers` accepts required `author: string` and optional `page_size: integer = 10`, `cursor: string | null = null`.

The live response provides both text content containing JSON and `structuredContent` containing the same object:

```json
{
  "ok": true,
  "data": {
    "query": "moisture transport cementitious materials",
    "page_size": 5,
    "cursor": "0",
    "next_cursor": "5",
    "source": "google_scholar",
    "results": [
      {
        "title": "...",
        "authors": ["..."],
        "snippet": "...",
        "url": "https://publisher.example/article/...",
        "year": 2007,
        "cited_by": 339,
        "source": "google_scholar"
      }
    ],
    "fetched_at": "2026-11-01T12:38:33.237782Z"
  }
}
```

`snippet`, `url`, `year`, and `cited_by` can be null. Semantic failure is returned as `{"ok":false,"error":{"code":"...","message":"...","retryable":false,"details":{}}}`. `details` is optional. MCP `isError` can remain false for these semantic errors, so integrations must check `payload.ok` as well as `CallToolResult.isError`.

The actual returned sources include Ishida, Maekawa and Kishi's 2007 moisture equilibrium/transport paper, Baroghel-Bouny et al.'s 2011 coupled moisture–ion transport paper, and Zhang and Angst's 2020 dual-permeability paper. These are discovery results, with publisher links and snippets; the search did not retrieve or read their full text.

## One-shot bridge for a local agent

`scholar-client.py` launches the unmodified server, initializes a real MCP session, calls its tool and prints the semantic JSON payload to stdout. Server diagnostics remain on stderr. Exit 0 means the tool returned `ok:true`; exit 2 means transport failure or semantic error.

```powershell
& 'D:/Development/research-workbench/search-tools/scholar-env/Scripts/python.exe' 'D:/Development/research-workbench/search-tools/scholar-client.py' --query 'moisture transport cementitious materials' --limit 5
```

Use `--list-tools` for the current schemas. Optional search flags are `--cursor`, `--year-min`, and `--year-max`. The wrapper limits each page to 1–10 because the upstream client does not send Google's `num` parameter despite allowing a page size up to 20.

The deployed app can dispatch a literature-search job to its existing agent bridge. The agent can run this CLI or keep an MCP stdio session alive, return raw discovery records and provenance, then let the service store and display them. A deployed service with permitted outbound access can run the same original server in its own isolated environment. A local agent remains useful when that deployment's IP cannot reach Google Scholar. Crossref can verify DOI and bibliographic metadata after discovery.

## Bounded integration concerns

- Google Scholar scraping is unofficial and HTML or access limits can change. Success on this machine proves these two calls, not permanent availability from other IPs.
- HTTP 403 becomes `blocked`; HTTP 429/503 becomes `rate_limited`. The upstream code accepts any HTTP 200 as a results page. A verification or consent page could therefore parse as an empty successful result. A deployment adapter should check the final redirect URL for `/sorry/`, CAPTCHA/recaptcha or `gs_captcha` forms/inputs, characteristic unusual-traffic/not-a-robot text, and consent-only pages before parsing. These are suggested checks; no challenge page was observed during this validation. A missing results container alone must not become a definitive claim that no papers exist. Do not automatically solve verification challenges or reuse browser sessions.
- Some actual `authors` entries contain journal names and years because the parser splits only an ordinary-space hyphen separator while Google uses nonbreaking spaces. Preserve raw search metadata; verify author/journal/DOI separately. Titles can contain `[HTML]`/`[PDF]` labels and truncation, and search snippets are not abstracts.
- The author endpoint searches an author name; it does not establish a unique Scholar profile identity. `author.id` and affiliation are null in its implementation.
- Attribution should identify Google Scholar as discovery source, preserve the original publisher URL and retrieval time, and describe Scholar-MCP as an independent third-party tool. The MIT license and copyright remain with the source distribution.

The alternative [mcp-free-web-search](https://github.com/mdelaguera/mcp-free-web-search) was checked as a small Google web-search candidate. The Scholar-specific tool already succeeded with both required engineering queries, so no second tool was installed. Web of Science was not used, and no credentials were requested, inspected or copied.

## Packaging

For a tiny deployment source archive include `scholar-mcp/scholar_mcp/`, `scholar-mcp/pyproject.toml`, `scholar-mcp/README.md`, `scholar-mcp/LICENSE`, and `scholar-constraints.txt`. Exclude `.git`, `scholar-env`, `__pycache__` and `*.egg-info`. The separate original checkout and environment are local implementation files, not data to send to the research cluster.
