"""Task tools bound to Research Workbench's existing authenticated HTTP APIs."""

from contextlib import ExitStack
import json as json_module
import mimetypes
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import uuid4

from fastmcp import FastMCP


workspace_api_mcp = FastMCP(name="workspace_api")
_client: Any = None
_READ = {"readOnlyHint": True, "destructiveHint": False}


def configure_client(client: Any) -> None:
    """Inject the coordinator-owned authenticated transport."""
    global _client
    _client = client


def _transport():
    if _client is None:
        raise RuntimeError("The Workbench client has not been configured")
    return _client


def _required(value, name):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{name} is required for this action")
    return value


def _project_route(project_id, suffix=""):
    return "/research/api/projects/" + quote(_required(project_id, "project_id"), safe="") + suffix


def _kb_route(knowledge_base):
    return "/api/knowledge-bases/" + quote(_required(knowledge_base, "knowledge_base"), safe="")


def _reply(value, route, message="Native Workbench result"):
    artifacts = []
    if isinstance(value, dict) and isinstance(value.get("path"), str) and "bytes" in value:
        artifacts = [{"description": "Downloaded native artifact", **value}]
    return {"message": message, "reference": _transport().origin.rstrip("/") + route,
            "artifacts": artifacts, "data": value}


async def _request(method, route, **kwargs):
    return _reply(await _transport().request(method, route, **kwargs), route)


async def _native(method, route, project_id, **kwargs):
    return _reply(await _transport().native_request(method, route, project_id, **kwargs), route)


async def _deliver(route, *, params=None, output_dir=None, filename="artifact.bin", native_project=None):
    if output_dir is None:
        if native_project is not None:
            return await _native("GET", route, native_project, params=params)
        return await _request("GET", route, params=params)
    if native_project is not None:
        project = await _transport().project(native_project)
        params = {**(params or {}), "dt_workspace": project["native_id"]}
    directory = Path(output_dir).expanduser().resolve() / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / Path(filename).name
    artifact = await _transport().download(route, str(destination), params=params)
    return _reply(artifact, route, "Downloaded the native artifact into a fresh directory")


async def _upload(route, file_paths, *, data=None, project_id=None, field="files", max_mib=None, allow_empty=False):
    paths = [Path(path).expanduser().resolve() for path in (file_paths or [])]
    if not paths and not allow_empty:
        raise ValueError("At least one local file path is required")
    with ExitStack() as stack:
        files = []
        for path in paths:
            if not path.is_file():
                raise ValueError(f"Local input file does not exist: {path}")
            if max_mib is not None and path.stat().st_size > max_mib * 1024**2:
                raise ValueError(f"Each upload must be at most {max_mib} MiB")
            files.append((field, (path.name, stack.enter_context(path.open("rb")), mimetypes.guess_type(path.name)[0] or "application/octet-stream")))
        if project_id is None:
            return await _request("POST", route, data=data, files=files or None)
        return await _native("POST", route, project_id, data=data, files=files or None)


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_account(
    action: Annotated[Literal["current", "status", "profile"], "Read the current identity, authentication status or account profile"] = "current",
) -> dict:
    """Inspect the current Workbench account and authentication state.
    Input selects an account view; output preserves its native identity/profile fields.
    """
    route = {"current": "/research/api/me", "status": "/api/auth/status", "profile": "/api/auth/profile"}[action]
    return await _request("GET", route)


@workspace_api_mcp.tool()
async def workbench_projects(
    action: Annotated[Literal["list", "create", "update"], "List projects, create one, or rename an existing owned project"] = "list",
    project_id: Annotated[str | None, "Existing project ID required for update"] = None,
    name: Annotated[str | None, "Project name of 1 to 100 characters for create or update"] = None,
) -> dict:
    """List, create or rename research projects through the original application.
    Input is an action and its project/name fields; output is the native project result.
    """
    if action == "list":
        return await _request("GET", "/research/api/projects")
    body = {"name": _required(name, "name")}
    route = "/research/api/projects" if action == "create" else _project_route(project_id)
    return await _request("POST" if action == "create" else "PATCH", route, json=body)


