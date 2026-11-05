# Figure workspace design review · 2026-11-01

Purpose: a formal scientific authoring workspace. Preserve the useful Dito composer, readable conversation and theme tokens. Use Plotly react-chart-editor for progressively disclosed plot settings and Penpot for contextual object properties. Apply the installed Anthropic frontend-design and Vercel web-design-guidelines skills. Ratings below are a local heuristic review on a ten-point scale, not third-party scores or usability-study results.

Design: quiet studio chrome, white scientific artboard, a single blue selection accent (#4c87c9; light #2764a4). Existing DeepTutor light/dark theme remains authoritative for chrome. Type: existing Geist and Chinese UI fallback, 13px controls, 12px secondary text, 15px contextual heading; scientific figure typography is independently edited. Layout: a broad artboard, a 280px contextual inspector, compact Dito conversation. No new dashboard cards. Align fields and action groups on consistent 8/12/16px spacing.

Plan critique: the earlier toolbar used unlabeled icons and a flat list of every Matplotlib artist. That encodes internal implementation, not the author's task. Replace it with grouped layers, one axis panel with X/Y/Z tabs, whole-figure typography and optional local overrides. Visual cells must come from the authored layout, including spans and separate colorbars. Preserve author positions until an explicit edit. Clamp selection affordances to the paper.

Baseline scores: grouping 3; typography workflow 4; toolbar discoverability 4; menu redundancy 3; visual hierarchy 4; layout geometry 2; selection geometry 2; keyboard/accessibility 4; asynchronous feedback 6; release clarity 3. Actual outcomes and revised scores will be recorded after browser verification.


Source references actually read:
- https://github.com/anthropics/skills/tree/main/skills/frontend-design (installed original skill)
- https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines (installed original skill)
- https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md (fetched rules in WEB_INTERFACE_GUIDELINES.md)
- https://github.com/plotly/react-chart-editor and live demo https://plotly.github.io/react-chart-editor/
- https://help.penpot.app/user-guide/designing/layers/
- https://help.penpot.app/user-guide/designing/flexible-layouts/
- https://penpot.app/blog/the-ultimate-guide-to-penpot-layouts/

Implementation findings: the old figure13 picker contained201flat options and12independent grid cells. The four standalone scalar-mappable colorbars were mistaken for subplots. Authored insets and twin axes also incorrectly participated in the grid. The final model separates main cells from nested/overlay axes and detached colorbars, using actual per-row geometry and native GridSpec spans. Inspection does not alter figure positions. Source images/data are not replaced by opening or previewing the canvas.

Formal release cleanup: renamed the real project Mois-Net · 水分扩散 via the normal native-backed UI. Archived only the two known agent-created examples; removed demo installation from the production UI/backend. Ten developer verification files/folders and the exact two-message translation smoke check moved to recoverable project trash. Kept manuscript, data, original artwork, source programs and provenance documents. The page uses no-store and release header2026.11.01-studio; final browser checks pending.


Final bounded review is recorded in ../verification/正式绘图界面复核.md and studio-ui-ratings.json. Final browser build/release identity will be appended after the last refresh. No new tests or synthetic authoring contents are installed in the formal project.
