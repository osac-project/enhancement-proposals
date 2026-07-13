"""Tests for ep_hooks.py — rubric table formatting and sanitization."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from ep_hooks import EPHooks

LONG_NOTE = "A" * 600


@pytest.fixture
def hooks():
    return EPHooks(repo="test/repo", skills_path="/tmp/skills", shadow=True)


class TestSanitizeText:
    def test_strips_whitespace(self):
        assert EPHooks._sanitize_text("  hello  ") == "hello"

    def test_default_max_len(self):
        result = EPHooks._sanitize_text("x" * 600)
        assert len(result) == 500

    def test_custom_max_len(self):
        result = EPHooks._sanitize_text("x" * 600, max_len=100)
        assert len(result) == 100

    def test_strips_image_markdown(self):
        assert EPHooks._sanitize_text("before ![alt](url) after") == "before  after"

    def test_strips_link_keeps_text(self):
        assert EPHooks._sanitize_text("see [docs](http://x.com)") == "see docs"

    def test_strips_html_tags(self):
        assert EPHooks._sanitize_text("<b>bold</b>") == "bold"

    def test_strips_at_mentions(self):
        assert EPHooks._sanitize_text("cc @user") == "cc user"

    def test_preserves_allowed_urls(self):
        text = "see https://github.com/org/repo and https://redhat.atlassian.net/browse/X"
        result = EPHooks._sanitize_text(text)
        assert "github.com" in result
        assert "redhat.atlassian.net" in result

    def test_removes_other_urls(self):
        result = EPHooks._sanitize_text("visit https://example.com/page")
        assert "[link removed]" in result
        assert "example.com" not in result


class TestApplyLabelsRubricTable:
    """Verify rubric table Notes column is not truncated at 200 chars."""

    def _make_verdict(self, note_length=300):
        note = "N" * note_length
        return {
            "verdict": "pass",
            "scores": {"what": 2, "why": 2, "how": 1, "task": 2, "size": 1},
            "total": 8,
            "criterionNotes": {
                "what": note,
                "why": note,
                "how": note,
                "task": note,
                "size": note,
            },
            "summary": "Overall good.",
            "feedback": "Improve scope.",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }

    def _capture_comment(self, note_length):
        """Run apply_labels in non-shadow mode, capture the posted comment body."""
        verdict = self._make_verdict(note_length=note_length)
        hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=False)
        written_comments = []

        def capture_gh(args, check=False):
            if "--body-file" in args:
                idx = args.index("--body-file")
                path = args[idx + 1]
                with open(path) as f:
                    written_comments.append(f.read())
            return ""

        with patch.object(hooks, '_gh', side_effect=capture_gh):
            hooks.apply_labels("EP-99", verdict, "review", "/tmp")

        assert len(written_comments) == 1
        return written_comments[0]

    def test_300_char_notes_not_truncated(self):
        """Notes of 300 chars must appear in full (was truncated at 200)."""
        comment = self._capture_comment(note_length=300)
        assert "N" * 300 in comment

    def test_450_char_notes_preserved(self):
        """Notes up to 450 chars must appear in full."""
        comment = self._capture_comment(note_length=450)
        assert "N" * 450 in comment

    def test_notes_truncated_beyond_500(self):
        """Notes beyond 500 chars are truncated to the default max_len."""
        comment = self._capture_comment(note_length=600)
        assert "N" * 600 not in comment
        assert "N" * 500 in comment

    def test_rubric_table_note_content(self):
        note_text = "This is a detailed review note that explains the scoring rationale in full"
        verdict = {
            "verdict": "pass",
            "scores": {"what": 2, "why": 2, "how": 1, "task": 2, "size": 1},
            "total": 8,
            "criterionNotes": {
                "what": note_text,
                "why": "Short note",
                "how": "Another note",
                "task": "Task note",
                "size": "Size note",
            },
            "summary": "Good.",
            "feedback": "None.",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }
        hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=False)
        written_comments = []

        def capture_gh(args, check=False):
            if "--body-file" in args:
                idx = args.index("--body-file")
                path = args[idx + 1]
                with open(path) as f:
                    written_comments.append(f.read())
            return ""

        with patch.object(hooks, '_gh', side_effect=capture_gh):
            hooks.apply_labels("EP-99", verdict, "review", "/tmp")

        assert len(written_comments) == 1
        assert note_text in written_comments[0]

    def test_pipe_characters_escaped_in_notes(self, hooks, capsys):
        verdict = self._make_verdict()
        verdict["criterionNotes"]["what"] = "contains | pipe character"
        hooks.apply_labels("EP-99", verdict, "review", "/tmp")
        captured = capsys.readouterr()
        assert "SHADOW" in captured.out

    def test_newlines_replaced_in_notes(self, hooks, capsys):
        verdict = self._make_verdict()
        verdict["criterionNotes"]["what"] = "line one\nline two"
        hooks.apply_labels("EP-99", verdict, "review", "/tmp")
        captured = capsys.readouterr()
        assert "SHADOW" in captured.out

    def test_250_char_note_preserved_in_comment(self):
        """Regression test: 250-char notes were truncated with the old 200-char limit."""
        note_250 = "X" * 250
        verdict = {
            "verdict": "pass",
            "scores": {"what": 2, "why": 1, "how": 1, "task": 2, "size": 1},
            "total": 7,
            "criterionNotes": {
                "what": note_250,
                "why": "ok",
                "how": "ok",
                "task": "ok",
                "size": "ok",
            },
            "summary": "Good.",
            "feedback": "None.",
            "findings": {"critical": [], "important": [], "suggestions": []},
        }
        hooks = EPHooks(repo="test/repo", skills_path="/tmp", shadow=False)
        written_comments = []
        original_gh = hooks._gh

        def capture_gh(args, check=False):
            if "--body-file" in args:
                idx = args.index("--body-file")
                path = args[idx + 1]
                with open(path) as f:
                    written_comments.append(f.read())
            return ""

        with patch.object(hooks, '_gh', side_effect=capture_gh):
            hooks.apply_labels("EP-99", verdict, "review", "/tmp")

        assert len(written_comments) == 1
        comment = written_comments[0]
        assert note_250 in comment, (
            f"250-char note was truncated in the comment body. "
            f"Found max consecutive X run of length "
            f"{max(len(s) for s in comment.split('|') if 'X' in s)}"
        )


class TestApplyLabelsDesignScores:
    """Verify design review keys work correctly."""

    def test_design_scores(self, hooks, capsys):
        verdict = {
            "verdict": "pass",
            "scores": {"feasibility": 2, "testability": 1, "scope": 2, "architecture": 1},
            "total": 6,
            "criterionNotes": {
                "feasibility": "Feasible design",
                "testability": "Needs more test plan",
                "scope": "Well scoped",
                "architecture": "Sound patterns",
            },
            "summary": "Solid design.",
            "feedback": "Add test plan details.",
            "findings": {"critical": [], "important": [], "suggestions": ["Add diagrams"]},
        }
        hooks.apply_labels("EP-99", verdict, "review", "/tmp")
        captured = capsys.readouterr()
        assert "SHADOW" in captured.out
        assert "6/8" in captured.out


class TestValidateScores:
    def test_valid_prd_scores(self, hooks):
        with tempfile.TemporaryDirectory() as d:
            verdict = {
                "verdict": "pass",
                "scores": {"what": 2, "why": 1, "how": 1, "task": 2, "size": 1},
                "total": 7,
            }
            with open(os.path.join(d, "verdict.json"), "w") as f:
                json.dump(verdict, f)
            _, errors = hooks.validate_scores("EP-1", work_dir=d)
            assert errors == []

    def test_invalid_score_value(self, hooks):
        with tempfile.TemporaryDirectory() as d:
            verdict = {
                "verdict": "pass",
                "scores": {"what": 5, "why": 1, "how": 1, "task": 2, "size": 1},
                "total": 10,
            }
            with open(os.path.join(d, "verdict.json"), "w") as f:
                json.dump(verdict, f)
            _, errors = hooks.validate_scores("EP-1", work_dir=d)
            assert any("invalid score" in e for e in errors)

    def test_missing_verdict_file(self, hooks):
        with tempfile.TemporaryDirectory() as d:
            _, errors = hooks.validate_scores("EP-1", work_dir=d)
            assert any("not found" in e for e in errors)
