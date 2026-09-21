import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tp_hooks import SCORE_COMMENT_TAG, TestPlanHooks


BOT = "github-actions[bot]"


class TestPlanCommentTests(unittest.TestCase):
    def setUp(self):
        self.hooks = TestPlanHooks(
            repo="test/repo", skills_path="/tmp", shadow=False,
        )
        self.body = f"## Test Plan Review: TP-42\n{SCORE_COMMENT_TAG}\n"

    @staticmethod
    def _response(*comments):
        return "\n".join(json.dumps(comment) for comment in comments)

    @staticmethod
    def _metadata_response(*comments):
        candidates = []
        for comment in comments:
            if comment["user"]["login"] != BOT:
                continue
            body = comment.get("body") or ""
            if SCORE_COMMENT_TAG in body:
                kind = "preferred"
            elif body.lstrip().startswith("## Test Plan Review:"):
                kind = "fallback"
            else:
                continue
            candidates.append({
                "id": comment["id"],
                "user": comment["user"],
                "created_at": comment["created_at"],
                "candidate_kind": kind,
            })
        return TestPlanCommentTests._response(*candidates)

    @staticmethod
    def _comment(comment_id, body, created_at="2026-09-14T00:00:00Z",
                 login=BOT):
        return {
            "id": comment_id,
            "user": {"login": login},
            "body": body,
            "created_at": created_at,
        }

    def test_find_score_comment_uses_bot_and_stable_marker(self):
        human = self._comment(1, self.body, login="developer")
        unrelated_bot = self._comment(
            2, "## Test Plan Review: old", created_at="2026-09-16T00:00:00Z",
        )
        canonical = self._comment(3, self.body, created_at="2026-09-15T00:00:00Z")

        with patch.object(
            self.hooks, "_gh", side_effect=[
                self._metadata_response(human, unrelated_bot, canonical),
                self._response(canonical),
            ],
        ) as gh:
            found = self.hooks._find_score_comment("42")

        self.assertEqual(found["id"], 3)
        args = gh.call_args_list[0].args[0]
        self.assertIn("issues/42/comments?per_page=100", args[1])
        self.assertIn("--paginate", args)
        self.assertIn("--jq", args)
        self.assertIn("max_by(.created_at)", args[args.index("--jq") + 1])

    def test_legacy_bot_comment_is_adopted_and_updated(self):
        legacy = self._comment(9, "## Test Plan Review: [TP-42]\n<!-- sha:abc12345 -->")
        captured = {}

        def fake_gh(args, check=False):
            if args[0] == "api" and "issues/42/comments?per_page=100" in args[1]:
                return self._metadata_response(legacy)
            if args[0] == "api" and "issues/comments/9" in args[1]:
                return self._response(legacy)
            captured["path"] = Path(args[args.index("-F") + 1].split("@", 1)[1])
            captured["body"] = captured["path"].read_text()
            return ""

        with patch.object(
            self.hooks, "_gh", side_effect=fake_gh,
        ):
            updated = self.hooks._upsert_score_comment("42", self.body)
        self.assertTrue(updated)
        self.assertIn(SCORE_COMMENT_TAG, captured["body"])
        self.assertFalse(captured["path"].exists())

    @unittest.skipUnless(shutil.which("jq"), "jq is required for filter integration")
    def test_generated_page_filter_executes_without_comment_bodies(self):
        canonical = self._comment(3, self.body)
        captured = {}

        def fake_gh(args, check=False):
            if "issues/42/comments?per_page=100" in args[1]:
                captured["filter"] = args[args.index("--jq") + 1]
                return self._metadata_response(canonical)
            return self._response(canonical)

        with patch.object(self.hooks, "_gh", side_effect=fake_gh):
            self.hooks._find_score_comment("42")

        page = [canonical]
        result = subprocess.run(
            ["jq", "-r", "-c", captured["filter"]],
            input=json.dumps(page), capture_output=True, text=True, check=True,
        )
        output = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(output[0]["id"], 3)
        self.assertEqual(output[0]["user"], {"login": BOT})
        self.assertEqual(output[0]["candidate_kind"], "preferred")
        self.assertNotIn("body", output[0])

    def test_creates_comment_when_no_score_comment_exists(self):
        captured = {}

        def fake_gh(args, check=False):
            if args[0] == "api":
                return ""
            captured["args"] = args
            captured["path"] = Path(args[args.index("--body-file") + 1])
            captured["body"] = captured["path"].read_text()
            return ""

        with patch.object(self.hooks, "_gh", side_effect=fake_gh):
            updated = self.hooks._upsert_score_comment("42", self.body)

        self.assertFalse(updated)
        self.assertEqual(captured["args"][:2], ["pr", "comment"])
        self.assertIn(SCORE_COMMENT_TAG, captured["body"])
        self.assertFalse(captured["path"].exists())

    def test_updates_existing_comment_in_place(self):
        existing = self._comment(23, self.body)
        calls = []
        captured = {}

        def fake_gh(args, check=False):
            calls.append(args)
            if args[0] == "api" and "issues/42/comments?per_page=100" in args[1]:
                return self._metadata_response(existing)
            if args[0] == "api" and "issues/comments/23" in args[1]:
                return self._response(existing)
            captured["path"] = Path(args[args.index("-F") + 1].split("@", 1)[1])
            return ""

        with patch.object(self.hooks, "_gh", side_effect=fake_gh):
            updated = self.hooks._upsert_score_comment("42", self.body)

        self.assertTrue(updated)
        self.assertTrue(any("PATCH" in call for call in calls))
        patch_call = next(call for call in calls if "PATCH" in call)
        self.assertIn("issues/comments/23", " ".join(patch_call))
        self.assertFalse(any(call[:2] == ["pr", "comment"] for call in calls))
        self.assertFalse(captured["path"].exists())

    def test_failed_update_cleans_up_comment_file(self):
        existing = self._comment(23, self.body)
        captured = {}

        def fake_gh(args, check=False):
            if args[0] == "api" and "issues/42/comments?per_page=100" in args[1]:
                return self._metadata_response(existing)
            if args[0] == "api" and "issues/comments/23" in args[1]:
                return self._response(existing)
            captured["path"] = Path(args[args.index("-F") + 1].split("@", 1)[1])
            raise RuntimeError("GitHub unavailable")

        with patch.object(self.hooks, "_gh", side_effect=fake_gh):
            with self.assertRaises(RuntimeError):
                self.hooks._upsert_score_comment("42", self.body)

        self.assertFalse(captured["path"].exists())

    def test_same_sha_is_skipped_and_changed_sha_is_scored(self):
        body = f"{self.body}\n<!-- sha:abc12345 -->"
        existing = self._comment(23, body)
        def fake_gh(args, check=False):
            if "issues/42/comments?per_page=100" in args[1]:
                return self._metadata_response(existing)
            if "issues/comments/23" in args[1]:
                return self._response(existing)
            return ""

        with patch.object(self.hooks, "_gh", side_effect=fake_gh):
            same_sha = self.hooks.check_already_scored(
                "TP-42", {"headRefOid": "abc12345deadbeef"},
                mode="resolve", work_dir=tempfile.gettempdir(),
            )
            changed_sha = self.hooks.check_already_scored(
                "TP-42", {"headRefOid": "fedcba98deadbeef"},
                mode="resolve", work_dir=tempfile.gettempdir(),
            )

        self.assertEqual(same_sha, "Already scored at SHA abc12345")
        self.assertIsNone(changed_sha)


class ApplyScoreTests(unittest.TestCase):
    def test_apply_score_writes_marker_and_head_sha(self):
        hooks = TestPlanHooks(repo="test/repo", skills_path="/tmp", shadow=False)
        captured = {}
        verdict = {
            "verdict": "Rework",
            "scores": {
                "specificity": 1,
                "grounding": 1,
                "scope_fidelity": 1,
                "actionability": 1,
                "consistency": 1,
            },
            "criterionNotes": {},
            "findings": {"critical": [], "important": [], "suggestions": []},
        }

        def fake_gh(args, check=False):
            if args[0] == "api":
                return ""
            if args[:2] == ["pr", "comment"]:
                path = Path(args[args.index("--body-file") + 1])
                captured["path"] = path
                captured["body"] = path.read_text()
            return ""

        with patch.object(hooks, "_gh", side_effect=fake_gh):
            hooks._apply_score(
                "TP-42", verdict, tempfile.gettempdir(),
                ticket={"headRefOid": "abc12345deadbeef"},
            )

        self.assertIn(SCORE_COMMENT_TAG, captured["body"])
        self.assertIn("<!-- sha:abc12345 -->", captured["body"])
        self.assertFalse(captured["path"].exists())


if __name__ == "__main__":
    unittest.main()
