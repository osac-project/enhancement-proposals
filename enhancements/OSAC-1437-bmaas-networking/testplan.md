# Testplan — OSAC-1437 BMaaS Networking

## Overview

- **Feature:** OSAC-1437 — BMaaS Networking: Single NIC, Provisioning Handoff,
  DHCP Discovery, and Auto External Access
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Deployment support boundary:** [Unified Networking deployment support
  boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary);
  BMaaS is supported only in connected deployments, not air-gapped or
  disconnected deployments.
- **Inherited creation rule:** BM and private worker admission follows the
  [strict dependency-ready creation contract](../OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation); BMaaS never creates a workload to wait for a Pending network dependency. Only OSAC-owned automatic ExternalIP children may be Pending after pool readiness and capacity validation.
- **Scope:** One tenant-facing physical attachment, BareMetalInstanceType
  interface validation, provisioning-network isolation, port move/reboot,
  DHCP lease discovery, CaaS private handoff, ExternalIP, and cleanup.
- **Prerequisite ownership:** The deployment-owned provisioning network,
  DHCP/gateway/SNAT, initial attach, BMC, inventory, and interface-MAC
  annotation exist before BMaaS begins. Every configured manager is a complete
  target with the BM handoff operations. Native Kubernetes NetworkPolicy alone
  is not sufficient for either OSAC policy contract. BMaaS does
  not create these deployment prerequisites.

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
| List omitted/empty | One default Subnet, default SecurityGroup, and first fabric interface; effective NetworkACL comes from that Subnet |
| Only Subnet in the tenant default VirtualNetwork | Preserve Subnet; fill only SecurityGroup and interface; inherit effective NetworkACL |
| Subnet in a non-default VirtualNetwork with SecurityGroup omitted | Reject with `InvalidArgument`; do not apply the tenant default group from another VirtualNetwork |
| One entry with an explicitly empty `security_groups` list | Treat the empty list as missing; preserve a default-VN Subnet and resolve the tenant default SecurityGroup; reject with `InvalidArgument` for a non-default-VN Subnet without a compatible group |
| Only compatible SecurityGroup list, Subnet omitted | Preserve groups; fill only the Subnet and interface when the groups belong to the tenant default VirtualNetwork; inherit effective NetworkACL |
| SecurityGroup list from a non-default VirtualNetwork, Subnet omitted | `InvalidArgument`; the default Subnet and explicit groups would be in different VirtualNetworks; no BM is persisted |
| Only interface | Preserve interface; fill only Subnet and SecurityGroup; inherit effective NetworkACL |
| Subnet and SecurityGroup list | Preserve both; fill only interface; inherit effective NetworkACL |
| Complete entry | Preserve every supplied field |
| Invalid explicit value | Reject; never replace with default |
| Selected Subnet has no effective NetworkACL | Reject with `FailedPrecondition`; do not use the deployment baseline or persist the BM |

##### Expected results

- Persisted BM resource contains exactly one attachment after resolution.
- The Subnet and its effective NetworkACL are Ready, in the same scope and
  VirtualNetwork, and IPv4. Every explicit/default
  SecurityGroup is unique, Ready, same-scope, and in the same VirtualNetwork.
- Omitted/true primary is accepted; sole entry is implicitly primary.
- After a Ready NetworkACL is associated with the previously unprotected
  Subnet, the same BM request succeeds and inherits that ACL.

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

#### TC-R1-03: SecurityGroup rule and complete-manager validation

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Create a tenant SecurityGroup with one valid allow-only rule and attach it
  to a BM; create an empty tenant group and verify rejection.
- Verify the auto-created default SecurityGroup may be empty and means deny.
- Reject action fields, deny rules, invalid direction/protocol/port/CIDR,
  duplicate group references, cross-tenant/wrong-VN groups, and non-Ready
  groups.
- Configure one complete manager or two complete managers.
- Route one policy operation through the temporary successful no-op AAP role.

##### Expected results

- One configured manager receives one policy target; two configured managers
  receive two targets and both must become Ready.
- Native Kubernetes NetworkPolicy alone is not sufficient for either OSAC
  policy contract; the complete adapter is required for manager registration.
- The resolved SecurityGroup list is carried through BM provisioning and the
  packet must pass both the SecurityGroup and effective Subnet ACL layers.

#### TC-R1-04: Non-Ready dependencies reject BM admission

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection and retry | critical | automated |

##### Cases

