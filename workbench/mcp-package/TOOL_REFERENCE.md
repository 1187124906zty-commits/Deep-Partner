# MCP tool reference

37 个任务工具。`project_id` 来自 workbench_projects；固定分支由 action 选择。表中必需项为 schema 层必需，部分可选参数会在具体 action 分支成为必需，见其说明。原生字段和来源通过 data 返回。

## workbench_manuscript

Read, save or import an editable manuscript and its image assets.
Input is a project, action and source document or file; output is the native document or upload receipt.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| action | 否 | "get" | Editable manuscript operation Choices: get, save, import, upload_asset |
| document | 否 | null | Existing Tiptap document and manuscript fields; save requires its revision |
| revision | 否 | null | Explicit current revision, overriding document.revision when supplied |
| reason | 否 | null | Reason retained with manuscript history |
| file_path | 否 | null | Local document to import or image asset to upload |

## workbench_manuscript_templates

Inspect supported manuscript templates and retrieve their actual source or preview.
Input is a catalog action or selected template and destination; output is native metadata or a local artifact.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "list" | Read template catalog, rendered preview or original source Choices: list, preview, source |
| kind | 否 | null | Template ID returned by the actual catalog |
| output_path | 否 | null | Destination file required for preview or original source downloads |

## workbench_manuscript_export

Submit a native manuscript export with its language and review settings.
Input is an owned project and export settings; output is the unchanged job ID for workbench_jobs polling.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| format | 是 | — | Native export format Choices: docx, pdf, tex |
| action | 否 | "export" | Submit the existing manuscript export operation |
| review | 否 | false | Include native review annotations |
| language | 否 | "auto" | Document language basis; auto may prepare an English draft Choices: auto, source, translation, reader |
| document_id | 否 | "" | Current reader document ID when exporting reader translation |
| columns | 否 | 2 | One or two columns, preserving backend default two Choices: 1, 2 |

## workbench_export_download

Download a completed manuscript or presentation artifact.
Input is a project, export area, name and destination; output is the saved file descriptor.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| name | 是 | — | Exact completed export name from the native job result |
| output_path | 是 | — | Explicit destination for the native export bytes |
| area | 否 | "manuscript" | Native export area Choices: manuscript, slides |
| action | 否 | "download" | Download an already completed export |

## workbench_references

Maintain stable citations and request source-backed replacement or related-paper proposals.
Input is a project and citation action with its revision or source metadata; output is the native document, proposal or state.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| action | 否 | "list" | Canonical citation operation Choices: list, add, recommend, replace, related |
| reference_id | 否 | null | Stable existing reference ID for recommend, replace or related |
| entry | 否 | null | Selected source metadata, including title and DOI |
| revision | 否 | null | Current manuscript revision required for add and replace |
| query | 否 | null | Optional real search query for replacement recommendations |
| newest | 否 | false | Prefer newer available search candidates |
| instruction | 否 | null | Specific recommendation request; omitted preserves backend instruction |
| paragraph | 否 | null | Reviewed replacement paragraph preserving citation numbers |
| expected_text | 否 | null | Exact paragraph from the recommendation receipt |
| years | 否 | 5 | Related-paper range, zero means all years Choices: 0, 5, 10 |
| source | 否 | "auto" | Actual configured search provider or auto |

## workbench_journals

Find journals, inspect sourced metrics or generate a supported journal preview.
Input is journal criteria or a project and selected layout; output is native metadata or a preview job ID.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "search" | Journal discovery, sourced details or manuscript preview Choices: search, details, preview |
| query | 否 | "" | Journal search words; empty returns generic template choices |
| journal_id | 否 | null | Selected journal ID; preview omission preserves generic-zh default |
| year | 否 | null | Optional source metric report year |
| project_id | 否 | null | Owned project required for generating a journal preview |
| columns | 否 | 1 | Journal preview column count, preserving backend default one Choices: 1, 2 |

## workbench_journal_templates

Discover and retain original official journal author-template packages.
Input is a journal or cached candidate selection; output is source provenance, a receipt or the original local file.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| action | 否 | "search" | Discover official candidates, retain a selected package or fetch its file Choices: search, download, file |
| journal | 否 | null | Journal ID required for source discovery and selected candidate download |
| template_id | 否 | null | Actual cached template candidate ID for download |
| name | 否 | null | Exact retained template filename for file retrieval |
| output_path | 否 | null | Destination file required for retrieving retained template bytes |