@workspace_api_mcp.tool()
async def workbench_files(
    project_id: Annotated[str, "Existing owned Workbench project ID"],
    action: Annotated[Literal["list", "read", "upload", "write", "create_folder", "trash"], "Project file operation"] = "list",
    path: Annotated[str, "Project-relative file path or directory; empty lists the root"] = "",
    content: Annotated[str | None, "Exact UTF-8 text to save for write"] = None,
    file_paths: Annotated[list[str] | None, "Local files to upload into path, each at most 256 MiB"] = None,
    expected_modified: Annotated[float | None, "Existing modification timestamp for optimistic write conflict detection"] = None,
    reason: Annotated[str, "Reason saved in native replacement history"] = "MCP file edit",
    output_dir: Annotated[str | None, "Optional local download base directory; a fresh child is created per read"] = None,
) -> dict:
    """Manage current project files while preserving native conflict and history behavior.
    Input supplies project-relative paths or local uploads; output is native state or an absolute artifact.
    """
    if action == "list":
        return await _request("GET", _project_route(project_id, "/files"), params={"path": path})
    if action == "upload":
        return await _upload(_project_route(project_id, "/files"), file_paths, data={"path": path}, max_mib=256)
    _required(path, "path")
    if action == "read":
        return await _deliver(_project_route(project_id, "/file"), params={"path": path}, output_dir=output_dir, filename=path)
    if action == "write":
        return await _request("PUT", _project_route(project_id, "/file"), json={"path": path, "content": _required(content, "content") if content is None else content, "expected_modified": expected_modified, "reason": reason})
    if action == "create_folder":
        return await _request("POST", _project_route(project_id, "/folders"), json={"path": path})
    return await _request("DELETE", _project_route(project_id, "/file"), params={"path": path})


@workspace_api_mcp.tool()
async def workbench_revisions(
    project_id: Annotated[str, "Existing owned project ID"],
    action: Annotated[Literal["list", "inspect", "restore"], "Inspect or restore native recoverable history"] = "list",
    revision_id: Annotated[str | None, "Native trash/revision ID required for inspect or restore"] = None,
    view: Annotated[Literal["diff", "preview"], "Readable history difference or original preview"] = "diff",
    output_dir: Annotated[str | None, "Download base directory for preview; each call creates a fresh child"] = None,
) -> dict:
    """Inspect or restore the application's recoverable artifact revisions.
    Input identifies a native revision; output is history, a native diff, preview or restoration result.
    """
    route = _project_route(project_id, "/trash")
    if action == "list":
        return await _request("GET", route)
    route += "/" + quote(_required(revision_id, "revision_id"), safe="")
    if action == "restore":
        return await _request("POST", route + "/restore")
    if view == "preview":
        return await _deliver(route + "/preview", output_dir=output_dir, filename="revision-preview.bin")
    return await _request("GET", route + "/diff")


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_rules(
    action: Annotated[Literal["standards", "skill", "llms", "schema", "context"], "Read task standards, a named skill, API schema or project integration context"] = "standards",
    project_id: Annotated[str | None, "Owned project ID required for context"] = None,
    identifier: Annotated[str | None, "Skill identifier returned by standards, required for skill"] = None,
    task: Annotated[Literal["code", "code-review", "test", "paper", "translation", "literature", "slides", "review", "reader", "figure"], "Task-specific integration context"] = "review",
) -> dict:
    """Read existing Workbench task rules and source integration contracts.
    Input selects a rule/context view; output preserves the actual published instructions or schema.
    """
    if action == "context":
        return await _request("GET", _project_route(project_id, "/agent-context"), params={"task": task})
    if action == "skill":
        return await _request("GET", "/research/api/standards/skills/" + quote(_required(identifier, "identifier"), safe="/"))
    return await _request("GET", {"standards": "/research/api/standards", "llms": "/research/llms.txt", "schema": "/research/api/schema"}[action])


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_storage(
    action: Annotated[Literal["usage"], "Read account quota, file and cache usage"] = "usage",
) -> dict:
    """Inspect the current account's storage usage and quota.
    Input selects usage; output is the native storage and cache report.
    """
    return await _request("GET", "/research/api/storage")


