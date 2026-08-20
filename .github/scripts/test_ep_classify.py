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

    def test_link_text_and_target_both_changing_is_still_safe(self):
        # Real shape from PR #174: a markdown link where both the visible
        # text and the target path change, but nothing outside the link does.
        files = [{
            "filename": "enhancements/OSAC-1-a/design.md",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": (
                "@@ -6,2 +6,2 @@ prd:\n"
                " | Date | 2026-01-01 |\n"
                "-| PRD | [old-name.md](https://example.com/enhancements/old-slug/README.md) |\n"
                "+| PRD | [README.md](https://example.com/enhancements/OSAC-1-a/README.md) |\n"
            ),
        }]
        self.assertEqual(ec.classify_logistics_only(files), ec.LOGISTICS_ONLY)

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
