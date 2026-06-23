# Region and Availability Zone Architecture Alignment

| Field       | Value   |
|-------------|---------|
| Author(s)   | Avishay Traeger |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1028 |
| Date        | 2026-06-23 |

## 1. Problem Statement

OSAC lacks a formalized region and availability zone architecture. Tenant users have no way to select fault domains for workload placement, and cloud infrastructure admins have no standard mechanism to map physical infrastructure to logical failure domains. Hub selection is currently random, virtual networks carry a region string but no corresponding deployment model defines what a region is, and availability zones are entirely absent from the data model. Without these constructs, OSAC cannot offer the high-availability guarantees and placement controls that cloud-native workloads require.

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenant users can place VMs, bare-metal instances, and OpenShift clusters in specific availability zones through the API and UI.
- Cloud infrastructure admins can deploy an OSAC region as a highly available, cross-AZ deployment with no single AZ as a point of failure.
- Regions are fully independent — nothing shared between regions except IAM — so that a failure in one region does not impact another.
- Virtual networks span all AZs within a region, enabling cross-AZ communication without cross-region networking.
- OSAC services can be deployed and upgraded in a highly available manner without downtime.

### 2.3 Non-Goals

- Cross-region networking or federation.
- IAM service implementation.
- Multi-region failover or disaster recovery automation.
- Specific hardware topology within an AZ (e.g., rack-level placement within a single AZ).
- Automated discovery of physical-to-AZ mappings (admins define AZ assignments in inventory).
- A cross-region API or portal for listing/selecting regions (each region is accessed via its own endpoint).

## 3. Requirements

### 3.1 Functional Requirements

#### Region

- **FR-1:** A region is defined as an OSAC deployment — the OpenShift cluster running fulfillment-service plus everything it manages (workload clusters, tenant VMs, bare-metal hosts, networking). Each region operates its own API endpoint, database, and operator instances. [User]
- **FR-2:** Regions must share nothing except IAM. No database, message bus, or control plane state is shared between regions. [User]

#### Availability Zone

- **FR-3:** An Availability Zone entity must be defined in the protobuf data model (public and private APIs) representing a failure domain within a region. [User]
- **FR-4:** Availability zones must be exposed in the public API and UI as a selectable attribute so tenant users can list available AZs and choose placement. [User]
- **FR-5:** Cloud infrastructure admins must be able to create and manage availability zones within a region via the private API. [User]

#### Workload Placement

- **FR-6:** ComputeInstance creation must accept an optional availability zone parameter, placing the VM or bare-metal instance in the specified AZ. [User]
- **FR-7:** Cluster creation must accept optional availability zone parameters for both control plane and worker node placement, enabling cross-AZ clusters. [User]
- **FR-8:** The control plane must use AZ information when scheduling tenant workloads onto hubs, replacing the current random hub selection. [User]
- **FR-9:** Tenant workloads must run in separate workload cluster(s) from the OSAC control plane. [User]

#### Networking

- **FR-10:** Virtual networks must be region-wide, spanning all availability zones within a region. The existing `region` field on VirtualNetworkSpec continues to identify the region this deployment belongs to. [User]
- **FR-11:** Subnets inherit their region scope from their parent virtual network. No changes to subnet region behavior are required. [User]

#### Inventory and Installation

- **FR-12:** The inventory model must include an AZ assignment for each host, so the system knows which AZ a bare-metal host or node belongs to. [User]
- **FR-13:** The enclave installation process must consume AZ topology information when deploying the region, distributing infrastructure components across AZs. [User]

#### High Availability

- **FR-14:** The OSAC control plane (fulfillment-service, operators, database) must be deployable across multiple AZs within a region so that loss of a single AZ does not cause control plane downtime. [User]
- **FR-15:** A deployment and upgrade strategy must be defined for OSAC services that maintains availability during rolling upgrades across AZs. [User]

### 3.2 Non-Functional Requirements

