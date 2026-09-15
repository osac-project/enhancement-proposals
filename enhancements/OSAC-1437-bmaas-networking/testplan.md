# Testplan — OSAC-1437 BMaaS Networking

## Overview

- **Feature:** OSAC-1437 — BMaaS Networking: Single NIC, Provisioning Handoff,
  DHCP Discovery, and Auto External Access
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Scope:** One tenant-facing physical attachment, BareMetalInstanceType
  interface validation, provisioning-network isolation, port move/reboot,
  DHCP lease discovery, CaaS private handoff, ExternalIP, and cleanup.
- **Prerequisite ownership:** The deployment-owned provisioning network,
  DHCP/gateway/SNAT, initial attach, BMC, inventory, and interface-MAC
  annotation exist before BMaaS begins. BMaaS does not create them.

## Execution strategy

- **Unit:** fulfillment-service validation, interface selection, operator phase
  ordering, move/DHCP request construction, status parsing, and cleanup.
- **Integration:** real PostgreSQL, BM CRD/controllers, fake Ironic/Metal3,
  dispatcher/AAP, fabric DHCP/IPAM, BMC, and feedback RPCs.
- **E2E:** real connected BMaaS with a provisioning network, fabric switch,
  inventory host, DHCP lease, reboot, tenant connectivity, ExternalIP, and
  cleanup.

## Test cases

### R1: One attachment and field-level defaulting

#### TC-R1-01: Omitted, empty, partial, and complete input

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Matrix

| Input | Expected result |
|---|---|
| List omitted/empty | One default Subnet, effective NetworkACL from that Subnet, first fabric interface |
| Only Subnet | Preserve Subnet; fill only interface; inherit the effective NetworkACL |
| Only interface | Preserve interface; fill only Subnet; inherit the effective NetworkACL |
| Complete entry | Preserve every supplied field |
| Invalid explicit value | Reject; never replace with default |

##### Expected results

- Persisted BM resource contains exactly one attachment after resolution.
- The Subnet and its effective NetworkACL are Ready, in the same scope and
  VirtualNetwork, and IPv4.
- Omitted/true primary is accepted; sole entry is implicitly primary.

#### TC-R1-02: Any multi-entry list and any explicit false-primary input are rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Expected results

- More than one `network_attachments` entry is rejected before interface
  discovery, persistence, capacity reservation, or dispatch.
- Explicit `primary: false` is rejected.
- Unknown nested attachment fields, a NetworkACL supplied inside the
  attachment, malformed typed Subnet references, and malformed `primary`
  presence/encoding are rejected before
  interface discovery or persistence.
- Direct API, Catalog, private CaaS, CRD, and controller paths agree.

### R2: BareMetalInstanceType and physical interface

#### TC-R2-01: First ordered fabric port is selected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Preconditions

- Ready BareMetalInstanceType contains multiple ordered ports, including
  fabric and lifecycle ports.

##### Expected results

- Omitted interface selects the first ordered `fabric` port.
- Supplied interface matches canonical port name and is preserved.
- Port list position, display label, tenant MAC, and arbitrary interface text
  are not alternate selectors.
- A later instance-type edit/reorder does not move an existing BM.

#### TC-R2-02: Ineligible interface requests fail closed

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- missing/Pending/Failed instance type;
- no fabric port;
- unknown interface;
- lifecycle, management, storage, or unknown-role port;
- inventory host lacks the selected port;
- selected port has no known MAC;
- catalog port name, fabric-manager logical interface name, and
  `osac.openshift.io/interface-macs` annotation key do not match.

##### Expected results

- Tenant-visible invalid input is rejected before persistence.
- Infrastructure allocation failure remains Pending/Failed and never becomes
  Ready with a different port.
- No lifecycle or unrelated port is moved.
- A naming mismatch fails closed before port movement or DHCP lease lookup; the
  system never targets a different NIC based on list position, display label,
  or an inconsistent annotation key.

#### TC-R2-03: Deployment capability admission is enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- K8s-only NetworkClass with no Fabric Manager;
- disabled Fabric Manager;
- Fabric Manager missing `move_network_attachment`;
- Fabric Manager missing `query_dhcp_lease`;
- capability becomes unavailable between NetworkClass creation and private
  CaaS worker dispatch.

##### Expected results

- Standalone, Catalog-based, and private CaaS BM creates fail with
  `FailedPrecondition` before BM, automatic ExternalIP, attachment, or CR
  persistence when the required capability set is unavailable.
