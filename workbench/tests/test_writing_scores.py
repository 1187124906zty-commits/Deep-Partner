import pytest
from server.writing_scores import normalize_score,RUBRIC


def assessment():
    return {'scores':[{'id':r['id'],'score':r['max']-2,'reason':'具体原句中的问题'} for r in RUBRIC],
            'issues':[{'id':'E1','classification':'necessary','location':'摘要','reason':'原句含未完成占位语'}]}


def test_total_is_computed_and_author_confirmation_stays_pending():
    value=normalize_score({**assessment(),'total_score':100})
    assert value['total_score']==90 and value['author_approval']=='pending'


def test_missing_dimension_invalid_score_and_uncategorized_issue_are_not_accepted():
    value=assessment();value['scores'].pop()
    with pytest.raises(ValueError):normalize_score(value)
    value=assessment();value['scores'][0]['score']=31
    with pytest.raises(ValueError):normalize_score(value)
    value=assessment();value['issues'][0]['classification']='auto-rewrite'
    with pytest.raises(ValueError):normalize_score(value)


def test_original_scores_are_not_replaced_by_projected_improvements():
    value=assessment()
    for row in value['scores']:row['baseline_score']=row['score']-1
    original=normalize_score(value,use_baseline=True)
    actual_review=normalize_score(value)
    assert original['total_score']==85
    assert actual_review['total_score']==90
    assert original['scores'][0]['projected_score']==28
    assert normalize_score(original,use_baseline=True)['scores'][0]['projected_score']==28
    assert value['scores'][0]['score']==28
    value['scores'][0]['baseline_score']=31
    with pytest.raises(ValueError):normalize_score(value,use_baseline=True)


def test_score_reasons_attached_to_original_locations_are_retained():
    value=assessment();row=value['scores'][0];row.pop('reason')
    row['locations']=[{'location':'P1S5','example':'原文实际句子','reason':'条件范围不清楚'},
                      {'location':'P5S4','reason':'待估量的指代需要说明'}]
    result=normalize_score(value)
    assert result['total_score']==90
    assert result['scores'][0]['reason']=='P1S5：条件范围不清楚；P5S4：待估量的指代需要说明'
    assert result['scores'][0]['locations']==row['locations']
    row['locations']=[{'location':'P1S5','example':'没有评分理由的原句'}]
    with pytest.raises(ValueError,match='评分需要给出依据'):normalize_score(value)


def test_review_issue_status_keeps_its_original_necessary_or_potential_classification():
    before=assessment();before['issues'].append({'id':'P1','classification':'potential','reason':'A possible expression improvement'})
    after=assessment();after['issues']=[{'id':'E1','status':'resolved'},{'id':'P1','status':'resolved'}]
    result=normalize_score(after,baseline_assessment=before)
    assert [row['classification'] for row in result['issues']]==['necessary','potential']
    assert all(row['status']=='resolved' for row in result['issues'])
    assert all('classification' not in row for row in after['issues'])
    after['issues'].append({'id':'unknown','status':'resolved'})
    with pytest.raises(ValueError,match='修改项需要区分'):normalize_score(after,baseline_assessment=before)
