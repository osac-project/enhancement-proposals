#!/usr/bin/env python3
"""Validate that new enhancement directories reference a Jira Feature.

Prints one JSON object on stdout:

    {"state": "success|failure|neutral", "description": "..."}

The workflow posts that object as the ``ep-jira-type`` commit status on the
pull request head commit. A non-zero exit is treated by the workflow as
``neutral`` so a crash can never leave a required check pending.

Only directories new to the pull request are validated, using the same
grandfathering rules as ``check_ep_naming.py``. The changed file list comes
from the GitHub API; no pull request code is checked out or executed.
"""

import json
import os
import subprocess
import sys

import requests

import ep_paths
from check_ep_naming import is_grandfathered, ref_exists

PROJECT_KEY = "OSAC"
DEFAULT_JIRA_URL = "https://redhat.atlassian.net"
TIMEOUT_SECONDS = 10
DESCRIPTION_MAX = 140

MISSING_CREDENTIALS = {
    "state": "neutral",
    "description": "Jira credentials are not configured; type not verified",
}
UNRESOLVED_BASE = {
    "state": "neutral",
    "description": "No usable PR base reference; cannot tell new paths from existing ones",
}
UNREACHABLE = {
    "state": "neutral",
    "description": "Could not read the OSAC project in Jira",
}


class CredentialsMissing(Exception):
    """Raised when the Jira credential is absent from the environment."""


def enhancement_dirs(files):
    """Return sorted (directory_name, jira_key) for each enhancement
    directory touched by the changed files.

    Any file counts, not just prd.md/design.md: a new directory must not
    escape validation by containing only, say, ui-design.md. Directories
    that already exist are removed later by grandfathering, so editing an
    established enhancement stays free.
    """
    found = {}
    for path in files:
        dir_name = ep_paths.top_level_enhancement_dir(path)
        if dir_name is None:
            continue
        match = ep_paths.KEY_RE.match(dir_name)
        if match:
            found[dir_name] = match.group(1)
    return sorted(found.items())


def changed_files(repo, pr_number):
    """File names changed by the pull request, read through the API."""
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/pulls/{pr_number}/files",
            "--jq",
            ".[].filename",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def jira_get(path, params=None):
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        raise CredentialsMissing()
    base = os.environ.get("JIRA_BASE_URL", DEFAULT_JIRA_URL)
    return requests.get(
        f"{base}{path}",
        params=params,
        auth=(email, token),
        timeout=TIMEOUT_SECONDS,
    )


def feature_verdict(key):
    """Return (state, description) for one Jira issue key."""
    response = jira_get(f"/rest/api/3/issue/{key}", {"fields": "issuetype"})
    if response.status_code == 404:
        return "failure", f"{key} does not exist in Jira or is not visible to CI"
    if response.status_code != 200:
        return "neutral", f"Jira returned HTTP {response.status_code} for {key}"
    issue_type = (
        response.json().get("fields", {}).get("issuetype", {}).get("name", "")
    )
    if issue_type.lower() != "feature":
        return (
            "failure",
            f"{key} is a {issue_type or 'unknown issue type'}, not a Feature",
        )
    return "success", f"{key} is a Feature"


def evaluate(files, base_sha, live_base_ref):
    """Return {"state": ..., "description": ...} for the changed file list."""
    directories = enhancement_dirs(files)
    if not directories:
        return {
            "state": "success",
            "description": "No enhancement directory in this pull request",
        }

    new_directories = [
        (dir_name, key)
        for dir_name, key in directories
        if not is_grandfathered(
            f"enhancements/{dir_name}", base_sha, live_base_ref
        )
    ]
    if not new_directories:
        return {
            "state": "success",
            "description": "Enhancement directories already exist; not re-validated",
        }

    try:
        probe = jira_get(f"/rest/api/3/project/{PROJECT_KEY}")
    except CredentialsMissing:
        return MISSING_CREDENTIALS
    except requests.RequestException:
        return UNREACHABLE
    if probe.status_code != 200:
        return UNREACHABLE

    for _, key in new_directories:
        try:
            state, description = feature_verdict(key)
        except CredentialsMissing:
            return MISSING_CREDENTIALS
        except requests.RequestException:
            return {
                "state": "neutral",
                "description": f"Could not reach Jira to check {key}",
            }
        if state != "success":
            return {"state": state, "description": description}

    keys = [key for _, key in new_directories]
    if len(keys) == 1:
        return {"state": "success", "description": f"{keys[0]} is a Feature"}
    return {
        "state": "success",
        "description": f"{', '.join(keys)} are Features",
    }


def sanitize(description):
    text = " ".join(str(description).split())
    return text[:DESCRIPTION_MAX]


def resolve_refs():
    """Return (base_sha, live_base_ref) that actually resolve in this clone."""
    base_sha = os.environ.get("PR_BASE_SHA") or None
    live_base_ref = os.environ.get("LIVE_BASE_REF") or None
    if base_sha is not None and not ref_exists(base_sha):
        base_sha = None
    if live_base_ref is not None and not ref_exists(live_base_ref):
        live_base_ref = None
    return base_sha, live_base_ref


def main():
    repo = os.environ.get("REPO", "")
    pr_number = os.environ.get("PR_NUMBER", "")
    base_sha, live_base_ref = resolve_refs()
    if base_sha is None and live_base_ref is None:
        result = UNRESOLVED_BASE
    else:
        files = changed_files(repo, pr_number)
        result = evaluate(files, base_sha, live_base_ref)
    print(
        json.dumps(
            {
                "state": result["state"],
                "description": sanitize(result["description"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
