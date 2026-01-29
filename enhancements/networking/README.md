---
title: OSAC Networking API
authors:
  - agentil@redhat.com
creation-date: 2025-11-29
last-updated: yyyy-mm-dd
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
  - TBD
see-also:
  - N/A
replaces:
  - N/A
superseded-by:
  - N/A
---

# OSAC Networking API

## Summary

This enhancement introduces a Networking API for OSAC fulfillment services. The
API provides familiar cloud networking primitives (VirtualNetwork, Subnet,
SecurityGroup, PublicIPPool, PublicIP) as first-class resources. PublicIPPools
are defined by the service provider; tenants manage VirtualNetworks, Subnets,
SecurityGroups, and PublicIPs (allocated from a pool). The implementation
leverages OpenShift User Defined Networks (UDN) through a pluggable NetworkClass
architecture, enabling providers to offer different networking capabilities
based on their infrastructure.

The Networking API is designed as a foundational service for OSAC, intended to
be consumed by multiple services. **Compute Instance (VMaaS) will be the first
service to integrate with this API**, with Cluster-as-a-Service and
BareMetal-as-a-Service planned for future integration.

## Terminology

This section defines the key networking terms used throughout this enhancement:

- **Region**: A user-facing abstraction representing a geographic or logical
  grouping of infrastructure. In OSAC, a Region maps to an internal "Hub" (a
  managed OpenShift cluster). VirtualNetworks, PublicIPPools, and PublicIPs are
  scoped to a specific Region.

- **VirtualNetwork**: A tenant's isolated virtual network environment, similar
  to an AWS VPC or Azure VNet. Provides logical isolation and defines the
  overall address space (CIDR) for a tenant's network resources within a region.

- **Subnet**: A subdivision of a VirtualNetwork's IP address space. Resources
  are attached to Subnets to receive IP addresses and network connectivity.

- **SecurityGroup**: A stateful firewall that controls inbound and outbound
  traffic for resources. Rules specify allowed protocols, ports, and source/
  destination addresses. SecurityGroups are applied to resources within a
  VirtualNetwork.

- **PublicIPPool**: A provider-defined pool of public IPv4 addresses. Pools are
  scoped to a region and define one or more address ranges (CIDRs) from which
  PublicIPs can be allocated. Tenants allocate PublicIPs from a PublicIPPool.

- **PublicIP** (also known as **Floating IP**): A public IPv4 address allocated
  from a PublicIPPool. PublicIPs can be dynamically attached to and detached
  from resources. They persist independently of the resources they're attached
  to, allowing tenants to reassign them as needed.

- **PublicIPAttachment**: The binding between a PublicIP and a target resource.
  Creating an attachment routes traffic to the resource; deleting it removes the
  association without releasing the IP.

- **NetworkClass**: A provider-defined resource that specifies how
  VirtualNetworks are implemented. Enables pluggable networking backends (e.g.,
  `tenant-isolated` for basic UDN, `fabric-integrated` for advanced topologies).

## Motivation

OSAC needs a unified networking layer that provides tenants with the ability to
define and manage their network topology. By introducing networking as a
standalone API with first-class resources, we align with how major cloud
providers (AWS, Azure, GCP) approach networking.

This familiar model allows users to:

1.  Define their network topology before provisioning workloads
2.  Reference pre-existing networks when provisioning resources
3.  Manage security policies centrally through SecurityGroups that can be
    applied across multiple resources
4.  Create isolated network segments for different workloads or environments

The Networking API is designed with extensibility and reuse as core principles.
It provides a consistent networking experience that can be leveraged by any OSAC
service requiring network connectivity, starting with Compute Instance and
extending to Cluster-as-a-Service and BareMetal-as-a-Service

### User Stories

#### End User Stories

- As an end-user, I want to be able to create one or several VirtualNetworks
  that are isolated from each other
- As an end-user, I want to be able to define a Subnet in my VirtualNetwork
- As an end-user, I want to be able to define SecurityGroups to control traffic
  to resources in my VirtualNetwork
- As an end-user, I want to be able to attach resources to a Subnet in one of my
  VirtualNetworks
- As an end-user, I want to allocate a Public IP from a PublicIPPool in a region
- As an end-user, I want to attach and detach a Public IP to a resource

#### Provider Stories

- As a service provider, I want to be able to provide my own implementation of
  the Networking API through NetworkClasses
- As a service provider, I want to control which networking capabilities are
  available to tenants
