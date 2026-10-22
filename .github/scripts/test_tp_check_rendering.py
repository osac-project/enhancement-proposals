"""Aggregate feedback is data inside trusted Markdown structure."""

import unittest

from tp_check import report_summary, text


class AggregateRenderingTests(unittest.TestCase):
    def test_feedback_and_errors_are_literal_markdown(self):
        attack = (
            "[approve](https://evil.example) ![pixel](https://evil.example/p)\n"
            "[ref][target]\n[target]: https://evil.example\n"
            "` ## heading <img src=x> &lt;script&gt; @all | end"
        )
        report = {
            "plans": [{"path": "enhancements/example/TestPlan.md", "total": 8,
                       "verdict": "Revise", "feedback": attack}],
            "error": attack,
        }
        summary = report_summary(report)
        self.assertTrue(summary.startswith("### Test Plan Score\n"))
        self.assertIn("| Plan | Score | Verdict | Feedback |", summary)
        self.assertEqual(summary.count(text(attack)), 2)
        for syntax in ("[approve](", "![pixel]", "[ref][target]", "<img src=x>",
                       "@all", "\n## heading"):
            self.assertNotIn(syntax, summary)
        self.assertIn("&#64;all", summary)
        self.assertIn(r"\| end", summary)
        self.assertIn(r"\&lt\;script\&gt\;", summary)

    def test_literal_escaping_preserves_readable_text_and_citations(self):
        self.assertEqual(text("No changes requested"), "No changes requested")
        self.assertEqual(text("source/file.go:100-160"),
                         r"source\/file\.go\:100\-160")
        self.assertEqual(text(r"\*"), r"\\\*")
        self.assertEqual(text("line\r\nnext"), "line  next")

    def test_truncation_does_not_leave_an_unpaired_escape(self):
        self.assertEqual(text("*" * 2000, max_len=1999), r"\*" * 999)
        self.assertEqual(text("\\" * 2000, max_len=1999), "\\\\" * 999)
        self.assertLessEqual(len(text("*" * 2000, max_len=2000)), 2000)


if __name__ == "__main__":
    unittest.main()
