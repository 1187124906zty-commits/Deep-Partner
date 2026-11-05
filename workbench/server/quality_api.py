"""Version-bound stage review endpoints shared by website and workflow nodes."""
from __future__ import annotations
import asyncio
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import Depends, Request
from pydantic import BaseModel, Field

from .storage import Conflict, atomic_json, child
from .native import actor, headers, BASE


class ReviewInput(BaseModel):
    operation_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    stage: str
    purpose: str = ''
    artifact_paths: list[str] = Field(default_factory=list, max_length=20)
    source_paths: list[str] = Field(default_factory=list, max_length=30)
    intended_use: str = Field(default='', max_length=3000)
    parent_review_id: str = ''


class OverrideInput(BaseModel):
    operation_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    confirmed: Literal[True]
    reason: str = Field(min_length=3, max_length=2000)


DEFAULT_PATHS = {'slides-plan': ['slides/plan.json'], 'slides-export': ['slides/exports/研究汇报.pptx'],
                 'writing': ['manuscript/main.json'], 'translation': ['manuscript/main.json']}


def read_settings(api_path, owner):
    path = api_path(owner)
    return json.loads(path.read_text(encoding='utf8')) if path.is_file() else {}


def file_binding(root, relative):
    target = child(root, relative)
    if not target.is_file():
        raise ValueError('评审材料不存在：' + relative)
    stat = target.stat()
    return {'path': target.relative_to(root).as_posix(), 'modified': stat.st_mtime_ns, 'size': stat.st_size}


def current_bindings(root, stage, purpose, paths, source_paths=()):
    from .stage_reviews import rubric
    sources = [file_binding(root, value) for value in source_paths]
    return {'stage_version': 'quality-stage.v1',
            'source_version': json.dumps(sources, ensure_ascii=False, sort_keys=True),
            'rule_version': rubric(stage, purpose)['version'],
            'artifacts': [file_binding(root, value) for value in paths]}



def normalized_bindings(value):
    return {**value, 'artifacts': sorted([{k:v for k,v in x.items() if k!='size'} for x in value['artifacts']], key=lambda x:x['path'])}

def source_packet(root, paths):
    """Read bounded actual files and disclose extraction limits to the reviewer."""
    rows = []
    remaining = 180_000
    for relative in paths:
        binding = file_binding(root, relative)
        target = child(root, relative)
        method = 'utf8'
        if target.suffix.lower() in ('.pdf', '.pptx'):
            if target.suffix.lower() == '.pdf':
                import fitz
                with fitz.open(target) as doc:
                    content = '\n'.join(f'PDF page {i+1}\n' + page.get_text() for i, page in enumerate(doc))
                method = 'pdf_text_layer_only'
            else:
                from pptx import Presentation
                presentation = Presentation(target)
                content = '\n'.join(f'Slide {i+1}\n' + '\n'.join(
                    shape.text for shape in slide.shapes if shape.has_text_frame)
                    for i, slide in enumerate(presentation.slides))
                method = 'pptx_text_objects_only'
        elif target.suffix.lower() in ('.md', '.txt', '.json', '.py', '.csv', '.tex', '.yaml', '.yml', '.toml', '.r', '.m', '.jl'):
            if target.stat().st_size > 2_000_000:
                raise ValueError('评审文本过大，请按阶段选择需要检查的材料')
            content = target.read_text(encoding='utf8')
        elif target.suffix.lower() == '.docx':
            from docx import Document
            document = Document(target)
            content = '\n'.join(p.text for p in document.paragraphs)
            content += '\n' + '\n'.join(' | '.join(c.text for c in row.cells)
                                         for table in document.tables for row in table.rows)
            method = 'docx_paragraph_and_table_text_only'
        else:
            content = ''
            method = 'file_metadata_only'
        taken = content[:remaining]
        remaining -= len(taken)
        rows.append({'binding': binding, 'extraction': method, 'content': taken,
                     'truncated': len(taken) < len(content)})
        if file_binding(root, relative) != binding:
            raise Conflict('评审读取期间材料发生变化，请重新提交')
    return rows


