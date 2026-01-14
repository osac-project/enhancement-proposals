---
title: Pluggable Inventory Sources
authors:
  - Juan Hernández
creation-date: 2025-12-10
last-updated: 2026-01-14
tracking-link:
  - TBD
replaces:
superseded-by:
---

# Pluggable Inventory Sources

## Summary

This document proposes enhancements to the fulfillment service to support pluggable inventory
sources. An inventory source is an external system that manages the physical infrastructure
(hosts, racks, network configuration, etc.) and provides this information to the fulfillment
service. By supporting pluggable inventory sources, the fulfillment service can integrate with
different datacenter management systems without requiring changes to its core logic.

The proposal includes API extensions to hosts, host classes, clusters, and hubs that capture the
additional hardware and configuration details needed for provisioning bare-metal infrastructure.
It also introduces a synchronization architecture where inventory source adapters run as separate
deployments and communicate with the fulfillment service through its private API.

## Motivation

The fulfillment service needs to provision clusters on bare-metal hosts. However, physical
infrastructure is typically managed by specialized datacenter management systems such as NVIDIA
Base Command Manager (BCM), OpenStack Ironic, or custom inventory databases. Each of these systems
has its own API, data model, and capabilities.

### Why Store Inventory Data?

Storing inventory information in the fulfillment service database serves two important purposes:

**Decoupling components from inventory sources**: When inventory data is available through the
fulfillment service API, other components (such as provisioning systems) can work independently of
the specific inventory source being used. For example, during a proof of concept integrating with
NVIDIA BCM, it became clear that using OpenStack for provisioning would be impractical due to its
complexity. Exploring alternatives like Metal3 was straightforward because it only required a
simple controller that reads host information from the fulfillment service API. This flexibility
is only possible when the inventory data is accessible through a single, consistent interface.

**Reducing integration complexity**: When there are `n` inventory sources and `m` provisioning
systems, direct integration would require `n × m` connectors—each inventory source would need to
know how to communicate with each provisioning system. By centralizing inventory data in the
fulfillment service, only `n + m` integrations are needed: each inventory source synchronizes with
the fulfillment service, and each provisioning component reads from it.

### Why a Pluggable Architecture?

Rather than embedding support for each inventory source directly into the fulfillment service, a
pluggable architecture allows:

- Integration with existing datacenter management systems without modifying core service logic.
- Different deployments to use different inventory sources based on their infrastructure.
- Independent development and maintenance of inventory source adapters.
- Testing and validation of the core service without requiring access to physical infrastructure.

### User Stories

- As a provider, I want to integrate my existing datacenter management system with the fulfillment
  service so that I can leverage my current inventory data.
- As a provider, I want to define host classes that map to my hardware categories so tenants can
  request specific types of resources.
- As a provider, I want the fulfillment service to automatically discover hosts from my inventory
  system and keep the data synchronized.
- As a provider, I want to use provisioning systems (such as Metal3 or Ironic) that can manage
  host power and boot operations during cluster provisioning.
- As a tenant, I want to see which hosts are assigned to my clusters so I can understand my
  resource allocation.

### Goals

- Define API extensions to capture hardware details needed for bare-metal provisioning.
- Establish a synchronization pattern for inventory source adapters.
- Support hub configuration for HyperShift-based cluster provisioning.
- Enable host assignment tracking for clusters.

### Non-Goals

The following are explicitly out of scope for this proposal:

- Implementation of specific inventory source adapters beyond the example provided.
- Automatic hardware discovery without an inventory source.
- Network topology management (addressed by VDCaaS proposal).
- Storage management and provisioning.
- DNS provisioning implementation. While DNS records are necessary for cluster access, the design
  and implementation of DNS provisioning is a separate concern. This proposal mentions DNS only as
  an example of a capability that provisioning systems may require.
- Mandating a specific host provisioning mechanism. While this document uses `BareMetalHost`
  resources (from the Metal3 project) as an example for provisioning bare-metal hosts, the
  pluggable inventory source architecture does not require this specific technology. Other
  provisioning mechanisms (e.g., Ironic directly, vendor-specific tools) can be used depending
  on the deployment environment.
- Defining a generic extension mechanism for custom object properties. While such a mechanism (a
  `properties` field in object metadata) would be useful for storing deployment-specific data, it
  is a general API enhancement that will be implemented independently of this proposal.
- Reverse synchronization from the fulfillment service back to inventory sources. This proposal
  only addresses reading inventory data; writing changes back to the source system is a separate
  concern.

