import io
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import check_ep_naming as cen


class TopLevelEnhancementDirTests(unittest.TestCase):
    def test_nested_path_returns_first_segment(self):
        self.assertEqual(
            cen.top_level_enhancement_dir("enhancements/OSAC-42-foo/design.md"),
            "OSAC-42-foo",
        )

    def test_path_outside_enhancements_returns_none(self):
        self.assertIsNone(cen.top_level_enhancement_dir("README.md"))
        self.assertIsNone(cen.top_level_enhancement_dir("guidelines/prd_template.md"))

    def test_bare_file_in_enhancements_returns_none(self):
        self.assertIsNone(cen.top_level_enhancement_dir("enhancements/stray-file.md"))


class ValidatePathsTests(unittest.TestCase):
    def _validate(self, paths, base_sha, existing_at_base, base_ref_exists=True):
        with patch.object(cen, "ref_exists", return_value=base_ref_exists), \
                patch.object(
                    cen, "path_exists_at_ref",
                    side_effect=lambda ref, path: path in existing_at_base,
                ):
            return cen.validate_paths(paths, base_sha)

    def test_grandfathered_directory_is_not_flagged(self):
        violations = self._validate(
            paths=["enhancements/networking/design.md"],
            base_sha="abc123",
            existing_at_base={"enhancements/networking"},
        )
        self.assertEqual(violations, [])

    def test_new_directory_with_bad_name_is_flagged(self):
        violations = self._validate(
            paths=["enhancements/storage-network/prd.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("storage-network", violations[0])

    def test_new_directory_with_zero_padded_key_is_flagged(self):
        violations = self._validate(
            paths=["enhancements/OSAC-000001-test-feature/prd.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("OSAC-000001-test-feature", violations[0])

    def test_new_directory_with_compliant_name_is_not_flagged(self):
        violations = self._validate(
            paths=["enhancements/OSAC-42-example-feature/design.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(violations, [])

    def test_new_file_with_wrong_case_is_flagged(self):
        for bad_name in ("PRD.md", "Design.md", "DESIGN.md"):
            with self.subTest(bad_name=bad_name):
                violations = self._validate(
                    paths=[f"enhancements/OSAC-42-example-feature/{bad_name}"],
                    base_sha="abc123",
                    existing_at_base=set(),
                )
                self.assertEqual(len(violations), 1)
                self.assertIn(bad_name, violations[0])

    def test_new_file_with_correct_case_is_not_flagged(self):
        for good_name in ("prd.md", "design.md"):
            with self.subTest(good_name=good_name):
                violations = self._validate(
                    paths=[f"enhancements/OSAC-42-example-feature/{good_name}"],
                    base_sha="abc123",
                    existing_at_base=set(),
                )
                self.assertEqual(violations, [])

    def test_edited_pre_existing_file_with_wrong_case_is_not_reflagged(self):
        path = "enhancements/cluster-version-api/DESIGN.md"
        violations = self._validate(
            paths=[path],
            base_sha="abc123",
            existing_at_base={"enhancements/cluster-version-api", path},
        )
        self.assertEqual(violations, [])

    def test_new_file_in_grandfathered_directory_is_still_checked_for_casing(self):
        violations = self._validate(
            paths=["enhancements/networking/PRD.md"],
            base_sha="abc123",
            existing_at_base={"enhancements/networking"},
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("PRD.md", violations[0])

    def test_no_base_sha_validates_everything_as_new(self):
        with redirect_stderr(io.StringIO()) as captured:
            violations = cen.validate_paths(
                ["enhancements/networking/design.md"], None,
            )
        self.assertEqual(len(violations), 1)
        self.assertIn("networking", violations[0])
        self.assertIn("grandfathering disabled", captured.getvalue().lower())

    def test_unresolvable_base_sha_falls_back_to_no_grandfathering(self):
        # path_exists_at_ref returns True here (i.e. the directory would be
        # grandfathered if base_sha were trusted) — this only passes if the
        # unresolvable ref actually resets base_sha to None internally,
        # rather than merely printing a warning while still grandfathering.
        with patch.object(cen, "ref_exists", return_value=False), \
                patch.object(cen, "path_exists_at_ref", return_value=True), \
                redirect_stderr(io.StringIO()) as captured:
            violations = cen.validate_paths(
                ["enhancements/networking/design.md"], "deadbeef",
            )
        self.assertEqual(len(violations), 1)
        self.assertIn("networking", violations[0])
        message = captured.getvalue().lower()
        self.assertIn("deadbeef", message)
        self.assertIn("fetch-depth", message)

    def test_path_outside_enhancements_is_ignored(self):
        violations = self._validate(
            paths=["README.md", "guidelines/prd_template.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(violations, [])


class MainTests(unittest.TestCase):
    def test_clean_input_returns_zero(self):
        env = {cen.BASE_SHA_ENV_VAR: "abc123"}
        with patch.dict(os.environ, env), \
                patch.object(cen, "ref_exists", return_value=True), \
                patch.object(cen, "path_exists_at_ref", return_value=True), \
                redirect_stderr(io.StringIO()):
            exit_code = cen.main(["enhancements/networking/design.md"])
        self.assertEqual(exit_code, 0)

    def test_violation_returns_one_and_prints_message(self):
        env = {cen.BASE_SHA_ENV_VAR: "abc123"}
        with patch.dict(os.environ, env), \
                patch.object(cen, "ref_exists", return_value=True), \
                patch.object(cen, "path_exists_at_ref", return_value=False), \
                redirect_stderr(io.StringIO()) as captured:
            exit_code = cen.main(["enhancements/storage-network/prd.md"])
        self.assertEqual(exit_code, 1)
        self.assertIn("storage-network", captured.getvalue())

    def test_missing_base_sha_env_var_falls_back_to_none(self):
        with patch.dict(os.environ, {}, clear=True), \
                redirect_stderr(io.StringIO()) as captured:
            exit_code = cen.main(["enhancements/networking/design.md"])
        self.assertEqual(exit_code, 1)
        self.assertIn("grandfathering disabled", captured.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
