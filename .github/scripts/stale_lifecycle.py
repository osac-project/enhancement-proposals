#!/usr/bin/env python3
"""Advance inactive issues and pull requests through the stale lifecycle."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
STALE_LABEL = "lifecycle/stale"
ROTTEN_LABEL = "lifecycle/rotten"
EXEMPT_LABELS = frozenset(("lifecycle/frozen", "pinned"))
STALE_AFTER = timedelta(days=30)
ROTTEN_AFTER = timedelta(days=7)
CLOSE_AFTER = timedelta(days=7)
ACTIVITY_CLOCK_SKEW = timedelta(seconds=15)
RETRYABLE_STATUS_CODES = frozenset((429, 500, 502, 503, 504))
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def parse_timestamp(value: str) -> datetime:
    """Parse a GitHub timestamp into a timezone-aware datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def next_link(value: str | None) -> str | None:
    """Return the next page URL from a GitHub Link header."""
    if not value:
        return None
    for part in value.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="([^"]+)"', part)
        if match and match.group(2) == "next":
            return match.group(1)
    return None


class GitHubClient:
    """Small GitHub REST client for the lifecycle operations."""

    def __init__(self, token: str, repository: str) -> None:
        self.token = token
        self.repository = repository

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[Any, Any]:
        url = path if path.startswith("https://") else f"{API_ROOT}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "osac-stale-lifecycle",
            },
        )

        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    body = response.read()
                    result = json.loads(body) if body else None
                    return result, response.headers
            except HTTPError as error:
                if error.code not in RETRYABLE_STATUS_CODES or attempt == 2:
                    detail = error.read().decode(errors="replace")[:500]
                    raise RuntimeError(
                        f"GitHub API {method} {path} failed with "
                        f"HTTP {error.code}: {detail}"
                    ) from error
            except URLError as error:
                if attempt == 2:
                    raise RuntimeError(
                        f"GitHub API {method} {path} failed: {error.reason}"
                    ) from error
            time.sleep(2**attempt)

        raise AssertionError("retry loop exited unexpectedly")

    def _paginate(self, path: str) -> Iterable[dict[str, Any]]:
        next_page: str | None = path
        while next_page:
            result, headers = self._request("GET", next_page)
            if not isinstance(result, list):
                raise RuntimeError(f"Expected a list from GitHub API {next_page}")
            yield from result
            next_page = next_link(headers.get("Link"))

    def list_open_items(self) -> list[dict[str, Any]]:
        path = (
            f"/repos/{self.repository}/issues"
            "?state=open&per_page=100&sort=updated&direction=desc"
        )
        return list(self._paginate(path))

    def latest_label_time(self, number: int, label: str) -> datetime | None:
        path = f"/repos/{self.repository}/issues/{number}/events?per_page=100"
        timestamps = (
            parse_timestamp(event["created_at"])
            for event in self._paginate(path)
            if event.get("event") == "labeled"
            and event.get("label", {}).get("name", "").casefold()
            == label.casefold()
        )
        return max(timestamps, default=None)

    def set_labels(self, number: int, labels: list[str]) -> None:
        path = f"/repos/{self.repository}/issues/{number}"
        self._request("PATCH", path, {"labels": labels})

    def comment(self, number: int, message: str) -> None:
        path = f"/repos/{self.repository}/issues/{number}/comments"
        self._request("POST", path, {"body": message})

    def close(self, number: int) -> None:
        path = f"/repos/{self.repository}/issues/{number}"
        self._request(
            "PATCH",
            path,
            {"state": "closed", "state_reason": "not_planned"},
        )


def lifecycle_labels(labels: list[str], target: str | None) -> list[str]:
    """Replace lifecycle labels while preserving unrelated labels."""
    lifecycle = {STALE_LABEL.casefold(), ROTTEN_LABEL.casefold()}
    result = [label for label in labels if label.casefold() not in lifecycle]
    if target:
        result.append(target)
    return result


def stale_message(is_pull_request: bool) -> str:
    item = "pull request" if is_pull_request else "issue"
    short_item = "PR" if is_pull_request else "issue"
    activity = (
        "Add a comment, push a commit, or make an update"
        if is_pull_request
        else "Add a comment or make an update"
    )
    return f"""This {item} has been automatically labeled as `{STALE_LABEL}` because it has not had any activity for 30 days.

**Lifecycle timeline:**
- After 7 more days of inactivity, this {short_item} will be labeled `{ROTTEN_LABEL}`.
- After 14 more days of inactivity, this {short_item} will be automatically closed.

**To keep this {short_item} active:**
- {activity} to reset the lifecycle timer.
- The `{STALE_LABEL}` label will be automatically removed when activity is detected.

**To prevent automatic lifecycle management:**
- Apply the `lifecycle/frozen` label to this {short_item}.

Closed {short_item}s can be reopened at any time if they are still relevant."""


