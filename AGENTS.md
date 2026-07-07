# AGENTS.md

## Project Context

This repository contains design documents (enhancement proposals) for the OSAC project. Each enhancement lives in its own directory under `enhancements/` and follows the OpenShift enhancement proposal format with YAML front matter and structured Markdown sections.

Enhancements provide a rally point to discuss, debate, and reach consensus for how OSAC enhancements are introduced. Given the breadth of the projects and repositories in the OSAC solution (third-party dependencies and de novo code), this centralized repository describes enhancements via actionable design proposals. Enhancements may span multiple releases and form the basis of the roadmap.

**Key characteristics:**
- Documentation-only repository—no build dependencies
- Development dependency: `pre-commit` (install via `pip install pre-commit`)
- Static Markdown files published via git
- Template-driven structure enforced by pre-commit hooks
- Fork-based PR workflow with mandatory reviews
- Enhancement proposals require consensus from domain-specific maintainers before implementation and acceptance

## Repository Structure

```text
enhancement-proposals/
├── enhancements/              # All enhancement proposals
│   ├── <feature-slug>/        # One directory per enhancement
│   │   ├── README.md          # Design document (main EP file)
│   │   ├── prd.md             # Optional PRD (product requirements)
│   │   └── <assets>/          # Optional diagrams, examples
│   └── ...
├── guidelines/
│   └── enhancement_template.md  # Template for new enhancements
├── OWNERS                     # Reviewers and approvers
├── .yamllint.yaml             # YAML front matter validation
└── .pre-commit-config.yaml    # Validation hooks
```

There are 28 enhancement directories covering networking, storage, VMs, tenant onboarding, and platform features.

## Enhancement Structure

### Directory Layout

Each enhancement uses a lowercase-with-dashes directory name under `enhancements/`:

```text
enhancements/<feature-slug>/
├── README.md       # Design document (required)
├── prd.md          # PRD (optional, used in two-stage PRD→Design workflow)
└── <assets>/       # Optional subdirectories for diagrams, code examples
```

**Examples:**
- `enhancements/networking-ui-vmaas-scope/`
- `enhancements/storage-backend-osac-1111/`
- `enhancements/tenant-onboarding/`

### Required Files

**Design Document**
- Main enhancement proposal file (filename varies by enhancement—see below)
- YAML front matter + structured Markdown sections
- Follows template at `guidelines/enhancement_template.md`
- **File naming**: Several conventions exist in the codebase:
  - `README.md` (21 enhancements) — the dominant standard
  - `design.md` (3 enhancements: `storage-backend-osac-1111`, `storage-tier-OSAC-1110`, `tenant-storage-onboarding-OSAC-23`)
  - `Design.md` (1 enhancement: `networking-ui-vmaas-scope`, renamed from README.md in OSAC-1425)
  - `DESIGN.md` (1 enhancement: `cluster-version-api`, renamed from README.md)
  - `prd.md` only, no design doc yet (2 enhancements: `caas-cluster-storage`, `cluster-and-vm-provisioning-wizard`) — mid-workflow, PRD stage complete but design stage not started
- **Recommendation**: Use `README.md` for new enhancements unless project guidance changes

**`prd.md`** (Optional)
- Product requirements document
- Used in two-stage PRD→Design workflow
- Same YAML front matter structure as design doc
- Lives in the same directory as `README.md`

## File Conventions

### YAML Front Matter

Required fields in all enhancement documents:

```yaml
---
title: Short Enhancement Title
authors:
  - "@github-username"
creation-date: 2026-01-15
last-updated: 2026-01-20
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1234
---
```

Optional fields:
- `prd: ./prd.md` — Link to PRD file in same directory
- `see-also: ["./related-ep/README.md"]` — Related enhancements
- `replaces: ["./old-ep/README.md"]` — Superseded proposals
- `superseded-by: ./new-ep/README.md` — When deprecated

### Content Structure

Follow the template at `guidelines/enhancement_template.md`:

