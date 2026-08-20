#!/usr/bin/env python3
"""
Test Plan Review — GitHub Action entry point.

Two modes:
  - score: score TestPlan.md against the 5-dimension rubric, post comment
  - respond: revise TestPlan.md based on PR review comments, commit + push
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from tp_hooks import TestPlanHooks
from tp_skill_config import build_skill_config


REPO = os.environ.get("GITHUB_REPOSITORY",
                       "osac-project/enhancement-proposals")
SKILLS_PATH = "/opt/test-plan-skills"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def gh(args):
    result = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        msg = f"gh {' '.join(args[:3])}... failed: {result.stderr[:300]}"
        if IN_CI:
            raise RuntimeError(msg)
        print(f"gh error: {msg}", file=sys.stderr)
    return result.stdout


def detect_ep_slug_from_branch(branch_name):
    if branch_name.startswith("test-plan/"):
        return branch_name.removeprefix("test-plan/")
    return None


def detect_ep_slug_from_files(pr_number):
    raw = gh(["api", f"repos/{REPO}/pulls/{pr_number}/files",
              "--paginate", "--jq", "[.[].filename]"])
    files = json.loads(raw) if raw.strip() else []
    pattern = re.compile(r"enhancements/([^/]+)/(?:TestPlan|testplan)\.md")
    for f in files:
        m = pattern.match(f)
        if m:
            return m.group(1)
    return None


def run_review(hooks, skill_name, skill_path, ticket_key, ticket, work_dir,
               pre_gates, post_gates):
    ticket = {**ticket, "_skill_name": skill_name, "_skill_path": skill_path}

    try:
        from agentic_ci.skill import run_skill

        config = build_skill_config(
            hooks=hooks,
            skill_name=skill_name,
            skills_path=SKILLS_PATH,
            pre_gates=pre_gates,
            post_gates=post_gates,
        )

        rc = run_skill(
            config,
            ticket_key=ticket_key,
            work_dir=work_dir,
            config_dir=Path("."),
            mode="resolve",
            ticket=ticket,
        )

        if skill_name == "test-plan-score":
            verdict_path = work_dir / "verdict.json"
            if verdict_path.exists():
                with open(verdict_path) as f:
                    v = json.load(f)
                total = v.get("total", 0)
                verdict_str = v.get("verdict", "unknown")
                print(f"  [{skill_name}] score={total}, "
                      f"verdict={verdict_str} (rc={rc})")
            else:
                print(f"  [{skill_name}] no verdict.json (rc={rc})")
        else:
            output = work_dir / "testplan-output.md"
            if output.exists():
                print(f"  [{skill_name}] Generated revised TestPlan.md "
                      f"({output.stat().st_size} bytes, rc={rc})")
            else:
                print(f"  [{skill_name}] No testplan-output.md (rc={rc})")

    except ImportError:
        if IN_CI:
            print("agentic-ci not installed in CI — this is a fatal error",
                  file=sys.stderr)
            sys.exit(1)
        print(f"  [{skill_name}] dry-run (agentic-ci not available)")
        hooks.write_context(
            ticket_key=ticket_key, ticket=ticket,
            mode="resolve", work_dir=work_dir,
        )


def main():
    pr_number = os.environ.get("PR_NUMBER")
    head_sha = os.environ.get("PR_HEAD_SHA", "")
    mode = os.environ.get("MODE", "score")
    shadow = os.environ.get("TP_SHADOW", "true").lower() == "true"

    if not pr_number:
        print("PR_NUMBER not set", file=sys.stderr)
        sys.exit(1)

    print(f"Test Plan Review — PR #{pr_number} (mode: {mode}, "
          f"sha: {head_sha[:8]})")
    if shadow:
        print("SHADOW MODE: will run but not post/commit")

    pr_raw = gh(["pr", "view", str(pr_number), "--repo", REPO,
                  "--json",
                  "number,title,body,author,labels,headRefOid,headRefName"])
    if not pr_raw.strip():
        print("Could not fetch PR details", file=sys.stderr)
        sys.exit(1)
    pr = json.loads(pr_raw)

    branch = pr.get("headRefName", "")
    ep_slug = detect_ep_slug_from_branch(branch)
    if not ep_slug:
        ep_slug = detect_ep_slug_from_files(pr_number)
    if not ep_slug:
        print("Could not detect EP slug — skipping")
        return

    live_sha = pr.get("headRefOid", "")
    if head_sha and live_sha and live_sha != head_sha:
        print(f"Stale run: PR head moved from {head_sha[:8]} to "
              f"{live_sha[:8]} — aborting")
        return

    print(f"EP slug: {ep_slug}, branch: {branch}")

    hooks = TestPlanHooks(
        repo=REPO,
        skills_path=SKILLS_PATH,
        shadow=shadow,
    )

    ticket = {
        "number": int(pr_number),
        "title": pr.get("title", ""),
        "body": pr.get("body", ""),
        "author": pr.get("author", {}).get("login", "unknown"),
        "headRefOid": pr.get("headRefOid", head_sha),
        "labels": [l.get("name", "") for l in pr.get("labels", [])],
        "_ep_slug": ep_slug,
    }

    if mode == "score":
        skill_name = "test-plan-score"
        skill_path = "skills/test-plan-score/SKILL.md"
        pre_gates = [hooks.check_already_scored]
        post_gates = [hooks.validate_scores]
    elif mode == "respond":
        skill_name = "test-plan-review"
        skill_path = "skills/test-plan-review/SKILL.md"
        pre_gates = []
        post_gates = []
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(1)

    ticket_key = f"TP-{pr_number}"
    work_dir = Path(f"workdir-{skill_name}")

    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(SKILLS_PATH, work_dir,
                    ignore=shutil.ignore_patterns('.git'))

    print(f"\nRunning {skill_name}...")
    try:
        run_review(hooks, skill_name, skill_path, ticket_key, ticket,
                   work_dir, pre_gates, post_gates)
    except Exception as e:
        print(f"  [{skill_name}] failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        if IN_CI:
            sys.exit(1)


if __name__ == "__main__":
    main()
