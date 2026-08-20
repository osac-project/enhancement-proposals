import unittest

import ep_paths as ep


class DeriveFeatureKeyTests(unittest.TestCase):
    def test_single_valid_dir_returns_key(self):
        files = ["enhancements/OSAC-1589-vm-worker-nodes/prd.md"]
        self.assertEqual(ep.derive_feature_key(files), "OSAC-1589")

    def test_multiple_files_same_dir_returns_same_key(self):
        files = [
            "enhancements/OSAC-1589-vm-worker-nodes/prd.md",
            "enhancements/OSAC-1589-vm-worker-nodes/design.md",
        ]
        self.assertEqual(ep.derive_feature_key(files), "OSAC-1589")

    def test_two_distinct_dirs_is_ambiguous(self):
        files = [
            "enhancements/OSAC-1589-vm-worker-nodes/prd.md",
            "enhancements/OSAC-2872-other-feature/design.md",
        ]
        self.assertEqual(ep.derive_feature_key(files), "ambiguous")

    def test_no_enhancements_path_returns_none(self):
        files = ["README.md", ".github/workflows/ep-review.yml"]
        self.assertIsNone(ep.derive_feature_key(files))

    def test_legacy_non_prefixed_dir_returns_none_not_ambiguous(self):
        files = ["enhancements/bare-metal-fulfillment/README.md"]
        self.assertIsNone(ep.derive_feature_key(files))

    def test_mixed_legacy_and_keyed_dir_returns_single_key(self):
        files = [
            "enhancements/bare-metal-fulfillment/README.md",
            "enhancements/OSAC-1589-vm-worker-nodes/prd.md",
        ]
        self.assertEqual(ep.derive_feature_key(files), "OSAC-1589")

    def test_bare_file_in_enhancements_ignored(self):
        files = ["enhancements/stray-file.md"]
        self.assertIsNone(ep.derive_feature_key(files))

    def test_canonical_doc_plus_unrelated_non_canonical_file_is_not_ambiguous(self):
        # Incidental drive-by edit to another EP's non-canonical file (e.g.
        # a repo-wide link fix touching README.md) must not downgrade the
        # unambiguous key of the actual reviewed document.
        files = [
            "enhancements/OSAC-100-a/design.md",
            "enhancements/OSAC-999-other/README.md",
        ]
        self.assertEqual(ep.derive_feature_key(files), "OSAC-100")

    def test_two_canonical_docs_in_different_dirs_is_ambiguous(self):
        files = [
            "enhancements/OSAC-100-a/design.md",
            "enhancements/OSAC-999-other/prd.md",
        ]
        self.assertEqual(ep.derive_feature_key(files), "ambiguous")

    def test_no_canonical_doc_touched_returns_none(self):
        files = [
            "enhancements/OSAC-100-a/README.md",
            "enhancements/OSAC-100-a/ui-design.md",
        ]
        self.assertIsNone(ep.derive_feature_key(files))


class ValidateEpStructureTests(unittest.TestCase):
    def test_canonical_pair_no_violations(self):
        files = [
            "enhancements/OSAC-1589-vm-worker-nodes/prd.md",
            "enhancements/OSAC-1589-vm-worker-nodes/design.md",
        ]
        self.assertEqual(ep.validate_ep_structure(files), [])

    def test_legacy_readme_only_dir_no_violations(self):
        files = ["enhancements/bare-metal-fulfillment/README.md"]
        self.assertEqual(ep.validate_ep_structure(files), [])

    def test_prd_only_dir_no_violations(self):
        files = ["enhancements/OSAC-1589-vm-worker-caas/prd.md"]
        self.assertEqual(ep.validate_ep_structure(files), [])

    def test_extra_non_canonical_file_no_violations(self):
        files = [
            "enhancements/OSAC-1589-vm-worker-nodes/prd.md",
            "enhancements/OSAC-1589-vm-worker-nodes/design.md",
            "enhancements/OSAC-1589-vm-worker-nodes/ui-design.md",
        ]
        self.assertEqual(ep.validate_ep_structure(files), [])

    def test_missing_key_prefix_is_a_violation(self):
        files = ["enhancements/vm-worker-nodes/prd.md"]
        violations = ep.validate_ep_structure(files)
        self.assertEqual(len(violations), 1)
        self.assertIn("vm-worker-nodes", violations[0])

    def test_wrong_filename_casing_is_a_violation(self):
        files = ["enhancements/OSAC-1589-vm-worker-nodes/PRD.md"]
        violations = ep.validate_ep_structure(files)
        self.assertEqual(len(violations), 1)
        self.assertIn("lowercase", violations[0])

    def test_orphan_prd_directly_under_enhancements_is_a_violation(self):
        files = ["enhancements/prd.md"]
        violations = ep.validate_ep_structure(files)
        self.assertEqual(len(violations), 1)
        self.assertIn("enhancements/prd.md", violations[0])


if __name__ == "__main__":
    unittest.main()
