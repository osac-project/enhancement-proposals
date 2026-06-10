---
title: region-api-abstraction-and-v1-topology
authors:
  - eranco74
creation-date: 2026-01-25
last-updated: 2026-01-25
tracking-link:
  - TBD
see-also:
  - https://github.com/osac-project/enhancement-proposals/pull/19
  - https://github.com/osac-project/docs/tree/main/architecture
replaces:
  - N/A
superseded-by:
  - N/A
---

# Region API Abstraction and V1 Topology

## Summary

This proposal establishes the definitive architectural mapping of **Region** and **Availability Zone (AZ)** constructs for the OSAC Virtualization Platform.

It decouples the **Logical API Contract** (what the user sees) from the **Physical Implementation** (how it is built).
* **Logical Contract:** A Region is a unified management boundary containing multiple Availability Zones for High Availability (HA).
* **V1 Implementation:** A Region maps 1:1 to a single OpenShift Cluster, and Availability Zones map to physical Failure Domains (Racks) via MachineSets.

This approach delivers a standard IaaS experience immediately (**Phase 1**) while retaining the flexibility to evolve into a multi-cluster federated model (**Phase 2**) once the VPC Operator matures.

## Motivation

To provide a competitive "Sovereign Cloud" experience, tenants require clear IaaS abstractions for workload placement and resilience. Users consuming Virtual Machines expect to deploy workloads across distinct failure domains within a single Region.

Currently, the platform lacks a formalized definition of these domains. Without this, Cloud Administrators have no standard way to configure physical infrastructure (racks, clusters) to expose these High Availability concepts to users.

**Architectural Justification:**
We must reconcile the "Ideal State" (Region = Collection of Clusters) with the prohibitive complexity of the current networking landscape. Implementing unified Subnets, NAT Gateways, and Security Groups across distinct clusters effectively requires engineering a bespoke cloud networking control plane from the ground up.

To avoid this overhead, we are selecting the **Single-Cluster Topology** for Phase 1. This allows us to leverage the stable, existing OVN-Kubernetes SDN to provide the necessary networking features (Subnets, Security Groups) without complex federation.

### User Stories (Cloud Admin Focus)

* **As a Cloud Administrator**, I want to onboard a new OpenShift Cluster and register it as a distinct **Region** (e.g., `us-east-1`), so that tenants can begin provisioning resources within that boundary.
* **As a Cloud Administrator**, I want to map physical racks to logical **Availability Zones** by applying standard node labels (`topology.kubernetes.io/zone=us-east-1a`), so that the scheduler is aware of the physical failure domains.
* **As a Cloud Administrator**, I want to configure **MachineSets** that strictly target specific racks (AZs), so that when the cluster autoscales or remediates nodes, it respects the physical isolation guarantees.


### Goals and Non-Goals

#### Goals

* **Establish a Stable API:** Define `Region` and `AvailabilityZone` as the primary consumption units for tenants, ensuring the API contract remains unchanged even if the backend implementation evolves.
* **Enable High Availability Placement:** Provide a standardized way for Cloud Admins to expose physical rack isolation (AZs) so tenants can distribute workloads across failure domains.
* **Codify Physical-to-Logical Mapping:** Standardize the use of `topology.kubernetes.io/zone` labels and MachineSets to enforce the boundary between physical infrastructure and logical cloud constructs.
* **Support Networking Primitives:** Ensure the topology allows for the use of standard Networking features (like Subnets, Gateways, RouteTables and Security Groups) within the single-cluster boundary in Phase 1.

#### Non-Goals

* **Define VPC Implementation:** This enhancement does **not** define how a VPC or the VPC Operator should function; it only defines the regional boundary where those networks will exist.
* **Cross-Cluster Networking in V1:** This proposal does not aim to solve L2/L3 stretching or Security Group synchronization across different OpenShift clusters.
* **Automated Rack-to-AZ Discovery:** This does not include tools to auto-scan physical hardware; Cloud Admins remain responsible for labeling nodes during the onboarding process.
* **Disaster Recovery (DR) Automation:** While this enables HA within a Region, automated failover between Regions is out of scope for this specific topology definition.

## Alignment with Architecture Guidelines