## workbench_figure

Inspect, preview and save actual registered Matplotlib figure objects.
Input is a project image and source-supported revisioned patches; output is native figure state or its save receipt.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| path | 是 | — | Image path relative to the project's program directory |
| action | 否 | "inspect" | Inspect actual plot objects, preview changes or save them Choices: inspect, preview, save |
| revision | 否 | null | Actual inspected figure revision required for preview/save |
| changes | 否 | null | Native figure, objects and layout patches using actual inspected object IDs |
| start_edit_session | 否 | false | Create the backend figure editing session during inspection |
| edit_session | 否 | "" | Existing editing-session ID for preview/save |
| reason | 否 | "调整图形样式" | Reason saved with figure history |
| autosave | 否 | false | Native figure save flag |
| include_context | 否 | false | Also return native image/manuscript/source-program context during inspection |

## workbench_figure_chat

Read or continue source-bound figure conversations and linked agent replies.
Input is an image, discussion action and optional selected objects; output is native messages, proposal or session state.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| path | 是 | — | Current project image path |
| action | 否 | "history" | Read image discussion, send a request or inspect an associated session Choices: history, send, session |
| message | 否 | null | Request required for send; model-backed replies retain source limits |
| revision | 否 | 0 | Current native figure revision |
| selection | 否 | null | Actual selected plot object IDs |
| changes | 否 | null | Current unsaved native figure patches |
| image_path | 否 | null | Optional local PNG snapshot for the native discussion |
| edit_session | 否 | "" | Current backend figure edit-session ID |
| include_context | 否 | true | Include actual figure/source context in the model request |
| session_id | 否 | null | Existing session previously associated with this figure |

## workbench_image_review

Prepare or submit an image review retaining source programs and annotations.
Input is a project image, local PNG and request; output is the native prepared-review or agent receipt.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| path | 是 | — | Existing image path relative to the project program directory |
| image_path | 是 | — | Local PNG review image or cropped screenshot |
| instruction | 是 | — | Actual image-review request |
| action | 否 | "review" | Prepare or submit the existing native image-review operation |
| plot_program | 否 | "" | Optional actual project-relative plotting source |
| compute_program | 否 | "" | Optional actual project-relative computation source |
| crop | 否 | null | Native crop locator, if present |
| annotations | 否 | null | Native image annotation records |
| send | 否 | true | Submit to the native agent; false saves only a prepared review |

## workbench_raster

Save edited bitmap pixels while retaining the previous native image version.
Input is a project image, local PNG and optional timestamp; output is the native save receipt or conflict.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| path | 是 | — | Existing bitmap path relative to the project program directory |
| image_path | 是 | — | Local complete PNG containing edited pixels |
| action | 否 | "save" | Save pixels through the existing version-preserving image endpoint |
| expected_modified | 否 | null | Original file timestamp for optimistic conflict detection |

## workbench_slide_templates

Inspect, upload, prepare and configure the original presentation templates.
Input is a project and template lifecycle action; output is the native catalog, manifest, selection or preparation job ID.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| action | 否 | "list" | Inspect or configure a project-private presentation template Choices: list, upload, prepare, select, roles |
| template | 否 | null | Actual catalog template ID; roles requires uploaded |
| file_path | 否 | null | Local editable PPTX required for upload |
| roles | 否 | null | Native role-to-page mapping for an uploaded template |

## workbench_slides

Manage audience-confirmed slide content and its original editable exports.
Input is a project and explicit slide lifecycle action; output is native plan, confirmation, job ID or preview artifact.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned research project ID |
| action | 否 | "get" | Native slide plan, confirmation, export or preview operation Choices: confirm, get, save, plan, export, preview |
| template | 否 | null | Actual selected template; confirm only after the user's choice |
| profile | 否 | null | User-selected audience and purpose required for confirm Choices: group, conference, project, proposal, defense, literature |
| confirmation_action | 否 | "generate" | Native confirmation operation Choices: generate, restyle |
| plan | 否 | null | Existing editable slide plan with sections and applicable confirmation ID |
| instruction | 否 | "" | Specific instructions for model-backed slide planning |
| length | 否 | "medium" | Native planning length, normally short, medium or long |
| use_native | 否 | true | Use the assigned native model for planning |
| confirmation_id | 否 | "" | Current explicit confirmation receipt required by the backend |
| kind | 否 | "deck" | deck or a catalog template ID for a rendered preview |
| page | 否 | 1 | One-based actual rendered page number |
| output_path | 否 | null | Destination PNG required for preview |