1. **Summary** — One-paragraph overview
2. **Motivation** — User stories, goals, non-goals
3. **Proposal** — Technical design, workflow description, API extensions, implementation details, risks/mitigations, drawbacks
4. **Alternatives (Not Implemented)** — Considered approaches and why they were rejected
5. **Open Questions** [optional]
6. **Test Plan** — Unit, integration, E2E coverage
7. **Graduation Criteria** — Alpha/Beta/GA milestones, including removal of deprecated features
8. **Upgrade / Downgrade Strategy**, **Version Skew Strategy**, **Support Procedures**
9. **Infrastructure Needed** [optional]

Note: this template does not have an "Implementation History" section (unlike some other OpenShift-style EP templates)—track changes via the `last-updated` field and PR history instead.

### Naming Conventions

- **Enhancement directories**: lowercase-with-dashes (e.g., `networking-ui-vmaas-scope`)
- **Design doc**: `README.md` (recommended), or `design.md` / `Design.md` / `DESIGN.md` (existing variants)
- **PRD**: `prd.md`
- **Branch names**: `prd/<TICKET>` or `design/<TICKET>` (e.g., `design/OSAC-1234`)

**Note on file naming standardization**: If working with an enhancement that uses a non-standard design document name (`design.md`, `Design.md`, or `DESIGN.md`), maintain the existing name for consistency within that enhancement unless explicitly asked to standardize it.

## Enhancement Proposals

### What Qualifies as an Enhancement?

A rough heuristic for an enhancement is anything that:

- includes addition or removal of significant capabilities
- impacts upgrade/downgrade
- needs significant effort to complete
- requires consensus/code across multiple domains/repositories
- proposes adding a new user-facing component
- has phases of maturity (Dev Preview, Tech Preview, GA)
- demands formal documentation to utilize

It is unlikely to require an enhancement if it:

- fixes a bug
- adds more testing
- internally refactors a code or component only visible to that components domain
- minimal impact to distribution as a whole

If you are not sure if the proposed work requires an enhancement, file an issue and ask.

### Review and Approval Process

The author of an enhancement is responsible for managing it through the review and approval process, including soliciting feedback on the pull request and in meetings, if necessary.

The set of reviewers for an enhancement proposal can be anyone that has an interest in this work or the expertise to provide a useful input/assessment. At a minimum, the reviewers must include a representative of any team that will need to do work for this proposal, or whose team will own/support the resulting implementation. Be mindful of the workload of reviewers, however, and the challenge of finding consensus as the group of reviewers grows larger. Clearly indicating what aspect of the proposal you expect each reviewer to be concerned with will allow them to focus their reviews.

An enhancement proposal is formally accepted when reviewers have reached consensus on the proposal and it has been merged into the main branch of the repository.

Approval of an enhancement proposal does not guarantee implementation. Developers have existing commitments that may take priority over some (or all) enhancement proposals.

### Helping Speed Up the Review Process

Enhancements should have agreement from all stakeholders prior to being approved and merged. Reviews are not time-boxed. If it is not possible to attract the attention of enough of the right maintainers to act as reviewers, that is a signal that the project's rate of change is maxed out. With that said, there are a few things that authors can do to help keep the conversation moving along:

1. Respond to comments quickly, so that a reviewer can tell you are engaged.
2. Push update patches, rather than force-pushing a replacement, to make it easier for reviewers to see what you have changed. Use descriptive commit messages on those updates, or plan to squash the commits when the pull request merges.
3. If the conversation otherwise seems stuck, pinging reviewers on Slack can be used to remind them to look at updates. It's generally appropriate to give people at least a business day or two to respond in the GitHub thread first, before reaching out to them directly on Slack, so that they can manage their work queue and disruptions.

### Enhancement Lifecycle

An enhancement begins life as a pull request against the enhancement-proposals repository. The pull request is reviewed by the core development team and other interested members of the community.

An enhancement proposal is accepted when the pull request has been merged into the main branch of the enhancement proposals repository. Ideally pull requests with enhancement proposals will be merged before significant coding work begins, since this avoids having to rework the implementation if the design changes as well as arguing in favor of accepting a design simply because it is already implemented.

After an enhancement proposal has been accepted and the implementation work is substantially complete, it may be necessary to update the design document in the OSAC docs repository.

## Development Workflow

