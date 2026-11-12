#!/usr/bin/env python3

from datetime import datetime, timedelta, timezone
import unittest

from stale_lifecycle import (
    GitHubClient,
    LabelActivity,
    LifecycleProcessor,
    ROTTEN_LABEL,
    STALE_LABEL,
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
        "state": "open",
    }
    if pull_request:
        result["pull_request"] = {"url": "https://example.test/pull/1"}
    return result


class FakeClient:
    def __init__(
        self,
        items=(),
        label_times=None,
        user_activity=None,
        automation_times=None,
        current_items=None,
        fail_add_labels=None,
    ):
        self.items = list(items)
        self.label_times = label_times or {}
        self.user_activity = user_activity or set()
        self.automation_times = automation_times or {}
        self.current_items = current_items or {
            target["number"]: target for target in self.items
        }
        self.fail_add_labels = fail_add_labels or set()
        self.calls = []

    def list_open_items(self):
        return self.items

    def get_item(self, number):
        self.calls.append(("get_item", number))
        return self.current_items[number]

    def label_activity(self, number, label):
        self.calls.append(("label_activity", number, label))
        labeled_at = self.label_times.get((number, label))
        automated_at = self.automation_times.get((number, label), labeled_at)
        return LabelActivity(
            labeled_at,
            automated_at,
            (number, label) in self.user_activity,
        )

    def add_label(self, number, label):
        self.calls.append(("add_label", number, label))
        if label in self.fail_add_labels:
            raise RuntimeError("label request failed")

    def remove_label(self, number, label):
        self.calls.append(("remove_label", number, label))

    def comment(self, number, message):
        self.calls.append(("comment", number, message))

    def close(self, number):
        self.calls.append(("close", number))


