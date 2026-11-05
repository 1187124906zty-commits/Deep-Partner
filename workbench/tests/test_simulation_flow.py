"""Simulation routing and declared physics-result checks are executable contracts."""
import importlib.util,unittest
from pathlib import Path
from server.research_simulation_flow import prepare
from server.research_flow import RunInput,KINDS

class SimulationFlowTests(unittest.TestCase):
    def test_prepared_simulation_is_required(self):
        with self.assertRaises(ValueError):prepare({},[])
        with self.assertRaises(ValueError):prepare({'entrypoint':'src/solve.py'},[])
        value=prepare({'entrypoint':'src/solve.py'},['src/solve.py'])
        self.assertEqual(value['resources']['cpus'],2);self.assertEqual(value['runtime'],'paso')
    def test_resource_and_source_scope(self):
        with self.assertRaises(ValueError):prepare({'entrypoint':'../../solve.py'},['../../solve.py'])
        with self.assertRaises(ValueError):prepare({'entrypoint':'src/solve.py','resources':{'cpus':1000}},['src/solve.py'])
        with self.assertRaises(ValueError):prepare({'entrypoint':'src/solve.py','checks':[{'field':'error','op':'le'}]},['src/solve.py'])
    def test_mcp_steps_are_explicit(self):
        with self.assertRaises(ValueError):prepare({'engine':'openpaso_mcp'},[])
        value=prepare({'engine':'openpaso_mcp','tool_steps':[{'tool':'run_simulation','arguments':{'backend':'actual-backend'}}]},[])
        self.assertEqual(value['tool_steps'][0]['tool'],'run_simulation')
    def test_result_comparison_distinguishes_execution_and_acceptance(self):
        path=Path(__file__).with_name('simulation_worker.py');spec=importlib.util.spec_from_file_location('simulation_test_worker',path);worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
        contract={'checks':[{'field':'max_error','op':'le','value':.01,'basis':'theoretical benchmark'},{'field':'boundary_error','op':'close','value':0,'atol':1e-12}]}
        self.assertTrue(all(row['passed'] for row in worker.checks({'max_error':.0032,'boundary_error':0},contract)))
        self.assertFalse(all(row['passed'] for row in worker.checks({'max_error':.1,'boundary_error':0},contract)))
        self.assertFalse(worker.checks({'x':float('nan')},{'checks':[{'field':'x','op':'finite'}]})[0]['passed'])
    def test_route_keeps_cluster_submission_and_validation(self):
        value=RunInput(kind='simulate',input_paths=['src/solve.py'],simulation={'entrypoint':'src/solve.py'})
        self.assertEqual(value.kind,'simulate');self.assertIn('submit',KINDS['simulate']['steps']);self.assertIn('validate',KINDS['simulate']['steps'])

if __name__=='__main__':unittest.main()
