from server.task_workflows import create, advance


def test_code_route_does_not_count_unrelated_literature_steps():
    tracking=create('research-flow',{'name':'code'},{'route_steps':['dispatch','archive']})
    assert [s['id'] for s in tracking['steps']]==['dispatch','archive']
    tracking=advance(tracking,{'status':'running'},'1',step='dispatch')
    tracking=advance(tracking,{'status':'running'},'2',step='archive')
    assert [s['state'] for s in tracking['steps']]==['done','running']


def test_external_poll_keeps_completed_stages_and_current_step():
    tracking = create('research-flow', {'name': 'study'})
    tracking = advance(tracking, {'status': 'running'}, '1', step='search')
    tracking = advance(tracking, {'status': 'running'}, '2', step='download')
    waiting = advance(tracking, {'status': 'queued'}, '3')
    assert waiting['current_step'] == 'download'
    assert waiting['steps'][0]['state'] == 'done'
    assert waiting['steps'][1]['state'] == 'waiting'


def test_waiting_for_service_does_not_display_active_execution():
    tracking = create('simulation', {'name': 'study'})
    tracking = advance(tracking, {'status': 'running'}, '1', step='prepare')
    tracking = advance(tracking, {'status': 'running'}, '2', step='monitor')
    waiting = advance(tracking, {'status': 'waiting_service'}, '3')
    assert waiting['current_step'] == 'monitor'
    assert waiting['steps'][0]['state'] == 'done'
    assert waiting['steps'][2]['state'] == 'waiting'
