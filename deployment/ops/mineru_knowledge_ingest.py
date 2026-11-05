"""Resume MinerU cloud parsing inside the existing deeptutor container.

Credentials are resolved only by the existing production config adapter.  This
script never serializes them.  Private job state holds temporary signed URLs;
export only derived artifacts and public-summary.json to the local workspace.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import tarfile
import time
import zipfile


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_message(value: object, secrets: list[str] = ()) -> str:
    message = str(value)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[redacted]")
    return re.sub(r"https?://[^\s\"']+", "[url omitted]", message)[:1200]


def config_snapshot(config) -> dict:
    return {key: getattr(config, key) for key in (
        "mode", "api_base_url", "model_version", "language", "enable_formula",
        "enable_table", "is_ocr", "max_pages_per_part", "normalize_tiny_scans")}


def event(root: Path, kind: str, **data) -> None:
    row = {"at": now(), "event": kind, **data}
    root.mkdir(parents=True, exist_ok=True)
    with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)


def input_mapping(manifest: dict | None, page_count: int, source_id: str) -> dict[int, dict]:
    if manifest is None:
        return {i: {"source_id": source_id, "source_pdf_page": i + 1} for i in range(page_count)}
    rows = manifest.get("pages", [])
    mapping = {}
    for row in rows:
        index = row.get("sample_pdf_page")
        source_page = row.get("source_pdf_page")
        if type(index) is not int or index < 1 or index > page_count or index - 1 in mapping:
            raise ValueError("Manifest has a duplicate or invalid sample page")
        if type(source_page) is not int or source_page < 1 or not row.get("source_id"):
            raise ValueError("Manifest has an invalid original-page locator")
        mapping[index - 1] = {"source_id": row["source_id"], "source_pdf_page": source_page}
    if len(mapping) != page_count:
        raise ValueError("Manifest must locate every input PDF page")
    return mapping


def ensure_archive(source: Path, part: Path, config, cloud, client, key_pool,
                   *, timeout: float, poll_interval: float) -> dict:
    """Resume a known batch; never re-submit a job after an ambiguous POST."""
    part.mkdir(parents=True, exist_ok=True)
    state_path = part / "private-state.json"
    archive = part / "original-result.zip"
    state = read_json(state_path) if state_path.exists() else {"created_at": now()}
    if archive.exists():
        with zipfile.ZipFile(archive) as check:
            if check.testzip() is not None:
                raise ValueError("Saved result ZIP has a corrupt member")
        return state
    if not state.get("batch_id"):
        if state.get("stage") in {"requesting_slot", "submit_unknown"}:
            raise RuntimeError("Upload-slot request outcome is unknown; do not create a replacement batch")
        state.update(stage="requesting_slot", source_sha256=file_digest(source))
        write_json(state_path, state)
        try:
            batch_id, upload_url = cloud._request_upload(client, source, config, key_pool)
        except Exception:
            state["stage"] = "submit_unknown"
            write_json(state_path, state)
            raise
        state.update(stage="slot_created", batch_id=batch_id, upload_url=upload_url,
                     slot_created_at=now())
        write_json(state_path, state)
        event(part, "batch_created", batch_id=batch_id)
    deadline = time.monotonic() + timeout
    last_state = None
    failures = 0
    while True:
        try:
            payload = cloud._get_json(client, "/api/v4/extract-results/batch/" + state["batch_id"], key_pool)
            write_json(part / "private-api-last-result.json", payload)
            entry = cloud._match_entry((payload.get("data") or {}).get("extract_result") or [], source.name)
            api_state = str((entry or {}).get("state") or "waiting-file").lower()
            if api_state != last_state:
                event(part, "cloud_state", batch_id=state["batch_id"], state=api_state,
                      progress=(entry or {}).get("extract_progress") or {})
                last_state = api_state
            if api_state == "done":
                state.update(stage="done", done_at=state.get("done_at") or now(),
                             zip_url=str((entry or {}).get("full_zip_url") or ""))
                write_json(state_path, state)
                if not state["zip_url"]:
                    raise RuntimeError("Cloud reports done without an archive URL")
                data = cloud._download(state["zip_url"])
                temporary = archive.with_suffix(".zip.tmp")
                temporary.write_bytes(data)
                with zipfile.ZipFile(temporary) as check:
                    if check.testzip() is not None:
                        raise RuntimeError("Downloaded ZIP has a corrupt member")
                temporary.replace(archive)
                state.update(stage="archive_saved", archive_bytes=len(data), downloaded_at=now())
                write_json(state_path, state)
                event(part, "archive_saved", batch_id=state["batch_id"], bytes=len(data))
                return state
            if api_state == "failed":
                state.update(stage="cloud_failed", failed_at=now())
                write_json(state_path, state)
                raise RuntimeError("Cloud parsing failed: " + safe_message((entry or {}).get("err_msg"), config.api_keys))
            if not state.get("upload_completed") and api_state in {"waiting-file", "waiting_file", ""}:
                state["stage"] = "uploading"
                write_json(state_path, state)
                cloud._upload_file(source, state["upload_url"])
                state.update(stage="uploaded", upload_completed=True, uploaded_at=now())
                write_json(state_path, state)
                event(part, "uploaded", batch_id=state["batch_id"], bytes=source.stat().st_size)
            failures = 0
        except Exception as exc:
            message = safe_message(exc, config.api_keys)
            # Authentication/business failures are not fixed by blind retries.
            transient = any(word in message.lower() for word in (
                "timed out", "timeout", "connect", "network", "http 50", "temporarily", "remoteprotocol"))
            if not transient or failures >= 3:
                raise
            failures += 1
            event(part, "transient_network_error", attempt=failures, message=message,
                  batch_id=state["batch_id"])
            time.sleep(min(3 * failures, 9))
        if time.monotonic() >= deadline:
            state.update(stage="poll_wait_timeout", last_wait_at=now())
            write_json(state_path, state)
            raise TimeoutError("Polling wait expired; resume the recorded batch, do not submit a replacement")
        time.sleep(poll_interval)


def block_markdown(block: dict, asset_prefix: str, raw: Path | None = None) -> str:
    kind = block.get("type", "")
    if kind == "text":
        level = block.get("text_level")
        prefix = "#" * min(max(level, 1), 6) + " " if type(level) is int and level > 0 else ""
        return prefix + str(block.get("text") or "")
    if kind in {"equation", "interline_equation"}:
        return "$$\n" + str(block.get("text") or "") + "\n$$"
    if kind == "list":
        return "\n".join("- " + str(item) for item in block.get("list_items", []))
    pieces = []
    if block.get("img_path"):
        pieces.append("![](" + asset_prefix + str(block["img_path"]) + ")")
    for key in ("image_caption", "table_caption", "table_body", "image_footnote", "table_footnote", "text"):
        value = block.get(key)
        if value:
            pieces.append("\n".join(map(str, value)) if isinstance(value, list) else str(value))
    text = "\n\n".join(pieces)
    if raw is not None:
        def materialize_reference(match):
            reference = match.group(2)
            if reference.startswith(("http://", "https://", "data:")):
                return match.group(0)
            relative = reference if (raw/reference).is_file() else "images/" + reference
            if (raw/relative).is_file():
                return match.group(1) + asset_prefix + relative + match.group(3)
            return match.group(0)
        text = re.sub(r'(<img\b[^>]*?\bsrc=["\x27])([^"\x27]+)(["\x27])',
                      materialize_reference, text, flags=re.I)
    return text


def map_content(items: list, mapping: dict[int, dict], offset: int, part_pages: int,
                raw: Path, job: Path, part_name: str) -> list[dict]:
    pages = {}
    for ordinal, original in enumerate(items):
        if not isinstance(original, dict):
            raise ValueError("Unsupported content-list shape; expected flat block objects")
        index = original.get("page_idx")
        if type(index) is not int or not 0 <= index < part_pages:
            raise ValueError("Content block page_idx lies outside its slice")
        source_index = offset + index
        locator = mapping[source_index]
        page = pages.setdefault(source_index, {"input_pdf_page": source_index + 1,
             **locator, "blocks": [], "assets": [], "text": "", "review_status": "unreviewed"})
        block = {"block_index": ordinal, "part": part_name, "slice_page_idx": index,
                 "locator": f"{locator['source_id']}:pdf-page:{locator['source_pdf_page']}:block:{ordinal}",
                 "original": original}
        page["blocks"].append(block)
        if original.get("img_path"):
            asset = str(original["img_path"])
            target = raw / asset
            page["assets"].append({"path": str(target.relative_to(job)).replace("\\", "/"),
                                    "exists": target.is_file(), "block_index": ordinal})
        prefix = "../" + str(raw.relative_to(job)).replace("\\", "/") + "/"
        text = block_markdown(original, prefix, raw)
        page["text"] += ("\n\n" if page["text"] else "") + text
    return [pages[index] for index in sorted(pages)]


def preproc_content(layout: dict, part_pages: int) -> list[dict]:
    """Keep physical-page ownership before MinerU's cross-page paragraph merge.

    This is automatic structural recovery only.  It never fills missing OCR
    words from context, another book, or human edits.
    """
    pages = layout.get("pdf_info")
    if not isinstance(pages, list) or len(pages) != part_pages:
        raise ValueError("Layout does not cover every physical slice page")
    result = []

    def spans(node):
        if isinstance(node, dict):
            if isinstance(node.get("spans"), list):
                yield from node["spans"]
            else:
                for value in node.values():
                    yield from spans(value)
        elif isinstance(node, list):
            for value in node:
                yield from spans(value)

    seen = set()
    for page in pages:
        index = page.get("page_idx")
        if type(index) is not int or index in seen or not 0 <= index < part_pages:
            raise ValueError("Layout contains a duplicate or invalid page index")
        seen.add(index)
        for block_index, block in enumerate(page.get("preproc_blocks", [])):
            for span_index, span in enumerate(spans(block)):
                kind = span.get("type")
                item = {"page_idx": index, "bbox": span.get("bbox", block.get("bbox")),
                        "preproc_block_index": block_index, "preproc_span_index": span_index,
                        "origin": "layout.preproc_blocks"}
                if kind == "table":
                    item.update(type="table", table_body=span.get("html", ""))
                elif kind == "image":
                    item.update(type="image")
                else:
                    item.update(type="text", text=span.get("content", ""))
                    if block.get("type") == "title":
                        item["text_level"] = block.get("level", 2)
                if span.get("image_path"):
                    asset = str(span["image_path"])
                    item["img_path"] = asset if asset.startswith("images/") else "images/" + asset
                if item.get("text") or item.get("table_body") or item.get("img_path"):
                    result.append(item)
    return result


def write_page_outputs(derived: Path, stem: str, source_id: str, page_count: int,
                       pages: list[dict], **metadata) -> None:
    write_json(derived / (stem + ".json"), {"source_id": source_id, "input_pages": page_count,
                                            **metadata, "pages": pages})
    markdown = []
    for page in pages:
        markdown.append(f"<!-- source:{page['source_id']}; pdf_page:{page['source_pdf_page']}; input_page:{page['input_pdf_page']} -->\n\n" + page["text"])
    (derived / (stem + ".md")).write_text("\n\n---\n\n".join(markdown) + "\n", encoding="utf-8")


def structure_probes(physical_pages: list[dict], legacy_pages: list[dict], expected: int) -> dict:
    """Flag missing/fragmented/relocated content without claiming OCR accuracy."""
    normalized = lambda text: " ".join(str(text).split())
    legacy = {p["input_pdf_page"]: normalized(p["text"]) for p in legacy_pages}
    rows, relocations = [], []
    for page in physical_pages:
        flags = []
        short_blocks = sum(0 < len(str(b["original"].get("text", "")).strip()) < 40
                           for b in page["blocks"])
        if short_blocks >= 8:
            flags.append("fragmented_short_text_layout_needs_visual_review")
        if page["assets"]:
            flags.append("visual_or_table_content_needs_visual_review")
        if any(not a["exists"] for a in page["assets"]):
            flags.append("missing_referenced_asset")
        for block in page["blocks"]:
            text = normalized(block["original"].get("text", ""))
            if len(text) >= 70 and text not in legacy.get(page["input_pdf_page"], ""):
                elsewhere = [number for number, body in legacy.items()
                             if number != page["input_pdf_page"] and text in body]
                if elsewhere:
                    relocations.append({"physical_input_pdf_page": page["input_pdf_page"],
                        "source_id": page["source_id"], "source_pdf_page": page["source_pdf_page"],
                        "legacy_input_pdf_pages": elsewhere, "text_preview": text[:100]})
                    flags.append("legacy_cross_page_text_relocation")
        page["risk_flags"] = sorted(set(flags))
        rows.append({key: page[key] for key in ("input_pdf_page", "source_id", "source_pdf_page", "review_status", "risk_flags")}
                    | {"block_count": len(page["blocks"]), "short_text_blocks": short_blocks,
                       "asset_count": len(page["assets"]), "text_characters": len(page["text"])})
    represented = {p["input_pdf_page"] for p in physical_pages}
    return {"scope": "Structural probes only; flags and coverage do not establish text accuracy",
            "expected_input_pages": expected, "represented_pages": len(represented),
            "pages_without_content_blocks": sorted(set(range(1, expected + 1)) - represented),
            "cross_page_relocations_in_legacy": relocations, "pages": rows}


def run_cloud(args) -> None:
    # These imports intentionally occur only on the production server.
    import httpx
    from pypdf import PdfReader, PdfWriter
    from deeptutor.services.keypool import KeyPool
    from deeptutor.services.parsing.engines.mineru import cloud
    from deeptutor.services.parsing.engines.mineru.config import resolve_mineru_config

    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    config = resolve_mineru_config()
    if not config.is_cloud or not config.api_keys:
        raise RuntimeError("Existing production MinerU cloud configuration is unavailable")
    source = Path(args.input).resolve()
    root = Path(args.root).resolve()
    job = root / "jobs" / args.source_id
    job.mkdir(parents=True, exist_ok=True)
    lock = job / "running.lock"
    # A stopped process releases the OS advisory lock; the inode stays reusable.
    import fcntl
    with lock.open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pdf_logger = logging.getLogger("pypdf")
        previous_propagate = pdf_logger.propagate
        warning_handler = logging.FileHandler(job / "input-warnings.log", encoding="utf-8")
        warning_handler.setLevel(logging.WARNING)
        pdf_logger.addHandler(warning_handler)
        pdf_logger.propagate = False
        try:
            reader = PdfReader(source)
        finally:
            pdf_logger.removeHandler(warning_handler)
            pdf_logger.propagate = previous_propagate
            warning_handler.close()
        page_count = len(reader.pages)
        if getattr(args, "expected_pages", None) is not None and page_count != args.expected_pages:
            raise RuntimeError("Transferred PDF page count does not match the approved batch plan")
        mapping = input_mapping(read_json(Path(args.manifest)) if args.manifest else None,
                                page_count, args.source_id)
        identity = {"source_id": args.source_id, "source_sha256": file_digest(source),
                    "input_pages": page_count, "config": config_snapshot(config),
                    "max_pages_per_part": min(args.max_pages, config.max_pages_per_part)}
        if getattr(args, "expected_sha256", None) and identity["source_sha256"] != args.expected_sha256:
            raise RuntimeError("Transferred PDF bytes do not match the approved source fingerprint")
        identity_path = job / "identity.json"
        if identity_path.exists() and read_json(identity_path) != identity:
            raise RuntimeError("Job input or parser settings changed; select a different source_id")
        write_json(identity_path, identity)
        write_json(job / "page-map.json", {"pages": list(mapping.values())})
        started = time.monotonic()
        event(job, "run_started", source_id=args.source_id, input_pages=page_count,
              parser=config_snapshot(config))
        all_pages, physical_pages, part_summaries = [], [], []
        prior_summary_path = job / "public-summary.json"
        prior_summary = read_json(prior_summary_path) if prior_summary_path.exists() else {}
        request_directory = job / "request-payloads"

        def capture_submission(request):
            if request.method == "POST" and request.url.path == "/api/v4/file-urls/batch":
                request_directory.mkdir(exist_ok=True)
                number = len(list(request_directory.glob("*.json"))) + 1
                write_json(request_directory / f"submit-{number:03d}.json", {
                    "at": now(), "path": request.url.path,
                    "authorization_present": bool(request.headers.get("Authorization")),
                    "body": json.loads(request.content)})

        try:
            with httpx.Client(base_url=config.api_base_url.rstrip("/"),
                              headers={"Accept": "application/json"},
                              event_hooks={"request": [capture_submission]}) as client:
                pool = KeyPool(config.api_keys)
                for start in range(0, page_count, identity["max_pages_per_part"]):
                    remaining = (getattr(args, "deadline", None) or float("inf")) - time.monotonic()
                    if remaining < 30:
                        raise TimeoutError("Batch wall budget reached before the next slice; resume without replacing existing tasks")
                    end = min(start + identity["max_pages_per_part"], page_count)
                    name = f"p{start + 1:04d}-{end:04d}"
                    part = job / "parts" / name
                    part.mkdir(parents=True, exist_ok=True)
                    if page_count <= identity["max_pages_per_part"]:
                        part_source = source
                    else:
                        part_source = part / (args.source_id + "-" + name + ".pdf")
                        if not part_source.exists():
                            writer = PdfWriter()
                            for index in range(start, end):
                                writer.add_page(reader.pages[index])
                            with part_source.open("wb") as stream:
                                writer.write(stream)
                    state = ensure_archive(part_source, part, config, cloud, client, pool,
                                           timeout=min(args.timeout, remaining), poll_interval=args.poll_interval)
                    raw = part / "raw"
                    if not (part / "extracted.json").exists():
                        raw.mkdir(exist_ok=True)
                        cloud._extract_archive((part / "original-result.zip").read_bytes(), raw)
                        write_json(part / "extracted.json", {"at": now()})
                    lists = sorted(p for p in raw.rglob("*_content_list.json") if p.is_file())
                    if len(lists) != 1:
                        raise RuntimeError("Expected one legacy MinerU content list in result ZIP")
                    content_path = lists[0]
                    items = json.loads(content_path.read_text(encoding="utf-8"))
                    mapped = map_content(items, mapping, start, end - start,
                                         content_path.parent, job, name)
                    all_pages.extend(mapped)
                    layout_path = content_path.parent / "layout.json"
                    producer = {}
                    if layout_path.exists():
                        layout = read_json(layout_path)
                        physical_pages.extend(map_content(preproc_content(layout, end - start),
                            mapping, start, end - start, content_path.parent, job, name))
                        producer = {key: layout.get(key) for key in (
                            "_version_name", "_backend", "_effort", "_ocr_enable")}
                    part_summaries.append({"part": name, "input_pdf_page_start": start + 1,
                        "input_pdf_page_end": end, "batch_id": state.get("batch_id"),
                        "created_at": state.get("created_at"), "uploaded_at": state.get("uploaded_at"),
                        "done_at": state.get("done_at"), "downloaded_at": state.get("downloaded_at"),
                        "archive_bytes": (part / "original-result.zip").stat().st_size,
                        "observed_producer": producer,
                        "raw_relative": str(raw.relative_to(job)).replace("\\", "/")})
            derived = job / "derived"
            derived.mkdir(exist_ok=True)
            write_json(derived / "pages.json", {"source_id": args.source_id, "input_pages": page_count,
                                                "pages": all_pages})
            write_page_outputs(derived, "knowledge", args.source_id, page_count, all_pages,
                               derivation="cloud content_list; cross-page merging may alter page attribution")
            if physical_pages:
                write_json(derived / "structure-probes.json", structure_probes(physical_pages, all_pages, page_count))
                write_page_outputs(derived, "page-faithful", args.source_id, page_count, physical_pages,
                    derivation="layout.preproc_blocks; physical-page ownership retained before cross-page merge",
                    human_corrections_applied=False)
            represented = {page["input_pdf_page"] for page in all_pages}
            summary = {"status": "parsed_requires_content_review", "finished_at": now(),
                       **identity, "elapsed_this_run_seconds": round(time.monotonic() - started, 3),
                       "first_success_elapsed_seconds": prior_summary.get("first_success_elapsed_seconds",
                            prior_summary.get("elapsed_this_run_seconds", round(time.monotonic() - started, 3))),
                       "represented_pages": sorted(represented),
                       "pages_without_content_blocks": sorted(set(range(1, page_count + 1)) - represented),
                       "parts": part_summaries,
                       "asset_count": sum(len(page["assets"]) for page in all_pages),
                       "missing_asset_count": sum(not asset["exists"] for page in all_pages for asset in page["assets"]),
                       "external_upload": True, "content_quality_passed": False}
            write_json(job / "public-summary.json", summary)
            event(job, "parsed", source_id=args.source_id, represented_pages=len(represented),
                  elapsed_seconds=summary["elapsed_this_run_seconds"])
        except Exception as exc:
            error = {"status": "incomplete_resume_existing_batch", "at": now(),
                     "source_id": args.source_id, "error_type": type(exc).__name__,
                     "message": safe_message(exc, config.api_keys)}
            write_json(job / "public-summary.json", error)
            event(job, "incomplete", **error)
            raise RuntimeError(error["message"]) from None


def make_plan(args) -> None:
    from pypdf import PdfReader
    registry = read_json(Path(args.registry))
    documents = []
    for source in registry["sources"]:
        if source.get("kind") != "writing_reference":
            continue
        path = Path(source["local_path"])
        count = len(PdfReader(path).pages)
        documents.append({"source_id": source["id"], "local_input": str(path),
            "remote_input": str(Path(args.remote_root) / "inputs" / (source["id"] + ".pdf")).replace("\\", "/"),
            "pages": count, "bytes": path.stat().st_size,
            "parts": [{"first_pdf_page": i + 1, "last_pdf_page": min(i + 180, count)} for i in range(0, count, 180)]})
    write_json(Path(args.output), {"status": "prepared_not_started", "root": args.remote_root,
               "documents": documents, "total_pages": sum(d["pages"] for d in documents),
               "execution": "cloud-run per document; resume same source_id/root after interruptions"})


def public_status(root: Path) -> dict:
    jobs = []
    for job in sorted((root / "jobs").glob("*")):
        if not job.is_dir():
            continue
        item = {"source_id": job.name, "parts": []}
        if (job / "public-summary.json").exists():
            item["summary"] = read_json(job / "public-summary.json")
        for part in sorted((job / "parts").glob("*")):
            path = part / "private-state.json"
            if path.exists():
                state = read_json(path)
                row = {key: state.get(key) for key in (
                    "stage", "batch_id", "created_at", "uploaded_at", "done_at", "archive_bytes")}
                row["part"] = part.name
                if (part / "private-api-last-result.json").exists():
                    payload = read_json(part / "private-api-last-result.json")
                    entries = (payload.get("data") or {}).get("extract_result") or []
                    if entries:
                        row["cloud_state"] = entries[0].get("state")
                        row["progress"] = entries[0].get("extract_progress") or {}
                item["parts"].append(row)
        jobs.append(item)
    return {"root": str(root), "at": now(), "jobs": jobs}


def run_batch(args) -> int:
    import fcntl
    plan = read_json(Path(args.plan))
    root = Path(plan["root"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "batch-running.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.monotonic()
        deadline = started + args.wall_budget
        progress = {"workflow_id": "mineru-three-writing-books-20261102-v1", "started_at": now(),
                    "status": "running", "concurrency": 1, "wall_budget_seconds": args.wall_budget,
                    "ordered_sources": [d["source_id"] for d in plan["documents"]], "completed_sources": []}
        path = root / "batch-progress.json"
        write_json(path, progress)
        for document in plan["documents"]:
            progress.update(current_source=document["source_id"], updated_at=now())
            write_json(path, progress)
            event(root, "book_started", workflow_id=progress["workflow_id"], source_id=document["source_id"])
            call = argparse.Namespace(input=document["remote_input"], source_id=document["source_id"],
                root=str(root), manifest=None, max_pages=180, timeout=args.timeout,
                poll_interval=args.poll_interval, deadline=deadline, expected_pages=document["pages"],
                expected_sha256=document.get("source_sha256"))
            try:
                run_cloud(call)
            except Exception as exc:
                progress.update(status="incomplete_resume_existing_batches", updated_at=now(),
                    elapsed_seconds=round(time.monotonic()-started, 3),
                    error_type=type(exc).__name__, message=safe_message(exc))
                write_json(path, progress)
                event(root, "batch_incomplete", source_id=document["source_id"], message=progress["message"])
                return 2
            progress["completed_sources"].append(document["source_id"])
            write_json(path, progress)
        progress.update(status="parsed_all_requires_content_review", updated_at=now(),
                        elapsed_seconds=round(time.monotonic()-started, 3))
        write_json(path, progress)
        event(root, "batch_parsed", completed_sources=progress["completed_sources"],
              elapsed_seconds=progress["elapsed_seconds"])
        return 0


def markdown_headings(text: str, source_id: str, source_url: str) -> list[dict]:
    lines = text.splitlines()
    headings = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append({"locator": f"{source_id}:heading:{len(headings)+1}",
                "level": len(match.group(1)), "title": match.group(2),
                "markdown_start_line": number, "source_url": source_url})
    if not headings:
        headings = [{"locator": f"{source_id}:document", "level": 0, "title": "Document",
                     "markdown_start_line": 1, "source_url": source_url}]
    for index, heading in enumerate(headings):
        heading["markdown_end_line"] = (headings[index+1]["markdown_start_line"]-1
                                          if index+1 < len(headings) else len(lines))
    return headings


def run_html(args) -> None:
    """Send original HTML to the documented MinerU-HTML cloud lane directly."""
    import fcntl
    import httpx
    from deeptutor.services.keypool import KeyPool
    from deeptutor.services.parsing.engines.mineru import cloud
    from deeptutor.services.parsing.engines.mineru.config import resolve_mineru_config

    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    original_config = resolve_mineru_config()
    config = replace(original_config, model_version="MinerU-HTML")
    if not config.is_cloud or not config.api_keys:
        raise RuntimeError("Existing production cloud configuration is unavailable")
    source = Path(args.input).resolve()
    if source.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("html-run requires an original HTML file")
    job = Path(args.root).resolve() / "jobs" / args.source_id
    job.mkdir(parents=True, exist_ok=True)
    with (job / "running.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        identity = {"source_id": args.source_id, "source_sha256": file_digest(source),
                    "source_url": args.source_url, "source_format": "html",
                    "input_scope": args.input_scope,
                    "config": config_snapshot(config)}
        if (job / "identity.json").exists() and read_json(job / "identity.json") != identity:
            raise RuntimeError("HTML source/config changed; select a new source_id")
        write_json(job / "identity.json", identity)
        started = time.monotonic()
        part = job / "parts/document"
        event(job, "html_started", source_id=args.source_id, source_url=args.source_url,
              model_version="MinerU-HTML")
        try:
            with httpx.Client(base_url=config.api_base_url.rstrip("/"), headers={"Accept": "application/json"}) as client:
                state = ensure_archive(source, part, config, cloud, client, KeyPool(config.api_keys),
                                       timeout=args.timeout, poll_interval=args.poll_interval)
            raw = part / "raw"
            if not (part / "extracted.json").exists():
                raw.mkdir(parents=True, exist_ok=True)
                cloud._extract_archive((part / "original-result.zip").read_bytes(), raw)
                write_json(part / "extracted.json", {"at": now()})
            markdown_files = sorted(raw.rglob("*.md"))
            if len(markdown_files) != 1:
                raise RuntimeError("Expected one Markdown document from MinerU-HTML")
            original_markdown = markdown_files[0].read_text(encoding="utf-8")
            relative = "../" + str(markdown_files[0].parent.relative_to(job)).replace("\\", "/") + "/"
            content = original_markdown.replace("](images/", "](" + relative + "images/")
            derived = job / "derived"
            derived.mkdir(exist_ok=True)
            text = f"<!-- source:{args.source_id}; original_url:{args.source_url}; parser:MinerU-HTML -->\n\n" + content
            (derived / "document.md").write_text(text, encoding="utf-8")
            headings = markdown_headings(text, args.source_id, args.source_url)
            write_json(derived / "heading-index.json", {**identity, "markdown_path": "document.md",
                                                       "headings": headings, "review_status": "unreviewed"})
            assets = []
            for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", original_markdown):
                external = target.startswith(("http://", "https://", "data:"))
                assets.append({"reference": target, "external": external,
                               "local_exists": None if external else (markdown_files[0].parent/target).is_file()})
            write_json(derived / "assets.json", {"assets": assets})
            summary = {"status": "parsed_requires_content_review", **identity,
                "finished_at": now(), "elapsed_seconds": round(time.monotonic()-started,3),
                "batch_id": state.get("batch_id"), "markdown_characters": len(content),
                "headings": len(headings), "asset_count": len(assets),
                "original_html_sent_directly": args.input_scope == "original_html",
                "html_sent_directly": True, "printed_to_pdf": False,
                "content_quality_passed": False}
            write_json(job / "public-summary.json", summary)
            event(job, "html_parsed", source_id=args.source_id, batch_id=state.get("batch_id"),
                  markdown_characters=len(content), headings=len(headings))
        except Exception as exc:
            error = {"status": "incomplete_resume_existing_batch", "source_id": args.source_id,
                     "error_type": type(exc).__name__, "message": safe_message(exc, config.api_keys)}
            write_json(job / "public-summary.json", error)
            event(job, "html_incomplete", **error)
            raise RuntimeError(error["message"]) from None


def archive_book(args) -> dict:
    """Create a data-only book package, excluding live signed-URL state."""
    root = Path(args.root).resolve()
    job = root / "jobs" / args.source_id
    summary = read_json(job / "public-summary.json")
    if summary.get("status") != "parsed_requires_content_review":
        raise RuntimeError("Only a completed parsed book can be archived")
    destination = root / "archives"
    destination.mkdir(exist_ok=True)
    archive = destination / (args.source_id + ".v1.tar.gz")
    manifest_path = destination / (args.source_id + ".v1.archive-manifest.json")
    if archive.exists() and manifest_path.exists():
        prior = read_json(manifest_path)
        if prior["source_sha256"] != summary["source_sha256"]:
            raise RuntimeError("Existing archive belongs to a different source")
        return prior
    members = []
    source = root / "inputs" / (args.source_id + ".pdf")
    candidates = [source] + sorted(job.rglob("*"))
    temporary = archive.with_suffix(".gz.tmp")
    with tarfile.open(temporary, "w:gz", compresslevel=3) as packed:
        for path in candidates:
            if not path.is_file() or path.is_symlink() or path.name.startswith("private-"):
                continue
            if path.name == "running.lock" or path.name.endswith(".tmp"):
                continue
            relative = path.relative_to(root).as_posix()
            packed.add(path, arcname=relative, recursive=False)
            members.append({"path": relative, "bytes": path.stat().st_size})
    temporary.replace(archive)
    manifest = {"source_id": args.source_id, "created_at": now(),
        "source_sha256": summary["source_sha256"], "input_pages": summary["input_pages"],
        "archive_path": str(archive), "archive_bytes": archive.stat().st_size,
        "archive_sha256": file_digest(archive), "members": members,
        "private_api_state_excluded": True, "content_review_status": "unreviewed_full_book",
        "page_faithful_relative": f"jobs/{args.source_id}/derived/page-faithful.md",
        "page_json_relative": f"jobs/{args.source_id}/derived/page-faithful.json",
        "probe_relative": f"jobs/{args.source_id}/derived/structure-probes.json"}
    write_json(manifest_path, manifest)
    return manifest


def receive_archive(args) -> dict:
    """Materialize the actual data package in the approved cluster subtree."""
    approved = Path("/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench/quality-library").resolve()
    target = Path(args.target).resolve()
    if approved not in target.parents:
        raise ValueError("Archive target is outside the approved independent library subtree")
    manifest = read_json(Path(args.manifest))
    source_id = manifest["source_id"]
    archive = Path(args.archive)
    if file_digest(archive) != manifest["archive_sha256"]:
        raise RuntimeError("Transferred binary archive fingerprint mismatch")
    receipt_path = target / "receipts" / (source_id + ".v1.receipt.json")
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt["archive_sha256"] != manifest["archive_sha256"]:
            raise RuntimeError("An existing receipt identifies a different archive")
        return receipt
    target.mkdir(parents=True, exist_ok=True)
    expected = {entry["path"]: entry["bytes"] for entry in manifest["members"]}
    materialized = []
    with tarfile.open(archive, "r:gz") as packed:
        for member in packed.getmembers():
            relative = Path(member.name)
            if member.name not in expected or not member.isfile() or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unexpected or unsafe archive member")
            path = (target / relative).resolve()
            if target not in path.parents:
                raise ValueError("Archive member escapes the approved target")
            if member.size != expected[member.name]:
                raise ValueError("Archive member size differs from source manifest")
            data = packed.extractfile(member).read()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.read_bytes() != data:
                    raise RuntimeError("Existing library content differs; refusing to overwrite it")
            else:
                temporary = path.with_name(path.name + ".incoming")
                temporary.write_bytes(data)
                temporary.replace(path)
            materialized.append(member.name)
    if set(materialized) != set(expected):
        raise RuntimeError("Archive does not materialize the complete manifest")
    original = target / "inputs" / (source_id + ".pdf")
    if file_digest(original) != manifest["source_sha256"]:
        raise RuntimeError("Archived original PDF fingerprint mismatch")
    job = target / "jobs" / source_id
    pages = read_json(job / "derived/page-faithful.json")
    missing_assets = [a["path"] for p in pages["pages"] for a in p["assets"]
                      if not (job/a["path"]).is_file()]
    if missing_assets:
        raise RuntimeError("Archived page/asset links refer to missing files")
    receipt = {"source_id": source_id, "received_at": now(), "archive_sha256": manifest["archive_sha256"],
        "archive_bytes": archive.stat().st_size, "members_materialized": len(materialized),
        "original_pdf_sha256_verified": True, "private_api_state_excluded": True,
        "original_pdf": str(original), "actual_markdown": str(target/manifest["page_faithful_relative"]),
        "actual_page_json": str(target/manifest["page_json_relative"]),
        "actual_structure_probes": str(target/manifest["probe_relative"]),
        "input_pages": manifest["input_pages"], "pages_with_content_blocks": len(pages["pages"]),
        "asset_links_verified": True, "review_status": "unreviewed_full_book"}
    write_json(receipt_path, receipt)
    return receipt


def run_purpose_queue(args) -> int:
    """Consume the source specialist's finite queue after the book workflow."""
    import fcntl
    queue_path = Path(args.queue).resolve()
    queue = read_json(queue_path)
    source_root = queue_path.parent
    root = Path(args.root).resolve()
    report_path = root / "reports/mineru-purpose-results.json"
    result = {"workflow_id": "mineru-presentation-sources-20261102-v1", "started_at": now(),
              "concurrency": 1, "source_queue": str(queue_path), "status": "running", "sources": []}
    unavailable_models = {}
    with (root / "batch-running.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for item in queue["items"]:
            source_id = "purpose." + item["source_id"]
            source = (source_root/item["input_path"]).resolve()
            original = (source_root/item["original_path"]).resolve()
            if source_root not in source.parents or source_root not in original.parents:
                raise ValueError("Queue source lies outside its approved source root")
            row = {"source_id": item["source_id"], "job_id": source_id,
                   "source_url": item["source_url"], "model_version": item["model_version"],
                   "original_path": str(original), "input_path": str(source),
                   "derivation": item["derivation"], "public_deployment_allowed": False,
                   "local_output_relative": str(Path(item["input_path"]).parent/"mineru").replace("\\","/")}
            result["sources"].append(row)
            if item["model_version"] in unavailable_models:
                row.update(status="not_retried_provider_model_unavailable", message=unavailable_models[item["model_version"]])
                write_json(report_path, result)
                continue
            common = dict(input=str(source), source_id=source_id, root=str(root),
                          timeout=args.timeout, poll_interval=args.poll_interval)
            try:
                if item["model_version"] == "MinerU-HTML":
                    run_html(argparse.Namespace(**common, source_url=item["source_url"], input_scope="scoped_html"))
                    markdown = root/"jobs"/source_id/"derived/document.md"
                elif item["model_version"] == "vlm" and source.suffix.lower() == ".pdf":
                    run_cloud(argparse.Namespace(**common, manifest=None, max_pages=180))
                    markdown = root/"jobs"/source_id/"derived/page-faithful.md"
                else:
                    raise ValueError("Queue requests an unsupported, undocumented model/format combination")
                job = root/"jobs"/source_id
                write_json(job/"source-provenance.json", {**row,
                    "original_sha256": file_digest(original), "input_sha256": file_digest(source),
                    "input_equals_original": source == original,
                    "scope_does_not_change_source_identity": True})
                row.update(status="mineru_parsed_requires_source_review", actual_markdown=str(markdown),
                           remote_job=str(job), summary=read_json(job/"public-summary.json"))
            except Exception as exc:
                message = safe_message(exc)
                row.update(status="failed_keep_native_fallback", error_type=type(exc).__name__, message=message)
                if any(word in message.lower() for word in ["version field invalid", "model not supported"]):
                    unavailable_models[item["model_version"]] = message
                write_json(report_path, result)
                if any(word in message.lower() for word in ["rejected the token", "rate limit", "quota"]):
                    result.update(status="provider_blocked_preserve_existing_jobs", finished_at=now())
                    write_json(report_path, result)
                    return 2
            write_json(report_path, result)
        result.update(status="completed_with_per_source_dispositions", finished_at=now())
        write_json(report_path, result)
    return 0


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("cloud-run")
    run.add_argument("--input", required=True)
    run.add_argument("--source-id", required=True)
    run.add_argument("--root", required=True)
    run.add_argument("--manifest")
    run.add_argument("--max-pages", type=int, default=180)
    run.add_argument("--timeout", type=float, default=1200)
    run.add_argument("--poll-interval", type=float, default=4)
    plan = commands.add_parser("plan")
    plan.add_argument("--registry", required=True)
    plan.add_argument("--remote-root", required=True)
    plan.add_argument("--output", required=True)
    batch = commands.add_parser("batch-run")
    batch.add_argument("--plan", required=True)
    batch.add_argument("--wall-budget", type=float, default=1200)
    batch.add_argument("--timeout", type=float, default=1200)
    batch.add_argument("--poll-interval", type=float, default=4)
    status = commands.add_parser("status")
    status.add_argument("--root", required=True)
    html = commands.add_parser("html-run")
    html.add_argument("--input", required=True)
    html.add_argument("--source-id", required=True)
    html.add_argument("--source-url", required=True)
    html.add_argument("--root", required=True)
    html.add_argument("--timeout", type=float, default=600)
    html.add_argument("--poll-interval", type=float, default=4)
    html.add_argument("--input-scope", choices=["original_html","scoped_html"], default="original_html")
    archive = commands.add_parser("archive-book")
    archive.add_argument("--root", required=True)
    archive.add_argument("--source-id", required=True)
    receive = commands.add_parser("receive-archive")
    receive.add_argument("--archive", required=True)
    receive.add_argument("--manifest", required=True)
    receive.add_argument("--target", required=True)
    purpose = commands.add_parser("purpose-queue")
    purpose.add_argument("--queue", required=True)
    purpose.add_argument("--root", required=True)
    purpose.add_argument("--timeout", type=float, default=600)
    purpose.add_argument("--poll-interval", type=float, default=4)
    args = parser.parse_args()
    if args.command in {"cloud-run", "html-run", "archive-book"}:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.source_id) or args.source_id in {".", ".."}:
            parser.error("source-id must be a single ASCII identifier")
    if args.command == "cloud-run":
        if not 1 <= args.max_pages <= 180:
            parser.error("max-pages must be in 1..180")
        run_cloud(args)
    elif args.command == "plan":
        make_plan(args)
    elif args.command == "batch-run":
        sys.exit(run_batch(args))
    elif args.command == "html-run":
        run_html(args)
    elif args.command == "archive-book":
        result = archive_book(args)
        print(json.dumps({key:value for key,value in result.items() if key != "members"}
                         | {"member_count": len(result["members"])},ensure_ascii=False,indent=2))
    elif args.command == "receive-archive":
        print(json.dumps(receive_archive(args),ensure_ascii=False,indent=2))
    elif args.command == "purpose-queue":
        sys.exit(run_purpose_queue(args))
    else:
        print(json.dumps(public_status(Path(args.root)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
