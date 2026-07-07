#!/usr/bin/env python3
"""
EP Review — GitHub Action entry point.

Detects which file type changed in the PR (prd.md or design.md),
runs the appropriate review skill via agentic-ci, and posts a
structured review comment on the PR.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from ep_hooks import EPHooks
from ep_skill_config import build_skill_config


REPO = os.environ.get("GITHUB_REPOSITORY", "osac-project/enhancement-proposals")
SKILLS_PATH = "/opt/skills"
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


def get_changed_files(pr_number):
    raw = gh(["api", f"repos/{REPO}/pulls/{pr_number}/files",
              "--paginate", "--jq", "[.[].filename]"])
    return json.loads(raw) if raw.strip() else []


def get_incremental_files(before_sha, head_sha):
    raw = gh(["api", f"repos/{REPO}/compare/{before_sha}...{head_sha}",
              "--jq", "[.files[].filename]"])
    return json.loads(raw) if raw.strip() else []


def detect_skills(files):
    skills = []
    has_prd = any(f.lower().endswith("prd.md") for f in files)
    has_design = any(
        f.lower().endswith("design.md") or
        (f.lower().endswith("readme.md") and "enhancements/" in f.lower())
        for f in files
    )

    if has_prd:
        skills.append(("prd-review", "skills/prd-review/SKILL.md"))
    if has_design:
        skills.append(("ep-review", "skills/ep-review/SKILL.md"))
    return skills


def run_review(hooks, skill_name, skill_path, ticket_key, ticket, work_dir):
    ticket = {**ticket, "_skill_name": skill_name, "_skill_path": skill_path}

    try:
        from agentic_ci.skill import run_skill

        config = build_skill_config(
            hooks=hooks,
            skill_name=skill_name,
            skills_path=SKILLS_PATH,
        )

        rc = run_skill(
            config,
            ticket_key=ticket_key,
            work_dir=work_dir,
            config_dir=Path("."),
            mode="resolve",
            ticket=ticket,
        )

        verdict_path = work_dir / "verdict.json"
        if verdict_path.exists():
            with open(verdict_path) as f:
                v = json.load(f)
            total = v.get("total", 0)
            verdict_str = v.get("verdict", "unknown")
            print(f"  [{skill_name}] score={total}, verdict={verdict_str} (rc={rc})")
        else:
            print(f"  [{skill_name}] no verdict.json (rc={rc})")

    except ImportError:
        if IN_CI:
            print("agentic-ci not installed in CI — this is a fatal error",
                  file=sys.stderr)
            sys.exit(1)
        print(f"  [{skill_name}] dry-run (agentic-ci not available)")
        hooks.write_pr_context(
            ticket_key=ticket_key, ticket=ticket,
            mode="resolve", work_dir=work_dir,
        )


def main():
    pr_number = os.environ.get("PR_NUMBER")
    head_sha = os.environ.get("PR_HEAD_SHA", "")
    shadow = os.environ.get("EP_REVIEW_SHADOW", "true").lower() == "true"

    if not pr_number:
        print("PR_NUMBER not set", file=sys.stderr)
        sys.exit(1)

    print(f"EP Review Action — PR #{pr_number} (sha: {head_sha[:8]})")
    if shadow:
        print("SHADOW MODE: review will run but no comment will be posted")

    event_name = os.environ.get("EVENT_NAME", "")
    event_action = os.environ.get("EVENT_ACTION", "")
    before_sha = os.environ.get("EVENT_BEFORE_SHA", "")

    # For synchronize events, only review files changed in the latest push
    if event_action == "synchronize" and before_sha and head_sha:
        files = get_incremental_files(before_sha, head_sha)
        print(f"Synchronize: checking incremental diff ({before_sha[:8]}..{head_sha[:8]})")
    else:
        files = get_changed_files(pr_number)

    if not files:
        print("No files changed")
        return

    skills = detect_skills(files)
    if not skills:
        print("No reviewable docs found in changed files — skipping")
        return

    print(f"Detected: {', '.join(s[0] for s in skills)} "
          f"(from {', '.join(f for f in files if f.lower().endswith('.md'))})")

    pr_raw = gh(["pr", "view", str(pr_number), "--repo", REPO,
                  "--json", "number,title,body,author,labels,headRefOid"])
    if not pr_raw.strip():
        print("Could not fetch PR details", file=sys.stderr)
        sys.exit(1)
    pr = json.loads(pr_raw)

    live_sha = pr.get("headRefOid", "")
    if head_sha and live_sha and live_sha != head_sha:
        print(f"Stale run: PR head moved from {head_sha[:8]} to {live_sha[:8]} — aborting")
        return

    hooks = EPHooks(
        repo=REPO,
        skills_path=SKILLS_PATH,
        shadow=shadow,
        bot_login="github-actions[bot]",
        reviewed_label="rfe-creator-auto-reviewed",
    )

    ticket_base = {
        "number": int(pr_number),
        "title": pr.get("title", ""),
        "body": pr.get("body", ""),
        "author": pr.get("author", {}).get("login", "unknown"),
        "authorAssociation": "MEMBER",
        "headRefOid": pr.get("headRefOid", head_sha),
        "labels": [l.get("name", "") for l in pr.get("labels", [])],
    }

    for skill_name, skill_path in skills:
        ticket_key = f"EP-{pr_number}"
        work_dir = Path(f"workdir-{skill_name}")
        work_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nRunning {skill_name}...")
        try:
            run_review(hooks, skill_name, skill_path, ticket_key, ticket_base, work_dir)
        except Exception as e:
            print(f"  [{skill_name}] failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            if IN_CI:
                sys.exit(1)


if __name__ == "__main__":
    main()