def rotten_message(is_pull_request: bool) -> str:
    item = "pull request" if is_pull_request else "issue"
    short_item = "PR" if is_pull_request else "issue"
    activity = (
        "Add a comment, push a commit, or make an update"
        if is_pull_request
        else "Add a comment or make an update"
    )
    return f"""This {item} has been automatically labeled as `{ROTTEN_LABEL}` because it has had no activity for 37+ days (30 days stale + 7 days without further activity).

**This {short_item} will be automatically closed in 7 days if no further activity occurs.**

**To keep this {short_item} open:**
- {activity} to reset the lifecycle timer.
- The `{ROTTEN_LABEL}` label will be automatically removed when activity is detected.

**To prevent automatic lifecycle management:**
- Apply the `lifecycle/frozen` label to this {short_item}.

Closed {short_item}s can be reopened at any time if they are still relevant."""


def close_message(is_pull_request: bool) -> str:
    item = "pull request" if is_pull_request else "issue"
    short_item = "PR" if is_pull_request else "issue"
    return f"""This {item} has been automatically closed after 44+ days of inactivity (30 days until stale, 7 days until rotten, 7 days until close).

If this {short_item} is still relevant, you can reopen it at any time. To prevent future automatic closure, apply the `lifecycle/frozen` label."""


class LifecycleProcessor:
    """Process every lifecycle stage in one scan without shared cursor state."""

    def __init__(
        self,
        client: GitHubClient,
        now: datetime,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.now = now
        self.dry_run = dry_run

    def run(self) -> Counter[str]:
        results: Counter[str] = Counter()
        for item in self.client.list_open_items():
            action = self.process_item(item)
            results[action] += 1
            if action not in ("unchanged", "exempt"):
                suffix = " (dry run)" if self.dry_run else ""
                print(f"#{item['number']}: {action}{suffix}")
        return results

    def process_item(self, item: dict[str, Any]) -> str:
        number = int(item["number"])
        updated_at = parse_timestamp(item["updated_at"])
        labels = [label["name"] for label in item.get("labels", [])]
        normalized = {label.casefold() for label in labels}
        is_pull_request = "pull_request" in item

        if normalized & EXEMPT_LABELS:
            return "exempt"
        if ROTTEN_LABEL.casefold() in normalized:
            return self._advance_labeled_item(
                number,
                labels,
                updated_at,
                ROTTEN_LABEL,
                CLOSE_AFTER,
                "closed",
                close_message(is_pull_request),
            )
        if STALE_LABEL.casefold() in normalized:
            return self._advance_labeled_item(
                number,
                labels,
                updated_at,
                STALE_LABEL,
                ROTTEN_AFTER,
                "rotten",
                rotten_message(is_pull_request),
            )
        if self.now - updated_at >= STALE_AFTER:
            self._comment_and_set_labels(
                number,
                stale_message(is_pull_request),
                lifecycle_labels(labels, STALE_LABEL),
            )
            return "stale"
        return "unchanged"

    def _advance_labeled_item(
        self,
        number: int,
        labels: list[str],
        updated_at: datetime,
        current_label: str,
        delay: timedelta,
        action: str,
        message: str,
    ) -> str:
        labeled_at = self.client.latest_label_time(number, current_label)
        transition_at = labeled_at or updated_at

        if updated_at > transition_at + ACTIVITY_CLOCK_SKEW:
            self._set_labels(number, lifecycle_labels(labels, None))
            return "reactivated"
        if self.now - transition_at < delay:
            return "unchanged"
        if action == "closed":
            self._comment_and_close(number, message)
        else:
            self._comment_and_set_labels(
                number,
                message,
                lifecycle_labels(labels, ROTTEN_LABEL),
            )
        return action

    def _set_labels(self, number: int, labels: list[str]) -> None:
        if not self.dry_run:
            self.client.set_labels(number, labels)

    def _comment_and_set_labels(
        self,
        number: int,
        message: str,
        labels: list[str],
    ) -> None:
        if not self.dry_run:
            # Apply the label last so the label event is the activity baseline.
            self.client.comment(number, message)
            self.client.set_labels(number, labels)

    def _comment_and_close(self, number: int, message: str) -> None:
        if not self.dry_run:
            self.client.comment(number, message)
            self.client.close(number)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN", "")
    repository = os.environ.get("TARGET_REPOSITORY", "")
    if not token:
        raise SystemExit("GH_TOKEN is required")
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise SystemExit("TARGET_REPOSITORY must be in owner/repository form")

    processor = LifecycleProcessor(
        GitHubClient(token, repository),
        datetime.now(timezone.utc),
        dry_run=args.dry_run,
    )
    results = processor.run()
    summary = ", ".join(
        f"{name}={count}" for name, count in sorted(results.items())
    )
    print(f"Lifecycle scan complete: {summary or 'no open items'}")


if __name__ == "__main__":
    main()
