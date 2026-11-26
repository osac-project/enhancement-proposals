# Test Plan — OSAC-1061 Resource names

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 7

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-RN-01: DNS label validation covers length, case and punctuation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 397-408](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L397-L408)
- **Dependencies:** Local protobuf validation with synthetic labels; no server or database.
- **Gap:** The Secret data-format test exercises another validator. No exactly matching full local DNS label matrix was verified in canonical validation sources.

**Preconditions.** Prepare a, my-resource, web01, a1b2c3, an empty label, 63 and 64 lowercase characters, uppercase, leading and trailing hyphen, and an underscore.

1. Validate each as metadata.name for a Create fixture.
2. Record decisions and field paths.

**Expected results.** Valid labels including 63 chars pass. Empty, 64 chars, uppercase and invalid punctuation fail on metadata.name.

#### TC-RN-02: The DAO rejects duplicate names in one tenant and project

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 414-423](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L414-L423)
- **Dependencies:** Real PostgreSQL and generic DAO, with fixture tenants and projects and mocked visibility; no public API.
- **Execution:** `fulfillment-service/internal/database/dao/generic_dao_name_uniqueness_test.go`
- **Evidence:** `Rejects duplicate name within same tenant and project` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/database/dao/generic_dao_name_uniqueness_test.go#L154)).
- **Selector:** Ginkgo focus `Rejects duplicate name within same tenant and project` in `fulfillment-service/internal/database/dao`. Source reviewed, test not run.

**Preconditions.** Use the fixture's t1/p1 and name my-obj.

1. Create once, then repeat with the same three values.
2. Inspect the typed DAO error.

**Expected results.** The first insert succeeds and the second returns ErrAlreadyExists.

#### TC-RN-03: A typed duplicate error preserves the ComputeInstance kind in gRPC

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 410-412](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L410-L412)
- **Dependencies:** Local error conversion with a typed fixture error; database omitted.
- **Execution:** `fulfillment-service/internal/servers/dao_error_converter_test.go`
- **Evidence:** `converts regular AlreadyExists to AlreadyExists code` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/dao_error_converter_test.go#L53)).
- **Selector:** `ginkgo run --timeout 10m --focus='converts regular AlreadyExists to AlreadyExists code' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use ErrAlreadyExists with kind compute instance and ID test-id.

1. Convert it for the Create operation.
2. Check the gRPC code and message.

**Expected results.** The code is AlreadyExists and the message contains compute instance.

#### TC-RN-04: PostgreSQL uniqueness distinguishes project, tenant and pending deletion

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 414-435](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L414-L435)
- **Dependencies:** Real PostgreSQL and DAO with synthetic resource fixtures; tenancy mocked; no deployed API.
- **Gap:** The canonical DAO suite has exact duplicate-name and archive specs plus individual positive isolation rows. Its cases do not certify the combined global, tenant and dual-scope constraint inventory.

**Preconditions.** Create named fixtures in two projects, two tenants and shared scope, plus a pending-deletion row with a finalizer.

1. Compare allowed reuses with forbidden duplicates in each configured scope.
2. Inspect the reported constraint and confirm a pending-deletion row blocks reuse until archive.

**Expected results.** Scope-appropriate reuses succeed. Same-scope, global and pending-deletion conflicts follow the table's declared constraint.

#### TC-RN-05: A project-scoped name can be reused after archival

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 418-425](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L418-L425)
- **Dependencies:** Real PostgreSQL and generic DAO, fixture t1/p1; public service omitted.
- **Execution:** `fulfillment-service/internal/database/dao/generic_dao_name_uniqueness_test.go`
- **Evidence:** `Allows name reuse after soft-delete and archive` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/database/dao/generic_dao_name_uniqueness_test.go#L210)).
- **Selector:** Ginkgo focus `Allows name reuse after soft-delete and archive` in `fulfillment-service/internal/database/dao`. Source reviewed, test not run.

**Preconditions.** Use the project's my-obj fixture without finalizers.

1. Create it and delete it so that deletion archives it.
2. Create another object with the same tenant, project and name.

**Expected results.** The replacement Create succeeds after archive.

#### TC-RN-06: Duplicate errors use a known table's kind and a generic fallback

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 410-412](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L410-L412)
- **Dependencies:** In-process table-to-kind translation and typed fixture error; no PostgreSQL.
- **Gap:** The gRPC converter test already supplies the kind. No exact known/unknown table lookup pair found in the canonical error tests.

**Preconditions.** Prepare a fixture duplicate error using virtual_networks and a second using an unknown table.

1. Translate both table names and format the resulting duplicate errors.
2. Compare their object-kind text.

**Expected results.** Known virtual_networks gives virtual network and an unknown table gives object.

#### TC-RN-07: Deployed Tenant Create rejects a name longer than 63 characters

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 399-408](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1061-resource-names/design.md#L399-L408)
- **Dependencies:** Real fulfillment and authenticated gRPC in Kind with PostgreSQL; no provider.
- **Execution:** `fulfillment-service/it/it_validation_test.go`
- **Evidence:** `Rejects Tenant with invalid metadata name (too long)` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_validation_test.go#L77)).
- **Selector:** Ginkgo focus `Rejects Tenant with invalid metadata name.*too long` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use a synthetic lowercase tenant name longer than 63 characters.

1. Submit Tenant Create through the private fixture API.
2. Inspect the gRPC diagnostic.

**Expected results.** InvalidArgument names metadata.name and the 63-character maximum.
