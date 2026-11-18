"""Mocked tracing regressions; no model, workflow or collector is started."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tp_review
from tp_telemetry import ReviewTrace


SENTINELS = (
    "credential-sentinel", "prompt-sentinel", "response-sentinel",
    "exception-sentinel", "environment-sentinel",
)


def attributes(span):
    return {
        attribute["key"]: next(iter(attribute["value"].values()))
        for attribute in span["attributes"]
    }


class ReviewTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work_dir = Path(self.temp.name) / "review"
        self.hooks = Mock()
        self.hooks.check_already_scored.return_value = None
        self.hooks.build_prompt.return_value = SENTINELS[1]
        self.hooks.validate_scores.return_value = (None, [])
        self.hooks.validate_testplan_output.return_value = (None, [])

        def write_context(**kwargs):
            context = kwargs["work_dir"] / ".context"
            context.mkdir()
            (context / "document.md").write_text(SENTINELS[1])

        self.hooks.write_context.side_effect = write_context
        self.model = self.enterContext(patch.object(
            tp_review, "complete", return_value=(
                '{"verdict":"Ready","summary":"response-sentinel"}',
                {"input_tokens": 10, "output_tokens": 5},
            ),
        ))
        self.latest_pr = self.enterContext(patch.object(
            tp_review, "get_pull_request", return_value={"head": {"sha": "head"}},
        ))
        self.enterContext(patch.dict(os.environ, {
            "TRACE_TEST_SECRET": SENTINELS[4],
            "GOOGLE_APPLICATION_CREDENTIALS": SENTINELS[0],
        }))

    def run_review(self, skill="test-plan-score", model="claude-opus-4-6"):
        return tp_review.run_review(
            self.hooks, skill, "TP-1",
            {"number": 1, "headRefOid": "head", "body": SENTINELS[1]},
            self.work_dir, model=model,
        )

    def spans(self):
        text = (self.work_dir / "_run/claude-otel.jsonl").read_text()
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, text)
        result = []
        for line in text.splitlines():
            record = json.loads(line)
            self.assertEqual(set(record), {"ts", "path", "payload"})
            self.assertEqual(record["path"], "/v1/traces")
            resource = record["payload"]["resourceSpans"][0]
            self.assertEqual(resource["resource"]["attributes"], [{
                "key": "service.name",
                "value": {"stringValue": "test-plan-review"},
            }])
            span = resource["scopeSpans"][0]["spans"][0]
            self.assertRegex(span["traceId"], r"^[0-9a-f]{32}$")
            self.assertRegex(span["spanId"], r"^[0-9a-f]{16}$")
            self.assertGreaterEqual(
                int(span["endTimeUnixNano"]), int(span["startTimeUnixNano"])
            )
            self.assertNotIn("message", span["status"])
            for attribute in span["attributes"]:
                self.assertIn(
                    next(iter(attribute["value"])), {"stringValue", "intValue"}
                )
            result.append(span)
        return result

    def test_success_modes_preserve_outputs_and_correlate_spans(self):
        for skill, filename in (
            ("test-plan-score", "verdict.json"),
            ("test-plan-review", "testplan-output.md"),
        ):
            with self.subTest(skill=skill):
                self.run_review(skill)
                attempt, root = self.spans()
                self.assertEqual(attempt["parentSpanId"], root["spanId"])
                self.assertEqual(attempt["traceId"], root["traceId"])
                self.assertNotIn("parentSpanId", root)
                self.assertEqual((attempt["kind"], root["kind"]), (3, 1))
                self.assertLessEqual(
                    int(root["startTimeUnixNano"]), int(attempt["startTimeUnixNano"])
                )
                self.assertLessEqual(
                    int(attempt["endTimeUnixNano"]), int(root["endTimeUnixNano"])
                )
                self.assertEqual(attempt["status"]["code"], 1)
                self.assertEqual(root["status"]["code"], 1)
                self.assertEqual(attributes(attempt)["input_tokens"], "10")
                self.assertEqual(attributes(attempt)["output_tokens"], "5")
                self.assertNotIn("input_tokens", attributes(root))
                self.assertEqual(attributes(root)["test_plan.operation"], skill)
                self.assertEqual(attributes(root)["test_plan.retry_count"], "0")
                self.assertTrue((self.work_dir / filename).exists())
        self.assertEqual(self.hooks.apply_labels.call_count, 2)
        self.assertEqual(self.model.call_args.kwargs["model"], "claude-opus-4-6")

    def test_retry_records_failed_attempt_and_actual_usage_before_completion(self):
        def complete(*args, **kwargs):
            if self.model.call_count == 1:
                return SENTINELS[2], {"input_tokens": 10}
            first, = self.spans()
            self.assertEqual(attributes(first)["error.type"], "invalid_output")
            self.assertEqual(first["status"]["code"], 2)
            return '{"verdict":"Ready"}', {"output_tokens": 20}

        self.model.side_effect = complete
        self.run_review()
        first, second, root = self.spans()
        self.assertEqual(attributes(root)["test_plan.attempt_count"], "2")
        self.assertEqual(attributes(root)["test_plan.retry_count"], "1")
        self.assertEqual(attributes(root)["test_plan.outcome"], "success")
        self.assertNotIn("error.type", attributes(root))
        self.assertNotIn("output_tokens", attributes(first))
        self.assertNotIn("input_tokens", attributes(second))
        self.assertEqual(attributes(second)["output_tokens"], "20")
        for index, span in enumerate((first, second), start=1):
            self.assertEqual(attributes(span)["test_plan.attempt"], str(index))
            self.assertEqual(span["parentSpanId"], root["spanId"])
            self.assertEqual(span["traceId"], root["traceId"])
        verdict = json.loads((self.work_dir / "verdict.json").read_text())
        self.assertEqual(verdict["_cost_summary"], "**Tokens:** 10 in / 20 out")

    def test_parse_exhaustion_flushes_errors_without_exception_text(self):
        self.model.return_value = (SENTINELS[2], {"input_tokens": 12})
        with self.assertRaises(RuntimeError):
            self.run_review()
        spans = self.spans()
        self.assertEqual(len(spans), 3)
        for span in spans:
            self.assertEqual(span["status"]["code"], 2)
            self.assertEqual(attributes(span)["error.type"], "invalid_output")
        self.hooks.apply_labels.assert_not_called()

    def test_model_errors_preserve_exception_and_do_not_invent_usage_or_retry(self):
        for skill in ("test-plan-score", "test-plan-review"):
            for failure in (RuntimeError(SENTINELS[3]), TimeoutError(SENTINELS[0])):
                with self.subTest(skill=skill, failure=type(failure)):
                    self.model.reset_mock()
                    self.model.side_effect = failure
                    with self.assertRaises(type(failure)) as caught:
                        self.run_review(skill)
                    self.assertIs(caught.exception, failure)
                    attempt, root = self.spans()
                    for span in (attempt, root):
                        self.assertEqual(span["status"]["code"], 2)
                        self.assertEqual(attributes(span)["error.type"], "model_error")
                        self.assertFalse(set(attributes(span)) & {
                            "input_tokens", "output_tokens", "cache_read_tokens",
                            "cache_creation_tokens",
                        })
                    self.model.assert_called_once()

    def test_early_stop_does_not_export_arbitrary_stop_reason(self):
        for skill in ("test-plan-score", "test-plan-review"):
            with self.subTest(skill=skill):
                self.model.return_value = (
                    SENTINELS[2], {"stop_reason": SENTINELS[3], "output_tokens": 7}
                )
                with self.assertRaises(RuntimeError):
                    self.run_review(skill)
                attempt, root = self.spans()
                self.assertEqual(attributes(attempt)["output_tokens"], "7")
                for span in (attempt, root):
                    self.assertEqual(attributes(span)["error.type"], "incomplete_output")

    def test_review_validation_and_publication_failures(self):
        for stage, category in (
            ("write_context", "context_error"),
            ("validate_scores", "validation_error"),
            ("apply_labels", "publication_error"),
        ):
            with self.subTest(stage=stage), patch.object(
                self.hooks, stage, side_effect=RuntimeError(SENTINELS[3])
            ):
                with self.assertRaisesRegex(RuntimeError, SENTINELS[3]):
                    self.run_review()
                root = self.spans()[-1]
                self.assertEqual(root["status"]["code"], 2)
                self.assertEqual(attributes(root)["error.type"], category)

    def test_invalid_review_output_flushes_after_validation(self):
        self.hooks.validate_testplan_output.return_value = (None, [SENTINELS[2]])
        with self.assertRaises(RuntimeError):
            self.run_review("test-plan-review")
        attempt, root = self.spans()
        self.assertEqual(attempt["status"]["code"], 1)
        self.assertEqual(attributes(root)["error.type"], "validation_error")

    def test_stale_and_skipped_runs_do_not_publish(self):
        self.latest_pr.return_value = {"head": {"sha": "new-head"}}
        self.run_review()
        self.assertEqual(attributes(self.spans()[-1])["test_plan.outcome"], "stale")
        self.hooks.apply_labels.assert_not_called()
        self.work_dir = Path(self.temp.name) / "skipped"
        self.hooks.check_already_scored.return_value = "already scored"
        self.model.reset_mock()
        self.run_review()
        root, = self.spans()
        self.assertEqual(attributes(root)["test_plan.outcome"], "skipped")
        self.assertEqual(attributes(root)["test_plan.attempt_count"], "0")
        self.model.assert_not_called()

    def test_usage_and_identity_are_strictly_allowlisted(self):
        self.model.return_value = ('{"verdict":"Ready"}', {
            "input_tokens": 0, "output_tokens": True,
            "cache_read_input_tokens": 3,
            "cache_creation_input_tokens": -1,
            "headers": {"Authorization": SENTINELS[0]},
            "prompt": SENTINELS[1], "response": SENTINELS[2],
            "error": SENTINELS[3], "arbitrary_number": 99,
        })
        self.run_review(model=SENTINELS[0])
        attempt, root = self.spans()
        self.assertEqual(attributes(attempt)["input_tokens"], "0")
        self.assertEqual(attributes(attempt)["cache_read_tokens"], "3")
        self.assertEqual(set(attributes(attempt)), {
            "test_plan.operation", "gen_ai.request.model", "test_plan.outcome",
            "test_plan.attempt", "input_tokens", "cache_read_tokens",
        })
        for span in (attempt, root):
            self.assertEqual(attributes(span)["gen_ai.request.model"], "other")
        self.model.assert_called_once()
        self.assertEqual(self.model.call_args.kwargs["model"], SENTINELS[0])

    def test_no_usage_is_invented_for_successful_response_without_usage(self):
        self.model.return_value = ('{"verdict":"Ready"}', {})
        self.run_review()
        attempt, _ = self.spans()
        self.assertNotIn("input_tokens", attributes(attempt))
        self.assertNotIn("output_tokens", attributes(attempt))

    def test_trace_write_failures_do_not_mask_success_or_original_failure(self):
        original_open = Path.open

        def failing_open(path, *args, **kwargs):
            if path.name == "claude-otel.jsonl":
                raise OSError(SENTINELS[0])
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", failing_open):
            self.run_review()
            self.hooks.apply_labels.assert_called_once()
            failure = RuntimeError(SENTINELS[3])
            self.model.side_effect = failure
            with self.assertRaises(RuntimeError) as caught:
                self.run_review()
            self.assertIs(caught.exception, failure)

    def test_cancellation_finalizes_with_bounded_category(self):
        self.model.side_effect = KeyboardInterrupt(SENTINELS[3])
        with self.assertRaises(KeyboardInterrupt):
            self.run_review()
        for span in self.spans():
            self.assertEqual(span["status"]["code"], 2)
            self.assertEqual(attributes(span)["test_plan.outcome"], "cancelled")
            self.assertEqual(attributes(span)["error.type"], "cancelled")

    def test_unknown_operation_and_non_numeric_usage_are_not_serialized(self):
        with ReviewTrace(self.work_dir, SENTINELS[1], SENTINELS[0]) as trace:
            with trace.attempt() as span:
                span.record_usage({
                    "input_tokens": SENTINELS[0], "output_tokens": 2**63,
                    "cache_read_input_tokens": 1.5,
                })
                span.record_usage(None)
        attempt, root = self.spans()
        self.assertNotIn("input_tokens", attributes(attempt))
        self.assertNotIn("output_tokens", attributes(attempt))
        self.assertNotIn("cache_read_tokens", attributes(attempt))
        self.assertEqual(attributes(root)["test_plan.operation"], "other")


if __name__ == "__main__":
    unittest.main()
