# Contributing

This document covers the directory and file naming convention for
`enhancements/`. For the general process of proposing an enhancement
(when one is needed, how proposals are reviewed), see [README.md](README.md).

## Directory and file naming convention

Each enhancement lives in its own directory under `enhancements/`:

```
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

A CI check validates any `enhancements/*` directory and
`prd.md`/`design.md` file that is newly added in a pull request. Directories
and files that already existed before the PR are not re-validated —
existing non-compliant directories are a separate, tracked cleanup
(see [OSAC-2870](https://redhat.atlassian.net/browse/OSAC-2870)), not a
blocker for new work.
