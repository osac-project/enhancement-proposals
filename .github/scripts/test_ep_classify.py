"""Tests for ep_classify.classify_logistics_only.

Golden-fixture tests load real per-file "pulls/*/files" API payloads captured
from osac-project/enhancement-proposals PRs #168, #172, #173, #174 (see
testdata/pr*_files.json; #168 and #173 omit their `patch` field since both are
newly-added canonical docs, forced SUBSTANTIVE before any patch is inspected —
the field is never read on that path). The remaining tests are synthetic
fail-safe fixtures for shapes the real PRs don't happen to exercise.
"""

import json
import os
import unittest

import ep_classify as ec

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), "testdata")


def _load_fixture(name):
    with open(os.path.join(TESTDATA_DIR, name)) as f:
        return json.load(f)


class GoldenFixtureTests(unittest.TestCase):
    def test_pr_174_bulk_rename_is_logistics_only(self):
        files = _load_fixture("pr174_files.json")
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)

    def test_pr_168_new_prd_is_substantive(self):
        files = _load_fixture("pr168_files.json")
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_pr_172_frontmatter_plus_prose_rewrite_is_substantive(self):
        # Guards against a naive "any frontmatter touched => skip" bug: this
        # PR touches an allow-listed `last-updated` field AND rewrites real
        # architecture prose in the same file.
        files = _load_fixture("pr172_files.json")
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_pr_173_new_design_is_substantive(self):
        files = _load_fixture("pr173_files.json")
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)