## workbench_account

Inspect the current Workbench account and authentication state.
Input selects an account view; output preserves its native identity/profile fields.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "current" | Read the current identity, authentication status or account profile Choices: current, status, profile |

## workbench_projects

List, create or rename research projects through the original application.
Input is an action and its project/name fields; output is the native project result.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "list" | List projects, create one, or rename an existing owned project Choices: list, create, update |
| project_id | 否 | null | Existing project ID required for update |
| name | 否 | null | Project name of 1 to 100 characters for create or update |

## workbench_files

Manage current project files while preserving native conflict and history behavior.
Input supplies project-relative paths or local uploads; output is native state or an absolute artifact.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Existing owned Workbench project ID |
| action | 否 | "list" | Project file operation Choices: list, read, upload, write, create_folder, trash |
| path | 否 | "" | Project-relative file path or directory; empty lists the root |
| content | 否 | null | Exact UTF-8 text to save for write |
| file_paths | 否 | null | Local files to upload into path, each at most 256 MiB |
| expected_modified | 否 | null | Existing modification timestamp for optimistic write conflict detection |
| reason | 否 | "MCP file edit" | Reason saved in native replacement history |
| output_dir | 否 | null | Optional local download base directory; a fresh child is created per read |

## workbench_revisions

Inspect or restore the application's recoverable artifact revisions.
Input identifies a native revision; output is history, a native diff, preview or restoration result.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Existing owned project ID |
| action | 否 | "list" | Inspect or restore native recoverable history Choices: list, inspect, restore |
| revision_id | 否 | null | Native trash/revision ID required for inspect or restore |
| view | 否 | "diff" | Readable history difference or original preview Choices: diff, preview |
| output_dir | 否 | null | Download base directory for preview; each call creates a fresh child |

## workbench_rules

Read existing Workbench task rules and source integration contracts.
Input selects a rule/context view; output preserves the actual published instructions or schema.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "standards" | Read task standards, a named skill, API schema or project integration context Choices: standards, skill, llms, schema, context |
| project_id | 否 | null | Owned project ID required for context |
| identifier | 否 | null | Skill identifier returned by standards, required for skill |
| task | 否 | "review" | Task-specific integration context Choices: code, code-review, test, paper, translation, literature, slides, review, reader, figure |

## workbench_storage

Inspect the current account's storage usage and quota.
Input selects usage; output is the native storage and cache report.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "usage" | Read account quota, file and cache usage |

## workbench_knowledge_bases

Manage knowledge-base resources in the owned project's native workspace scope.
Input supplies existing IDs or new-KB sources; output preserves native metadata and indexing task IDs.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project used to resolve the actual native workspace scope |
| action | 否 | "list" | List assignable resources, inspect/create a KB, or bind visible KB IDs Choices: list, details, create, bind |
| knowledge_base | 否 | null | Native qualified knowledge-base ID for details |
| name | 否 | null | Name for a new knowledge base |
| knowledge_bases | 否 | null | Exact visible qualified IDs to bind; an explicit empty list clears bindings |
| file_paths | 否 | null | Optional local source files; no files creates a native empty KB |
| rag_provider | 否 | "llamaindex" | Source-supported native provider identifier, fixed for the new KB |
| pageindex_mode | 否 | "" | Optional native PageIndex OSS mode Choices: , flash, standard |
| search_mode | 否 | "" | Optional search mode supported by the selected native provider |
| rel_paths | 否 | null | Optional upload-relative paths aligned with local files |
| indexing_llm | 否 | null | Legacy native indexing selection; current upstream may reject per-KB overrides |
| embedding_model | 否 | null | Native configured profile_id/model_id selection, without secrets |

## workbench_knowledge_files

