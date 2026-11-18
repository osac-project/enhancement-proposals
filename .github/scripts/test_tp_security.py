"""Security regression tests for the privileged Test Plan Review workflow."""

import base64
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

import tp_model
import tp_review
from tp_hooks import TestPlanHooks


REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPlanWorkflowSecurityTests(unittest.TestCase):
    def test_trace_upload_is_independent_and_best_effort(self):
        workflow = (REPO_ROOT / ".github/workflows/test-plan-review.yml").read_text()
        steps = yaml.safe_load(workflow)["jobs"]["review"]["steps"]
        uploads = [
            index for index, step in enumerate(steps)
            if step.get("name") == "Upload OTEL traces"
        ]
        self.assertEqual(len(uploads), 1)
        upload_index, = uploads
        upload = steps[upload_index]
        producers = [
            index for index, step in enumerate(steps)
            if step.get("name") == "Run test plan review"
        ]
        self.assertEqual(len(producers), 1)
        producer_index, = producers
        self.assertEqual(steps[producer_index]["run"], "python .github/scripts/tp_review.py")
        self.assertLess(producer_index, upload_index)
        self.assertEqual(upload["if"], "always()")
        self.assertIs(upload["continue-on-error"], True)
        self.assertEqual(
            upload["uses"],
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        )
        self.assertEqual(upload["with"], {
            "name": "tp-review-otel-pr${{ needs.resolve-pr.outputs.pr_number }}"
                    "-run${{ github.run_id }}-attempt${{ github.run_attempt }}",
            "path": "workdir-*/_run/claude-otel.jsonl",
            "retention-days": 90,
            "if-no-files-found": "ignore",
        })

    def test_trace_upload_comments_cannot_override_effective_configuration(self):
        workflow = (REPO_ROOT / ".github/workflows/test-plan-review.yml").read_text()
        for original, replacement in (
            ("if: always()", "if: failure() # if: always()"),
            ("continue-on-error: true", "continue-on-error: false # continue-on-error: true"),
            ("retention-days: 90", "retention-days: 1 # retention-days: 90"),
        ):
            with self.subTest(original=original), patch.object(
                Path, "read_text", return_value=workflow.replace(original, replacement),
            ):
                with self.assertRaises(AssertionError):
                    self.test_trace_upload_is_independent_and_best_effort()

    def test_trace_upload_must_follow_producer_in_review_job(self):
        workflow = yaml.safe_load(
            (REPO_ROOT / ".github/workflows/test-plan-review.yml").read_text()
        )
        for location in ("before_producer", "other_job"):
            mutated = copy.deepcopy(workflow)
            steps = mutated["jobs"]["review"]["steps"]
            upload = next(step for step in steps if step.get("name") == "Upload OTEL traces")
            steps.remove(upload)
            if location == "before_producer":
                producer_index = next(
                    index for index, step in enumerate(steps)
                    if step.get("name") == "Run test plan review"
                )
                steps.insert(producer_index, upload)
            else:
                mutated["jobs"]["unrelated"] = {
                    "runs-on": "ubuntu-latest", "steps": [upload],
                }
            with self.subTest(location=location), patch.object(
                Path, "read_text", return_value=yaml.safe_dump(mutated),
            ):
                with self.assertRaises(AssertionError):
                    self.test_trace_upload_is_independent_and_best_effort()

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
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.summary_file = Path(directory) / "step-summary.md"
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_STEP_SUMMARY": str(self.summary_file),
        }))

    def test_runner_summary_fixture_preserves_ambient_ci_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            ambient = Path(directory) / "ambient-summary.md"
            ambient.write_text("existing job summary\n")
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(ambient)}):
                fixture = VertexCallSecurityTests()
                try:
                    fixture.setUp()
                    fixture.test_review_consumes_model_response_as_data_without_a_container()
                    fixture.test_score_mode_still_validates_and_posts_a_structured_verdict()
                    self.assertEqual(ambient.read_text(), "existing job summary\n")
                    self.assertEqual(
                        fixture.summary_file.read_text(),
                        "\n### Test Plan Usage — TP-42\n**Tokens:** 100 in / 50 out\n" * 2,
                    )
                finally:
                    fixture.doCleanups()
                self.assertEqual(os.environ["GITHUB_STEP_SUMMARY"], str(ambient))
                self.assertFalse(fixture.summary_file.exists())

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
