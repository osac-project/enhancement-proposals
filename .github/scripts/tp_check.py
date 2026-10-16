#!/usr/bin/env python3
"""Publish the required check on the PR head, including setup failures.

Uses only the Python standard library so start/finish do not depend on model
packages or successful checkout of the skills and OSAC grounding sources.
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from tp_gate import PLAN_NAMES, DESIGN_NAMES, affected_enhancements, write_json

CHECK_NAME = "Test Plan Score"
STATE_PATH = Path(".test-plan-check.json")
REPORT_PATH = Path("test-plan-score/report.json")


def api(endpoint, *, method="GET", payload=None, optional=False):
    args = ["gh", "api", "-X", method, endpoint]
    with tempfile.TemporaryDirectory(prefix="tp-check-") as directory:
        if payload is not None:
            body = Path(directory) / "request.json"
            body.write_text(json.dumps(payload))
            args.extend(["--input", str(body)])
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode and optional and "HTTP 404" in result.stderr:
        return None
    if result.returncode:
        raise RuntimeError(f"GitHub check API failed (exit {result.returncode})")
    return json.loads(result.stdout)


def text(value):
    return (html.escape(str(value)).replace("@", "&#64;")
            .replace("|", "\\|").replace("\n", " ").replace("\r", " "))


def report_summary(report):
    rows = report.get("plans", [])
    lines = [f"### {CHECK_NAME}",
             f"Commit: `{report.get('head_sha', '')}`", ""]
    if rows:
        lines.extend(["| Plan | Score | Verdict | Feedback |",
                      "|------|-------|---------|----------|"])
        for row in rows:
            feedback = text(row.get("feedback") or row.get("summary", ""))[:2000]
            lines.append(f"| {text(row['path'])} | {text(row.get('total', '—'))} "
                         f"| {text(row['verdict'])} | {feedback} |")
    elif report.get("conclusion") == "success":
        lines.append("Not applicable: this PR changes no enhancement PRD, design or test plan.")
    if report.get("error"):
        lines.append("Failure: " + text(report["error"])[:2000])
    for key in ("skills_sha", "osac_sha"):
        if key in report:
            lines.append(f"{key}: `{report[key]}`")
    return "\n".join(lines)[:60_000]


def start(repo, head_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise RuntimeError("A full PR head SHA is required")
    response = api(f"repos/{repo}/check-runs", method="POST", payload={
        "name": CHECK_NAME, "head_sha": head_sha, "status": "in_progress",
        "details_url": f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        "output": {"title": CHECK_NAME, "summary": "Evaluating test-plan applicability and readiness."},
    })
    if type(response.get("id")) is not int:
        raise RuntimeError("GitHub did not return a check-run ID")
    write_json(STATE_PATH, {"id": response["id"], "head_sha": head_sha})


def prepare(repo, pr_number, head_sha):
    """Resolve applicability without model packages or cloud credentials."""
    pr = api(f"repos/{repo}/pulls/{pr_number}")
    if pr.get("head", {}).get("sha") != head_sha:
        raise RuntimeError("PR head changed before applicability detection")
    head_repo = (pr["head"].get("repo") or {}).get("full_name", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", head_repo):
        raise RuntimeError("PR head repository is unavailable")
    expected = pr.get("changed_files")
    if type(expected) is not int or expected > 3000:
        raise RuntimeError("Cannot obtain a complete changed-file listing")
    files = []
    for page in range(1, 31):
        batch = api(f"repos/{repo}/pulls/{pr_number}/files?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError("Invalid changed-file listing")
        files.extend(batch)
        if len(batch) < 100:
            break
    if len(files) != expected:
        raise RuntimeError("Incomplete changed-file listing")
    rows = []
    needs_review = False
    for slug in affected_enhancements(files):
        base = f"enhancements/{slug}"
        entries = api(
            f"repos/{head_repo}/contents/{quote(base, safe='/')}?ref={head_sha}",
            optional=True,
        )
        if entries is not None and (not isinstance(entries, list) or len(entries) >= 1000):
            raise RuntimeError("Cannot obtain complete enhancement contents")
        if entries is None and any(
            file.get("filename", "").startswith(base + "/")
            and file.get("status") != "removed" for file in files
        ):
            raise RuntimeError("Changed enhancement is unavailable at the PR head")
        names = {item["name"] for item in (entries or [])}
        plan_changed = any(
            file.get(key) in {f"{base}/{name}" for name in PLAN_NAMES}
            for file in files for key in ("filename", "previous_filename")
        )
        if names.intersection(PLAN_NAMES):
            needs_review = True
        elif names.intersection(DESIGN_NAMES) or (plan_changed and entries is not None):
            rows.append({"path": base, "verdict": "Error", "summary": "Required test plan is missing"})
        else:
            rows.append({"path": base, "verdict": "Not applicable", "summary": "PRD-only work or enhancement removed in full"})
    report = {"head_sha": head_sha, "plans": rows, "conclusion": "failure"}
    if not needs_review and all(row["verdict"] == "Not applicable" for row in rows):
        report["conclusion"] = "success"
    write_json(REPORT_PATH, report)
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"needs_review={str(needs_review).lower()}\n")


def finish(repo, pr_number, job_status):
    state = json.loads(STATE_PATH.read_text())
    report = {"head_sha": state["head_sha"], "conclusion": "failure",
              "error": "Review did not complete; inspect the workflow setup or model failure."}
    if REPORT_PATH.exists():
        try:
            candidate = json.loads(REPORT_PATH.read_text())
            if not isinstance(candidate, dict) or not isinstance(candidate.get("plans", []), list):
                raise ValueError("Invalid aggregate report")
            report = candidate
        except (OSError, ValueError):
            report["error"] = "Review produced an invalid aggregate report."
    try:
        live_pr = api(f"repos/{repo}/pulls/{pr_number}")
        current = live_pr.get("head", {}).get("sha")
    except RuntimeError:
        current = state["head_sha"]
        report["conclusion"] = "failure"
        report["error"] = "Could not verify the current PR head."
    conclusion = "failure"
    if current != state["head_sha"]:
        conclusion = "cancelled"
        report["error"] = "PR head changed; this result cannot authorize the new commit."
    elif (job_status == "success" and report.get("head_sha") == state["head_sha"]
          and report.get("conclusion") == "success" and not report.get("error")):
        conclusion = "success"
    elif job_status != "success":
        report["error"] = "Workflow did not complete successfully; inspect its failed steps."
    api(f"repos/{repo}/check-runs/{state['id']}", method="PATCH", payload={
        "status": "completed", "conclusion": conclusion,
        "output": {"title": CHECK_NAME, "summary": report_summary(report)},
    })
    return 0 if conclusion == "success" else 1


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    if sys.argv[1] == "start":
        start(repo, os.environ["PR_HEAD_SHA"])
    elif sys.argv[1] == "prepare":
        prepare(repo, os.environ["PR_NUMBER"], os.environ["PR_HEAD_SHA"])
    elif sys.argv[1] == "finish":
        return finish(repo, os.environ["PR_NUMBER"], os.environ["REVIEW_JOB_STATUS"])
    else:
        raise RuntimeError("Expected start, prepare or finish")


if __name__ == "__main__":
    sys.exit(main())
