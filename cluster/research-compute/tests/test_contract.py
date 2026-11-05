import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cluster_dispatch as core


class ComputeContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = patch.object(core, 'ROOT', Path(self.tmp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.payload = {'request_id': 'test-request-0001', 'identity': {'owner_id': 'alice'}, 'spec': {
            'question': 'Does a known manufactured field satisfy the requested accuracy?',
            'runtime': 'python', 'files': [{'path': 'main.py', 'content': 'print(1)\n'}], 'entrypoint': 'main.py',
            'criteria': [{'name': 'accuracy', 'metric': 'error', 'op': 'le', 'threshold': .01}],
            'reference': {'type': 'analytic', 'equation': 'u=sin(pi*x)'}}}

    def prepared(self):
        result = core.prepare(self.payload)
        return {**self.payload, 'experiment_id': result['experiment_id']}

    def test_inputs_and_criteria_are_immutable(self):
        self.prepared()
        self.payload['spec']['criteria'][0]['threshold'] = 1
        with self.assertRaises(ValueError):
            core.prepare(self.payload)

    def test_owner_cannot_read_another_experiment(self):
        payload = self.prepared()
        payload['identity'] = {'owner_id': 'bob'}
        with self.assertRaises(ValueError):
            core.experiment(payload)

    def test_submission_deduplicated(self):
        payload = self.prepared()
        with patch.object(core, 'command', return_value='1234') as submit:
            first = core.submit(payload)
            second = core.submit(payload)
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertTrue(second['deduplicated'])
        submit.assert_called_once()

    def test_completed_process_can_fail_scientific_metric(self):
        payload = self.prepared()
        folder, _ = core.experiment(payload)
        core.write_json(folder / 'outputs/metrics.json', {'metrics': {'error': .2}})
        run = {'state': 'COMPLETED', 'exit_code': '0:0', 'finished': True, 'job_id': '1234', 'execution': {'exit_code': 0}}
        with patch.object(core, 'status', return_value=run):
            result = core.assess(payload)
        self.assertTrue(result['executed'])
        self.assertEqual(result['status'], 'FAILED')

    def test_missing_metrics_fail(self):
        payload = self.prepared()
        run = {'state': 'COMPLETED', 'exit_code': '0:0', 'finished': True, 'job_id': '1234', 'execution': {'exit_code': 0}}
        with patch.object(core, 'status', return_value=run):
            result = core.assess(payload)
        self.assertEqual(result['status'], 'FAILED')
        self.assertTrue(result['checks'][0]['missing_or_nonfinite'])

    def test_queue_is_inconclusive(self):
        payload = self.prepared()
        with patch.object(core, 'status', return_value={'state': 'PENDING', 'finished': False}):
            self.assertEqual(core.assess(payload)['status'], 'INCONCLUSIVE')

    def test_resource_limit_and_traversal(self):
        self.payload['spec']['resources'] = {'cpus': 128}
        with self.assertRaises(ValueError):
            core.prepare(self.payload)
        with self.assertRaises(ValueError):
            core.relative('../original-data.csv')


if __name__ == '__main__':
    unittest.main()