def review_and_revise_plan(store, api_path, owner, pid, payload, native_headers):
    """Execute at most two bounded wording/layout repairs; scientific choices go to author."""
    from .review_transport import complete_review
    root = store.path(owner, pid)
    target = root / 'slides/plan.json'
    project = store.get(owner, pid)
    parent = ''
    history = []
    for round_number in range(3):
        request = {**payload, 'operation_id': payload['operation_id'] + '-r' + str(round_number),
                   'parent_review_id': parent}
        result = run_review(store, api_path, owner, pid, request, native_headers)
        history.append(result['review_id'])
        if result.get('can_proceed') or not result.get('revision_allowed'):
            return {**result, 'review_history': history}
        issues = result.get('issues') or []
        if not issues or any(x.get('scope') not in ('wording', 'layout') for x in issues):
            return {**result, 'review_history': history, 'stop_reason': 'author_or_executor_required'}
        source_paths = payload.get('source_paths') or ['manuscript/main.json']
        bound_now = current_bindings(root,'slides-plan',payload.get('purpose',''),['slides/plan.json'],source_paths)
        if normalized_bindings(bound_now)!=result['bindings']:
            raise Conflict('评分后材料已改变，不将旧意见自动应用到新计划')
        plan = json.loads(target.read_text(encoding='utf8'))
        allowed_sections=set()
        for issue in issues:
            refs=issue.get('evidence_refs') or [{'path':issue.get('path'),'locator':issue.get('locator',{})}]
            for ref in refs:
                if ref.get('path')!='slides/plan.json':continue
                loc=ref.get('locator') or {}
                if isinstance(loc.get('section_index'),int) and not isinstance(loc['section_index'],bool):allowed_sections.add(loc['section_index'])
                if loc.get('section_id') is not None:
                    allowed_sections.update(i for i,section in enumerate(plan.get('sections',[])) if section.get('id')==loc['section_id'])
        if not allowed_sections:
            return {**result,'review_history':history,'stop_reason':'repair_needs_section_locator'}
        before = file_binding(root, 'slides/plan.json')
        prompt = ('只针对给定issues修订幻灯片的title/content/notes。保持研究事实、数字、来源、图表引用、'
                  '页面id、模板与用途身份及其它字段。需要新数据、改变主张或作者选择时不能代替决定。'
                  '返回完整plan JSON对象，不能返回评分。')
        text = json.dumps({'plan': plan, 'issues': issues,
                           'source': source_packet(root, payload.get('source_paths') or ['manuscript/main.json'])}, ensure_ascii=False)
        answer, _ = complete_review(read_settings(api_path, owner), native_headers, project['native_id'], prompt, text, BASE)
        repaired = json.loads(answer.strip().removeprefix('```json').removesuffix('```').strip())
        old_sections, new_sections = plan.get('sections'), repaired.get('sections')
        if not isinstance(new_sections, list) or not new_sections or len(old_sections or []) != len(new_sections):
            return {**result, 'review_history': history, 'stop_reason': 'repair_contract_not_met'}
        # Renderer identities and source inventories are fixed during automatic wording repair.
        for key in plan:
            if key != 'sections' and repaired.get(key) != plan[key]:
                raise ValueError('自动修订改变了模板、来源或其它计划身份，原计划保留')
        if set(repaired)!=set(plan):raise ValueError('自动修订改变了计划结构，原计划保留')
        token_pattern=r'(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|\b(?:not|no|without|never|may|might|cannot)\b|不|未|无'
        for index,(old, new) in enumerate(zip(old_sections, new_sections)):
            if index not in allowed_sections and old!=new:
                raise ValueError('自动修订改变了未定位的问题页面，原计划保留')
            if set(new)-set(old)-{'title','content','notes'} or any(new.get(k) != v for k, v in old.items() if k not in ('title', 'content', 'notes')):
                raise ValueError('自动修订改变了页面身份或图表引用，原计划保留')
            if not all(isinstance(new.get(k,''),str) for k in ('title','content','notes')):
                raise ValueError('自动修订文字字段格式无效，原计划保留')
            old_text=' '.join(str(old.get(k,'')) for k in ('title','content','notes'))
            new_text=' '.join(new.get(k,'') for k in ('title','content','notes'))
            if sorted(re.findall(token_pattern,old_text,re.I))!=sorted(re.findall(token_pattern,new_text,re.I)):
                return {**result,'review_history':history,'stop_reason':'repair_requires_scientific_choice'}
        if repaired == plan:
            return {**result, 'review_history': history, 'stop_reason': 'no_artifact_change'}
        with store.lock(pid):
            if file_binding(root, 'slides/plan.json') != before or normalized_bindings(current_bindings(root,'slides-plan',payload.get('purpose',''),['slides/plan.json'],source_paths))!=result['bindings']:
                raise Conflict('修订期间原计划或来源已更新，保留当前版本')
            store.replace(owner, pid, target, json.dumps(repaired, ensure_ascii=False, indent=2).encode(), '根据阶段评分定向修订文字与布局')
        parent = result['review_id']
    return {**result, 'review_history': history, 'stop_reason': 'revision_limit'}



