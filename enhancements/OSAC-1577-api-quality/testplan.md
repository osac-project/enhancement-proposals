# Test Plan — OSAC-1577 API quality

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 7

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-GEN-01: Public validation annotations survive generation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 536-541](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L536-L541)
- **Dependencies:** Local generator, fixture descriptors and validator; no service or database.
- **Gap:** Buf lint is supplemental static validation. No exact descriptor annotation and behavioral parity test was verified in canonical proto generation sources.

**Preconditions.** Use a private fixture with a public field that has a required validation annotation.

1. Generate the public descriptor.
2. Compare the retained annotation and evaluate an input that violates it.

**Expected results.** Validation metadata is retained and the generated public type rejects the invalid value.

#### TC-GEN-02: Private-marked fields are excluded from generated public descriptors

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 536-538](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L536-L538)
- **Dependencies:** Local generator and synthetic private schema with marked and unmarked fields.
- **Gap:** No independent exact fixture assertion verified in canonical generator and proto validation sources.

**Preconditions.** Prepare a message with one marked private field and one normal public field.

1. Generate the public type, then list its fields.
2. Compare the generated descriptor with the fixture classification.

**Expected results.** The public field is present and the private-marked field is absent.

#### TC-GEN-03: Retained field numbers and public-only files survive generation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 537-541](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L537-L541)
- **Dependencies:** Local generation and descriptor/file snapshots; no deployment.
- **Gap:** No exact assertion for preservation of both numeric descriptors and public-only sources found in canonical proto test and CI inventory.

**Preconditions.** Snapshot private field numbers for a fixture and the public-only console proxy and JWKS protos.

1. Generate the public tree in a disposable copy.
2. Compare retained field numbers and byte contents of both standalone protos.

**Expected results.** Public retained fields preserve private numbers and the public-only files are unchanged.

#### TC-GEN-04: An active Subnet blocks soft-deleting its VirtualNetwork parent

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 543-547](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L543-L547)
- **Dependencies:** Real migrated PostgreSQL fixture; synthetic VirtualNetwork and Subnet rows; no fulfillment process.
- **Execution:** `fulfillment-service/internal/database/migrations/90_update_triggers_for_typed_references_test.go`
- **Evidence:** `Prevents soft-deleting a virtual network referenced by a subnet with typed reference` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/database/migrations/90_update_triggers_for_typed_references_test.go#L131)).
- **Selector:** Ginkgo focus `Prevents soft-deleting a virtual network referenced by a subnet with typed reference` in `fulfillment-service/internal/database/migrations`. Source reviewed, test not run.

**Preconditions.** Use the migration suite's active VirtualNetwork and Subnet with a typed reference.

1. Attempt to soft-delete the VirtualNetwork in the fixture database.
2. Read the resulting protection error.

**Expected results.** The database rejects the parent deletion while the Subnet reference is active.

#### TC-GEN-05: SQLSTATE translation yields the designed typed DAO errors

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 550-551](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L550-L551)
- **Dependencies:** Local translator and synthetic PostgreSQL error fixtures; no gRPC server or database.
- **Gap:** The gRPC converter tests start with already typed DAO errors. An exhaustive translateError matrix by SQLSTATE and operation was not verified in the DAO test inventory.

**Preconditions.** Prepare a table of SQLSTATEs named by the design for Create, Update and Delete.

1. Translate each synthetic PostgreSQL error at its DAO operation boundary.
2. Compare resulting error type and relevant constraint information.

**Expected results.** Each SQLSTATE maps to the corresponding DAO type with its documented context.

#### TC-GEN-06: Child admission recognizes an active versus deleted parent

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 543-548](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L543-L548)
- **Dependencies:** Real migrated PostgreSQL and DAO; synthetic parent and child rows; no service.
- **Gap:** The archive spec proves archive effects. No matching named DAO selector verified for the combined active-parent insert and soft-deleted-parent rejection.

**Preconditions.** Prepare an active VirtualNetwork and a second one in a deleted fixture state.

1. Create a Subnet for each.
2. Remove the first child, then remove that parent and inspect the active view.

**Expected results.** An active parent accepts the child and the deleted parent yields ErrReference. A parent with no active child can be removed and disappears from the active view.

#### TC-GEN-07: Public and private APIs preserve public fields and hide private-only fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 553-558](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1577-api-quality/design.md#L553-L558)
- **Dependencies:** Real deployed fulfillment public/private APIs and PostgreSQL in Kind; fixture object; no provider.
- **Gap:** No exact deployed round-trip selector verified for shared fields, private-only fields and public service method inventory together.

**Preconditions.** Prepare a known fixture resource with public inputs and server-controlled hub/region/finalizers.

1. Create using public API and Get through both APIs.
2. Compare their descriptors and public service methods.

**Expected results.** Common fields match, public output omits the private-only fields and public gRPC does not expose Signal.