@workspace_api_mcp.tool()
async def workbench_knowledge_bases(
    project_id: Annotated[str, "Owned project used to resolve the actual native workspace scope"],
    action: Annotated[Literal["list", "details", "create", "bind"], "List assignable resources, inspect/create a KB, or bind visible KB IDs"] = "list",
    knowledge_base: Annotated[str | None, "Native qualified knowledge-base ID for details"] = None,
    name: Annotated[str | None, "Name for a new knowledge base"] = None,
    knowledge_bases: Annotated[list[str] | None, "Exact visible qualified IDs to bind; an explicit empty list clears bindings"] = None,
    file_paths: Annotated[list[str] | None, "Optional local source files; no files creates a native empty KB"] = None,
    rag_provider: Annotated[str, "Source-supported native provider identifier, fixed for the new KB"] = "llamaindex",
    pageindex_mode: Annotated[Literal["", "flash", "standard"], "Optional native PageIndex OSS mode"] = "",
    search_mode: Annotated[str, "Optional search mode supported by the selected native provider"] = "",
    rel_paths: Annotated[list[str] | None, "Optional upload-relative paths aligned with local files"] = None,
    indexing_llm: Annotated[dict | None, "Legacy native indexing selection; current upstream may reject per-KB overrides"] = None,
    embedding_model: Annotated[dict | None, "Native configured profile_id/model_id selection, without secrets"] = None,
) -> dict:
    """Manage knowledge-base resources in the owned project's native workspace scope.
    Input supplies existing IDs or new-KB sources; output preserves native metadata and indexing task IDs.
    """
    if action == "bind":
        if knowledge_bases is None:
            raise ValueError("knowledge_bases is required for bind; use [] to clear")
        return await _request("PATCH", _project_route(project_id), json={"knowledge_bases": knowledge_bases})
    if action == "list":
        return await _native("GET", "/api/knowledge-bases", project_id, params={"resource_library": "true"})
    if action == "details":
        return await _native("GET", _kb_route(knowledge_base), project_id)
    project = await _transport().project(project_id)
    data = {"name": _required(name, "name"), "rag_provider": rag_provider, "storage_workspace_id": project["native_id"],
            "pageindex_mode": pageindex_mode, "search_mode": search_mode}
    if rel_paths is not None:
        data["rel_paths"] = rel_paths
    if indexing_llm is not None:
        data["indexing_llm"] = json_module.dumps(indexing_llm)
    if embedding_model is not None:
        data["embedding_model"] = json_module.dumps(embedding_model)
    return await _upload("/api/knowledge-bases", file_paths, data=data, project_id=project_id, allow_empty=True)


@workspace_api_mcp.tool()
async def workbench_knowledge_files(
    project_id: Annotated[str, "Owned project supplying the native workspace scope"],
    knowledge_base: Annotated[str, "Actual qualified knowledge-base ID visible in that scope"],
    action: Annotated[Literal["list", "read", "upload", "create_folder", "move"], "Native KB source-file operation"] = "list",
    filename: Annotated[str | None, "KB-relative source filename for read"] = None,
    view: Annotated[Literal["original", "text"], "Original bytes or the actual plain-text extraction preview"] = "text",
    file_paths: Annotated[list[str] | None, "Local files for upload"] = None,
    rel_paths: Annotated[list[str] | None, "Optional source-relative paths aligned with uploaded files"] = None,
    dest_subdir: Annotated[str | None, "Optional organizational destination for an upload batch"] = None,
    rag_provider: Annotated[str | None, "Optional provider check; must match the KB's fixed provider"] = None,
    image_analysis: Annotated[bool | None, "Native pinned image-analysis policy; omitted preserves that policy"] = None,
    path: Annotated[str | None, "KB-relative folder to create"] = None,
    source: Annotated[str | None, "Current KB-relative file/folder to move"] = None,
    dest_folder: Annotated[str, "Destination folder for a move; empty selects KB root"] = "",
    output_dir: Annotated[str | None, "Download base directory for original files; a fresh child is created"] = None,
) -> dict:
    """Read, append or organize native knowledge-base source files.
    Input supplies scoped KB paths or local files; output is native file state, text preview or an artifact.
    """
    route = _kb_route(knowledge_base)
    if action == "list":
        return await _native("GET", route + "/files", project_id)
    if action == "read":
        name = _required(filename, "filename")
        suffix = "/file-preview-text/" if view == "text" else "/files/"
        return await _deliver(route + suffix + quote(name, safe="/"), native_project=project_id,
                              output_dir=output_dir if view == "original" else None, filename=name)
    if action == "upload":
        data = {key: value for key, value in {"rag_provider": rag_provider, "rel_paths": rel_paths, "dest_subdir": dest_subdir,
                "image_analysis": None if image_analysis is None else str(image_analysis).lower()}.items() if value is not None}
        return await _upload(route + "/upload", file_paths, data=data, project_id=project_id)
    if action == "create_folder":
        return await _native("POST", route + "/folders", project_id, json={"path": _required(path, "path")})
    return await _native("POST", route + "/files/move", project_id, json={"source": _required(source, "source"), "dest_folder": dest_folder})


