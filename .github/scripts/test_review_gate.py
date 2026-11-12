import json
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

import refresh_review_gate as relay


WORKFLOW = Path(__file__).resolve().parents[1] / "workflows/review-gate.yml"


def review(state, reviewer="human", review_id=1, user_type="User"):
    return {
        "id": review_id,
        "state": state,
        "submitted_at": "2026-11-05T14:06:51Z",
        "user": {"login": reviewer, "type": user_type},
    }


def evaluate(pages, workflow=WORKFLOW, api_error=False):
    script = textwrap.dedent(workflow.read_text().split("        run: |\n", 1)[1])
    with tempfile.TemporaryDirectory() as directory:
        executable = Path(directory) / "gh"
        executable.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$CALLS"\n'
            'if [ "$API_ERROR" = 1 ]; then exit 1; fi\n'
            'cat "$REVIEWS"\n'
        )
        executable.chmod(0o700)
        reviews = Path(directory) / "reviews.json"
        reviews.write_text(json.dumps(pages))
        calls = Path(directory) / "calls"
        result = subprocess.run(
            ["bash", "-c", script],
            env={
                **os.environ,
                "PATH": directory + os.pathsep + os.environ["PATH"],
                "REVIEWS": str(reviews),
                "CALLS": str(calls),
                "API_ERROR": str(int(api_error)),
                "PR": "459",
                "REPO": "osac-project/enhancement-proposals",
            },
            text=True,
            capture_output=True,
        )
        return result, calls.read_text().splitlines()


class ReviewPolicyTests(unittest.TestCase):
    def test_changes_requested_fails_and_later_approval_passes(self):
        blocked, first_calls = evaluate([[review("CHANGES_REQUESTED")]])
        cleared, later_calls = evaluate([
            [review("CHANGES_REQUESTED")], [review("APPROVED", review_id=2)],
        ])
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("Human reviewer still has CHANGES_REQUESTED", blocked.stdout)
        self.assertEqual(cleared.returncode, 0, cleared.stderr)
        self.assertIn("No outstanding human changes requested", cleared.stdout)
        self.assertEqual(first_calls, later_calls)
        self.assertEqual(len(later_calls), 1)
        self.assertIn("--paginate --slurp", later_calls[0])

    def test_dismissal_clears_request(self):
        result, _ = evaluate([[review("CHANGES_REQUESTED"), review("DISMISSED", review_id=2)]])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_comment_and_pending_do_not_clear_request(self):
        for state in ("COMMENTED", "PENDING"):
            with self.subTest(state=state):
                result, _ = evaluate([[review("CHANGES_REQUESTED"), review(state, review_id=2)]])
                self.assertEqual(result.returncode, 1)

    def test_other_human_still_blocks(self):
        result, _ = evaluate([
            [review("CHANGES_REQUESTED"), review("APPROVED", review_id=2)],
            [review("CHANGES_REQUESTED", reviewer="other")],
        ])
        self.assertEqual(result.returncode, 1)

    def test_bots_and_null_users_do_not_block(self):
        missing_user = review("CHANGES_REQUESTED")
        missing_user["user"] = None
        result, _ = evaluate([[
            review("CHANGES_REQUESTED", user_type="Bot"),
            review("CHANGES_REQUESTED", reviewer="automation[bot]"),
            missing_user,
        ]])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_timestamp_then_id_ordering(self):
        later = review("CHANGES_REQUESTED", review_id=1)
        later["submitted_at"] = "2026-11-06T00:00:00Z"
        result, _ = evaluate([[later, review("APPROVED", review_id=999)]])
        self.assertEqual(result.returncode, 1)

    def test_malformed_decisive_timestamps_fail_closed(self):
        for state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            for timestamp in (
                None, "", "not-a-date", 123, False, [], {},
                "2026-11-06", "2026-02-30T00:00:00Z",
                "2026-11-06T24:00:00Z", "2026-11-06T00:00:00Ztrailing",
            ):
                with self.subTest(state=state, timestamp=timestamp):
                    malformed = {**review(state, review_id=2), "submitted_at": timestamp}
                    result, _ = evaluate([[review("APPROVED")], [malformed]])
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Invalid review response", result.stderr)
            with self.subTest(state=state, timestamp="missing"):
                malformed = review(state, review_id=2)
                del malformed["submitted_at"]
                result, _ = evaluate([[review("APPROVED")], [malformed]])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid review response", result.stderr)

    def test_pending_without_timestamp_is_supported(self):
        for timestamp in ("missing", None):
            with self.subTest(timestamp=timestamp):
                pending = {**review("PENDING", review_id=2), "submitted_at": timestamp}
                if timestamp == "missing":
                    del pending["submitted_at"]
                for state, expected in (("APPROVED", 0), ("CHANGES_REQUESTED", 1), ("DISMISSED", 0)):
                    with self.subTest(state=state):
                        result, _ = evaluate([[review(state)], [pending]])
                        self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(evaluate([[pending]])[0].returncode, 0)

    def test_empty_reviews_pass(self):
        self.assertEqual(evaluate([[]])[0].returncode, 0)

    def test_api_and_malformed_responses_fail_closed(self):
        self.assertNotEqual(evaluate([[]], api_error=True)[0].returncode, 0)
        for response in (
            None, {}, [None], [["not a review"]], [[{}]],
            [[{**review("APPROVED"), "id": "invalid"}]],
            [[{**review("APPROVED"), "state": "invalid"}]],
            [[{**review("APPROVED"), "user": {}}]],
        ):
            with self.subTest(response=response):
                self.assertNotEqual(evaluate(response)[0].returncode, 0)


