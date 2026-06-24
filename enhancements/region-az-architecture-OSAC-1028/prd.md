# Region and Availability Zone Architecture Alignment

| Field       | Value   |
|-------------|---------|
| Author(s)   | Avishay Traeger |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1028 |
| Date        | 2026-06-23 |

## 1. Problem Statement

OSAC lacks a formalized region and availability zone architecture. Tenant users have no way to select fault domains for workload placement, and cloud infrastructure admins have no standard mechanism to map physical infrastructure to logical failure domains. Virtual networks carry a region string but no corresponding deployment model defines what a region is, and availability zones are entirely absent from the data model. Without these constructs, OSAC cannot offer the high-availability guarantees and placement controls that cloud-native workloads require.

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenant users can place VMs, bare-metal instances, and worker nodes in specific availability zones through the API and UI.
- Cloud infrastructure admins can deploy an OSAC region as a highly available, cross-AZ deployment with no single AZ as a point of failure.
- All workloads and OSAC services are contained within a region, so that a failure in one region does not impact another.
- Virtual networks span all AZs within a region, enabling cross-AZ communication without cross-region networking.
- OSAC services can be deployed and upgraded in a highly available manner without downtime.

### 2.2 Non-Goals

- Multi-region support — this PRD scopes a single region. Topics such as cross-region networking and IAM federation are out of scope.
- IAM service implementation.
- Specific hardware topology within an AZ (e.g., rack-level placement within a single AZ).
- Automated discovery of physical-to-AZ mappings (admins define AZ assignments in inventory).
- A cross-region API or portal for listing/selecting regions (each region is accessed via its own endpoint).

## 3. Requirements

### 3.1 Functional Requirements

#### Region

- **FR-1:** A region is defined as an OSAC deployment — the OpenShift cluster running fulfillment-service plus everything it manages (workload clusters, tenant VMs, bare-metal hosts, networking). Each region operates its own API endpoint, database, and operator instances. [User]
- **FR-2:** All workloads and OSAC services are contained within a region. Users work with a specific region to deploy workloads. [User]

#### Availability Zone

- **FR-3:** An Availability Zone is a logical grouping of infrastructure within a region, with independent power, cooling, and networking from other AZs. An Availability Zone entity must be exposed so tenants and admins can discover and select AZs. [User]
- **FR-4:** Availability zones must be exposed in the public API and UI as a selectable attribute so tenant users can list available AZs and choose placement. [User]
- **FR-5:** Cloud infrastructure admins must be able to create and manage availability zones within a region via the private API. [User]

#### Workload Placement

- **FR-6:** ComputeInstance creation must accept an optional availability zone parameter, placing the VM or bare-metal instance in the specified AZ. [User]
- **FR-7:** Cluster creation must accept optional availability zone parameters for worker node placement, enabling cross-AZ worker distribution. [User]
- **FR-8:** When a tenant specifies an availability zone for workload placement, the system must schedule the workload in the requested AZ. [User]
- **FR-9:** Tenant workloads should run in separate workload cluster(s) from the OSAC control plane for production deployments. Single-cluster deployments must also be supported for smaller environments. [User]

#### Networking

- **FR-10:** Virtual networks must be region-wide, spanning all availability zones within a region. [User]
- **FR-11:** Subnets inherit their region scope from their parent virtual network. No changes to subnet region behavior are required. [User]

#### Inventory and Installation

- **FR-12:** The inventory model must include an AZ assignment for each host, so the system knows which AZ a bare-metal host or node belongs to. [User]
- **FR-13:** The enclave installation process must consume AZ topology information when deploying the region, distributing infrastructure components across AZs. [User]

#### High Availability

- **FR-14:** For HA deployments, a region must support a minimum of 2 availability zones. The OSAC control plane (fulfillment-service, operators, database) must be deployable across multiple AZs so that loss of a single AZ does not cause control plane downtime. Single-AZ regions must also be supported for non-HA use cases (test, dev, smaller providers). [User]
- **FR-15:** OSAC services must support HA deployment and a zero-downtime upgrade strategy when deployed across multiple AZs. [User]

## 4. Acceptance Criteria

- [ ] A tenant user can list available availability zones via the API.
- [ ] A tenant user can create a ComputeInstance specifying an availability zone, and the instance is placed in that AZ.
- [ ] A tenant user can create a cluster specifying AZ placement for worker nodes, and the nodes are distributed accordingly.
- [ ] Virtual networks span all AZs within the region.
- [ ] When a tenant specifies an AZ, the system places the workload in the requested AZ.
- [ ] The inventory model includes AZ assignment per host, and the enclave installer consumes this topology.
- [ ] A single-AZ region can be deployed for non-HA use cases.
- [ ] When deployed in HA mode with 2+ AZs, the OSAC control plane can survive the loss of one AZ without service interruption.
- [ ] A tenant user can view and select availability zones in the UI when creating a workload.
- [ ] OSAC services can be upgraded with zero downtime when deployed in HA mode.

## 5. Assumptions

- OpenShift Hosted Control Planes support distributing control plane and worker nodes across availability zones via topology-aware scheduling.
- The enclave installation tooling (osac-installer) can be extended to accept AZ topology as input without a fundamental redesign.

## 6. Dependencies

- **fulfillment-service:** The AvailabilityZone entity and AZ-aware scheduling must be added to the fulfillment service.

## 7. Risks

### 7.1 Cross-AZ network latency

Distributing control plane components across AZs introduces inter-AZ network latency for database replication and operator coordination.

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Validate that PostgreSQL synchronous replication and etcd consensus tolerate expected inter-AZ latencies (typically 1-2ms within a metro area).

### 7.2 Hosted Control Plane AZ distribution

OpenShift Hosted Control Planes may have constraints on distributing control plane pods across AZs that are not yet validated in OSAC's deployment model.

- **Owner:** To be determined
- **Mitigation:** Validate HCP AZ distribution capabilities early in the design phase. Document any limitations as constraints on FR-7.