@workspace_api_mcp.tool()
async def workbench_knowledge_index(
    project_id: Annotated[str, "Owned project supplying native workspace access"],
    knowledge_base: Annotated[str, "Actual native qualified KB ID"],
    action: Annotated[Literal["readiness", "run", "progress", "retry", "cancel"], "Inspect index state, retry failed work, or request safe-boundary cancellation"] = "readiness",
    task_id: Annotated[str | None, "Native indexing-run task ID required for cancel"] = None,
) -> dict:
    """Inspect and control the existing native knowledge indexing lifecycle.
    Input identifies the scoped KB/run; output preserves readiness, durable state or retry/cancel acceptance.
    """
    route = _kb_route(knowledge_base)
    if action in {"readiness", "run", "progress"}:
        suffix = {"readiness": "/indexing-readiness", "run": "/indexing-run", "progress": "/progress"}[action]
        return await _native("GET", route + suffix, project_id)
    if action == "retry":
        return await _native("POST", route + "/retry", project_id)
    return await _native("POST", route + "/indexing-run/" + quote(_required(task_id, "task_id"), safe="") + "/cancel", project_id)


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_search_sources(
    action: Annotated[Literal["status"], "Read actual paper, web, institution and metrics provider configuration flags"] = "status",
) -> dict:
    """Inspect the actual configured discovery sources for the current account.
    Input selects status; output contains native source names and availability flags.
    """
    return await _request("GET", "/research/api/search/sources")


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_web_search(
    q: Annotated[str, "Web query of 3 to 600 characters"],
    action: Annotated[Literal["search"], "Search using the account's actual configured web provider"] = "search",
    kind: Annotated[Literal["all", "journal", "template"], "Use general search or the source's publisher-domain filter"] = "all",
) -> dict:
    """Search real web pages through the Workbench discovery provider.
    Input is a query and source-supported domain filter; output is the native search response.
    """
    return await _request("GET", "/research/api/search/web", params={"q": q, "kind": kind})


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_paper_search(
    project_id: Annotated[str, "Owned project anchoring the discovery task"],
    q: Annotated[str, "Actual literature search query"],
    action: Annotated[Literal["search"], "Search bibliographic sources without claiming full-text verification"] = "search",
    source: Annotated[Literal["auto", "scholar_mcp", "academic_web", "crossref", "semantic", "scholar", "wos"], "Native provider selection; configured credentials remain server-side"] = "auto",
    years: Annotated[Literal[0, 5, 10], "Publication-year window; zero applies no year filter"] = 0,
    newest: Annotated[bool, "Request the upstream source's newest-first ordering"] = False,
    page: Annotated[int, "Native result page from 1 to 50"] = 1,
    limit: Annotated[int, "Results from 1 to 20; Scholar MCP natively caps this at 10"] = 20,
) -> dict:
    """Search existing literature providers and retain stable native selection identities.
    Input is a project query/provider/window/page; output preserves bibliographic records and source status.
    """
    return await _request("GET", _project_route(project_id, "/literature/search"),
                          params={"q": q, "source": source, "years": years, "newest": newest, "page": page, "limit": limit})


@workspace_api_mcp.tool()
async def workbench_literature(
    project_id: Annotated[str, "Existing owned research project ID"],
    action: Annotated[Literal["list", "upload", "match", "read", "preview"], "List, attach, identify or read source documents"] = "list",
    asset: Annotated[str | None, "Actual project-literature or linked-KB relative source path"] = None,
    library: Annotated[str, "workspace or an actual project-bound native KB ID"] = "workspace",
    file_paths: Annotated[list[str] | None, "Local PDF files for upload, each at most 100 MiB"] = None,
    folder: Annotated[Literal["references", "validation", "methods", "reading"], "Purpose category for new PDF attachments"] = "reading",
    output_dir: Annotated[str | None, "Local download base directory; a fresh child is created per artifact"] = None,
) -> dict:
    """Manage source-bound literature attachments without replacing their identity checks.
    Input supplies PDF files or native source identities; output is attachment metadata, original bytes or a preview.
    """
    route = _project_route(project_id, "/literature")
    if action == "list":
        return await _request("GET", route + "/items")
    if action == "upload":
        return await _upload(route + "/upload", file_paths, data={"folder": folder}, max_mib=100)
    _required(asset, "asset")
    if action == "match":
        return await _request("POST", route + "/match", json={"asset": asset})
    if action == "preview":
        return await _deliver(route + "/preview", params={"asset": asset, "library": library}, output_dir=output_dir, filename=Path(asset).stem + ".png")
    if library != "workspace":
        project = await _transport().project(project_id)
        if library not in project.get("config", {}).get("knowledge_bases", []):
            raise ValueError("The knowledge base is not bound to this project")
        return await _deliver(_kb_route(library) + "/files/" + quote(asset, safe="/"), native_project=project_id,
                              output_dir=output_dir, filename=asset)
    return await _deliver(route + "/file", params={"asset": asset}, output_dir=output_dir, filename=asset)


@workspace_api_mcp.tool()
async def workbench_literature_organization(
    project_id: Annotated[str, "Existing owned project ID"],
    action: Annotated[Literal["folders", "assign", "classification", "classify"], "Read/assign purpose folders or inspect/request source-based classification"] = "folders",
    asset: Annotated[str | None, "Actual source identity required for assign"] = None,
    category: Annotated[Literal["references", "validation", "methods", "reading"], "Source-supported literature purpose"] = "reading",
) -> dict:
    """Organize research sources by purpose and native source-based classification.
    Input identifies sources or requests classification; output is assignments, classification state or a native job ID.
    """
    if action in {"folders", "assign"}:
        route = _project_route(project_id, "/literature/folders")
        return await _request("GET", route) if action == "folders" else await _request("PUT", route, json={"asset": _required(asset, "asset"), "category": category})
    return await _request("GET" if action == "classification" else "POST", _project_route(project_id, "/literature/classification"))


