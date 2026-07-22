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
    def _validate(
        self,
        paths,
        base_sha,
        existing_at_base,
        base_ref_exists=True,
        live_base_ref=None,
        live_base_ref_exists=True,
        existing_at_live_base=frozenset(),
    ):
        def fake_ref_exists(ref):
            if ref == base_sha:
                return base_ref_exists
            if ref == live_base_ref:
                return live_base_ref_exists
            return False

        def fake_path_exists_at_ref(ref, path):
            if ref == live_base_ref:
                return path in existing_at_live_base
            return path in existing_at_base

        with patch.object(cen, "ref_exists", side_effect=fake_ref_exists), \
                patch.object(
                    cen, "path_exists_at_ref", side_effect=fake_path_exists_at_ref,
                ):
            return cen.validate_paths(paths, base_sha, live_base_ref)

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

    def test_bad_name_violation_includes_example_and_doc_pointer(self):
        # The message must give a concrete example (not just the abstract
        # OSAC-<jira-key>-<slug> placeholder) and point to CONTRIBUTING.md,
        # since this same generic template previously fired identically for
        # unrelated failure reasons (missing prefix, missing slug,
        # zero-padding, bad dashes) with no way to tell them apart.
        violations = self._validate(
            paths=["enhancements/storage-network/prd.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertIn("OSAC-1110-storage-tier-api", violations[0])
        self.assertIn("CONTRIBUTING.md", violations[0])

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

    def test_new_directory_with_unrecognized_prefix_is_still_flagged(self):
        violations = self._validate(
            paths=["enhancements/JIRA-123-example-feature/prd.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("JIRA-123-example-feature", violations[0])

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

    def test_no_base_sha_is_advisory_only_and_flags_nothing(self):
        with redirect_stderr(io.StringIO()) as captured:
            violations = cen.validate_paths(
                ["enhancements/networking/design.md"], None,
            )
        self.assertEqual(violations, [])
        self.assertIn("no pr base sha available", captured.getvalue().lower())

    def test_no_base_sha_does_not_catch_new_bad_name_either(self):
        # Documents the accepted tradeoff: without a base SHA, local runs
        # can't distinguish new from pre-existing, so enforcement is
        # skipped entirely — even for a genuinely new, badly-named
        # directory. CI (which always sets the base SHA) is the real gate.
        with redirect_stderr(io.StringIO()):
            violations = cen.validate_paths(
                ["enhancements/storage-network/prd.md"], None,
            )
        self.assertEqual(violations, [])

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

    def test_pre_existing_on_live_main_but_absent_at_stale_base_sha_is_not_flagged(self):
        # Reproduces the false positive seen on PR #121: a directory merged
        # by an unrelated PR after this PR's base SHA was last captured is
        # absent at the stale base_sha but present on the live tip of main
        # — it must still be recognized as grandfathered, not flagged as
        # "new" just because this PR's own history predates it.
        violations = self._validate(
            paths=["enhancements/storage-control-plane-osac-2872/prd.md"],
            base_sha="stale123",
            existing_at_base=set(),
            live_base_ref="origin/main",
            existing_at_live_base={"enhancements/storage-control-plane-osac-2872"},
        )
        self.assertEqual(violations, [])

    def test_new_directory_absent_from_both_refs_is_still_flagged(self):
        # The live-ref check is supplementary, not a blanket exemption —
        # a genuinely new, badly-named directory (absent from the stale
        # base SHA *and* from the live tip of main) must still be flagged.
        violations = self._validate(
            paths=["enhancements/storage-network/prd.md"],
            base_sha="stale123",
            existing_at_base=set(),
            live_base_ref="origin/main",
            existing_at_live_base=set(),
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("storage-network", violations[0])

    def test_live_base_ref_unresolvable_falls_back_to_base_sha_only(self):
        # If the live ref was never fetched (e.g. an older CI run before
        # this env var existed, or a checkout quirk), grandfathering falls
        # back to base-SHA-only behavior rather than erroring.
        violations = self._validate(
            paths=["enhancements/networking/design.md"],
            base_sha="abc123",
            existing_at_base={"enhancements/networking"},
            live_base_ref="origin/main",
            live_base_ref_exists=False,
        )
        self.assertEqual(violations, [])

    def test_pre_existing_on_live_main_but_absent_at_stale_base_sha_file_casing_is_not_reflagged(self):
        # Same false-positive class as the directory-grandfathering case
        # above, but for the filename-casing check specifically — it's a
        # separate code path (file_is_grandfathered) using the same
        # is_grandfathered() helper, so it needs its own coverage.
        path = "enhancements/OSAC-42-example-feature/DESIGN.md"
        violations = self._validate(
            paths=[path],
            base_sha="stale123",
            existing_at_base=set(),
            live_base_ref="origin/main",
            existing_at_live_base={
                "enhancements/OSAC-42-example-feature",
                path,
            },
        )
        self.assertEqual(violations, [])

    def test_unresolvable_base_sha_disables_live_ref_grandfathering_too(self):
        # The fail-closed guarantee ("grandfathering disabled, every path
        # validated as new") must hold in full: an unresolvable base SHA
        # can't partially fail closed by still trusting the live ref. Here
        # the live ref alone would grandfather the path if it were
        # consulted — it must not be.
        violations = self._validate(
            paths=["enhancements/networking/design.md"],
            base_sha="deadbeef",
            base_ref_exists=False,
            existing_at_base=set(),
            live_base_ref="origin/main",
            live_base_ref_exists=True,
            existing_at_live_base={"enhancements/networking"},
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("networking", violations[0])

    def test_new_directory_with_consecutive_dashes_is_flagged(self):
        violations = self._validate(
            paths=["enhancements/OSAC-1--foo/prd.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("OSAC-1--foo", violations[0])

    def test_new_directory_with_trailing_dash_is_flagged(self):
        violations = self._validate(
            paths=["enhancements/OSAC-1-foo-/prd.md"],
            base_sha="abc123",
            existing_at_base=set(),
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("OSAC-1-foo-", violations[0])

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

    def test_missing_base_sha_env_var_is_advisory_only(self):
        with patch.dict(os.environ, {}, clear=True), \
                redirect_stderr(io.StringIO()) as captured:
            exit_code = cen.main(["enhancements/storage-network/PRD.md"])
        self.assertEqual(exit_code, 0)
        self.assertIn("no pr base sha available", captured.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