## Proposal

### API Extensions

To support bare-metal provisioning, the fulfillment service API requires extensions to capture
hardware details, BMC configuration, and host assignment information.

#### Host Type Extensions

The host type requires additional fields to store hardware and provisioning details:

**Spec fields:**

| Field | Type | Description |
|-------|------|-------------|
| `bmc` | `BMC` | BMC (Baseboard Management Controller) connection details |
| `topology` | `map<string, string>` | Physical location attributes (e.g., region, zone, rack, slot) |
| `class` | `string` | Reference to the host class identifier |
| `boot_mac` | `string` | MAC address of the network interface used for PXE boot |
| `boot_ip` | `string` | IP address assigned for network boot |
| `available` | `bool` | Whether the host is available for allocation (excludes degraded, maintenance, or decommissioned hosts) |
| `title` | `string` | Human-readable title |
| `description` | `string` | Detailed description |

The `topology` field provides flexible physical location information. The keys are
deployment-specific (e.g., "region", "zone", "cabinet", "pod", "row", "slot", "u") and the values
are the corresponding location identifiers. Provisioning components can translate these into
appropriate constructs—for example, a Metal3-based provisioner could convert topology entries
into Kubernetes labels on `BareMetalHost` resources.

The `BMC` message contains:

| Field | Type | Description |
|-------|------|-------------|
| `url` | `string` | URL of the BMC interface (e.g., `redfish-virtualmedia://10.0.0.1/redfish/v1/Systems/1`) |
| `user` | `string` | Username for BMC authentication |
| `password` | `string` | Password for BMC authentication |
| `insecure` | `bool` | Whether to skip TLS certificate verification |
| `trusted_cas` | `string` | PEM-encoded CA certificates to trust when verifying the BMC's TLS certificate |

**Status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `hub` | `string` | Identifier of the hub managing this host |

Note: Host-to-cluster assignment will be tracked through a `HostPool` resource rather than a
field on the host itself, allowing for more flexible pool-based allocation.

#### Cluster Type Extensions

The cluster type requires extensions to track host assignments:

**Status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `alias` | `string` | Short alias used for Kubernetes object names in the hub |
| `port` | `int32` | NodePort number allocated for the cluster API service |

**ClusterNodeSet extensions:**

| Field | Type | Description |
|-------|------|-------------|
| `hosts` | `repeated string` | List of host identifiers assigned to this node set |

#### Hub Type Extensions

The hub type requires additional configuration for HyperShift-based provisioning:

| Field | Type | Description |
|-------|------|-------------|
| `pull_secret` | `string` | Container registry credentials for pulling images |
| `ssh_public_key` | `string` | SSH public key to install on provisioned hosts |
| `ip` | `string` | IP address of the hub cluster (used for DNS configuration) |

### Hub Reconciler

A new hub reconciler is introduced to manage the Kubernetes resources required for HyperShift-based
cluster provisioning. When a hub is created or updated, the reconciler ensures the following
resources exist in the hub cluster:

1. **Namespace**: A dedicated namespace for the fulfillment service resources.

2. **Pull Secret**: A Kubernetes secret containing container registry credentials for pulling
   images during cluster installation.

3. **InfraEnv**: An Agent-based installer `InfraEnv` resource that configures the discovery ISO
   parameters, including SSH authorized keys and network configuration.

4. **CAPI Provider Role**: An RBAC role granting the Cluster API provider access to manage Agent
   resources for bare-metal provisioning.

The hub reconciler also starts a Kubernetes resource watcher for each hub. This watcher monitors
changes to relevant Kubernetes resources, signaling the appropriate fulfillment service entities
when changes occur. This enables reactive reconciliation instead of polling.

For example, in a hypothetical HyperShift-based deployment using Metal3 for bare-metal
provisioning, the watcher would monitor `HostedCluster`, `NodePool`, `BareMetalHost`, and `Agent`
resources. Different provisioning mechanisms would require watching different resource types.

### Inventory Synchronization Architecture

Inventory source adapters follow a common architecture pattern:

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│                     │     │                     │     │                     │
│  Inventory Source   │────▶│  Synchronizer       │────▶│  Fulfillment        │
│  (BCM, Ironic, etc) │     │  Deployment         │     │  Service            │
│                     │     │                     │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

The synchronizer is deployed as an optional component, separate from the core fulfillment service.
It periodically queries the inventory source and updates the fulfillment service database through
the private gRPC API. This design provides:

