# Testplan — OSAC-5073

## Overview

- **Feature:** OSAC-5073 — Storage Connectivity Through Networking
- **Total test cases:** 17 (13 IDs; parameterized rows count individually)
- **Requirements covered:** 9 of 10 (FR-7 is documentation-only)
- **Interface changes covered:** 1 of 1 (IC-2, documentation, by manual review and the Helm contract)

The design changes no code ([Locked: D10]). The automated cases verify the existing behavior that the
design relies on; the manual cases review the documentation.

## Coverage Matrix

One row per behavior and boundary, from the
[fulfillment-service](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#fulfillment-service),
[osac-installer](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#osac-installer)
and [tests/e2e](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#testse2e)
sections of the OSAC integration testing guide. That guide makes `internal/` suites Unit and `it/` suites
Component integration for the fulfillment service. Paths are relative to the component; commands run from
the named directory.

| Row | Behavior | Req / IC | Tier, owner | Boundary proved | Cases | Suite (status) | Command, directory | Real | Faked or omitted |
|---|---|---|---|---|---|---|---|---|---|
| M1 | Startup refusal on an existing network resource; Clusters not compared | FR-4 | Unit (`internal/startup`, with a PostgreSQL test server), [DEV] fulfillment-service | `CheckInstallationSettings` against PostgreSQL | TC-FR4-01 | `internal/startup/installation_settings_test.go` `DescribeTable` of excluded-range overlaps (existing, no change) | `ginkgo run --timeout 10m internal/startup`, `fulfillment-service/` | Startup check and PostgreSQL test server | Rows inserted by SQL, not through the API; no rollout |
| M2 | VirtualNetwork and ExternalIPPool rejection | FR-2 | Component integration, [DEV] fulfillment-service | Deployed public and private APIs, PostgreSQL | TC-FR2-01 | `it/it_networking_design_test.go` TC-IPAM-03 (existing, no change) | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`, repository root | Deployed Fulfillment service, PostgreSQL, Keycloak; dev profile range `192.0.2.0/24` | Provider networking disabled; no operator in this phase |
| M3 | Several ranges render to the service flag; the IC-2 description edits keep the values and schema valid | FR-1, IC-2 | Contract (Helm contract), [DEV] osac-installer | Helm rendering of the real chart and schema validation | TC-FR1-01 | `scripts/test-networking-values.py` `test_provisioning_enabled` (existing, no change) | `make helm-networking-test` (depends on `helm-deps`), `osac-installer/` | `helm template` of the real chart | No cluster |
| M4 | Storage reached through the NATGateway, tenant identity, no inbound through the NATGateway | FR-5, FR-6, NFR-2, NFR-3 | E2E, [QE] | Deployed OSAC, Fabric Manager NAT, provider routes, storage endpoint | TC-FR5-01 to TC-FR5-04, TC-FR6-01, TC-NFR2-01, TC-NFR3-01 | `tests/e2e/networking/storage/test_storage_nat.py` (proposed; status: blocked until the Netris lab storage server in `osac-test-infra` exists; owner [QE]) | Proposed: `uv run pytest -n 0 -x tests/e2e/networking/storage/test_storage_nat.py`, repository root | Fulfillment, operator, AAP, KubeVirt, HyperShift for CaaS, BMaaS, Fabric and Kubernetes Managers, routed pool, NFS server, OSAC CSI Driver | None faked |
| M5 | No vendor or Fabric Manager setting | NFR-1 | Manual review (not a test tier), [DEV] | Documentation diff | TC-NFR1-01 | Pull request review | N/A | The diff | Not an executed test |
| M6 | Cluster network guidance and the admin check of existing Cluster networks before adding a range | FR-3, FR-4, FR-7, IC-2 | Manual review (not a test tier), [DEV] | Guide text, followed against a test deployment | TC-FR3-01, TC-FR4-02 | Installation and tenant guides | N/A | The guide; a test deployment for the check procedure | Not an executed test; no code checks Cluster networks; the value and schema description edits run M3 |

Execution status: M1, M2 and M3 are existing suites that run in CI and need no change. M4 is planned but
not execution-ready. M5 and M6 are review steps.

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-FR1-01 | Two excluded ranges render to the fulfillment service flag | IC-2 | medium |
| TC-FR2-01 | VirtualNetwork and ExternalIPPool overlapping an excluded range are rejected | — | high |
| TC-FR3-01 | Installation and tenant guides give the Cluster network guidance | IC-2 | high |
| TC-FR4-01 | Startup refuses an excluded range over an existing network resource and skips Clusters (parameterized, 5 rows, existing) | — | high |
| TC-FR4-02 | Installation guide gives the existing-Cluster check before adding a range | IC-2 | medium |
| TC-FR5-01 | VM guest mounts NFS through the NATGateway | — | critical |
| TC-FR5-02 | No NATGateway, no storage | — | medium |
| TC-FR5-03 | CaaS PVC mounts through the Cluster's NATGateway | — | high |
| TC-FR5-04 | BMaaS host mounts NFS through the NATGateway | — | high |
| TC-FR6-01 | New tenant's default network reaches storage | — | high |
| TC-NFR1-01 | Change adds no vendor or Fabric Manager setting | — | medium |
| TC-NFR2-01 | Storage endpoint cannot open a connection through the NATGateway | — | high |
| TC-NFR3-01 | Same CIDR in two tenants, two source addresses | — | critical |

## Test Cases

### FR-1: Storage ranges listed in the excluded ranges setting

#### TC-FR1-01: Two excluded ranges render to the fulfillment service flag

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- Chart dependencies built (`make helm-deps`) and `helm` on the path.

**Steps:** 1. Render the chart with `excludedIpv4Cidrs: [192.0.2.0/24, 198.51.100.0/24]` → 2. Read the
fulfillment Deployment arguments.
**Expected:** The arguments contain `--networking-excluded-ipv4-cidrs=192.0.2.0/24,198.51.100.0/24`, and the
values pass schema validation after the IC-2 description edits.

### FR-2: VirtualNetwork and ExternalIPPool rejection

#### TC-FR2-01: VirtualNetwork and ExternalIPPool overlapping an excluded range are rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Preconditions

- The deployment excludes `192.0.2.0/24` (dev profile).

##### Steps

1. Create VirtualNetworks `192.0.2.0/24` and `192.0.0.0/16`.
2. Create an ExternalIPPool `192.0.2.0/28` through the private API.
3. Create a VirtualNetwork `192.0.3.0/24` and a pool `192.0.4.0/28`.

##### Expected Results

- Steps 1 and 2 return `INVALID_ARGUMENT` with "overlaps the excluded range 192.0.2.0/24", and a List shows
  no resource with those names.
- Step 3 creates both resources.

### FR-3: Cluster network guidance

#### TC-FR3-01: Installation and tenant guides give the Cluster network guidance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | manual |

##### Preconditions

- The installation guide and tenant guide changes are open.

##### Steps

1. Read the storage connectivity section of the installation guide on choosing ranges.
2. Read the tenant guide on Cluster pod and service CIDRs.

##### Expected Results

- The installation guide states that Cluster pod and service networks must not cover a storage range, and
  that nothing rejects a Cluster whose networks do.
- It names the sources of a Cluster's networks in order: the request, the ClusterTemplate's
  `spec_defaults.network`, and the AAP role defaults pod `10.132.0.0/14` and service `172.31.0.0/16`.
- It tells the admin and catalog authors to keep ClusterTemplate defaults and catalog item policies outside
  every storage range, and states that only storage ranges, not every excluded range, must stay outside
  the Cluster networks.
- The tenant guide tells tenants who set pod or service CIDRs to keep them off the storage ranges.

### FR-4: Rollout fails when a new range overlaps an existing resource

These cases map FR-4 to existing behavior. The startup check does not compare Cluster networks, by
decision; the admin check of existing Clusters is documentation (TC-FR4-02).

#### TC-FR4-01: Startup refuses an excluded range over an existing network resource (parameterized, existing)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Steps

1. Insert `{resource}` by SQL.
2. Run the startup check with `excludedIpv4Cidrs: [{excluded}]`.

##### Expected Results

| `{resource}` | `{excluded}` | Expected Result |
|---|---|---|
| VirtualNetwork `10.0.0.0/16` | `192.168.0.0/24` | No error |
| NetworkClass default `10.200.0.0/16` | `10.200.1.0/24` | Error `excludedIpv4Cidrs range 10.200.1.0/24 overlaps the NetworkClass default virtual_network_ipv4_cidr 10.200.0.0/16` |
| VirtualNetwork `vn-1` `10.0.0.0/16` | `10.0.5.0/24` | Error `excludedIpv4Cidrs range 10.0.5.0/24 overlaps VirtualNetwork vn-1` |
| ExternalIPPool `pool-1` `192.0.2.0/24` | `192.0.2.128/25` | Error `excludedIpv4Cidrs range 192.0.2.128/25 overlaps ExternalIPPool pool-1` |
| Cluster `cluster-1` with no `spec.network` | `10.0.0.0/8` | No error: Cluster networks are not compared |

#### TC-FR4-02: Installation guide gives the existing-Cluster check before adding a range

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | manual |

##### Preconditions

- The installation guide change is open.

**Steps:** 1. Read the storage connectivity section on extending ranges → 2. Follow it against a test
deployment holding a Cluster with `pod_cidr: 10.150.0.0/16`, a Cluster with no `spec.network` from a
ClusterTemplate without network defaults, and planned ranges `10.150.0.0/24` and `10.133.0.0/24`.
**Expected:** The guide states that the startup check does not compare Cluster networks, tells the admin to
list every tenant's Clusters and compare their pod and service CIDRs with each new range (the ClusterTemplate
defaults, else `10.132.0.0/14` and `172.31.0.0/16`, when unset), and the procedure finds `10.150.0.0/24`
overlapping the first Cluster and `10.133.0.0/24` overlapping the second.

### FR-5: Workloads reach storage through the NATGateway

##### Shared Preconditions

- A Netris lab from `osac-test-infra` (`infra/netris/`) with provider networking enabled, a routed ExternalIPPool,
  and a plain Linux NFS server (no storage vendor) outside the fabric gateway. The server's address is in
  `excludedIpv4Cidrs` in the lab's installer values, it has a route to the lab's ExternalIPPool CIDRs and is
  reached from the NAT path, and it logs client addresses. See the lab gap below.

#### TC-FR5-01: VM guest mounts NFS through the NATGateway

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

##### Steps

1. Create a VM on a new tenant's default Subnet.
2. In the guest, mount the NFS export with NFSv4.1 and write a file.
3. Read the NFS server's client log.

##### Expected Results

- The mount succeeds and the file is on the export.
- The server logs the address of the tenant's `default-nat` ExternalIP as the client.

#### TC-FR5-02: No NATGateway, no storage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | medium | automated |

**Steps:** 1. Create a VM on a VirtualNetwork without a NATGateway → 2. Mount the export with a 30 second
timeout.
**Expected:** The mount times out, and the NFS server logs no connection from the tenant.

#### TC-FR5-03: CaaS PVC mounts through the Cluster's NATGateway

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Additional Preconditions

- A READY CaaS Cluster on the tenant's default Subnet, with a StorageClass that uses the OSAC CSI Driver and
  is backed by the NFS server, so that the CSI controller's calls to the hub fulfillment API and its OIDC
  issuer also cross the NAT.

##### Steps

1. Create a PVC and a pod that writes a file to it.
2. Read the NFS server's client log.

##### Expected Results

- The PVC is Bound and the file is on the export.
- The server logs the Cluster VirtualNetwork's NAT address as the client.

#### TC-FR5-04: BMaaS host mounts NFS through the NATGateway

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Additional Preconditions

- A RUNNING BareMetalInstance on a tenant Subnet whose VirtualNetwork has a READY NATGateway, after the
  port move (not at first boot on the provisioning network).

**Steps:** 1. On the host, mount the export with NFSv4.1 and write a file → 2. Read the NFS server's client log.
**Expected:** The file is on the export, and the server logs the VirtualNetwork's NAT address as the client.

### FR-6: Default network reaches storage

#### TC-FR6-01: New tenant's default network reaches storage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Preconditions

- As in FR-5; a Cloud Provider Admin creates a new Tenant.

##### Steps

1. Wait for the Tenant's `DefaultNetworkingReady=True`.
2. Without creating any networking resource, create a VM with defaulted attachment and mount the export.

##### Expected Results

- The mount succeeds; the tenant created no NATGateway, ExternalIP, or VirtualNetwork.

### FR-7: Documentation

Documentation-only; see Gaps.

### NFR-1: No vendor or Fabric Manager setting

#### TC-NFR1-01: Change adds no vendor or Fabric Manager setting

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | medium | manual |

##### Preconditions

- The documentation pull requests are open.

**Steps:** 1. Review the diff and the guide section → 2. Search them for new Helm values, API fields,
capability tokens, code changes, and vendor or Fabric Manager names.
**Expected:** No new Helm value, API field, capability, or code change; vendor names appear only as examples
in the guide.

### NFR-2: No inbound connections through the NATGateway

#### TC-NFR2-01: Storage endpoint cannot open a connection through the NATGateway

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

##### Preconditions

- As in FR-5; the VM from TC-FR5-01, which has no ExternalIPAttachment, listens on TCP 2222.

##### Steps

1. From the NFS server, connect to the NAT address on TCP 2222.
2. From the NFS server, connect to the VM's tenant address on TCP 2222.

##### Expected Results

- Both connections fail; the VM's listener logs no connection.

### NFR-3: Per-tenant source address

#### TC-NFR3-01: Same CIDR in two tenants, two source addresses

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

##### Preconditions

- As in FR-5; two tenants with the same default VirtualNetwork CIDR, each with a VM; the export admits
  both tenants.

##### Steps

1. Mount the export from tenant A's VM.
2. Mount the export from tenant B's VM.
3. Read the NFS server's client log.

##### Expected Results

- Both mounts succeed.
- The log shows two different client addresses, each the `default-nat` address of its tenant.

## Gaps

### Requirement Coverage Gaps

- **FR-7** is documentation-only (installation guide, tenant guide, value descriptions). It is checked in
  documentation review, not by a test case.
- **FR-3** has only the manual review TC-FR3-01. By decision D10 no code checks Cluster networks, so no
  automated case asserts a rejection, and no case asserts that an overlapping Cluster is accepted.
- **M4 (TC-FR5-01 to TC-FR5-04, TC-FR6-01, TC-NFR2-01, TC-NFR3-01) is not execution-ready.** No lab has an
  IP storage endpoint on the NAT path yet, and the suite file does not exist. Prerequisite, owned by
  [QE] with `osac-test-infra`: add a vendor-neutral storage server to the Netris lab (`infra/netris/`): a
  plain Linux NFS server (an iSCSI or NVMe/TCP target can follow) outside the fabric gateway, routed to and
  from the lab's ExternalIPPool CIDRs, with its range in the lab's `excludedIpv4Cidrs` and a lab verify
  step that mounts from a VM on a tenant default network and checks the server logs the NAT address. No
  Jira ticket exists yet. No lower tier covers the deployed path: the existing Netris VMaaS NAT egress test
  proves SNAT to a public `egressURL`, not to a storage endpoint.
- **NFR-2 covers only workloads without an ExternalIPAttachment.** Workloads with one stay reachable by
  design; no case tests that.
- **CLI and UI for VirtualNetwork rejection.** TC-IPAM-03 uses the API only. The CLI and UI show the server
  error; no case checks the CLI message for a VirtualNetwork, and no osac-ui test is planned. Unresolved, no
  ticket.
- **Rollout completing after a range is removed** (PRD acceptance criterion) is shown by the TC-FR4-01 "no
  overlap" row, not by a deployed rollout. Unresolved at the deployed tier.
- **Existing Cluster networks at rollout are not checked by code.** This is a decision (clarifications
  R2.Q1); TC-FR4-02 reviews the documented admin check, and no automated case exists or is planned.
- **Integration testing guide note.** The guide's Networking design note says the dev profile "sets no
  `excludedIpv4Cidrs`", but `osac-installer/values/dev/kind-instance.yaml` sets `192.0.2.0/24` and
  TC-IPAM-03 uses it. The documentation work corrects the note.

### Interface Change Coverage Gaps

- **IC-2** is documentation-only. M3 checks that its value and schema description edits keep rendering;
  TC-FR3-01 and TC-FR4-02 review the Cluster guidance by hand; the rest is checked with FR-7 in
  documentation review.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 17 |
| Critical | 2 |
| High | 11 |
| Medium | 4 |
| Low | 0 |
| Automated | 14 |
| Manual | 3 |
| Requirements with test cases | 9 / 10 |
| Interface changes with test cases | 1 / 1 |
