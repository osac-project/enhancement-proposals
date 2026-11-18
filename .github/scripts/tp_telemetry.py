"""Best-effort, metadata-only OTLP JSONL for trusted test-plan reviews.

The envelope and bare token attributes match the shared runner's collector
and trace consumer. No request, response, environment or exception text is
accepted. Each completed span is atomically persisted before returning.
"""

import json
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


SAFE_MODELS = frozenset({
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5",
})
OPERATIONS = frozenset({"test-plan-score", "test-plan-review"})
ERROR_CATEGORIES = frozenset({
    "review_error", "context_error", "model_error", "invalid_output",
    "incomplete_output", "validation_error", "publication_error", "cancelled",
})
TOKEN_FIELDS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_input_tokens": "cache_read_tokens",
    "cache_creation_input_tokens": "cache_creation_tokens",
}


def _attribute(key, value):
    value_type = "intValue" if type(value) is int else "stringValue"
    return {"key": key, "value": {value_type: str(value)}}


class _Span:
    def __init__(self, trace, name, *, parent_id=None, attempt=None):
        self.trace = trace
        self.name = name
        self.parent_id = parent_id
        self.attempt = attempt
        self.span_id = None
        self.start_ns = None
        try:
            self.span_id = uuid.uuid4().hex[:16]
            self.start_ns = trace.now_ns()
        except Exception:
            pass
        self.outcome = "success"
        self.error_category = "model_error" if parent_id else "review_error"
        self.tokens = {}

    def record_usage(self, usage):
        if type(usage) is not dict:
            return
        for source, target in TOKEN_FIELDS.items():
            value = usage.get(source)
            if type(value) is int and 0 <= value <= 2**63 - 1:
                self.tokens[target] = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            self.outcome = "error"
            if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
                self.outcome = "cancelled"
                self.error_category = "cancelled"
        if self.parent_id and self.outcome != "success":
            self.trace.root.error_category = self.error_category
        self.trace.emit(self)
        return False


class ReviewTrace:
    def __init__(self, work_dir, operation, model):
        self.path = Path(work_dir) / "_run" / "claude-otel.jsonl"
        self.operation = (
            operation if type(operation) is str and operation in OPERATIONS else "other"
        )
        self.model = model if type(model) is str and model in SAFE_MODELS else "other"
        self.trace_id = None
        self.epoch_ns = None
        self.monotonic_ns = None
        try:
            self.trace_id = uuid.uuid4().hex
            self.epoch_ns = time.time_ns()
            self.monotonic_ns = time.monotonic_ns()
        except Exception:
            pass
        self.attempts = 0
        self.root = _Span(self, "test-plan-review")

    def now_ns(self):
        if self.epoch_ns is None or self.monotonic_ns is None:
            return None
        return self.epoch_ns + time.monotonic_ns() - self.monotonic_ns

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self.root.__exit__(exc_type, exc, traceback)

    def attempt(self):
        self.attempts += 1
        return _Span(
            self, "test-plan-model-attempt",
            parent_id=self.root.span_id, attempt=self.attempts,
        )

    def emit(self, span):
        try:
            if (
                not (self.trace_id and self.root.span_id and span.span_id)
                or self.root.start_ns is None or span.start_ns is None
            ):
                return
            outcome = span.outcome if span.outcome in {
                "success", "error", "cancelled", "skipped", "stale",
            } else "error"
            attributes = [
                _attribute("test_plan.operation", self.operation),
                _attribute("gen_ai.request.model", self.model),
                _attribute("test_plan.outcome", outcome),
            ]
            if span.parent_id:
                attributes.append(_attribute("test_plan.attempt", span.attempt))
                attributes.extend(
                    _attribute(key, value) for key, value in span.tokens.items()
                )
            else:
                attributes.extend([
                    _attribute("test_plan.attempt_count", self.attempts),
                    _attribute("test_plan.retry_count", max(0, self.attempts - 1)),
                ])
            if outcome in {"error", "cancelled"}:
                category = span.error_category
                attributes.append(_attribute(
                    "error.type",
                    category if category in ERROR_CATEGORIES else "review_error",
                ))
            end_ns = max(span.start_ns, self.now_ns())
            payload_span = {
                "traceId": self.trace_id,
                "spanId": span.span_id,
                "name": span.name,
                "kind": 3 if span.parent_id else 1,
                "startTimeUnixNano": str(span.start_ns),
                "endTimeUnixNano": str(end_ns),
                "status": {"code": 2 if outcome in {"error", "cancelled"} else 1},
                "attributes": attributes,
            }
            if span.parent_id:
                payload_span["parentSpanId"] = span.parent_id
            record = {
                "ts": datetime.fromtimestamp(end_ns / 1e9, timezone.utc).isoformat(),
                "path": "/v1/traces",
                "payload": {"resourceSpans": [{
                    "resource": {"attributes": [
                        _attribute("service.name", "test-plan-review"),
                    ]},
                    "scopeSpans": [{
                        "scope": {"name": "test-plan-review"},
                        "spans": [payload_span],
                    }],
                }]},
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".otel-", dir=self.path.parent) as directory:
                staged = Path(directory) / self.path.name
                content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
                content += json.dumps(record) + "\n"
                with staged.open("w", encoding="utf-8") as stream:
                    if stream.write(content) != len(content):
                        return
                staged.replace(self.path)
        except Exception:
            pass