@workspace_api_mcp.tool()
async def workbench_paper_downloads(
    action: Annotated[Literal["enqueue", "list", "worker_status", "retry", "cancel"], "Queue or inspect the existing authorized ScanSci download pipeline"] = "worker_status",
    project_id: Annotated[str | None, "Owned project ID required except for worker_status"] = None,
    entries: Annotated[list[dict] | None, "One to 100 source-supported DOI/arXiv/title metadata entries"] = None,
    folder: Annotated[Literal["references", "validation", "methods", "reading"], "Purpose category for queued attachments"] = "reading",
    job_id: Annotated[str | None, "Native download task ID for retry or cancel"] = None,
) -> dict:
    """Use the existing authorized document-download queue and its real progress.
    Input supplies source identities or task IDs; output retains queue, transfer and receipt states.
    """
    if action == "worker_status":
        return await _request("GET", "/research/api/download-worker/status")
    route = _project_route(project_id, "/literature")
    if action == "enqueue":
        return await _request("POST", route + "/download-batch", json={"entries": _required(entries, "entries"), "folder": folder})
    if action == "list":
        return await _request("GET", route + "/downloads")
    return await _request("POST", route + "/downloads/" + quote(_required(job_id, "job_id"), safe="") + "/" + action)


@workspace_api_mcp.tool()
async def workbench_reader(
    project_id: Annotated[str, "Owned project containing the manuscript or source PDF"],
    action: Annotated[Literal["open", "content", "image"], "Open a real source PDF, read its native blocks/state, or locate an image"] = "open",
    area: Annotated[Literal["paper", "literature"], "Manuscript or attached literature source"] = "paper",
    asset: Annotated[str, "Actual source path; manuscript/main.json is the current manuscript"] = "manuscript/main.json",
    library: Annotated[str, "workspace or the actual bound KB for literature; empty for manuscript"] = "",
    title: Annotated[str, "Optional source display title"] = "",
    width: Annotated[int, "Native reader viewport width"] = 1000,
    theme: Annotated[str, "Native reader theme identifier"] = "snow",
    document_id: Annotated[str | None, "Native reader document ID returned by open"] = None,
    view: Annotated[Literal["blocks", "translations", "options", "source"], "Native parsed content, saved translations, options or original PDF"] = "blocks",
    block_id: Annotated[str | None, "Native image block ID required for image"] = None,
    output_dir: Annotated[str | None, "Download base directory for the original PDF; each call creates a fresh child"] = None,
) -> dict:
    """Open and inspect the actual project-bound PDF reading protocol.
    Input identifies a real source/document/block; output preserves parsed source blocks, saved states or artifacts.
    """
    if action == "open":
        return await _request("POST", _project_route(project_id, "/reader"), json={"area": area, "asset": asset, "library": library, "title": title, "width": width, "theme": theme})
    identifier = _required(document_id, "document_id")
    if action == "image":
        return await _request("GET", _project_route(project_id, "/reader-image"), params={"document_id": identifier, "block_id": _required(block_id, "block_id")})
    prefix = "/research/reader/" + quote(project_id, safe="")
    if view == "source":
        return await _deliver(prefix + "/pub/workbench/" + quote(identifier, safe="") + "/original.pdf", output_dir=output_dir, filename="original.pdf")
    suffix = {"blocks": "blocks", "translations": "translations", "options": "translation-options"}[view]
    return await _request("GET", prefix + "/api/documents/" + quote(identifier, safe="") + "/" + suffix)


