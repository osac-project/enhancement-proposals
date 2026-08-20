import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from ep_hooks import (
    DESIGN_DISPLAY,
    DESIGN_KEYS,
    DESIGN_PASS_THRESHOLD,
    EPHooks,
    PRD_DISPLAY,
    PRD_KEYS,
    PRD_PASS_THRESHOLD,
)


class PRDKeysTests(unittest.TestCase):
    """PRD_KEYS must match the prd-review skill's rubric criteria."""

    EXPECTED_PRD_KEYS = {"what", "why", "user_facing_focus", "right_sized", "testability"}

    def test_prd_keys_match_skill_rubric(self):
        self.assertEqual(PRD_KEYS, self.EXPECTED_PRD_KEYS)

    def test_prd_keys_no_overlap_with_design_keys(self):
        overlap = PRD_KEYS & DESIGN_KEYS
        self.assertEqual(overlap, {"testability"})

    def test_design_keys_unchanged(self):
        self.assertEqual(
            DESIGN_KEYS,
            {"feasibility", "testability", "scope", "architecture"},
        )


class PRDDisplayTests(unittest.TestCase):
    """Display labels must exist for every PRD and design key."""

    def test_prd_display_covers_all_keys(self):
        self.assertEqual(set(PRD_DISPLAY.keys()), PRD_KEYS)

    def test_design_display_covers_all_keys(self):
        self.assertEqual(set(DESIGN_DISPLAY.keys()), DESIGN_KEYS)

    def test_prd_display_labels(self):
        self.assertEqual(PRD_DISPLAY["what"], "WHAT (clear need)")
        self.assertEqual(PRD_DISPLAY["why"], "WHY (justification)")
        self.assertEqual(PRD_DISPLAY["user_facing_focus"], "User-Facing Focus")
        self.assertEqual(PRD_DISPLAY["right_sized"], "Right-Sized")
        self.assertEqual(PRD_DISPLAY["testability"], "Testability")


class PRDPromptTests(unittest.TestCase):
    """_prd_prompt() must request scores using the skill's criteria."""

    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp")
        self.prompt = self.hooks._prd_prompt({})

    def test_prompt_contains_all_prd_keys(self):
        for key in PRD_KEYS:
            self.assertIn(f"- {key} (0-2):", self.prompt)

    def test_prompt_does_not_contain_old_keys(self):
        old_keys = {"how", "task", "size"}
        for key in old_keys:
            self.assertNotIn(f"- {key} (0-2):", self.prompt)

    def test_prompt_verdict_json_uses_new_keys(self):
        self.assertIn('"user_facing_focus"', self.prompt)
        self.assertIn('"right_sized"', self.prompt)
        self.assertIn('"testability"', self.prompt)

    def test_prompt_pass_threshold(self):
        self.assertIn("total >= 7", self.prompt)
        self.assertIn("no zeros", self.prompt)


class DesignPromptTests(unittest.TestCase):
    """_design_prompt() must remain unchanged (already correct)."""

    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp")
        self.prompt = self.hooks._design_prompt({})

    def test_prompt_contains_all_design_keys(self):
        for key in DESIGN_KEYS:
            self.assertIn(f"- {key} (0-2):", self.prompt)


