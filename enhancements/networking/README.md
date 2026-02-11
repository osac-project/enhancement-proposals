---
title: OSAC Networking API
authors:
  - agentil@redhat.com
creation-date: 2025-11-29
last-updated: 2026-02-11
tracking-link:
  - https://issues.redhat.com/browse/MGMT-22637
see-also:
  - Region and Availability Zone API: https://github.com/osac-project/enhancement-proposals/pull/20
replaces:
  - N/A
superseded-by:
  - N/A
---

# OSAC Networking API

## Summary

This enhancement introduces a Networking API for OSAC fulfillment services. The
API provides familiar cloud networking primitives (VirtualNetwork, Subnet,
SecurityGroup, PublicIPPool, PublicIP, NAT Gateway) as first-class resources. It
supports IPv4 and IPv6: VirtualNetworks and Subnets may use IPv4, IPv6, or
dual-stack CIDRs; PublicIPPools are either IPv4 or IPv6 (one address family per
pool). PublicIPPools are defined by the service provider; tenants manage
VirtualNetworks, Subnets, SecurityGroups, and PublicIPs (allocated from a pool).

The Networking API is pluggable through a NetworkClass architecture, and an
implementation designed for VMaaS is being proposed.

The Networking API is designed as a foundational service for OSAC, intended to
be consumed by multiple services. **Compute Instance (VMaaS) will be the first
service to integrate with this API**, with Cluster-as-a-Service and
BareMetal-as-a-Service planned for future integration.

## Terminology

This section defines the key networking terms used throughout this enhancement:

- **Region**: Region is the management boundary; networking resources such as
  VirtualNetworks, Subnets, PublicIPPools, and PublicIPs are scoped to a Region.

- **VirtualNetwork**: A tenant's isolated virtual network environment, similar
  to an AWS VPC or Azure VNet. VirtualNetwork is scoped to a Region. It provides
  logical isolation and defines the overall address space via optional `ipv4`
  and `ipv6` sections (each with a `cidr`). Single-stack = one section;
  dual-stack = both.

- **Subnet**: A subdivision of a VirtualNetwork's IP address space, scoped to a
  Region (the same Region as the VirtualNetwork). Subnets use optional `ipv4`
  and `ipv6` sections (each with a `cidr`), consistent with the VirtualNetwork.
  Resources are attached to Subnets to receive IP addresses and network
  connectivity.

- **SecurityGroup**: A stateful firewall that controls inbound and outbound
  traffic for resources. Rules specify allowed protocols, ports, and source/
  destination addresses (IPv4 or IPv6 CIDRs). SecurityGroups are applied to
  resources within a VirtualNetwork.

- **PublicIPPool**: A provider-defined pool of public IP addresses. Each pool is
  either IPv4 or IPv6 (not both), defined via `ipv4.cidrs` or `ipv6.cidrs`.
  Pools are scoped to a region. Tenants allocate PublicIPs from a PublicIPPool.

- **PublicIP** (also known as **Floating IP**): A public IP address (IPv4 or
  IPv6) allocated from a PublicIPPool. PublicIPs can be dynamically attached to
  and detached from resources. They persist independently of the resources
  they're attached to, allowing tenants to reassign them as needed.

- **PublicIPAttachment**: The binding between a PublicIP and a target resource.
  Creating an attachment routes traffic to the resource; deleting it removes the
  association without releasing the IP.

- **NAT Gateway**: A gateway that provides outbound NAT for resources in a
  VirtualNetwork. It is scoped to a VirtualNetwork and uses a PublicIP. Traffic
  from resources in that VirtualNetwork (or in Subnets that use the gateway)
  appears to originate from the gateway's public IP, giving tenants a single
  egress identity for outbound access (e.g., to the internet) without assigning
  a public IP to each resource.

- **NetworkClass**: A provider-defined resource that specifies how
  VirtualNetworks are implemented. Enables pluggable networking backends (e.g.,
  `udn-net` for basic UDN, `phys-net` for advanced topologies).