def review_images(root, paths, max_pages=12):
    """Render selected artifact pages for a configured visual reviewer, with explicit coverage."""
    import base64
    import fitz
    images, coverage = [], []
    for relative in paths:
        target = child(root, relative)
        pdf = target if target.suffix.lower()=='.pdf' else target.with_suffix('.pdf') if target.suffix.lower()=='.pptx' else None
        if pdf is None or not pdf.is_file():
            continue
        if target.suffix.lower()=='.pptx' and pdf.stat().st_mtime_ns < target.stat().st_mtime_ns:
            continue
        with fitz.open(pdf) as document:
            count = min(len(document), max_pages-len(images))
            for i in range(count):
                page=document[i];scale=min(1.5,1400/max(page.rect.width,page.rect.height))
                data=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
                images.append('data:image/png;base64,'+base64.b64encode(data).decode())
            coverage.append({'path':pdf.relative_to(root).as_posix(),'pages_rendered':list(range(1,count+1)),'total_pages':len(document)})
        if len(images)>=max_pages:break
    return images,coverage


def deterministic_checks(root, bindings, stage, source_paths):
    checks = [{'id': 'artifact_current', 'status': 'passed', 'source': 'server',
               'performed_by': 'quality_api.file_binding', 'evidence': bindings['artifacts']}]
    if stage.startswith('slides-'):
        valid = bool(source_paths) and all(child(root, p).is_file() for p in source_paths)
        checks.append({'id': 'source_refs_valid', 'status': 'passed' if valid else 'unknown',
                       'source': 'server', 'performed_by': 'quality_api.source_file_presence',
                       'evidence': {'paths': source_paths, 'scope': 'Source files exist; semantic support is independently reviewed.'}})
    if stage == 'slides-export':
        report_path = root / 'slides/verification.json'
        status = 'unknown'
        evidence = {'path': 'slides/verification.json', 'scope': 'Rendered geometry and text presence only'}
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding='utf8'))
            export = child(root, bindings['artifacts'][0]['path'])
            newer = report_path.stat().st_mtime_ns >= export.stat().st_mtime_ns
            raw = report.get('render_validation', {})
            if newer and raw:
                required = {'complete_visible_text': True, 'page_bounds': True, 'text_line_overlap': False, 'content_text_image_overlap': False}
                if all(key in raw for key in required):
                    status = 'passed' if all(raw[key] is expected for key, expected in required.items()) else 'failed'
                evidence['measurement'] = raw
        checks.append({'id': 'render_validation', 'status': status, 'source': 'server',
                       'performed_by': 'slide_quality.verify_rendered', 'evidence': evidence})
    return checks


def run_review(store, api_path, owner, pid, payload, native_headers, progress=None):
    from .stage_reviews import rubric, save_review, list_reviews
    from .review_transport import complete_review, review_prompt
    if progress:progress('bind','正在核对评审产物与来源版本')
    stage, purpose = payload['stage'], payload.get('purpose', '')
    project = store.get(owner, pid)
    root = store.path(owner, pid)
    paths = payload.get('artifact_paths') or DEFAULT_PATHS.get(stage, [])
    if not paths:
        raise ValueError('为这个阶段选择实际产物路径')
    sources = payload.get('source_paths') or (['manuscript/main.json'] if stage.startswith('slides-') else [])
    bindings = current_bindings(root, stage, purpose, paths, sources)
    request = {'operation_id': payload['operation_id'], 'stage': stage, 'purpose': purpose,
               'bindings': bindings, 'input_refs': [{'path': p} for p in sources], 'parent_review_id': payload.get('parent_review_id', '')}
    # A single operation lock covers the provider call as well as persistence.
    with store.lock('quality-call:' + pid + ':' + payload['operation_id']):
        operation = root / '.workbench/quality-operations' / (payload['operation_id'] + '.json')
        if operation.is_file():
            prior = json.loads(operation.read_text(encoding='utf8'))
            if prior.get('payload') != payload:
                raise Conflict('相同评审命令对应了不同输入')
            if prior.get('result'):
                if normalized_bindings(bindings)!=prior['result'].get('bindings'):
                    raise Conflict('这个评审命令已绑定旧版本，请读取旧结果或用新命令评审当前产物')
                return prior['result']
        packet = {'rubric': rubric(stage, purpose), 'intended_use': payload.get('intended_use', ''),
                  'artifacts': source_packet(root, paths), 'sources': source_packet(root, sources)}
        settings = read_settings(api_path, owner)
        images, image_coverage = review_images(root, paths) if settings.get('reviewer_mode')=='custom' and settings.get('reviewer_supports_vision') else ([],[])
        packet['image_coverage']=image_coverage
        if progress:progress('evaluate','正在独立评审当前产物')
        answer, identity = complete_review(settings, native_headers, project['native_id'], review_prompt(),
                                            json.dumps(packet, ensure_ascii=False), BASE, images=images)
        if current_bindings(root, stage, purpose, paths, sources) != bindings:
            raise Conflict('评审期间来源或产物已更新，本轮结果不用于新版本')
        if progress:progress('check','正在核验来源位置与确定性检查项')
        checks = deterministic_checks(root, bindings, stage, sources)
        identity['input_coverage'] = [{'path': x['binding']['path'], 'extraction': x['extraction'], 'truncated': x['truncated']} for x in packet['artifacts'] + packet['sources']]
        identity['visual_review_performed'] = bool(images)
        identity['image_coverage'] = image_coverage
        if progress:progress('save','正在保存评审结果与可回查位置')
        result = save_review(store, owner, pid, request, answer, hard_checks=checks, evaluator=identity,
                             actor={'id': owner, 'role': 'author'})
        result['input_coverage'] = [{'path': x['binding']['path'], 'extraction': x['extraction'],
                                     'truncated': x['truncated']} for x in packet['artifacts'] + packet['sources']]
        result['visual_review_performed'] = bool(images)
        atomic_json(operation, {'payload': payload, 'result': result})
        return result


