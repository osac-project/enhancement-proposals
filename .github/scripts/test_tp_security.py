"""Security regression tests for the privileged Test Plan Review workflow."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tp_model
import tp_review
from tp_hooks import TestPlanHooks


REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPlanWorkflowSecurityTests(unittest.TestCase):
    def test_review_uses_default_branch_and_never_checks_out_pr_code(self):
        workflow = (REPO_ROOT / ".github/workflows/test-plan-review.yml").read_text()

        self.assertIn("ref: ${{ github.event.repository.default_branch }}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("gh pr checkout", workflow)
        self.assertNotIn("base_ref:", workflow)
        self.assertIn("head_repo: ${{ steps.resolve.outputs.head_repo }}", workflow)
        self.assertIn("Upload TestPlan response for fork PR", workflow)
        self.assertIn("Link fork response on the PR", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("Authenticate to GCP with Workload Identity Federation", workflow)
        self.assertIn("vars.GCP_WORKLOAD_IDENTITY_PROVIDER", workflow)

    def test_review_does_not_run_an_agent_container_or_pr_supplied_code(self):
        source = (REPO_ROOT / ".github/scripts/tp_review.py").read_text()

        self.assertNotIn("agentic_ci", source)
        self.assertNotIn("run_skill", source)
        self.assertIn("from tp_model import complete", source)
        self.assertIn("fetch_pr_file(", source)

    def test_testplan_path_must_be_a_single_enhancement_file(self):
        slug, path = tp_review.find_testplan_path([
            {"filename": "enhancements/OSAC-12/sample/TestPlan.md"},
            {"filename": "enhancements/OSAC-12/TestPlan.md"},
        ])
        self.assertEqual(slug, "OSAC-12")
        self.assertEqual(path, "enhancements/OSAC-12/TestPlan.md")

        slug, path = tp_review.find_testplan_path([
            {"filename": "enhancements/../TestPlan.md"},
            {"filename": "enhancements/a\\b/TestPlan.md"},
        ])
        self.assertIsNone(slug)
        self.assertIsNone(path)

    def test_pr_documents_are_read_from_the_exact_pr_head(self):
        pr = {
            "head": {
                "repo": {"full_name": "contributor/enhancement-proposals"},
                "ref": "test-plan/osac-12",
            }
        }
        responses = [
            {"encoding": "base64", "content": base64.b64encode(b"plan").decode(), "sha": "plan-blob"},
            {"encoding": "base64", "content": base64.b64encode(b"design").decode(), "sha": "design-blob"},
            {"encoding": "base64", "content": base64.b64encode(b"prd").decode(), "sha": "prd-blob"},
        ]
        calls = []

        def fake_gh(args, check=True):
            calls.append(args)
            return json.dumps(responses.pop(0))

        with patch.object(tp_review, "gh", side_effect=fake_gh):
            result = tp_review.fetch_pr_documents(
                pr, "OSAC-12", "enhancements/OSAC-12/TestPlan.md", "head-sha"
            )

        self.assertEqual(result["testplan_content"], "plan")
        self.assertEqual(result["design_content"], "design")
        self.assertEqual(result["prd_content"], "prd")
        self.assertEqual(result["head_repo"], "contributor/enhancement-proposals")
        self.assertEqual(result["head_branch"], "test-plan/osac-12")
        self.assertTrue(all(call[1:3] == ["-X", "GET"] for call in calls))
        self.assertTrue(all("?ref=head-sha" in call[3] for call in calls))
        self.assertTrue(all("repos/contributor/enhancement-proposals/contents/" in call[3]
                            for call in calls))

    def test_missing_required_testplan_raises_clear_error(self):
        pr = {
            "head": {
                "repo": {"full_name": "contributor/enhancement-proposals"},
                "ref": "test-plan/osac-12",
            }
        }
        with patch.object(tp_review, "fetch_pr_file", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Could not fetch required PR file"):
                tp_review.fetch_pr_documents(
                    pr, "OSAC-12", "enhancements/OSAC-12/TestPlan.md", "head-sha"
                )


class VertexCallSecurityTests(unittest.TestCase):
    def test_vertex_error_does_not_expose_response_body(self):
        credentials = Mock(token="test-access-token")
        response = Mock(
            ok=False,
            status_code=400,
            text="sensitive prompt content echoed by upstream",
        )
        session = Mock()
        session.post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "HTTP 400") as error:
            tp_model.complete(
                "sensitive prompt content",
                "trusted review instructions",
                4096,
                model="claude-test",
                project_id="project",
                region="global",
                credentials=credentials,
                session=session,
            )

        self.assertNotIn("sensitive prompt content", str(error.exception))

    def test_vertex_request_has_no_tools_and_uses_credentials_only_as_header(self):
        credentials = Mock(token="test-access-token")
        response = Mock(
            ok=True,
            json=lambda: {
                "content": [{"type": "text", "text": "review result"}],
                "usage": {"input_tokens": 10, "output_tokens": 4},
            },
        )
        session = Mock()
        session.post.return_value = response

        result, usage = tp_model.complete(
            "untrusted PR text", "trusted review instructions", 4096,
            model="claude-test", project_id="project", region="global",
            credentials=credentials, session=session,
        )

        args, kwargs = session.post.call_args
        self.assertEqual(
            args[0],
            "https://aiplatform.googleapis.com/v1/projects/project/locations/"
            "global/publishers/anthropic/models/claude-test:rawPredict",
        )
        self.assertEqual(kwargs["headers"]["Authorization"],
                         "Bearer test-access-token")
        self.assertNotIn("tools", kwargs["json"])
        self.assertNotIn("test-access-token", json.dumps(kwargs["json"]))
        self.assertEqual(result, "review result")
        self.assertEqual(usage["input_tokens"], 10)

    def test_review_consumes_model_response_as_data_without_a_container(self):
        hooks = TestPlanHooks(
            repo="osac-project/enhancement-proposals",
            skills_path="/missing-skills",
            shadow=True,
            pr_data={
                "testplan_content": "A test plan supplied by the PR",
                "design_content": "Design supplied by the PR",
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "review"
            with patch.object(hooks, "_gh", return_value=""), patch.object(
                tp_review,
                "complete",
                return_value=("# Revised plan\n" + "detail " * 100,
                              {"input_tokens": 100, "output_tokens": 50}),
            ) as model, patch.object(
                tp_review,
                "get_pull_request",
                return_value={"head": {"sha": "head-sha"}},
            ):
                tp_review.run_review(
                    hooks,
                    "test-plan-review",
                    "TP-42",
                    {
                        "number": 42,
                        "title": "PR title",
                        "_ep_slug": "osac-12",
                        "headRefOid": "head-sha",
                    },
                    work_dir,
                    model="claude-test",
                )

            self.assertIn("A test plan supplied by the PR",
                          model.call_args.args[0])
            self.assertIn("Design supplied by the PR",
                          model.call_args.args[0])
            self.assertTrue((work_dir / "testplan-output.md").exists())
            self.assertFalse((work_dir / ".git").exists())

    def test_score_mode_still_validates_and_posts_a_structured_verdict(self):
        hooks = TestPlanHooks(
            repo="osac-project/enhancement-proposals",
            skills_path="/missing-skills",
            shadow=True,
            pr_data={"testplan_content": "PR test plan"},
        )
        model_output = json.dumps({
            "verdict": "Ready",
            "scores": {
                "specificity": 2,
                "grounding": 2,
                "scope_fidelity": 2,
                "actionability": 2,
                "consistency": 2,
            },
            "total": 10,
            "criterionNotes": {},
            "summary": "Ready to implement",
            "feedback": "No changes requested.",
            "findings": {"critical": [], "important": [], "suggestions": []},
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "review"
            with patch.object(hooks, "_gh", return_value=""), patch.object(
                tp_review,
                "complete",
                return_value=(model_output,
                              {"input_tokens": 100, "output_tokens": 50}),
            ), patch.object(
                tp_review,
                "get_pull_request",
                return_value={"head": {"sha": "head-sha"}},
            ):
                tp_review.run_review(
                    hooks,
                    "test-plan-score",
                    "TP-42",
                    {
                        "number": 42,
                        "title": "PR title",
                        "_ep_slug": "osac-12",
                        "headRefOid": "head-sha",
                    },
                    work_dir,
                    model="claude-test",
                )

            verdict = json.loads((work_dir / "verdict.json").read_text())
            self.assertEqual(verdict["verdict"], "Ready")
            self.assertEqual(verdict["total"], 10)


if __name__ == "__main__":
    unittest.main()
