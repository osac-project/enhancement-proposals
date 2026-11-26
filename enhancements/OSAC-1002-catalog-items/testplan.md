# Test Plan — OSAC-1002 Catalog items

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 8

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-CAT-01: Catalog offering Create returns an ID and starts unpublished

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 617-626](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L617-L626)
- **Dependencies:** Real deployed fulfillment and PostgreSQL in Kind with Keycloak fixture identity; in-process MCP and fixture template; no VM provider.
- **Execution:** `fulfillment-service/it/it_mcp_catalog_test.go`
- **Evidence:** `creates, updates, publishes, and deletes as the authorized caller` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_mcp_catalog_test.go#L19)).
- **Selector:** Ginkgo focus `creates, updates, publishes, and deletes as the authorized caller` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the fixture Tenant Admin and ComputeInstance template.

1. Create a compute offering through the MCP client.
2. Read it by its returned ID using public ComputeInstanceCatalogItems Get.

**Expected results.** Create returns a nonempty ID and Get returns its initial unpublished state. This is the ComputeInstance offering path.

#### TC-CAT-02: An invalid governed value is rejected before creating an offering

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 598-606](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L598-L606)
- **Dependencies:** In-process schema validation and synthetic offering fields; no database.
- **Gap:** Canonical current tests validate typed policies. The legacy freeform schema contract in this proposal has no verified matching selector and was superseded by Catalog Items V2.

**Preconditions.** Prepare a legacy field definition for an editable numeric quantity and a valid numeric value.

1. Compare the definition using the valid number and a nonnumeric fixture value.
2. Inspect the validation result.

**Expected results.** The invalid value is rejected at its field and the valid value is accepted under the legacy schema contract.

#### TC-CAT-03: Unpublished items are excluded from published-only selection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 615-616](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L615-L616)
- **Dependencies:** Real fulfillment, PostgreSQL and fixture tenant roles in Kind; no deployed VM provider.
- **Execution:** `fulfillment-service/it/it_compute_instance_catalog_items_test.go`
- **Evidence:** `lets a Tenant Admin publish governed items for members of that tenant` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_compute_instance_catalog_items_test.go#L765)).
- **Selector:** Ginkgo focus `lets a Tenant Admin publish governed items for members of that tenant` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use a synthetic draft ComputeInstance item owned by the suite's tenant.

1. Read the item using an authorized member, then list using the published filter.
2. Publish and subsequently unpublish it, then try a new member Create.

**Expected results.** Current main allows a same-tenant member to read the draft, excludes it from published-only List, and rejects new provisioning after unpublish. The stricter legacy read scope is a separate gap.

#### TC-CAT-04: A tenant creates a Cluster from a published offering

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 625-630](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L625-L630)
- **Dependencies:** Real fulfillment, hub, AAP and CaaS provider fixtures; a published item and synthetic tenant.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Prepare the suite's published offering with a resolved version and worker configuration.

1. Create a Cluster as the fixture tenant selecting the item.
2. Read the stored CatalogItem ID and materialized Template and observe cluster readiness.

**Expected results.** The selected item and a resolved Template are persisted and the cluster becomes available. Current main retains both references.

#### TC-CAT-05: A foreign tenant cannot see a tenant-scoped offering

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 612-615](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L612-L615)
- **Dependencies:** Real fulfillment authorization, PostgreSQL and two isolated tenant identities in Kind; no workload provider.
- **Execution:** `fulfillment-service/it/it_compute_instance_catalog_items_test.go`
- **Evidence:** `lets a Tenant Admin publish governed items for members of that tenant` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_compute_instance_catalog_items_test.go#L765)).
- **Selector:** Ginkgo focus `lets a Tenant Admin publish governed items for members of that tenant` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's published ComputeInstance offering and a separate fixture tenant user.

1. Check the foreign tenant's ordinary Get and filtered List results.
2. Verify that the fixture offering remains visible to its owning tenant.

**Expected results.** Foreign reads are absent with NotFound or an empty list. The owning scope can read it.

#### TC-CAT-06: Legacy CNA reference exception and draft visibility

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 615-617](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L615-L617)
- **Dependencies:** Real fulfillment and PostgreSQL with fixture Tenant User, Tenant Admin and a legacy CNA relationship; no provider.
- **Gap:** The legacy CNA-based exception is not established by the current canonical CatalogItem tests. Current same-tenant draft Get/List behavior differs and is documented in TC-CAT-03.

**Preconditions.** Use two unpublished fixture items with one already referenced by a legacy CNA.

1. Compare Tenant User Get and List with Tenant Admin Get and List for the two items.
2. Record the CNA association for the readable item.

**Expected results.** The legacy design permits tenant-user Get only for the referenced item and tenant-admin visibility of both own-tenant items.

#### TC-CAT-07: ComputeInstance offering updates, publication and deletion respect ownership

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 618-620](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L618-L620)
- **Dependencies:** Real fulfillment, PostgreSQL and isolated tenant-admin roles in Kind; in-process MCP; no workload provider.
- **Execution:** `fulfillment-service/it/it_mcp_catalog_test.go`
- **Evidence:** `isolates ComputeInstance offering mutations between tenant admins` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_mcp_catalog_test.go#L168)).
- **Selector:** Ginkgo focus `isolates ComputeInstance offering mutations between tenant admins` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the two tenant-admin fixtures and a ComputeInstance offering in each tenant.

1. Compare the fixture admins' update, publication and delete outcomes in their own and different tenant scopes.
2. Read the unchanged offering through its owner.

**Expected results.** Owner operations succeed. The other tenant has no write permission and the original record stays unchanged. The separate direct Create scope and legacy tenant-field omission remain unresolved.

#### TC-CAT-08: Catalog item Create derives the owner tenant from its caller

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 618-620](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1002-catalog-items/README.md#L618-L620)
- **Dependencies:** Real fulfillment, PostgreSQL and isolated tenant-admin roles in Kind; in-process MCP; no workload provider.
- **Gap:** Canonical offering Create uses the caller's tenant and includes tenant metadata on authorized public Get. No exact direct API test verified the legacy hidden tenant field and rejected foreign-scope Create together.

**Preconditions.** Use an isolated Tenant Admin with a fixture ComputeInstance template.

1. Create an item with ordinary tenant-scoped input.
2. Check its assigned ownership using an authorized fixture read and compare the API field shape.

**Expected results.** The created item belongs to the calling tenant. The legacy design omits tenant from the public shape, while main currently exposes the tenant metadata on authorized Get.