- **NFR-1:** AZ-aware hub selection must not add more than 50ms latency to workload scheduling compared to the current random selection.
- **NFR-2:** The AvailabilityZone data model must follow existing OSAC protobuf conventions (metadata, spec/status pattern, CRUD services with HTTP annotations).
- **NFR-3:** Region isolation must be validated by architecture review — no shared state between regions other than IAM federation.

## 4. Acceptance Criteria

- [ ] AvailabilityZone protobuf type exists in both public and private API definitions, following OSAC conventions (metadata, spec, status, CRUD service).
- [ ] A tenant user can list available availability zones via the public API.
- [ ] A tenant user can create a ComputeInstance specifying an availability zone, and the instance is placed in that AZ.
- [ ] A tenant user can create a Cluster specifying AZ placement for control plane and workers, and the cluster nodes are distributed accordingly.
- [ ] Virtual networks span all AZs within the region.
- [ ] Hub selection uses AZ topology instead of random selection when an AZ constraint is specified.
- [ ] The inventory model includes AZ assignment per host, and the enclave installer consumes this topology.
- [ ] The OSAC control plane can survive the loss of a single AZ without service interruption.
- [ ] OSAC services can be upgraded with zero downtime using a rolling strategy across AZs.
- [ ] No shared state exists between regions other than IAM — validated by architecture review.

## 5. Assumptions

- IAM exists as an external service that supports federation across regions.
- The existing `region` field on VirtualNetworkSpec (currently a free-form string) remains valid as a region identifier without requiring migration to a new entity type.
- OpenShift Hosted Control Planes support distributing control plane and worker nodes across availability zones via topology-aware scheduling.
- The enclave installation tooling (osac-installer) can be extended to accept AZ topology as input without a fundamental redesign.

## 6. Dependencies

- **IAM service:** Region isolation requires IAM to be the only shared service. IAM federation must support cross-region identity without sharing other state.
- **osac-installer / enclave:** The installation process must be updated to consume AZ topology and distribute components accordingly (FR-13).
- **osac-aap:** Ansible roles for network provisioning and hosted cluster deployment must be updated to support AZ-aware placement.
- **osac-operator:** Controllers must be updated to pass AZ constraints during reconciliation (hub selection, workload scheduling).
- **fulfillment-service:** Protobuf definitions, database schema, server implementations, and controllers must be extended for the AvailabilityZone entity and AZ-aware scheduling.

## 7. Risks

### 7.1 Cross-AZ network latency

Distributing control plane components across AZs introduces inter-AZ network latency for database replication and operator coordination.

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Validate that PostgreSQL synchronous replication and etcd consensus tolerate expected inter-AZ latencies (typically 1-2ms within a metro area).

### 7.2 Hosted Control Plane AZ distribution

OpenShift Hosted Control Planes may have constraints on distributing control plane pods across AZs that are not yet validated in OSAC's deployment model.

- **Owner:** To be determined
- **Mitigation:** Validate HCP AZ distribution capabilities early in the design phase. Document any limitations as constraints on FR-7.

## 8. Open Questions

### 8.1 How should AZ-aware hub selection interact with existing capacity and affinity considerations?

- **Owner:** fulfillment-service team
- **Impact:** FR-8. The current random selection has no capacity awareness. AZ-aware selection could be combined with capacity checks, or capacity could be addressed separately.

### 8.2 What is the minimum number of AZs required for a highly available region deployment?

- **Owner:** Architecture team
- **Impact:** FR-14, FR-15. Determines whether 2-AZ or 3-AZ configurations are supported and what availability guarantees each provides.

### 8.3 How does the HA upgrade strategy interact with the OpenShift upgrade lifecycle?

- **Owner:** Cloud Infrastructure Admin / osac-installer team
- **Impact:** FR-15. OSAC services run on OpenShift — the upgrade strategy must account for both OSAC component upgrades and underlying OpenShift cluster upgrades.
