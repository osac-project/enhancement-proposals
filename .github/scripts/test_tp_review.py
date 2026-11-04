import json
import unittest

import tp_review


class FindTestplanPathTests(unittest.TestCase):
    def test_prefers_an_added_testplan(self):
        slug, path = tp_review.find_testplan_path([
            {"filename": "enhancements/OSAC-1433-existing/testplan.md",
             "status": "modified", "changes": 6},
            {"filename": "enhancements/OSAC-7068-new/testplan.md",
             "status": "added", "changes": 617},
        ])
        self.assertEqual(slug, "OSAC-7068-new")
        self.assertEqual(path, "enhancements/OSAC-7068-new/testplan.md")

    def test_prefers_the_most_changed_testplan(self):
        slug, path = tp_review.find_testplan_path([
            {"filename": "enhancements/OSAC-1-small/testplan.md",
             "status": "modified", "changes": 2},
            {"filename": "enhancements/OSAC-2-large/TestPlan.md",
             "status": "modified", "changes": 40},
        ])
        self.assertEqual(slug, "OSAC-2-large")
        self.assertEqual(path, "enhancements/OSAC-2-large/TestPlan.md")

    def test_ignores_a_removed_testplan(self):
        slug, path = tp_review.find_testplan_path([
            {"filename": "enhancements/OSAC-1-old/testplan.md",
             "status": "removed", "changes": 90},
            {"filename": "enhancements/OSAC-2-new/testplan.md",
             "status": "modified", "changes": 3},
        ])
        self.assertEqual(slug, "OSAC-2-new")

    def test_returns_none_without_a_testplan(self):
        self.assertEqual(tp_review.find_testplan_path([]), (None, None))
        self.assertEqual(
            tp_review.find_testplan_path([
                {"filename": "enhancements/OSAC-1/design.md"},
            ]),
            (None, None),
        )


class ParseVerdictTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(
            tp_review.parse_verdict('{"verdict": "Ready"}'),
            {"verdict": "Ready"},
        )

    def test_markdown_fence(self):
        self.assertEqual(
            tp_review.parse_verdict('```json\n{"verdict": "Ready"}\n```'),
            {"verdict": "Ready"},
        )

    def test_leading_prose(self):
        self.assertEqual(
            tp_review.parse_verdict('Here it is:\n{"verdict": "Ready"}\nDone.'),
            {"verdict": "Ready"},
        )

    def test_single_quoted_python_dict(self):
        self.assertEqual(
            tp_review.parse_verdict("{'verdict': 'Ready', 'total': 8}"),
            {"verdict": "Ready", "total": 8},
        )

    def test_bare_keys(self):
        self.assertEqual(
            tp_review.parse_verdict(
                '{verdict: "Ready", scores: {"specificity": 2}, total: 8}'
            ),
            {"verdict": "Ready", "scores": {"specificity": 2}, "total": 8},
        )

    def test_bare_keys_preserve_punctuation_in_strings(self):
        self.assertEqual(
            tp_review.parse_verdict(
                '{summary: "passes, but: check this", verdict: "Revise"}'
            ),
            {"summary": "passes, but: check this", "verdict": "Revise"},
        )

    def test_recovers_object_from_json_array(self):
        self.assertEqual(
            tp_review.parse_verdict('[{"verdict": "Ready"}]'),
            {"verdict": "Ready"},
        )

    def test_non_object_json_raises(self):
        with self.assertRaises(ValueError):
            tp_review.parse_verdict("null")

    def test_unhashable_literal_key_uses_the_json_fallback(self):
        with self.assertRaises(json.JSONDecodeError):
            tp_review.parse_verdict("{[1]: 2}")

    def test_non_serializable_literal_value_uses_the_json_fallback(self):
        with self.assertRaises(json.JSONDecodeError):
            tp_review.parse_verdict("{'scores': {1, 2}}")

    def test_invalid_json_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            tp_review.parse_verdict('{"verdict": ')

    def test_missing_object_raises(self):
        with self.assertRaises(ValueError):
            tp_review.parse_verdict("no json here")


class RequestVerdictTests(unittest.TestCase):
    def test_retries_after_invalid_json(self):
        responses = iter([
            ("not json", {"stop_reason": "end_turn"}),
            ('{"verdict": "Ready"}', {"stop_reason": "end_turn"}),
        ])
        prompts = []

        def complete(prompt, system, *, max_tokens, model):
            prompts.append(prompt)
            return next(responses)

        verdict, usage = tp_review.request_verdict(
            "base prompt", max_tokens=10, model="m", complete_fn=complete
        )
        self.assertEqual(verdict, {"verdict": "Ready"})
        self.assertEqual(usage["stop_reason"], "end_turn")
        self.assertTrue(prompts[1].startswith("base prompt"))
        self.assertIn("not valid JSON", prompts[1])

    def test_accumulates_usage_across_retries(self):
        responses = iter([
            ("not json", {
                "stop_reason": "end_turn",
                "input_tokens": 100,
                "output_tokens": 50,
            }),
            ('{"verdict": "Ready"}', {
                "stop_reason": "end_turn",
                "input_tokens": 200,
                "output_tokens": 75,
            }),
        ])

        def complete(prompt, system, *, max_tokens, model):
            return next(responses)

        _, usage = tp_review.request_verdict(
            "base prompt", max_tokens=10, model="m", complete_fn=complete
        )
        self.assertEqual(usage["input_tokens"], 300)
        self.assertEqual(usage["output_tokens"], 125)
        self.assertEqual(usage["stop_reason"], "end_turn")
        self.assertEqual(
            tp_review.usage_summary(usage), "**Tokens:** 300 in / 125 out"
        )

    def test_retries_after_non_object_json(self):
        responses = iter([
            ("null", {"stop_reason": "end_turn"}),
            ('{"verdict": "Ready"}', {"stop_reason": "end_turn"}),
        ])

        def complete(prompt, system, *, max_tokens, model):
            return next(responses)

        verdict, _ = tp_review.request_verdict(
            "base prompt", max_tokens=10, model="m", complete_fn=complete
        )
        self.assertEqual(verdict, {"verdict": "Ready"})

    def test_raises_after_repeated_invalid_json(self):
        def complete(prompt, system, *, max_tokens, model):
            return ("not json", {"stop_reason": "end_turn"})

        with self.assertRaises(RuntimeError):
            tp_review.request_verdict(
                "p", max_tokens=10, model="m", complete_fn=complete
            )

    def test_raises_when_the_response_ends_early(self):
        def complete(prompt, system, *, max_tokens, model):
            return ('{"verdict": "Ready"}', {"stop_reason": "max_tokens"})

        with self.assertRaises(RuntimeError):
            tp_review.request_verdict(
                "p", max_tokens=10, model="m", complete_fn=complete
            )


if __name__ == "__main__":
    unittest.main()