@workspace_api_mcp.tool()
async def workbench_translation(
    project_id: Annotated[str, "Owned project containing the selected manuscript or source PDF"],
    action: Annotated[Literal["manuscript", "reader_start", "export_pdf"], "Translate an editable manuscript, start native PDF translation or export saved PDF translation"] = "manuscript",
    target: Annotated[str, "Target language; reader_start accepts en or zh-CN"] = "zh-CN",
    use_native: Annotated[bool, "Use the assigned native model for manuscript translation instead of the saved Workbench API"] = True,
    source: Annotated[Literal["source", "translation"], "Translate the source manuscript or its existing editable translation"] = "source",
    document_id: Annotated[str | None, "Actual native reader document ID for reader_start or export_pdf"] = None,
    columns: Annotated[Literal[1, 2], "Columns in the native saved-translation PDF export"] = 2,
) -> dict:
    """Translate existing source content through the application's native model protocols.
    Input selects a manuscript or reader document; output retains native jobs or accepted reader operations.
    """
    if action == "manuscript":
        return await _request("POST", _project_route(project_id, "/manuscript/translate"), json={"target": target, "use_native": use_native, "source": source})
    identifier = _required(document_id, "document_id")
    if action == "export_pdf":
        return await _request("POST", _project_route(project_id, "/pdf-translation/export"), json={"document_id": identifier, "columns": columns})
    if target not in {"en", "zh-CN"}:
        raise ValueError("Native reader target must be en or zh-CN")
    route = "/research/reader/" + quote(project_id, safe="") + "/api/documents/" + quote(identifier, safe="")
    options = await _transport().request("PUT", route + "/translation-options", json={"targetLanguage": target})
    processing = await _transport().request("POST", route + "/processing")
    translated = await _transport().request("POST", route + "/translations", json={"blockId": ""})
    return _reply({"options": options, "processing": processing, "translations": translated}, route + "/translations",
                  "Native translation operations accepted; poll reader content view=translations for actual block states")


@workspace_api_mcp.tool()
async def workbench_annotations(
    project_id: Annotated[str, "Owned project containing the real annotated artifact"],
    action: Annotated[Literal["list", "create", "update", "submit"], "Read, create/update anchored questions or submit selected native question IDs"] = "list",
    area: Annotated[Literal["", "paper", "literature", "code", "slides", "image"], "Optional list filter or annotation content area"] = "",
    asset: Annotated[str, "Actual artifact path or source identity"] = "",
    identifier: Annotated[str | None, "Existing annotation ID required for update"] = None,
    payload: Annotated[dict | None, "Native annotation fields: title,quote,body,color,status,locator,origin; area/asset can also be supplied"] = None,
    ids: Annotated[list[str] | None, "Selected annotation IDs required for submit"] = None,
) -> dict:
    """Manage questions anchored to actual project artifacts and native audit history.
    Input is an annotation record or selected question IDs; output is native annotated state or submission receipt.
    """
    route = _project_route(project_id, "/annotations")
    if action == "list":
        return await _request("GET", route, params={"area": area, "asset": asset})
    if action == "submit":
        return await _request("POST", route + "/submit", json={"ids": _required(ids, "ids")})
    body = dict(payload or {})
    if area:
        body["area"] = area
    if asset:
        body["asset"] = asset
    if action == "create":
        _required(body.get("asset"), "asset")
        return await _request("POST", route, json=body)
    return await _request("PATCH", route + "/" + quote(_required(identifier, "identifier"), safe=""), json=body)


