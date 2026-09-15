"""Shared helpers for finding and updating bot-owned pull-request comments."""

import json
import os
import tempfile


def _newer(candidate, current):
    if current is None:
        return candidate
    if candidate.get("created_at", "") > current.get("created_at", ""):
        return candidate
    return current


def find_bot_comment(
    gh, repo, pr_number, bot_login, marker, *, include_body=True,
    fallback_prefix=None,
):
    """Return the newest marked bot comment, or an optional legacy match.

    Let ``gh`` handle pagination and have jq emit only one small metadata
    record per match type per page. A fallback is selected only when no marked
    comment exists across the complete result. The selected comment body is
    fetched only when the caller needs it; ID-only callers avoid the extra API
    request.
    """
    bot = json.dumps(bot_login)
    marker_json = json.dumps(marker)
    fallback_json = json.dumps(fallback_prefix) if fallback_prefix else None
    fallback_branch = (
        f'elif ((.body // "") | startswith({fallback_json})) then '
        '{id, user, created_at, candidate_kind: "fallback"} '
        if fallback_json else ""
    )
    jq_filter = (
        f'[.[] | select(.user.login == {bot}) | '
        f'if ((.body // "") | contains({marker_json})) then '
        '{id, user, created_at, candidate_kind: "preferred"} '
        f'{fallback_branch}else empty end] | '
        'group_by(.candidate_kind)[] | max_by(.created_at) | @json'
    )

    raw = gh([
        "api", f"repos/{repo}/issues/{pr_number}/comments?per_page=100",
        "--paginate", "--jq", jq_filter,
    ], check=True)
    preferred = None
    fallback = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GitHub returned invalid comment JSON") from exc
        if not isinstance(candidate, dict):
            raise RuntimeError("GitHub returned an unexpected comment response")
        if (candidate.get("user") or {}).get("login") != bot_login:
            continue
        if candidate.get("candidate_kind") == "preferred":
            preferred = _newer(candidate, preferred)
        elif candidate.get("candidate_kind") == "fallback":
            fallback = _newer(candidate, fallback)

    selected = preferred or fallback
    if not selected:
        return None
    if not include_body:
        return selected

    raw = gh([
        "api", f"repos/{repo}/issues/comments/{selected['id']}",
        "--jq", "{id, user, body, created_at} | @json",
    ], check=True)
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            comment = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GitHub returned invalid comment JSON") from exc
        if not isinstance(comment, dict):
            raise RuntimeError("GitHub returned an unexpected comment response")
        if (comment.get("user") or {}).get("login") == bot_login:
            return comment
    return None


def write_comment(gh, repo, pr_number, body, comment_id=None):
    """PATCH ``comment_id`` or create a PR comment, then remove the temp file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        comment_file = f.name

    try:
        if comment_id is not None:
            gh([
                "api", "--method", "PATCH",
                f"repos/{repo}/issues/comments/{comment_id}",
                "-F", f"body=@{comment_file}",
            ], check=True)
        else:
            gh([
                "pr", "comment", pr_number, "--repo", repo,
                "--body-file", comment_file,
            ], check=True)
    finally:
        os.unlink(comment_file)

    return comment_id is not None