Read, append or organize native knowledge-base source files.
Input supplies scoped KB paths or local files; output is native file state, text preview or an artifact.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project supplying the native workspace scope |
| knowledge_base | 是 | — | Actual qualified knowledge-base ID visible in that scope |
| action | 否 | "list" | Native KB source-file operation Choices: list, read, upload, create_folder, move |
| filename | 否 | null | KB-relative source filename for read |
| view | 否 | "text" | Original bytes or the actual plain-text extraction preview Choices: original, text |
| file_paths | 否 | null | Local files for upload |
| rel_paths | 否 | null | Optional source-relative paths aligned with uploaded files |
| dest_subdir | 否 | null | Optional organizational destination for an upload batch |
| rag_provider | 否 | null | Optional provider check; must match the KB's fixed provider |
| image_analysis | 否 | null | Native pinned image-analysis policy; omitted preserves that policy |
| path | 否 | null | KB-relative folder to create |
| source | 否 | null | Current KB-relative file/folder to move |
| dest_folder | 否 | "" | Destination folder for a move; empty selects KB root |
| output_dir | 否 | null | Download base directory for original files; a fresh child is created |

## workbench_knowledge_index

Inspect and control the existing native knowledge indexing lifecycle.
Input identifies the scoped KB/run; output preserves readiness, durable state or retry/cancel acceptance.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project supplying native workspace access |
| knowledge_base | 是 | — | Actual native qualified KB ID |
| action | 否 | "readiness" | Inspect index state, retry failed work, or request safe-boundary cancellation Choices: readiness, run, progress, retry, cancel |
| task_id | 否 | null | Native indexing-run task ID required for cancel |

## workbench_search_sources

Inspect the actual configured discovery sources for the current account.
Input selects status; output contains native source names and availability flags.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "status" | Read actual paper, web, institution and metrics provider configuration flags |

## workbench_web_search

Search real web pages through the Workbench discovery provider.
Input is a query and source-supported domain filter; output is the native search response.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| q | 是 | — | Web query of 3 to 600 characters |
| action | 否 | "search" | Search using the account's actual configured web provider |
| kind | 否 | "all" | Use general search or the source's publisher-domain filter Choices: all, journal, template |

## workbench_paper_search

Search existing literature providers and retain stable native selection identities.
Input is a project query/provider/window/page; output preserves bibliographic records and source status.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project anchoring the discovery task |
| q | 是 | — | Actual literature search query |
| action | 否 | "search" | Search bibliographic sources without claiming full-text verification |
| source | 否 | "auto" | Native provider selection; configured credentials remain server-side Choices: auto, scholar_mcp, academic_web, crossref, semantic, scholar, wos |
| years | 否 | 0 | Publication-year window; zero applies no year filter Choices: 0, 5, 10 |
| newest | 否 | false | Request the upstream source's newest-first ordering |
| page | 否 | 1 | Native result page from 1 to 50 |
| limit | 否 | 20 | Results from 1 to 20; Scholar MCP natively caps this at 10 |

## workbench_literature

Manage source-bound literature attachments without replacing their identity checks.
Input supplies PDF files or native source identities; output is attachment metadata, original bytes or a preview.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Existing owned research project ID |
| action | 否 | "list" | List, attach, identify or read source documents Choices: list, upload, match, read, preview |
| asset | 否 | null | Actual project-literature or linked-KB relative source path |
| library | 否 | "workspace" | workspace or an actual project-bound native KB ID |
| file_paths | 否 | null | Local PDF files for upload, each at most 100 MiB |
| folder | 否 | "reading" | Purpose category for new PDF attachments Choices: references, validation, methods, reading |
| output_dir | 否 | null | Local download base directory; a fresh child is created per artifact |

## workbench_literature_organization

Organize research sources by purpose and native source-based classification.
Input identifies sources or requests classification; output is assignments, classification state or a native job ID.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Existing owned project ID |
| action | 否 | "folders" | Read/assign purpose folders or inspect/request source-based classification Choices: folders, assign, classification, classify |
| asset | 否 | null | Actual source identity required for assign |
| category | 否 | "reading" | Source-supported literature purpose Choices: references, validation, methods, reading |

## workbench_paper_downloads