REPO = "osac-project/enhancement-proposals"
HEAD = "7a6eaa76cdf7b5ac737e972df07218c6f451e44c"
FORK = "contributor/enhancement-proposals"
SOURCE_ID = 42041871450
TARGET_ID = 41867805257
WORKFLOW_ID = 350405333


def run_fixture(run_id, event):
    return {
        "id": run_id,
        "repository": {"full_name": REPO},
        "head_repository": {"full_name": REPO if event == "pull_request_review" else FORK},
        "head_sha": HEAD,
        "head_branch": "proposal",
        "event": event,
        "workflow_id": WORKFLOW_ID,
        "path": relay.WORKFLOW_PATH,
        "status": "completed",
        "conclusion": "failure",
        "pull_requests": [],
    }


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.event = {
            "action": "completed",
            "workflow_run": {"id": SOURCE_ID, "head_sha": HEAD, "head_branch": "proposal"},
        }
        self.source = run_fixture(SOURCE_ID, "pull_request_review")
        self.target = run_fixture(TARGET_ID, "pull_request")
        self.pull = {
            "number": 459,
            "state": "open",
            "base": {"ref": "main", "repo": {"full_name": REPO}},
            "head": {"sha": HEAD, "ref": "proposal", "repo": {"full_name": FORK}},
        }
        self.associated = [self.pull]
        self.runs = [self.target]
        self.current_pull = None
        self.statuses = []
        self.extra_targets = {}
        self.on_post = None
        self.posts = []
        self.mock_api = patch.object(relay, "api", side_effect=self.api).start()
        self.addCleanup(patch.stopall)
        self.sleep = patch.object(relay.time, "sleep").start()

    def api(self, endpoint, method="GET", paginate=False):
        if method == "POST":
            self.posts.append(endpoint)
            if self.on_post:
                self.on_post()
            return
        if endpoint.endswith("/actions/workflows/review-gate.yml"):
            return {"id": WORKFLOW_ID, "path": relay.WORKFLOW_PATH}
        if endpoint.endswith(f"/actions/runs/{SOURCE_ID}"):
            return deepcopy(self.source)
        if "/commits/" in endpoint:
            self.assertTrue(paginate)
            return [[], deepcopy(self.associated)]
        if endpoint.endswith("/pulls/459"):
            return deepcopy(self.current_pull or self.pull)
        if "/runs?" in endpoint:
            self.assertTrue(paginate)
            self.assertIn("event=pull_request&head_sha=" + HEAD, endpoint)
            return [{"workflow_runs": []}, {"workflow_runs": deepcopy(self.runs)}]
        if endpoint.endswith(f"/actions/runs/{TARGET_ID}"):
            result = deepcopy(self.target)
            if self.statuses:
                result["status"] = self.statuses.pop(0)
            return result
        for run_id, target in self.extra_targets.items():
            if endpoint.endswith(f"/actions/runs/{run_id}"):
                return deepcopy(target)
        self.fail(f"Unexpected API request: {endpoint}")

    def refresh(self):
        relay.refresh(self.event, REPO)

    def test_review_change_refreshes_original_suite(self):
        for state in ("APPROVED", "DISMISSED", "COMMENTED"):
            with self.subTest(state=state):
                blocked, original_calls = evaluate([[review("CHANGES_REQUESTED")]])
                suite = {113452576674: blocked.returncode}
                reviews = [[review("CHANGES_REQUESTED")], [review(state, review_id=2)]]
                evaluate(reviews)
                self.assertEqual(suite[113452576674], 1)
                self.assertTrue(all("/rerun" not in call for call in original_calls))
                self.on_post = lambda: suite.update({113452576674: evaluate(reviews)[0].returncode})
                self.refresh()
                self.assertEqual(suite[113452576674], 1 if state == "COMMENTED" else 0)
                self.assertEqual(self.posts[-1], f"repos/{REPO}/actions/runs/{TARGET_ID}/rerun")

    def test_source_conclusion_is_not_trusted(self):
        for conclusion in ("success", "failure", "cancelled", "timed_out"):
            self.source["conclusion"] = conclusion
            self.refresh()
        self.assertEqual(len(self.posts), 4)

    def test_refresh_uses_current_blockers_and_fails_closed(self):
        for reviews, api_error in (
            ([[review("CHANGES_REQUESTED")]], False),
            ([[review("APPROVED"), review("CHANGES_REQUESTED", reviewer="other")]], False),
            ([[]], True),
        ):
            with self.subTest(reviews=reviews, api_error=api_error):
                self.source["conclusion"] = "success"
                outcome = []
                self.on_post = lambda: outcome.append(evaluate(reviews, api_error=api_error)[0].returncode)
                self.refresh()
                self.assertNotEqual(outcome, [0])
                self.assertEqual(len(outcome), 1)

    def test_refreshes_matching_pr_event_runs_not_other_revisions(self):
        second = run_fixture(TARGET_ID + 1, "pull_request")
        second["pull_requests"] = [{"number": 459}]
        unrelated = run_fixture(TARGET_ID + 2, "pull_request")
        unrelated["head_sha"] = "a" * 40
        self.extra_targets[second["id"]] = second
        self.runs.extend([second, unrelated])
        self.refresh()
        self.assertEqual(self.posts, [
            f"repos/{REPO}/actions/runs/{TARGET_ID}/rerun",
            f"repos/{REPO}/actions/runs/{TARGET_ID + 1}/rerun",
        ])

    def test_closed_and_changed_heads_are_ignored(self):
        for field, value in (("state", "closed"), ("head", {**self.pull["head"], "sha": "a" * 40})):
            self.current_pull = {**self.pull, field: value}
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_stale_review_without_current_association_is_ignored(self):
        self.associated = []
        self.refresh()
        self.assertEqual(self.posts, [])

    def test_ambiguous_pr_association_is_rejected(self):
        self.associated.append({**self.pull, "number": 460})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_source_validation(self):
        cases = {
            "repository": {"full_name": "other/repo"},
            "path": ".github/workflows/other.yml",
            "workflow_id": 123,
            "event": "pull_request",
            "head_sha": "invalid",
            "head_repository": {"full_name": "other/repo"},
            "status": "in_progress",
        }
        original = deepcopy(self.source)
        for field, value in cases.items():
            with self.subTest(field=field):
                self.source = {**original, field: value}
                with self.assertRaises(ValueError):
                    self.refresh()
                self.assertEqual(self.posts, [])

    def test_wrong_target_revision_branch_or_fork_is_not_rerun(self):
        original = deepcopy(self.target)
        for field, value in (
            ("head_sha", "a" * 40), ("head_branch", "other"),
            ("head_repository", {"full_name": "other/repo"}),
            ("pull_requests", [{"number": 460}]),
            ("workflow_id", 123), ("event", "push"),
            ("path", ".github/workflows/other.yml"),
        ):
            with self.subTest(field=field):
                self.target = {**original, field: value}
                self.runs = [self.target]
                with self.assertRaises(ValueError):
                    self.refresh()
                self.assertEqual(self.posts, [])

    def test_missing_target_fails(self):
        self.runs = []
        with self.assertRaisesRegex(ValueError, "No matching"):
            self.refresh()

    def test_waits_for_concurrent_rerun(self):
        self.statuses = ["queued", "in_progress", "completed"]
        self.refresh()
        self.assertEqual(self.sleep.call_count, 2)
        self.assertEqual(len(self.posts), 1)

    def test_head_change_while_waiting_stops_rerun(self):
        self.statuses = ["in_progress"]
        self.sleep.side_effect = lambda _: self.pull["head"].update(sha="a" * 40)
        self.refresh()
        self.assertEqual(self.posts, [])

    def test_busy_target_times_out_without_post(self):
        self.statuses = ["in_progress"] * 60
        with self.assertRaises(TimeoutError):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_api_failures_propagate_without_success(self):
        self.mock_api.side_effect = subprocess.CalledProcessError(1, ["gh", "api"])
        with self.assertRaises(subprocess.CalledProcessError):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_expired_or_rejected_rerun_fails_visibly(self):
        def reject():
            raise subprocess.CalledProcessError(1, ["gh", "api"])

        self.on_post = reject
        with self.assertRaises(subprocess.CalledProcessError):
            self.refresh()

    def test_revalidates_target_immediately_before_rerun(self):
        self.statuses = ["in_progress"]
        self.sleep.side_effect = lambda _: self.target.update(path=".github/workflows/other.yml")
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_source_revision_must_match_concurrency_lock(self):
        for field, value in (("head_sha", "a" * 40), ("head_branch", "other")):
            with self.subTest(field=field):
                original = self.event["workflow_run"][field]
                self.event["workflow_run"][field] = value
                with self.assertRaisesRegex(ValueError, "differs from lock"):
                    self.refresh()
                self.assertEqual(self.posts, [])
                self.event["workflow_run"][field] = original

    def test_target_pr_association_is_rechecked(self):
        self.statuses = ["in_progress"]
        self.sleep.side_effect = lambda _: self.target.update(pull_requests=[{"number": 460}])
        with self.assertRaisesRegex(ValueError, "association changed"):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_current_pr_number_is_verified(self):
        self.current_pull = {**self.pull, "number": 460}
        with self.assertRaisesRegex(ValueError, "Wrong PR returned"):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_current_pr_number_is_rechecked_after_waiting(self):
        self.statuses = ["in_progress"]
        self.sleep.side_effect = lambda _: self.pull.update(number=460)
        with self.assertRaisesRegex(ValueError, "Wrong current PR returned"):
            self.refresh()
        self.assertEqual(self.posts, [])

    def test_malformed_responses_raise(self):
        self.mock_api.return_value = None
        self.mock_api.side_effect = None
        with self.assertRaises(TypeError):
            self.refresh()
        self.assertEqual(self.posts, [])