- As a service provider, I want to define PublicIPPools per region so tenants
  can allocate PublicIPs from those pools

### Goals

- Introduce a Networking API as a foundational OSAC service with VirtualNetwork,
  Subnet, SecurityGroup, PublicIPPool, PublicIP, and PublicIPAttachment as
  first-class resources
- Design the API to be generic and reusable across all OSAC services (Compute
  Instance, Cluster-as-a-Service, BareMetal-as-a-Service)
- Implement a pluggable architecture (NetworkClass) that allows providers to
  offer different networking implementations
- Deliver initial integration with Compute Instance service as the first
  consumer of the Networking API
- Provide a first NetworkClass implementation (`tenant-isolated`) based on
  OpenShift User Defined Networks (UDN)

### Non-Goals

- Storage Networking
- Integration with Cluster-as-a-Service and BareMetal-as-a-Service (planned for
  future enhancements)
- APIs for NAT Gateways, Internet Gateways, and Load Balancers
- Tenant-definable PublicIPPools or BYOIP (pools are provider-defined only)

## Proposal

This proposal relies on User Defined Networks (UDN), a networking feature
provided by OpenShift that enables the creation of isolated networks within an
OpenShift cluster. UDN leverages OVN-Kubernetes to provide network isolation.

Because UDN is local to an OpenShift cluster, a Virtual Network must be tied to
a specific Hub in the OSAC architecture. A Hub represents a managed OpenShift
cluster that hosts tenant workloads and their associated network resources.
Since "Hub" is an internal OSAC concept not exposed to end-users, we propose to
present this as a **Region** in the user-facing API. This aligns with how other
cloud providers expose geographic or logical groupings of infrastructure, making
the model intuitive for users familiar with public cloud networking.

### NetworkClass

Different deployment scenarios may require different networking implementations.
For example, a basic deployment might use standalone UDN for simple tenant
isolation, while an advanced deployment could integrate with the underlying
network fabric to provide additional capabilities like multiple subnets,
external connectivity, or VLAN integration.

To accommodate this variability, we introduce the concept of
**NetworkClass**---a provider-defined resource that specifies how Virtual
Networks are implemented. This follows the same pattern as Kubernetes
`StorageClass` or `IngressClass`, where:

- **Providers** define available NetworkClasses with their capabilities and
  implementation details
- **Tenants** select a NetworkClass when creating a Virtual Network (or use the
  default)
- **Controllers** reconcile Virtual Networks based on the selected NetworkClass

This design ensures the networking API remains stable and user-friendly while
allowing providers to plug in different implementations as needed.

#### NetworkClass: `tenant-isolated`

This enhancement defines a single NetworkClass called `tenant-isolated`. This
class provides:

- **Isolated tenant networking**: Each Virtual Network is fully isolated from
  other tenants using OVN-Kubernetes
- **Single subnet per Virtual Network**: Due to UDN architecture constraints,
  each Virtual Network contains exactly one subnet
- **Layer 2 connectivity**: VMs within the same Virtual Network can communicate
  at Layer 2

The `tenant-isolated` class is suitable for deployments where:

- Tenants need simple, isolated networks for their workloads
- No integration with external network infrastructure is required
- Each logical network segment can be represented as a separate Virtual Network

Future enhancements may introduce additional NetworkClasses (e.g.,
`fabric-integrated`) that leverage UDN Localnet mode to provide multi-subnet
VirtualNetworks, external connectivity, and tighter integration with physical
network infrastructure.

The Networking API introduces a cloud-like abstraction layer built on
OpenShift's User Defined Networking (UDN). This design provides tenants with
familiar networking primitives while allowing providers to maintain control over
network configurations through NetworkClasses.

The proposal relies on the following core concepts:

- **NetworkClass**: A provider-defined resource that specifies how Virtual
  Networks are implemented. Different NetworkClasses enable different networking
  capabilities (e.g., single-subnet isolated networks vs. multi-subnet
  fabric-integrated networks). Tenants select a NetworkClass when creating a
  Virtual Network.
- **VirtualNetwork**: A tenant's isolated virtual network environment within a
  specific region. The implementation behavior depends on the selected
  NetworkClass. For the `tenant-isolated` class, VirtualNetwork is a logical
  grouping; the actual namespace and UDN are created per Subnet.
- **Subnet**: An IP address range within a VirtualNetwork. For the
  `tenant-isolated` NetworkClass, each Subnet maps to a dedicated namespace
  containing an OpenShift UserDefinedNetwork resource. Each VirtualNetwork
  contains exactly one Subnet due to UDN isolation constraints.
