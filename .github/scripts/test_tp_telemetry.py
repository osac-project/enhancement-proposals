"""Mocked tracing regressions; no model, workflow or collector is started."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tp_review
from tp_hooks import TestPlanHooks
from tp_telemetry import ReviewTrace


SENTINELS = (
    "credential-sentinel", "prompt-sentinel", "response-sentinel",
    "exception-sentinel", "environment-sentinel", "document-sentinel",
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
        self.summary_file = Path(self.temp.name) / "step-summary.md"
        self.hooks = Mock()
        self.hooks.check_already_scored.return_value = None
        self.hooks.build_prompt.return_value = SENTINELS[1]
        self.hooks.validate_scores.return_value = (None, [])
        self.hooks.validate_testplan_output.return_value = (None, [])

        def write_context(**kwargs):
            context = kwargs["work_dir"] / ".context"
            context.mkdir()
            (context / "document.md").write_text(SENTINELS[5])

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
            "GITHUB_STEP_SUMMARY": str(self.summary_file),
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
            self.assertEqual(set(record["payload"]), {"resourceSpans"})
            resource = record["payload"]["resourceSpans"][0]
            self.assertEqual(set(resource), {"resource", "scopeSpans"})
            self.assertEqual(resource["resource"]["attributes"], [{
                "key": "service.name",
                "value": {"stringValue": "test-plan-review"},
            }])
            span = resource["scopeSpans"][0]["spans"][0]
            self.assertEqual(resource["scopeSpans"][0]["scope"], {
                "name": "test-plan-review",
            })
            self.assertEqual(set(span) - {"parentSpanId"}, {
                "traceId", "spanId", "name", "kind", "startTimeUnixNano",
                "endTimeUnixNano", "status", "attributes",
            })
            self.assertIn(span["name"], {"test-plan-review", "test-plan-model-attempt"})
            self.assertRegex(span["traceId"], r"^[0-9a-f]{32}$")
            self.assertRegex(span["spanId"], r"^[0-9a-f]{16}$")
            self.assertGreaterEqual(
                int(span["endTimeUnixNano"]), int(span["startTimeUnixNano"])
            )
            self.assertIn(span["status"], ({"code": 1}, {"code": 2}))
            allowed = {
                "test_plan.operation", "gen_ai.request.model", "test_plan.outcome",
                "test_plan.attempt", "test_plan.attempt_count", "test_plan.retry_count",
                "input_tokens", "output_tokens", "cache_read_tokens",
                "cache_creation_tokens", "error.type",
            }
            self.assertLessEqual(set(attributes(span)), allowed)
            self.assertIn(attributes(span)["test_plan.operation"], {
                "test-plan-score", "test-plan-review", "other",
            })
            self.assertIn(attributes(span)["gen_ai.request.model"], {
                "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5", "other",
            })
            self.assertIn(attributes(span)["test_plan.outcome"], {
                "success", "error", "cancelled", "skipped", "stale",
            })
            if "error.type" in attributes(span):
                self.assertIn(attributes(span)["error.type"], {
                    "review_error", "context_error", "model_error", "invalid_output",
                    "incomplete_output", "validation_error", "publication_error",
                    "cancelled",
                })
            for attribute in span["attributes"]:
                self.assertIn(
                    next(iter(attribute["value"])), {"stringValue", "intValue"}
                )
                if "intValue" in attribute["value"]:
                    self.assertGreaterEqual(int(attribute["value"]["intValue"]), 0)
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

    def test_real_hook_partial_publication_is_nonfatal_but_traced_as_error(self):
        for failed_edit in (0, 1, None):
            with self.subTest(failed_edit=failed_edit):
                hooks = TestPlanHooks(repo="test/repo", skills_path="/tmp")
                for method in ("check_already_scored", "write_context", "build_prompt",
                               "validate_scores"):
                    setattr(hooks, method, getattr(self.hooks, method))
                responses = [subprocess.CompletedProcess(
                    ["gh"], 1 if index == failed_edit else 0,
                    stdout="", stderr=SENTINELS[3],
                ) for index in range(2)]
                with patch.object(hooks, "_upsert_score_comment") as comment, patch(
                    "tp_hooks.subprocess.run", side_effect=responses,
                ):
                    result = tp_review.run_review(
                        hooks, "test-plan-score", "TP-1",
                        {"number": 1, "headRefOid": "head"},
                        self.work_dir, model="claude-opus-4-6",
                    )
                self.assertIsNone(result)
                comment.assert_called_once()
                attempt, root = self.spans()
                self.assertEqual(attempt["status"]["code"], 1)
                if failed_edit is None:
                    self.assertEqual(attributes(root)["test_plan.outcome"], "success")
                    self.assertNotIn("error.type", attributes(root))
                else:
                    self.assertEqual(attributes(root)["test_plan.outcome"], "error")
                    self.assertEqual(attributes(root)["error.type"], "publication_error")

    def test_span_times_share_an_epoch_anchor_and_monotonic_offsets(self):
        with patch("tp_telemetry.time.time_ns", side_effect=[1000, 900, 800, 700]) as wall, patch(
            "tp_telemetry.time.monotonic_ns", side_effect=[100, 110, 120, 140, 150],
        ):
            with ReviewTrace(self.work_dir, "test-plan-score", "claude-opus-4-6") as trace:
                with trace.attempt():
                    pass
        attempt, root = self.spans()
        self.assertEqual(wall.call_count, 1)
        self.assertEqual(int(root["startTimeUnixNano"]), 1010)
        self.assertEqual(int(attempt["startTimeUnixNano"]), 1020)
        self.assertEqual(int(attempt["endTimeUnixNano"]), 1040)
        self.assertEqual(int(root["endTimeUnixNano"]), 1050)

    def test_real_hook_shadow_and_fork_respond_are_not_publication_errors(self):
        for skill, shadow in (("test-plan-score", True), ("test-plan-review", True),
                              ("test-plan-review", False)):
            with self.subTest(skill=skill, shadow=shadow):
                hooks = TestPlanHooks(
                    repo="test/repo", skills_path="/tmp", shadow=shadow,
                    pr_data={"head_repo": "contributor/repo", "head_branch": "plan",
                             "testplan_path": "enhancements/example/TestPlan.md",
                             "testplan_sha": "file-sha"},
                )
                hooks.publication_failed = True
                for method in ("check_already_scored", "write_context", "build_prompt",
                               "validate_scores", "validate_testplan_output"):
                    setattr(hooks, method, getattr(self.hooks, method))
                with patch.object(hooks, "_gh") as gh:
                    tp_review.run_review(
                        hooks, skill, "TP-1", {"number": 1, "headRefOid": "head"},
                        self.work_dir, model="claude-opus-4-6",
                    )
                gh.assert_not_called()
                self.assertIs(hooks.publication_failed, False)
                self.assertEqual(attributes(self.spans()[-1])["test_plan.outcome"], "success")

    def test_late_clock_failures_do_not_mask_success_or_model_exception(self):
        for failure_index in (3, 4):
            for model_failure in (None, RuntimeError(SENTINELS[3])):
                times = [100, 110, 120, 140, 150]
                times[failure_index] = OSError(SENTINELS[3])
                self.model.side_effect = model_failure
                with self.subTest(failure_index=failure_index, model_failure=bool(model_failure)):
                    with patch("tp_telemetry.time.monotonic_ns", side_effect=times):
                        if model_failure is None:
                            self.assertIsNone(self.run_review())
                        else:
                            with self.assertRaises(RuntimeError) as caught:
                                self.run_review()
                            self.assertIs(caught.exception, model_failure)
                    span, = self.spans()
                    self.assertEqual(span["name"], "test-plan-review" if failure_index == 3
                                     else "test-plan-model-attempt")

    def test_failed_record_update_preserves_previous_and_subsequent_jsonl(self):
        original_open = Path.open
        original_replace = Path.replace

        class InterruptedFile:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def write(self, text):
                if failure == "write":
                    self.stream.write(text[:13])
                    self.stream.flush()
                    raise OSError(SENTINELS[3])
                if failure == "short_write":
                    return self.stream.write(text[:13])
                return self.stream.write(text)

            def __exit__(self, *args):
                result = self.stream.__exit__(*args)
                if failure == "close":
                    raise OSError(SENTINELS[3])
                return result

        def interrupted_open(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return InterruptedFile(stream) if args and args[0] == "w" else stream

        def interrupted_replace(path, target):
            if failure == "replace":
                raise OSError(SENTINELS[3])
            return original_replace(path, target)

        for failure in ("write", "short_write", "close", "replace"):
            self.work_dir = Path(self.temp.name) / failure
            with self.subTest(failure=failure), ReviewTrace(
                self.work_dir, "test-plan-score", "claude-opus-4-6",
            ) as trace:
                with trace.attempt():
                    pass
                before = trace.path.read_text()
                with patch.object(Path, "open", interrupted_open), patch.object(
                    Path, "replace", interrupted_replace,
                ):
                    with trace.attempt():
                        pass
                self.assertEqual(trace.path.read_text(), before)
                self.assertEqual(list(trace.path.parent.iterdir()), [trace.path])
            first, root = self.spans()
            self.assertEqual(first["parentSpanId"], root["spanId"])
            self.assertEqual(attributes(root)["test_plan.attempt_count"], "2")
            self.assertEqual(list(trace.path.parent.iterdir()), [trace.path])

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

    def test_trace_initialization_failures_do_not_change_review(self):
        for target in ("tp_telemetry.uuid.uuid4", "tp_telemetry.time.time_ns",
                       "tp_telemetry.time.monotonic_ns"):
            with self.subTest(target=target), patch(
                target, side_effect=OSError(SENTINELS[3])
            ):
                self.model.side_effect = None
                self.hooks.apply_labels.reset_mock()
                self.run_review()
                self.hooks.apply_labels.assert_called_once()
                failure = RuntimeError(SENTINELS[3])
                self.model.side_effect = failure
                with self.assertRaises(RuntimeError) as caught:
                    self.run_review()
                self.assertIs(caught.exception, failure)

    def test_hostile_identity_and_numeric_subclasses_do_not_escape(self):
        class HostileModel(str):
            def __str__(self):
                return SENTINELS[0]

        class HostileNumber(int):
            def __str__(self):
                return SENTINELS[3]

        for model in (HostileModel("claude-opus-4-6"), [SENTINELS[0]], 42):
            with self.subTest(model_type=type(model)):
                self.work_dir = Path(self.temp.name) / type(model).__name__
                with ReviewTrace(self.work_dir, "test-plan-score", model) as trace:
                    with trace.attempt() as span:
                        span.record_usage({
                            "input_tokens": HostileNumber(10),
                            "output_tokens": {"content": SENTINELS[2]},
                            "cache_read_input_tokens": 2**1000,
                            "cache_creation_input_tokens": 7,
                        })
                attempt, root = self.spans()
                self.assertEqual(attributes(root)["gen_ai.request.model"], "other")
                self.assertEqual(attributes(attempt)["cache_creation_tokens"], "7")
                self.assertNotIn("input_tokens", attributes(attempt))
                self.assertNotIn("output_tokens", attributes(attempt))
                self.assertNotIn("cache_read_tokens", attributes(attempt))

    def test_output_write_errors_preserve_exception_and_flush_root(self):
        original_write = Path.write_text
        for skill, filename in (
            ("test-plan-score", "verdict.json"),
            ("test-plan-review", "testplan-output.md"),
        ):
            failure = OSError(SENTINELS[3])

            def failing_write(path, *args, **kwargs):
                if path.name == filename:
                    raise failure
                return original_write(path, *args, **kwargs)

            with self.subTest(skill=skill), patch.object(Path, "write_text", failing_write):
                with self.assertRaises(OSError) as caught:
                    self.run_review(skill)
                self.assertIs(caught.exception, failure)
                attempt, root = self.spans()
                self.assertEqual(attempt["status"]["code"], 1)
                self.assertEqual(attributes(root)["error.type"], "validation_error")
                self.hooks.apply_labels.assert_not_called()

    def test_raw_parser_error_is_not_recorded(self):
        with patch.object(tp_review, "parse_verdict", side_effect=ValueError(SENTINELS[3])):
            with self.assertRaisesRegex(RuntimeError, SENTINELS[3]):
                self.run_review()
        for span in self.spans():
            self.assertEqual(attributes(span)["error.type"], "invalid_output")

    def test_trace_directory_failures_preserve_results(self):
        original_mkdir = Path.mkdir

        def failing_mkdir(path, *args, **kwargs):
            if path.name == "_run":
                raise OSError(SENTINELS[3])
            return original_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", failing_mkdir):
            self.run_review()
            self.hooks.apply_labels.assert_called_once()
            failure = RuntimeError(SENTINELS[3])
            self.model.side_effect = failure
            with self.assertRaises(RuntimeError) as caught:
                self.run_review()
            self.assertIs(caught.exception, failure)

    def test_trace_close_errors_do_not_mask_success_or_review_error(self):
        original_open = Path.open

        class FailingClose:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self.stream

            def __exit__(self, *args):
                self.stream.close()
                raise OSError(SENTINELS[3])

        def failing_open(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return FailingClose(stream) if path.name == "claude-otel.jsonl" else stream

        with patch.object(Path, "open", failing_open):
            self.run_review()
            self.hooks.apply_labels.assert_called_once()
            failure = RuntimeError(SENTINELS[3])
            self.model.side_effect = failure
            with self.assertRaises(RuntimeError) as caught:
                self.run_review()
            self.assertIs(caught.exception, failure)
        self.assertFalse((self.work_dir / "_run/claude-otel.jsonl").exists())
        self.assertEqual(list((self.work_dir / "_run").iterdir()), [])

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


class ReviewSummaryIsolationTests(unittest.TestCase):
    def test_real_hook_summary_does_not_modify_ambient_ci_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            ambient = Path(directory) / "ambient-summary.md"
            ambient.write_text("existing job summary\n")
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(ambient)}):
                fixture = ReviewTelemetryTests()
                try:
                    fixture.setUp()
                    hooks = TestPlanHooks(repo="test/repo", skills_path="/tmp", shadow=True)
                    hooks.apply_labels(
                        "TP-42", {"verdict": "Ready", "_cost_summary": "mocked usage"},
                        "resolve", fixture.work_dir,
                    )
                    self.assertEqual(ambient.read_text(), "existing job summary\n")
                    self.assertEqual(
                        (Path(fixture.temp.name) / "step-summary.md").read_text(),
                        "\n### Test Plan Usage — TP-42\nmocked usage\n",
                    )
                finally:
                    fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
