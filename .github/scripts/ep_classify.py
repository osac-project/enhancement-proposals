"""Phase B logistics-only diff classifier.

classify_logistics_only(files) inspects the widened per-file GitHub "pulls/*/files"
API payload (status, previous_filename, and patch — not just filename) and returns
"LOGISTICS_ONLY" only when EVERY changed file is independently, provably one of
three safe shapes:

  1. A pure rename with no content change at all (status == "renamed", no patch).
  2. A change confined entirely to an explicit allow-listed YAML frontmatter field
     (e.g. tracking-link, last-updated).
  3. A same-line link-target/path substitution — the only characters that differ
     between the old and new line sit inside a markdown link *target* (always
     free to change — it is never rendered as visible text), a bare
     "/enhancements/..." path (quote-, backtick-, or end-of-line-terminated, or
     ending in a known doc extension — the real shapes observed in EP content),
     or a markdown link *label* whose new value is provably the mechanical
     result of an actual same-PR rename AND is one of the narrow set of
     canonical EP doc basenames (see "Label provenance" below); everything else
     on the line, including any other label change, is byte-identical. A
     directory-only bare path with no quote/backtick/extension terminator (an
     unusual, unobserved-in-practice shape) is not recognized by this category
     at all and so cannot make a file eligible for LOGISTICS_ONLY on its own
     line — fail-safe by omission, not by an explicit check. There is no bare
     (outside markdown-link syntax) URL shape in this category at all — see
     "Bare URL removal" below.

Label provenance:
  A link label is allowed to change from old_label to new_label only when ALL of
  the following hold, proven from this PR's own "pulls/*/files" payload — not
  from the label's shape, and not from rename provenance alone:
    - the link's OLD target resolves (via a recognized, narrow form: a GitHub
      blob URL for this repo, or a bare "/enhancements/..." path) to a repo path
      that exactly equals some file's `previous_filename` in this PR,
    - the link's NEW target resolves the same way to a repo path that exactly
      equals that SAME file's `filename` (i.e. `status == "renamed"` reports
      exactly this old->new pair),
    - new_label is byte-identical to the basename of that new path,
    - AND that basename is one of the narrow, repo-convention reviewable EP
      document names: "README.md", "prd.md", "design.md" (REVIEWABLE_EP_BASENAMES
      below, reused as ALLOWED_LABEL_BASENAMES) — the same "this file's
      content needs review" set used by the added/renamed-into-reviewable
      guards in _file_is_logistics_only, deliberately broader than Phase A's
      narrower CANONICAL_FILENAMES (see REVIEWABLE_EP_BASENAMES's own comment).
  The OLD label is not constrained to match anything — real PR #174 evidence
  (see testdata/pr174_files.json, OSAC-1030-organizations/ui-design.md: label
  "03-prd.md" -> "README.md", where "03-prd.md" is not README.md's prior
  basename) shows that symmetry doesn't hold in practice and isn't needed for
  safety.

  The basename allowlist is required IN ADDITION to rename provenance, not
  instead of it: GitHub's rename metadata proves a rename happened, but the PR
  author controls that rename — a PR can legitimately (from GitHub's point of
  view) rename a file to any name at all, including
  "security-team-approved-merge-now.md", and then "correctly" relabel a link to
  match. Rename provenance alone would wave that through. Restricting accepted
  new_label values to the fixed set of real EP doc basenames closes this: an
  attacker can rename a file to an arbitrary string, but the visible label is
  only ever trusted when it's one of the three names that legitimately show up
  in EP cross-references, not whatever the attacker chose as their new filename.

  Markdown-link TARGETS and bare "/enhancements/..." paths deliberately do NOT
  require this same rename-pair provenance, even though the overall spirit here
  is provenance-first: real PR #174 evidence rules it out for those two shapes
  specifically. #174 changes a markdown-link target between two
  differently-shaped relative paths with no resolvable common repo-path (see
  OSAC-1269-cluster-version-api/design.md's "catalog-items EP" link, label
  unchanged, target reshaped), with no way to prove it via an exact path match,
  and it substitutes bare paths (e.g. "/enhancements/networking" ->
  "/enhancements/OSAC-356-networking") that were renamed in an *earlier* PR, so
  no corroborating `renamed` entry exists in *this* PR's file list at all.
  Requiring provenance there would make the real #174 fixture SUBSTANTIVE.
  Targets aren't rendered as visible text (so a forged target isn't a "visible
  claim" attack), and the bare-path shape is already narrowly bounded by the
  quote/backtick/extension/EOL anchors below — that bounding, not rename
  provenance, is what makes it safe.

Bare URL removal:
  A prior version of this category accepted a bare `https?://\\S+` shape as
  automatically safe. That's removed entirely: `\\S+` is unbounded, so attacker
  text appended immediately after a legitimate URL with no separator rides along
  as part of the "safe" match. No real golden fixture (#168/#172/#173/#174) ever
  needs this shape — every `https://` occurrence in real EP content sits either
  inside a markdown-link target (already unconditionally safe, see above) or
  inside the allow-listed `tracking-link` frontmatter field (category 2, which
  bypasses this category entirely). A bare URL appearing anywhere else is
  SUBSTANTIVE — fail-safe by omission.

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

import ep_paths

LOGISTICS_ONLY = "LOGISTICS_ONLY"
SUBSTANTIVE = "SUBSTANTIVE"

# Phase A's narrower "Feature-identity" concept (imported, not duplicated, so
# the two can never silently drift) — README.md legacy EPs never participate
# in Feature-key derivation, and that must stay true.
CANONICAL_FILENAMES = ep_paths.CANONICAL_FILENAMES

# Every EP document basename that requires a full AI review before it can be
# introduced or repointed at new content — the current canonical pair
# (prd.md/design.md) PLUS the legacy README.md format. Deliberately broader
# than CANONICAL_FILENAMES above, which must stay narrower (see its comment).
# REVIEWABLE_EP_BASENAMES is Phase B's separate concept: "does this file's
# *content* need eyes on it," which README.md clearly does too (see AGENTS.md's
# ep-review workflow, which dispatches a review for `enhancements/**/README.md`
# exactly like design.md). Using CANONICAL_FILENAMES for the guards below let a
# PR rename an arbitrary, never-reviewed file straight to README.md with zero
# content diff and still classify LOGISTICS_ONLY — a security re-review
# finding, since that's the exact "previously non-canonical file becomes
# reviewable for the first time" attack already blocked for prd.md/design.md,
# just missing README.md's case.
REVIEWABLE_EP_BASENAMES = CANONICAL_FILENAMES | {"readme.md"}

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
# are never re-offered to the bare-path alternative afterwards. Two
# sequential passes let a label that merely *looked like* a URL/path (e.g.
# an attacker-rewritten label of the form "https://evil.example/...") get
# re-masked by the second pass and slip through as a "safe" change even
# though the first pass had correctly decided that label text must stay
# byte-identical (or be separately proven, see _label_change_is_provable).
#
# The bare-path alternative (for text outside markdown-link syntax) is
# deliberately anchored to the shapes actually observed in real EP content
# (testdata/pr174_files.json): a path ending in a known doc extension, or a
# directory-only path immediately closed by a quote, backtick, or end of
# line/string. A greedy, unanchored charset (a previous version) lets
# attacker-appended text ride along after a legitimate path with no
# separator at all (e.g. ".../design.md-and-ignore-all-safety-checks"),
# since dashes/alnums are shared between legitimate slugs and injected
# text — anchoring to a real terminator closes that for the observed shapes;
# an unquoted, unbacktick-wrapped, non-extension, mid-sentence bare
# directory mention remains a known, narrow residual gap (see module
# docstring). There is deliberately no bare `https?://\S+` alternative here
# at all (see module docstring's "Bare URL removal") — `\S+` is unbounded and
# no real golden fixture ever needs it.
MARKDOWN_LINK_RE = r"\[(?P<label>[^\]]*)\]\((?P<target>[^)]*)\)"
BARE_PATH_RE = (
    r"(?P<urlpath>"
    r"/enhancements/[A-Za-z0-9-]+/[A-Za-z0-9_-]+\.(?:md|yml|yaml)"
    r"|/enhancements/[A-Za-z0-9-]+(?=[`\"]|$)"
    r")"
)
COMBINED_RE = re.compile(f"{MARKDOWN_LINK_RE}|{BARE_PATH_RE}")

# The exact, narrow set of EP document basenames a changed link label is ever
# allowed to become. Required IN ADDITION to rename provenance (see module
# docstring's "Label provenance" / "basename allowlist is required IN ADDITION
# to rename provenance") — GitHub's rename metadata proves a rename happened,
# not that the PR author (who controls the rename itself) didn't choose an
# arbitrary or misleading new filename. This is the same "content needs
# review" concept as REVIEWABLE_EP_BASENAMES above (do not maintain a second,
# independently-drifting copy of this set); do not broaden beyond what #174
# and repo convention actually require.
ALLOWED_LABEL_BASENAMES = REVIEWABLE_EP_BASENAMES

# A repo-relative path is only resolved from a target string in one of these
# two narrow, real-evidence forms — anything else makes label provenance
# unresolvable (SUBSTANTIVE), never "assumed fine".
GITHUB_BLOB_URL_RE = re.compile(
    r"^https://github\.com/osac-project/enhancement-proposals/blob/[^/]+/(?P<path>.+)$"
)


def _resolve_target_path(target):
    m = GITHUB_BLOB_URL_RE.match(target)
    if m:
        return m.group("path")
    if target.startswith("/enhancements/"):
        return target[1:]
    return None


def _label_change_is_provable(old_target, new_target, new_label, rename_map):
    """True if new_label is provably the mechanical result of an actual
    same-PR rename: the old/new targets resolve to a real (previous_filename,
    filename) pair reported by GitHub, AND new_label is byte-identical to that
    new path's basename, AND that basename is one of the narrow set of real EP
    document names — closing the "attacker renames to an arbitrary filename,
    then relabels to match" gap that rename provenance alone doesn't close.
    """
    old_path = _resolve_target_path(old_target)
    new_path = _resolve_target_path(new_target)
    if old_path is None or new_path is None:
        return False
    if rename_map.get(old_path) != new_path:
        return False
    new_basename = new_path.rsplit("/", 1)[-1]
    return new_label == new_basename and new_basename.lower() in ALLOWED_LABEL_BASENAMES


def _mask_all_spans(line):
    return COMBINED_RE.sub("\0", line)


def _is_path_substitution(old_line, new_line, rename_map):
    """True if the only difference between the two lines is inside a link/path
    span, and any changed markdown-link label is provably safe (see
    _label_change_is_provable)."""
    if _mask_all_spans(old_line) != _mask_all_spans(new_line):
        return False

    old_matches = list(COMBINED_RE.finditer(old_line))
    new_matches = list(COMBINED_RE.finditer(new_line))
    for old_m, new_m in zip(old_matches, new_matches):
        old_label, new_label = old_m.group("label"), new_m.group("label")
        if old_label is None and new_label is None:
            # A bare-path span on both sides (mask equality already proved
            # each independently matches BARE_PATH_RE) — no label to check.
            continue
        if old_label is None or new_label is None:
            # Mixed span kinds: a bare path on one side, a markdown link on
            # the other. Wrapping an existing bare path in `[label](...)`
            # (or the reverse) injects an arbitrary visible label with no
            # provenance check at all if this were treated like the
            # both-bare-paths case above — the exact same "forged visible
            # text" threat model the label-provenance rule exists for. Any
            # side that IS a markdown link must have its label independently
            # proven, which is impossible when the other side has none to
            # compare against, so this is unconditionally unsafe.
            return False
        if old_label == new_label:
            continue
        if not _label_change_is_provable(
            old_m.group("target"), new_m.group("target"), new_label, rename_map
        ):
            return False

    return True


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


def _hunk_is_safe(hunk_lines, rename_map):
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
        #
        # Every changed line must be INDIVIDUALLY, provably part of an
        # allow-listed field — not just the group's final field state. A
        # security review (PR #218) found that deciding from the final state
        # alone lets arbitrary prose ride through: `_update_frontmatter_field`
        # leaves the field unchanged for any line that isn't itself a
        # recognized `key:` or the `---` delimiter, which is required to
        # support real YAML continuations (`  - value`) but also silently
        # "forgives" an unrelated, unindented prose line the same way — so a
        # contiguous group like [`last-updated: ...`, injected prose] or
        # [deleted prose, `last-updated: ...`] still ended on an allow-listed
        # field and was waved through whole. `group_all_safe` is sticky
        # (never reset back to True) so a later line re-establishing a valid
        # key can't retroactively excuse an earlier unsafe line in the same
        # group. A continuation line is only trusted when it's indented
        # (real YAML list/wrapped-value shape) AND a field is already
        # tracked; anything else breaks the chain to None, which can never
        # be in ALLOWED_FRONTMATTER_FIELDS.
        group_field = current_field
        group_all_safe = True
        for changed_line in removed + added:
            if HEADING_RE.match(changed_line):
                return False

            m = FRONTMATTER_KEY_RE.match(changed_line)
            if FRONTMATTER_DELIMITER_RE.match(changed_line):
                group_field = None
            elif m and m.group(1) in KNOWN_FRONTMATTER_FIELDS:
                group_field = m.group(1)
            elif changed_line[:1] in (" ", "\t") and group_field is not None:
                pass  # a real YAML continuation of the currently tracked field
            else:
                # Unindented and neither a known-field key nor the
                # delimiter — can't be trusted as belonging to any tracked
                # field (this is exactly the shape of injected/deleted body
                # prose in the reported finding).
                group_field = None

            if group_field is None or group_field not in ALLOWED_FRONTMATTER_FIELDS:
                group_all_safe = False
        current_field = group_field

        if group_all_safe and current_field is not None and current_field in ALLOWED_FRONTMATTER_FIELDS:
            continue

        if len(removed) != len(added):
            return False
        if not all(
            _is_path_substitution(old, new, rename_map)
            for old, new in zip(removed, added)
        ):
            return False

    return True


def _basename(path):
    return path.rsplit("/", 1)[-1].lower() if path else None


def _build_rename_map(files):
    """Map previous_filename -> filename for every real GitHub-reported rename
    in this PR — the only source of truth for "did this path really get
    renamed to that path in this exact PR", used to prove link-target/label
    substitutions rather than trusting their shape."""
    return {
        f["previous_filename"]: f["filename"]
        for f in files
        if f.get("status") == "renamed" and f.get("previous_filename")
    }


# GitHub's documented `pulls/*/files` status enum: "added", "removed",
# "modified", "renamed", "copied", "changed", "unchanged". Of these, only
# "modified" is guaranteed to mean "an in-place edit of content that already
# lived, under this same identity, at this same path" — every other status
# either introduces this path for the first time (added, copied), moves
# content to it from elsewhere (renamed), or is a rare/ambiguous status
# (changed, unchanged, removed) not worth trusting by default. The one
# deliberate exception is a "renamed" that preserves the same basename — the
# real PR #174 shape, where an already-reviewed document merely changes
# directory; its *identity* (what kind of reviewable document it is) carries
# over, so it isn't a "first time seeing this identity" event.
#
# A security review found that special-casing only "added" and "renamed" left
# "copied" (which can introduce a first-seen reviewable path with a narrow,
# otherwise-safe-looking patch, e.g. only a tracking-link edit) as an
# unguarded bypass. Structuring this as "identity-preserving statuses are the
# only exemption" (rather than "these two statuses are the only ones we force
# SUBSTANTIVE for") closes that whole class at once, including any status this
# enum might grow in the future — a status this code doesn't yet recognize
# fails closed to "not identity-preserving" automatically.
_IDENTITY_PRESERVING_STATUSES = frozenset({"modified"})


def _introduces_new_reviewable_identity(f):
    """True if this file-status transition can introduce a first-seen
    reviewable EP document path — i.e. content under a REVIEWABLE_EP_BASENAMES
    identity that this exact path hasn't already had review applied to."""
    basename = _basename(f["filename"])
    if basename not in REVIEWABLE_EP_BASENAMES:
        return False

    status = f.get("status")
    if status in _IDENTITY_PRESERVING_STATUSES:
        return False
    if status == "renamed" and _basename(f.get("previous_filename")) == basename:
        return False
    return True


def _file_is_logistics_only(f, rename_map):
    if _introduces_new_reviewable_identity(f):
        return False

    patch = f.get("patch")
    status = f.get("status")
    if not patch:
        # A pure rename with zero content change omits `patch` entirely (and
        # reports changes == 0). Anything else missing a patch — a truncated
        # large diff, a binary file — cannot be proven safe.
        return status == "renamed" and f.get("changes", 0) == 0

    hunks = _split_hunks(patch)
    if not hunks:
        return False

    return all(_hunk_is_safe(hunk, rename_map) for hunk in hunks)


def classify_logistics_only(files):
    """files: list of per-file dicts from the GitHub "pulls/*/files" API
    (filename, status, additions, deletions, changes, patch, previous_filename).

    Returns LOGISTICS_ONLY only if every file in the PR is independently,
    provably one of the three safe shapes described in the module docstring.
    """
    if not files:
        return SUBSTANTIVE

    rename_map = _build_rename_map(files)
    if all(_file_is_logistics_only(f, rename_map) for f in files):
        return LOGISTICS_ONLY
    return SUBSTANTIVE