def latest_gate(store, owner, pid, stage, purpose='', paths=None, source_paths=None):
    from .stage_reviews import list_reviews
    root = store.path(owner, pid)
    prior = list_reviews(store, owner, pid, stage=stage, purpose=purpose).get('latest')
    if paths is None:
        paths = [x['path'] for x in prior['bindings']['artifacts']] if prior else DEFAULT_PATHS.get(stage, [])
    if source_paths is None and prior:
        sources = [x['path'] for x in json.loads(prior['bindings'].get('source_version') or '[]')]
    else:
        sources = source_paths or (['manuscript/main.json'] if stage.startswith('slides-') else [])
    if not paths:
        return {'can_proceed': False, 'decision': 'not_reviewed', 'reason': '尚未指定阶段产物'}
    missing = [p for p in paths + sources if not child(root, p).is_file()]
    if missing:
        return {'can_proceed': False, 'automatic_flow': False,
                'decision': 'stale' if prior else 'not_reviewed',
                'reason': '当前阶段的产物或来源尚不存在，保留历史评审但不放行',
                'missing_paths': missing, 'review': None}
    bindings = current_bindings(root, stage, purpose, paths, sources)
    rows = list_reviews(store, owner, pid, stage=stage, purpose=purpose, current_bindings=bindings)
    selected = rows.get('current')
    return {**rows, 'review': selected, 'can_proceed': bool(selected and selected.get('can_proceed')),
            'automatic_flow': bool(selected and selected.get('automatic_flow')),
            'decision': selected.get('decision') if selected else 'not_reviewed'}


