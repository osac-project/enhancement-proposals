#!/usr/bin/env python3
"""Validate enhancements/ directory and file naming for paths new to a PR.

Directories and files that already existed at the PR base branch are
grandfathered — this only enforces the naming convention on new work.

Enforcement requires a PR base SHA (set via PRE_COMMIT_PR_BASE_SHA, always
present in the CI pre-commit job). Local runs without it are advisory-only
(a note is printed, nothing is flagged) so the git hook never blocks a
commit that CI would pass.
"""

import os
import re
import subprocess
import sys

NAME_RE = re.compile(r"^OSAC-[1-9][0-9]*-[a-z0-9]+(?:-[a-z0-9]+)*$")
CHECKED_FILENAMES = frozenset({"prd.md", "design.md"})

# A closed, deliberately tiny allowlist — not a general "any legacy prefix is
# OK" carve-out. Each entry is a pre-existing EP whose only tracking key
# predates the OSAC Jira project, so it can never earn an OSAC-<N>- name
# (see OSAC-2870). New EPs must get a real OSAC Feature key; this list is not
# meant to grow, and isn't advertised in CONTRIBUTING.md.
LEGACY_KEY_ALLOWLIST = frozenset({"MGMT-23669-tenant-storage-tiers"})

BASE_SHA_ENV_VAR = "PRE_COMMIT_PR_BASE_SHA"


def path_exists_at_ref(ref: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", ref], capture_output=True, check=False
    )
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
    # No base SHA at all means this is a local, non-CI run (CI always sets
    # PRE_COMMIT_PR_BASE_SHA). Enforcing here would block commits that CI
    # would pass — e.g. anyone with the git hook installed editing a file in
    # an existing legacy directory — and push contributors toward
    # `--no-verify`, which skips every other hook too. So local runs are
    # advisory-only; CI remains the sole enforcement gate.
    if base_sha is None:
        print(
            "note: no PR base SHA available — normal for local, non-CI "
            "runs (pre-commit has no way to know your PR's base branch "
            "outside CI). Skipping enhancements/ naming/casing checks "
            "here; the CI pre-commit job (which sets "
            "PRE_COMMIT_PR_BASE_SHA) is the authoritative gate and will "
            "still catch violations before merge.",
            file=sys.stderr,
        )
        return []

    # A base SHA *was* provided (i.e. we're in CI) but doesn't resolve —
    # unlike the "no base SHA" case above, this indicates a CI
    # misconfiguration (e.g. a shallow checkout) and should stay fail-closed
    # rather than silently disabling enforcement.
    if not ref_exists(base_sha):
        print(
            f"warning: PR base SHA '{base_sha}' is not available in this "
            "checkout (the checkout step needs fetch-depth: 0) — "
            "grandfathering disabled, every enhancements/ path will be "
            "validated as new",
            file=sys.stderr,
        )
        base_sha = None

    violations = []
    for path in paths:
        dir_name = top_level_enhancement_dir(path)
        if dir_name is None:
            continue

        dir_path = f"enhancements/{dir_name}"
        dir_is_grandfathered = base_sha is not None and path_exists_at_ref(base_sha, dir_path)

        if (
            not dir_is_grandfathered
            and not NAME_RE.match(dir_name)
            and dir_name not in LEGACY_KEY_ALLOWLIST
        ):
            violations.append(
                f"{path}: directory '{dir_name}' doesn't match the "
                "required format OSAC-<jira-key>-<slug> (e.g. "
                "OSAC-1110-storage-tier-api) — see CONTRIBUTING.md for "
                "the full naming convention"
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