- **SecurityGroup**: A set of inbound and outbound traffic rules applied to
  resources within a VirtualNetwork. SecurityGroups are implemented using
  OVN-Kubernetes
  [NetworkPolicies](https://ovn-kubernetes.io/features/network-security-controls/network-policy/).
- **PublicIPPool**: A provider-defined pool of public IPv4 addresses, scoped to a
  region. Defines one or more address ranges (CIDRs) from which PublicIPs can be
  allocated. Tenants do not create pools; they allocate PublicIPs from existing
  pools.
- **PublicIP**: A floating public IP address allocated from a PublicIPPool.
  PublicIPs are tenant-wide and scoped to a region. The IP persists until
  explicitly released.
- **PublicIPAttachment**: Binds a PublicIP to a target resource (e.g.,
  ComputeInstance). Only one attachment per PublicIP is allowed at a time.

The Networking API will be implemented through updates to the following O-SAC
components:

- **Fulfillment Service**: Expose the Networking API endpoints for
  VirtualNetwork, Subnet, SecurityGroup, PublicIPPool, PublicIP, and
  PublicIPAttachment resources
- **Fulfillment CLI**: Provide tenant access to Networking API operations
- **O-SAC Operator**: Manage and reconcile networking Custom Resources,
  translating them to OpenShift primitives (UDN, NetworkPolicies, ...)
- **O-SAC Ansible**: Execute provider's Ansible playbooks to perform custom
  operations to the networking infrastructure (e.g., allocating a Public IP
  from a pool and assigning it to a resource)

### Integration with OSAC Services

The Networking API is designed to be consumed by multiple OSAC services. This
enhancement delivers the first integration:

**Initial Integration (this enhancement):** - **ComputeInstance**: Extended with
a `network_attachments` field that references Subnets and SecurityGroups within
the tenant's VirtualNetwork

**Planned Future Integrations:** - **HostPool**: Will leverage the
`networkAttachments` pattern, referencing Subnets and SecurityGroups for
bare-metal networking - **Cluster**: Will support cluster-level network
configuration for OpenShift cluster networking

### Workflow Description

**Provider** is a cloud administrator responsible for managing the overall
network infrastructure and defining what networking capabilities are available
to tenants.

**Tenant** is an organization or user that consumes networking services to
connect their resources (VMs, bare metal hosts, clusters).

#### VirtualNetwork Creation

1.  The tenant uses the Fulfillment CLI to create a VirtualNetwork by specifying
    a name, region, NetworkClass, and CIDR range.
2.  The Fulfillment Service validates the request and creates a VirtualNetwork
    custom resource (CR) in the appropriate Hub (identified by the region).
3.  The O-SAC Operator detects the new VirtualNetwork CR and marks it as ready.
4.  Depending on the NetworkClass, additional provisioning operations may be
    performed (e.g., configuring external fabric integration, allocating network
    resources from infrastructure providers).
5.  The tenant uses the Fulfillment CLI to check the VirtualNetwork status.

#### Subnet Management

1.  The tenant uses the Fulfillment CLI to create a new Subnet within their
    VirtualNetwork.
2.  The Fulfillment Service validates that the CIDR is within the
    VirtualNetwork's CIDR range and creates a Subnet CR.
3.  The O-SAC Operator detects the new Subnet CR and begins reconciliation:
    - Creates a dedicated namespace for the Subnet
    - Provisions the corresponding UserDefinedNetwork within that namespace
4.  Depending on the NetworkClass, additional provisioning operations may be
    performed (e.g., configuring VLAN tags, establishing connectivity to
    external networks).
5.  Once ready, the Subnet can be referenced when creating resources.

#### Attaching Resources to Networks

1.  When creating a resource (e.g., ComputeInstance), the tenant specifies a
    `network_attachment` referencing a Subnet and optionally one or more
    SecurityGroups.
2.  The Fulfillment Service validates that the Subnet and SecurityGroups belong
    to the tenant's VirtualNetwork.
3.  The O-SAC Operator configures the resource's network interfaces to attach to
    the specified UserDefinedNetworks.
4.  Depending on the NetworkClass, additional network configurations may be
    applied (e.g., DHCP reservations, external routing setup).
5.  The resource receives an IP address from the Subnet's CIDR range (the
    allocation method depends on the NetworkClass implementation).

#### SecurityGroup Configuration