- Hold the selected Subnet, SecurityGroup, or effective NetworkACL in
  `Pending`, `Failed`, and `Deleting`; submit omitted, partial, and complete
  BM attachment requests.
- Hold the BareMetalInstanceType or required provisioning input non-Ready.
- Repeat through direct BMaaS, Catalog, private CaaS worker, REST, and direct
  CR paths; then advance each dependency and retry.

##### Expected results

- Every blocked request returns `FailedPrecondition` naming the exact
  attachment/profile field, dependency identity, observed state, required
  state, and wait-and-retry remediation.
- No BaremetalInstance, auto-child, capacity reservation, CR, interface move,
  DHCP request, or backend job is created for a rejected request.
- The private CaaS system-tenant BMI path still validates the Cluster owner's
  network dependencies; the tenant-scope exception does not bypass readiness.
- A BM may be `Pending` only after valid admission while its own provisioning
  and handoff run. Only OSAC-owned automatic ExternalIP and attachment
  children may be Pending; BMaaS never creates a workload to wait for a
  Pending network dependency.
- After the dependency is Ready, retry succeeds exactly once and begins one
  provisioning/handoff flow.

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

#### TC-R2-03: Complete manager admission is enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- no manager registration with the complete BM handoff contract;
- partial resource/policy/scope/service manager registration;
- disabled Fabric Manager;
- Fabric Manager missing `move_network_attachment`;
- Fabric Manager missing `query_dhcp_lease`;
- complete manager registration becomes invalid between NetworkClass creation
  and private CaaS worker dispatch.

##### Expected results

- Standalone, Catalog-based, and private CaaS BM creates fail with a provider
  `FailedPrecondition` before BM, automatic ExternalIP, attachment, or CR
  persistence when the complete manager profile is invalid.
- An unfinished operation uses the successful no-op AAP role rather than a
  tenant-visible partial manager/service path.
- The complete-profile check is repeated before private CaaS worker dispatch.

#### TC-R2-04: Shared resource dispatch and BM-specific handoff are separated

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- Create a VirtualNetwork, Subnet, SecurityGroup, NetworkACL, ExternalIP,
  ExternalIPAttachment, and NATGateway under complete Fabric-only, K8s-only,
  and combined manager registrations.
- Use the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md)
  for the complete K8s manager entrypoints, and a Fabric-only manager with the
  required BM handoff operations.
- Attempt BM creation in K8s-only mode through the complete workload path.
- In a combined deployment, make shared-resource jobs and the BM
  `move_network_attachment`/`query_dhcp_lease` phases complete or fail
  independently.

##### Expected results

- Shared resource creation follows the unified complete-manager contract: one
  target when one manager is configured, two targets when both are configured.
- BMaaS uses the selected manager's `move_network_attachment` and
  `query_dhcp_lease` operations; an unfinished operation may use the approved
  successful no-op.
- The current K8s-only profile's shared-resource entrypoints and complete
  `NetworkACL`/`NATGateway` contract are covered by the [K8s-only manager
  test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md). Its provider
  mechanics do not use the Fabric-specific BM port-move or DHCP jobs.
- ExternalIP and ExternalIPAttachment are dispatched to every selected
  manager. Their readiness waits for all selected implementations, while BM
  IP discovery remains a Fabric-manager DHCP operation.
- No tenant-supplied manager name, implementation annotation, or alternate
  dispatch path can make K8s-only BMaaS pass its Fabric prerequisite.

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
- The fabric manager confirms that the selected port no longer has an active
  lease in the tenant Subnet, the released address is no longer advertised in
  BaremetalInstance status after network cleanup, and a later server can
  allocate the address without a stale ownership conflict.
- If lease release/verification fails, the networking finalizer remains and
  the deletion retries; the controller does not silently finish with a stale
  tenant lease or status address.

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
  auto-created marker and exact immutable BM owner relationship. The
  ExternalIP may also carry `auto-created-for` for indexed discovery, but the
  label alone is not ownership proof.
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
- An owned auto-created attachment is deleted before its owned ExternalIP and
  before the BM finalizer completes. Ownership requires the canonical marker
  and exact immutable BaremetalInstance owner; the label alone is insufficient.
- A tenant-created ExternalIPAttachment targeting the BM blocks BM deletion;
  it is never detached, retargeted, or deleted by the BM controller.
