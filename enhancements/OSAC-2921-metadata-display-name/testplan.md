# Test Plan — OSAC-2921 Metadata display name

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 7

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-MD-01: Protovalidate enforces display-name and description limits

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 500-503](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L500-L503)
- **Dependencies:** Local protobuf validation and synthetic values; no database.
- **Gap:** No verified 0/63/64 and 0/256/257 matrix found in canonical metadata and server test sources.

**Preconditions.** Generate ASCII fields of lengths 0, 63 and 64 for display name, and 0, 256 and 257 for description.

1. Validate each against an otherwise valid Metadata fixture.
2. Compare results and failing field paths.

**Expected results.** Zero and each maximum pass. Each maximum plus one fails on its field.

#### TC-MD-02: Metadata survives supported Create, Update and Get operations

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 503-505](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L503-L505)
- **Dependencies:** In-process fulfillment server and real PostgreSQL; fixture attribution and tenancy; no deployed provider.
- **Gap:** Canonical metadata coverage reviewed focuses on labels and annotations. Display-name and description CRUD across the design's scoped persistent types is unverified.

**Preconditions.** Use fixture resource types from the proposal, display name Example and description First.

1. Create and Get each resource, then update description to Second for APIs that support Update.
2. Get again and compare identity and metadata.

**Expected results.** Create preserves both values. Supported updates change only description, and create-only APIs remain outside the update matrix.

#### TC-MD-03: A supported masked update clears Metadata text fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 503-505](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L503-L505)
- **Dependencies:** Real in-process fulfillment server and PostgreSQL; fixture authorization context.
- **Gap:** No exact clear-to-empty masked text field assertion was found in canonical metadata tests.

**Preconditions.** Create a fixture Project with nonempty Metadata text.

1. Update both text fields to empty with the explicit masks.
2. Get the project by its unchanged ID.

**Expected results.** Both fields read back empty and other metadata remains intact.

#### TC-MD-04: Deployed List filters and orders by Metadata display name

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 523-530](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L523-L530)
- **Dependencies:** Real deployed fulfillment, PostgreSQL, CLI and authentication in a disposable Kind fixture; no provider execution.
- **Gap:** The cited canonical deployed metadata test proves private-key visibility, not display-name list behavior. No matching named selector found in deployed metadata sources.

**Preconditions.** Create Project and ComputeInstanceCatalogItem fixtures named Alpha and Beta, plus a create-only NetworkClass row.

1. Filter for Alpha and list descending by display name.
2. Read the NetworkClass and verify its declared display name.

**Expected results.** Filtering selects only Alpha, descending results put Beta before Alpha, and NetworkClass Get returns the stored name.

#### TC-MD-05: The order parser rejects an unknown metadata sort field

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 506-509](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L506-L509)
- **Dependencies:** In-process order parser; no database or API server.
- **Gap:** No exact display-name acceptance and unknown-metadata-field pair found in order translator tests.

**Preconditions.** Use orders metadata.display_name desc and metadata.unknown desc.

1. Parse each independently.
2. Compare accepted projection and rejected path.

**Expected results.** The first resolves to descending display-name order and the second rejects the unknown field.

#### TC-MD-06: Equal display names produce stable, nonoverlapping pages

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 508-509](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L508-L509)
- **Dependencies:** Real PostgreSQL and fulfillment List logic; synthetic rows; no provider.
- **Gap:** Canonical metadata and ordering test sources did not establish the stable display-name tie break.

**Preconditions.** Seed two synthetic rows with identical display names and distinct IDs.

1. List by metadata.display_name using page size 1 at offsets 0 and 1.
2. Repeat and compare with listing by explicit secondary ID order.

**Expected results.** The same two IDs occur once each in ascending ID order.

#### TC-MD-07: Migration removes only designated text fields and retains nested values

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 513-519](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2921-metadata-display-name/design.md#L513-L519)
- **Dependencies:** Real disposable PostgreSQL with pre-migration fixture rows and captured logs; no deployed API.
- **Gap:** No verified test identified for this migration plus excluded nested fields and truncation warning in the canonical migration inventory.

**Preconditions.** Seed flat and spec titles, a 257-character description, and nested TemplateParameter.title, FieldDefinition.display_name and HostType interface description.

1. Apply the migration and read columns, retained JSON and logs.
2. Compare unrelated nested values with the original fixtures.

**Expected results.** The designated text appears in new columns, description is truncated to 256, migrated paths are removed, nested values remain, and the warning reports resource type and count without contents.
