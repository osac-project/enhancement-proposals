#!/usr/bin/env python3
"""Validate enhancements/ directory and file naming for paths new to a PR.

Directories and files that already existed at the PR base branch are
grandfathered — this only enforces the naming convention on new work.
"""

import os
import re
import subprocess
import sys

NAME_RE = re.compile(r"^OSAC-[1-9][0-9]*-[a-z0-9-]+$")
CHECKED_FILENAMES = frozenset({"prd.md", "design.md"})

BASE_SHA_ENV_VAR = "PRE_COMMIT_PR_BASE_SHA"


def path_exists_at_ref(ref: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True,
    )
    return result.returncode == 0


def ref_exists(ref: str) -> bool:
    result = subprocess.run(["git", "cat-file", "-e", ref], capture_output=True)
    return result.returncode == 0


def top_level_enhancement_dir(path: str) -> str | None:
    prefix = "enhancements/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix):]
    if "/" not in rest:
        return None
    return rest.split("/", 1)[0]


def validate_paths(paths: list[str], base_sha: str | None) -> list[str]:
    if base_sha is not None and not ref_exists(base_sha):
        print(
            f"warning: PR base SHA '{base_sha}' is not available in this "
            "checkout (the checkout step needs fetch-depth: 0) — "
            "grandfathering disabled, every enhancements/ path will be "
            "validated as new",
            file=sys.stderr,
        )
        base_sha = None
    elif base_sha is None:
        print(
            "warning: no PR base SHA available — expected for local, "
            "non-CI runs; grandfathering disabled here, but the CI "
            "pre-commit job (which sets PRE_COMMIT_PR_BASE_SHA) is the "
            "authoritative gate — every enhancements/ path will be "
            "validated as new",
            file=sys.stderr,
        )

    violations = []
    for path in paths:
        dir_name = top_level_enhancement_dir(path)
        if dir_name is None:
            continue

        dir_path = f"enhancements/{dir_name}"
        dir_is_grandfathered = base_sha is not None and path_exists_at_ref(base_sha, dir_path)

        if not dir_is_grandfathered and not NAME_RE.match(dir_name):
            violations.append(
                f"{path}: directory '{dir_name}' does not match the naming "
                f"convention (expected OSAC-<jira-key>-<feature-slug>)"
            )

        basename = path.rsplit("/", 1)[-1]
        if basename.lower() not in CHECKED_FILENAMES or basename.lower() == basename:
            continue

        file_is_grandfathered = base_sha is not None and path_exists_at_ref(base_sha, path)
        if not file_is_grandfathered:
            violations.append(
                f"{path}: filename '{basename}' must be lowercase "
                f"('{basename.lower()}')"
            )

    return violations


def main(argv: list[str]) -> int:
    base_sha = os.environ.get(BASE_SHA_ENV_VAR) or None
    violations = validate_paths(argv, base_sha)
    for violation in violations:
        print(violation, file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