@workspace_api_mcp.tool()
async def workbench_review(
    project_id: Annotated[str, "Owned project containing the review context"],
    action: Annotated[Literal["history", "chat_history", "chat_send", "receipt", "quality_rubric", "quality_submit", "quality_list", "quality_gate"], "Read review/chat, record work, or submit/read native version-bound stage quality reviews"] = "history",
    area: Annotated[Literal["paper", "literature", "code", "slides", "image"], "Native content area for review chat"] = "paper",
    asset: Annotated[str, "Actual source/artifact path for chat_send"] = "",
    message: Annotated[str | None, "User-authorized review message, up to 16000 characters"] = None,
    title: Annotated[str, "Optional artifact or question title"] = "",
    quote: Annotated[str, "Actual quoted source passage"] = "",
    locator: Annotated[dict | None, "Native page/paragraph/file locator and optional current_draft editor object"] = None,
    question_ids: Annotated[list[str] | None, "Existing project question IDs addressed by a receipt"] = None,
    artifacts: Annotated[list[dict] | None, "Native receipt artifact records with existing project-root-relative path"] = None,
    validation: Annotated[list[str | dict] | None, "Actual textual or structured validation results for the receipt"] = None,
    limitations: Annotated[list[str] | None, "Actual remaining limitations for the receipt"] = None,
    resolved: Annotated[bool, "Mark only the supplied receipt question IDs resolved"] = False,
    stage: Annotated[str, "Stage ID for quality actions or optional receipt quality evaluation; empty preserves legacy receipts"] = "",
    purpose: Annotated[str, "Presentation purpose ID for slides stages; optional for other stages"] = "",
    operation_id: Annotated[str, "Stable operation ID for quality_submit or staged receipts; reuse only for identical input"] = "",
    artifact_paths: Annotated[list[str] | None, "Project-root-relative stage artifacts; optional when the server has stage defaults"] = None,
    source_paths: Annotated[list[str] | None, "Project-root-relative actual source evidence for the stage review"] = None,
    intended_use: Annotated[str, "Specific purpose and claim scope for quality_submit"] = "",
) -> dict:
    """Continue source-anchored review and record actual project changes and checks.
    Input is chat, a truthful receipt or stage quality request; output preserves native events, jobs and quality decisions.
    """
    if action == "history":
        return await _request("GET", _project_route(project_id, "/review-history"))
    if action == "receipt":
        body = {"question_ids": question_ids or [], "artifacts": artifacts or [],
                "validation": validation or [], "limitations": limitations or [], "resolved": resolved}
        if stage:
            body.update(stage=stage, purpose=purpose, operation_id=operation_id)
        return await _request("POST", _project_route(project_id, "/agent-receipt"), json=body)
    if action == "quality_rubric":
        return await _request("GET", "/research/api/quality/rubric", params={"stage": _required(stage, "stage"), "purpose": purpose})
    if action == "quality_submit":
        return await _request("POST", _project_route(project_id, "/quality/reviews"), json={
            "stage": _required(stage, "stage"), "purpose": purpose, "operation_id": _required(operation_id, "operation_id"),
            "artifact_paths": artifact_paths or [], "source_paths": source_paths or [], "intended_use": intended_use})
    if action == "quality_list":
        return await _request("GET", _project_route(project_id, "/quality/reviews"), params={"stage": stage, "purpose": purpose})
    if action == "quality_gate":
        if artifact_paths and len(artifact_paths) != 1:
            raise ValueError("quality_gate accepts one artifact path; use quality_list for the stored artifact set")
        return await _request("GET", _project_route(project_id, "/quality/gate"), params={
            "stage": _required(stage, "stage"), "purpose": purpose, "artifact_path": artifact_paths[0] if artifact_paths else ""})
    route = _project_route(project_id, "/review-chat")
    if action == "chat_history":
        return await _request("GET", route, params={"area": area})
    return await _request("POST", route, json={"area": area, "asset": _required(asset, "asset"), "message": _required(message, "message"),
        "title": title, "quote": quote, "locator": locator or {}})


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_jobs(
    project_id: Annotated[str, "Owned project whose latest native jobs are read"],
    action: Annotated[Literal["status"], "Read actual queued/running/completed/failed/interrupted jobs"] = "status",
    job_id: Annotated[str | None, "Optional job ID filter within the latest 20 native project jobs"] = None,
) -> dict:
    """Read the actual state and outcomes of asynchronous project operations.
    Input identifies a project and optional recent job; output retains native job status/result/error fields.
    """
    route = _project_route(project_id, "/jobs")
    value = await _transport().request("GET", route)
    if job_id:
        rows = value.get("jobs", value.get("items", [])) if isinstance(value, dict) else value
        value = next((row for row in rows if row.get("id") == job_id), {"status": "not_found_in_recent_jobs", "job_id": job_id})
    return _reply(value, route)


@workspace_api_mcp.tool()
async def workbench_settings(
    action: Annotated[Literal["get", "save"], "Read masked settings or merge explicitly supplied updates into current non-secret settings"] = "get",
    base_url: Annotated[str | None, "Optional HTTPS model API base URL"] = None,
    model: Annotated[str | None, "Optional model identifier"] = None,
    api_key: Annotated[str | None, "Optional new model API key; omitted/empty retains the saved secret"] = None,
    translation_prompt: Annotated[str | None, "Optional custom translation instruction; empty resets to the native default"] = None,
    literature_token: Annotated[str | None, "Optional new native literature token; never returned"] = None,
    literature_provider: Annotated[Literal["auto", "crossref", "semantic", "scholar", "wos"] | None, "Saved native default discovery provider"] = None,
    scholar_api_key: Annotated[str | None, "Optional new Scholar SerpApi key; never returned"] = None,
    wos_api_key: Annotated[str | None, "Optional new Web of Science key; never returned"] = None,
    web_search_api_key: Annotated[str | None, "Optional new web-search key; never returned"] = None,
    jcr_api_key: Annotated[str | None, "Optional new Clarivate metrics key; never returned"] = None,
    reviewer_mode: Annotated[Literal["inherit", "custom"] | None, "Inherit the Tutor account model or explicitly select a separate reviewer; omitted retains current mode"] = None,
    reviewer_base_url: Annotated[str | None, "Optional reviewer endpoint; omitted retains the current non-secret value"] = None,
    reviewer_model: Annotated[str | None, "Optional independent reviewer model; omitted retains the current value"] = None,
    reviewer_api_key: Annotated[str | None, "Optional new reviewer key; omitted or empty retains the server's saved secret"] = None,
    reviewer_supports_vision: Annotated[bool | None, "Declare that the configured reviewer accepts image inputs; omitted retains current choice"] = None,
) -> dict:
    """Read masked account settings or update their explicitly supplied values.
    Input contains setting changes; output is masked native configuration or saved/configured flags.
    """
    route = "/research/api/api-settings"
    current = await _transport().request("GET", route)
    if action == "get":
        return _reply(current, route)
    non_secret = {"base_url": base_url, "model": model, "translation_prompt": translation_prompt, "literature_provider": literature_provider}
    body = {key: current.get(key, "auto" if key == "literature_provider" else "") if value is None else value for key, value in non_secret.items()}
    body.update({key: value for key, value in {"api_key": api_key, "literature_token": literature_token, "scholar_api_key": scholar_api_key,
        "wos_api_key": wos_api_key, "web_search_api_key": web_search_api_key, "jcr_api_key": jcr_api_key}.items() if value is not None})
    reviewer = {"reviewer_mode": reviewer_mode, "reviewer_base_url": reviewer_base_url,
                "reviewer_model": reviewer_model, "reviewer_supports_vision": reviewer_supports_vision}
    if any(key.startswith("reviewer_") for key in current) or any(value is not None for value in reviewer.values()) or reviewer_api_key is not None:
        defaults = {"reviewer_mode": "inherit", "reviewer_supports_vision": False}
        body.update({key: current.get(key, defaults.get(key, "")) if value is None else value
                     for key, value in reviewer.items()})
    if reviewer_api_key is not None:
        body["reviewer_api_key"] = reviewer_api_key
    return await _request("PUT", route, json=body)