class ValidateScoresTests(unittest.TestCase):
    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp")
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        verdict_path = os.path.join(self.work_dir, "verdict.json")
        if os.path.exists(verdict_path):
            os.unlink(verdict_path)
        os.rmdir(self.work_dir)

    def _write_verdict(self, verdict):
        with open(os.path.join(self.work_dir, "verdict.json"), "w") as f:
            json.dump(verdict, f)

    def test_valid_prd_scores(self):
        self._write_verdict({
            "verdict": "pass",
            "scores": {
                "what": 2, "why": 2, "user_facing_focus": 2,
                "right_sized": 2, "testability": 2,
            },
            "total": 10,
        })
        _, errors = self.hooks.validate_scores(
            "EP-1", work_dir=self.work_dir,
        )
        self.assertEqual(errors, [])

    def test_old_prd_keys_rejected(self):
        self._write_verdict({
            "verdict": "pass",
            "scores": {
                "what": 2, "why": 2, "how": 2, "task": 2, "size": 2,
            },
            "total": 10,
        })
        _, errors = self.hooks.validate_scores(
            "EP-1", work_dir=self.work_dir,
        )
        self.assertTrue(len(errors) > 0, "Old PRD keys should produce errors")

    def test_valid_design_scores(self):
        self._write_verdict({
            "verdict": "pass",
            "scores": {
                "feasibility": 2, "testability": 2,
                "scope": 2, "architecture": 2,
            },
            "total": 8,
        })
        _, errors = self.hooks.validate_scores(
            "EP-1", work_dir=self.work_dir,
        )
        self.assertEqual(errors, [])

    def test_missing_verdict_file(self):
        _, errors = self.hooks.validate_scores(
            "EP-1", work_dir=self.work_dir,
        )
        self.assertIn("verdict.json not found", errors[0])

    def test_total_auto_corrected(self):
        self._write_verdict({
            "verdict": "pass",
            "scores": {
                "what": 2, "why": 1, "user_facing_focus": 2,
                "right_sized": 1, "testability": 2,
            },
            "total": 99,
        })
        self.hooks.validate_scores("EP-1", work_dir=self.work_dir)
        with open(os.path.join(self.work_dir, "verdict.json")) as f:
            v = json.load(f)
        self.assertEqual(v["total"], 8)