class ApiTests(unittest.TestCase):
    def test_production_concurrency_key_is_exact_and_revision_specific(self):
        workflow = (WORKFLOW.parent / "refresh-review-gate.yml").read_text()
        script = textwrap.dedent(
            workflow.split("        shell: python\n        run: |\n", 1)[1].split("\n  refresh:\n", 1)[0],
        )
        keys = []
        for branch, head in (("proposal", HEAD), ("Proposal", HEAD), ("other", HEAD), ("proposal", "a" * 40), ("proposal", HEAD)):
            with tempfile.TemporaryDirectory() as directory:
                event = Path(directory) / "event.json"
                output = Path(directory) / "output"
                event.write_text(json.dumps({"workflow_run": {"head_branch": branch, "head_sha": head}}))
                subprocess.run(
                    [sys.executable, "-c", script], check=True,
                    env={**os.environ, "GITHUB_EVENT_PATH": str(event), "GITHUB_OUTPUT": str(output)},
                )
                keys.append(output.read_text())
        self.assertEqual(len(set(keys[:4])), 4)
        self.assertEqual(keys[0], keys[4])
        self.assertRegex(keys[0], r"^key=[0-9a-f]{64}\n$")

    @patch.object(relay.subprocess, "run")
    def test_paginated_get_and_rerun_transport(self, command):
        command.return_value.stdout = "[[]]"
        self.assertEqual(relay.api("repos/owner/repo/test", paginate=True), [[]])
        self.assertEqual(command.call_args.args[0], [
            "gh", "api", "--method", "GET", "repos/owner/repo/test", "--paginate", "--slurp",
        ])
        self.assertTrue(command.call_args.kwargs["check"])
        command.return_value.stdout = ""
        relay.api("repos/owner/repo/actions/runs/1/rerun", method="POST")
        self.assertIn("POST", command.call_args.args[0])

    def test_workflow_trust_and_ci_wiring(self):
        directory = WORKFLOW.parent
        refresh_workflow = (directory / "refresh-review-gate.yml").read_text()
        self.assertIn("workflow_run:", refresh_workflow)
        self.assertIn("workflows: [review-gate]", refresh_workflow)
        self.assertIn("event == 'pull_request_review'", refresh_workflow)
        self.assertIn("ref: ${{ github.workflow_sha }}", refresh_workflow)
        self.assertIn("persist-credentials: false", refresh_workflow)
        self.assertIn("cancel-in-progress: false", refresh_workflow)
        self.assertIn("actions: write", refresh_workflow)
        self.assertNotIn("head_sha }}", refresh_workflow.split("steps:", 1)[1])
        self.assertNotIn("download-artifact", refresh_workflow)
        self.assertNotIn("actions: write", WORKFLOW.read_text())
        self.assertIn("  check-human-reviews:", WORKFLOW.read_text())
        consumer = (directory / "test-ep-review.yml").read_text()
        for path in (
            ".github/scripts/test_review_gate.py", ".github/scripts/refresh_review_gate.py",
            ".github/workflows/review-gate.yml", ".github/workflows/refresh-review-gate.yml",
        ):
            self.assertIn(path, consumer)
        self.assertIn('python3 -m unittest discover -s . -p "test_*.py" -v', consumer)


if __name__ == "__main__":
    unittest.main()
