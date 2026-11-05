"""Task tools bound to the Research Workbench authoring HTTP APIs."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastmcp import FastMCP

authoring_api_mcp = FastMCP(name="authoring_api")
_client: Any = None


def configure_client(client: Any) -> None:
    """Install the coordinator-owned authenticated transport."""
    global _client
    _client = client


def _transport() -> Any:
    if _client is None:
        raise RuntimeError("Configure the workbench client before calling authoring tools")
    return _client


def _required(value: Any, name: str) -> Any:
    if value is None or (isinstance(value, str) and not value):
        raise ValueError(f"{name} is required for this action")
    return value


def _project_path(project_id: str, suffix: str) -> str:
    return "/research/api/projects/" + quote(_required(project_id, "project_id"), safe="") + suffix


def _result(message: str, path: str, data: Any, artifacts: list[dict] | None = None) -> dict:
    return {"message": message, "reference": _transport().origin.rstrip("/") + path,
            "artifacts": artifacts or [], "data": data}


async def _project_call(method: str, project_id: str, suffix: str, **kwargs: Any) -> tuple[str, Any]:
    path = _project_path(project_id, suffix)
    data = await _transport().native_request(method, path, project_id, **kwargs)
    return path, data


async def _upload(project_id: str, suffix: str, file_path: str) -> tuple[str, Any]:
    source = Path(_required(file_path, "file_path")).expanduser().resolve()
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    with source.open("rb") as stream:
        return await _project_call("POST", project_id, suffix,
                                   files={"file": (source.name, stream, mime)})


async def _download(path: str, output_path: str | None, description: str,
                    params: dict | None = None) -> dict:
    target = str(Path(_required(output_path, "output_path")).expanduser().resolve())
    native = await _transport().download(path, target, params=params)
    return _result("Artifact downloaded", path, native, [{"description": description, **native}])


def _png_data(file_path: str) -> str:
    return "data:image/png;base64," + base64.b64encode(
        Path(_required(file_path, "image_path")).expanduser().resolve().read_bytes()
    ).decode("ascii")


@authoring_api_mcp.tool()
async def workbench_manuscript(
    project_id: Annotated[str, "Owned research project ID"],
    action: Annotated[Literal["get", "save", "import", "upload_asset"], "Editable manuscript operation"] = "get",
    document: Annotated[dict | None, "Existing Tiptap document and manuscript fields; save requires its revision"] = None,
    revision: Annotated[int | None, "Explicit current revision, overriding document.revision when supplied"] = None,
    reason: Annotated[str | None, "Reason retained with manuscript history"] = None,
    file_path: Annotated[str | None, "Local document to import or image asset to upload"] = None,
) -> dict:
    """Read, save or import an editable manuscript and its image assets.
    Input is a project, action and source document or file; output is the native document or upload receipt.
    """
    if action == "get":
        path, data = await _project_call("GET", project_id, "/manuscript")
    elif action == "save":
        payload = dict(_required(document, "document"))
        if revision is not None:
            payload["revision"] = revision
        _required(payload.get("revision"), "document.revision or revision")
        if reason is not None:
            payload["reason"] = reason
        path, data = await _project_call("PUT", project_id, "/manuscript", json=payload)
    else:
        suffix = "/manuscript/import" if action == "import" else "/manuscript/assets"
        path, data = await _upload(project_id, suffix, _required(file_path, "file_path"))
    return _result("Manuscript operation returned", path, data)


@authoring_api_mcp.tool()
async def workbench_manuscript_templates(
    action: Annotated[Literal["list", "preview", "source"], "Read template catalog, rendered preview or original source"] = "list",
    kind: Annotated[str | None, "Template ID returned by the actual catalog"] = None,
    output_path: Annotated[str | None, "Destination file required for preview or original source downloads"] = None,
) -> dict:
    """Inspect supported manuscript templates and retrieve their actual source or preview.
    Input is a catalog action or selected template and destination; output is native metadata or a local artifact.
    """
    if action == "list":
        path = "/research/api/manuscript-templates"
        return _result("Manuscript template catalog returned", path, await _transport().request("GET", path))
    selected = quote(_required(kind, "kind"), safe="")
    path = f"/research/api/manuscript-template-{action}/{selected}"
    return await _download(path, output_path, "Manuscript template " + action)


@authoring_api_mcp.tool()
async def workbench_manuscript_export(
    project_id: Annotated[str, "Owned research project ID"],
    format: Annotated[Literal["docx", "pdf", "tex"], "Native export format"],
    action: Annotated[Literal["export"], "Submit the existing manuscript export operation"] = "export",
    review: Annotated[bool, "Include native review annotations"] = False,
    language: Annotated[Literal["auto", "source", "translation", "reader"], "Document language basis; auto may prepare an English draft"] = "auto",
    document_id: Annotated[str, "Current reader document ID when exporting reader translation"] = "",
    columns: Annotated[Literal[1, 2], "One or two columns, preserving backend default two"] = 2,
) -> dict:
    """Submit a native manuscript export with its language and review settings.
    Input is an owned project and export settings; output is the unchanged job ID for workbench_jobs polling.
    """
    path, data = await _project_call("POST", project_id, "/manuscript/export", json={
        "format": format, "review": review, "language": language,
        "document_id": document_id, "columns": columns})
    return _result("Manuscript export submitted; poll workbench_jobs", path, data)


@authoring_api_mcp.tool()
async def workbench_export_download(
    project_id: Annotated[str, "Owned research project ID"],
    name: Annotated[str, "Exact completed export name from the native job result"],
    output_path: Annotated[str, "Explicit destination for the native export bytes"],
    area: Annotated[Literal["manuscript", "slides"], "Native export area"] = "manuscript",
    action: Annotated[Literal["download"], "Download an already completed export"] = "download",
) -> dict:
    """Download a completed manuscript or presentation artifact.
    Input is a project, export area, name and destination; output is the saved file descriptor.
    """
    await _transport().project(project_id)
    return await _download(_project_path(project_id, "/download"), output_path,
                           "Completed " + area + " export", {"area": area, "name": name})


@authoring_api_mcp.tool()
async def workbench_references(
    project_id: Annotated[str, "Owned research project ID"],
    action: Annotated[Literal["list", "add", "recommend", "replace", "related"], "Canonical citation operation"] = "list",
    reference_id: Annotated[str | None, "Stable existing reference ID for recommend, replace or related"] = None,
    entry: Annotated[dict | None, "Selected source metadata, including title and DOI"] = None,
    revision: Annotated[int | None, "Current manuscript revision required for add and replace"] = None,
    query: Annotated[str | None, "Optional real search query for replacement recommendations"] = None,
    newest: Annotated[bool, "Prefer newer available search candidates"] = False,
    instruction: Annotated[str | None, "Specific recommendation request; omitted preserves backend instruction"] = None,
    paragraph: Annotated[str | None, "Reviewed replacement paragraph preserving citation numbers"] = None,
    expected_text: Annotated[str | None, "Exact paragraph from the recommendation receipt"] = None,
    years: Annotated[Literal[0, 5, 10], "Related-paper range, zero means all years"] = 5,
    source: Annotated[str, "Actual configured search provider or auto"] = "auto",
) -> dict:
    """Maintain stable citations and request source-backed replacement or related-paper proposals.
    Input is a project and citation action with its revision or source metadata; output is the native document, proposal or state.
    """
    if action == "list":
        path, data = await _project_call("GET", project_id, "/references")
    elif action == "related":
        rid = quote(_required(reference_id, "reference_id"), safe="")
        path, data = await _project_call("GET", project_id, f"/references/{rid}/related",
                                         params={"years": years, "source": source})
    else:
        payload: dict = {}
        if action in ("add", "replace"):
            payload.update(entry=_required(entry, "entry"), revision=_required(revision, "revision"))
        if action in ("replace", "recommend"):
            payload["id"] = _required(reference_id, "reference_id")
        if action == "recommend":
            payload["newest"] = newest
            for key, value in (("query", query), ("instruction", instruction)):
                if value is not None:
                    payload[key] = value
        if action == "replace":
            for key, value in (("paragraph", paragraph), ("expected_text", expected_text)):
                if value is not None:
                    payload[key] = value
        suffix = "/references" if action == "add" else "/references/" + action
        path, data = await _project_call("POST", project_id, suffix, json=payload)
    return _result("Citation operation returned; related results may require polling", path, data)


@authoring_api_mcp.tool()
async def workbench_journals(
    action: Annotated[Literal["search", "details", "preview"], "Journal discovery, sourced details or manuscript preview"] = "search",
    query: Annotated[str, "Journal search words; empty returns generic template choices"] = "",
    journal_id: Annotated[str | None, "Selected journal ID; preview omission preserves generic-zh default"] = None,
    year: Annotated[int | None, "Optional source metric report year"] = None,
    project_id: Annotated[str | None, "Owned project required for generating a journal preview"] = None,
    columns: Annotated[Literal[1, 2], "Journal preview column count, preserving backend default one"] = 1,
) -> dict:
    """Find journals, inspect sourced metrics or generate a supported journal preview.
    Input is journal criteria or a project and selected layout; output is native metadata or a preview job ID.
    """
    if action == "preview":
        path, data = await _project_call("POST", _required(project_id, "project_id"), "/journal-preview",
                                         json={"journal": journal_id or "generic-zh", "columns": columns})
        return _result("Journal preview submitted; poll workbench_jobs", path, data)
    if action == "search":
        path, params = "/research/api/journals/search", {"q": query}
    else:
        path = "/research/api/journals/" + quote(_required(journal_id, "journal_id"), safe="")
        params = {"year": year} if year is not None else None
    return _result("Journal source metadata returned", path, await _transport().request("GET", path, params=params))


@authoring_api_mcp.tool()
async def workbench_journal_templates(
    project_id: Annotated[str, "Owned research project ID"],
    action: Annotated[Literal["search", "download", "file"], "Discover official candidates, retain a selected package or fetch its file"] = "search",
    journal: Annotated[str | None, "Journal ID required for source discovery and selected candidate download"] = None,
    template_id: Annotated[str | None, "Actual cached template candidate ID for download"] = None,
    name: Annotated[str | None, "Exact retained template filename for file retrieval"] = None,
    output_path: Annotated[str | None, "Destination file required for retrieving retained template bytes"] = None,
) -> dict:
    """Discover and retain original official journal author-template packages.
    Input is a journal or cached candidate selection; output is source provenance, a receipt or the original local file.
    """
    if action == "file":
        await _transport().project(project_id)
        return await _download(_project_path(project_id, "/journal-templates/file"), output_path,
                               "Original journal template package", {"name": _required(name, "name")})
    payload = {"journal": _required(journal, "journal")}
    if action == "download":
        payload["template"] = _required(template_id, "template_id")
    path, data = await _project_call("POST", project_id, "/journal-templates/" + action, json=payload)
    return _result("Official template source operation returned", path, data)


@authoring_api_mcp.tool()
async def workbench_figure(
    project_id: Annotated[str, "Owned research project ID"],
    path: Annotated[str, "Image path relative to the project's program directory"],
    action: Annotated[Literal["inspect", "preview", "save"], "Inspect actual plot objects, preview changes or save them"] = "inspect",
    revision: Annotated[int | None, "Actual inspected figure revision required for preview/save"] = None,
    changes: Annotated[dict | None, "Native figure, objects and layout patches using actual inspected object IDs"] = None,
    start_edit_session: Annotated[bool, "Create the backend figure editing session during inspection"] = False,
    edit_session: Annotated[str, "Existing editing-session ID for preview/save"] = "",
    reason: Annotated[str, "Reason saved with figure history"] = "调整图形样式",
    autosave: Annotated[bool, "Native figure save flag"] = False,
    include_context: Annotated[bool, "Also return native image/manuscript/source-program context during inspection"] = False,
) -> dict:
    """Inspect, preview and save actual registered Matplotlib figure objects.
    Input is a project image and source-supported revisioned patches; output is native figure state or its save receipt.
    """
    if action == "inspect":
        route, data = await _project_call("GET", project_id, "/figure", params={"path": path, "edit_session": start_edit_session})
        if include_context:
            _, context = await _project_call("GET", project_id, "/image-context", params={"path": path})
            data = {"figure": data, "context": context}
    else:
        payload = {"path": path, "revision": _required(revision, "revision"),
                   "changes": _required(changes, "changes"), "edit_session": edit_session,
                   "reason": reason, "autosave": autosave}
        route, data = await _project_call("POST", project_id, "/figure/" + action, json=payload)
    return _result("Figure operation returned; unregistered images remain raster", route, data)


@authoring_api_mcp.tool()
async def workbench_figure_chat(
    project_id: Annotated[str, "Owned research project ID"],
    path: Annotated[str, "Current project image path"],
    action: Annotated[Literal["history", "send", "session"], "Read image discussion, send a request or inspect an associated session"] = "history",
    message: Annotated[str | None, "Request required for send; model-backed replies retain source limits"] = None,
    revision: Annotated[int, "Current native figure revision"] = 0,
    selection: Annotated[list[str] | None, "Actual selected plot object IDs"] = None,
    changes: Annotated[dict | None, "Current unsaved native figure patches"] = None,
    image_path: Annotated[str | None, "Optional local PNG snapshot for the native discussion"] = None,
    edit_session: Annotated[str, "Current backend figure edit-session ID"] = "",
    include_context: Annotated[bool, "Include actual figure/source context in the model request"] = True,
    session_id: Annotated[str | None, "Existing session previously associated with this figure"] = None,
) -> dict:
    """Read or continue source-bound figure conversations and linked agent replies.
    Input is an image, discussion action and optional selected objects; output is native messages, proposal or session state.
    """
    if action == "history":
        route, data = await _project_call("GET", project_id, "/figure/chat", params={"path": path})
    elif action == "session":
        route, data = await _project_call("GET", project_id, "/figure/session",
                                         params={"path": path, "session_id": _required(session_id, "session_id")})
    else:
        payload = {"path": path, "message": _required(message, "message"), "revision": revision,
                   "selection": selection if selection is not None else [],
                   "changes": changes if changes is not None else {}, "edit_session": edit_session,
                   "include_context": include_context}
        if image_path is not None:
            payload["image"] = _png_data(image_path)
        route, data = await _project_call("POST", project_id, "/figure/chat", json=payload)
    return _result("Figure discussion operation returned", route, data)


@authoring_api_mcp.tool()
async def workbench_image_review(
    project_id: Annotated[str, "Owned research project ID"],
    path: Annotated[str, "Existing image path relative to the project program directory"],
    image_path: Annotated[str, "Local PNG review image or cropped screenshot"],
    instruction: Annotated[str, "Actual image-review request"],
    action: Annotated[Literal["review"], "Prepare or submit the existing native image-review operation"] = "review",
    plot_program: Annotated[str, "Optional actual project-relative plotting source"] = "",
    compute_program: Annotated[str, "Optional actual project-relative computation source"] = "",
    crop: Annotated[dict | None, "Native crop locator, if present"] = None,
    annotations: Annotated[list[dict] | None, "Native image annotation records"] = None,
    send: Annotated[bool, "Submit to the native agent; false saves only a prepared review"] = True,
) -> dict:
    """Prepare or submit an image review retaining source programs and annotations.
    Input is a project image, local PNG and request; output is the native prepared-review or agent receipt.
    """
    route, data = await _project_call("POST", project_id, "/image-review", json={
        "path": path, "image": _png_data(image_path), "instruction": instruction,
        "plot_program": plot_program, "compute_program": compute_program, "crop": crop,
        "annotations": annotations if annotations is not None else [], "send": send})
    return _result("Image review operation returned", route, data)


@authoring_api_mcp.tool()
async def workbench_raster(
    project_id: Annotated[str, "Owned research project ID"],
    path: Annotated[str, "Existing bitmap path relative to the project program directory"],
    image_path: Annotated[str, "Local complete PNG containing edited pixels"],
    action: Annotated[Literal["save"], "Save pixels through the existing version-preserving image endpoint"] = "save",
    expected_modified: Annotated[float | None, "Original file timestamp for optimistic conflict detection"] = None,
) -> dict:
    """Save edited bitmap pixels while retaining the previous native image version.
    Input is a project image, local PNG and optional timestamp; output is the native save receipt or conflict.
    """
    payload: dict = {"path": path, "image": _png_data(image_path)}
    if expected_modified is not None:
        payload["expected_modified"] = expected_modified
    route, data = await _project_call("POST", project_id, "/image/save", json=payload)
    return _result("Raster save returned", route, data)


@authoring_api_mcp.tool()
async def workbench_slide_templates(
    project_id: Annotated[str, "Owned research project ID"],
    action: Annotated[Literal["list", "upload", "prepare", "select", "roles"], "Inspect or configure a project-private presentation template"] = "list",
    template: Annotated[str | None, "Actual catalog template ID; roles requires uploaded"] = None,
    file_path: Annotated[str | None, "Local editable PPTX required for upload"] = None,
    roles: Annotated[dict | None, "Native role-to-page mapping for an uploaded template"] = None,
) -> dict:
    """Inspect, upload, prepare and configure the original presentation templates.
    Input is a project and template lifecycle action; output is the native catalog, manifest, selection or preparation job ID.
    """
    if action == "list":
        route, data = await _project_call("GET", project_id, "/slide-templates")
    elif action == "upload":
        route, data = await _upload(project_id, "/slide-templates", _required(file_path, "file_path"))
    elif action == "select":
        route, data = await _project_call("PUT", project_id, "/slide-template", json={"template": _required(template, "template")})
    else:
        kind = quote(_required(template, "template"), safe="")
        if action == "prepare":
            route, data = await _project_call("POST", project_id, f"/slide-templates/{kind}/prepare")
        else:
            route, data = await _project_call("PATCH", project_id, f"/slide-templates/{kind}/roles", json=_required(roles, "roles"))
    return _result("Slide template operation returned; preparation jobs require polling", route, data)


@authoring_api_mcp.tool()
async def workbench_slides(
    project_id: Annotated[str, "Owned research project ID"],
    action: Annotated[Literal["confirm", "get", "save", "plan", "export", "preview"], "Native slide plan, confirmation, export or preview operation"] = "get",
    template: Annotated[str | None, "Actual selected template; confirm only after the user's choice"] = None,
    profile: Annotated[Literal["group", "conference", "project", "proposal", "defense", "literature"] | None, "User-selected audience and purpose required for confirm"] = None,
    confirmation_action: Annotated[Literal["generate", "restyle"], "Native confirmation operation"] = "generate",
    plan: Annotated[dict | None, "Existing editable slide plan with sections and applicable confirmation ID"] = None,
    instruction: Annotated[str, "Specific instructions for model-backed slide planning"] = "",
    length: Annotated[str, "Native planning length, normally short, medium or long"] = "medium",
    use_native: Annotated[bool, "Use the assigned native model for planning"] = True,
    confirmation_id: Annotated[str, "Current explicit confirmation receipt required by the backend"] = "",
    kind: Annotated[str, "deck or a catalog template ID for a rendered preview"] = "deck",
    page: Annotated[int, "One-based actual rendered page number"] = 1,
    output_path: Annotated[str | None, "Destination PNG required for preview"] = None,
) -> dict:
    """Manage audience-confirmed slide content and its original editable exports.
    Input is a project and explicit slide lifecycle action; output is native plan, confirmation, job ID or preview artifact.
    """
    if action == "get":
        route, data = await _project_call("GET", project_id, "/slides")
    elif action == "save":
        route, data = await _project_call("PUT", project_id, "/slides", json=_required(plan, "plan"))
    elif action == "confirm":
        route, data = await _project_call("POST", project_id, "/slides/confirm", json={
            "template": _required(template, "template"), "profile": _required(profile, "profile"), "action": confirmation_action})
    elif action == "plan":
        route, data = await _project_call("POST", project_id, "/slides/plan", json={
            "instruction": instruction, "length": length, "use_native": use_native, "confirmation_id": confirmation_id})
    elif action == "export":
        route, data = await _project_call("POST", project_id, "/slides/export")
    else:
        await _transport().project(project_id)
        return await _download(_project_path(project_id, "/slide-preview"), output_path,
                               "Rendered slide page", {"kind": kind, "page": page})
    return _result("Slide operation returned; job IDs require workbench_jobs polling", route, data)
