#!/usr/bin/env python3

from datetime import datetime, timedelta, timezone
import unittest

from stale_lifecycle import (
    LifecycleProcessor,
    ROTTEN_LABEL,
    STALE_LABEL,
    lifecycle_labels,
    next_link,
)


NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def item(
    number,
    *,
    age_days=0,
    labels=(),
    pull_request=False,
    updated_at=None,
):
    result = {
        "number": number,
        "updated_at": (updated_at or NOW - timedelta(days=age_days))
        .isoformat()
        .replace("+00:00", "Z"),
        "labels": [{"name": label} for label in labels],
    }
    if pull_request:
        result["pull_request"] = {"url": "https://example.test/pull/1"}
    return result


class FakeClient:
    def __init__(self, items=(), label_times=None):
        self.items = list(items)
        self.label_times = label_times or {}
        self.calls = []

    def list_open_items(self):
        return self.items

    def latest_label_time(self, number, label):
        self.calls.append(("label_time", number, label))
        return self.label_times.get((number, label))

    def set_labels(self, number, labels):
        self.calls.append(("set_labels", number, labels))

    def comment(self, number, message):
        self.calls.append(("comment", number, message))

    def close(self, number):
        self.calls.append(("close", number))


class LifecycleProcessorTests(unittest.TestCase):
    def process(self, target, *, label_times=None, dry_run=False):
        client = FakeClient([target], label_times)
        result = LifecycleProcessor(client, NOW, dry_run=dry_run).run()
        return result, client.calls

    def test_marks_inactive_issue_stale(self):
        result, calls = self.process(item(1, age_days=30))

        self.assertEqual(result["stale"], 1)
        self.assertIn(("set_labels", 1, [STALE_LABEL]), calls)
        self.assertIn("This issue", calls[0][2])

    def test_marks_inactive_pull_request_stale(self):
        _, calls = self.process(item(2, age_days=31, pull_request=True))

        self.assertIn("This pull request", calls[0][2])
        self.assertIn(("set_labels", 2, [STALE_LABEL]), calls)

    def test_leaves_recent_item_unchanged(self):
        result, calls = self.process(item(3, age_days=29))

        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(calls, [])

    def test_advances_stale_item_to_rotten(self):
        labeled_at = NOW - timedelta(days=7)
        target = item(4, labels=(STALE_LABEL,), updated_at=labeled_at)
        result, calls = self.process(
            target,
            label_times={(4, STALE_LABEL): labeled_at},
        )

        self.assertEqual(result["rotten"], 1)
        self.assertIn(("set_labels", 4, [ROTTEN_LABEL]), calls)

    def test_keeps_stale_item_before_rotten_deadline(self):
        labeled_at = NOW - timedelta(days=6)
        target = item(12, labels=(STALE_LABEL,), updated_at=labeled_at)
        result, calls = self.process(
            target,
            label_times={(12, STALE_LABEL): labeled_at},
        )

        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(calls, [("label_time", 12, STALE_LABEL)])

    def test_closes_rotten_item(self):
        labeled_at = NOW - timedelta(days=7)
        target = item(5, labels=(ROTTEN_LABEL,), updated_at=labeled_at)
        result, calls = self.process(
            target,
            label_times={(5, ROTTEN_LABEL): labeled_at},
        )

        self.assertEqual(result["closed"], 1)
        self.assertEqual(calls[-1], ("close", 5))

    def test_activity_removes_stale_label(self):
        labeled_at = NOW - timedelta(days=8)
        target = item(
            6,
            labels=("area/docs", STALE_LABEL),
            updated_at=labeled_at + timedelta(hours=1),
        )
        result, calls = self.process(
            target,
            label_times={(6, STALE_LABEL): labeled_at},
        )

        self.assertEqual(result["reactivated"], 1)
        self.assertIn(("set_labels", 6, ["area/docs"]), calls)

    def test_activity_removes_rotten_label(self):
        labeled_at = NOW - timedelta(days=8)
        target = item(
            13,
            labels=("area/docs", ROTTEN_LABEL),
            updated_at=labeled_at + timedelta(minutes=1),
        )
        result, calls = self.process(
            target,
            label_times={(13, ROTTEN_LABEL): labeled_at},
        )

        self.assertEqual(result["reactivated"], 1)
        self.assertIn(("set_labels", 13, ["area/docs"]), calls)

    def test_missing_label_event_uses_item_update_time(self):
        target = item(14, age_days=7, labels=(STALE_LABEL,))
        result, calls = self.process(target)

        self.assertEqual(result["rotten"], 1)
        self.assertIn(("set_labels", 14, [ROTTEN_LABEL]), calls)

    def test_exempt_item_keeps_lifecycle_label(self):
        result, calls = self.process(
            item(7, age_days=60, labels=(STALE_LABEL, "lifecycle/frozen"))
        )

        self.assertEqual(result["exempt"], 1)
        self.assertEqual(calls, [])

    def test_single_scan_processes_each_lifecycle_stage(self):
        stale_at = NOW - timedelta(days=7)
        rotten_at = NOW - timedelta(days=8)
        client = FakeClient(
            [
                item(8, age_days=40),
                item(9, labels=(STALE_LABEL,), updated_at=stale_at),
                item(10, labels=(ROTTEN_LABEL,), updated_at=rotten_at),
            ],
            {
                (9, STALE_LABEL): stale_at,
                (10, ROTTEN_LABEL): rotten_at,
            },
        )

        results = LifecycleProcessor(client, NOW).run()

        self.assertEqual(results["stale"], 1)
        self.assertEqual(results["rotten"], 1)
        self.assertEqual(results["closed"], 1)

    def test_dry_run_makes_no_changes(self):
        result, calls = self.process(item(11, age_days=40), dry_run=True)

        self.assertEqual(result["stale"], 1)
        self.assertEqual(calls, [])


class HelperTests(unittest.TestCase):
    def test_lifecycle_labels_preserve_unrelated_labels(self):
        labels = lifecycle_labels(
            ["area/docs", STALE_LABEL, "priority/high"],
            ROTTEN_LABEL,
        )

        self.assertEqual(labels, ["area/docs", "priority/high", ROTTEN_LABEL])

    def test_next_link_selects_next_relation(self):
        header = (
            '<https://api.github.test/issues?page=2>; rel="next", '
            '<https://api.github.test/issues?page=4>; rel="last"'
        )

        self.assertEqual(
            next_link(header),
            "https://api.github.test/issues?page=2",
        )


if __name__ == "__main__":
    unittest.main()