- BMaaS does not create a long-lived Pending instance waiting for an
  unsupported capability.
- The capability check is repeated before private CaaS worker dispatch.

### R3: Provisioning network and handoff

#### TC-R3-01: Provisioning flow is isolated and ordered

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Allocate an unassigned host on the deployment provisioning network.
2. Complete inventory and OS provisioning.
3. Inspect the private BaremetalInstance CR and verify that public
   `spec.network_attachments` was copied to the CRD's
   `spec.networkAttachments` resource-specific message, with no dropped
   attachment or legacy shared message.
4. Move only the selected fabric port to the tenant Subnet.
5. Reboot as required for fresh tenant DHCP.
6. Discover the tenant IP.

##### Expected results

- Phase order is inventory → provisioning → networking → reboot → IP
  discovery → Ready.
- Reboot and IP discovery do not begin until the target tenant network segment
  reports active/ready after the selected port move.
- Tenant cannot reach the host before the port move and readiness.
- Port move uses provisioning-network → tenant-network direction and selected
  logical interface only.
- The CRD contains the same resolved typed Subnet, interface, and primary
  value that passed API validation. The worker uses the effective NetworkACL
  inherited from the Subnet; no ACL reference is copied into the attachment.
- Host does not retain the provisioning network after handoff.
- Deployment-owned provisioning network is consumed, not created, by BMaaS.

#### TC-R3-02: Provisioning, networking, and AAP failures recover safely

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E recovery | high | automated |

##### Cases

- inventory allocation failure;
- switch port-move failure;
- AAP/template execution failure;
- controller restart during provisioning or networking reconciliation.

##### Expected results

- The BaremetalInstance remains Pending or enters Failed with the documented
  condition and job reference; it is never Ready before the tenant handoff
  and IP discovery complete.
- Retry after recovery is idempotent and does not move a second or unrelated
  port, create a second BM, or expose the provisioning-network IP.
- Controller restart resumes the existing phase without duplicating the
  network move or provisioning job.

#### TC-R3-03: Deletion reverses the handoff safely

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Expected results

- Host powers off while still on tenant network.
- Selected port moves tenant network → provisioning network.
- Host is not running tenant workload on provisioning network.
- Ironic/Metal3 cleanup runs after the network move.
- Subsequent inspection can use the provisioning network.

### R4: DHCP lease discovery and status

#### TC-R4-01: Correct lease becomes the sole status entry

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- lease matches selected port MAC;
- documented named-server fallback;
- lease delayed;
- wrong MAC/server;
- wrong Subnet;
- IPv6/malformed address;
- duplicate or multiple leases.

##### Expected results

- Only canonical IPv4 in the resolved Subnet is published.
- Status contains at most one interface/IP entry.
- The status entry contains the resolved interface, typed Subnet reference,
  canonical IPv4 address, and implicit `primary=true`.
- Missing/wrong lease requeues and keeps BM non-Ready.
- Status feedback updates fulfillment-service without changing spec.

### R5: Automatic ExternalIP

#### TC-R5-01: Auto ExternalIP waits for BM IP

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Create an otherwise valid BM with `auto_external_ip_attachment=true`.
2. Inspect the atomically created ExternalIP and Pending
   ExternalIPAttachment, including their cleanup labels.
3. Complete ExternalIP allocation while withholding BM IP discovery, then
   discover the selected interface IP and verify DNAT activation.

##### Expected results

- Ready IPv4 pool and capacity are required.
- Parent, ExternalIP, and Pending ExternalIPAttachment are atomic.
- Auto-created ExternalIP and ExternalIPAttachment carry the canonical
  auto-created labels, including `auto-created-for` on the ExternalIP.
- Attachment target is BM with `UNSPECIFIED` endpoint.
- DNAT waits for both ExternalIP Allocated and discovered BM IP.
- DNAT uses the selected interface's discovered IP only.
- VM/CaaS endpoint semantics are not accepted on the BM path.

#### TC-R5-02: Allocation and cleanup failure are safe

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E rejection/recovery | critical | automated |

##### Expected results

- Pool exhaustion leaves no BM, child, job, or capacity reservation.
- Auto attachment is deleted before ExternalIP and before parent finalizer
  removal.
- Manual ExternalIP resources remain tenant-managed.
- Transient finalizer/fabric failure retries without duplicate moves or IPs;
  permanent failure follows documented manual cleanup.

