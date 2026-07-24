To get started with this template:
1. **Create a directory.** Create a directory inside `enhancements/` using
   the naming convention `OSAC-NNNN-feature-slug`, where `OSAC-NNNN` is the
   Jira **Feature**-level key exactly as it appears in Jira (no
   zero-padding), followed by a kebab-case slug derived from the feature
   summary. See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full
   convention and examples.
1. **Make a copy of this template.** Copy this file into your directory
   as `prd.md`.
1. **Fill out the metadata** at the top (the table below).
1. **Fill out each section.** If a section does not apply, mark it `N/A`
   rather than removing it.
1. **Create a pull request** against the main branch of this repository.
1. After the PRD is merged, create the design EP (`design.md`) in the
   same directory. See [design_template.md](design_template.md).

**Using the `/prd` skill (recommended):** If you are using an AI-assisted
development tool (Claude Code, Cursor, or similar), use the `/prd` workflow
instead of copying this template manually. Run `/prd:ingest` with your Jira
ticket to start the guided flow: ingest, clarify, draft, publish. The skill
produces a PRD that follows this template and publishes it as a PR.

For detailed authoring guidance, PRD vs design EP boundaries, personas,
and good/bad examples, see [prd_guide.md](prd_guide.md).

# {Title}

| Field       | Value   |
|-------------|---------|
| Author(s)   |         |
| Jira        |         |
| Date        |         |

## Problem Statement

{Who is affected, what pain exists today, and what happens if this is not addressed?}

## In Scope

- {What this work delivers}

## Out of Scope

- {Explicitly excluded to prevent scope creep}

## User Stories

{Group by persona or workflow. Ground each story in explicit use cases — name
the concrete artifacts, workflows, or scenarios, not generic capabilities.
"I want to store SSH keypairs and OIDC client secrets" is actionable;
"I want to create and manage secrets" is too vague to review. See
[prd_guide.md](prd_guide.md) for OSAC personas and more good/bad examples.}

### {Persona or workflow name}

- As a {persona}, I want {capability} so that {outcome}.

## Assumptions
<!-- Optional: omit if no unverified assumptions underpin the requirements -->

- {Statement believed to be true but not yet verified}

## Dependencies
<!-- Optional: omit if source material identifies no external dependencies -->

- **{Dependency name}:** {What it provides and any ordering constraints}
