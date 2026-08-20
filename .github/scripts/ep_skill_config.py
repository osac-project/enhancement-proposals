"""Build agentic-ci SkillConfig for EP review."""

try:
    from agentic_ci.skill import SkillConfig
except ImportError:
    SkillConfig = None


def _forward_ticket(hook):
    """Adapt a hook that expects `ticket=` to agentic_ci.skill.run_skill's
    calling convention for prompt_builder/label_applier.

    run_skill() only forwards its own `ticket=` argument to
    pre_gates/context_writer/extension_config_writer — prompt_builder and
    label_applier are called with **extra_kwargs only, so a `ticket=...`
    passed into run_skill() never reaches them. ep_review.py's run_review()
    works around this by also passing the ticket dict under the plain kwarg
    name `osac_ticket`, which *does* survive into **extra_kwargs; this
    wrapper renames it back to `ticket` so hooks.build_prompt/apply_labels
    see the same `ticket=` keyword regardless of which pipeline stage calls
    them.
    """

    def wrapped(**kw):
        kw["ticket"] = kw.pop("osac_ticket", None)
        return hook(**kw)

    return wrapped


def build_skill_config(hooks, skill_name, skills_path):
    if SkillConfig is None:
        raise ImportError("agentic-ci not installed")

    return SkillConfig(
        skill_name=skill_name,
        skill_source=skills_path,

        prompt_builder=_forward_ticket(hooks.build_prompt),
        context_writer=hooks.write_pr_context,
        verdict_loader=hooks.load_verdict,
        label_applier=_forward_ticket(hooks.apply_labels),
        cost_formatter=hooks.format_cost,

        pre_gates=[hooks.check_pr_state],
        post_gates=[hooks.validate_scores],

        backend_name="podman",
        harness_name="claude-code",
        container_image="quay.io/aipcc/agentic-ci/claude-runner:latest",
        container_env={},
        max_retries=2,
    )
