"""Unit tests for ep_jira_type.py (no network, no live Jira)."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import ep_jira_type

CREDENTIALS = {"JIRA_EMAIL": "ci@example.com", "JIRA_API_TOKEN": "token"}

# Conclusions the posting step accepts from this script.
CHECK_RUN_CONCLUSIONS = frozenset({"success", "failure", "neutral"})


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def issue_payload(issue_type):
    return {"fields": {"issuetype": {"name": issue_type}}}


def files_for(directory, *names):
    return [f"enhancements/{directory}/{name}" for name in names]


class EnhancementDirsTest(unittest.TestCase):
    def test_returns_key_for_each_touched_directory(self):
        files = [
            "enhancements/OSAC-1110-storage-tier/prd.md",
            "enhancements/OSAC-1110-storage-tier/design.md",
            "enhancements/OSAC-1200-other/design.md",
        ]
        self.assertEqual(
            ep_jira_type.enhancement_dirs(files),
            [
                ("OSAC-1110-storage-tier", "OSAC-1110"),
                ("OSAC-1200-other", "OSAC-1200"),
            ],
        )

    def test_counts_any_file_in_the_directory(self):
        files = ["enhancements/OSAC-1110-storage-tier/ui-design.md"]
        self.assertEqual(
            ep_jira_type.enhancement_dirs(files),
            [("OSAC-1110-storage-tier", "OSAC-1110")],
        )

    def test_ignores_documents_outside_an_enhancement_directory(self):
        files = ["prd.md", "enhancements/prd.md", "guidelines/prd_guide.md"]
        self.assertEqual(ep_jira_type.enhancement_dirs(files), [])

    def test_ignores_directory_without_a_jira_key(self):
        files = ["enhancements/bare-metal-fulfillment/README.md"]
        self.assertEqual(ep_jira_type.enhancement_dirs(files), [])


class EvaluateTest(unittest.TestCase):
    def run_evaluate(self, files, responses, grandfathered=False):
        with mock.patch.dict(os.environ, CREDENTIALS, clear=False):
            with mock.patch.object(
                ep_jira_type, "is_grandfathered", return_value=grandfathered
            ):
                with mock.patch.object(
                    ep_jira_type.requests, "get", side_effect=responses
                ) as get:
                    result = ep_jira_type.evaluate(files, "base", "origin/main")
        return result, get

    def test_feature_passes(self):
        result, get = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [FakeResponse(200), FakeResponse(200, issue_payload("Feature"))],
        )
        self.assertEqual(result["state"], "success")
        self.assertIn("OSAC-1110", result["description"])
        self.assertEqual(get.call_count, 2)

    def test_feature_type_match_is_case_insensitive(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [FakeResponse(200), FakeResponse(200, issue_payload("feature"))],
        )
        self.assertEqual(result["state"], "success")

    def test_non_feature_fails_and_names_the_real_type(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [FakeResponse(200), FakeResponse(200, issue_payload("Task"))],
        )
        self.assertEqual(result["state"], "failure")
        self.assertIn("Task", result["description"])
        self.assertIn("not a Feature", result["description"])

    def test_missing_issue_fails(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-9999-nowhere", "prd.md"),
            [FakeResponse(200), FakeResponse(404)],
        )
        self.assertEqual(result["state"], "failure")
        self.assertIn("OSAC-9999", result["description"])

    def test_unreadable_project_is_neutral(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [FakeResponse(401)],
        )
        self.assertEqual(result["state"], "neutral")

    def test_unexpected_status_on_issue_is_neutral(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [FakeResponse(200), FakeResponse(500)],
        )
        self.assertEqual(result["state"], "neutral")

    def test_connection_error_is_neutral(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [ep_jira_type.requests.ConnectionError("boom")],
        )
        self.assertEqual(result["state"], "neutral")

    def test_error_after_probe_is_neutral(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [
                FakeResponse(200),
                ep_jira_type.requests.ConnectionError("boom"),
            ],
        )
        self.assertEqual(result["state"], "neutral")

    def test_missing_credentials_is_neutral(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(
                ep_jira_type, "is_grandfathered", return_value=False
            ):
                result = ep_jira_type.evaluate(
                    files_for("OSAC-1110-storage-tier", "prd.md"),
                    "base",
                    "origin/main",
                )
        self.assertEqual(result["state"], "neutral")
        self.assertIn("credentials", result["description"])

    def test_directory_with_only_a_non_canonical_file_is_checked(self):
        result, _ = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "ui-design.md"),
            [FakeResponse(200), FakeResponse(200, issue_payload("Task"))],
        )
        self.assertEqual(result["state"], "failure")

    def test_no_enhancement_directory_passes_without_calling_jira(self):
        result, get = self.run_evaluate(
            ["docs/notes.md"], [FakeResponse(200)]
        )
        self.assertEqual(result["state"], "success")
        get.assert_not_called()

    def test_grandfathered_directory_passes_without_calling_jira(self):
        result, get = self.run_evaluate(
            files_for("OSAC-1110-storage-tier", "prd.md"),
            [FakeResponse(200)],
            grandfathered=True,
        )
        self.assertEqual(result["state"], "success")
        self.assertIn("already exist", result["description"])
        get.assert_not_called()

    def test_every_new_directory_is_checked(self):
        files = files_for("OSAC-1-one", "prd.md") + files_for(
            "OSAC-2-two", "design.md"
        )
        result, get = self.run_evaluate(
            files,
            [
                FakeResponse(200),
                FakeResponse(200, issue_payload("Feature")),
                FakeResponse(200, issue_payload("Bug")),
            ],
        )
        self.assertEqual(result["state"], "failure")
        self.assertIn("OSAC-2", result["description"])
        self.assertEqual(get.call_count, 3)

    def test_first_failure_stops_further_lookups(self):
        files = files_for("OSAC-1-one", "prd.md") + files_for(
            "OSAC-2-two", "design.md"
        )
        result, get = self.run_evaluate(
            files,
            [FakeResponse(200), FakeResponse(200, issue_payload("Task"))],
        )
        self.assertEqual(result["state"], "failure")
        self.assertEqual(get.call_count, 2)

    def test_two_features_pass(self):
        files = files_for("OSAC-1-one", "prd.md") + files_for(
            "OSAC-2-two", "design.md"
        )
        result, _ = self.run_evaluate(
            files,
            [
                FakeResponse(200),
                FakeResponse(200, issue_payload("Feature")),
                FakeResponse(200, issue_payload("Feature")),
            ],
        )
        self.assertEqual(result["state"], "success")
        self.assertIn("OSAC-1", result["description"])
        self.assertIn("OSAC-2", result["description"])


class SanitizeTest(unittest.TestCase):
    def test_collapses_newlines(self):
        self.assertEqual(
            ep_jira_type.sanitize("a\nb\tc"), "a b c"
        )

    def test_truncates_to_the_status_limit(self):
        self.assertEqual(
            len(ep_jira_type.sanitize("x" * 500)),
            ep_jira_type.DESCRIPTION_MAX,
        )


class ResolveRefsTest(unittest.TestCase):
    def test_unresolvable_references_become_none(self):
        with mock.patch.dict(
            os.environ,
            {"PR_BASE_SHA": "deadbeef", "LIVE_BASE_REF": "origin/main"},
            clear=True,
        ):
            with mock.patch.object(ep_jira_type, "ref_exists", return_value=False):
                self.assertEqual(ep_jira_type.resolve_refs(), (None, None))

    def test_resolvable_references_are_returned(self):
        with mock.patch.dict(
            os.environ,
            {"PR_BASE_SHA": "abc123", "LIVE_BASE_REF": "origin/main"},
            clear=True,
        ):
            with mock.patch.object(ep_jira_type, "ref_exists", return_value=True):
                self.assertEqual(
                    ep_jira_type.resolve_refs(), ("abc123", "origin/main")
                )


class ChangedFilesTest(unittest.TestCase):
    def test_returns_file_names_from_the_api(self):
        completed = mock.Mock(
            stdout="enhancements/OSAC-1-a/prd.md\n\nREADME.md\n"
        )
        with mock.patch.object(
            ep_jira_type.subprocess, "run", return_value=completed
        ) as run:
            self.assertEqual(
                ep_jira_type.changed_files("o/r", 7),
                ["enhancements/OSAC-1-a/prd.md", "README.md"],
            )
        self.assertIn("repos/o/r/pulls/7/files", run.call_args.args[0])


class MainTest(unittest.TestCase):
    def call_main(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ep_jira_type.main(), 0)
        return json.loads(out.getvalue())

    def test_unresolved_references_emit_neutral_without_calling_the_api(self):
        with (
            mock.patch.object(ep_jira_type, "resolve_refs", return_value=(None, None)),
            mock.patch.object(ep_jira_type, "changed_files") as changed,
        ):
            emitted = self.call_main()
        self.assertEqual(emitted["state"], "neutral")
        self.assertIn(emitted["state"], CHECK_RUN_CONCLUSIONS)
        changed.assert_not_called()

    def test_no_changed_files_emits_success(self):
        with (
            mock.patch.object(
                ep_jira_type, "resolve_refs", return_value=("abc", "origin/main")
            ),
            mock.patch.object(ep_jira_type, "changed_files", return_value=[]),
            mock.patch.dict(
                os.environ, {"REPO": "o/r", "PR_NUMBER": "7"}, clear=False
            ),
        ):
            emitted = self.call_main()
        self.assertEqual(emitted["state"], "success")
        self.assertIn(emitted["state"], CHECK_RUN_CONCLUSIONS)

    def test_verdict_is_emitted_unchanged(self):
        verdict = {
            "state": "failure",
            "description": "OSAC-1 is a Task, not a Feature",
        }
        with (
            mock.patch.object(
                ep_jira_type, "resolve_refs", return_value=("abc", "origin/main")
            ),
            mock.patch.object(ep_jira_type, "changed_files", return_value=["x"]),
            mock.patch.object(ep_jira_type, "evaluate", return_value=verdict),
            mock.patch.dict(
                os.environ, {"REPO": "o/r", "PR_NUMBER": "7"}, clear=False
            ),
        ):
            emitted = self.call_main()
        self.assertEqual(emitted, verdict)
        self.assertIn(emitted["state"], CHECK_RUN_CONCLUSIONS)


    def test_incomplete_enumeration_fails(self):
        with (
            mock.patch.object(
                ep_jira_type, "resolve_refs", return_value=("abc", "origin/main")
            ),
            mock.patch.object(
                ep_jira_type, "changed_files", return_value=["a", "b"]
            ),
            mock.patch.object(ep_jira_type, "evaluate") as evaluate,
            mock.patch.dict(
                os.environ,
                {"REPO": "o/r", "PR_NUMBER": "7", "PR_CHANGED_FILES": "5"},
                clear=False,
            ),
        ):
            emitted = self.call_main()
        self.assertEqual(emitted["state"], "failure")
        self.assertIn("split", emitted["description"])
        evaluate.assert_not_called()

    def test_complete_enumeration_is_evaluated(self):
        verdict = {"state": "success", "description": "OSAC-1 is a Feature"}
        with (
            mock.patch.object(
                ep_jira_type, "resolve_refs", return_value=("abc", "origin/main")
            ),
            mock.patch.object(
                ep_jira_type, "changed_files", return_value=["a", "b"]
            ),
            mock.patch.object(
                ep_jira_type, "evaluate", return_value=verdict
            ) as evaluate,
            mock.patch.dict(
                os.environ,
                {"REPO": "o/r", "PR_NUMBER": "7", "PR_CHANGED_FILES": "2"},
                clear=False,
            ),
        ):
            emitted = self.call_main()
        self.assertEqual(emitted, verdict)
        evaluate.assert_called_once()

    def test_unknown_expected_count_is_ignored(self):
        verdict = {"state": "success", "description": "none"}
        with (
            mock.patch.object(
                ep_jira_type, "resolve_refs", return_value=("abc", "origin/main")
            ),
            mock.patch.object(
                ep_jira_type, "changed_files", return_value=["a"]
            ),
            mock.patch.object(ep_jira_type, "evaluate", return_value=verdict),
            mock.patch.dict(
                os.environ,
                {"REPO": "o/r", "PR_NUMBER": "7", "PR_CHANGED_FILES": "unknown"},
                clear=False,
            ),
        ):
            emitted = self.call_main()
        self.assertEqual(emitted, verdict)


if __name__ == "__main__":
    unittest.main()
