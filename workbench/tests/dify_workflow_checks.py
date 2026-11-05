"""Execute the exact Python bodies embedded into the production Dify graph."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "integrations/dify-bridge/configure_workflow.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf8"))


def body(name):
    node = next(n for n in ast.walk(TREE) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    scope = {}
    exec(ast.literal_eval(node.value), scope)
    return scope["main"]


class WorkflowChecks(unittest.TestCase):
    def setUp(self):
        self.project = "a" * 32
        self.account = [{"data": {"id": "synthetic-owner", "username": "synthetic"}}]
        self.rules = [{"reference": "https://workbench.example/research/api/projects/" + self.project + "/agent-context",
                       "data": {"project": {"id": self.project}, "standard_version": "current",
                                "instructions": "actual contract", "skills": [{"content": "actual skill"}]}}]
        self.record = {"created": "2026-11-01T00:00:00Z", "artifacts": [{"path": "project/docs/result.txt"}],
                       "validation": [{"check": "workbench_readback", "result": "passed"}]}
        self.receipt = {"status": "saved", "run_id": "run", "project_id": self.project,
                        "standard_version": "current", "artifact": {"path": "project/docs/result.txt", "modified": 42},
                        "receipt": {"recorded": True, **self.record}}
        self.history = [{"reference": "https://workbench.example/research/api/projects/" + self.project + "/review-history",
                         "data": {"events": [{"id": 17, "kind": "agent.receipt", "project": self.project,
                                               "owner": "synthetic-owner", "payload": self.record}]}}]

    def test_current_mcp_originals_and_native_history_match(self):
        result = body("check_context_source")(self.account, self.rules, self.project, "current")
        self.assertEqual(result, {"account_id": "synthetic-owner", "verified": True})
        checked = body("receipt_source")(json.dumps(self.receipt), 200, self.project, "run", "current")
        final = body("check_history_source")(self.history, checked["receipt"], self.project, result["account_id"])
        self.assertEqual(final["history_event_id"], "17")
        self.assertTrue(json.loads(final["receipt"])["processing_history_verified"])

    def test_dify_success_with_mcp_error_cannot_pass(self):
        for malformed in ([], [{"data": []}], [{"error": "missing required argument", "data": {}}], [{"isError": True, "data": {}}]):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                body("check_context_source")(self.account, malformed, self.project, "current")
            with self.subTest(history=malformed), self.assertRaises(ValueError):
                body("check_history_source")(malformed, json.dumps(self.receipt), self.project, "synthetic-owner")

    def test_other_project_stale_rules_or_missing_originals_cannot_pass(self):
        for key, value in (("project", {"id": "b" * 32}), ("standard_version", "stale"),
                           ("instructions", ""), ("skills", [{"id": "summary-without-original"}])):
            changed = deepcopy(self.rules)
            changed[0]["data"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                body("check_context_source")(self.account, changed, self.project, "current")

    def test_saved_flag_without_current_receipt_is_rejected(self):
        for key, value in (("run_id", "other-run"), ("project_id", "b" * 32), ("standard_version", "stale"),
                           ("receipt", {"recorded": False}), ("artifact", {"path": "missing-metadata"})):
            changed = deepcopy(self.receipt)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                body("receipt_source")(json.dumps(changed), 200, self.project, "run", "current")

    def test_old_or_other_owner_history_cannot_pass(self):
        for key, value in (("owner", "other-owner"), ("project", "other-project"),
                           ("payload", {**self.record, "created": "old"}),
                           ("payload", {**self.record, "artifacts": [{"path": "other.txt"}]})):
            changed = deepcopy(self.history)
            changed[0]["data"]["events"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                body("check_history_source")(changed, json.dumps(self.receipt), self.project, "synthetic-owner")


if __name__ == "__main__":
    unittest.main()
