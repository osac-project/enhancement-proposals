"""Regression coverage for EP skill-source traceability."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_REPOSITORY = "osac-project/osac-ai-skills"
WORKFLOWS = {
    "EP Review": (
        ".github/workflows/ep-review.yml",
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
    ),
    "Test Plan Review": (
        ".github/workflows/test-plan-review.yml",
        "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
    ),
}


def extract_step(content, step_name):
    start = content.index(f"      - name: {step_name}\n")
    end = content.find("\n      - name:", start + 1)
    return content[start:end if end != -1 else None]


class SkillSourceTraceabilityTests(unittest.TestCase):
    def test_workflows_validate_then_log_the_resolved_skills_commit(self):
        for workflow_name, (workflow_path, _) in WORKFLOWS.items():
            with self.subTest(workflow=workflow_name):
                content = (REPO_ROOT / workflow_path).read_text()
                verify_step = extract_step(content, "Verify skills checkout")

                self.assertIn(
                    'skills_path="$GITHUB_WORKSPACE/osac-ai-skills"',
                    verify_step,
                )
                self.assertIn(
                    '''skills_sha="$(git -C "$skills_path" rev-parse --verify "HEAD^{commit}")"
          if ! [[ "$skills_sha" =~ ^[0-9a-f]{40}$ ]]; then
            echo "::error::osac-ai-skills resolved to an invalid commit SHA: $skills_sha"
            exit 1
          fi
          echo "Resolved osac-ai-skills commit: ${skills_sha}"
          {
            echo "### OSAC AI skills"
            echo
            echo "Resolved osac-ai-skills commit: ${skills_sha}"
          } >> "$GITHUB_STEP_SUMMARY"''',
                    verify_step,
                )

    def test_private_skills_checkout_uses_scoped_token_without_persisting_it(self):
        for workflow_name, (workflow_path, checkout_sha) in WORKFLOWS.items():
            with self.subTest(workflow=workflow_name):
                content = (REPO_ROOT / workflow_path).read_text()
                checkout_step = extract_step(content, "Checkout OSAC AI skills")

                self.assertIn(f"uses: actions/checkout@{checkout_sha}", checkout_step)
                self.assertIn(f"repository: {SKILLS_REPOSITORY}", checkout_step)
                self.assertIn("token: ${{ secrets.OSAC_AI_SKILLS_READ_TOKEN }}", checkout_step)
                self.assertIn("path: osac-ai-skills", checkout_step)
                self.assertIn("persist-credentials: false", checkout_step)
                self.assertNotIn("git clone", checkout_step)

    def test_ep_review_keeps_required_skill_validation(self):
        content = (REPO_ROOT / ".github/workflows/ep-review.yml").read_text()

        self.assertIn("for s in prd-review design-review; do", content)
        verify_step = extract_step(content, "Verify skills checkout")
        self.assertIn('"$skills_path/skills/$s/SKILL.md"', verify_step)
        self.assertIn(
            "EP_REVIEW_SKILLS_PATH: ${{ github.workspace }}/osac-ai-skills",
            content,
        )
        self.assertIn(
            "TP_REVIEW_SKILLS_PATH: ${{ github.workspace }}/osac-ai-skills",
            (REPO_ROOT / ".github/workflows/test-plan-review.yml").read_text(),
        )


if __name__ == "__main__":
    unittest.main()
