---
name: research-workbench
description: Use the connected Research Workbench to retrieve source literature, manage project files, translate and edit manuscripts, refine figures, prepare confirmed presentations, or deliver source-bound artifacts and processing receipts.
---

# Research Workbench

Use the tools from this package against the actual signed-in account and selected project. [USAGE.md](../USAGE.md) covers installation and prerequisites; [TOOL_REFERENCE.md](../TOOL_REFERENCE.md) maps task actions and parameters.

1. Read `workbench_account` and `workbench_projects`. Select the user's current owned project; derive its native workspace from the returned record.
2. Read `workbench_rules(action="context", project_id=..., task=...)`, then the relevant skill originals it names. The current source, project API and user request govern this task.
3. Execute the appropriate tool. For source claims retain article identity, passage/page locator and access scope. For edits preserve revision/timestamp conflicts, original mathematical content and native editable objects.
4. Follow the native asynchronous state until the affected operation has a terminal result. Use the download/index/reader-specific state where applicable. Report an interrupted or unavailable dependency without calling it completed.
5. Inspect actual artifacts and write a `workbench_review(action="receipt")` with their paths, checks, source relations, stage, purpose and stable operation_id from the current task. Follow the returned quality job; use quality_list for evidence and quality_gate before automatic progression. quality_rubric provides current criteria, and quality_submit requests a new evaluation. Match the saved current version; retain missing checks and stale reviews as such. Revision is limited to two targeted rounds, with scientific choices and remaining failures returned to the author.

For literature, inspect available sources, search with the research question and compare actual candidates before selecting downloads. Use full text for claims that require full text. The paired ScanSci path delivers through cluster acceptance into the user's project.

For papers, begin with the current editable manuscript and evidence. Read the user-selected or generic template before rendering. Preserve named author information and label preview dates. Verify mathematical text, references and layout in the resulting file.

For figures, resolve the selected artist/image and original plotting source before changes. For slides, obtain the user's actual content, audience and template choices before recording confirmation and generating.

Dify's deployed HTTP adapter adds the active delivery `run_id` and retains its account/project scope. Use server-side project and task output paths there; local stdio uploads use actual local paths. Credentials belong to the configured transport, not the task payload.