Use the existing authorized document-download queue and its real progress.
Input supplies source identities or task IDs; output retains queue, transfer and receipt states.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "worker_status" | Queue or inspect the existing authorized ScanSci download pipeline Choices: enqueue, list, worker_status, retry, cancel |
| project_id | 否 | null | Owned project ID required except for worker_status |
| entries | 否 | null | One to 100 source-supported DOI/arXiv/title metadata entries |
| folder | 否 | "reading" | Purpose category for queued attachments Choices: references, validation, methods, reading |
| job_id | 否 | null | Native download task ID for retry or cancel |

## workbench_reader

Open and inspect the actual project-bound PDF reading protocol.
Input identifies a real source/document/block; output preserves parsed source blocks, saved states or artifacts.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project containing the manuscript or source PDF |
| action | 否 | "open" | Open a real source PDF, read its native blocks/state, or locate an image Choices: open, content, image |
| area | 否 | "paper" | Manuscript or attached literature source Choices: paper, literature |
| asset | 否 | "manuscript/main.json" | Actual source path; manuscript/main.json is the current manuscript |
| library | 否 | "" | workspace or the actual bound KB for literature; empty for manuscript |
| title | 否 | "" | Optional source display title |
| width | 否 | 1000 | Native reader viewport width |
| theme | 否 | "snow" | Native reader theme identifier |
| document_id | 否 | null | Native reader document ID returned by open |
| view | 否 | "blocks" | Native parsed content, saved translations, options or original PDF Choices: blocks, translations, options, source |
| block_id | 否 | null | Native image block ID required for image |
| output_dir | 否 | null | Download base directory for the original PDF; each call creates a fresh child |

## workbench_translation

Translate existing source content through the application's native model protocols.
Input selects a manuscript or reader document; output retains native jobs or accepted reader operations.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project containing the selected manuscript or source PDF |
| action | 否 | "manuscript" | Translate an editable manuscript, start native PDF translation or export saved PDF translation Choices: manuscript, reader_start, export_pdf |
| target | 否 | "zh-CN" | Target language; reader_start accepts en or zh-CN |
| use_native | 否 | true | Use the assigned native model for manuscript translation instead of the saved Workbench API |
| source | 否 | "source" | Translate the source manuscript or its existing editable translation Choices: source, translation |
| document_id | 否 | null | Actual native reader document ID for reader_start or export_pdf |
| columns | 否 | 2 | Columns in the native saved-translation PDF export Choices: 1, 2 |

## workbench_annotations

Manage questions anchored to actual project artifacts and native audit history.
Input is an annotation record or selected question IDs; output is native annotated state or submission receipt.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project containing the real annotated artifact |
| action | 否 | "list" | Read, create/update anchored questions or submit selected native question IDs Choices: list, create, update, submit |
| area | 否 | "" | Optional list filter or annotation content area Choices: , paper, literature, code, slides, image |
| asset | 否 | "" | Actual artifact path or source identity |
| identifier | 否 | null | Existing annotation ID required for update |
| payload | 否 | null | Native annotation fields: title,quote,body,color,status,locator,origin; area/asset can also be supplied |
| ids | 否 | null | Selected annotation IDs required for submit |

## workbench_review

Continue source-anchored review and record actual project changes and checks.
Input is chat, a truthful receipt or stage quality request; output preserves native events, jobs and quality decisions.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project containing the review context |
| action | 否 | "history" | Read review/chat, record work, or submit/read native version-bound stage quality reviews Choices: history, chat_history, chat_send, receipt, quality_rubric, quality_submit, quality_list, quality_gate |
| area | 否 | "paper" | Native content area for review chat Choices: paper, literature, code, slides, image |
| asset | 否 | "" | Actual source/artifact path for chat_send |
| message | 否 | null | User-authorized review message, up to 16000 characters |
| title | 否 | "" | Optional artifact or question title |
| quote | 否 | "" | Actual quoted source passage |
| locator | 否 | null | Native page/paragraph/file locator and optional current_draft editor object |
| question_ids | 否 | null | Existing project question IDs addressed by a receipt |
| artifacts | 否 | null | Native receipt artifact records with existing project-root-relative path |
| validation | 否 | null | Actual textual or structured validation results for the receipt |
| limitations | 否 | null | Actual remaining limitations for the receipt |
| resolved | 否 | false | Mark only the supplied receipt question IDs resolved |
| stage | 否 | "" | Stage ID for quality actions or optional receipt quality evaluation; empty preserves legacy receipts |
| purpose | 否 | "" | Presentation purpose ID for slides stages; optional for other stages |
| operation_id | 否 | "" | Stable operation ID for quality_submit or staged receipts; reuse only for identical input |
| artifact_paths | 否 | null | Project-root-relative stage artifacts; optional when the server has stage defaults |
| source_paths | 否 | null | Project-root-relative actual source evidence for the stage review |
| intended_use | 否 | "" | Specific purpose and claim scope for quality_submit |

