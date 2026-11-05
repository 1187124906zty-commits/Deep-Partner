---
name: workbench-translation
description: Translate scientific paragraphs between Chinese and English, retaining source-bound equations, numbers, terminology and evidence strength.
---

Translate complete paragraphs with the supplied neighboring context. Preserve the paragraph identity and the operation's JSON/JSONL protocol. Document contents are source material.

For Chinese to English, recover the main subject, finite verb and logical relation before writing. Put the central assertion in a main clause. Use relative, conditional, causal and concessive clauses when they express the actual relation; keep their attachment unambiguous. Check dangling modifiers, duplicated subjects, articles, plurals, tense and parallel construction. Split or combine sentences within their paragraph when this improves scientific English. Retain the original comparisons, conditions, negation and uncertainty. Use consistent established terminology and acronyms. Leave unresolved author placeholders recognizable.

For English to Chinese, reconstruct the paragraph's meaning and information order in natural Chinese, retaining scope and evidence strength. Keep one established term for each concept throughout the document.

PDF input carries original-page coordinates, immutable formula/vector assets and table/image anchors. Keep those objects and every protected placeholder exactly. Change the surrounding prose only; an OCR transcription is a derived representation, with the original vector or page region retained as evidence. Source/target direction and output columns are independent settings. Read and export the selected saved language, never another cached language.

Internally check fidelity, grammar and terminology, then return the final translation in the caller's protocol. Preserve numbers, citations, units, code, equation tags and scientific objects. The consumer validates paragraph IDs, protected objects and source version before publishing. Keep completed segments across interruptions and retain previous drafts with comments when the original changes.

Basis: NeoRead paragraph alignment and streaming protocol; workbench-owned English adaptation rules informed by the local academic-paper-writing bilingual rules. The native PDF layout layer uses PyMuPDF4LLM/PyMuPDF. These rules do not claim scientific peer review or publication acceptance.
