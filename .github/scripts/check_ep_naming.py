#!/usr/bin/env python3
"""Validate enhancements/ directory and file naming for paths new to a PR.

Directories and files that already existed at the PR base branch are
grandfathered — this only enforces the naming convention on new work.

Enforcement requires a PR base SHA (set via PRE_COMMIT_PR_BASE_SHA, always
present in the CI pre-commit job). Local runs without it are advisory-only
(a note is printed, nothing is flagged) so the git hook never blocks a
commit that CI would pass.

PRE_COMMIT_PR_BASE_SHA is a snapshot of `main` taken from the
`pull_request` webhook payload at the PR's last open/synchronize event —
it does not advance just because `main` gains new commits, and re-running
an old CI job replays that same stale payload rather than refreshing it.
For a long-lived PR that hasn't been pushed to since some *other*,
unrelated PR merged a still-non-compliant directory into `main`, that
stale SHA predates the unrelated directory, so it looks "new" here and
gets (incorrectly) enforced against — even though the current PR never
touches it and it's already correctly grandfathered on `main` itself.

To avoid that false positive, grandfathering also checks the *live* tip
of the base branch (PRE_COMMIT_LIVE_BASE_REF, e.g. `origin/main`, fetched
fresh at the start of every CI run) in addition to the stale base SHA: a
path is grandfathered if it exists at *either* reference. This keeps
enforcement scoped to paths that are genuinely new — including for
contributors actively renaming their own non-compliant directory to fix
it, who should never be blocked by an unrelated pre-existing violation
elsewhere in the repo.
"""

import os
import re
import subprocess
import sys

NAME_RE = re.compile(r"^OSAC-[1-9][0-9]*-[a-z0-9]+(?:-[a-z0-9]+)*$")
CHECKED_FILENAMES = frozenset({"prd.md", "design.md"})

BASE_SHA_ENV_VAR = "PRE_COMMIT_PR_BASE_SHA"
LIVE_BASE_REF_ENV_VAR = "PRE_COMMIT_LIVE_BASE_REF"


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


def resolve_live_base_ref(live_base_ref: str | None) -> str | None:
    # The live ref is best-effort: it's only set in CI (and only useful once
    # actions/checkout has actually fetched it). If it's absent or doesn't
    # resolve, grandfathering silently falls back to the base-SHA-only
    # behavior below rather than erroring — this is a supplementary check,
    # not a required one.
    if live_base_ref is not None and ref_exists(live_base_ref):
        return live_base_ref
    return None


def is_grandfathered(
    path: str, base_sha: str | None, live_base_ref: str | None
) -> bool:
    if base_sha is not None and path_exists_at_ref(base_sha, path):
        return True
    if live_base_ref is not None and path_exists_at_ref(live_base_ref, path):
        return True
    return False


def validate_paths(
    paths: list[str],
    base_sha: str | None,
    live_base_ref: str | None = None,
) -> list[str]:
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

    live_base_ref = resolve_live_base_ref(live_base_ref)

    violations = []
    for path in paths:
        dir_name = top_level_enhancement_dir(path)
        if dir_name is None:
            continue

        dir_path = f"enhancements/{dir_name}"
        dir_is_grandfathered = is_grandfathered(dir_path, base_sha, live_base_ref)

        if not dir_is_grandfathered and not NAME_RE.match(dir_name):
            violations.append(
                f"{path}: directory '{dir_name}' doesn't match the "
                "required format OSAC-<jira-key>-<slug> (e.g. "
                "OSAC-1110-storage-tier-api) — see CONTRIBUTING.md for "
                "the full naming convention"
            )

        basename = path.rsplit("/", 1)[-1]
        if basename.lower() not in CHECKED_FILENAMES or basename.lower() == basename:
            continue

        file_is_grandfathered = is_grandfathered(path, base_sha, live_base_ref)
        if not file_is_grandfathered:
            violations.append(
                f"{path}: filename '{basename}' must be lowercase "
                f"('{basename.lower()}')"
            )

    return violations


def main(argv: list[str]) -> int:
    base_sha = os.environ.get(BASE_SHA_ENV_VAR) or None
    live_base_ref = os.environ.get(LIVE_BASE_REF_ENV_VAR) or None
    violations = validate_paths(argv, base_sha, live_base_ref)
    for violation in violations:
        print(violation, file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
