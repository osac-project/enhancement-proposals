# Contributing

This document covers the directory and file naming convention for
`enhancements/`. For the general process of proposing an enhancement
(when one is needed, how proposals are reviewed), see [README.md](README.md).

## Directory and file naming convention

Each enhancement lives in its own directory under `enhancements/`:

```text
enhancements/OSAC-NNNN-feature-slug/
├── prd.md
└── design.md
```

- **Directory name:** `OSAC-NNNN-feature-slug`, where `OSAC-NNNN` is the
  Jira **Feature**-level key exactly as it appears in Jira, followed by
  a kebab-case slug derived from the feature summary. For example, the
  Feature "StorageTier API" (OSAC-1110) lives at
  `enhancements/OSAC-1110-storage-tier-api/`.
- **File names:** always lowercase — `prd.md` and `design.md`.
  `README.md` is legacy-only, used by enhancements filed before the
  PRD/design split; it is not used for new work.

### `OSAC-NNNN` is not a fixed digit width

`NNNN` is placeholder notation for "the numeric Jira key," not a
required four-digit format — the key is used exactly as it appears in
Jira, with no zero-padding. `OSAC-42`, `OSAC-2868`, and `OSAC-10000`
are all valid. This is a deliberate choice: 1:1 parity with the real
Jira key was judged more valuable than zero-padded alphabetical
sorting. The one accepted, cosmetic-only consequence is that once keys
cross a digit-count boundary (4 digits to 5, e.g. `OSAC-10000`),
GitHub's alphabetical folder view will interleave 5-digit keys ahead of
4-digit ones out of numeric order. This doesn't affect tooling, since
matching an enhancement directory to its Jira Feature only requires an
exact substring match on the key, not a sortable one.

## Enforcement

Two CI checks enforce this convention on new work. Both validate only what
is newly added in a pull request: any directory or file under
`enhancements/` for the naming check, and any directory for the type check.
Anything that already existed before the PR — either at the PR's base
commit, or currently on the PR's base branch — is not re-validated. This
means an unrelated, still-non-compliant directory merged by someone else's
PR never blocks your PR, even if your branch hasn't been rebased since.
Existing non-compliant directories are a separate, tracked cleanup
(see [OSAC-2870](https://redhat.atlassian.net/browse/OSAC-2870)), not a
blocker for new work.

- `pre-commit` validates the directory name and the file names.
- `ep-jira-type` resolves the Jira key in each new directory and requires
  the issue to be of type **Feature**. A key that resolves to another
  issue type, or to no issue at all, fails the check. If Jira cannot be
  reached, or the CI credential is not configured, the check reports
  neutral instead of failing — that is an infrastructure problem, not an
  authoring one.

Because `ep-jira-type` needs a credential that is deliberately unavailable
to pull requests from forks, it runs only in CI; there is no local
equivalent. If you do not have access to Red Hat Jira, for example as an
external contributor, ask a maintainer to create or identify the Feature
and give you its key — the key must exist and must be a Feature.

If you have `pre-commit install`ed locally, the naming check is
advisory-only whenever `PRE_COMMIT_PR_BASE_SHA` isn't set (the normal case
for a local commit) — it can't tell new paths from pre-existing ones
without a PR base branch to compare against, so it skips enforcement
rather than guessing. If that variable happens to be set in your local
shell, enforcement behaves the same as CI. Either way, CI is the
authoritative gate.