1.  The tenant creates or updates a SecurityGroup with ingress/egress rules.
2.  The Fulfillment Service creates or updates the SecurityGroup CR.
3.  The O-SAC Operator translates the rules into OVN-Kubernetes NetworkPolicies.
4.  Depending on the NetworkClass, additional security configurations may be
    applied (e.g., hardware firewall rules, fabric-level ACLs).
5.  Traffic to/from resources associated with the SecurityGroup is filtered
    according to the rules.

#### PublicIPPool and PublicIP Allocation

1.  The **provider** defines one or more PublicIPPools per region (e.g., via
    admin API or cluster-scoped CR), specifying the region and one or more
    CIDR ranges for each pool.
2.  The Fulfillment Service (or O-SAC Operator) creates PublicIPPool resources
    and tracks capacity (total, allocated, available).
3.  A **tenant** requests a PublicIP by specifying a pool name (e.g.,
    `--pool public-us-east-1`). The pool determines the region and address
    ranges from which an IP can be allocated.
4.  The Fulfillment Service validates that the pool exists and has available
    capacity, then creates a PublicIP CR and allocates an address from that
    pool.
5.  The tenant can attach the PublicIP to a resource via PublicIPAttachment;
    releasing the PublicIP returns the address to the pool.

### API Extensions

The following sections describe the API resources introduced by this
enhancement.

#### VirtualNetwork

A tenant requests a VirtualNetwork to create an isolated network environment
with its own address space.

Example CLI command:

    $ ./fulfillment-cli create virtualnetwork \
           --cidr 10.0.0.0/16 \
           --network-class tenant-isolated \
           --name my-network

The Fulfillment CLI sends this JSON request to the Fulfillment Service:

``` json
{
  "object": {
    "id": "my-network",
    "spec": {
      "cidr": "10.0.0.0/16",
      "networkClass": "tenant-isolated"
    }
  }
}
```

The Fulfillment Service creates the following VirtualNetwork CR:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: VirtualNetwork
metadata:
  name: my-network
  labels:
    tenantUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
spec:
  cidr: 10.0.0.0/16
  networkClass: tenant-isolated
status:
  state: Ready
  conditions:
  - type: Ready
    status: "True"
    lastTransitionTime: "2025-01-07T10:00:00Z"
```

#### Subnet

Subnets define IP address ranges within a VirtualNetwork. Each Subnet maps to a
dedicated namespace containing an OpenShift UserDefinedNetwork.

Example CLI command:

    $ ./fulfillment-cli create subnet \
           --virtual-network my-network \
           --cidr 10.0.1.0/24 \
           --name frontend-subnet

The Fulfillment Service creates the following Subnet CR:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: Subnet
metadata:
  name: frontend-subnet
  ownerReferences:
  - apiVersion: o-sac.openshift.io/v1alpha1
    kind: VirtualNetwork
    name: my-network
    uid: 77c9fe7g-2bg3-5903-bd23-58ce58ebde51
spec:
  virtualNetwork: my-network
  cidr: 10.0.1.0/24
status:
  state: Ready
  namespace: tenant-66b8ed6f-subnet-frontend-subnet
  udnName: frontend-subnet-udn
```

The O-SAC Operator creates a namespace for the Subnet and the corresponding
UserDefinedNetwork:

``` yaml
apiVersion: k8s.ovn.org/v1
kind: UserDefinedNetwork
metadata:
  name: frontend-subnet-udn
  namespace: tenant-66b8ed6f-subnet-frontend-subnet
spec:
  topology: Layer2
  layer2:
    role: Primary
    subnets:
    - cidr: 10.0.1.0/24
      hostSubnet: 24
```

#### SecurityGroup

SecurityGroups define traffic filtering rules for resources within a
VirtualNetwork.

Example CLI command:

    $ ./fulfillment-cli create security-group \
           --virtual-network my-network \
           --name web-servers \
           --ingress "protocol:tcp,port:80,source:0.0.0.0/0" \
           --ingress "protocol:tcp,port:443,source:0.0.0.0/0" \
           --egress "protocol:all,destination:0.0.0.0/0"

The Fulfillment Service creates the following SecurityGroup CR:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: SecurityGroup
metadata:
  name: web-servers
  ownerReferences:
  - apiVersion: o-sac.openshift.io/v1alpha1
    kind: VirtualNetwork
    name: my-network
spec:
  virtualNetwork: my-network
  ingressRules:
  - protocol: TCP
    port: 80
    source: 0.0.0.0/0
    description: "Allow HTTP"
  - protocol: TCP
    port: 443
    source: 0.0.0.0/0
    description: "Allow HTTPS"
  egressRules:
  - protocol: All
    destination: 0.0.0.0/0
    description: "Allow all outbound"
