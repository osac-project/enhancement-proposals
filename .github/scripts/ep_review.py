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


REPO = "osac-project/enhancement-proposals"
SKILLS_PATH = "/opt/skills"


def gh(args):
    result = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"gh error: {result.stderr[:300]}", file=sys.stderr)
    return result.stdout


def get_changed_files(pr_number):
    raw = gh(["api", f"repos/{REPO}/pulls/{pr_number}/files",
              "--paginate", "--jq", "[.[].filename]"])
    return json.loads(raw) if raw.strip() else []


def detect_skill(files):
    has_prd = any(f.endswith("prd.md") for f in files)
    has_design = any(f.endswith("design.md") for f in files)

    if has_prd:
        return "prd-review", "skills/prd-review/SKILL.md"
    if has_design:
        return "ep-review", "skills/ep-review/SKILL.md"
    return None, None


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

    files = get_changed_files(pr_number)
    if not files:
        print("No files changed in PR")
        return

    skill_name, skill_path = detect_skill(files)
    if not skill_name:
        print("No prd.md or design.md found in changed files — skipping")
        return

    print(f"Detected: {skill_name} (from {', '.join(f for f in files if f.endswith('.md'))})")

    pr_raw = gh(["pr", "view", str(pr_number), "--repo", REPO,
                  "--json", "number,title,body,author,labels,headRefOid"])
    if not pr_raw.strip():
        print("Could not fetch PR details", file=sys.stderr)
        sys.exit(1)
    pr = json.loads(pr_raw)

    ticket_key = f"EP-{pr_number}"
    work_dir = Path("workdir")
    work_dir.mkdir(parents=True, exist_ok=True)

    ticket = {
        "number": int(pr_number),
        "title": pr.get("title", ""),
        "body": pr.get("body", ""),
        "author": pr.get("author", {}).get("login", "unknown"),
        "authorAssociation": "MEMBER",
        "headRefOid": pr.get("headRefOid", head_sha),
        "labels": [l.get("name", "") for l in pr.get("labels", [])],
        "_skill_name": skill_name,
        "_skill_path": skill_path,
    }

    hooks = EPHooks(
        repo=REPO,
        skills_path=SKILLS_PATH,
        shadow=shadow,
        bot_login="github-actions[bot]",
        reviewed_label="rfe-creator-auto-reviewed",
    )

    try:
        from agentic_ci.skill import run_skill

        config = build_skill_config(
            hooks=hooks,
            skill_name=skill_name,
            skills_path=SKILLS_PATH,
            skill_path=skill_path,
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
            print(f"Review complete: score={total}, verdict={verdict_str} (rc={rc})")
        else:
            print(f"Review completed but no verdict.json found (rc={rc})")

    except ImportError:
        print("agentic-ci not available — running in dry-run mode")
        hooks.write_pr_context(
            ticket_key=ticket_key, ticket=ticket,
            mode="resolve", work_dir=work_dir,
        )
        print(f"Context written to {work_dir}/.context/")

    except Exception as e:
        print(f"Review failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
