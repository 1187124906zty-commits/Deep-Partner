"""Version-bound stage judgments, independent checks, and append-only review history.

The caller authenticates the account and supplies bindings/checks obtained from
real project state. Model output may propose scores and located reasons only;
it cannot set checks, totals, progression, author identity, or revision counts.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import PurePosixPath
import uuid

from .storage import Conflict, atomic_json, child, now


VERSION = 'stage-review.v1'
MAX_REVISIONS = 2
ANCHORS = {
    '0': '缺失或与本次目标明显冲突',
    '1': '存在重大缺口',
    '2': '部分成立，仍需实质修改',
    '3': '满足本次用途，证据与表达充分',
    '4': '充分清楚，细节与取舍有说服力',
}

# These are product review criteria, not empirically calibrated scientific scales.
_CRITERIA = {
    'purpose_fit': ('问题与用途', '回答本阶段承诺的问题，信息深度与实际用途相符。'),
    'evidence_grounding': ('证据与来源', '主张能返回实际来源、数据或推导；保留条件与反证。'),
    'scientific_integrity': ('专业正确性与边界', '机制、数值、单位和条件一致，区分事实、推断、计划及未知。'),
    'audience_clarity': ('组织与可读性', '读者能够理解推理、图表和下一步，避免用格式代替信息。'),
    'novelty_position': ('已有工作与贡献位置', '用已核对的相关工作说明差别，不将改名或组合自动当作创新。'),
    'testability': ('可检验性', '明确可证伪的问题、比较对象、观测量与最小验证。'),
    'feasibility': ('可执行性', '资源、输入、步骤与时间足以支撑本次范围。'),
    'synthesis': ('综合判断', '比较方法的条件、分歧及适用边界，而非堆叠文献摘要。'),
    'counterevidence': ('反证与覆盖范围', '查明替代解释、相关反例和访问范围，不把未读当作已证实。'),
    'mechanism': ('机制成立', '解释所解决的物理、数学或数值问题以及方法为何可能改善它。'),
    'implementation': ('实现完整', '必要方程、输入输出、假设、算法和参数足以落实。'),
    'validation_plan': ('验证路径', '基准、消融、实验或理论比较能够区分主要解释。'),
    'validation_adequacy': ('验证充分', '实际检验覆盖关键主张，呈现误差、边界、收敛或不确定性。'),
    'reproducibility': ('可复现与交接', '真实输入、环境、命令及结果定位足以复查和承接。'),
    'argument': ('论证联系', '问题、方法、证据与结论相接，论断强度匹配证据。'),
    'actionability': ('修改可执行', '问题定位、影响和具体修订足以指导实际行动。'),
    'correctness': ('行为正确', '实现满足真实需求和边界，未用静态推测代替实际行为检查。'),
    'data_provenance': ('数据与对象来源', '图形、数据、引用及关联程序身份明确，未改造研究数值。'),
    'readability': ('展示可读', '文字、单位、图例和关系在实际阅读尺寸下清楚。'),
    'translation_fidelity': ('翻译忠实', '保留原意、论断强弱、数字、公式、引文和段落对应。'),
    'terminology': ('术语与符号', '术语一致，专业含义和符号保持，歧义据原文处理。'),
    'source_integrity': ('输入完整与身份', '资料身份、访问范围和解析状态明确，内容可返回原始材料。'),
    'delivery_integrity': ('交付完整与可访问', '所需产物真实存在、属于当前项目且可读取，限制清楚。'),
}
_STAGE_DIMENSIONS = {
    'idea': ('purpose_fit', 'novelty_position', 'testability', 'feasibility'),
    'landscape': ('purpose_fit', 'evidence_grounding', 'synthesis', 'counterevidence'),
    'concept': ('mechanism', 'implementation', 'validation_plan', 'scientific_integrity'),
    'evidence': ('evidence_grounding', 'scientific_integrity', 'validation_adequacy', 'reproducibility'),
    'writing': ('argument', 'evidence_grounding', 'scientific_integrity', 'audience_clarity'),
    'review': ('purpose_fit', 'evidence_grounding', 'scientific_integrity', 'actionability'),
    'code': ('purpose_fit', 'correctness', 'validation_adequacy', 'reproducibility'),
    'figure': ('scientific_integrity', 'data_provenance', 'readability', 'purpose_fit'),
    'translation': ('translation_fidelity', 'terminology', 'scientific_integrity', 'readability'),
    'slides-plan': ('purpose_fit', 'evidence_grounding', 'scientific_integrity', 'audience_clarity'),
    'slides-export': ('purpose_fit', 'evidence_grounding', 'scientific_integrity', 'audience_clarity'),
    'ingestion': ('source_integrity', 'data_provenance', 'purpose_fit', 'reproducibility'),
    'delivery': ('delivery_integrity', 'data_provenance', 'purpose_fit', 'actionability'),
}
_ADDITIONAL_CHECKS = {
    'slides-plan': ('source_refs_valid',),
    'slides-export': ('source_refs_valid', 'render_validation'),
    'code': ('code_validation',),
    'figure': ('figure_validation',),
    'translation': ('translation_integrity',),
    'evidence': ('evidence_validation',),
}


def rubric(stage: str, purpose: str = '') -> dict:
    """Return the current stage contract; PPT purposes come from the shared catalog."""
    if stage not in _STAGE_DIMENSIONS:
        raise ValueError('未知评审阶段：' + str(stage))
    dimensions = [
        {'id': identifier, 'label': _CRITERIA[identifier][0], 'description': _CRITERIA[identifier][1],
         'core': True, 'weight': 1, 'anchors': dict(ANCHORS)}
        for identifier in _STAGE_DIMENSIONS[stage]
    ]
    result = {'id': stage, 'stage': stage, 'purpose': purpose, 'version': VERSION,
              'minimum': 0, 'maximum': 4, 'core_minimum': 3, 'anchors': dict(ANCHORS),
              'dimensions': dimensions, 'max_revisions': MAX_REVISIONS,
              'aggregation': 'equal_weight_mean_of_evidence_supported_scores; core scores each >= 3',
              'required_hard_checks': [
                  {'id': identifier, 'required': True, 'critical': True}
                  for identifier in ('artifact_current',) + _ADDITIONAL_CHECKS.get(stage, ())]}
    if stage.startswith('slides-'):
        from .presentation_catalog import purpose_rule, purpose_rules
        card = purpose_rule(purpose)
        result['version'] += ':ppt-' + str(purpose_rules()['version'])
        result['purpose_guidance'] = deepcopy(card)
        existing = {d['id'] for d in dimensions}
        for dimension in card['evaluation_dimensions']:
            if dimension['id'] in existing:
                raise ValueError('汇报用途评价维度ID重复')
            existing.add(dimension['id'])
            dimensions.append({'id': dimension['id'], 'label': dimension['label'],
                               'description': dimension.get('question', dimension['label']),
                               'core': bool(dimension['core']), 'weight': 1, 'anchors': dict(ANCHORS)})
    return result


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _version(value, name):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(name + '需要明确的版本标识')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(name + '版本无效')
    if isinstance(value, str) and not value.strip():
        raise ValueError(name + '版本不能为空')
    return value


def _path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('评审引用需要真实项目路径')
    value = value.replace('\\', '/')
    parts = PurePosixPath(value)
    if parts.is_absolute() or ':' in value or '\x00' in value or '..' in parts.parts:
        raise ValueError('评审引用路径必须位于当前项目')
    return parts.as_posix()


def _bindings(value):
    if not isinstance(value, dict):
        raise ValueError('评审需要阶段、来源、规则及产物版本')
    result = {key: _version(value.get(key), key)
              for key in ('stage_version', 'source_version', 'rule_version')}
    artifacts = value.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError('评审至少绑定一个实际产物')
    result['artifacts'] = []
    seen = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError('产物版本记录无效')
        path = _path(item.get('path'))
        if path in seen:
            raise ValueError('产物路径重复：' + path)
        seen.add(path)
        ref = {'path': path}
        for key in ('revision', 'modified', 'version'):
            if key in item:
                ref[key] = _version(item[key], key)
        if len(ref) == 1:
            raise ValueError('产物缺少revision、modified或version：' + path)
        result['artifacts'].append(ref)
    result['artifacts'].sort(key=lambda item: item['path'])
    return result


def _request(value):
    if not isinstance(value, dict):
        raise ValueError('评审请求需要对象')
    operation = value.get('operation_id')
    if not isinstance(operation, str) or not operation.strip() or len(operation) > 240:
        raise ValueError('评审需要稳定的operation_id（1–240字符）')
    stage = value.get('stage')
    purpose = value.get('purpose', '')
    rules = rubric(stage, purpose)
    binding = _bindings(value.get('bindings'))
    if binding['rule_version'] != rules['version']:
        raise Conflict('评审规则已变化，请读取当前rubric后重新评审')
    request = deepcopy(value)
    request.update(operation_id=operation, stage=stage, purpose=purpose, bindings=binding)
    input_refs = request.get('input_refs', [])
    if not isinstance(input_refs, list):
        raise ValueError('input_refs需要列表')
    request['input_refs'] = []
    for item in input_refs:
        if not isinstance(item, dict):
            raise ValueError('输入来源引用无效')
        request['input_refs'].append({**item, 'path': _path(item.get('path'))})
    # Request metadata must also remain valid JSON; model output is normalized separately.
    _canonical(request)
    return request, rules


def _model_object(raw):
    if raw is None:
        return {}, ['未收到模型评审']
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith('```') and text.endswith('```'):
            text = text[text.find('\n') + 1:-3].strip()
        try:
            raw = json.loads(text, parse_constant=lambda _: None)
        except (TypeError, ValueError):
            return {}, ['模型评审不是有效JSON对象']
    if not isinstance(raw, dict):
        return {}, ['模型评审需要JSON对象']
    return raw, []


def _has_evidence(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value) and all(_has_evidence(item) for item in value)
    return False


def _json_pointer_tokens(pointer):
    """RFC 6901 sections 3–5 JSON-string form; '' denotes the whole document.

    URI fragments are a separate representation and are not accepted here.
    Decode ~1 before ~0 so that ~01 identifies a literal '~1', not '/'.
    https://www.rfc-editor.org/rfc/rfc6901.html#section-4
    """
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('json_pointer需要空字符串或以/开头的RFC6901定位')
    for index, character in enumerate(pointer):
        if character == '~' and (index + 1 == len(pointer) or pointer[index + 1] not in '01'):
            raise ValueError('json_pointer包含非法~转义')
    return [token.replace('~1', '/').replace('~0', '~') for token in pointer[1:].split('/')] if pointer else []


def _json_pointer_exists(document, pointer):
    current = document
    for token in _json_pointer_tokens(pointer):
        if isinstance(current, dict):
            if token not in current:
                return False
            current = current[token]
        elif isinstance(current, list):
            # RFC6901: zero or ASCII digits without a leading zero. '-' never
            # identifies an existing element, so it cannot support evidence.
            if not token or any(character not in '0123456789' for character in token) or (len(token) > 1 and token[0] == '0'):
                return False
            # Compare length before int conversion to bound arbitrarily long indices.
            if len(token) > len(str(len(current))):
                return False
            index = int(token)
            if index >= len(current):
                return False
            current = current[index]
        else:
            return False
    return True


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON对象成员重复，定位不明确')
        result[key] = value
    return result


def _evidence_refs(value, allowed_paths):
    if not isinstance(value, list) or not value:
        return [], '缺少可定位依据'
    refs = []
    for ref in value:
        if not isinstance(ref, dict):
            return [], '依据引用不是对象'
        try:
            path = _path(ref.get('path'))
        except ValueError:
            return [], '依据路径无效'
        if path not in allowed_paths:
            return [], '依据不在本轮绑定的产物或来源中：' + path
        locator = ref.get('locator')
        if not _has_evidence(locator):
            return [], '依据缺少页码、段落、页面ID或对象定位'
        if isinstance(locator, dict):
            if not set(locator) & {'page', 'line', 'paragraph', 'block_index', 'section_id', 'field',
                                   'object_id', 'block_id', 'figure_id', 'table_id', 'quote', 'kind', 'json_pointer'}:
                return [], '依据定位缺少可识别的位置字段'
            if 'json_pointer' in locator:
                try:
                    _json_pointer_tokens(locator['json_pointer'])
                except ValueError as error:
                    return [], str(error)
            for key in ('page', 'line', 'paragraph', 'block_index'):
                if key in locator and (isinstance(locator[key], bool) or
                                       not isinstance(locator[key], int) or
                                       locator[key] < (0 if key == 'block_index' else 1)):
                    return [], '依据数字定位无效：' + key
        try:
            _canonical(locator)
        except (TypeError, ValueError):
            return [], '依据定位不是有效JSON'
        refs.append({'path': path, 'locator': deepcopy(locator),
                     **({'quote': str(ref['quote'])} if ref.get('quote') else {})})
    return refs, ''


def _issues(raw, request):
    """Retain actionable, located model findings without accepting model state."""
    values = raw.get('issues', [])
    if not isinstance(values, list):
        return [], ['issues需要列表']
    allowed = {item['path'] for item in request['bindings']['artifacts'] + request['input_refs']}
    result, errors = [], []
    for position, value in enumerate(values, 1):
        if not isinstance(value, dict):
            errors.append('评审问题需要对象')
            continue
        proposed_refs = value.get('evidence_refs')
        if proposed_refs is None and value.get('path') is not None:
            proposed_refs = [{'path': value['path'], 'locator': value.get('locator')}]
        refs, error = _evidence_refs(proposed_refs, allowed)
        reason = value.get('reason', '')
        change = value.get('requested_change', '')
        if error or not isinstance(reason, str) or not reason.strip() or not isinstance(change, str) or not change.strip():
            errors.append('评审问题缺少定位、原因或具体修改')
            continue
        result.append({'id': str(value.get('id') or 'issue-' + str(position)),
                       'dimension_id': str(value.get('dimension_id', '')),
                       'severity': value.get('severity') if value.get('severity') in
                       ('info', 'low', 'medium', 'high', 'critical', 'blocker', 'major') else 'medium',
                       'scope': value.get('scope') if value.get('scope') in
                       ('wording', 'layout', 'evidence', 'scientific_choice') else 'unspecified',
                       'reason': reason.strip(), 'requested_change': change.strip(), 'evidence_refs': refs,
                       'path': refs[0]['path'], 'locator': refs[0]['locator'], 'reported_by': 'model'})
    return result, errors


def _normalize_dimensions(raw, rules, request):
    errors = []
    values = raw.get('dimensions', [])
    if not isinstance(values, list):
        values = []
        errors.append('dimensions需要列表')
    indexed = {}
    duplicates = set()
    permitted = {item['id'] for item in rules['dimensions']}
    for value in values:
        if not isinstance(value, dict) or value.get('id') not in permitted:
            errors.append('模型返回了未知或无效评价维度')
            continue
        identifier = value['id']
        if identifier in indexed:
            duplicates.add(identifier)
        indexed[identifier] = value
    allowed = {item['path'] for item in request['bindings']['artifacts'] + request['input_refs']}
    normalized = []
    for specification in rules['dimensions']:
        identifier = specification['id']
        value = indexed.get(identifier, {})
        score = value.get('score')
        reason = value.get('reason')
        reason = reason.strip() if isinstance(reason, str) else ''
        refs, evidence_error = _evidence_refs(value.get('evidence_refs'), allowed)
        invalid = ''
        if identifier in duplicates:
            invalid = '评价维度重复'
        elif score is None:
            invalid = '未评分'
        elif isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 4:
            invalid = '分数必须是0–4有限数值，不能是布尔值或字符串'
        elif not reason:
            invalid = '缺少评分理由'
        elif evidence_error:
            invalid = evidence_error
        normalized.append({'id': identifier, 'label': specification['label'], 'core': specification['core'],
                           'weight': specification['weight'], 'score': None if invalid else float(score),
                           'status': 'not_scored' if invalid else 'scored', 'reason': reason,
                           'evidence_refs': refs, 'validation_error': invalid})
    return normalized, errors


def _normalize_checks(raw_checks, rules):
    if raw_checks is None:
        raw_checks = []
    if not isinstance(raw_checks, list):
        raise ValueError('硬检查需要服务端提供的列表')
    required = {item['id']: item for item in rules['required_hard_checks']}
    indexed = {}
    for check in raw_checks:
        if not isinstance(check, dict) or not isinstance(check.get('id'), str) or not check['id']:
            raise ValueError('硬检查缺少稳定ID')
        if check['id'] in indexed:
            raise ValueError('硬检查ID重复：' + check['id'])
        indexed[check['id']] = check
    result = []
    for identifier in list(required) + [key for key in indexed if key not in required]:
        value = indexed.get(identifier, {})
        spec = required.get(identifier, {})
        reported = value.get('status', 'unknown')
        status = {'N/A': 'not_applicable', 'n/a': 'not_applicable', 'N_A': 'not_applicable'}.get(reported, reported)
        if status not in ('passed', 'failed', 'unknown', 'not_applicable'):
            status = 'unknown'
        source = value.get('source', 'not_run')
        evidence = value.get('evidence', value.get('evidence_refs'))
        performer = value.get('performed_by') or value.get('tool')
        verified = source in ('server', 'tool') and isinstance(performer, str) and bool(performer.strip()) and _has_evidence(evidence)
        if status == 'not_applicable' and not value.get('reason'):
            verified = False
        if status != 'unknown' and not verified:
            status = 'unknown'
        result.append({'id': identifier, 'status': status,
                       'required': spec.get('required', bool(value.get('required', False))),
                       'critical': spec.get('critical', bool(value.get('critical', True))),
                       'source': source, 'performed_by': performer or '',
                       'verified': verified and status != 'unknown',
                       'reported_status': reported,
                       'evidence': deepcopy(evidence), 'reason': str(value.get('reason', ''))})
    return result


def _assess(dimensions, checks, round_number, issues=None):
    scored = [d for d in dimensions if d['score'] is not None]
    core = [d for d in dimensions if d['core']]
    missing = [d['id'] for d in dimensions if d['score'] is None]
    missing_core = [d['id'] for d in core if d['score'] is None]
    low_core = [d['id'] for d in core if d['score'] is not None and d['score'] < 3]
    blockers = [c['id'] for c in checks if (c['critical'] and c['status'] == 'failed') or
                (c['required'] and c['status'] == 'unknown')]
    quality_passed = not missing_core and not low_core
    reported_blocking_issues = [item['id'] for item in issues or []
                               if item['severity'] in ('high', 'critical', 'blocker', 'major')]
    consistent = not (quality_passed and reported_blocking_issues)
    passed = quality_passed and not blockers and consistent
    if blockers:
        decision = 'blocked'
    elif missing_core:
        decision = 'needs_evidence'
    elif low_core or not consistent:
        decision = 'needs_revision'
    else:
        decision = 'passed'
    revision_allowed = not passed and round_number < MAX_REVISIONS
    stop = 'passed' if passed else 'revision_limit' if not revision_allowed else ''
    if not passed and not revision_allowed:
        decision = 'needs_author'
    mean = round(sum(d['score'] * d['weight'] for d in scored) / sum(d['weight'] for d in scored), 4) if scored else None
    return {'overall': mean, 'overall_max': 4, 'score_percent': round(mean * 25, 2) if mean is not None else None,
            'coverage': {'scored': len(scored), 'total': len(dimensions),
                         'ratio': round(len(scored) / len(dimensions), 4),
                         'core_scored': len(core) - len(missing_core), 'core_total': len(core)},
            'missing_dimensions': missing, 'missing_core_dimensions': missing_core, 'low_core_dimensions': low_core,
            'hard_blockers': blockers, 'quality_passed': quality_passed, 'passed': passed,
            'review_consistency_passed': consistent, 'reported_blocking_issues': reported_blocking_issues,
            'decision': decision, 'can_proceed': passed, 'automatic_flow': passed,
            'revision_allowed': revision_allowed, 'stop_reason': stop}


def evaluate_review(request: dict, model_result: dict | str | None, *, hard_checks: list[dict] | None = None,
                    evaluator: dict | None = None, actor: dict | None = None, parent: dict | None = None) -> dict:
    """Normalize a model judgment and calculate policy decisions without file I/O.

    Evidence validation here establishes declared path and locator structure, not
    semantic truth. Only trusted ``hard_checks`` can attest actual tool behavior.
    An override requires the original saved review as ``parent`` and a server
    constructed ``actor={'role':'author','id':...}``; it never changes ``passed``.
    """
    request, rules = _request(request)
    override = request.get('override')
    parent_id = request.get('parent_review_id')
    if override is not None:
        if not isinstance(override, dict) or not parent or override.get('review_id') != parent.get('review_id'):
            raise ValueError('作者继续决定需要绑定真实评审')
        if not actor or actor.get('role') != 'author' or not isinstance(actor.get('id'), str) or not actor['id'].strip():
            raise ValueError('只有已认证作者可以明确继续')
        if override.get('confirmed') is not True or not isinstance(override.get('reason'), str) or not override['reason'].strip():
            raise ValueError('作者继续决定需要明确确认及原因')
        if request['bindings'] != parent.get('bindings') or request['stage'] != parent.get('stage') or request['purpose'] != parent.get('purpose'):
            raise Conflict('旧评审不能为新版本提供作者继续决定')
        result = deepcopy(parent)
        for key in ('review_id', 'created', 'operation_id'):
            result.pop(key, None)
        result.update(kind='override', operation_id=request['operation_id'], parent_review_id=parent['review_id'],
                      base_decision=parent.get('base_decision', parent['decision']), decision='author_override',
                      can_proceed=True, automatic_flow=False, revision_allowed=False, stop_reason='author_override',
                      author_override={'author_id': actor['id'], 'confirmed': True, 'reason': override['reason'].strip(),
                                       'review_id': parent['review_id']})
        return result
    if parent_id:
        if not parent or parent.get('review_id') != parent_id:
            raise ValueError('定向修订需要真实上一轮评审')
        if parent['stage'] != request['stage'] or parent['purpose'] != request['purpose']:
            raise Conflict('定向修订不能更换阶段或用途')
        for key in ('stage_version', 'source_version', 'rule_version'):
            if parent['bindings'][key] != request['bindings'][key]:
                raise Conflict('输入或规则已改变，请建立新的评审链')
        if parent.get('kind') == 'override' or not parent.get('revision_allowed'):
            raise Conflict('上一轮评审不允许继续自动修订')
        if parent['bindings']['artifacts'] == request['bindings']['artifacts']:
            raise Conflict('定向修订需要保存新的产物版本')
        round_number = parent['round'] + 1
        if round_number > MAX_REVISIONS:
            raise Conflict('最多允许两轮定向修订')
    else:
        if parent:
            raise ValueError('缺少parent_review_id')
        round_number = 0
    raw, errors = _model_object(model_result)
    dimensions, dimension_errors = _normalize_dimensions(raw, rules, request)
    issues, issue_errors = _issues(raw, request)
    checks = _normalize_checks(hard_checks, rules)
    result = {'schema_version': VERSION, 'kind': 'evaluation', 'operation_id': request['operation_id'],
              'stage': request['stage'], 'purpose': request['purpose'], 'bindings': request['bindings'],
              'input_refs': request['input_refs'], 'rubric': rules,
              'evaluator': deepcopy(evaluator or {'kind': 'model', 'status': 'not_identified'}),
              'round': round_number, 'parent_review_id': parent_id or '',
              'root_review_id': parent.get('root_review_id') or parent.get('review_id') if parent else '',
              'dimensions': dimensions, 'hard_checks': checks,
              'evaluation_errors': errors + dimension_errors + issue_errors,
              'evidence_validation': 'declared_project_paths_and_locator_structure_only',
              'issues': issues, 'issues_are_model_reported': True,
              'limitations': [item for item in raw.get('limitations', []) if isinstance(item, str)]
              if isinstance(raw.get('limitations', []), list) else []}
    result.update(_assess(dimensions, checks, round_number, issues))
    return result


def _payload_value(value):
    """Keep invalid model numbers representable for exact idempotency comparison."""
    if isinstance(value, float) and not math.isfinite(value):
        return {'invalid_number': str(value)}
    if isinstance(value, dict):
        return {str(key): _payload_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_payload_value(item) for item in value]
    return value


def _index_path(store, owner, pid):
    store.get(owner, pid)
    return store.path(owner, pid) / '.workbench/stage-reviews/index.json'


def _read_index(path):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else {'schema_version': VERSION, 'operations': {}, 'reviews': []}


def _load_review(directory, identifier):
    if not isinstance(identifier, str) or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
        raise ValueError('评审标识无效')
    path = directory / (identifier + '.json')
    if not path.is_file():
        raise KeyError('评审不存在')
    return json.loads(path.read_text(encoding='utf8'))


def _location_exists(root, ref):
    """Check concrete positions when their artifact format makes them decidable."""
    target = child(root, ref['path'])
    if not target.is_file():
        return False
    locator = ref['locator']
    if not isinstance(locator, dict):
        return True
    if 'json_pointer' in locator:
        if target.suffix.lower() != '.json':
            return False
        try:
            # Duplicate keys are ambiguous and non-finite literals are not JSON.
            document = json.loads(target.read_text(encoding='utf8'), object_pairs_hook=_unique_json_object,
                                  parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if not _json_pointer_exists(document, locator['json_pointer']):
                return False
        except (ValueError, UnicodeError):
            return False
    if target.suffix.lower() in ('.json', '.md', '.txt', '.py', '.tex', '.csv', '.r', '.m', '.jl'):
        text = target.read_text(encoding='utf8', errors='replace')
        if 'line' in locator and locator['line'] > max(1, len(text.splitlines())):
            return False
        quote = ref.get('quote') or locator.get('quote')
        if isinstance(quote, str) and quote and quote not in text:
            return False
        if target.suffix.lower() == '.json':
            try:
                document = json.loads(text)
            except ValueError:
                return False
            if isinstance(document, dict) and 'section_id' in locator and isinstance(document.get('sections'), list):
                return any(item.get('id') == locator['section_id'] for item in document['sections'] if isinstance(item, dict))
            if isinstance(document, dict) and 'block_index' in locator and isinstance(document.get('content'), dict):
                return locator['block_index'] < len(document['content'].get('content', []))
    return True


def save_review(store, owner, pid, request, model_result, *, hard_checks=None, evaluator=None, actor=None) -> dict:
    """Append a review and atomically update its index under the project lock.

    Reusing operation_id with a different request/result/check/author payload is
    a conflict. The append is recoverable if interrupted before index replacement.
    """
    normalized, _ = _request(request)
    payload = _payload_value({'request': normalized, 'model_result': model_result,
                              'hard_checks': hard_checks, 'evaluator': evaluator, 'actor': actor})
    payload_text = _canonical(payload)
    with store.lock(pid):
        path = _index_path(store, owner, pid)
        index = _read_index(path)
        operation = normalized['operation_id']
        # Stable per-operation filenames recover append-before-index interruptions.
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, str(owner) + '/' + pid + '/' + operation).hex
        if operation in index['operations'] or (path.parent / (identifier + '.json')).exists():
            existing = _load_review(path.parent, index['operations'].get(operation, identifier))
            if _canonical(existing.get('operation_payload')) != payload_text:
                raise Conflict('operation_id已用于不同评审载荷')
            if operation not in index['operations']:
                index['operations'][operation] = existing['review_id']
                index['reviews'].append(existing['review_id'])
                atomic_json(path, index)
            return existing
        parent_id = normalized.get('parent_review_id') or (normalized.get('override') or {}).get('review_id')
        parent = _load_review(path.parent, parent_id) if parent_id else None
        if normalized.get('override'):
            if not actor or actor.get('id') != owner:
                raise ValueError('作者继续决定必须由当前所有者提交')
            if normalized.get('parent_review_id') not in (None, '', normalized['override']['review_id']):
                raise ValueError('作者继续决定与上一轮评审不一致')
        result = evaluate_review(normalized, model_result, hard_checks=hard_checks,
                                 evaluator=evaluator, actor=actor, parent=parent)
        result.update(review_id=identifier, project_id=pid, created=now(), operation_payload=payload)
        result['root_review_id'] = result.get('root_review_id') or identifier
        # Declared model references cannot point to absent files even when the
        # caller has supplied a high score. Semantic correspondence remains reviewable.
        root = store.path(owner, pid)
        for dimension in result['dimensions']:
            if dimension['score'] is not None and any(not _location_exists(root, ref) for ref in dimension['evidence_refs']):
                if result['kind'] == 'override':
                    raise Conflict('原评审依据已失效，请先评审当前版本')
                dimension.update(score=None, status='not_scored', validation_error='依据文件或可核验定位不存在')
        if result['kind'] == 'evaluation':
            result.update(_assess(result['dimensions'], result['hard_checks'], result['round'], result['issues']))
        path.parent.mkdir(parents=True, exist_ok=True)
        # No public operation updates an existing review. Atomic replacement of a
        # previously absent path avoids a partial JSON record after interruption.
        _canonical(result)
        atomic_json(path.parent / (identifier + '.json'), result)
        index['operations'][operation] = identifier
        index['reviews'].append(identifier)
        atomic_json(path, index)
        return result


def list_reviews(store, owner, pid, *, stage='', purpose='', current_bindings=None) -> dict:
    """Read history; mismatched/unknown bindings never authorize progression."""
    current = _bindings(current_bindings) if current_bindings is not None else None
    with store.lock(pid):
        path = _index_path(store, owner, pid)
        index = _read_index(path)
        items = []
        for identifier in reversed(index['reviews']):
            item = _load_review(path.parent, identifier)
            if stage and item['stage'] != stage or purpose and item['purpose'] != purpose:
                continue
            item.pop('operation_payload', None)
            rules_changed = item['bindings']['rule_version'] != rubric(item['stage'], item['purpose'])['version']
            matches = current is not None and item['bindings'] == current and not rules_changed
            item['stale'] = rules_changed or current is not None and not matches
            item['current_binding_verified'] = matches
            if not matches:
                item['can_proceed'] = False
                item['automatic_flow'] = False
            items.append(item)
        current_review = next((item for item in items if item['current_binding_verified']), None)
        return {'items': items, 'latest': items[0] if items else None, 'current': current_review,
                'can_proceed': bool(current_review and current_review['can_proceed']),
                'automatic_flow': bool(current_review and current_review['automatic_flow']),
                'decision': current_review['decision'] if current_review else
                'stale' if items and current is not None else 'binding_unverified' if items else 'not_reviewed'}
