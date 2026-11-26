# Test Plan — OSAC-1269 Cluster version API

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 12

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-CV-01: Creating a default clears the previous default

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 382-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L382-L385)
- **Dependencies:** In-process private server with real PostgreSQL testcontainer; attribution and tenancy fixtures; no Kubernetes or provider.
- **Execution:** `fulfillment-service/internal/servers/private_cluster_versions_server_test.go`
- **Evidence:** `Create with is_default clears previous default` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_cluster_versions_server_test.go#L981)).
- **Selector:** `ginkgo run --timeout 10m --focus='Create with is_default clears previous default' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Prepare two fixture versions and available disk images.

1. Create 4.17.0 as the default, then create 4.18.0 as the default.
2. Get the first resource again.

**Expected results.** The second is default and the first is no longer default.

#### TC-CV-02: Public List excludes obsolete and disabled versions by default

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 382-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L382-L385)
- **Dependencies:** In-process public and private fulfillment servers and PostgreSQL; tenancy and attribution fixtures; no provider.
- **Execution:** `fulfillment-service/internal/servers/cluster_versions_server_test.go`
- **Evidence:** `Lists ACTIVE and DEPRECATED by default, hides OBSOLETE and disabled` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/cluster_versions_server_test.go#L106)).
- **Selector:** `ginkgo run --timeout 10m --focus='Lists ACTIVE and DEPRECATED by default' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the suite fixtures with active, deprecated, obsolete and disabled versions.

1. Call public List with no state or enabled filter.
2. Compare the returned versions with the fixtures.

**Expected results.** Active and deprecated fixtures appear; obsolete and disabled fixtures are absent.

#### TC-CV-03: A version's release image reaches ClusterOrder through the Kind handoff

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 384-386](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L384-L386)
- **Dependencies:** Real isolated Kind and fulfillment server, PostgreSQL and ClusterOrder projection controller; recording AAP double; Assisted Installer and guest provisioning omitted.
- **Gap:** The deployed version-resource CRUD test does not reconcile a Cluster. The CaaS E2E journey checks the image at its own boundary. No exact focused Kind version-to-ClusterOrder test found in fulfillment integration tests.

**Preconditions.** Create a ClusterVersion with fixture release image v4.18 and an eligible template.

1. Create a Cluster referencing the version.
2. Wait for the matching ClusterOrder and compare spec.releaseImage with the version record.

**Expected results.** The ClusterOrder uses exactly the fixture release image.

#### TC-CV-04: An active Cluster protects its selected version from deletion

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 384-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L384-L385)
- **Dependencies:** In-process private fulfillment server and PostgreSQL; synthetic Cluster reference; no provider.
- **Execution:** `fulfillment-service/internal/servers/private_cluster_versions_server_test.go`
- **Evidence:** `Blocks delete when referenced by an active cluster` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_cluster_versions_server_test.go#L264)).
- **Selector:** `ginkgo run --timeout 10m --focus='Blocks delete when referenced by an active cluster$' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create the suite version and active Cluster referencing it.

1. Attempt private Delete of the version.
2. Read the error from the server.

**Expected results.** Deletion is rejected as a live reference conflict.

#### TC-CV-05: A tenant cluster uses the administrator's managed release version

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 385-386](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L385-L386)
- **Dependencies:** Real deployed fulfillment, hub, HostedCluster/worker controllers and AAP; test version, image, catalog and worker provider; test metering harness.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Provision the suite's synthetic DiskImage and managed version, then publish a fixture catalog item that locks that version.

1. As tenant, create a Cluster from the catalog item.
2. Wait for readiness and read the ClusterOrder and HostedCluster release image.

**Expected results.** The cluster reaches readiness and its HostedCluster release image matches the ClusterOrder's resolved image.

#### TC-CV-06: The private API preserves the DiskImage reference across Create and Get

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 382-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L382-L385)
- **Dependencies:** In-process private server and real PostgreSQL; DiskImage row and fake tenancy/attribution; no image import or provider.
- **Execution:** `fulfillment-service/internal/servers/private_cluster_versions_server_test.go`
- **Evidence:** `Create with valid disk_image persists and returns the reference` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_cluster_versions_server_test.go#L1434)).
- **Selector:** `ginkgo run --timeout 10m --focus='Create with valid disk_image persists' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create the AVAILABLE DiskImage fixture rhcos-417.

