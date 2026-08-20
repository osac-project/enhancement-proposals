#!/usr/bin/env python3
"""
EP Review — GitHub Action entry point.

Detects which file type changed in the PR (prd.md or design.md),
runs the appropriate review skill via agentic-ci, and posts a
structured review comment on the PR.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import ep_classify
import ep_paths
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
    """Return the full per-file detail (filename, status, previous_filename,
    patch, additions, deletions, changes) for every file changed in the PR —
    the raw shape the GitHub "pulls/*/files" API already returns, just no
    longer narrowed to filenames only. ep_classify.classify_logistics_only
    needs status/patch; Phase A's filename-only consumers (detect_skills,
    ep_paths, pr_enhancement_slugs) get a `[f["filename"] for f in files]`
    view instead — see filenames_only() below.

    Emitting one JSON object per line (rather than a single array) lets
    --paginate's multiple pages concatenate safely without needing --slurp.
    """
    raw = gh(["api", f"repos/{REPO}/pulls/{pr_number}/files",
              "--paginate", "--jq",
              ".[] | {filename, status, previous_filename, patch, "
              "additions, deletions, changes}"])
    files = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            files.append(json.loads(line))
    return files


def filenames_only(files):
    return [f["filename"] for f in files]


def detect_skills(files):
    skills = []
    basenames = [os.path.basename(f).lower() for f in files]
    has_prd = "prd.md" in basenames
    has_design = "design.md" in basenames or any(
        os.path.basename(f).lower() == "readme.md" and "enhancements/" in f.lower()
        for f in files
    )

    if has_prd:
        skills.append(("prd-review", "skills/prd-review/SKILL.md"))
    if has_design:
        skills.append(("design-review", "skills/design-review/SKILL.md"))
    return skills


def pr_enhancement_slugs(files):
    """Extract enhancements/<slug>/ directories touched by this PR."""
    slugs = set()
    for f in files:
        m = re.match(r"enhancements/([^/]+)/", f)
        if m:
            slugs.add(m.group(1))
    return slugs


def exclude_own_slug_from_reference_library(work_dir, files):
    """Remove this PR's own enhancement directory from the staged
    enhancement-proposals/enhancements/ reference library.

    design-review's "Comparison with Similar Designs" step treats
    enhancements/ as a library of *merged* designs to calibrate against.
    If this PR updates an existing enhancement, the pre-PR version of that
    same document would otherwise sit in the reference library right
    alongside .context/pr-diff.txt's new version, and could get cited as a
    "similar past design" — a stale ghost of the very document under
    review, not a real precedent.
    """
    ref_root = Path(work_dir) / "enhancement-proposals" / "enhancements"
    if not ref_root.exists():
        return
    for slug in pr_enhancement_slugs(files):
        slug_dir = ref_root / slug
        if slug_dir.exists():
            shutil.rmtree(slug_dir)


def build_ticket_base(pr, head_sha, pr_number, files):
    """Build the base ticket dict shared by every skill run for this PR.

    jira_key/jira_key_ambiguous/structure_violations are derived only from
    the changed-file paths (ep_paths), never from pr title/body — see
    OSAC-3416 design decision on Jira-key derivation.
    """
    feature_key_result = ep_paths.derive_feature_key(files)

    return {
        "number": int(pr_number),
        "title": pr.get("title", ""),
        "body": pr.get("body", ""),
        "author": pr.get("author", {}).get("login", "unknown"),
        "authorAssociation": "MEMBER",
        "headRefOid": pr.get("headRefOid", head_sha),
        "labels": [l.get("name", "") for l in pr.get("labels", [])],
        "jira_key": feature_key_result if feature_key_result != "ambiguous" else None,
        "jira_key_ambiguous": feature_key_result == "ambiguous",
        "structure_violations": ep_paths.validate_ep_structure(files),
    }


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
    skip_logistics = os.environ.get("EP_REVIEW_SKIP_LOGISTICS", "false").lower() == "true"

    if not pr_number:
        print("PR_NUMBER not set", file=sys.stderr)
        sys.exit(1)

    print(f"EP Review Action — PR #{pr_number} (sha: {head_sha[:8]})")
    if shadow:
        print("SHADOW MODE: review will run but no comment will be posted")

    files = get_changed_files(pr_number)

    if not files:
        print("No files changed")
        return

    filenames = filenames_only(files)

    skills = detect_skills(filenames)
    if not skills:
        print("No reviewable docs found in changed files — skipping")
        return

    print(f"Detected: {', '.join(s[0] for s in skills)} "
          f"(from {', '.join(f for f in filenames if f.lower().endswith('.md'))})")

    logistics_verdict = ep_classify.classify_logistics_only(files)
    if skip_logistics:
        print(f"Logistics classification: {logistics_verdict}")
    else:
        print(f"Logistics classification: {logistics_verdict} "
              "(EP_REVIEW_SKIP_LOGISTICS is off — full review still runs)")

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

    ticket_base = build_ticket_base(pr, head_sha, pr_number, filenames)

    for skill_name, skill_path in skills:
        ticket_key = f"EP-{pr_number}"

        if skip_logistics and logistics_verdict == ep_classify.LOGISTICS_ONLY:
            print(f"\n[{skill_name}] LOGISTICS_ONLY — skipping full review")
            hooks.apply_logistics_comment(ticket_key, ticket_base, skill_name)
            continue

        work_dir = Path(f"workdir-{skill_name}")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        # Tolerate cross-repo symlinks whose targets are absent in CI rather
        # than aborting the whole copy.
        shutil.copytree(SKILLS_PATH, work_dir,
                        ignore=shutil.ignore_patterns('.git'),
                        ignore_dangling_symlinks=True)
        exclude_own_slug_from_reference_library(work_dir, filenames)

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
