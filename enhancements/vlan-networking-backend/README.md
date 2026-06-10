---
title: vlan-based-multi-tenant-network-backend
authors:
  - dmanor@redhat.com
creation-date: 2026-05-31
last-updated: 2026-05-31
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-957
see-also:
  - "/enhancements/networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# VLAN-Based Multi-Tenant Network Backend

## Summary

This enhancement introduces two new Ansible collections (`ansible_networking.l2`
and `ansible_networking.l3`) that provide multi-tenant network isolation for
bare-metal infrastructure using VLAN-based L2 switching and software-defined L3
routing. The L2 layer uses
[networking-ansible](https://github.com/CCI-MOC/networking-ansible) /
[network-runner](https://github.com/ansible-network/network-runner) to configure
physical switches directly via SSH. The L3 layer uses Linux network namespaces
with iptables on a dedicated network node to provide per-tenant routing, SNAT,
and DNAT. No external network controller is required.

## Motivation

OSAC currently supports two network backends: Netris (a proprietary network
controller) and ESI/OpenStack. Both require deploying and maintaining an external
system alongside OSAC. Customers who don't run either need an alternative that
works with their existing switches without additional infrastructure.

The networking-ansible project (used by OpenStack Neutron's ML2 plugin at the
Massachusetts Open Cloud) provides a proven approach to automating physical
switch configuration via Ansible. However, L2 switch automation alone only
provides isolation -- a routing layer is needed for NAT and external
connectivity. This enhancement combines both layers into a self-contained
backend.

### User Stories

- As a Cloud Infrastructure Admin, I want OSAC to configure my switches directly
  via SSH/Ansible so that I don't need to deploy a separate network controller
  like Netris or OpenStack.
- As a Cloud Infrastructure Admin, I want per-tenant VLAN isolation so that
  tenants' bare-metal servers are isolated at the switch hardware level, with no
  software bypass possible.
- As a Cloud Infrastructure Admin, I want per-tenant routing with SNAT so that
  each tenant's servers can reach the internet through a dedicated NAT IP.
- As a Cloud Infrastructure Admin, I want DNAT port-forwarding so that I can
  expose tenant services (e.g., API endpoints) to external clients via public
  IPs.
- As a Cloud Provider Admin, I want to define my switch inventory (hostnames,
  credentials, vendor OS) in configuration so that the backend works with my
  existing network equipment.
- As a Cloud Provider Admin, I want to onboard new sites by providing switch
  credentials and a network node, without deploying any additional control plane
  components.
- As a Tenant User, I want to provision resources through the same self-service
  interface regardless of the network backend, so my workflow is unaffected by
  infrastructure-level choices.

### Goals

- Provide L2 switch automation (VLAN management and port configuration) via
  networking-ansible/network-runner, supporting any vendor that network-runner
  supports (Juniper Junos, Cisco NX-OS, Arista EOS, Cumulus, Dell OS10)
- Provide L3 routing, SNAT, and DNAT via Linux network namespaces and iptables
  on a dedicated network node, with no persistent agent required
- Provide simple IP pool management for public IPs and VLAN IDs, tracked in a
  state file on the network node
- Keep the collections generic and reusable -- they are building blocks that any
  orchestration layer can compose

### Non-Goals

- Replacing Netris or ESI as default network backends
- Supporting overlay networking (VXLAN/Geneve) -- this backend uses VLAN-based
  isolation only
- Supporting every switch vendor from day one -- initial scope is one vendor as
  proof of concept
- High availability for the network node (keepalived/VRRP is a future
  enhancement)
- Multi-site support (one site for initial implementation)
- Defining how servers get their IPs (DHCP, static NMState, etc.) -- this is
  decided by the consumer, not by this backend
- Changes to the OSAC operator, fulfillment-service, or tenant-facing APIs

## Proposal

The proposal introduces two Ansible collections:

**`ansible_networking.l2`** manages physical switches via networking-ansible /
network-runner. It communicates with switches over SSH using vendor-specific
Ansible modules (e.g., `junos_command`, `nxos_config`, `eos_config`).

**`ansible_networking.l3`** manages per-tenant routing on a dedicated Linux
server (the "network node") via SSH. Each tenant gets an isolated Linux network
namespace with its own interfaces, routing table, and iptables rules.

These collections are generic building blocks. An orchestration layer (such as
OSAC's `network_steps_collection`) composes them for specific workflows like
cluster provisioning or VM networking.

### Workflow Description

**cloud infrastructure admin** is a human user responsible for deploying and
configuring the network infrastructure.

**orchestration layer** is the automation system (e.g., OSAC AAP playbooks) that
calls these roles to provision tenant networks.

#### Initial Setup

1. The cloud infrastructure admin connects servers to leaf switches and
   configures inter-switch links as TRUNK ports carrying all VLANs.
2. The admin connects a network node to the switches via a TRUNK port and to the
   upstream/provider network.
3. The admin defines the switch inventory (hostnames, credentials, vendor OS),
   network node details, VLAN range, and public IP pool in Ansible
   configuration.

#### Tenant Network Creation

1. The orchestration layer calls `ansible_networking.l2.vlan` to create a VLAN on
   all managed switches. A VLAN ID is allocated from the configured range and
   tracked in the state file.
2. For each server assigned to the tenant, the orchestration layer calls
   `ansible_networking.l2.port` to configure the server's switch port as an
   ACCESS port on the tenant's VLAN. The server sends/receives untagged frames;
   the switch tags them with the tenant's VLAN.
3. The orchestration layer calls `ansible_networking.l3.router` to create a Linux
   network namespace on the network node with an internal interface on the
   tenant's VLAN and an external interface on the provider network.
4. The orchestration layer calls `ansible_networking.l3.ipam` to allocate a
   public IP, then calls `ansible_networking.l3.snat` to add an SNAT rule in the
   router namespace for outbound internet access.

#### External Access Setup

1. The orchestration layer calls `ansible_networking.l3.ipam` to allocate public
   IPs for API and ingress access.
2. The orchestration layer calls `ansible_networking.l3.dnat` to add DNAT rules
   in the router namespace, forwarding specific ports from the public IP to
   internal service IPs.
3. The orchestration layer creates DNS A records pointing to the public IPs.

#### Tenant Network Deletion

1. Remove DNAT rules and release associated public IPs.
2. Remove the SNAT rule and release the SNAT IP.
3. Delete the router namespace (all iptables rules inside are automatically
   cleaned up).
4. Reset each server's switch port to default configuration.
5. Delete the VLAN from all managed switches.
6. Remove allocations from the state file.

### API Extensions

This enhancement does not introduce or modify any Kubernetes CRDs, webhooks, or
API resources. The collections are pure Ansible roles that manage external
infrastructure (switches and a Linux network node).

### Implementation Details/Notes/Constraints

#### `ansible_networking.l2` Collection

| Role | Purpose |
|------|---------|
| `vlan` | Create/delete a VLAN on all managed switches |
| `port` | Configure a switch port as ACCESS (single VLAN) or reset it |

**`vlan` role:**

- `create`: Takes a VLAN ID. Calls network-runner `create_vlan()` on every
  switch in the inventory. Idempotent -- skips if VLAN already exists.
- `delete`: Takes a VLAN ID. Calls network-runner `delete_vlan()` on every
  switch. Checks no active ports use the VLAN before deleting.

**`port` role:**

- `set_access_port`: Takes a switch name, port name, and VLAN ID. Calls
  network-runner `conf_access_port()` to configure the port in access mode on
  the specified VLAN.
- `reset_port`: Takes a switch name and port name. Calls network-runner
  `delete_port()` to remove all VLAN configuration from the port.

#### `ansible_networking.l3` Collection

| Role | Purpose |
|------|---------|
| `router` | Create/delete a per-tenant router (Linux namespace with interfaces, IP forwarding) |
| `snat` | Add/remove an SNAT rule in a router namespace |
| `dnat` | Add/remove a DNAT port-forwarding rule in a router namespace |
| `ipam` | Allocate/release public IPs from a configured pool |

**`router` role:**

- `create`: Takes a router name, internal VLAN ID, internal subnet CIDR, and
  external network details. Creates a Linux namespace, a VLAN sub-interface on
  the network node's trunk NIC for the internal leg, an interface on the
  external/provider network, and enables IP forwarding inside the namespace.
- `delete`: Removes the namespace and all associated interfaces. All iptables
  rules inside the namespace are automatically cleaned up.

**`snat` role:**

- `create`: Takes a router name, source subnet, and SNAT IP. Adds an iptables
  SNAT rule in the router's namespace for outbound traffic.
- `delete`: Removes the corresponding iptables rule.

**`dnat` role:**

- `create`: Takes a router name, public IP, public port, internal IP, and
  internal port. Adds an iptables DNAT rule in the router's namespace.
- `delete`: Removes the corresponding iptables rule.

**`ipam` role:**

- `allocate`: Takes a purpose label and count. Reads the state file, picks the
  next available IP(s) from the configured pool, writes the allocation, and
  returns the allocated IP(s).
- `release`: Takes a purpose label. Removes the allocation from the state file.

#### Configuration

Switch inventory:

```yaml
switches:
  leaf-1:
    ansible_network_os: junos
    ansible_host: 10.10.2.250
    ansible_user: ansible
    ansible_pass: "{{ vault_switch_password }}"
  leaf-2:
    ansible_network_os: junos
    ansible_host: 10.10.2.251
    ansible_user: ansible
    ansible_pass: "{{ vault_switch_password }}"
```

Network node:

```yaml
network_node:
  ansible_host: 10.10.2.200
  ansible_user: root
  trunk_interface: eth1
  external_interface: eth0
  external_gateway: 10.0.0.1
```

Resource pools:

```yaml
vlan_range: 1000-1099
public_ip_pool: 203.0.113.10-203.0.113.50
```

#### State Tracking

A JSON file on the network node (default: `/etc/osac/network_state.json`)
tracks VLAN and public IP allocations:

```json
{
  "vlans": {
    "tenant-alpha": 1042,
    "tenant-beta": 1043
  },
  "public_ips": {
    "tenant-alpha-snat": "203.0.113.10",
    "tenant-alpha-api-dnat": "203.0.113.11"
  }
}
```

All operations are idempotent. Re-running create with the same name reuses
existing allocations.

#### Physical Topology

- One or more leaf switches with servers connected via ACCESS ports
- Inter-switch links configured as TRUNK (all VLANs)
- One network node connected to the switches via a TRUNK port (carries all
  tenant VLANs) and to the upstream/provider network
- One site (multi-site is out of scope)

#### Network Isolation Model

- Each tenant gets a unique VLAN ID. Servers on different VLANs cannot
  communicate at L2 -- enforced by switch ASIC hardware.
- Each tenant gets its own Linux namespace on the network node with its own
  routing table and iptables rules, isolated from other tenants' namespaces.
- ACCESS ports on servers strip/ignore incoming VLAN tags, preventing tenants
  from injecting frames into other VLANs.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Network node reboot loses namespaces and iptables rules | Tenant networking broken until re-applied | Persist configuration via systemd-networkd and nftables persistence; provide a reconcile playbook |
| State file corruption or loss | VLAN/IP allocation state lost | Back up the state file; derive state from actual switch/namespace config as fallback |
| Switch SSH connectivity failure | VLAN/port changes cannot be applied | Retry logic in network-runner; alerting on SSH failures |
| VLAN range exhaustion | No more tenant networks can be created | Monitor VLAN utilization; plan range size based on expected tenant count |
| Concurrent Ansible runs modify state file simultaneously | Race condition on allocations | Use file locking (flock) in the IPAM role; or serialize operations via AAP job queue |

### Drawbacks

- **Agentless model**: Unlike Neutron's L3 agent, there is no persistent daemon
  to detect and repair drift. If the network node reboots or configuration is
  manually changed, the system does not self-heal. This is acceptable for
  initial deployment where network node reboots are rare and planned, but may
  need to be addressed for production-grade deployments.
- **VLAN scale**: Limited to ~4094 VLANs (802.1Q). The configured range may be
  smaller. For deployments needing more tenant networks, overlay technologies
  (VXLAN/Geneve) would be needed, which this backend does not support.
- **Single network node**: No HA means the network node is a single point of
  failure for all tenant routing and NAT.

## Alternatives (Not Implemented)

### Alternative 1: Deploy OpenStack Neutron for L3

Use the full Neutron L3 agent for routing, DHCP, and NAT, paired with the
networking-ansible ML2 plugin for L2.

**Why not selected**: Requires deploying Keystone, a database, a message queue,
and the Neutron server -- essentially a chunk of OpenStack. This contradicts the
goal of providing a backend with no external controller dependencies.

### Alternative 2: Configure physical routers directly via Ansible

Instead of Linux namespaces on a network node, configure NAT rules directly on
the upstream physical router (e.g., Juniper, Cisco) using Ansible modules.

**Why not selected**: Tightly couples to the router vendor. Router configuration
is more fragile than Linux iptables. Not all environments have a programmable
router. Can be revisited as a future enhancement.

### Alternative 3: Lightweight agent on the network node

Deploy a small daemon on the network node that reads a desired-state file and
re-applies namespaces/iptables on boot or drift detection, without the full
Neutron stack.

**Why not selected**: Adds operational complexity (another service to deploy and
monitor). The agentless approach with configuration persistence is simpler for
initial deployment. This can be added later if drift becomes a real problem.

## Open Questions

1. Should the state file be replaced with a more robust store (e.g., a ConfigMap
   on the hub cluster, etcd, or a small SQLite database) to avoid file-level
   race conditions and improve durability?

2. Should the L3 roles support nftables in addition to (or instead of) iptables,
   given that nftables is the default on newer Linux distributions?

3. How should the backend handle the network node's trunk port VLAN membership?
   Should the L2 roles automatically add new VLANs to the trunk, or is that
   pre-configured by the admin?

## Test Plan

- **Unit tests**: Ansible role argument validation, IPAM allocation logic, state
  file read/write idempotency.
- **Integration tests**: End-to-end with virtual switches (e.g., Open vSwitch in
  a test environment) and network namespaces on a test Linux host. Verify VLAN
  creation, port configuration, namespace creation, SNAT/DNAT rule application.
- **Isolation tests**: Verify that servers on different VLANs cannot communicate
  at L2. Verify that tenants' router namespaces are isolated from each other.
- **Idempotency tests**: Run create twice with the same parameters; verify no
  errors and no duplicate resources.
- **Vendor testing**: At least one real switch vendor (e.g., Juniper Junos via
  network-runner).

## Graduation Criteria

- **Dev Preview**: L2 and L3 collections functional against at least one switch
  vendor in a lab environment; basic isolation verified.
- **Tech Preview**: Tested in a real deployment with multiple tenants;
  documentation complete; reconcile playbook available.
- **GA**: Production use validated; persistence and recovery procedures
  documented; performance benchmarks for VLAN/NAT operations at expected scale.

## Upgrade / Downgrade Strategy

The collections are stateless Ansible roles -- there is no running component to
upgrade. Version changes are applied by updating the collection version. The
state file format should be versioned to support future schema changes.

Backward compatibility: new versions of the roles must be able to operate on
state files and infrastructure created by previous versions.

## Version Skew Strategy

Not applicable. The L2 and L3 collections are standalone Ansible roles with no
inter-component versioning requirements. The consumer (orchestration layer) is
responsible for using compatible versions of both collections.

## Support Procedures

- **Tenant network unreachable**: Check that the router namespace exists on the
  network node (`ip netns list`), verify iptables rules inside the namespace,
  verify the VLAN exists on the switches, verify the server's switch port is
  configured as ACCESS on the correct VLAN.
- **SNAT not working**: Verify the SNAT rule in the namespace
  (`ip netns exec <name> iptables -t nat -L`), verify the external interface has
  connectivity to the upstream gateway.
- **DNAT not working**: Verify the DNAT rule in the namespace, verify the
  internal service IP is reachable from inside the namespace.
- **State file out of sync**: Compare the state file with actual switch config
  and namespace config; update the state file manually or run the reconcile
  playbook.

## Infrastructure Needed

- A new Git repository for the `ansible_networking.l2` and
  `ansible_networking.l3` Ansible collections (or a single repository with both
  collections).
- A test environment with at least one managed switch (or OVS for integration
  testing) and a Linux host for the network node.
