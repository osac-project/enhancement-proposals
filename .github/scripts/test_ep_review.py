import shutil
import tempfile
import unittest
from pathlib import Path

import ep_review as er


class PrEnhancementSlugsTests(unittest.TestCase):
    def test_single_slug_multiple_files(self):
        files = [
            "enhancements/OSAC-2917-gpu-instance-types/design.md",
            "enhancements/OSAC-2917-gpu-instance-types/prd.md",
        ]
        self.assertEqual(
            er.pr_enhancement_slugs(files), {"OSAC-2917-gpu-instance-types"}
        )

    def test_multiple_slugs(self):
        files = [
            "enhancements/OSAC-1-a/design.md",
            "enhancements/OSAC-2-b/prd.md",
        ]
        self.assertEqual(
            er.pr_enhancement_slugs(files), {"OSAC-1-a", "OSAC-2-b"}
        )

    def test_unrelated_paths_ignored(self):
        files = [
            "guidelines/prd_template.md",
            "README.md",
            ".github/workflows/ep-review.yml",
        ]
        self.assertEqual(er.pr_enhancement_slugs(files), set())

    def test_bare_file_in_enhancements_ignored(self):
        # A file directly under enhancements/ (no slug subdirectory) is not
        # itself a slug.
        self.assertEqual(
            er.pr_enhancement_slugs(["enhancements/stray-file.md"]), set()
        )

    def test_mixed_related_and_unrelated(self):
        files = [
            "enhancements/OSAC-42-foo/design.md",
            "some/other/unrelated-file.go",
        ]
        self.assertEqual(er.pr_enhancement_slugs(files), {"OSAC-42-foo"})


class ExcludeOwnSlugFromReferenceLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.work_dir = Path(self.tmp) / "workdir-design-review"
        self.ref_root = self.work_dir / "enhancement-proposals" / "enhancements"

    def _make_slug_dir(self, slug, content="content"):
        d = self.ref_root / slug
        d.mkdir(parents=True)
        (d / "design.md").write_text(content)
        return d

    def test_own_slug_removed_unrelated_slug_survives(self):
        self._make_slug_dir(
            "OSAC-2917-gpu-instance-types", "stale pre-PR version"
        )
        self._make_slug_dir("networking", "unrelated reference design")
        files = ["enhancements/OSAC-2917-gpu-instance-types/design.md"]

        er.exclude_own_slug_from_reference_library(self.work_dir, files)

        self.assertFalse(
            (self.ref_root / "OSAC-2917-gpu-instance-types").exists()
        )
        self.assertTrue((self.ref_root / "networking").exists())

    def test_multiple_own_slugs_removed(self):
        self._make_slug_dir("OSAC-1-a")
        self._make_slug_dir("OSAC-2-b")
        self._make_slug_dir("unrelated")
        files = [
            "enhancements/OSAC-1-a/design.md",
            "enhancements/OSAC-2-b/prd.md",
        ]

        er.exclude_own_slug_from_reference_library(self.work_dir, files)

        self.assertFalse((self.ref_root / "OSAC-1-a").exists())
        self.assertFalse((self.ref_root / "OSAC-2-b").exists())
        self.assertTrue((self.ref_root / "unrelated").exists())

    def test_missing_reference_root_is_a_noop(self):
        # enhancement-proposals/enhancements/ doesn't exist at all (e.g. a
        # prd-review work_dir, which never needs the reference library).
        self.work_dir.mkdir(parents=True)
        files = ["enhancements/OSAC-2917-gpu-instance-types/design.md"]

        er.exclude_own_slug_from_reference_library(self.work_dir, files)

        self.assertFalse(self.ref_root.exists())

    def test_absent_slug_directory_is_a_noop(self):
        # The PR's own slug isn't present in the reference library at all
        # (e.g. a brand-new enhancement with no prior merged version).
        self._make_slug_dir("unrelated")
        files = ["enhancements/OSAC-brand-new/design.md"]

        er.exclude_own_slug_from_reference_library(self.work_dir, files)

        self.assertTrue((self.ref_root / "unrelated").exists())


