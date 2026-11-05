from server.writing_expression import selected_issue_ids,key_sentence_windows,expression_feedback_coverage


def test_explicit_author_expression_request_selects_style_without_reclassifying_it():
    request='关键位置太绕，保留原意，让句子更直接。'
    issues=[
        {'id':'N1','classification':'necessary'},
        {'id':'P1','classification':'potential','selected_for_this_round':True,
            'selection_basis':'author_request','author_request_quote':'让句子更直接'},
        {'id':'P2','classification':'potential','selected_for_this_round':True,
            'selection_basis':'author_request','author_request_quote':'新增实验结论'},
        {'id':'P3','classification':'potential','selected_for_this_round':True},
        {'id':'P4','classification':'potential','selected_for_this_round':False,
            'selection_basis':'author_request','author_request_quote':'让句子更直接'},
        {'id':'A1','classification':'author_decision','selected_for_this_round':True,
            'selection_basis':'author_request','author_request_quote':'让句子更直接'},
    ]
    assert selected_issue_ids({'issues':issues},request)=={'N1','P1'}
    assert selected_issue_ids({'issues':issues})=={'N1'}
    assert issues[1]['classification']=='potential'


def test_sentence_positions_preserve_context_and_do_not_label_all_openers_bad():
    sections=[{'title':'Introduction','paragraphs':[
        {'id':'p1','context':'裂纹扩展改变离子迁移通道。不同孔隙率下比较有效扩散系数。'},
        {'id':'p2','context':'A direct scientific statement. Another clear statement.'}]}]
    result=key_sentence_windows(sections)
    assert result[0]['opening']=='裂纹扩展改变离子迁移通道。'
    assert result[0]['ending']=='不同孔隙率下比较有效扩散系数。'
    assert result[1]['opening']=='A direct scientific statement.'
    assert all('score' not in row and 'requires_edit' not in row for row in result)


def test_named_feedback_cannot_be_counted_as_addressed_by_unrelated_paragraph_edit():
    def doc(value):return {'content':{'content':[{'type':'paragraph','content':[{'type':'text','text':value}]}]}}
    source=doc('点名原句。随后解释。')
    request='请修改点名原句。'
    targets=[{'quote':'点名原句。'},{'quote':'模型自行增加的要求。'}]
    result=expression_feedback_coverage(source,doc('点名原句。随后解释更清楚。'),targets,request)
    assert result[0]['status']=='unchanged'
    assert result[1]['status']=='not_in_current_author_request'
    result=expression_feedback_coverage(source,doc('直接表达原意。随后解释。'),targets,request)
    assert result[0]['status']=='revised'
    assert 'quality_passed' not in result[0]
