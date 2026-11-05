"""A live PID is insufficient: the remote tool endpoint must actually answer."""
from pathlib import Path
import json, os, sys, tempfile, unittest
from unittest.mock import AsyncMock,Mock, patch
import asyncio,importlib.util,time
sys.path.insert(0, 'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
import search_runtime
import tool_runtime,cluster_pdf_runtime,download_runtime


class RecoveryContractTests(unittest.TestCase):
    def test_live_tunnel_pid_does_not_hide_broken_remote_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bridge.json').write_text(json.dumps({'port': 47903, 'python': sys.executable}))
            (root / 'tunnel-state.json').write_text(json.dumps({'pid': os.getpid(), 'port': 47903}))
            reply = Mock()
            reply.__enter__ = Mock(return_value=Mock(read=lambda: '{"source":"Google Scholar · MCP"}'.encode()))
            reply.__exit__ = Mock(return_value=False)
            opener = Mock(open=Mock(return_value=reply))
            failed = Mock(returncode=1, stdout='', stderr='connection refused')
            restored = Mock(returncode=0, stdout='1\n', stderr='')
            child = Mock(pid=900001, poll=Mock(return_value=None))
            with patch.object(search_runtime, 'ROOT', root), patch.object(search_runtime.urllib.request, 'build_opener', return_value=opener), patch.object(search_runtime.subprocess, 'run', side_effect=[failed, restored]) as probe, patch.object(search_runtime.subprocess, 'Popen', return_value=child), patch.object(search_runtime.time, 'sleep'):
                result = search_runtime.restore()
            self.assertGreaterEqual(probe.call_count, 1, 'Remote endpoint was never checked; stale PID falsely reported ready')
            self.assertTrue(result['ready'])
            self.assertFalse(result.get('tunnel_reused', True))

    def test_cluster_disconnect_is_recoverable_but_solver_error_is_not(self):
        with patch.object(cluster_pdf_runtime.subprocess,'run',return_value=Mock(returncode=255,stderr=b'connection reset')):
            with self.assertRaises(ConnectionError):cluster_pdf_runtime.ssh('sacct')
        with patch.object(cluster_pdf_runtime.subprocess,'run',return_value=Mock(returncode=1,stderr=b'bad input file')):
            with self.assertRaises(RuntimeError):cluster_pdf_runtime.ssh('solve')

    def test_detached_native_turn_is_read_without_another_mcp_execution(self):
        state={'id':'owned-operation','native_turn_id':'turn-preserved'}
        async def check():
            snapshot={'turn':{'status':'completed','threadId':'session-preserved'},'summary':'source and tests completed','approvals':[]}
            with patch.object(tool_runtime,'read_agent_turn',new_callable=AsyncMock,return_value=snapshot),patch.object(tool_runtime,'mcp_call',new_callable=AsyncMock) as invoke:
                result=await tool_runtime.durable_agent_call(state,{})
                invoke.assert_not_awaited();self.assertEqual(result['result']['session_id'],'session-preserved')
        # The preserved-turn branch does not need to read an instruction or workspace.
        state.update(payload={'instruction':'existing task'})
        asyncio.run(check())

    def test_download_transient_failure_preserves_the_original_job(self):
        path=Path('D:/Development/电脑答疑/deeptutor-desktop/assets/download_worker.py')
        spec=importlib.util.spec_from_file_location('download_recovery_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);worker=module.Worker({'output':directory,'_config_path':str(root/'worker.json'),'origin':'https://example.invalid','token':'test-token'})
            session=Mock();session.post=Mock();worker.session=session
            job={'id':'existing-download','identifier':'10.1234/source'}
            with patch.object(worker,'progress',side_effect=module.requests.ConnectionError('connection reset')):
                worker.run(job)
            self.assertIn(job['id'],json.loads(worker.pending_path.read_text()))
            self.assertEqual(worker.pending[job['id']]['job']['id'],job['id'])
            self.assertEqual(worker.pending[job['id']]['state'],'recovering')
            session.post.assert_not_called()

    def test_fresh_download_heartbeat_does_not_hide_authentication_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'worker.json'
            path.with_suffix('.status.json').write_text(json.dumps({'pid':123,'heartbeat':time.time(),
                'runtime_revision':'automatic-recovery-1','state':'error','error':'401 Unauthorized'}))
            selected={'configured':True,'runtime':{'device_config':str(path)}}
            with patch.object(download_runtime,'discover',return_value=selected),patch.object(download_runtime,'pid_alive',return_value=True),patch.object(download_runtime,'spawn') as spawn:
                result=download_runtime.restore()
            self.assertFalse(result['ready']);self.assertTrue(result['requires_input']);spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