#### TC-R5-03: Asynchronous ExternalIP and DNAT failures preserve BM state

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E recovery | critical | automated |

##### Cases

- ExternalIP allocation enters `Failed` after the BM and Pending children are
  persisted;
- ExternalIPAttachment/DNAT dispatch fails after the BM reaches its tenant
  network;
- delayed or missing IP discovery while the ExternalIP is already Allocated.

##### Expected results

- ExternalIP failure leaves the BM Pending/functional without inbound
  external access; the BM is not falsely reported as externally reachable.
- Attachment failure does not activate DNAT, while the BM remains on its
  validated tenant network.
- Missing BM IP keeps the attachment Pending and requeues; no DNAT is created
  with the provisioning-network IP or an arbitrary address.

### R6: CaaS private handoff and Catalog parity

#### TC-R6-01: Private CaaS workers use normal BMaaS validation

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Expected results

- Private request contains exactly one attachment with Cluster Subnet and
  immutable node-set fabric interface; the effective NetworkACL is inherited
  from the Subnet.
- BMaaS revalidates port role, type, readiness, and the Subnet's effective
  NetworkACL. For the trusted private CaaS path, network references are resolved in the source Cluster's
  tenant/project and are not rejected merely because the destination BMI is
  owned by the `system` tenant.
- Private caller cannot inject a second attachment or lifecycle port.

#### TC-R6-02: Catalog and direct BM creates are equivalent

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Expected results

- Locked/editable policy and tenant/default precedence match direct creation.
- Shared Catalog Items cannot lock/default tenant-local references.
- Catalog metadata and existing BM network specs remain unchanged after policy
  updates.

### R7: Immutability and unsupported BM networking

#### TC-R7-01: Network-owned fields are immutable

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- attachment list, Subnet, interface, primary;
- an attempt to supply a NetworkACL inside the attachment;
- auto-external switch;
- status attempt to mutate spec;
- update, patch, replace, and nested field mask;
- in-place Ready-resource re-provision handoff reset.

##### Expected results

- All unsupported changes are rejected; delete/recreate is required.
- Controller may update status, conditions, IP, and finalizers only.

#### TC-R7-02: Unsupported host-network behavior is rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- multi-NIC or second tenant attachment;
- tenant-selected MAC, DHCP address, static host config, alternate IPAM, or
  lifecycle/provisioning interface;
- moving all host ports;
- BMaaS VM/KubeVirt networking operations;
- operator creation of the deployment provisioning network.

##### Expected results

- Unsupported behavior is rejected or remains deployment-owned/out of scope.
- No tenant access or backend mutation occurs.

### R8: BM CLI contract

#### TC-R8-01: CLI mapping, interface, and defaulting

**Unit:** Verify one optional `--network-attachment` maps to repeated
`spec.network_attachments` containing `BareMetalNetworkAttachment`. Verify
the compound `interface=<port-name>` key, rejection of a NetworkACL key,
omitted interface selection, invalid/lifecycle interfaces, repeated
attachments, the deprecated plural `--network-attachments` option, and
explicit `primary=false` behavior.

**Integration:** Verify CLI requests use typed local references and the same
readiness, same-VirtualNetwork, capability, and rollback rules as direct API
requests. Verify `--external-ip-attachment` mapping in both states: present
sets true and starts automatic external access; omitted sets false, creates no
automatic ExternalIP/attachment, and consumes no pool capacity. Verify the
switch is immutable and there is no separate `--interface` syntax.

**E2E:** Create a BM with an explicit interface, with a default interface,
with partial networking, and with no attachment, with the external-access flag
both present and omitted. Verify the resolved list, create-time switch, port
move, reboot, DHCP discovery, automatic ExternalIP behavior, and cleanup.
Attempt a second attachment, the deprecated plural `--network-attachments`
option, an invalid interface, update/patch, IPv6, and malformed references;
verify no partial BM, port move, or allocation remains.

## Graduation gate

- Every BMaaS server-validation rule and phase-ordering rule has unit or
  integration coverage.
- NetworkClass Fabric Manager capability admission, including the repeated
  private-worker check, has negative coverage.
- E2E covers one-attachment success, isolation, port move, reboot, DHCP,
  ExternalIP, CaaS handoff, deletion, and recovery.
- Every user-visible unsupported interface, cardinality, IP, and update path
  has a negative test.