class LifecycleProcessorTests(unittest.TestCase):
    def process(
        self,
        target,
        *,
        label_times=None,
        user_activity=None,
        automation_times=None,
        current_items=None,
        fail_add_labels=None,
        dry_run=False,
    ):
        client = FakeClient(
            [target],
            label_times,
            user_activity,
            automation_times,
            current_items,
            fail_add_labels,
        )
        result = LifecycleProcessor(client, NOW, dry_run=dry_run).run()
        return result, client.calls

    def test_marks_inactive_issue_stale(self):
        result, calls = self.process(item(1, age_days=30))

        self.assertEqual(result["stale"], 1)
        self.assertIn(("add_label", 1, STALE_LABEL), calls)
        self.assertIn("This issue", calls[0][2])

    def test_marks_inactive_pull_request_stale(self):
        _, calls = self.process(item(2, age_days=31, pull_request=True))

        self.assertIn("This pull request", calls[0][2])
        self.assertIn(("add_label", 2, STALE_LABEL), calls)

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
        add_index = calls.index(("add_label", 4, ROTTEN_LABEL))
        remove_index = calls.index(("remove_label", 4, STALE_LABEL))
        self.assertLess(add_index, remove_index)

    def test_failed_rotten_label_keeps_stale_label_for_retry(self):
        labeled_at = NOW - timedelta(days=7)
        target = item(19, labels=(STALE_LABEL,), updated_at=labeled_at)
        client = FakeClient(
            [target],
            {(19, STALE_LABEL): labeled_at},
            fail_add_labels={ROTTEN_LABEL},
        )

        with self.assertRaisesRegex(RuntimeError, "label request failed"):
            LifecycleProcessor(client, NOW).run()

        # add_label fails before remove_label can remove the retryable stage.
        self.assertNotIn(("remove_label", 19, STALE_LABEL), client.calls)
        self.assertFalse(any(call[0] == "comment" for call in client.calls))

    def test_keeps_stale_item_before_rotten_deadline(self):
        labeled_at = NOW - timedelta(days=6)
        target = item(12, labels=(STALE_LABEL,), updated_at=labeled_at)
        result, calls = self.process(
            target,
            label_times={(12, STALE_LABEL): labeled_at},
        )

        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(calls, [("label_activity", 12, STALE_LABEL)])

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
        self.assertIn(("remove_label", 6, STALE_LABEL), calls)

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
        self.assertIn(("remove_label", 13, ROTTEN_LABEL), calls)

    def test_user_activity_within_skew_reactivates_stale_item(self):
        labeled_at = NOW - timedelta(days=7)
        target = item(
            15,
            labels=(STALE_LABEL,),
            updated_at=labeled_at + timedelta(seconds=10),
        )
        result, calls = self.process(
            target,
            label_times={(15, STALE_LABEL): labeled_at},
            user_activity={(15, STALE_LABEL)},
        )

        self.assertEqual(result["reactivated"], 1)
        self.assertIn(("remove_label", 15, STALE_LABEL), calls)

    def test_user_activity_within_skew_prevents_rotten_item_closure(self):
        labeled_at = NOW - timedelta(days=7)
        target = item(
            16,
            labels=(ROTTEN_LABEL,),
            updated_at=labeled_at + timedelta(seconds=10),
        )
        result, calls = self.process(
            target,
            label_times={(16, ROTTEN_LABEL): labeled_at},
            user_activity={(16, ROTTEN_LABEL)},
        )

        self.assertEqual(result["reactivated"], 1)
        self.assertIn(("remove_label", 16, ROTTEN_LABEL), calls)
        self.assertNotIn(("close", 16), calls)

    def test_missing_label_event_uses_item_update_time(self):
        target = item(14, age_days=7, labels=(STALE_LABEL,))
        result, calls = self.process(target)

        self.assertEqual(result["rotten"], 1)
        self.assertIn(("add_label", 14, ROTTEN_LABEL), calls)

    def test_changed_labels_prevent_closure(self):
        labeled_at = NOW - timedelta(days=7)
        scanned = item(17, labels=(ROTTEN_LABEL,), updated_at=labeled_at)
        current = item(
            17,
            labels=(ROTTEN_LABEL, "lifecycle/frozen"),
            updated_at=labeled_at,
        )
        result, calls = self.process(
            scanned,
            label_times={(17, ROTTEN_LABEL): labeled_at},
            current_items={17: current},
        )

        self.assertEqual(result["changed"], 1)
        self.assertNotIn(("close", 17), calls)

    def test_changed_activity_prevents_closure(self):
        labeled_at = NOW - timedelta(days=7)
        scanned = item(18, labels=(ROTTEN_LABEL,), updated_at=labeled_at)
        current = item(
            18,
            labels=(ROTTEN_LABEL,),
            updated_at=labeled_at + timedelta(seconds=1),
        )
        result, calls = self.process(
            scanned,
            label_times={(18, ROTTEN_LABEL): labeled_at},
            current_items={18: current},
        )

        self.assertEqual(result["changed"], 1)
        self.assertNotIn(("close", 18), calls)

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
    def test_timeline_commit_without_created_at_counts_as_activity(self):
        client = GitHubClient("token", "owner/repository")
        client._paginate = lambda _path: iter(
            [
                {
                    "event": "labeled",
                    "created_at": "2026-11-01T00:00:00Z",
                    "label": {"name": STALE_LABEL},
                    "actor": {"type": "Bot"},
                },
                {
                    "event": "committed",
                    "author": {"name": "Contributor"},
                },
            ]
        )

        activity = client.label_activity(1, STALE_LABEL)

        self.assertTrue(activity.user_activity)

    def test_bot_review_submitted_at_updates_automation_clock(self):
        client = GitHubClient("token", "owner/repository")
        client._paginate = lambda _path: iter(
            [
                {
                    "event": "labeled",
                    "created_at": "2026-11-01T00:00:00Z",
                    "label": {"name": STALE_LABEL},
                    "actor": {"type": "Bot"},
                },
                {
                    "event": "reviewed",
                    "submitted_at": "2026-11-01T00:01:00Z",
                    "user": {"type": "Bot"},
                },
            ]
        )

        activity = client.label_activity(1, STALE_LABEL)

        self.assertFalse(activity.user_activity)
        self.assertEqual(
            activity.latest_automation_at,
            datetime(2026, 11, 1, 0, 1, tzinfo=timezone.utc),
        )

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
