# AGENTS.md

## Project Context

This repository contains design documents (enhancement proposals) for the OSAC project. It is a documentation-only repository with no build dependencies.

**Do not create PRDs or design documents directly in this repo.** Use the osac-workspace AI workflows instead:

- **PRD workflow**: `/prd:ingest` → `/prd:clarify` → `/prd:draft` → `/prd:publish`
- **Design workflow**: `/design:ingest` → `/design:draft` → `/design:publish`

These workflows handle template selection, feature dimensions context, section guidance, and publishing. See `osac-workspace/AGENTS.md` for full instructions.

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