class ApplyLabelsDisplayTests(unittest.TestCase):
    """apply_labels() must use display labels from PRD_DISPLAY/DESIGN_DISPLAY."""

    def setUp(self):
        self.hooks = EPHooks(
            repo="test/repo", skills_path="/tmp", shadow=True,
        )

    def test_prd_labels_in_comment(self):
        verdict = {
            "verdict": "pass",
            "scores": {
                "what": 2, "why": 2, "user_facing_focus": 1,
                "right_sized": 2, "testability": 1,
            },
            "total": 8,
            "criterionNotes": {},
            "summary": "Good PRD",
            "feedback": "Minor issues",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.hooks.apply_labels(
                "EP-1", verdict, "resolve", "/tmp",
                ticket={"headRefOid": "abc12345"},
            )
        output = buf.getvalue()
        self.assertIn("SHADOW", output)
        self.assertIn("8/10", output)

    def test_design_labels_unchanged(self):
        verdict = {
            "verdict": "pass",
            "scores": {
                "feasibility": 2, "testability": 2,
                "scope": 2, "architecture": 2,
            },
            "total": 8,
            "criterionNotes": {},
            "summary": "Good design",
            "feedback": "No issues",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.hooks.apply_labels(
                "EP-1", verdict, "resolve", "/tmp",
                ticket={"headRefOid": "abc12345"},
            )
        output = buf.getvalue()
        self.assertIn("SHADOW", output)
        self.assertIn("8/8", output)


class ApplyLabelsPassFailTests(unittest.TestCase):
    """apply_labels() PASS/FAIL must match skill thresholds, not max_total // 2."""

    def setUp(self):
        self.hooks = EPHooks(
            repo="test/repo", skills_path="/tmp", shadow=True,
        )

    def _verdict(self, scores):
        return {
            "verdict": "pass",
            "scores": scores,
            "total": sum(scores.values()),
            "criterionNotes": {},
            "summary": "test",
            "feedback": "test",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }

    def _get_pass_fail(self, scores):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.hooks.apply_labels(
                "EP-1", self._verdict(scores), "resolve", "/tmp",
                ticket={"headRefOid": "abc12345"},
            )
        output = buf.getvalue()
        if "PASS)" in output:
            return "PASS"
        return "FAIL"

    def test_prd_threshold_constants(self):
        self.assertEqual(PRD_PASS_THRESHOLD, 7)
        self.assertEqual(DESIGN_PASS_THRESHOLD, 5)

    def test_prd_all_ones_total5_fails(self):
        scores = {"what": 1, "why": 1, "user_facing_focus": 1,
                  "right_sized": 1, "testability": 1}
        self.assertEqual(self._get_pass_fail(scores), "FAIL")

    def test_prd_total8_with_zero_fails(self):
        scores = {"what": 2, "why": 2, "user_facing_focus": 2,
                  "right_sized": 2, "testability": 0}
        self.assertEqual(self._get_pass_fail(scores), "FAIL")

    def test_prd_total7_no_zeros_passes(self):
        scores = {"what": 2, "why": 2, "user_facing_focus": 1,
                  "right_sized": 1, "testability": 1}
        self.assertEqual(self._get_pass_fail(scores), "PASS")

    def test_prd_total6_no_zeros_fails(self):
        scores = {"what": 1, "why": 1, "user_facing_focus": 2,
                  "right_sized": 1, "testability": 1}
        self.assertEqual(self._get_pass_fail(scores), "FAIL")

    def test_prd_perfect_score_passes(self):
        scores = {"what": 2, "why": 2, "user_facing_focus": 2,
                  "right_sized": 2, "testability": 2}
        self.assertEqual(self._get_pass_fail(scores), "PASS")

    def test_design_total5_no_zeros_passes(self):
        scores = {"feasibility": 2, "testability": 1,
                  "scope": 1, "architecture": 1}
        self.assertEqual(self._get_pass_fail(scores), "PASS")

    def test_design_total4_no_zeros_fails(self):
        scores = {"feasibility": 1, "testability": 1,
                  "scope": 1, "architecture": 1}
        self.assertEqual(self._get_pass_fail(scores), "FAIL")

    def test_design_total6_with_zero_fails(self):
        scores = {"feasibility": 2, "testability": 2,
                  "scope": 2, "architecture": 0}
        self.assertEqual(self._get_pass_fail(scores), "FAIL")

    def test_design_perfect_score_passes(self):
        scores = {"feasibility": 2, "testability": 2,
                  "scope": 2, "architecture": 2}
        self.assertEqual(self._get_pass_fail(scores), "PASS")


class DesignPromptThresholdTests(unittest.TestCase):
    """_design_prompt() threshold must match design-review skill."""

    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp")
        self.prompt = self.hooks._design_prompt({})

    def test_prompt_pass_threshold(self):
        self.assertIn("total >= 5", self.prompt)
        self.assertIn("no zeros", self.prompt)


class CriterionNoteTruncationTests(unittest.TestCase):
    """Criterion notes in the PR comment must not be cut off at 500 chars (OSAC-2907)."""

    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=False)

    def _render_comment(self, note_text):
        verdict = {
            "verdict": "pass",
            "scores": {
                "feasibility": 2, "testability": 2,
                "scope": 2, "architecture": 2,
            },
            "total": 8,
            "criterionNotes": {
                "feasibility": note_text, "testability": "",
                "scope": "", "architecture": "",
            },
            "summary": "",
            "feedback": "",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }
        captured = {}

        def fake_run(cmd, capture_output=True, text=True, timeout=120):
            if "comment" in cmd and "--body-file" in cmd:
                body_file = cmd[cmd.index("--body-file") + 1]
                with open(body_file) as f:
                    captured["body"] = f.read()
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with mock.patch("ep_hooks.subprocess.run", side_effect=fake_run):
            self.hooks.apply_labels(
                "EP-1", verdict, "resolve", "/tmp",
                ticket={"headRefOid": "abc12345"},
            )
        return captured["body"]

    def test_criterion_note_over_500_chars_not_truncated(self):
        long_note = "x" * 700
        body = self._render_comment(long_note)
        self.assertIn(long_note, body)

    def test_criterion_note_still_bounded_at_1000(self):
        long_note = "x" * 5000
        body = self._render_comment(long_note)
        self.assertIn("x" * 1000, body)
        self.assertNotIn("x" * 1001, body)

    def test_sanitize_text_default_limit_unchanged(self):
        """Unrelated _sanitize_text call sites (e.g. findings items) keep the 500 default."""
        self.assertEqual(len(self.hooks._sanitize_text("x" * 600)), 500)


class FeatureContextBlockTests(unittest.TestCase):
    """Both prompts must surface the harness-derived Jira key as trusted
    context, and never fall back to ticket title/body as a key source."""

    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp")

    def test_prd_prompt_includes_key_when_present(self):
        prompt = self.hooks._prd_prompt({"jira_key": "OSAC-1589"})
        self.assertIn("Jira Feature key: OSAC-1589", prompt)

    def test_design_prompt_includes_key_when_present(self):
        prompt = self.hooks._design_prompt({"jira_key": "OSAC-2872"})
        self.assertIn("Jira Feature key: OSAC-2872", prompt)

    def test_prompt_says_could_not_be_determined_when_absent(self):
        prompt = self.hooks._prd_prompt({"jira_key": None})
        self.assertIn("Jira Feature key: could not be determined", prompt)

    def test_prompt_says_could_not_be_determined_when_ambiguous(self):
        prompt = self.hooks._prd_prompt(
            {"jira_key": None, "jira_key_ambiguous": True}
        )
        self.assertIn("Jira Feature key: could not be determined", prompt)

    def test_prompt_missing_ticket_fields_defaults_to_undetermined(self):
        prompt = self.hooks._design_prompt({})
        self.assertIn("Jira Feature key: could not be determined", prompt)

    def test_prompt_never_echoes_title_or_body_as_key_source(self):
        ticket = {
            "jira_key": None,
            "jira_key_ambiguous": False,
            "title": "OSAC-9999: unrelated title mentioning a Jira key",
            "body": "See OSAC-8888 for context",
        }
        prd_prompt = self.hooks._prd_prompt(ticket)
        design_prompt = self.hooks._design_prompt(ticket)
        for prompt in (prd_prompt, design_prompt):
            self.assertNotIn("OSAC-9999", prompt)
            self.assertNotIn("OSAC-8888", prompt)
            self.assertIn("Jira Feature key: could not be determined", prompt)

    def test_build_prompt_threads_ticket_through(self):
        prompt = self.hooks.build_prompt(
            "EP-1", "resolve", "prd-review", ticket={"jira_key": "OSAC-42"}
        )
        self.assertIn("Jira Feature key: OSAC-42", prompt)


class ApplyLabelsFeatureContextTests(unittest.TestCase):
    """apply_labels() must render the Feature line and Structural notes
    section, sourced from the ticket dict's harness-derived fields."""

    def setUp(self):
        self.hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=False)
        self.verdict = {
            "verdict": "pass",
            "scores": {
                "feasibility": 2, "testability": 2,
                "scope": 2, "architecture": 2,
            },
            "total": 8,
            "criterionNotes": {},
            "summary": "Good design",
            "feedback": "No issues",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }

    def _comment(self, ticket):
        from pathlib import Path
        from unittest.mock import patch

        captured = {}

        def fake_gh(args, check=False):
            if "comment" in args and "--body-file" in args:
                captured["body"] = Path(args[args.index("--body-file") + 1]).read_text()
            return ""

        with patch.object(self.hooks, "_gh", side_effect=fake_gh):
            self.hooks.apply_labels(
                "EP-1", self.verdict, "resolve", "/tmp", ticket=ticket,
            )
        return captured["body"]

    def test_feature_line_with_key(self):
        output = self._comment({
            "headRefOid": "abc12345", "jira_key": "OSAC-1589",
            "jira_key_ambiguous": False, "structure_violations": [],
        })
        self.assertIn("**Feature:** OSAC-1589", output)

    def test_feature_line_could_not_be_determined(self):
        output = self._comment({
            "headRefOid": "abc12345", "jira_key": None,
            "jira_key_ambiguous": False, "structure_violations": [],
        })
        self.assertIn("**Feature:** could not be determined", output)

    def test_feature_line_ambiguous_treated_as_undetermined(self):
        output = self._comment({
            "headRefOid": "abc12345", "jira_key": None,
            "jira_key_ambiguous": True, "structure_violations": [],
        })
        self.assertIn("**Feature:** could not be determined", output)

    def test_structural_notes_lists_violations(self):
        output = self._comment({
            "headRefOid": "abc12345", "jira_key": "OSAC-1589",
            "jira_key_ambiguous": False,
            "structure_violations": [
                "enhancements/vm-worker-nodes/prd.md: directory doesn't match the required format",
            ],
        })
        self.assertIn("### Structural notes (1)", output)
        self.assertIn("doesn't match the required format", output)

    def test_structural_notes_none_when_empty(self):
        output = self._comment({
            "headRefOid": "abc12345", "jira_key": "OSAC-1589",
            "jira_key_ambiguous": False, "structure_violations": [],
        })
        self.assertIn("### Structural notes (0)", output)