- **Loose coupling**: The core service has no knowledge of specific inventory sources.
- **Independent scaling**: Synchronizers can be scaled and configured independently.
- **Failure isolation**: Inventory source issues don't affect core service operations.
- **Flexible deployment**: Only the needed synchronizers are deployed for each environment.

#### Synchronization Protocol

Inventory synchronization should preferably be **event-driven**, with periodic synchronization
serving as a fallback mechanism. This approach minimizes latency and reduces unnecessary API calls.

**Event-Based Synchronization (Preferred)**

When the inventory source supports event notifications (webhooks, message queues, change streams,
etc.), the synchronizer should:

1. **Subscribe**: Register for change events from the inventory source.

2. **React**: When an event is received, fetch only the affected resource(s) from the inventory
   source.

3. **Transform**: Convert the inventory source data model to the fulfillment service data model.

4. **Reconcile**: Use the private API to create, update, or delete the corresponding fulfillment
   service entity.

**Periodic Synchronization (Fallback)**

When event-based synchronization is not available, or as a complement to catch missed events, the
synchronizer falls back to periodic polling:

1. **Fetch**: Query the inventory source for the current state of all resources (hosts,
   categories, racks, etc.).

2. **Transform**: Convert the inventory source data model to the fulfillment service data model.
   This includes extracting relevant metadata from inventory source fields.

3. **Reconcile**: For each resource, use the private API to create or update the corresponding
   fulfillment service entity. The synchronizer uses field masks to update only the fields it
   manages.

4. **Repeat**: Wait for the configured interval and repeat the process.

**Hybrid Approach**

The recommended pattern is to combine both mechanisms:

- Use event-based synchronization for real-time updates.
- Run periodic synchronization at longer intervals (e.g., hourly) to catch any missed events and
  ensure eventual consistency.
- Track synchronization state to avoid redundant updates when both mechanisms report the same
  change.

#### Host Class Mapping

Host classes in the fulfillment service correspond to hardware categories in the inventory source.
The synchronizer maps inventory categories to host classes, preserving:

- Unique identifier from the inventory source
- Human-readable name
- Title and description (extracted from inventory source metadata if available)

#### Host Synchronization

For each host in the inventory source, the synchronizer:

1. Searches for an existing host by identifier or name.
2. Creates a new host if not found, using the inventory source identifier.
3. Updates the host spec with BMC details, boot MAC/IP, topology, and host class reference.
4. Updates links back to the inventory source for operator reference.

#### Host Selection

The decision of which hosts to assign to a cluster (or host pool) is made by the provisioning
component, not the inventory source. Some inventory systems, like NVIDIA BCM, do not have host
selection capabilities. By storing topology and class information in the fulfillment service,
provisioning components can implement their own selection logic.

If an inventory system does provide selection capabilities, a provisioning component can be built
to delegate that decision. In such cases, the detailed topology information may not need to be
copied to the fulfillment service.

### Example: Minimal Synchronization (Ironic with Ansible)

The simplest deployment scenario illustrates that synchronizers and detailed inventory data are
optional. Consider a deployment where:

- **Inventory source**: OpenStack Ironic manages the physical hosts.
- **Provisioning**: Ansible playbooks interact directly with Ironic to provision hosts.

In this architecture, the Ansible playbooks already know how to communicate with Ironic; they
only need to know which types of hosts to provision for a given cluster. The fulfillment service
provides this information through the `class` field on hosts and cluster node sets.

The only inventory data required in the fulfillment service is:

- **Host classes**: Categories of hosts (e.g., "compute-large", "gpu-node") for allocation
  purposes.

No BMC credentials, boot MAC addresses, or other hardware details need to be synchronized because
Ironic already has this information and the playbooks know how to use it. In fact, some inventory
systems like Ironic may not expose BMC passwords through their APIs at all. In such environments,
administrators must choose a provisioning component that works directly with the inventory system
rather than expecting BMC information in the fulfillment service.

This pattern—where a single external system handles both inventory and provisioning—is common.
The disadvantage is that inventory fields like `bmc`, `boot_mac`, and `boot_ip` remain empty in
the fulfillment service, but this is acceptable when the provisioning component doesn't need them.

This minimal approach requires no synchronizer deployment at all; hosts and host classes can be
created using the API as needed. The proposal's API extensions are additive and optional.

This example demonstrates that the proposal does not impose additional complexity on deployments
that don't need detailed inventory data in the fulfillment service.

