# AGENTS.md

## Project Context

This repository contains design documents (enhancement proposals) for the OSAC project. It is a documentation-only repository with no build dependencies.

**Do not create PRDs or design documents directly in this repo.** Use the PRD
and design workflows from a bootstrapped checkout of `osac-project/osac`
instead. Start the agent from that repository's root—the directory containing
`tools/bootstrap.sh` and `skills/`—not from this documentation repository.

- **PRD workflow**: `/prd:ingest` → `/prd:clarify` → `/prd:draft` → `/prd:publish`
- **Design workflow**: `/design:ingest` → `/design:draft` → `/design:publish`

Run `tools/bootstrap.sh` in that OSAC checkout if the workflows are not
installed. These workflows handle template selection, feature dimensions
context, section guidance, provenance, and publishing; the relevant publish
command writes the resulting documents to this `enhancement-proposals`
checkout. See the OSAC repository's `AGENTS.md` for the full instructions.

## Enhancement Proposals

See `README.md` for qualification heuristics, review/approval process, and enhancement lifecycle. `guidelines/prd_guide.md` and `guidelines/design_guide.md` hold the per-section authoring guidance, PRD vs design EP boundary, and OSAC personas that the `/prd` and `/design` skills above draft against — use them to review an existing `prd.md`/`design.md` or to support a human author on the manual workflow, not as a way to author these documents yourself.

## Validation

### Pre-Commit Hooks

GitHub Actions workflow (`.github/workflows/pre-commit.yaml`) runs on all PRs. Install locally:

```bash
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

Hooks:
- **trailing-whitespace** — removes trailing spaces
- **check-merge-conflict** — detects merge conflict markers
- **end-of-file-fixer** — ensures files end with newline
- **check-added-large-files** — prevents large binaries
- **check-case-conflict** — detects file name case conflicts
- **check-json** — validates JSON syntax
- **check-symlinks** — validates symbolic links
- **detect-private-key** — scans for accidentally committed secrets
- **yamllint** — validates `.yaml`/`.yml` files against `.yamllint.yaml` (does not lint YAML front matter in `.md` files)

### Automated EP Review

`.github/workflows/ep-review.yml` runs an AI-assisted review (`.github/scripts/ep_review.py`) on PRs and can be re-triggered by commenting `/review-ep`. It dispatches a `prd-review` skill for changed `prd.md` files and an `ep-review` skill for design documents. The workflow and `detect_skills()` recognize `design.md`, `Design.md`, `DESIGN.md`, and `enhancements/**/README.md`.

### Review Requirements

- Reviewers and approvers are defined in the `OWNERS` file
- Consensus required from domain-specific maintainers before merge
- Pre-commit CI must pass
- `Test Plan Score` must pass for the current PR head once its required-check
  rule is enabled. Every new or edited design needs a test plan; PRD/design
  edits re-score existing plans. PRD-only proposals without a design and
  unrelated changes receive an explicit not-applicable result.
- A numeric score is insufficient: every affected plan must have a valid Ready
  verdict under the current rubric. Revise, Rework, missing context and review
  errors block the check. Plan readiness does not establish test execution.
  CI requests an internal assessment with explicit policy facts; trusted code
  computes the public verdict from scores and the rubric's caps/vetoes. Missing
  or malformed policy facts fail the check. Existing public verdict fields are
  preserved; standalone skill scoring retains its documented output format.
- `/test-plan-score` retries scoring on the current head. `/test-plan-respond`
  does not pass the gate itself; same-repository revisions are scored again,
  and fork revisions must be applied before re-scoring.
  The CI revision step requests exact text replacements to preserve unchanged
  plan content. Missing, ambiguous or overlapping matches fail before a commit;
  the complete reconstructed plan is validated and then scored on its new SHA.
- Cite large source files as `component/path/file.go:100-160` to provide an
  explicit inclusive line excerpt from the pinned OSAC checkout. The review
  records omitted lines; an unqualified citation includes the full file.
  Required component guidance is always included in full. Invalid ranges and
  oversized context fail the check before any model request.
- Referenced `TC-{req}-{NN}` IDs must have unique Markdown case-definition
  headings. Audit tables and evidence-matrix mentions do not define cases.
  Missing or duplicate definitions fail before a model request; semantic
  completeness still requires assessment against the PRD/design.
- Keep each review within four affected enhancements and four plan files,
  counting both aliases and unchanged plans. Rendered prompts are capped at
  1,200,000 UTF-8 bytes each and 2,400,000 bytes per scoring batch before
  any scoring request. Split oversized changes or narrow cited excerpts.
