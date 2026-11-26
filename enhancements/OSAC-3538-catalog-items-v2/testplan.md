# Test Plan — OSAC-3538 Catalog items v2

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 9

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-C2-01: Locked scalar policy supplies the catalog value and rejects overrides

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [prd.md, lines 23-30](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L23-L30)
- **Dependencies:** In-process typed policy helper with synthetic strings; no server, database or provider.
- **Execution:** `fulfillment-service/internal/servers/catalog_item_field_policies_test.go`
- **Evidence:** `applies scalar precedence` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/catalog_item_field_policies_test.go#L86)).
- **Selector:** `ginkgo run --timeout 10m --focus='applies scalar precedence' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the suite's locked scalar string and a recording setter.

1. Apply it with no caller value, then with an explicit caller value.
2. Apply a policy with no behavior and inspect diagnostics.

**Expected results.** Omission writes the catalog value, a caller override is rejected as not editable, and an empty policy fails validation.

#### TC-C2-02: Publication management follows Catalog Item ownership

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [prd.md, lines 44-52](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L44-L52)
- **Dependencies:** Real fulfillment, authorization and PostgreSQL; isolated provider-admin, tenant-admin and tenant-user fixtures; no workload provider.
- **Gap:** Canonical catalog authoring and access suites exist, but no verified single exact role-by-scope publication matrix was identified.

**Preconditions.** Use a global item and one item in each of two isolated fixture tenants.

1. Exercise the supported publication operation with each fixture role in its permitted and outside-scope contexts.
2. Read publication state through the authorized API.

**Expected results.** Provider admin controls global publication, each tenant admin controls their own item, and other roles or scopes receive a denial without changing state.

#### TC-C2-03: Provisioning selects a published offering and persists its resolved template

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [prd.md, lines 34-42](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L34-L42)
- **Dependencies:** Real deployed fulfillment and cluster controllers; synthetic published offering, template and test BMaaS provider.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's published ClusterCatalogItem, managed version, worker type and registered Secret references.

1. Create a Cluster via the tenant CLI selecting the offering.
2. Get the Cluster and read its catalog provenance and Template reference.

**Expected results.** The spec contains the selected CatalogItem ID and a nonempty materialized Template ID.

#### TC-C2-04: Unpublishing stops new provisioning while members can still read the draft

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [prd.md, lines 36-46](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L36-L46)
- **Dependencies:** Real fulfillment, authorization and PostgreSQL with isolated tenant fixtures; provider omitted.
- **Execution:** `fulfillment-service/it/it_compute_instance_catalog_items_test.go`
- **Evidence:** `lets a Tenant Admin publish governed items for members of that tenant` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_compute_instance_catalog_items_test.go#L765)).
- **Selector:** Ginkgo focus `lets a Tenant Admin publish governed items for members of that tenant` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's published tenant ComputeInstance offering, its admin and its ordinary member.

1. Create a fixture resource as the member and unpublish the offering as its admin.
2. Try a new Create, Get the offering and List with a published filter.

**Expected results.** New member Create returns NotFound. The member can still Get the draft, and it is excluded from published-only List.

#### TC-C2-05: Editable policy preserves explicit values and supplies defaults on omission

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [prd.md, lines 23-30](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L23-L30)
- **Dependencies:** In-process typed policy functions and synthetic protobuf specs; no provider or database.
- **Execution:** `fulfillment-service/internal/servers/catalog_item_field_policies_test.go`
- **Evidence:** `applies editable defaults and preserves supplied values` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/catalog_item_field_policies_test.go#L249)).
- **Selector:** `ginkgo run --timeout 10m --focus='applies editable defaults and preserves supplied values' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the suite's fixture policies for ComputeInstance image and Cluster version and node sets.

1. Apply the policies to requests with absent values.
2. Apply them to requests with supplied values.

**Expected results.** Absent fields receive the fixture defaults and supplied values remain unchanged.

#### TC-C2-06: Catalog field dependencies cannot be deleted while referenced

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [prd.md, lines 36-38](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L36-L38)
- **Dependencies:** Real disposable PostgreSQL migration fixture and synthetic catalog and dependency rows; no service or provider process.
- **Execution:** `fulfillment-service/internal/database/migrations/114_update_catalog_policy_reverse_references_test.go`
- **Evidence:** `protects locked and editable default dependencies of active catalog items` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/database/migrations/114_update_catalog_policy_reverse_references_test.go#L28)).
- **Selector:** Ginkgo focus `protects locked and editable default dependencies of active catalog items` in `fulfillment-service/internal/database/migrations`. Source reviewed, test not run.

**Preconditions.** Use the suite's locked and editable defaults pointing at fixture dependency rows.

1. Attempt to soft-delete the referenced dependency with the catalog row active.
2. Clear the catalog reference using the fixture's cleanup path and compare the result.

**Expected results.** The database rejects deletion while the active catalog item holds the reference; the guard releases when the reference is gone.

#### TC-C2-07: Governed template parameters must match parameter names and types

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [prd.md, lines 30-35](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L30-L35)
- **Dependencies:** Real deployed fulfillment and PostgreSQL in Kind; isolated template and synthetic parameter profiles; provider omitted.
- **Gap:** Canonical authoring tables cover invalid template parameter values. Locked/editable default and caller behavior across all three resources requires further verified mappings.

**Preconditions.** Use one fixture Template defining a Boolean enabled parameter.

1. Author locked and editable policies using a Boolean value, then compare with a policy for an unknown parameter and a string value.
2. Resolve a Create with omitted editable value.

**Expected results.** Valid policies are accepted, invalid names and types are rejected, and omitted editable input resolves to its valid default.

#### TC-C2-08: Create accepts exactly one provisioning source

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 23-31](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/design.md#L23-L31)
- **Dependencies:** Real fulfillment and PostgreSQL; synthetic Template, item and resolved workload rows; no provider or running workloads.
- **Gap:** Canonical workload and catalog tests cover individual resource and source combinations. The complete two-path and invalid mixed-source matrix for all three resources remains a separate gap.

**Preconditions.** Use fixture ComputeInstance, Cluster and BareMetalInstance templates, each with a valid published item.

1. For each resource, submit a direct Template Create and a published CatalogItem Create in isolation.
2. Compare with a request specifying both sources.

**Expected results.** The two supported single-source requests succeed. The mixed-source request fails without producing an object.

#### TC-C2-09: Catalog policy edits apply only to future VM creates

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [prd.md, lines 30-40](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-3538-catalog-items-v2/prd.md#L30-L40)
- **Dependencies:** Real deployed fulfillment and PostgreSQL in Kind with a fixture template and public API identities. Guest workloads and provider provisioning are outside this assertion.
- **Execution:** `fulfillment-service/it/it_compute_instance_catalog_items_test.go`
- **Evidence:** `applies policy edits only to future compute instances and preserves provenance after catalog item deletion` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_compute_instance_catalog_items_test.go#L1679)).
- **Selector:** Ginkgo focus `applies policy edits only to future compute instances and preserves provenance after catalog item deletion` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite published ComputeInstance item with initial editable fixture value first.

1. Create one VM, update the item to a locked fixture value second, and create another VM.
2. Get both VMs and compare the persisted values.

**Expected results.** The first VM retains first and the second VM contains second. The editable or locked policy is applied during Create.