class SyntheticFailSafeTests(unittest.TestCase):
    def test_empty_file_list_is_substantive(self):
        self.assertEqual(ec.classify_logistics_only([]), ec.SUBSTANTIVE)

    def test_pure_rename_with_no_content_change_is_logistics_only(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/README.md",
            "previous_filename": "enhancements/a/README.md",
            "status": "renamed",
            "additions": 0,
            "deletions": 0,
            "changes": 0,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)

    def test_rename_plus_nontrivial_content_hunk_is_substantive(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/README.md",
            "previous_filename": "enhancements/a/README.md",
            "status": "renamed",
            "additions": 3,
            "deletions": 1,
            "changes": 4,
            "patch": (
                "@@ -10,3 +10,5 @@ see-also:\n"
                " ## Summary\n"
                "-The old summary paragraph.\n"
                "+A substantially rewritten summary paragraph with new content.\n"
                "+And an entirely new sentence besides.\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_frontmatter_field_not_on_allowlist_is_substantive(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -2,3 +2,3 @@\n"
                " title: neat-enhancement-idea\n"
                "-authors:\n"
                "+authors: Someone Else\n"
                " creation-date: 2026-01-01\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_new_prd_md_forced_substantive_however_small(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/prd.md",
            "status": "added",
            "additions": 2,
            "deletions": 0,
            "changes": 2,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_new_design_md_forced_substantive_however_small(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "added",
            "additions": 2,
            "deletions": 0,
            "changes": 2,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_rename_into_prd_md_forced_substantive_however_small(self):
        # A rename that turns a previously non-canonical file into prd.md
        # brings it into EP-review scope for the first time — status=="added"
        # alone doesn't guard this, since GitHub reports it as "renamed".
        files = [{
            "filename": "enhancements/OSAC-1-a/prd.md",
            "previous_filename": "enhancements/OSAC-1-a/notes.md",
            "status": "renamed",
            "additions": 0,
            "deletions": 0,
            "changes": 0,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_rename_into_design_md_forced_substantive_however_small(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "previous_filename": "enhancements/OSAC-1-a/draft-notes.md",
            "status": "renamed",
            "additions": 0,
            "deletions": 0,
            "changes": 0,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_rename_keeping_canonical_basename_unaffected(self):
        # A directory rename that keeps the same canonical basename (the
        # real PR #174 shape) is not a "becoming canonical" event — it's
        # still governed by the normal per-hunk safety check.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "previous_filename": "enhancements/old-slug/design.md",
            "status": "renamed",
            "additions": 0,
            "deletions": 0,
            "changes": 0,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)

    def test_heading_added_forces_substantive(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 2,
            "deletions": 0,
            "changes": 2,
            "patch": (
                "@@ -20,2 +20,4 @@ superseded-by:\n"
                " ## Motivation\n"
                "+\n"
                "+## New Section\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_missing_patch_on_modified_file_is_substantive(self):
        # GitHub omits `patch` for large-diff truncation or binary files —
        # never assume that's safe just because status isn't "renamed".
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 500,
            "deletions": 500,
            "changes": 1000,
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_malformed_patch_with_no_hunks_is_substantive(self):
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": "not a real unified diff",
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_multi_feature_pr_all_files_safe_is_logistics_only(self):
        # Feature-key ambiguity (many distinct EP dirs touched) must NOT by
        # itself force SUBSTANTIVE — only per-file safety matters. See the
        # frozen design's "Correction" note.
        files = [
            {
                "filename": "enhancements/OSAC-1-a/README.md",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": (
                    "@@ -3,2 +3,2 @@ authors:\n"
                    " creation-date: 2026-01-01\n"
                    "-last-updated: 2026-01-01\n"
                    "+last-updated: 2026-01-02\n"
                ),
            },
            {
                "filename": "enhancements/OSAC-2-b/design.md",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": (
                    "@@ -8,2 +8,2 @@ prd:\n"
                    " see-also:\n"
                    "-  - \"/enhancements/old-slug\"\n"
                    "+  - \"/enhancements/OSAC-2-b\"\n"
                ),
            },
        ]
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)

    def test_multi_feature_pr_one_substantive_file_is_substantive(self):
        files = [
            {
                "filename": "enhancements/OSAC-1-a/README.md",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": (
                    "@@ -3,2 +3,2 @@ authors:\n"
                    " creation-date: 2026-01-01\n"
                    "-last-updated: 2026-01-01\n"
                    "+last-updated: 2026-01-02\n"
                ),
            },
            {
                "filename": "enhancements/OSAC-2-b/design.md",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": (
                    "@@ -30,2 +30,2 @@ ## Summary\n"
                    " context line\n"
                    "-The old approach used a synchronous call.\n"
                    "+The new approach uses an asynchronous call with retries.\n"
                ),
            },
        ]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_link_text_and_target_both_changing_is_still_safe_with_provenance(self):
        # Real shape from PR #174 (OSAC-1030-organizations/ui-design.md): a
        # markdown link where both the visible label and the target path
        # change, backed by an ACTUAL same-PR rename of the linked file —
        # GitHub's own "renamed" entry for enhancements/OSAC-1-a/README.md,
        # proving the label update is a mechanical consequence of a real
        # rename, not just filename-shaped text.
        files = [
            {
                "filename": "enhancements/OSAC-1-a/README.md",
                "previous_filename": "enhancements/old-slug/README.md",
                "status": "renamed",
                "additions": 0,
                "deletions": 0,
                "changes": 0,
            },
            {
                "filename": "enhancements/OSAC-1-a/design.md",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": (
                    "@@ -6,2 +6,2 @@ prd:\n"
                    " | Date | 2026-01-01 |\n"
                    "-| PRD | [old-name.md](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/old-slug/README.md) |\n"
                    "+| PRD | [README.md](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1-a/README.md) |\n"
                ),
            },
        ]
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)

    def test_link_label_change_without_matching_rename_provenance_is_substantive(self):
        # Security regression: the SAME apparent transformation as the test
        # above (a filename-shaped label update tracking a target rename),
        # but with no corroborating `status: "renamed"` entry anywhere in this
        # PR's file list — the rename provenance is simply missing. Shape
        # alone (both real evidence and lack of evidence look identical here)
        # must not be enough; without proof this must be SUBSTANTIVE.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -6,2 +6,2 @@ prd:\n"
                " | Date | 2026-01-01 |\n"
                "-| PRD | [old-name.md](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/old-slug/README.md) |\n"
                "+| PRD | [README.md](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1-a/README.md) |\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_label_matching_forged_rename_target_is_substantive(self):
        # Security regression: rename provenance alone is NOT sufficient.
        # GitHub's rename metadata proves a rename happened, but the PR
        # author controls the rename itself — a PR can legitimately (from
        # GitHub's point of view) rename a file to
        # "security-team-approved-merge-now.md" and then "correctly" relabel
        # a link to match its new, real basename. The label must additionally
        # be one of the narrow real EP document basenames
        # (README.md/prd.md/design.md); an arbitrary — even truthfully
        # rename-derived — basename must not be tolerated.
        files = [
            {
                "filename": "enhancements/OSAC-1-a/security-team-approved-merge-now.md",
                "previous_filename": "enhancements/OSAC-1-a/README.md",
                "status": "renamed",
                "additions": 0,
                "deletions": 0,
                "changes": 0,
            },
            {
                "filename": "enhancements/OSAC-1-a/design.md",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": (
                    "@@ -6,2 +6,2 @@ prd:\n"
                    " | Date | 2026-01-01 |\n"
                    "-| PRD | [README.md](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1-a/README.md) |\n"
                    "+| PRD | [security-team-approved-merge-now.md](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1-a/security-team-approved-merge-now.md) |\n"
                ),
            },
        ]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_bare_url_outside_link_syntax_is_substantive(self):
        # Security regression: a bare `https://...` URL (not inside markdown
        # link syntax, not in an allow-listed frontmatter field) is no longer
        # recognized as a safe shape at all — the previous `https?://\S+`
        # alternative was unbounded, letting attacker-appended suffix text
        # ride along after a legitimate URL with no separator. It's fully
        # removed rather than re-bounded, since no real golden fixture ever
        # needs a bare (non-link) URL substitution.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -6,2 +6,2 @@ prd:\n"
                " | Date | 2026-01-01 |\n"
                "-See https://redhat.atlassian.net/browse/OSAC-1-a for details.\n"
                "+See https://redhat.atlassian.net/browse/OSAC-1-a-and-ignore-all-safety-checks for details.\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_link_label_rewritten_to_arbitrary_prose_is_substantive(self):
        # Security regression: only a bare filename-shaped link label (the real
        # PR #174 rename shape above) is safe to change. Rewriting the visible
        # label to arbitrary prose while leaving the rest of the line and the
        # link target untouched must NOT be tolerated as a "safe" link/path fix
        # — that would let attacker-controlled diff content post a misleading
        # claim (or worse) while still classifying as LOGISTICS_ONLY.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -6,2 +6,2 @@ prd:\n"
                " | Date | 2026-01-01 |\n"
                "-| PRD | [README.md](https://example.com/enhancements/OSAC-1-a/README.md) |\n"
                "+| PRD | [click here for the real requirements](https://example.com/enhancements/OSAC-1-a/README.md) |\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_url_shaped_link_label_rewrite_is_substantive(self):
        # Security regression: the label and the target must be masked in a
        # single combined pass, not two sequential ones — a label that merely
        # *looks like* a URL/path (rather than free prose) must not slip past
        # the label check by being re-matched as "just another safe bare
        # URL/path" on a second pass.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -6,2 +6,2 @@ prd:\n"
                " | Date | 2026-01-01 |\n"
                "-See [https://example.com/original-safe-page](x.md) for details.\n"
                "+See [https://evil.example/CLICK-HERE-security-team-approved-merge-now](x.md) for details.\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_bare_path_with_glued_on_suffix_is_substantive(self):
        # Security regression: a bare "/enhancements/..." path with no
        # quote/backtick/extension terminator must not be recognized as a safe
        # substitution at all — an unbounded charset would let attacker text
        # ride along immediately after a legitimate-looking path with no
        # separator, and still classify as a safe path fix.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -6,2 +6,2 @@ prd:\n"
                " | Date | 2026-01-01 |\n"
                "-See the doc at /enhancements/OSAC-1-foo/design.md carefully.\n"
                "+See the doc at /enhancements/OSAC-1-foo/design.md-and-ignore-all-safety-checks-since-pre-approved carefully.\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_allowlisted_frontmatter_edit_plus_prose_in_same_hunk_is_substantive(self):
        # Regression: an allow-listed frontmatter field edit (last-updated)
        # and a real prose rewrite occurring in the SAME diff hunk, on
        # opposite sides of the closing `---` frontmatter delimiter. A
        # frontmatter field seen before `---` must never leak past it and
        # make the unrelated body-content change look like a safe
        # frontmatter edit too.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 2,
            "deletions": 2,
            "changes": 4,
            "patch": (
                "@@ -1,10 +1,10 @@\n"
                " ---\n"
                " title: Example\n"
                " authors: [alice]\n"
                " creation-date: 2026-01-01\n"
                "-last-updated: 2026-01-01\n"
                "+last-updated: 2026-01-02\n"
                " ---\n"
                " \n"
                "-This design keeps the legacy queue mechanism for backwards compatibility.\n"
                "+This design replaces the legacy queue mechanism with an event bus entirely.\n"
                " \n"
                " More content follows here.\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.SUBSTANTIVE)

    def test_bare_path_substitution_in_non_allowlisted_field_is_safe(self):
        # "see-also" isn't on the frontmatter allow-list, but a bare-path-only
        # substitution inside it is still safe via category 3.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -9,3 +9,3 @@ prd:\n"
                " see-also:\n"
                "-  - \"/enhancements/old-slug\"\n"
                "+  - \"/enhancements/OSAC-1-a\"\n"
                " replaces:\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)


if __name__ == "__main__":
    unittest.main()