def receipt_review(store, api_path, run_job, owner, pid, receipt, native_headers):
    """Start a version-bound review for an explicitly identified workflow deliverable."""
    if not receipt.get('stage'):
        return {'status': 'not_reviewed', 'required': True,
                'endpoint': '/research/api/projects/' + pid + '/quality/reviews', 'automatic_flow': False}
    from .stage_reviews import rubric
    stage, purpose = receipt['stage'], receipt.get('purpose', '')
    rubric(stage, purpose)
    operation = 'receipt-' + str(receipt.get('operation_id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{9,100}', operation):
        raise ValueError('阶段交付需要稳定的operation_id')
    paths = [x['path'] for x in receipt.get('artifacts', [])]
    sources = list(dict.fromkeys(p for x in receipt.get('artifacts', []) for p in x.get('source_paths', [])))
    payload = {'operation_id': operation, 'stage': stage, 'purpose': purpose,
               'artifact_paths': paths, 'source_paths': sources,
               'intended_use': '\n'.join(x.get('summary', '') for x in receipt.get('artifacts', []))}
    root = store.path(owner, pid)
    current_bindings(root, stage, purpose, paths, sources)
    marker = root / '.workbench/quality-submissions' / (operation + '.json')
    with store.lock('quality-submit:' + pid):
        if marker.is_file():
            prior = json.loads(marker.read_text())
            if prior['payload'] != payload:
                raise Conflict('阶段交付命令已用于不同内容')
            jid = prior['job_id']
        else:
            jid = store.job(owner, pid, 'quality-review',{'subject':'、'.join(Path(p).name for p in paths[:2]),'stage':stage,'purpose':purpose})
            atomic_json(marker, {'payload': payload, 'job_id': jid})
            run_job(jid, lambda: run_review(store, api_path, owner, pid, payload, native_headers,progress=lambda step,message:store.set_job(jid,step=step,stage=message)))
    return {'status': 'pending', 'job_id': jid, 'stage': stage, 'purpose': purpose,
            'gate': '/research/api/projects/' + pid + '/quality/gate?stage=' + stage + '&purpose=' + purpose,
            'automatic_flow': False}


def install(app, store, api_path, run_job):
    @app.get('/research/api/quality/rubric')
    async def get_rubric(stage: str, purpose: str = '', user=Depends(actor)):
        from .stage_reviews import rubric
        return rubric(stage, purpose)

    @app.get('/research/api/projects/{pid}/quality/reviews')
    async def reviews(pid: str, stage: str = '', purpose: str = '', user=Depends(actor)):
        from .stage_reviews import list_reviews
        store.get(user['id'], pid)
        rows = list_reviews(store, user['id'], pid, stage=stage, purpose=purpose)
        if stage and rows.get('latest'):
            previous = rows['latest']; bound = previous['bindings']
            paths = [x['path'] for x in bound['artifacts']]
            sources = json.loads(bound.get('source_version') or '[]')
            bindings = current_bindings(store.path(user['id'], pid), stage, purpose, paths, [x['path'] for x in sources])
            return list_reviews(store, user['id'], pid, stage=stage, purpose=purpose, current_bindings=bindings)
        return rows

    @app.post('/research/api/projects/{pid}/quality/reviews')
    async def submit(request: Request, pid: str, payload: ReviewInput, user=Depends(actor)):
        owner = user['id']
        store.get(owner, pid)
        value = payload.model_dump()
        # Validate references before accepting a background model job.
        root = store.path(owner, pid)
        paths = value['artifact_paths'] or DEFAULT_PATHS.get(value['stage'], [])
        if not paths:
            raise ValueError('为这个阶段选择实际产物路径')
        current_bindings(root, value['stage'], value['purpose'], paths, value['source_paths'])
        op = root / '.workbench/quality-submissions' / (value['operation_id'] + '.json')
        with store.lock('quality-submit:' + pid):
            if op.is_file():
                prior = json.loads(op.read_text(encoding='utf8'))
                if prior['payload'] != value:
                    raise Conflict('相同评审命令对应了不同输入')
                return {'job_id': prior['job_id'], 'deduplicated': True}
            jid = store.job(owner, pid, 'quality-review',{'subject':'、'.join(Path(p).name for p in paths[:2]),'stage':value['stage'],'purpose':value.get('purpose','')})
            atomic_json(op, {'payload': value, 'job_id': jid})
        run_job(jid, lambda: run_review(store, api_path, owner, pid, value, headers(request),progress=lambda step,message:store.set_job(jid,step=step,stage=message)))
        return {'job_id': jid, 'deduplicated': False}

    @app.get('/research/api/projects/{pid}/quality/gate')
    async def gate(pid: str, stage: str, purpose: str = '', artifact_path: str = '', user=Depends(actor)):
        store.get(user['id'], pid)
        return latest_gate(store, user['id'], pid, stage, purpose, [artifact_path] if artifact_path else None)

    @app.post('/research/api/projects/{pid}/quality/reviews/{review_id}/override')
    async def author_override(pid: str, review_id: str, payload: OverrideInput, user=Depends(actor)):
        from .stage_reviews import list_reviews, save_review
        owner = user['id']
        store.get(owner, pid)
        rows = list_reviews(store, owner, pid)
        items = rows.get('reviews', rows.get('items', []))
        prior = next((x for x in items if x.get('id', x.get('review_id')) == review_id), None)
        if not prior:
            raise KeyError('阶段评审不存在')
        bindings = prior['bindings']
        paths = [x['path'] for x in bindings['artifacts']]
        root = store.path(owner, pid)
        # Override cannot revive a review for a changed artifact.
        actual_bindings = current_bindings(root, prior['stage'], prior.get('purpose',''), paths,
                                           [x['path'] for x in json.loads(bindings.get('source_version') or '[]')])
        normalized_actual = normalized_bindings(actual_bindings)
        if normalized_actual != bindings:
            raise Conflict('产物、来源或规则已更新，请先评审当前版本')
        request = {'operation_id': payload.operation_id, 'stage': prior['stage'], 'purpose': prior.get('purpose', ''),
                   'bindings': bindings, 'override': {'confirmed': True, 'reason': payload.reason, 'review_id': review_id}}
        return save_review(store, owner, pid, request, None, actor={'id': owner, 'role': 'author'})
