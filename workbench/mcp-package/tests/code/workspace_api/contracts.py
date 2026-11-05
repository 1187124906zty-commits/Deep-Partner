"""Native source call inputs from the executor, independently selected by verifier."""
from .support import PID, KB, DOC, ASSET, REV, ANNOTATION, LEDGER, PACKAGE, EVIDENCE

INPUTS = PACKAGE / "tests/results/workspace_api/inputs"
INPUTS.mkdir(parents=True, exist_ok=True)
UPLOAD = INPUTS / "upload.txt"
UPLOAD.write_bytes(b"Native multipart upload fixture\n")
KBFILE = INPUTS / "knowledge-fixture.txt"
KBFILE.write_bytes(LEDGER["kb_fixture_raw"]["value"].encode("utf-8"))
BUNDLE = EVIDENCE / "data/material-import-fixture.zip"

def p(action=None, **kw):
    return {"project_id": PID, **({"action": action} if action else {}), **kw}
def k(action=None, **kw):
    return p(action, knowledge_base=KB, **kw)
def j(label):
    return dict(LEDGER[label]["json"])

CASES = {
 "workbench_account": [("account_current", {}), ("account_status", {"action":"status"}), ("account_profile", {"action":"profile"})],
 "workbench_projects": [("projects", {})],
 "workbench_files": [("files_initial",p()), ("files_final",p()), ("fixture_folder",p("create_folder",**j("fixture_folder"))), ("fixture_write_v1",p("write",**j("fixture_write_v1"))), ("fixture_write_v2",p("write",**j("fixture_write_v2"))), ("fixture_read_v1",p("read",path="docs/mcp-execution-fixture/evidence.txt")), ("fixture_stale_write",p("write",**j("fixture_stale_write"))), ("fixture_upload",p("upload",path="docs/mcp-execution-fixture",file_paths=[str(UPLOAD)])), ("fixture_trash",p("trash",path="docs/mcp-execution-fixture/evidence.txt")), ("file_traversal_error",p("read",path="../../mcp-no-such-file")), ("file_missing_error",p("read",path="docs/mcp-no-such-file.txt"))],
 "workbench_revisions": [("revisions_list",p()), ("revision_diff",p("inspect",revision_id=REV)), ("revision_restore",p("restore",revision_id=REV))],
 "workbench_rules": [("standards",{}),("llms",{"action":"llms"}),("health_schema",{"action":"schema"}),("context_code",p("context",task="code")),("context_literature",p("context",task="literature"))],
 "workbench_storage": [("storage",{})],
 "workbench_knowledge_bases": [("kb_fixture_list",p()),("kb_fixture_details",k("details")),("kb_fixture_create",p("create",name="MCP-Execution-Fixture")),("kb_fixture_bind",p("bind",knowledge_bases=[KB])),("kb_missing_details",p("details",knowledge_base="mcp-execution-no-such-kb"))],
 "workbench_knowledge_files": [("kb_fixture_text",k("read",filename="knowledge-fixture.txt")),("kb_fixture_raw",k("read",filename="knowledge-fixture.txt",view="original")),("kb_fixture_files",k()),("kb_fixture_folder",k("create_folder",path="fixture-notes")),("kb_fixture_move",k("move",source="knowledge-fixture.txt",dest_folder="fixture-notes")),("kb_fixture_moved_read",k("read",filename="fixture-notes/knowledge-fixture.txt",view="original")),("kb_fixture_upload",k("upload",file_paths=[str(KBFILE)],rag_provider="llamaindex",image_analysis=False)),("kb_missing_files",p(knowledge_base="mcp-execution-no-such-kb"))],
 "workbench_knowledge_index": [("kb_fixture_final_readiness",k()),("kb_fixture_final_run",k("run")),("kb_fixture_final_progress",k("progress")),("kb_missing_readiness",p(knowledge_base="mcp-execution-no-such-kb"))],
 "workbench_search_sources": [("health_sources",{})],
 "workbench_web_search": [("web_search",{"q":"Fourier neural operator ICLR 2021"}),("web_search_short_query",{"q":"x"})],
 "workbench_paper_search": [("scholar_papers",p(q='"Fourier Neural Operator"',source="scholar_mcp",limit=5)),("crossref_papers",p(q="Fourier Neural Operator",source="crossref",limit=5)),("paper_search_invalid_page",p(q="Fourier",source="crossref",page=0))],
 "workbench_literature": [("literature_initial",p()),("literature_replay",p()),("literature_preview",p("preview",asset=ASSET)),("literature_pdf",p("read",asset=ASSET))],
 "workbench_literature_organization": [("literature_folders",p()),("literature_classification",p("classification"))],
 "workbench_paper_downloads": [("download_worker",{}),("download_jobs",p("list"))],
 "workbench_reader": [("reader_open",p("open",**j("reader_open"))),("reader_blocks",p("content",document_id=DOC)),("reader_translations",p("content",document_id=DOC,view="translations")),("reader_translation_options",p("content",document_id=DOC,view="options"))],
 "workbench_translation": [("translation_submit",p(target="en"))],
 "workbench_annotations": [("annotations_initial",p()),("annotation_create",p("create",payload=j("annotation_create"))),("annotation_update",p("update",identifier=ANNOTATION,payload=j("annotation_update"))),("annotation_filtered",p(area="literature",asset=ASSET)),("annotation_invalid_area",p("create",payload=j("annotation_invalid_area")))],
 "workbench_review": [("review_history_initial",p()),("review_chat",p("chat_history",area="literature")),("review_receipt",p("receipt",**j("review_receipt")))],
 "workbench_jobs": [("jobs_initial",p()),("jobs_final",p())],
 "workbench_settings": [("settings_masked",{})],
 "workbench_author_profile": [("author_profile_initial",{}),("preview_author",p("preview")),("author_profile_fixture",{"action":"save",**j("author_profile_fixture")}),("author_profile_invalid_email",{"action":"save",**j("author_profile_invalid_email")})],
 "workbench_project_import": [("material_import_submit",p(file_path=str(BUNDLE)))],
 "workbench_knowledge_search": [(label,p(**j(label))) for label in ["knowledge_fourier","knowledge_changed_query","knowledge_no_hit","knowledge_query_too_short","knowledge_unbound_library","knowledge_semantic_missing_library","kb_fixture_keyword","kb_fixture_semantic","kb_fixture_semantic_retry","kb_fixture_semantic_after_native_roots"]]
}
# The frozen Crossref failure input is independent of its unavailable provider.
CASES["workbench_paper_search"][1] = ("crossref_papers",p(**LEDGER["crossref_papers"]["params"]))
REQUIRED = {t: ["project_id"] for t in CASES}
for t in ["workbench_account","workbench_projects","workbench_rules","workbench_storage","workbench_search_sources","workbench_paper_downloads","workbench_settings","workbench_author_profile"]: REQUIRED[t]=[]
REQUIRED.update(workbench_web_search=["q"],workbench_paper_search=["project_id","q"],workbench_knowledge_files=["project_id","knowledge_base"],workbench_knowledge_index=["project_id","knowledge_base"],workbench_project_import=["project_id","file_path"],workbench_knowledge_search=["project_id","query"])