The [OSAC Architecture Document](https://github.com/osac-project/docs/tree/main/architecture) states that *"A single Management Cluster may be treated as a failure domain or availability zone."*

This proposal **refines** that definition by introducing two Topology Profiles to support the platform's evolution:

1.  **Converged Topology (Phase 1 - Proposed Here):**
    * **Region:** Single Cluster.
    * **AZ:** Physical Rack (MachineSet).
    * *Rationale:* This enables a flat, high-performance SDN (OVN-Kubernetes) immediately. It avoids the complexity of stitching together fragmented networks across clusters.

2.  **Federated Topology (Phase 2 - Future):**
    * **Region:** Collection of Clusters.
    * **AZ:** Distinct Cluster.
    * *Rationale:* This aligns with the "Cluster as Failure Domain" vision. It will be adopted once the **VPC Operator** enables seamless cross-cluster networking.

## Options Analysis

The architecture must support the scale, resilience, and isolation expected of a Sovereign Cloud provider. We evaluated two primary topology models:

### Option A: Distributed Federation (Region = Collection of Clusters)
In this model, every Availability Zone is a distinct OpenShift Cluster. The Region is a logical federation layer above them.

* **Blast Radius:** Minimal. If a cluster control plane fails, only that AZ is affected.
* **Networking & Security Complexity (Prohibitive):**
    * **IPAM Nightmares:** Requires a global IPAM to coordinate CIDRs across clusters. Without this, Cloud Admins must manually ensure VMs in the same "Region" but different "AZ clusters" do not have IP conflicts, breaking the "seamless cloud" experience.
    * **Security Inconsistency:** Ensuring a "Security Group" rule created in Cluster A is instantly and accurately replicated to Cluster B is a massive distributed systems challenge. Maintaining stateful firewall consistency across distinct control planes is prone to "drift" and security holes.
* **Verdict:** **Deferred.** Too complex for V1 without a mature VPC Operator.


### Option B: Single-Cluster Topology (Region = Single Cluster)
The Region is a single OpenShift Cluster; AZs are distinct physical racks mapped via MachineSets.

* **Blast Radius:** High. If the cluster's control plane fails, the entire Region management is affected.
* **Networking Complexity:** **Low.** Uses standard OVN-Kubernetes. Subnets and Security Groups natively span all AZs (Racks) without extra orchestration.
* **Verdict:** **Selected for V1.** Immediate stability outweighs theoretical blast radius risks.

## Proposal: The V1 Architecture

### 1. Technical Mapping
| IaaS Concept | Physical Reality (V1) | Implementation Mechanism |
| :--- | :--- | :--- |
| **Region** | **Single OCP Cluster** | The API endpoint/Management boundary. |
| **Availability Zone** | **Physical Rack** | **MachineSets** + `topology.kubernetes.io/zone`. |
| **VPC / Subnet** | **Project / OVN** | Native OVN isolation provided by the cluster SDN. |

### 2. Mandatory Infrastructure Constraints
To ensure Phase 1 provides true isolation and performance, the following tweaks are integrated:

* **Physical Failure Domains:** An Availability Zone **must** map to a physical domain with independent power (PDU) and networking (Top-of-Rack switch).
* **API-First Guarantee:** The OSAC API will never expose "Cluster IDs" to tenants. This abstraction allows us to swap the backend to Phase 2 (Multi-Cluster) in the future without breaking user automation.

### 3. Evolution Strategy (Phase 2 - Future)

We acknowledge that the long-term architectural goal is to map `1 AZ = 1 Distinct Cluster` for maximum isolation. However, this requires the **VPC Operator** to abstract the complex networking between clusters.

* **Transition:** The Platform API will be updated to orchestrate workloads across multiple backing clusters under the same "Region" ID.
* **User Impact:** None. The API contract (Region/AZ) remains stable.

### Workflow Description

**Administrator Configuration Workflow:**
1.  **Rack Provisioning:** Admin provisions physical servers in "Rack A" and "Rack B".
2.  **Cluster Installation:** Admin installs OpenShift. During installation or post-install, Admin applies labels:
    * Nodes in Rack A $\rightarrow$ `topology.kubernetes.io/zone=zone-a`
    * Nodes in Rack B $\rightarrow$ `topology.kubernetes.io/zone=zone-b`
3.  **MachineSet Creation:** Admin creates `MachineSet-A` configured to provision nodes only with label `zone=zone-a`.

**Tenant Consumption Workflow:**
1.  Tenant requests a VM in `Region: region-1`.
2.  Tenant specifies `Availability Zone: zone-a`.
3.  The scheduler matches the request to nodes labeled `zone=zone-a` (Rack A).

## API Extensions

To support the Phase 1 Converged Topology, we introduce two primary Administrative APIs using gRPC/Protocol Buffers. These allow the Fulfillment Service to bridge the logical cloud request to the physical OpenShift cluster and its internal rack structure.

### API Protocol

All APIs are exposed via **gRPC** with Protocol Buffer definitions. This ensures:
* **Type Safety:** Strongly-typed schemas prevent runtime errors.
* **Performance:** Binary serialization reduces payload size and parsing overhead.
* **Streaming Support:** Future-ready for real-time cluster health monitoring.

### API Scopes

The Region and Availability Zone APIs are split into two distinct scopes:

#### Private API (Admin-Only)
Administrative fields that expose the physical infrastructure mapping. These are **only accessible** to Cloud Administrators and internal services:
* `hub_id` - Reference to the hub (management cluster) this region uses
* `topology_profile` - Implementation strategy (converged vs federated)
* `failure_domain.id` - Physical rack identifier
* `failure_domain.node_selector` - Kubernetes node selector for scheduling

#### Public API (User-Facing)
Logical cloud constructs exposed to end-users for workload placement:
* `region_id` - Logical region identifier (e.g., `us-east-1`)
* `region.name` - Human-readable region name
* `region.description` - Region description
* `availability_zone_id` - Logical AZ identifier (e.g., `us-east-1a`)
* `availability_zone.name` - Human-readable AZ name

End-users interact **only** with the public API fields. They never see hub references or physical rack details.

### 1. Region Registration (Hub Binding)

This private API registers a logical OSAC Region and binds it to a hub (management cluster). The hub contains the kubeconfig and connection details for the cluster where the cloudkit-operator resides.

**gRPC Method:** `private.v1.RegionService/CreateRegion`

```protobuf
message CreateRegionRequest {
  Region region = 1;
}

message Region {
  // Unique identifier - automatically generated
  string id = 1;

  private.v1.Metadata metadata = 2;

  RegionSpec spec = 3;
}

message RegionSpec {
  // Public API Fields
  string name = 1;                  // e.g., "US East (Appalachia)"
  string description = 2;

  // Private API Fields (Admin-Only)
  string hub_id = 3;                // Reference to the hub managing this region
  TopologyProfile topology_profile = 4;
}

enum TopologyProfile {
  TOPOLOGY_PROFILE_UNSPECIFIED = 0;
  TOPOLOGY_PROFILE_CONVERGED_V1 = 1;    // Region = Single Cluster
  TOPOLOGY_PROFILE_FEDERATED_V2 = 2;    // Region = Collection of Clusters
}
```

**Example Request:**
```protobuf
{
  region: {
    metadata: {
      name: "us-east-1"
      labels: {
        "environment": "production"
      }
    }
    spec: {
      name: "US East (Appalachia)"
      description: "Converged Regional boundary mapping 1:1 to Cluster-01."
      hub_id: "hub-01"
      topology_profile: TOPOLOGY_PROFILE_CONVERGED_V1
    }
  }
}
```

### 2. Availability Zone Definition (Rack Mapping)

This private API maps the physical racks within the registered Region to logical AZs. In Phase 1, these AZs use the hub referenced by their parent Region.

**gRPC Method:** `private.v1.AvailabilityZoneService/CreateAvailabilityZone`

```protobuf
message CreateAvailabilityZoneRequest {
  AvailabilityZone availability_zone = 1;
}

message AvailabilityZone {
  // Unique identifier - automatically generated
  string id = 1;

  private.v1.Metadata metadata = 2;

  AvailabilityZoneSpec spec = 3;
}

message AvailabilityZoneSpec {
  // Public API Fields
  string name = 1;                  // e.g., "N. Virginia Zone A"
  string region_id = 2;             // Parent region reference

  // Private API Fields (Admin-Only)
  FailureDomain failure_domain = 3;
}

message FailureDomain {
  FailureDomainType type = 1;
  string id = 2;                    // Physical rack identifier
  map<string, string> node_selector = 3;
}

enum FailureDomainType {
  FAILURE_DOMAIN_TYPE_UNSPECIFIED = 0;
  FAILURE_DOMAIN_TYPE_RACK = 1;
  FAILURE_DOMAIN_TYPE_CLUSTER = 2;  // For Phase 2
}
```

**Example Request:**
```protobuf
{
  availability_zone: {
    metadata: {
      name: "us-east-1a"
    }
    spec: {
      name: "N. Virginia Zone A"
      region_id: "us-east-1"
      failure_domain: {
        type: FAILURE_DOMAIN_TYPE_RACK
        id: "rack-01"
        node_selector: {
          "topology.kubernetes.io/zone": "us-east-1a"
        }
      }
    }
  }
}
```

### 3. Hub Relationship

The **Hub** is the management cluster that hosts the control plane for fulfillment operations. Each region references exactly one hub.

**Hub Definition (from existing API):**
```protobuf
message Hub {
  string id = 1;
  private.v1.Metadata metadata = 2;
  bytes kubeconfig = 3;          // Contains address and credentials
  string namespace = 4;          // Namespace for cluster orders
}
```

**Key Points:**
* **Hub = Management Cluster:** The hub contains the kubeconfig with the API endpoint and credentials for the OpenShift cluster.
* **Region → Hub Reference:** Each region points to a hub via `region.spec.hub_id`.
* **Current Design:** 1:1 relationship - one region points to one hub.

**API Visibility:**
* The `hub_id` field is part of the **private API** (admin-only).
* End-users never see hub references. They only interact with `region_id` and `availability_zone_id`.
* The fulfillment service uses the hub's kubeconfig to connect to the cluster and create cluster orders in the specified namespace.

**Example:**
```
Hub: hub-01
  ├── kubeconfig: (contains api.cluster-01.provider.com:6443)
  ├── namespace: "osac-orders"
  └── Region: us-east-1
        ├── AZ: us-east-1a (Rack-01)
        └── AZ: us-east-1b (Rack-02)

Hub: hub-02
  ├── kubeconfig: (contains api.cluster-02.provider.com:6443)
  ├── namespace: "osac-orders"
  └── Region: us-west-1
        ├── AZ: us-west-1a (Rack-03)
        └── AZ: us-west-1b (Rack-04)
```

**Future Evolution:**
* In Phase 2, when regions may span multiple clusters, a region might reference multiple hubs.
* The API contract for regions and AZs remains stable - only the internal implementation changes.

### 4. Data Model Summary

* **Hub:** The management cluster that hosts the fulfillment control plane. Contains kubeconfig and connection details.
* **Region:** A logical IaaS boundary that references a hub. Acts as the user-facing "Gateway" to cloud resources.
* **AZ:** A logical failure domain within a region, mapped to physical racks via node selectors.
* **Topology Profile:** Explicitly defined in `region.spec.topology_profile` to indicate converged (single-cluster) vs federated (multi-cluster) implementation.

### Implementation Details/Notes/Constraints

**Zone Mapping via MachineSets:**
We will rigidly map MachineSets to physical infrastructure tags.
* `MachineSet-A` $\rightarrow$ `topology.kubernetes.io/zone=us-east-1a` $\rightarrow$ Physical Rack 1
* `MachineSet-B` $\rightarrow$ `topology.kubernetes.io/zone=us-east-1b` $\rightarrow$ Physical Rack 2


**Networking Abstraction:**
Since all Racks share the same OVN overlay:
* **Subnets:** Can logically span AZs without routing complexity.
* **Gateways:** A single set of Gateway Nodes can serve traffic for all AZs.

### Risks and Mitigations

**Risk: Single Point of Failure (Control Plane)**
* **Description:** The primary trade-off is the Blast Radius. A Region control plane failure affects all networking configuration updates for all AZs.
* **Mitigation:** We explicitly define the "Region" as the failure domain. Critical tenant workloads requiring higher survivability must be deployed across **two distinct Regions**.

**Risk: Scalability Limits**
* **Description:** A Region is limited by the maximum node count of a single OCP cluster (~2,000 nodes).
* **Mitigation:** The Cloud Administrator can create additional Regions to accommodate growth.

## Implementation Roadmap

### Phase 1: Standardization (Target: v1.0)
* Define the **Region API** and enforce `1 Region = 1 Cluster` mapping.
* Configure Installer/MachineSets to apply `topology.kubernetes.io/zone` labels based on Rack ID.
* **Goal:** Admins can configure HA-ready infrastructure using standard labels.

### Phase 2: Federation (Target: v2.0)
* **Condition:** VPC Operator reaches maturity.
* Introduce **Multi-Cluster Regions** where `Region 1` spans `Cluster A` and `Cluster B`.
* **Goal:** Unlimited scale and isolated AZ failure domains.
