"""Exercise the workflow's staging loop and both skills' actual lookup paths."""

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import ep_review


SHA = "a" * 40
WORKFLOW = Path(__file__).resolve().parents[1] / "workflows/ep-review.yml"
CONTEXT_NAMES = (
    "enclave-wizard-pipeline", "networking-decisions", "osac-dimensions", "review-patterns",
)


class StageContextTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.skills = self.root / "skills"
        forwarding = self.skills / ".design/context/osac-dimensions.md"
        forwarding.parent.mkdir(parents=True)
        forwarding.write_text("Shared skill context entry point\n")
        content = WORKFLOW.read_text()
        step = content.split("- name: Stage canonical OSAC context", 1)[1]
        step = step.split("- name: Stage enhancement-proposals content", 1)[0]
        self.script = textwrap.dedent(step.split("run: |\n", 1)[1]).replace(
            "/opt/skills", str(self.skills),
        )
        gh = self.root / "gh"
        gh.write_text('''#!/usr/bin/env python3
import os, sys
endpoint = sys.argv[2]
sha = "a" * 40
if endpoint == "repos/osac-project/osac/commits/main":
    print(sha)
    sys.exit(0)
assert endpoint.endswith("?ref=" + sha), endpoint
assert sys.argv[3:] == ["-H", "Accept: application/vnd.github.raw+json"]
path = endpoint.split("/contents/", 1)[1].split("?", 1)[0]
if path == os.environ.get("FAIL_DOC"):
    sys.exit(1)
if path != os.environ.get("EMPTY_DOC"):
    print("Full canonical context: " + path)
''')
        gh.chmod(0o755)

    def stage(self, **env):
        return subprocess.run(
            ["bash", "-c", self.script], capture_output=True, text=True,
            env={**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}",
                 "GITHUB_STEP_SUMMARY": str(self.root / "summary.md"), **env},
        )

    def assert_lookup_paths(self, root):
        for name in CONTEXT_NAMES:
            source = f"docs/agent-context/{name}.md"
            self.assertEqual((root / f"reference/agent-context/{name}.md").read_text(),
                             f"Full canonical context: {source}\n")
        for name in ("ARCHITECTURE", "CONVENTIONS", "personas", "INTEGRATION-TESTING"):
            source = f"docs/{name}.md"
            self.assertEqual((root / f"reference/{name}.md").read_text(),
                             f"Full canonical context: {source}\n")
        self.assertEqual((root / "reference/osac-context-sha.txt").read_text(), SHA + "\n")
        self.assertFalse((root / "docs").exists())
        self.assertFalse((root / "osac-docs").exists())
        self.assertEqual((root / ".design/context/osac-dimensions.md").read_text(),
                         "Shared skill context entry point\n")

    def test_full_documents_reach_both_review_workspaces_at_skill_lookup_paths(self):
        staged = self.stage()
        self.assertEqual(staged.returncode, 0, staged.stderr)
        self.assert_lookup_paths(self.skills)
        self.assertIn(SHA, (self.root / "summary.md").read_text())
        files = [{"filename": f"enhancements/OSAC-1-example/{name}"}
                 for name in ("prd.md", "design.md")]
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.root)
        with mock.patch.dict(os.environ, {"PR_NUMBER": "1", "PR_HEAD_SHA": SHA,
                                          "EP_REVIEW_SKIP_LOGISTICS": "false"}), \
                mock.patch.object(ep_review, "SKILLS_PATH", str(self.skills)), \
                mock.patch.object(ep_review, "get_changed_files", return_value=files), \
                mock.patch.object(ep_review, "gh", return_value=json.dumps({"headRefOid": SHA})), \
                mock.patch.object(ep_review, "EPHooks") as hooks, \
                mock.patch.object(ep_review, "run_review") as review:
            hooks.return_value.check_pr_state.return_value = None
            ep_review.main()
        self.assertEqual([call.args[1] for call in review.call_args_list],
                         ["prd-review", "design-review"])
        for call in review.call_args_list:
            self.assert_lookup_paths(call.args[-1])

    def test_failed_or_empty_required_download_stops_staging(self):
        for variable in ("FAIL_DOC", "EMPTY_DOC"):
            with self.subTest(variable=variable):
                staged = self.stage(**{variable: "docs/INTEGRATION-TESTING.md"})
                self.assertNotEqual(staged.returncode, 0)
                self.assertFalse((self.skills / "reference/osac-context-sha.txt").exists())


if __name__ == "__main__":
    unittest.main()
