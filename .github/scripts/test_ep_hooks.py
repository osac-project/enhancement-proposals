import json
import os
import tempfile
import unittest

from ep_hooks import (
    DESIGN_DISPLAY,
    DESIGN_KEYS,
    EPHooks,
    PRD_DISPLAY,
    PRD_KEYS,
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
        self.prompt = self.hooks._prd_prompt()

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
        self.prompt = self.hooks._design_prompt()

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


if __name__ == "__main__":
    unittest.main()