## Motivation

OSAC needs a unified networking layer aligned with major cloud providers (AWS,
Azure, GCP). A standalone API with first-class resources lets tenants define
topology before workloads, reference existing networks, manage SecurityGroups
centrally, and create isolated segments. The API is designed for extensibility
and reuse across OSAC services (Compute Instance first, then Cluster and
BareMetal).

### User Stories

#### Tenant Admin Stories

- As an end-user, I want to be able to create one or several VirtualNetworks
  that are isolated from each other
- As an end-user, I want to be able to define a Subnet in my VirtualNetwork
- As an end-user, I want to be able to define SecurityGroups to control traffic
  to resources in my VirtualNetwork
- As an end-user, I want to be able to attach resources to a Subnet in one of my
  VirtualNetworks
- As an end-user, I want to allocate a Public IP (IPv4 or IPv6) from a
  PublicIPPool in a region
- As an end-user, I want to attach and detach a Public IP to a resource
- As an end-user, I want to create a NAT Gateway in my VirtualNetwork so that
  outbound traffic from my resources uses a dedicated public IP

#### Provider Stories

- As a service provider, I want to be able to provide my own implementation of
  the Networking API through NetworkClasses
- As a service provider, I want to control which networking capabilities are
  available to tenants
- As a service provider, I want to define PublicIPPools per region so tenants
  can allocate PublicIPs from those pools

### Goals

