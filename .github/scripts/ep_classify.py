"""Phase B logistics-only diff classifier.

classify_logistics_only(files) inspects the widened per-file GitHub "pulls/*/files"
API payload (status, previous_filename, and patch — not just filename) and returns
"LOGISTICS_ONLY" only when EVERY changed file is independently, provably one of
three safe shapes:

  1. A pure rename with no content change at all (status == "renamed", no patch).
  2. A change confined entirely to an explicit allow-listed YAML frontmatter field
     (e.g. tracking-link, last-updated).
  3. A same-line link-target/path substitution — the only characters that differ
     between the old and new line sit inside a markdown link, a bare URL, or a bare
     "/enhancements/..." path; everything else on the line is byte-identical.

There is no separate "ambiguous" bucket. Anything that isn't provably one of the
three shapes above — an unrecognized frontmatter field, a heading added/removed, a
brand-new prd.md/design.md, a truncated/unparseable patch, real prose rewritten —
is SUBSTANTIVE. "When in doubt, review."

This is a per-file decision. It is intentionally independent of Phase A's
ep_paths.derive_feature_key: a PR can legitimately touch many different EP
directories (and therefore many distinct Feature keys) while still being a pure
logistics sweep — see PR #174, a 16-file cross-EP rename PR that must classify
LOGISTICS_ONLY despite derive_feature_key reporting "ambiguous" for it. Feature-key
attribution and logistics classification answer different questions and must not be
coupled; see the "Correction" note in the frozen design doc for the discovery that
led to this split.
"""

import re

LOGISTICS_ONLY = "LOGISTICS_ONLY"
SUBSTANTIVE = "SUBSTANTIVE"

CANONICAL_FILENAMES = frozenset({"prd.md", "design.md"})

# Top-level YAML frontmatter keys used by the EP templates (guidelines/design_template.md
# and legacy README.md EPs). Restricting to this known set (rather than matching any
# "word:" at column 0) keeps a body-prose line that happens to start with "word:" from
# being mistaken for frontmatter.
KNOWN_FRONTMATTER_FIELDS = frozenset({
    "title", "authors", "creation-date", "last-updated", "tracking-link",
    "prd", "see-also", "replaces", "superseded-by", "status",
})

# Fields whose value may change without the file losing its LOGISTICS_ONLY-eligible
# status. Deliberately narrow — see design's "frontmatter field not on the allow-list"
# fail-safe. Any other frontmatter field change must still pass the path-substitution
# check (category 3) or the file is SUBSTANTIVE.
ALLOWED_FRONTMATTER_FIELDS = frozenset({"tracking-link", "last-updated"})

FRONTMATTER_KEY_RE = re.compile(r"^([a-z][a-z0-9-]*):")
HEADING_RE = re.compile(r"^#{1,6}(\s|$)")
HUNK_HEADER_RE = re.compile(r"^@@ ")

# Matches the parts of a line that are allowed to change under category 3: a full
# markdown link `[text](target)`, a bare URL, or a bare "/enhancements/..." path.
LINK_OR_PATH_RE = re.compile(
    r"\[[^\]]*\]\([^)]*\)"
    r"|https?://\S+"
    r"|/enhancements/[A-Za-z0-9._/-]+"
)


def _mask_links_and_paths(line):
    return LINK_OR_PATH_RE.sub("\0", line)


def _is_path_substitution(old_line, new_line):
    """True if the only difference between the two lines is inside a link/path
    span — i.e. masking out every link/path substring makes them byte-identical."""
    return _mask_links_and_paths(old_line) == _mask_links_and_paths(new_line)


def _split_hunks(patch):
    """Split a unified-diff patch into a list of hunks, each a list of raw
    (prefix-included) lines, in file order."""
    hunks = []
    current = None
    for line in patch.splitlines():
        if HUNK_HEADER_RE.match(line):
            current = []
            hunks.append(current)
        elif current is not None:
            current.append(line)
    return hunks


def _update_frontmatter_field(content, current_field):
    m = FRONTMATTER_KEY_RE.match(content)
    if m and m.group(1) in KNOWN_FRONTMATTER_FIELDS:
        return m.group(1)
    return current_field


def _hunk_is_safe(hunk_lines):
    current_field = None
    i = 0
    n = len(hunk_lines)
    while i < n:
        line = hunk_lines[i]
        marker = line[:1]
        content = line[1:]

        if marker == " " or marker == "":
            current_field = _update_frontmatter_field(content, current_field)
            i += 1
            continue

        if marker not in "+-":
            # e.g. "\ No newline at end of file" — not a content change.
            i += 1
            continue

        removed = []
        while i < n and hunk_lines[i].startswith("-"):
            removed.append(hunk_lines[i][1:])
            i += 1
        added = []
        while i < n and hunk_lines[i].startswith("+"):
            added.append(hunk_lines[i][1:])
            i += 1

        for changed_line in removed + added:
            if HEADING_RE.match(changed_line):
                return False
            current_field = _update_frontmatter_field(changed_line, current_field)

        if current_field in ALLOWED_FRONTMATTER_FIELDS:
            continue

        if len(removed) != len(added):
            return False
        if not all(
            _is_path_substitution(old, new) for old, new in zip(removed, added)
        ):
            return False

    return True


def _file_is_logistics_only(f):
    basename = f["filename"].rsplit("/", 1)[-1].lower()
    status = f.get("status")

    if status == "added" and basename in CANONICAL_FILENAMES:
        return False

    patch = f.get("patch")
    if not patch:
        # A pure rename with zero content change omits `patch` entirely (and
        # reports changes == 0). Anything else missing a patch — a truncated
        # large diff, a binary file — cannot be proven safe.
        return status == "renamed" and f.get("changes", 0) == 0

    hunks = _split_hunks(patch)
    if not hunks:
        return False

    return all(_hunk_is_safe(hunk) for hunk in hunks)


def classify_logistics_only(files):
    """files: list of per-file dicts from the GitHub "pulls/*/files" API
    (filename, status, additions, deletions, changes, patch, previous_filename).

    Returns LOGISTICS_ONLY only if every file in the PR is independently,
    provably one of the three safe shapes described in the module docstring.
    """
    if not files:
        return SUBSTANTIVE

    if all(_file_is_logistics_only(f) for f in files):
        return LOGISTICS_ONLY
    return SUBSTANTIVE