status:
  state: Ready
```

The O-SAC Operator translates the SecurityGroup into an OVN-Kubernetes
NetworkPolicy:

``` yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-servers
  namespace: tenant-66b8ed6f-subnet-frontend-subnet
spec:
  podSelector:
    matchLabels:
      o-sac.openshift.io/security-group: web-servers
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - protocol: TCP
      port: 80
  - from:
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - protocol: TCP
      port: 443
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
```

#### PublicIPPool

PublicIPPools are provider-defined pools of public IPv4 addresses, scoped to a
region. A pool can contain multiple CIDR ranges; addresses are allocated from
any of those ranges. Tenants allocate PublicIPs from a pool; they cannot
create or delete pools.

Example provider workflow (e.g., via Fulfillment Service admin API or
cluster-scoped CR):

A provider defines a PublicIPPool:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: PublicIPPool
metadata:
  name: public-us-east-1
spec:
  region: us-east-1
  cidrs:
  - 203.0.113.0/24
  - 198.51.100.0/24
status:
  state: Ready
  capacity:
    total: 508      # sum of usable addresses across all CIDRs
    allocated: 12
    available: 496
```

#### PublicIP

PublicIPs are floating public IP addresses allocated from a PublicIPPool. They
are tenant-wide and scoped to a region, allowing them to be attached to any
resource in that region. A PublicIP must be allocated from a PublicIPPool.

Example CLI commands:

    $ ./fulfillment-cli create publicip --pool public-us-east-1 --name my-public-ip
    $ ./fulfillment-cli delete publicip my-public-ip

The Fulfillment Service creates the following PublicIP CR:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: PublicIP
metadata:
  name: my-public-ip
  labels:
    tenantUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
spec:
  pool: public-us-east-1
  # region is implied by the pool
status:
  state: Allocated  # Allocated | Attached | Releasing
  address: 203.0.113.45
```

#### PublicIPAttachment

PublicIPAttachment binds a PublicIP to a target resource. Only one attachment
per PublicIP is allowed at a time. Deleting the attachment detaches the IP but
does not release it.

Example CLI commands:

    $ ./fulfillment-cli create publicipattachment \
           --publicip my-public-ip \
           --target-type ComputeInstance \
           --target-name my-vm \
           --name my-attachment

    $ ./fulfillment-cli delete publicipattachment my-attachment

The Fulfillment Service creates the following PublicIPAttachment CR:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: PublicIPAttachment
metadata:
  name: my-attachment
  ownerReferences:
  - apiVersion: o-sac.openshift.io/v1alpha1
    kind: PublicIP
    name: my-public-ip
spec:
  publicIP: my-public-ip
  target:
    kind: ComputeInstance
    name: my-vm
status:
  state: Active
```

#### Integration: ComputeInstance

As the first consumer of the Networking API, ComputeInstance is extended with a
`network_attachments` field:

``` yaml
spec:
  template: ocp_virt_vm
  network_attachments:
  - subnet: frontend-subnet
    securityGroups:
    - web-servers
```

This allows tenants to attach their Compute Instances to specific Subnets and
apply SecurityGroups for traffic control.

### Implementation Details/Notes/Constraints

**NetworkClass Controller**: The NetworkClass resource is cluster-scoped and
managed by the provider. The O-SAC Operator watches NetworkClass resources to
determine which provisioner to use when reconciling VirtualNetworks.

**Namespace per Subnet**: For the `tenant-isolated` NetworkClass, each Subnet
gets its own namespace. Since UDNs are namespace-scoped in OpenShift, this
mapping ensures proper isolation. The VirtualNetwork itself is a logical
grouping that doesn't require a dedicated namespace.

**UDN Lifecycle**: A namespace and UserDefinedNetwork are created when a Subnet
is provisioned. Both are deleted when the Subnet is removed. The VirtualNetwork
can only be deleted after all its child Subnets have been removed.