- Introduce the Networking API as a foundational OSAC service with the resources
  defined in [Terminology](#terminology) as first-class API objects
- Support IPv4 and IPv6 (dual-stack where applicable) for VirtualNetworks,
  Subnets, PublicIPPools, PublicIPs, and SecurityGroup rules
- Keep the API generic and reusable across OSAC services (Compute Instance,
  Cluster, BareMetal)
- Support pluggable implementations via NetworkClass and deliver initial
  integration with Compute Instance (first: `udn-net` based on OpenShift UDN) as
  the first consumer

### Non-Goals

- Storage Networking
- Integration with Cluster-as-a-Service and BareMetal-as-a-Service (planned for
  future enhancements)
- APIs for Internet Gateways and Load Balancers
- Tenant-definable PublicIPPools or BYOIP (pools are provider-defined only)

## Proposal

This proposal relies on User Defined Networks (UDN), a networking feature
provided by OpenShift that enables the creation of isolated networks within an
OpenShift cluster. UDN leverages OVN-Kubernetes to provide network isolation.

VirtualNetworks and Subnets are scoped to a Region.

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

#### NetworkClass: `udn-net`

This enhancement defines a single NetworkClass called `udn-net`. This class
provides:

- **Isolated tenant networking**: Each Virtual Network is fully isolated from
  other tenants using OVN-Kubernetes
- **Single subnet per Virtual Network**: Due to UDN architecture constraints,
  each Virtual Network contains exactly one subnet
- **Layer 2 connectivity**: VMs within the same Virtual Network can communicate
  at Layer 2
- **NAT Gateway**: A NAT Gateway is implemented via OVN's **EgressIP** resource.
  The O-SAC Operator creates and reconciles an EgressIP (`k8s.ovn.org/v1`): the
  NAT Gateway's PublicIP is set as `egressIPs`, and the EgressIP's
  `namespaceSelector` targets the namespace(s) of the VirtualNetwork's
  Subnet(s). Egress traffic from those namespaces then appears to originate from
  the gateway's public IP.

The `udn-net` class is suitable for deployments where:

- Tenants need simple, isolated networks for their workloads
- No integration with external network infrastructure is required
- Each logical network segment can be represented as a separate Virtual Network

Future enhancements may introduce additional NetworkClasses (e.g., `phys-net`)
that leverage UDN Localnet mode to provide multi-subnet VirtualNetworks,
external connectivity, and tighter integration with physical network
infrastructure.

The Networking API is built on OpenShift's User Defined Networking (UDN).
Resource definitions are in [Terminology](#terminology); implementation notes
for the `udn-net` NetworkClass are in the subsections above.

The Networking API will be implemented through updates to the following O-SAC
components:

- **Fulfillment Service**: Expose the Networking API endpoints for
  VirtualNetwork, Subnet, SecurityGroup, PublicIPPool, PublicIP,
  PublicIPAttachment, and NAT Gateway resources
- **Fulfillment CLI**: Provide tenant access to Networking API operations
- **O-SAC Operator**: Manage and reconcile networking Custom Resources,
  translating them to OpenShift primitives (UDN, NetworkPolicies, ...)
- **O-SAC Ansible**: Execute provider's Ansible playbooks to perform custom
  operations to the networking infrastructure (e.g., allocating a Public IP from
  a pool and assigning it to a resource)

### Integration with OSAC Services

- **This enhancement:** ComputeInstance is extended with `network_attachments`
  (Subnets and SecurityGroups within the tenant's VirtualNetwork).
- **Planned:** HostPool will use the same pattern for bare-metal; Cluster will
  support cluster-level network configuration.

### Workflow Description

**Provider**: Cloud administrator managing network infrastructure and
NetworkClasses. **Tenant**: Organization or user consuming networking for
resources (VMs, bare metal, clusters).

#### VirtualNetwork Creation

1.  The tenant uses the Fulfillment CLI to create a VirtualNetwork by specifying
    a name, region, NetworkClass, and address space (ipv4.cidr and/or
    ipv6.cidr).
2.  The Fulfillment Service validates the request and creates a VirtualNetwork
    custom resource (CR) scoped to that Region.
3.  The O-SAC Operator detects the new VirtualNetwork CR and marks it as ready.
4.  Depending on the NetworkClass, additional provisioning operations may be
    performed (e.g., configuring external fabric integration, allocating network
    resources from infrastructure providers).
5.  The tenant uses the Fulfillment CLI to check the VirtualNetwork status.

#### Subnet Management

1.  The tenant uses the Fulfillment CLI to create a new Subnet within their
    VirtualNetwork, specifying the VirtualNetwork and address space (ipv4.cidr
    and/or ipv6.cidr).
2.  The Fulfillment Service validates that each Subnet CIDR is within the
    VirtualNetwork's CIDR of the same address family and creates a Subnet CR
    scoped to the VirtualNetwork's Region.
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
    admin API or cluster-scoped CR), specifying the region and one or more CIDR
    ranges for each pool.
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

#### NAT Gateway

1.  The tenant creates a NAT Gateway within a VirtualNetwork, specifying a
    PublicIP (allocated from a PublicIPPool) to use for outbound NAT.
2.  The Fulfillment Service validates that the PublicIP exists and is not
    attached to another resource (or is reserved for NAT), and creates a NAT
    Gateway CR owned by the VirtualNetwork.
3.  The O-SAC Operator reconciles the NAT Gateway so that egress traffic from
    the VirtualNetwork's Subnets uses the gateway's public IP (for the `udn-net`
    NetworkClass, see that class for implementation details).
4.  Resources (e.g., ComputeInstances) in Subnets of that VirtualNetwork
    automatically have their egress traffic source-NAT'd to the NAT Gateway's
    public IP, or the tenant explicitly associates the NAT Gateway with specific
    Subnets/resources as defined by the API.

### API Extensions

#### VirtualNetwork

A tenant requests a VirtualNetwork to create an isolated network environment
with its own address space. Address space is specified via optional `ipv4` and
`ipv6` sections, each with a `cidr` field. **Single-stack** = one section (ipv4
or ipv6). **Dual-stack** = both sections.

Example CLI commands:

Single-stack (IPv4):

    $ ./fulfillment-cli create virtualnetwork \
           --region us-east-1 \
           --ipv4-cidr 10.0.0.0/16 \
           --network-class udn-net \
           --name my-network

Dual-stack:

    $ ./fulfillment-cli create virtualnetwork \
           --region us-east-1 \
           --ipv4-cidr 10.0.0.0/16 --ipv6-cidr 2001:dead:beef::/48 \
           --network-class udn-net \
           --name my-network

The Fulfillment CLI sends this JSON request to the Fulfillment Service
(dual-stack example):

``` json
{
  "object": {
    "id": "my-network",
    "spec": {
      "region": "us-east-1",
      "ipv4": { "cidr": "10.0.0.0/16" },
      "ipv6": { "cidr": "2001:dead:beef::/48" },
      "networkClass": "udn-net"
    }
  }
}
```

The Fulfillment Service creates the following VirtualNetwork CR (dual-stack
example):

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: VirtualNetwork
metadata:
  name: my-network
  labels:
    tenantUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
spec:
  region: us-east-1
  ipv4:
    cidr: 10.0.0.0/16
  ipv6:
    cidr: 2001:dead:beef::/48
  networkClass: udn-net
status:
  state: Ready
  conditions:
  - type: Ready
    status: "True"
    lastTransitionTime: "2025-01-07T10:00:00Z"
```

#### Subnet

Subnets define IP address ranges within a VirtualNetwork and are scoped to a
Region (the same Region as the VirtualNetwork). Address space is specified via
optional `ipv4` and `ipv6` sections, each with a `cidr` field. **Single-stack**
= one section. **Dual-stack** = both sections. Each Subnet maps to a dedicated
namespace containing an OpenShift UserDefinedNetwork.

Example CLI commands:

Single-stack (IPv4):

    $ ./fulfillment-cli create subnet \
           --virtual-network my-network \
           --ipv4-cidr 10.0.1.0/24 \
           --name frontend-subnet

Dual-stack:

    $ ./fulfillment-cli create subnet \
           --virtual-network my-network \
           --ipv4-cidr 10.0.1.0/24 --ipv6-cidr 2001:dead:beef::/48 \
           --name frontend-subnet

The Fulfillment Service creates the following Subnet CR (dual-stack example):

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
  ipv4:
    cidr: 10.0.1.0/24
  ipv6:
    cidr: 2001:dead:beef::/48
status:
  state: Ready
  namespace: tenant-66b8ed6f-subnet-frontend-subnet
  udnName: frontend-subnet-udn
```

The O-SAC Operator creates a namespace for the Subnet and the corresponding
UserDefinedNetwork (dual-stack: one subnet entry per CIDR):

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
    - cidr: 2001:dead:beef::/48
      hostSubnet: 48
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

PublicIPPools are provider-defined pools of public IP addresses, scoped to a
region. Each pool is either IPv4 or IPv6 (not both), specified via `ipv4.cidrs`
or `ipv6.cidrs` (one or the other). Addresses are allocated from those ranges.
Tenants allocate PublicIPs from a pool; they cannot create or delete pools.

Example provider workflow (e.g., via Fulfillment Service admin API or
cluster-scoped CR):

A provider defines a PublicIPPool (either IPv4 or IPv6; one family per pool):

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: PublicIPPool
metadata:
  name: public-us-east-1
spec:
  region: us-east-1
  ipv4:
    cidrs:
    - 203.0.113.0/24
    - 198.51.100.0/24
  # Or ipv6.cidrs for an IPv6-only pool, e.g.:
  # ipv6:
  #   cidrs:
  #   - 2001:db8::/32
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

#### NAT Gateway

A NAT Gateway provides outbound NAT for resources in a VirtualNetwork. It is
scoped to a VirtualNetwork and uses a PublicIP; traffic from resources in that
VirtualNetwork (or in selected Subnets) appears to originate from the gateway's
public IP.

Example CLI command:

    $ ./fulfillment-cli create natgateway \
           --virtual-network my-network \
           --publicip my-public-ip \
           --name my-nat-gateway

The Fulfillment Service creates the following NAT Gateway CR:

``` yaml
apiVersion: o-sac.openshift.io/v1alpha1
kind: NATGateway
metadata:
  name: my-nat-gateway
  ownerReferences:
  - apiVersion: o-sac.openshift.io/v1alpha1
    kind: VirtualNetwork
    name: my-network
    uid: 77c9fe7g-2bg3-5903-bd23-58ce58ebde51
spec:
  virtualNetwork: my-network
  publicIP: my-public-ip
status:
  state: Ready
  address: 203.0.113.45   # from the referenced PublicIP
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

- **NetworkClass**: Cluster-scoped, provider-managed; the O-SAC Operator uses it
  to select the provisioner when reconciling VirtualNetworks.
- **IPv4 and IPv6**: VirtualNetworks and Subnets use optional `ipv4` and `ipv6`
  sections, each with a `cidr` field; single-stack = one section, dual-stack =
  both. PublicIPPools are either IPv4 or IPv6 (one family per pool), with
  `ipv4.cidrs` or `ipv6.cidrs` (list). Allocation returns an address from the
  pool's family. SecurityGroup rules use CIDR notation (e.g. `0.0.0.0/0`,
  `::/0`). Implementation support for IPv6 depends on the NetworkClass and
  underlying platform (e.g. OVN-Kubernetes / UDN).
- **Namespace per Subnet** (`udn-net`): Each Subnet has its own namespace and
  UserDefinedNetwork; VirtualNetwork is a logical grouping. UDN and namespace
  are created with the Subnet and removed with it; VirtualNetwork can be deleted
  only after all Subnets are removed.
- **Subnet and Region**: Subnets are scoped to the same Region as their
  VirtualNetwork.

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

**Single Subnet per Virtual Network**: As described in NetworkClass `udn-net`,
UDN constraints limit each VirtualNetwork to one Subnet. Users needing multiple
segments must create multiple VirtualNetworks. This limitation will be lifted in
OpenShift 4.22, and the Cluster Network Connect feature that will allow the
interconnection of multiple UDNs.

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

2.  Should PublicIPPool or PublicIP be part of a NetworkClass? Today
    PublicIPPool is a standalone provider resource; future NetworkClasses might
    define how public IPs are implemented (e.g., NAT vs. direct allocation).

3.  IPv6: Should the API require dual-stack by default (when the provider
    supports it), or should IPv6 be opt-in per VirtualNetwork/Subnet/Pool? How
    should NAT Gateway behave for IPv6 (e.g. NAT66 vs. prefix delegation)?

## Test Plan

*Section to be completed when targeted at a release.*

- Unit: API validation and controller logic
- Integration: lifecycle of all networking resources (VirtualNetwork through NAT
  Gateway)
- E2E: network attachment workflows
- Multi-tenant: isolation and network separation

## Graduation Criteria

*Section to be completed when targeted at a release.*

- **Dev Preview → Tech Preview:** All core networking resources and `udn-net`
  NetworkClass functional and tested; tenant and provider documentation
  complete.
- **Tech Preview → GA:** API stable (no breaking changes); performance and
  scalability validated; support procedures documented.

## Upgrade / Downgrade Strategy

*Section to be completed when targeted at a release.*

- Existing Compute Instances must continue to work; new networking resources are
  opt-in initially; downgrade preserves existing network configuration.

## Version Skew Strategy

*Section to be completed when targeted at a release.*

Fulfillment Service API changes must remain backward compatible; O-SAC Operator
must handle CRs from both old and new API versions during upgrades.

## Support Procedures

*Section to be completed when targeted at a release.*

- VirtualNetwork stuck in "Pending" → UDN creation failure
- SecurityGroup rules not applied → NetworkPolicy reconciliation issues
- Compute Instance unable to attach → NAD or UDN misconfiguration

## Infrastructure Needed

No additional infrastructure is required for this enhancement. Implementation
will use existing OSAC components and OpenShift UDN capabilities.