### Example: BCM Synchronizer

An example implementation for NVIDIA Base Command Manager (BCM) demonstrates a full synchronization
scenario where detailed hardware information is needed. The initial implementation uses periodic
synchronization; future iterations should leverage BCM's event capabilities if available to enable
real-time updates.

It is deployed as a separate Helm chart (`bcm-sync`) with the following configuration:

| Parameter | Description |
|-----------|-------------|
| `bcm.url` | URL of the BCM API endpoint |
| `bcm.credentialsSecret` | Kubernetes secret containing TLS client certificate and key |
| `bcm.syncInterval` | Interval between synchronization cycles |
| `grpc.server.address` | Address of the fulfillment service gRPC endpoint |

The BCM synchronizer maps:

- BCM device categories → Host classes
- BCM devices (LiteNode type) → Hosts
- BCM physical location → Host topology map entries
- BCM BMC settings → Host BMC configuration
- BCM network interfaces → Boot MAC and IP addresses

Note that we only synchronize the subset of inventory data required for provisioning components
to function. BCM stores extensive information about hardware, physical location, installed
packages, and more. Copying all of this would be impractical and unnecessary. The fields defined
in this proposal are sufficient for the provisioning use cases we support.

### Workflow Integration

Host assignment for clusters follows this general flow:

1. **Host Discovery**: Synchronizer creates/updates hosts with hardware details and host class
   references.

2. **Cluster Creation**: Tenant requests a cluster with node sets specifying host class and count.

3. **Host Selection**: Cluster reconciler selects unassigned hosts matching the requested host
   class.

4. **Host Provisioning**: Reconciler triggers the provisioning mechanism with BMC credentials
   from the host spec.

5. **Host Registration**: When hosts boot and complete provisioning, they are registered with
   the cluster.

6. **Status Update**: Host status is updated with the assigned cluster and hub identifiers.

#### Example: HyperShift with Metal3

As a concrete example of how a provisioning component might work, consider a hypothetical
deployment using HyperShift with Metal3 for bare-metal provisioning. Note that Metal3 is not
currently part of our bare-metal deployment; this is presented as an illustration of how the
pluggable architecture could support different provisioning mechanisms.

In this scenario, the workflow becomes:

1. **Host Discovery**: The synchronizer creates or updates hosts in the fulfillment service.

2. **BareMetalHost Creation**: Immediately after host discovery, the reconciler creates
   `BareMetalHost` resources in the hub cluster using BMC credentials from the host spec. This
   happens before any cluster is created, making hosts available in the Metal3 inventory.

3. **Cluster Creation**: Tenant requests a cluster with node sets specifying host class and count.

4. **Host Selection**: Cluster reconciler selects unassigned hosts matching the requested host
   class.

5. **Agent Binding**: When hosts boot and register as Agents, they are bound to the appropriate
   `HostedCluster`.

6. **Status Update**: Host status is updated with the assigned hub identifier.

Other provisioning mechanisms would implement steps 2 and 5 differently while maintaining the same
overall inventory synchronization and host selection patterns.

### Example: DNS Provisioning as a Related Concern

This section illustrates how the inventory synchronization pattern can inform the design of other
provisioning-related integrations. DNS provisioning is presented as an example; its detailed
design and implementation are out of scope for this proposal.

Bare-metal cluster provisioning typically requires dynamic DNS record management. When a cluster
is created, DNS records may need to be provisioned for:

- **API endpoint**: `api.<cluster-alias>.<base-domain>` pointing to the hub cluster IP where the
  hosted control plane runs.
- **Internal API endpoint**: `api-int.<cluster-alias>.<base-domain>` for internal cluster
  communication.
- **Ingress wildcard**: `*.apps.<cluster-alias>.<base-domain>` for application routes.

Following the pluggable pattern established for inventory sources, DNS provisioning could be
implemented as a separate component that:

- Receives cluster lifecycle events from the fulfillment service.
- Creates, updates, or deletes DNS records accordingly.
- Supports different DNS backends (BIND, Route53, etc.) through adapter implementations.

This example demonstrates how the architectural principles in this proposal—separation of concerns,
pluggable adapters, and event-driven updates—can be applied to other infrastructure integrations.

### Risks and Mitigations

**Risk**: Synchronization conflicts if multiple sources manage the same hosts.

**Mitigation**: Each host should be managed by a single inventory source. The host identifier
should be stable and unique across sources.

**Risk**: Stale data if synchronization fails.