class BuildTicketBaseTests(unittest.TestCase):
    """Real file-list shapes from #168/#172/#173/#174 — filenames only, no
    diff content needed for Phase A."""

    def test_pr_168_single_key_no_violations(self):
        files = ["enhancements/OSAC-1589-vm-worker-caas/prd.md"]
        pr = {"title": "OSAC-1589: PRD — VM Worker CaaS", "body": "", "author": {}, "labels": []}

        ticket = er.build_ticket_base(pr, "deadbeef", "168", files)

        self.assertEqual(ticket["jira_key"], "OSAC-1589")
        self.assertFalse(ticket["jira_key_ambiguous"])
        self.assertEqual(ticket["structure_violations"], [])

    def test_pr_172_single_key_no_violations(self):
        files = ["enhancements/OSAC-2872-storage-control-plane/design.md"]
        pr = {"title": "OSAC-2872: Design update", "body": "", "author": {}, "labels": []}

        ticket = er.build_ticket_base(pr, "deadbeef", "172", files)

        self.assertEqual(ticket["jira_key"], "OSAC-2872")
        self.assertFalse(ticket["jira_key_ambiguous"])
        self.assertEqual(ticket["structure_violations"], [])

    def test_pr_173_key_derived_from_path_not_title(self):
        # Real case: PR title references OSAC-2645, but the touched EP
        # directory is OSAC-1339-bcm-backend/ — the derived key must come
        # from the path, not the (unrelated) title.
        files = ["enhancements/OSAC-1339-bcm-backend/design.md"]
        pr = {
            "title": "OSAC-2645: Design — BCM Backend Integration for BMaaS",
            "body": "Relates to OSAC-2645",
            "author": {},
            "labels": [],
        }

        ticket = er.build_ticket_base(pr, "deadbeef", "173", files)

        self.assertEqual(ticket["jira_key"], "OSAC-1339")
        self.assertFalse(ticket["jira_key_ambiguous"])
        self.assertEqual(ticket["structure_violations"], [])

    def test_pr_174_multi_ep_rename_is_ambiguous(self):
        files = [
            "enhancements/OSAC-1002-catalog-items/README.md",
            "enhancements/OSAC-1002-catalog-items/ui-design.md",
            "enhancements/OSAC-1030-organizations/README.md",
            "enhancements/OSAC-1030-organizations/ui-design.md",
            "enhancements/OSAC-1034-vm-api-fields/README.md",
            "enhancements/OSAC-1050-dns-api/README.md",
            "enhancements/OSAC-1118-baremetal-instance-api/README.md",
            "enhancements/OSAC-1269-cluster-version-api/design.md",
            "enhancements/OSAC-1330-type-safe-resource-references/design.md",
            "enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/design.md",
            "enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/prd.md",
            "enhancements/OSAC-1567-secret-management/design.md",
            "enhancements/OSAC-1732-repository-consolidation/README.md",
            "enhancements/OSAC-979-image-management/README.md",
            "enhancements/OSAC-985-metering-and-usage-tracking/design.md",
            "enhancements/OSAC-985-metering-and-usage-tracking/prd.md",
        ]
        pr = {
            "title": "OSAC-2870: rename 5 more EPs per Jira-content cross-check",
            "body": "",
            "author": {},
            "labels": [],
        }

        ticket = er.build_ticket_base(pr, "deadbeef", "174", files)

        self.assertIsNone(ticket["jira_key"])
        self.assertTrue(ticket["jira_key_ambiguous"])
        self.assertEqual(ticket["structure_violations"], [])

    def test_missing_key_prefix_surfaces_as_structure_violation(self):
        files = ["enhancements/vm-worker-nodes/prd.md"]
        pr = {"title": "", "body": "", "author": {}, "labels": []}

        ticket = er.build_ticket_base(pr, "deadbeef", "999", files)

        self.assertIsNone(ticket["jira_key"])
        self.assertFalse(ticket["jira_key_ambiguous"])
        self.assertEqual(len(ticket["structure_violations"]), 1)


if __name__ == "__main__":
    unittest.main()