### Creating a New Enhancement

1. **Create directory structure**:
   ```bash
   mkdir -p enhancements/<feature-slug>
   ```

2. **Copy template** (for design doc):
   ```bash
   cp guidelines/enhancement_template.md enhancements/<feature-slug>/README.md
   ```

3. **Fill YAML front matter**:
   - Set `title`, `authors`, `creation-date`, `tracking-link`
   - Add `prd: ./prd.md` if using two-stage workflow

4. **Write content**:
   - Follow template sections
   - Reference existing enhancements for examples
   - Keep diagrams and examples in subdirectories if needed

### Two-Stage PRD→Design Workflow

When using the `/prd` and `/design` AI workflows:

1. **PRD Phase**:
   - Create `enhancements/<feature-slug>/prd.md`
   - Branch: `prd/<TICKET>`
   - Push to `fork`, create PR from `fork/prd/<TICKET>` to `origin/main`

2. **Design Phase**:
   - Create `enhancements/<feature-slug>/README.md` in the same directory
   - Reference PRD in YAML front matter: `prd: ./prd.md`
   - Branch: `design/<TICKET>`
   - Push to `fork`, create PR from `fork/design/<TICKET>` to `origin/main`

Both files live in the same feature directory—no separate `prd/` subdirectory.

### Editing Existing Enhancements

1. **Update `last-updated` field** in YAML front matter
2. **Run pre-commit hooks** before committing (see Validation section)

## PR Workflow

### Fork-Based Workflow

**Remotes:**
- `origin` — upstream osac-project/enhancement-proposals (read-only, never push here)
- `fork` — your fork (push target for all work)

**Steps:**
1. Create a feature branch from `main`:
   ```bash
   git checkout -b prd/OSAC-1234
   # or
   git checkout -b design/OSAC-1234
   ```

2. Make changes, commit with DCO sign-off:
   ```bash
   git commit -s -m "OSAC-1234: Add storage network enhancement"
   ```

3. For AI-assisted commits, add trailer:
   ```text
   OSAC-1234: Add storage network enhancement

   Assisted-by: Claude Code <noreply@anthropic.com>
   ```

4. Push to fork remote:
   ```bash
   git push fork prd/OSAC-1234
   ```

5. Create PR from `fork/<branch>` to `origin/main`

### Review Requirements

- **Multiple reviewers required** — reviewers defined in `OWNERS` file:
  - Approvers: architects and leads
  - Reviewers: broader team
- **Consensus required** before merge (all reviewers must agree or abstain)
- **Pre-commit CI must pass** (yamllint, whitespace checks)

### Branch Naming

- PRD work: `prd/<TICKET>` (e.g., `prd/OSAC-1234`)
- Design work: `design/<TICKET>` (e.g., `design/OSAC-1234`)
- Quick fixes: `fix/<description>` (e.g., `fix/typo-in-networking-ep`)

## Validation

### Pre-Commit Hooks

GitHub Actions workflow (`.github/workflows/pre-commit.yaml`) runs on all PRs:

1. **trailing-whitespace** — Removes trailing spaces
2. **check-merge-conflict** — Detects merge conflict markers
3. **end-of-file-fixer** — Ensures files end with newline
4. **check-added-large-files** — Prevents large binaries
5. **check-case-conflict** — Detects file name case conflicts
6. **check-json** — Validates JSON syntax (if present)
7. **check-symlinks** — Validates symbolic links
8. **detect-private-key** — Scans for accidentally committed secrets
9. **yamllint** — Validates `.yaml`/`.yml` files against `.yamllint.yaml` config (the hook is scoped to files matching `\.(yaml|yml)$`, so it does not lint the YAML front matter embedded in enhancement `.md` files)

### Automated EP Review

`.github/workflows/ep-review.yml` runs an AI-assisted review (`.github/scripts/ep_review.py`) on PRs and can be re-triggered by commenting `/review-ep`. It dispatches a `prd-review` skill for changed `prd.md` files and an `ep-review` skill for changed `design.md` files, and posts a verdict comment.
- The workflow's path filter and the script's file-type detection (`ep_review.py:detect_skills`) both match lowercase `design.md` only—PRs that only touch a capitalized variant (`Design.md`, `DESIGN.md`) will not trigger the `ep-review` skill.