**Mitigation**: Synchronizers should log failures clearly and expose health metrics. Operators
should monitor synchronization health.

**Risk**: Security of BMC credentials in transit and at rest.

**Mitigation**: BMC passwords are stored in the fulfillment service database. The gRPC connection
between synchronizer and service should use TLS. A separate enhancement proposal
([PR #16](https://github.com/innabox/enhancement-proposals/pull/16)) addresses secrets management,
introducing mechanisms for secure storage and reference-based secret handling.

**Risk**: External provisioning dependencies (DNS, DHCP, etc.) can fail independently.

**Mitigation**: Related provisioning mechanisms (discussed as examples in this proposal) should
implement idempotent operations with retry logic. The cluster reconciler should verify that
prerequisites are in place before marking clusters as ready.

### Drawbacks

- Additional deployment complexity with separate synchronizer components, though the minimal
  synchronization example shows this is optional for simpler architectures.
- When event-based synchronization is not available, falling back to periodic synchronization
  introduces latency for inventory changes.
- Not all inventory sources support event notifications, limiting real-time synchronization
  capabilities in some environments.
- BMC credentials are stored in the fulfillment service database, requiring appropriate security
  measures. The secrets management enhancement
  ([PR #16](https://github.com/innabox/enhancement-proposals/pull/16)) will address this concern.

## Alternatives

### Embedded Inventory Source Support

Embedding inventory source adapters directly in the fulfillment service was considered but
rejected because:

- It would require service redeployment to add new inventory sources.
- It would increase the core service's complexity and dependency footprint.
- It would make testing harder without access to all supported inventory systems.

### Inventory Source API Abstraction

An alternative approach is to define a standard API that all inventory sources must implement. The
fulfillment service would query this API on-demand rather than storing inventory data locally.
For example, when a provisioning component needs host information, it would call this abstraction
layer, which would delegate to the appropriate inventory source.

**Advantages**:

- No data duplication between the inventory source and the fulfillment service.
- Always returns up-to-date information without synchronization delays.
- Simpler architecture with fewer moving parts (no synchronizers needed).

**Disadvantages**:

- **Query performance**: Some inventory sources (such as BCM) lack query capabilities. Translating
  fulfillment service queries into inventory source API calls would require fetching entire
  collections and filtering in memory, which becomes expensive for large inventories.
- **Availability coupling**: The fulfillment service's ability to serve inventory data depends on
  the availability of the underlying inventory source. If BCM is down, hosts cannot be listed. With
  local storage, the fulfillment service remains operational even when the inventory source is
  temporarily unreachable.
- **Complexity in the abstraction layer**: Each inventory source has a different data model and
  capabilities. Building a sufficiently flexible abstraction that works well with all sources while
  maintaining good performance is challenging.

This proposal chooses local storage with synchronization primarily for query flexibility and
availability guarantees, accepting the tradeoff of eventual consistency.

## Test Plan

- Unit tests for API extensions and field handling.
- Integration tests with mock inventory data.
- End-to-end tests with BCM synchronizer against a test BCM instance.

## Graduation Criteria

- API extensions are stable and documented.
- BCM synchronizer is deployed and validated in a production-like environment.
- Documentation covers creating custom inventory source adapters.

### Dev Preview

- API extensions implemented in private API.
- BCM synchronizer functional with periodic synchronization as initial implementation.

### Tech Preview

- API extensions evaluated for public API inclusion.
- Event-based synchronization implemented for inventory sources that support it.
- Hybrid synchronization pattern (events + periodic fallback) validated.
- Monitoring and alerting guidance documented.

### GA

- Public API stable for tenant-facing fields.
- Multiple inventory source adapters validated.
- Security review completed for credential handling.

## Upgrade / Downgrade Strategy

New fields are additive and optional. Existing deployments without inventory sources continue to
work. Downgrading removes synchronizer functionality but preserves manually-created host data.

## Version Skew Strategy

Synchronizers should be compatible with the fulfillment service version they were released with.
Minor version skew between synchronizer and service is acceptable. Major version changes may
require synchronizer updates.

## Support Procedures

- Synchronizer logs should be checked for connection and authentication errors.
- Host data can be verified through the private API.
- Stale hosts can be manually deleted or updated through the private API.

## Infrastructure Needed

- Access to inventory source for synchronizer deployment (if using a synchronizer).
- TLS certificates for secure communication between synchronizer and fulfillment service.
- Network connectivity between synchronizer, inventory source, and fulfillment service.