## workbench_jobs

Read the actual state and outcomes of asynchronous project operations.
Input identifies a project and optional recent job; output retains native job status/result/error fields.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project whose latest native jobs are read |
| action | 否 | "status" | Read actual queued/running/completed/failed/interrupted jobs |
| job_id | 否 | null | Optional job ID filter within the latest 20 native project jobs |

## workbench_settings

Read masked account settings or update their explicitly supplied values.
Input contains setting changes; output is masked native configuration or saved/configured flags.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "get" | Read masked settings or merge explicitly supplied updates into current non-secret settings Choices: get, save |
| base_url | 否 | null | Optional HTTPS model API base URL |
| model | 否 | null | Optional model identifier |
| api_key | 否 | null | Optional new model API key; omitted/empty retains the saved secret |
| translation_prompt | 否 | null | Optional custom translation instruction; empty resets to the native default |
| literature_token | 否 | null | Optional new native literature token; never returned |
| literature_provider | 否 | null | Saved native default discovery provider |
| scholar_api_key | 否 | null | Optional new Scholar SerpApi key; never returned |
| wos_api_key | 否 | null | Optional new Web of Science key; never returned |
| web_search_api_key | 否 | null | Optional new web-search key; never returned |
| jcr_api_key | 否 | null | Optional new Clarivate metrics key; never returned |
| reviewer_mode | 否 | null | Inherit the Tutor account model or explicitly select a separate reviewer; omitted retains current mode |
| reviewer_base_url | 否 | null | Optional reviewer endpoint; omitted retains the current non-secret value |
| reviewer_model | 否 | null | Optional independent reviewer model; omitted retains the current value |
| reviewer_api_key | 否 | null | Optional new reviewer key; omitted or empty retains the server's saved secret |
| reviewer_supports_vision | 否 | null | Declare that the configured reviewer accepts image inputs; omitted retains current choice |

## workbench_author_profile

Manage manuscript author metadata independently of account authentication.
Input selects profile fields, manuscript context or institution search; output is native author data or candidates.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| action | 否 | "get" | Read/update author details, read current manuscript front matter or search real institutions Choices: get, save, preview, institutions |
| project_id | 否 | null | Owned project ID required for preview |
| name | 否 | null | Author name; omitted fields retain current values on save |
| affiliation | 否 | null | Author affiliation |
| email | 否 | null | Author contact email, separate from login credentials |
| orcid | 否 | null | Author ORCID in native 0000-0000-0000-0000 format |
| address | 否 | null | Author postal address |
| name_en | 否 | null | Author English name |
| affiliation_en | 否 | null | Author English affiliation |
| q | 否 | null | Institution query for the actual native ROR search |

## workbench_project_import

Import a user-selected source-bound research material bundle.
Input is the native manifest ZIP; output retains its asynchronous import job ID.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned destination project for the selected source bundle |
| file_path | 是 | — | Local ZIP up to 300 MiB with workbench-import.json and the required editable DOCX manuscript |
| action | 否 | "import" | Submit the source-supported native material import |

## workbench_knowledge_search

Retrieve source passages from the project's real PDFs or bound native index.
Input is a scoped query/mode; output preserves native passages, coverage, errors and provenance.

| 参数 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| project_id | 是 | — | Owned project limiting retrieval to its PDFs and bound native knowledge bases |
| query | 是 | — | Actual source query, trimmed/truncated to 600 characters by upstream; minimum length two |
| action | 否 | "search" | Retrieve through the existing source-text or native semantic operation |
| mode | 否 | "fulltext-keyword" | PDF/native text preview keywords or the original indexed native RAG Choices: fulltext-keyword, semantic |
| knowledge_base | 否 | "" | Optional project-bound KB ID; required for semantic mode |
| limit | 否 | 8 | Source results from 1 to 20 |
