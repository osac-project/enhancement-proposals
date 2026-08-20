"""Build agentic-ci SkillConfig for test plan actions."""

try:
    from agentic_ci.skill import SkillConfig
except ImportError:
    SkillConfig = None


def build_skill_config(hooks, skill_name, skills_path,
                       pre_gates=None, post_gates=None):
    if SkillConfig is None:
        raise ImportError("agentic-ci not installed")

    return SkillConfig(
        skill_name=skill_name,
        skill_source=skills_path,

        prompt_builder=hooks.build_prompt,
        context_writer=hooks.write_context,
        verdict_loader=hooks.load_verdict,
        label_applier=hooks.apply_labels,
        cost_formatter=hooks.format_cost,

        pre_gates=pre_gates or [],
        post_gates=post_gates or [],

        backend_name="podman",
        harness_name="claude-code",
        container_image="quay.io/aipcc/agentic-ci/claude-runner:latest",
        container_env={},
        max_retries=2,
    )