# Changed-input properties are justified by the named bound HTTP signatures;
# these are transport-contract tests, not invented model/search result oracles.
CP = "changed-project-42"
CK = "workspace:ws_changed_42:kb:changed"
ROOT_ROUTE = "/research/api/projects/" + CP
CHANGED = {
 "workbench_projects": dict(method="PATCH", path=ROOT_ROUTE, arguments={"action":"update","project_id":CP,"name":"Independent changed 项目"}, json={"name":"Independent changed 项目"}, expected={"id":CP,"name":"Independent changed 项目"}),
 "workbench_files": dict(method="PUT", path=ROOT_ROUTE+"/file", arguments={"action":"write","project_id":CP,"path":"notes/空白.txt","content":"","expected_modified":1.5,"reason":"blank source file"}, json={"path":"notes/空白.txt","content":"","expected_modified":1.5,"reason":"blank source file"}, expected={"saved":True,"modified":2.5}),
 "workbench_rules": dict(method="GET", path="/research/api/standards/skills/paper/reading", arguments={"action":"skill","identifier":"paper/reading"}, expected={"id":"paper/reading","title":"Independent source skill"}),
 "workbench_knowledge_bases": dict(method="PATCH",path=ROOT_ROUTE,arguments={"action":"bind","project_id":CP,"knowledge_bases":[]},json={"knowledge_bases":[]},expected={"id":CP,"config":{"knowledge_bases":[]}}),
 "workbench_knowledge_files": dict(method="POST",path="/api/knowledge-bases/"+CK+"/files/move",arguments={"action":"move","project_id":CP,"knowledge_base":CK,"source":"原文/a b.txt","dest_folder":"changed"},params={"dt_workspace":"ws_changed_42"},json={"source":"原文/a b.txt","dest_folder":"changed"},expected={"status":"ok","path":"changed/a b.txt"}),
 "workbench_knowledge_index": dict(method="POST",path="/api/knowledge-bases/"+CK+"/indexing-run/task-changed/cancel",arguments={"action":"cancel","project_id":CP,"knowledge_base":CK,"task_id":"task-changed"},params={"dt_workspace":"ws_changed_42"},expected={"accepted":True,"task_id":"task-changed"}),
 "workbench_web_search": dict(method="GET",path="/research/api/search/web",arguments={"q":"porous media reactive transport","kind":"template"},params={"q":"porous media reactive transport","kind":"template"},expected={"items":[],"source":"fixture source-supported empty discovery"}),
 "workbench_paper_search": dict(method="GET",path=ROOT_ROUTE+"/literature/search",arguments={"project_id":CP,"q":"reactive transport","source":"auto","years":10,"newest":True,"page":3,"limit":7},params={"q":"reactive transport","source":"auto","years":"10","newest":"true","page":"3","limit":"7"},expected={"query":"reactive transport","page":3,"limit":7,"items":[]}),
 "workbench_literature_organization": dict(method="PUT",path=ROOT_ROUTE+"/literature/folders",arguments={"project_id":CP,"action":"assign","asset":"changed/source.pdf","category":"validation"},json={"asset":"changed/source.pdf","category":"validation"},expected={"assignments":{"changed/source.pdf":"validation"}}),
 "workbench_paper_downloads": dict(method="POST",path=ROOT_ROUTE+"/literature/download-batch",arguments={"project_id":CP,"action":"enqueue","entries":[{"doi":"10.1234/example"},{"arxiv":"2010.08895"}],"folder":"methods"},json={"entries":[{"doi":"10.1234/example"},{"arxiv":"2010.08895"}],"folder":"methods"},expected={"queued":0,"items":[],"skipped":[],"rejected":[]}),
 "workbench_reader": dict(method="POST",path=ROOT_ROUTE+"/reader",arguments={"project_id":CP,"area":"literature","asset":"changed/source.pdf","library":"workspace","title":"Changed source title","width":850,"theme":"night"},json={"area":"literature","asset":"changed/source.pdf","library":"workspace","title":"Changed source title","width":850,"theme":"night"},expected={"document_id":"b"*32,"area":"literature","asset":"workspace/changed/source.pdf","title":"Changed source title"}),
 "workbench_annotations": dict(method="PATCH",path=ROOT_ROUTE+"/annotations/changed-id",arguments={"project_id":CP,"action":"update","identifier":"changed-id","area":"code","asset":"src/changed.py","payload":{"body":"changed question","status":"resolved","locator":{"line":17}}},json={"body":"changed question","status":"resolved","locator":{"line":17},"area":"code","asset":"src/changed.py"},expected={"id":"changed-id","body":"changed question","status":"resolved","locator":{"line":17},"area":"code","asset":"src/changed.py"}),
 "workbench_review": dict(method="POST",path=ROOT_ROUTE+"/agent-receipt",arguments={"project_id":CP,"action":"receipt","question_ids":[],"artifacts":[],"validation":[{"name":"native check","passed":True}],"limitations":["Synthetic fixture"],"resolved":False},json={"question_ids":[],"artifacts":[],"validation":[{"name":"native check","passed":True}],"limitations":["Synthetic fixture"],"resolved":False},expected={"recorded":True,"question_ids":[],"validation":[{"name":"native check","passed":True}]}),
 "workbench_settings": dict(method="PUT",path="/research/api/api-settings",arguments={"action":"save","model":"changed-model","api_key":"synthetic-not-a-secret"},current={"base_url":"https://example.invalid/v1","model":"old","translation_prompt":"keep instruction","literature_provider":"semantic"},json={"base_url":"https://example.invalid/v1","model":"changed-model","translation_prompt":"keep instruction","literature_provider":"semantic","api_key":"synthetic-not-a-secret"},expected={"saved":True,"configured":True}),
 "workbench_author_profile": dict(method="PUT",path="/research/api/author-profile",arguments={"action":"save","name_en":"Changed author"},current={"name":"保留姓名","name_en":"","affiliation":"A","affiliation_en":"B","email":"fixture@example.invalid","orcid":"0000-0000-0000-0000","address":"C"},json={"name":"保留姓名","name_en":"Changed author","affiliation":"A","affiliation_en":"B","email":"fixture@example.invalid","orcid":"0000-0000-0000-0000","address":"C"},expected={"saved":True,"profile":{"name":"保留姓名","name_en":"Changed author"}}),
 "workbench_knowledge_search": dict(method="POST",path=ROOT_ROUTE+"/knowledge/search",arguments={"project_id":CP,"query":" independent changed query ","knowledge_base":CK,"mode":"semantic","limit":1},json={"query":" independent changed query ","knowledge_base":CK,"mode":"semantic","limit":1},expected={"mode":"semantic","query":"independent changed query","knowledge_base":CK,"result":{"sources":[]}})
}