1. Create a ClusterVersion referencing the image ID and name.
2. Get the version by its response ID.

**Expected results.** Create returns the image ID and name, and Get returns the same image ID.

#### TC-CV-07: Template version defaults precede the service default

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 380-386](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L380-L386)
- **Dependencies:** Real fulfillment server and PostgreSQL; fixture templates and versions; provider omitted.
- **Gap:** Canonical server default-swap coverage does not assert this template/default selection. Required fallback and release-image handoff remain unmapped.

**Preconditions.** Create distinct active versions and mark one default. Configure a template default to the other version.

1. Create without an explicit version on templates with and without a default.
2. Compare each persisted version reference.

**Expected results.** The configured template version wins when present. Without it, the current enabled default is selected.

#### TC-CV-08: A live template protects its default version from deletion

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 384-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L384-L385)
- **Dependencies:** In-process private server and real PostgreSQL; template and version fixtures; no provider.
- **Execution:** `fulfillment-service/internal/servers/private_cluster_versions_server_test.go`
- **Evidence:** `Blocks delete when referenced by an active cluster template` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_cluster_versions_server_test.go#L308)).
- **Selector:** `ginkgo run --timeout 10m --focus='Blocks delete when referenced by an active cluster template' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create a version and active fixture template referencing it.

1. Attempt private Delete of the version.
2. Read the server's conflict diagnostic.

**Expected results.** The template reference blocks deletion.

#### TC-CV-09: A live catalog item protects its version from deletion

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 384-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L384-L385)
- **Dependencies:** In-process private server and real PostgreSQL; catalog and version fixtures; no provider.
- **Execution:** `fulfillment-service/internal/servers/private_cluster_versions_server_test.go`
- **Evidence:** `Blocks delete when referenced by an active cluster catalog item` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_cluster_versions_server_test.go#L352)).
- **Selector:** `ginkgo run --timeout 10m --focus='Blocks delete when referenced by an active cluster catalog item' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create a version and active fixture catalog item referencing it.

1. Attempt private Delete of the version.
2. Read the server's conflict diagnostic.

**Expected results.** The catalog reference blocks deletion.

#### TC-CV-10: A private version supports CRUD and filtered List in Kind

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 382-385](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L382-L385)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and private API in isolated Kind; provider omitted.
- **Execution:** `fulfillment-service/it/it_private_cluster_versions_test.go`
- **Evidence:** `CRUD lifecycle` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_private_cluster_versions_test.go#L70)).
- **Selector:** Ginkgo focus `CRUD lifecycle` in the ClusterVersions context of the deployed fulfillment suite, `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's synthetic version and available image fixtures.

1. Create a version, Get by ID, List by name, and update its env label.
2. Delete the version and Get by ID again.

**Expected results.** Get and List identify the created version, Update returns env=test, and the final Get returns NotFound.

#### TC-CV-11: Validation rejects malformed version inputs and protects immutable fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 382-384](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L382-L384)
- **Dependencies:** Real fulfillment server and PostgreSQL; synthetic release data; no provider.
- **Gap:** Private server validation tables and the deployed immutable-version spec cover parts of the matrix. The full validation and immutability matrix needs individual verified selectors.

**Preconditions.** Prepare a valid version and variants with a missing version or release image.

1. Submit each create and attempt to change version and image on the accepted resource.
2. Read status and Get the original version.

**Expected results.** Create rejects malformed inputs, updates of immutable values are rejected, and the stored version and image are retained.

#### TC-CV-12: Deployed ClusterVersion Update rejects a version change

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 382-384](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1269-cluster-version-api/design.md#L382-L384)
- **Dependencies:** Real deployed fulfillment, private gRPC and PostgreSQL in Kind. The version and DiskImage are fixture records, with provider provisioning omitted.
- **Execution:** `fulfillment-service/it/it_private_cluster_versions_test.go`
- **Evidence:** `Rejects update of immutable field spec.version` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_private_cluster_versions_test.go#L129)).
- **Selector:** Ginkgo focus `Rejects update of immutable field spec.version` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Create the private ClusterVersion fixture with the suite version and available DiskImage.

1. Send Update with mask spec.version and a different version, 9.9.9.
2. Inspect the returned gRPC status.

**Expected results.** The API returns InvalidArgument for the attempted change.