### Risks and Mitigations

  ------------------------------------------------------------------------------
  Risk               Impact                  Mitigation
  ------------------ ----------------------- -----------------------------------
  UDN feature        UDN requires            Document minimum OpenShift version
  availability       OVN-Kubernetes and may  requirements; provide clear error
                     not be available in all messages if UDN is unavailable
                     OpenShift versions      

  Namespace          Many Subnets could lead Implement namespace quotas per
  proliferation      to namespace management tenant; consider namespace pooling
                     overhead (one namespace in future enhancements
                     per Subnet)             

  Network isolation  Misconfigured           Default-deny network policies;
  bypass             SecurityGroups could    validate SecurityGroup rules
                     expose tenant resources against allowed patterns

  API complexity     New networking concepts Provide sensible defaults;
                     add learning curve for  comprehensive CLI help and
                     users                   documentation
  ------------------------------------------------------------------------------

### Drawbacks

**Single Subnet per Virtual Network**: OpenShift's User Defined Networks (UDN)
are isolated from each other at the OVN level. This architectural constraint
means that each Virtual Network can only contain a single subnet. Unlike
traditional cloud providers where a Virtual Network can host multiple subnets,
our implementation maps one Subnet to one UDN, which inherently supports only
one subnet. Users requiring multiple isolated network segments must create
multiple Virtual Networks rather than multiple Subnets within a single Virtual
Network.

## Alternatives (Not Implemented)

### Alternative 1: Embed networking in ComputeInstance spec

Instead of separate VirtualNetwork/Subnet resources, networking could be defined
inline within the ComputeInstance specification.

**Why not selected**: This approach maintains the tight coupling we're trying to
eliminate. It prevents network reuse across resources and doesn't align with
cloud provider patterns that users are familiar with.

### Alternative 2: Use Multus directly without UDN abstraction

Directly expose Multus NetworkAttachmentDefinitions to tenants without the
VirtualNetwork/Subnet abstraction.

**Why not selected**: Multus NADs are lower-level primitives that expose
implementation details. The VirtualNetwork abstraction provides a cleaner tenant
experience and allows swapping implementations via NetworkClass.

### Alternative 3: Single VirtualNetwork per tenant (no explicit creation)

Automatically create one VirtualNetwork per tenant, eliminating the need for
explicit VirtualNetwork management.

**Why not selected**: This limits flexibility for tenants who need multiple
isolated network segments. It also restricts providers from offering
NetworkClasses that support multiple subnets within a VirtualNetwork. The
explicit VirtualNetwork creation aligns with cloud provider models and provides
better isolation control.

## Open Questions

1.  Should SecurityGroups be scoped to a VirtualNetwork or to the entire tenant?
    Current proposal scopes them to VirtualNetwork (similar to AWS), but
    tenant-wide SecurityGroups could simplify reuse.

2.  Should PublicIPPool or PublicIP be part of a NetworkClass? Today PublicIPPool
    is a standalone provider resource; future NetworkClasses might define how
    public IPs are implemented (e.g., NAT vs. direct allocation).

## Test Plan

*Section to be completed when targeted at a release.*

Testing strategy will include: - Unit tests for API validation and controller
logic - Integration tests for VirtualNetwork, Subnet, SecurityGroup,
PublicIPPool, PublicIP, and PublicIPAttachment lifecycle - E2E tests for
resource network attachment workflows - Multi-tenant isolation tests to verify
network separation

## Graduation Criteria

*Section to be completed when targeted at a release.*

Graduation from Dev Preview to Tech Preview: - Core API resources
(VirtualNetwork, Subnet, SecurityGroup, PublicIPPool, PublicIP,
PublicIPAttachment) are functional - `tenant-isolated` NetworkClass is
implemented and tested - Documentation for tenant and provider workflows

Graduation from Tech Preview to GA: - API stability (no breaking changes) -
Performance and scalability validated - Support procedures documented

## Upgrade / Downgrade Strategy

*Section to be completed when targeted at a release.*

Key considerations: - Existing Compute Instances created before this enhancement
must continue to work - New networking resources should be opt-in initially -
Downgrade should preserve existing network configurations

## Version Skew Strategy

*Section to be completed when targeted at a release.*

The Networking API is managed by the Fulfillment Service and O-SAC Operator.
Version skew considerations: - Fulfillment Service API changes must be backward
compatible - O-SAC Operator must handle CRs from both old and new API versions
during upgrades

## Support Procedures

*Section to be completed when targeted at a release.*

Failure detection: - VirtualNetwork stuck in "Pending" state indicates UDN
creation failure - SecurityGroup rules not applied indicates NetworkPolicy
reconciliation issues - Compute Instance unable to attach to network indicates
NAD or UDN misconfiguration

## Infrastructure Needed

No additional infrastructure is required for this enhancement. Implementation
will use existing OSAC components and OpenShift UDN capabilities.