- Transient or permanent cleanup failure retains the BM finalizer and leaves
  the BM `Deleting` until the attachment and ExternalIP cleanup succeeds; the
  controller never removes the finalizer to create an orphan.
- Manual ExternalIP resources remain tenant-managed and the ExternalIPPool is
  never cascaded.

#### TC-R5-03: BMaaS dependency guards and NetworkACL associations

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Delete a Subnet referenced by the BM's single attachment and by its effective
  NetworkACL. Verify the BM attachment and ACL are returned as direct blockers,
  including a child already `Deleting` but not archived; the SecurityGroup is
  validated as part of the BM attachment and is not a direct Subnet blocker.
- Delete the VirtualNetwork while its Subnet, SecurityGroup, NetworkACL, or supported
  NATGateway exists. Verify all direct blockers are returned and no resource is
  detached or deleted as a side effect.
- Attempt Subnet and VirtualNetwork deletion while a NetworkACL association
  exists. Verify the ACL is reported as a blocker with its identity and
  relationship. Delete the ACL, verify only the ACL/rules are removed and the
  Subnets and VirtualNetwork are unchanged, then retry the parent deletions
  and verify the ACL is no longer reported as a blocker.
- Run BM deletion concurrently with creation of a tenant attachment. Verify
  the transaction/locking contract admits either the reference or the delete,
  never a deleted target with a live attachment.

##### Expected results

- Every rejected delete returns `FAILED_PRECONDITION` with blocker kind,
  ID/name, relationship field, and required remediation, and leaves API,
  backend, finalizer, and capacity state unchanged.
- The BM-specific one-attachment contract remains immutable; deletion never
  changes the attachment list to make a non-leaf resource appear deletable.

#### TC-R5-04: Asynchronous ExternalIP and DNAT failures preserve BM state

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

- Private request contains exactly one attachment with Cluster Subnet,
  SecurityGroup list, and immutable node-set fabric interface; the effective
  NetworkACL is inherited from the Subnet.
- BMaaS revalidates port role, type, readiness, SecurityGroup references, and
  the Subnet's effective NetworkACL. For the trusted private CaaS path, network references are resolved in the source Cluster's
  tenant/project and are not rejected merely because the destination BMI is
  owned by the `system` tenant.
- Private caller cannot inject a second attachment or lifecycle port.

#### TC-R6-02: Catalog and direct BM creates are equivalent

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Expected results

- Execute the shared [TC-R4-04 precedence matrix](../OSAC-1433-unified-networking/testplan.md#tc-r4-04-catalog-template-private-and-direct-default-precedence-match)
  for direct BM creation, Catalog/Template materialization, and the trusted
  private CaaS worker request. Locked fields reject conflicting values;
  editable Catalog values accept an explicit valid tenant value; omitted values
  fall back Catalog → Template → tenant defaults; and explicit invalid,
  non-Ready, wrong-scope, or wrong-VirtualNetwork values are rejected rather
  than repaired.
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
the compound `interface=<port-name>` key, `security-groups=<name>[,...]`,
rejection of a NetworkACL key,
omitted interface selection, invalid/lifecycle interfaces, repeated
attachments, the deprecated plural `--network-attachments` option, and
explicit `primary=false` behavior.

**Integration:** Verify CLI requests use typed local references and the same
readiness, same-VirtualNetwork, capability, and rollback rules as direct API
requests. Verify `--external-ip-attachment` mapping in both states: present
sets true and starts automatic external access; omitted sets false, creates no
automatic ExternalIP/attachment, and consumes no pool capacity. Verify the
switch is immutable and there is no separate `--interface` syntax.

**E2E:** Create a BM with an explicit interface and SecurityGroup list, with a
default interface, with partial networking, and with no attachment, with the external-access flag
both present and omitted. Verify the resolved list, create-time switch, port
move, reboot, DHCP discovery, automatic ExternalIP behavior, and cleanup.
Attempt a second attachment, the deprecated plural `--network-attachments`
option, an invalid interface, update/patch, IPv6, and malformed references;
verify no partial BM, port move, or allocation remains.

## Graduation gate

- Every BMaaS server-validation rule and phase-ordering rule has unit or
  integration coverage.
- NetworkClass Fabric Manager complete-profile admission, including the repeated
  private-worker check, has negative coverage.
- E2E covers one-attachment success, isolation, port move, reboot, DHCP,
  ExternalIP, CaaS handoff, deletion, and recovery.
- Every user-visible unsupported interface, cardinality, IP, and update path
  has a negative test.