class ApplyLogisticsCommentTests(unittest.TestCase):
    """apply_logistics_comment() posts the minimal "skipped" comment for a
    PR ep_classify has determined is LOGISTICS_ONLY (Phase B)."""

    def setUp(self):
        self.ticket = {
            "headRefOid": "abc12345",
            "jira_key": "OSAC-1589",
            "jira_key_ambiguous": False,
            "structure_violations": [],
        }

    def _comment(self, ticket=None, skill_name="design-review", shadow=False):
        from pathlib import Path
        from unittest.mock import patch

        hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=shadow)
        captured = {}

        def fake_gh(args, check=False):
            if "comment" in args and "--body-file" in args:
                captured["body"] = Path(args[args.index("--body-file") + 1]).read_text()
            if "--add-label" in args:
                captured["label"] = args[args.index("--add-label") + 1]
            return ""

        with patch.object(hooks, "_gh", side_effect=fake_gh) as mock_gh:
            hooks.apply_logistics_comment(
                "EP-1", ticket or self.ticket, skill_name,
            )
        return captured, mock_gh

    def test_marker_is_design_review_for_design_skill(self):
        captured, _ = self._comment(skill_name="design-review")
        self.assertIn("## AI Design Review: Logistics-only change", captured["body"])

    def test_marker_is_ep_review_for_prd_skill(self):
        captured, _ = self._comment(skill_name="prd-review")
        self.assertIn("## AI EP Review: Logistics-only change", captured["body"])

    def test_feature_line_rendered(self):
        captured, _ = self._comment()
        self.assertIn("**Feature:** OSAC-1589", captured["body"])

    def test_feature_line_could_not_be_determined(self):
        captured, _ = self._comment(ticket={
            "headRefOid": "abc12345", "jira_key": None,
            "jira_key_ambiguous": False, "structure_violations": [],
        })
        self.assertIn("**Feature:** could not be determined", captured["body"])

    def test_structural_notes_rendered(self):
        captured, _ = self._comment(ticket={
            "headRefOid": "abc12345", "jira_key": "OSAC-1589",
            "jira_key_ambiguous": False,
            "structure_violations": ["some violation"],
        })
        self.assertIn("### Structural notes (1)", captured["body"])
        self.assertIn("some violation", captured["body"])

    def test_posts_comment_and_adds_reviewed_label(self):
        captured, mock_gh = self._comment()
        self.assertIn("body", captured)
        self.assertEqual(captured.get("label"), "rfe-creator-auto-reviewed")
        self.assertEqual(mock_gh.call_count, 2)

    def test_shadow_mode_prints_only_no_gh_calls(self):
        from unittest.mock import patch

        hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=True)
        with patch.object(hooks, "_gh") as mock_gh:
            hooks.apply_logistics_comment("EP-1", self.ticket, "design-review")
        mock_gh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
