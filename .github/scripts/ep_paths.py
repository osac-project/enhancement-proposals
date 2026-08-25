"""Shared enhancements/ path parsing: OSAC-key regex, Feature-key derivation,
and directory-structure validation.

Single source of truth for the OSAC-key/directory regex — both
check_ep_naming.py (pre-commit enforcement) and ep_review.py (review-bot
context) import from here rather than each defining their own copy.
"""

import re

NAME_RE = re.compile(r"^OSAC-[1-9][0-9]*-[a-z0-9]+(?:-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^(OSAC-[1-9][0-9]*)-")

CANONICAL_FILENAMES = frozenset({"prd.md", "design.md"})


def top_level_enhancement_dir(path: str) -> str | None:
    prefix = "enhancements/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix):]
    if "/" not in rest:
        return None
    return rest.split("/", 1)[0]


def derive_feature_key(files: list[str]) -> str | None:
    """Return the single Jira Feature key found across the canonical EP
    documents (prd.md/design.md) touched by the PR.

    Only prd.md/design.md paths are considered — an incidental drive-by
    edit to another EP's non-canonical file (e.g. a repo-wide link fix
    touching README.md) must not downgrade an otherwise-unambiguous key to
    "ambiguous". Returns None if no canonical enhancements/<KEY>-<slug>/
    doc is touched, or the string "ambiguous" if two or more distinct keys
    are found across canonical docs. Never guesses, never reads PR
    title/body — path-derived only.
    """
    keys = set()
    for f in files:
        basename = f.rsplit("/", 1)[-1]
        if basename.lower() not in CANONICAL_FILENAMES:
            continue
        dir_name = top_level_enhancement_dir(f)
        if dir_name is None:
            continue
        m = KEY_RE.match(dir_name)
        if m:
            keys.add(m.group(1))

    if len(keys) == 0:
        return None
    if len(keys) > 1:
        return "ambiguous"
    return next(iter(keys))


def validate_ep_structure(files: list[str]) -> list[str]:
    """Return a list of human-readable structural violations.

    Informational only — never blocks, never forces a review skip. Real,
    legitimate directory shapes (README.md-only legacy dirs, prd.md-only
    dirs pending design, extra non-canonical files, grandfathered
    non-prefixed dirs) are tolerated without a violation.
    """
    violations = []
    for f in files:
        dir_name = top_level_enhancement_dir(f)
        basename = f.rsplit("/", 1)[-1]

        if dir_name is None:
            if f.startswith("enhancements/") and basename.lower() in CANONICAL_FILENAMES:
                violations.append(
                    f"{f}: '{basename}' sits directly under enhancements/ "
                    "instead of inside an enhancements/<KEY>-<slug>/ directory"
                )
            continue

        if basename.lower() in CANONICAL_FILENAMES and not NAME_RE.match(dir_name):
            violations.append(
                f"{f}: directory 'enhancements/{dir_name}' doesn't match the "
                "required format OSAC-<jira-key>-<slug>"
            )

        if basename.lower() in CANONICAL_FILENAMES and basename != basename.lower():
            violations.append(
                f"{f}: filename '{basename}' must be lowercase "
                f"('{basename.lower()}')"
            )

    return violations