@workspace_api_mcp.tool()
async def workbench_author_profile(
    action: Annotated[Literal["get", "save", "preview", "institutions"], "Read/update author details, read current manuscript front matter or search real institutions"] = "get",
    project_id: Annotated[str | None, "Owned project ID required for preview"] = None,
    name: Annotated[str | None, "Author name; omitted fields retain current values on save"] = None,
    affiliation: Annotated[str | None, "Author affiliation"] = None,
    email: Annotated[str | None, "Author contact email, separate from login credentials"] = None,
    orcid: Annotated[str | None, "Author ORCID in native 0000-0000-0000-0000 format"] = None,
    address: Annotated[str | None, "Author postal address"] = None,
    name_en: Annotated[str | None, "Author English name"] = None,
    affiliation_en: Annotated[str | None, "Author English affiliation"] = None,
    q: Annotated[str | None, "Institution query for the actual native ROR search"] = None,
) -> dict:
    """Manage manuscript author metadata independently of account authentication.
    Input selects profile fields, manuscript context or institution search; output is native author data or candidates.
    """
    if action == "preview":
        return await _request("GET", _project_route(project_id, "/preview-author"))
    if action == "institutions":
        return await _request("GET", "/research/api/author-profile/institutions", params={"q": _required(q, "q")})
    route = "/research/api/author-profile"
    current = await _transport().request("GET", route)
    if action == "get":
        return _reply(current, route)
    updates = {"name": name, "affiliation": affiliation, "email": email, "orcid": orcid, "address": address, "name_en": name_en, "affiliation_en": affiliation_en}
    return await _request("PUT", route, json={key: current.get(key, "") if value is None else value for key, value in updates.items()})


@workspace_api_mcp.tool()
async def workbench_project_import(
    project_id: Annotated[str, "Owned destination project for the selected source bundle"],
    file_path: Annotated[str, "Local ZIP up to 300 MiB with workbench-import.json and the required editable DOCX manuscript"],
    action: Annotated[Literal["import"], "Submit the source-supported native material import"] = "import",
) -> dict:
    """Import a user-selected source-bound research material bundle.
    Input is the native manifest ZIP; output retains its asynchronous import job ID.
    """
    return await _upload(_project_route(project_id, "/import"), [file_path], field="file", max_mib=300)


@workspace_api_mcp.tool(annotations=_READ)
async def workbench_knowledge_search(
    project_id: Annotated[str, "Owned project limiting retrieval to its PDFs and bound native knowledge bases"],
    query: Annotated[str, "Actual source query, trimmed/truncated to 600 characters by upstream; minimum length two"],
    action: Annotated[Literal["search"], "Retrieve through the existing source-text or native semantic operation"] = "search",
    mode: Annotated[Literal["fulltext-keyword", "semantic"], "PDF/native text preview keywords or the original indexed native RAG"] = "fulltext-keyword",
    knowledge_base: Annotated[str, "Optional project-bound KB ID; required for semantic mode"] = "",
    limit: Annotated[int, "Source results from 1 to 20"] = 8,
) -> dict:
    """Retrieve source passages from the project's real PDFs or bound native index.
    Input is a scoped query/mode; output preserves native passages, coverage, errors and provenance.
    """
    return await _request("POST", _project_route(project_id, "/knowledge/search"),
                          json={"query": query, "mode": mode, "knowledge_base": knowledge_base, "limit": limit})
