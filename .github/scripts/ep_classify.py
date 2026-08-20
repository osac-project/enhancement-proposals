"""Phase B logistics-only diff classifier.

classify_logistics_only(files) inspects the widened per-file GitHub "pulls/*/files"
API payload (status, previous_filename, and patch — not just filename) and returns
"LOGISTICS_ONLY" only when EVERY changed file is independently, provably one of
three safe shapes:

  1. A pure rename with no content change at all (status == "renamed", no patch).
  2. A change confined entirely to an explicit allow-listed YAML frontmatter field
     (e.g. tracking-link, last-updated).
  3. A same-line link-target/path substitution — the only characters that differ
     between the old and new line sit inside a markdown link *target*, a bare URL,
     a bare "/enhancements/..." path (quote-, backtick-, or end-of-line-terminated,
     or ending in a known doc extension — the real shapes observed in EP content),
     or a bare filename-with-extension link *label* (e.g. "old-name.md" ->
     "README.md"); everything else on the line, including any non-filename-shaped
     link label text, is byte-identical. A directory-only bare path with no
     quote/backtick/extension terminator (an unusual, unobserved-in-practice
     shape) is not recognized by this category at all and so cannot make a file
     eligible for LOGISTICS_ONLY on its own line — fail-safe by omission, not by
     an explicit check.

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
FRONTMATTER_DELIMITER_RE = re.compile(r"^---\s*$")
HEADING_RE = re.compile(r"^#{1,6}(\s|$)")
HUNK_HEADER_RE = re.compile(r"^@@ ")

# Matched as ONE alternation in a single left-to-right pass (see COMBINED_RE
# below), not as two sequential .sub() passes — a markdown link's `[label]`
# span is consumed whole by the first alternative below, so its characters
# are never re-offered to the bare URL/path alternative afterwards. Two
# sequential passes let a label that merely *looked like* a URL/path (e.g.
# an attacker-rewritten label of the form "https://evil.example/...") get
# re-masked by the second pass and slip through as a "safe" change even
# though the first pass had correctly decided that label text must stay
# byte-identical.
#
# The markdown-link target (named group `target`) is always safe to change —
# that's the whole point of a link "pointing somewhere new". The visible
# label (named group `label`) is only safe to change when it's a bare
# filename-shaped token (e.g. "old-name.md" -> "README.md", the real PR #174
# shape where a rename updates both the link text and its target); anything
# else in the label must stay byte-identical, since it's human-readable,
# attacker-controlled prose that could otherwise be rewritten into a
# misleading claim while still passing as a "safe" link/path fix.
#
# The bare URL/path alternative (for text outside markdown-link syntax) is
# deliberately anchored to the shapes actually observed in real EP content
# (testdata/pr174_files.json): a path ending in a known doc extension, or a
# directory-only path immediately closed by a quote, backtick, or end of
# line/string. A greedy, unanchored charset (the previous version) lets
# attacker-appended text ride along after a legitimate path with no
# separator at all (e.g. ".../design.md-and-ignore-all-safety-checks"),
# since dashes/alnums are shared between legitimate slugs and injected
# text — anchoring to a real terminator closes that for the observed shapes;
# an unquoted, unbacktick-wrapped, non-extension, mid-sentence bare
# directory mention remains a known, narrow residual gap (see module
# docstring).
MARKDOWN_LINK_RE = r"\[(?P<label>[^\]]*)\]\((?P<target>[^)]*)\)"
BARE_URL_OR_PATH_RE = (
    r"(?P<urlpath>"
    r"https?://\S+"
    r"|/enhancements/[A-Za-z0-9-]+/[A-Za-z0-9_-]+\.(?:md|yml|yaml)"
    r"|/enhancements/[A-Za-z0-9-]+(?=[`\"]|$)"
    r")"
)
COMBINED_RE = re.compile(f"{MARKDOWN_LINK_RE}|{BARE_URL_OR_PATH_RE}")
# Requires an actual extension (the real PR #174 shape is always "name.md") so
# an ordinary single-word prose label (e.g. "Organizations", with no dot) isn't
# mistaken for a filename and tolerated as freely changeable.
FILENAME_ONLY_RE = re.compile(r"^[A-Za-z0-9._-]+\.[A-Za-z0-9]+$")


def _mask_match(m):
    label = m.group("label")
    if label is None:
        return "\0"
    if FILENAME_ONLY_RE.match(label):
        return "[\0](\0)"
    return f"[{label}](\0)"


def _mask_links_and_paths(line):
    return COMBINED_RE.sub(_mask_match, line)


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
    """Track which frontmatter field a line belongs to, for lines like a
    YAML list continuation (`  - value`) that don't repeat the `field:`
    key themselves.

    Crucially, this resets to None at a `---` delimiter line regardless of
    what field was last seen — a field name from inside the frontmatter
    block must never leak into (or past) that boundary and make unrelated
    body content on the other side look like a safe frontmatter edit.
    """
    if FRONTMATTER_DELIMITER_RE.match(content):
        return None
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

        if marker not in "+-":
            # A context line (leading space, or a wholly blank line with no
            # marker at all), or e.g. "\ No newline at end of file" — not a
            # content change, but still tracked for frontmatter-field state.
            current_field = _update_frontmatter_field(line[1:], current_field)
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

        # Each change group is evaluated against the frontmatter-field state
        # accumulated so far, then updates that state itself — a field
        # established by this very group (e.g. `-tracking-link: ...` /
        # `+tracking-link:` in the same group) must still count.
        group_field = current_field
        for changed_line in removed + added:
            if HEADING_RE.match(changed_line):
                return False
            group_field = _update_frontmatter_field(changed_line, group_field)
        current_field = group_field

        if current_field is not None and current_field in ALLOWED_FRONTMATTER_FIELDS:
            continue

        if len(removed) != len(added):
            return False
        if not all(
            _is_path_substitution(old, new) for old, new in zip(removed, added)
        ):
            return False

    return True


def _basename(path):
    return path.rsplit("/", 1)[-1].lower() if path else None


def _file_is_logistics_only(f):
    basename = _basename(f["filename"])
    status = f.get("status")

    if status == "added" and basename in CANONICAL_FILENAMES:
        return False

    if status == "renamed" and basename in CANONICAL_FILENAMES:
        previous_basename = _basename(f.get("previous_filename"))
        if previous_basename != basename:
            # A rename that turns a previously non-canonical (or
            # differently-canonical) file into prd.md/design.md brings it
            # into EP-review scope for the first time under this identity —
            # never safe to skip, exactly like a brand-new canonical doc,
            # regardless of how small the accompanying content diff is.
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