### Running Locally

Install pre-commit and run before pushing:

```bash
# First time setup
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### Common Validation Errors

**YAML front matter issues** (not caught by pre-commit—verify manually or rely on EP review/human reviewers):
- Missing required fields (`title`, `authors`, `creation-date`, `tracking-link`)
- Incorrect date format (use `YYYY-MM-DD`)
- Invalid YAML syntax (check indentation, colons, quotes)

**Whitespace issues:**
- Trailing spaces at end of lines
- Missing newline at end of file

**Large files:**
- Keep diagrams and assets under 500KB
- Use external links for large images if needed

## Common Tasks

### Create New Enhancement from Template

```bash
# 1. Create directory
mkdir -p enhancements/my-feature

# 2. Copy template
cp guidelines/enhancement_template.md enhancements/my-feature/README.md

# 3. Edit YAML front matter and content
# Update title, authors, creation-date, tracking-link

# 4. Validate
pre-commit run --files enhancements/my-feature/README.md

# 5. Commit with DCO
git add enhancements/my-feature/
git commit -s -m "OSAC-1234: Add my-feature enhancement proposal"
```

### Add PRD to Existing Enhancement

```bash
# 1. Create PRD file in enhancement directory
cp guidelines/enhancement_template.md enhancements/existing-feature/prd.md

# 2. Update YAML front matter
# Change title to "[PRD] <feature name>"
# Update creation-date, tracking-link

# 3. Update design doc to reference PRD
# In enhancements/existing-feature/README.md YAML front matter:
# prd: ./prd.md

# 4. Validate and commit
pre-commit run --all-files
git add enhancements/existing-feature/
git commit -s -m "OSAC-1234: Add PRD for existing-feature"
```

### Update Existing Enhancement

```bash
# 1. Edit enhancement file
vim enhancements/existing-feature/README.md

# 2. Update YAML front matter
# - Update last-updated field to current date

# 3. Validate and commit
pre-commit run --files enhancements/existing-feature/README.md
git add enhancements/existing-feature/README.md
git commit -s -m "OSAC-1234: Update existing-feature EP with dual-stack support"
```

### Link Related Enhancements

Use `see-also` field in YAML front matter:

```yaml
---
title: Storage Network Enhancement
see-also:
  - "../networking-ui-vmaas-scope/README.md"
  - "../virtual-network/README.md"
---
```

### Supersede Old Enhancement

When replacing an old enhancement:

1. **In new enhancement** (`enhancements/new-approach/README.md`):
   ```yaml
   ---
   title: New Approach to Feature
   replaces:
     - "../old-approach/README.md"
   ---
   ```

2. **In old enhancement** (`enhancements/old-approach/README.md`):
   ```yaml
   ---
   title: Old Approach to Feature (Deprecated)
   superseded-by: ../new-approach/README.md
   ---
   ```

## Reference Files

- **Template**: `guidelines/enhancement_template.md` — Full structure and section guidance
- **Validation**: `.yamllint.yaml` — YAML linting rules
- **Pre-commit**: `.pre-commit-config.yaml` — Hook configuration
- **Ownership**: `OWNERS` — Reviewers and approvers

## Example Enhancements

Reference these for structure and style:
- `enhancements/networking-ui-vmaas-scope/` — Complex multi-component feature with `Design.md` (capitalized) and `prd.md`
- `enhancements/storage-backend-osac-1111/` — Two-stage PRD→Design workflow with both `prd.md` and `design.md` (lowercase)
- `enhancements/cluster-version-api/` — Two-stage workflow with `prd.md` and `DESIGN.md` (all caps)
- `enhancements/tenant-onboarding/` — Process-focused enhancement with workflow diagrams using `README.md`
- `enhancements/networking/` — Standard single-document enhancement using `README.md`
- `enhancements/caas-cluster-storage/` — PRD stage only (`prd.md`), design stage not yet started

**File naming note**: Most enhancements (21/28) use `README.md` for the design document. When creating new enhancements, use `README.md` unless instructed otherwise.
