# DeepPartner shared product frontend

This is the formal shared Web/Desktop client. It imports the production DeepTutor ChatWorkspace and cached ChatRuntime directly; it does not copy a replacement chat implementation or load a remote page. Research Workbench business views render in the same React tree.

Build on the cluster, using the production source tree:

```sh
cd /work/home/cluster_user/research-projects/deeptutor-integration/research-workbench/src/unified-ui
export DEEPTUTOR_WEB_SOURCE=/work/home/cluster_user/research-projects/deeptutor-integration/frontend/src/web
export WORKBENCH_WEB_SOURCE=../web
npm install --no-audit --no-fund
npm test
npm run typecheck
npm run build
```

The output is `dist/`. Serve the same output at `/research/` on Web and `/` on the desktop. Vite uses relative assets; host navigation keeps the physical entry fixed and stores project/workspace/session in the query. `/api`, `/research/api`, and `/ws` are same-origin proxy contracts; desktop `/desktop/*` is served by its local protected host. Frontend version 0.4.0, turn protocol 2.0. No dynamic frontend updates.

`DEEPTUTOR_WEB_SOURCE` defaults to the local production integration checkout, not the older user-profile installation. Source aliases retain production turn recovery/cache fixes. A deployment must provide both source trees at build time. `dist` contains local Geist/Lora assets and original public renderer assets. Model/provider administration remains in the existing management pages.

Typechecking uses `scripts/typecheck.mjs` to resolve the runtime source roots and check the full imported graph. Diagnostics from unmodified production dependencies are listed separately in `upstream-type-diagnostics.txt` to locate integration errors, and any remaining diagnostic fails the check. React types and Tiptap/ProseMirror packages resolve to one shared dependency tree. Vite resolves and compiles the same actual source imports.

The current release was built by `D:/Development/询问/dify-research-deployment/ops/build_unified_ui.py` on Slurm job `25171485` (COMPLETED, 0:0), with zero imported-graph type errors and 23 passing tests. Registry DNS was unavailable on the cluster, so the script reused the already installed production and workbench packages; `dependency-inventory.json` records the actual direct dependency versions. A fresh environment can use npm install; the verified existing cluster should use the maintained build script rather than create another dependency tree.
