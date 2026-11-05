import path from 'node:path';
import { pathToFileURL } from 'node:url';
const skill='C:/Users/DEVELOPER/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const workspaceDir='D:/Development/询问/dify-research-deployment';
const outputDir=path.join(workspaceDir,'reports/氯硫建模逻辑图-20261104');
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
 workspaceDir,
 candidatePath:path.join(outputDir,'.build/建模逻辑_模板版_draft.pptx'),
 finalPath:path.join(outputDir,'氯硫耦合建模逻辑图_清晰版.pptx'),
 pythonExecutable:'C:/Users/DEVELOPER/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:1,
 requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],
 verifyArtifactToolImport:true,
 receiptPath:path.join(workspaceDir,'.local/model-map-pptx-validation-v2.json')
});
console.log(JSON.stringify(result));
