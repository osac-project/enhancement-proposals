"""Regression coverage for EP skill-source traceability."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_REPOSITORY = "https://github.com/osac-project/osac-ai-skills"
WORKFLOWS = {
    "EP Review": (".github/workflows/ep-review.yml", "/opt/skills", "Clone skills"),
    "Test Plan Review": (
        ".github/workflows/test-plan-review.yml",
        "/opt/test-plan-skills",
        "Clone test plan skills",
    ),
}


class SkillSourceTraceabilityTests(unittest.TestCase):
    def test_workflows_validate_then_log_the_resolved_skills_commit(self):
        for workflow_name, (workflow_path, checkout_path, _) in WORKFLOWS.items():
            with self.subTest(workflow=workflow_name):
                content = (REPO_ROOT / workflow_path).read_text()

                self.assertIn(
                    f"git clone --depth 1 {SKILLS_REPOSITORY} {checkout_path}",
                    content,
                )
                self.assertIn(
                    f'''skills_sha="$(git -C {checkout_path} rev-parse --verify "HEAD^{{commit}}")"
          if ! [[ "$skills_sha" =~ ^[0-9a-f]{{40}}$ ]]; then
            echo "::error::osac-ai-skills resolved to an invalid commit SHA: $skills_sha"
            exit 1
          fi
          echo "Resolved osac-ai-skills commit: ${{skills_sha}}"
          {{
            echo "### OSAC AI skills"
            echo
            echo "Resolved osac-ai-skills commit: ${{skills_sha}}"
          }} >> "$GITHUB_STEP_SUMMARY"''',
                    content,
                )

    def test_private_skills_clone_uses_step_scoped_read_token(self):
        for workflow_name, (workflow_path, _, clone_step_name) in WORKFLOWS.items():
            with self.subTest(workflow=workflow_name):
                content = (REPO_ROOT / workflow_path).read_text()
                start = content.index(f"      - name: {clone_step_name}\n")
                end = content.find("\n      - name:", start + 1)
                clone_step = content[start:end if end != -1 else None]

                self.assertIn(
                    "OSAC_AI_SKILLS_READ_TOKEN: "
                    "${{ secrets.OSAC_AI_SKILLS_READ_TOKEN }}",
                    clone_step,
                )
                self.assertIn(
                    'GIT_CONFIG_KEY_0="http.https://github.com/'
                    'osac-project/osac-ai-skills/.extraheader"',
                    clone_step,
                )
                self.assertIn(
                    'GIT_CONFIG_VALUE_0="AUTHORIZATION: basic ${skills_auth}"',
                    clone_step,
                )
                self.assertIn(
                    "unset skills_auth OSAC_AI_SKILLS_READ_TOKEN", clone_step
                )

    def test_ep_review_keeps_required_skill_validation(self):
        content = (REPO_ROOT / ".github/workflows/ep-review.yml").read_text()

        self.assertIn("for s in prd-review design-review; do", content)
        self.assertIn('"/opt/skills/skills/$s/SKILL.md"', content)


if __name__ == "__main__":
    unittest.main()
