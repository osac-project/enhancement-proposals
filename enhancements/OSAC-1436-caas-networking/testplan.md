# Testplan — OSAC-1436 CaaS Networking

## Overview

- **Feature:** OSAC-1436 — CaaS Networking via the OSAC Networking API
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Deployment support boundary:** [Unified Networking deployment support
  boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary);
  CaaS is supported only in connected deployments, not air-gapped or
  disconnected deployments.
- **Inherited creation rule:** Cluster and private worker admission follows the
  [strict dependency-ready creation contract](../OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation); neither may be created to wait for a Pending network dependency. Only OSAC-owned automatic ExternalIP children may be Pending after pool readiness and capacity validation.
- **Scope:** Singular Cluster attachment, BM node-set interface resolution,
  private BMaaS worker handoff, MetalLB/API/Ingress VIP feedback, auto
  ExternalIP, and cleanup.
- **Current support boundary:** BM node sets only, one tenant attachment per
  Cluster, one Subnet and SecurityGroup list shared by all node sets, and one
  resolved fabric interface per node-set type. Every configured manager is a
  complete resource/workload target. VM node
  sets, multi-NIC, tenant-selected physical interfaces, and DNS API are
  unsupported.

## Execution strategy

- **Unit:** Cluster server validation, node-set/port resolution, worker request
  construction, endpoint/VIP validation, Catalog resolution, and finalizer
  decisions.
- **Integration:** real PostgreSQL and CaaS handlers, Cluster/ClusterOrder
  CRDs/controllers in envtest/Kind, fake BMaaS private API, fake MetalLB and
  manager jobs, and asynchronous feedback.
- **E2E:** real connected CaaS with BM workers, MetalLB, API/Ingress
  connectivity, ExternalIP/DNAT, and deletion.

## Test cases

### R1: Singular Cluster attachment

#### TC-R1-01: Omitted, empty, partial, and complete attachment input

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Matrix

| Input | Expected result |
|---|---|
| Field omitted | Tenant default Subnet and default SecurityGroup; inherit effective NetworkACL |
| Empty message | Tenant default Subnet and default SecurityGroup; inherit effective NetworkACL |
| Only Subnet in the tenant default VirtualNetwork | Preserve Subnet; default only SecurityGroup; inherit effective NetworkACL |
| Subnet in a non-default VirtualNetwork with SecurityGroup omitted | Reject with `InvalidArgument`; do not apply the tenant default group from another VirtualNetwork |
| Attachment with an explicitly empty `security_groups` list | Treat the empty list as missing; preserve a default-VN Subnet and resolve the tenant default SecurityGroup; reject with `InvalidArgument` for a non-default-VN Subnet without a compatible group |
| Only compatible SecurityGroup list, Subnet omitted | Preserve groups; default only the Subnet when the groups belong to the tenant default VirtualNetwork; inherit effective NetworkACL |
| SecurityGroup list from a non-default VirtualNetwork, Subnet omitted | `InvalidArgument`; the default Subnet and explicit groups would be in different VirtualNetworks; no Cluster is persisted |
| Subnet and SecurityGroup list | Preserve both; inherit effective NetworkACL |
| Complete message | Preserve all supplied fields |
| Invalid explicit value | Reject; never repair with default |
| Selected Subnet has no effective NetworkACL | Reject with `FailedPrecondition`; do not use the deployment baseline or persist the Cluster |

##### Expected results

- Catalog/Template resolution precedes tenant defaults.
- Exactly one resolved Cluster attachment is stored.
- The selected Subnet and its effective NetworkACL are Ready, same-scope,
  same-VirtualNetwork, and IPv4. Every explicit/default
  SecurityGroup is unique, Ready, same-scope, and in the same VirtualNetwork.
- After a Ready NetworkACL is associated with the previously unprotected
  Subnet, the same Cluster request succeeds and inherits that ACL.

#### TC-R1-02: Unsupported Cluster attachment shapes are rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- repeated/multi-attachment representation;
- `fabric_interface` or physical-port field in public Cluster input;
- per-node Subnet/NetworkACL/SecurityGroup/tenant-interface override;
- wrong-scope, cross-VN, Pending, Failed, IPv6, or duplicate reference.

##### Expected results

- Request is rejected before Cluster, ClusterOrder, or worker persistence.
- No worker or port-move operation is dispatched.

#### TC-R1-03: SecurityGroup rule and complete-manager validation

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Create a tenant SecurityGroup with a valid allow-only rule and attach it to
  a Cluster; create an empty tenant group and verify rejection.
- Verify the auto-created default SecurityGroup may be empty and means deny.
- Reject action fields, deny rules, invalid direction/protocol/port/CIDR,
  duplicate group references, cross-tenant/wrong-VN groups, and non-Ready
  groups.
- Configure Fabric-only, K8s-only, and combined deployments with complete
  manager profiles.
- Route a policy operation through a temporary successful no-op AAP role.

##### Expected results

- One configured manager receives one policy target; two configured managers
  receive two targets and both must become Ready.
- Native Kubernetes NetworkPolicy alone is not sufficient for either OSAC
  policy contract; the complete adapter is required for the manager profile.
- Worker requests carry the exact resolved SecurityGroup list and the
  effective ACL is inherited from the Subnet. A packet must pass both layers.

#### TC-R1-04: Shared resources use complete manager targets

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- Create the CaaS VirtualNetwork and Subnet with Fabric-only, K8s-only, and
  combined complete manager registrations.
- In the combined case, make the selected Fabric and K8s jobs complete in
  different orders and make each target fail independently.
- Use the current K8s-only complete-manager entrypoint matrix from the
  [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
- Attempt NATGateway creation with the current K8s-only profile and route one
  operation through the development no-op AAP role.

##### Expected results

- VirtualNetwork/Subnet creation dispatches one job per configured manager and
  becomes Ready only after all selected targets succeed.
- K8s-only shared-resource operations are direct K8s operations, not a
  fallback to Fabric. The complete K8s-only profile and its normal no-op
  development path are covered by the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
- A NATGateway is accepted through the complete manager contract; MetalLB
  support alone is not treated as SNAT.
- Cluster creation uses the K8s-only, Fabric-only, or combined workload path
  when its service-specific prerequisites are Ready.
- ExternalIPAttachment dispatches to every selected manager after the
  ExternalIP is Allocated and the MetalLB-discovered endpoint is present. It
  becomes Ready only after all selected DNAT implementations succeed.

#### TC-R1-05: Non-Ready dependencies reject Cluster and worker admission

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection and retry | critical | automated |

##### Cases

- Hold the Cluster attachment's Subnet, SecurityGroup, or effective
  NetworkACL in `Pending`, `Failed`, or `Deleting` and submit direct and
  Catalog/Template Cluster creates.
- Hold a required NATGateway non-Ready in a topology without a direct route.
- Hold a ClusterTemplate, BareMetalInstanceType, or node-set input non-Ready
  and submit a Cluster create.
- During private worker materialization, hold the Cluster owner's resolved
  network dependency non-Ready and submit the system-tenant BMI request.
- Repeat the Cluster/ClusterOrder and private-worker cases through their direct
  hub-CR admission paths, not only through the public or private service APIs.
- Advance each dependency to its required state and retry the same request.

##### Expected results

- Each blocked request returns `FailedPrecondition` with the exact request
  field, dependency identity, observed state, required state, and remediation.
- No Cluster, ClusterOrder, BMI, worker CR, port-move operation, ExternalIP
  child, capacity reservation, or backend job is created for a rejected
  request.
- Direct hub-CR admission applies the same readiness guard: a non-Ready
  reference is rejected before the dependent CR is persisted or reconciled.
- The system-tenant location of a private BMI does not waive readiness of the
  Cluster owner's Subnet or policy resources.
- A Cluster can be Pending only after valid admission while its own selected
  manager or provisioning workflow runs. The only Pending dependency exception
  is the OSAC-owned automatic ExternalIP/ExternalIPAttachment pair after a
  Ready pool and capacity validation; NATGateway itself is never created to
  wait for a Pending dependency.
- After all dependencies become Ready, retry creates exactly one Cluster and
  one worker flow, with no duplicate dispatch.

### R2: BM node-set and interface resolution

#### TC-R2-01: Node-set types resolve ordered fabric interfaces

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Preconditions

- Two Ready BareMetalInstanceTypes with different ordered fabric ports.

##### Steps

1. Create a Cluster from a ClusterTemplate containing two authoritative node
   sets and wait for the resolved `fabric_interface` values to be stored.
2. Edit or reorder the ports on one referenced BareMetalInstanceType.
3. Reconcile the existing Cluster and inspect its ClusterOrder and subsequent
   BMaaS worker requests.

##### Expected results

- Each node set stores the first ordered `fabric` port for its type.
- Node sets may have different physical interfaces while sharing one tenant
  Subnet and inheriting its effective NetworkACL.
- The stored interface is immutable after Cluster creation.
- The existing Cluster and later worker requests retain the originally stored
  interfaces; the BareMetalInstanceType edit does not trigger re-resolution.

#### TC-R2-02: Invalid node-set types and ports fail closed

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- missing/Pending/Failed BareMetalInstanceType;
- no valid `fabric`-role port, including lifecycle-only or malformed port
  definitions; unrelated or unknown role strings may exist in the inventory but
  must never be selected for tenant networking;
- inventory host cannot provide stored interface;
- VM node set or multi-NIC node request.
- missing, extra, or renamed node-set keys compared with the authoritative
  ClusterTemplate;
- caller-supplied `baremetal_instance_type` that differs from the Template's
  typed reference.

##### Expected results

- Cluster create or worker provisioning fails with the specific field/condition.
- No fallback to an arbitrary or first non-fabric port occurs, and the presence
  of an unrelated unknown role does not invalidate an otherwise valid profile.
- Existing Cluster never silently re-resolves to a different port.
- Node-set keys must equal the Template's keys exactly, and hardware
  references must equal the Template's references exactly; only permitted
  node-set sizes may differ.

### R3: Private BMaaS worker handoff

#### TC-R3-01: Worker request is enriched with exactly one attachment

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Expected results

- Each worker request contains one BM attachment.
- `ClusterOrder.spec.networkAttachment` is the singular private-CR field.
- The Subnet comes from the Cluster attachment as a typed local reference; the
  effective NetworkACL is inherited through the Subnet association. No
  `networkAttachments[0]`, `subnetRef`, or NetworkACL reference in the
  attachment is accepted.
- Physical interface comes from immutable node-set resolution.
- Primary is implicit/true.
- BMaaS resolves the local network references in the Cluster tenant/project,
  does not require them to match the destination BMI's `system` tenant, and
  revalidates readiness, same-VN, instance type, and lifecycle role.
- Worker reconciliation never appends a second attachment or silently chooses
  another interface.

#### TC-R3-02: On-demand BMaaS lifecycle owns port movement and IP discovery

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Expected results

- CaaS creates each worker through the BMaaS private API on demand; it does
  not consume a pre-booted agent pool.
- BMaaS provisions the host on the provisioning network, moves the selected
  port to the tenant network after provisioning, reboots it, and discovers
  the tenant IP through the fabric DHCP lease API.
- CaaS watches Agent objects only for MAC correlation and worker/NodePool
  binding. It does not treat Agent status as the source of the tenant IP.
- A worker is not Ready before the BMaaS networking handoff and IP discovery
  complete; failed handoff or missing DHCP lease requeues/fails the worker
  without a partial ClusterOrder success.

#### TC-R3-03: Worker deletion protects network dependencies

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | high | automated |

##### Expected results

- Cluster deletion calls BMaaS deletion for every worker.
- Worker port returns to provisioning network before dependent network
  resources are released.
- ClusterOrder finalizer waits while workers remain.
- A worker failure/retry does not release the Subnet or ExternalIP early.

### R4: MetalLB and VIP feedback

#### TC-R4-01: VIPs are allocated and synchronized before readiness

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Create a Cluster with a valid attachment.
2. Provision MetalLB API and Ingress VIPs.
3. Propagate endpoint status through ClusterOrder to Cluster.
4. Verify readiness and connectivity.

##### Expected results

- API and ingress endpoints are canonical IPv4 values in the permitted Subnet
  and VIP pool.
- Cluster is not Ready before required endpoint status is present.
- Reserved MetalLB range does not overlap fabric DHCP allocation.

#### TC-R4-02: Endpoint and ExternalIP ordering failures requeue

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- endpoint status before ExternalIP allocation;
- ExternalIP allocation before endpoint status;
- empty, IPv6, duplicate, or out-of-subnet endpoint;
- a valid API or ingress endpoint changes after the Cluster has become Ready;
- missing/overlapping MetalLB pool;
- Signal RPC failure;
- manager/controller restart.

##### Expected results

- API and ingress attachments wait independently for their matching endpoint
  and Allocated ExternalIP.
- DNAT never dispatches with an empty, wrong, or duplicate endpoint.
- A changed endpoint after readiness is rejected or ignored, does not replace
  the persisted stable endpoint, and does not retarget an existing DNAT rule.
- Retry is idempotent and does not allocate duplicate VIPs or IPs.

#### TC-R4-03: Provider reachability selects the valid egress path

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- Provider reports `direct_route_available == true`.
- Provider reports no direct route and the resolved VirtualNetwork has a Ready
  NATGateway.
- Provider reports no direct route and the VirtualNetwork has no NATGateway,
  or its NATGateway is Pending, Failed, or Deleting.
- Provider cannot establish whether a direct route exists.
- Tenant attempts to override the route result or select an alternate
  reachability strategy.

##### Expected results

- A direct route is sufficient and does not require NATGateway.
- Without a direct route, only a Ready NATGateway satisfies the prerequisite.
- Unknown or unsatisfied reachability fails with `FailedPrecondition` before
  Cluster, worker, VIP, ExternalIP, or capacity persistence.
- No tenant-settable route override or fallback to an unready NATGateway is
  accepted.

### R5: Automatic ExternalIP access

#### TC-R5-01: Cluster auto external access reserves two distinct addresses

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Create a valid Cluster with `auto_external_ip_attachment=true`.
2. Verify two distinct IPv4 ExternalIPs and matching Pending attachments are
   reserved atomically.
3. Complete API and ingress endpoint discovery and wait for both attachments
   to become Ready.
4. Inspect the inline DNS records and verify that API and wildcard ingress
   records point to the corresponding ExternalIPs only for the `true` case.
5. Repeat with the field omitted and with it explicitly false, then inspect
   child resources, auto-created labels, pool capacity, and DNS records.

##### Expected results

- For the `true` case, two distinct IPv4 ExternalIPs are reserved atomically.
- For the `true` case, one attachment uses `API`, the other `INGRESS`.
- Pool exhaustion or inability to reserve two addresses leaves no Cluster,
  child, or capacity reservation.
- API DNAT uses only `status.apiEndpoint`; ingress DNAT uses only
  `status.ingressEndpoint`.
- Auto-created ExternalIPs and ExternalIPAttachments carry the canonical
  `osac.openshift.io/auto-created: "true"` marker and an exact immutable
  Cluster owner relationship. ExternalIPs may also carry the matching
  `auto-created-for` label for indexed discovery, but the label alone is not
  ownership proof.
- When automatic external access is enabled, inline DNS records point to the
  ExternalIPs; when it is omitted or false, no ExternalIP or
  ExternalIPAttachment is created, no pool capacity is reserved, and no
  ExternalIP-backed DNS records are created.

#### TC-R5-02: Asynchronous worker, ExternalIP, and cleanup failures recover safely

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E recovery | critical | automated |

##### Cases

- BMaaS private API failure or no available host;
- Agent registration timeout;
- AAP/template failure;
- ExternalIP allocation enters `Failed` after the Cluster and Pending child
  records were persisted;
- ExternalIPAttachment/DNAT dispatch fails after the Cluster is provisioned;
- transient and permanent auto-created-resource cleanup failure.

##### Expected results

- A worker failure is recorded and retried without marking the Cluster Ready
  or releasing the Subnet/ExternalIP prematurely.
- An Agent registration timeout deletes the timed-out BMI and retries; the
  failed worker does not remain bound to the Cluster.
- An AAP failure leaves ClusterOrder Failed with the job reference.
- ExternalIP failure leaves the Cluster Pending/functional without inbound
  external access; attachment failure does not activate DNAT.
- Transient cleanup retries through the parent finalizer. Permanent cleanup
  keeps the Cluster `Deleting` and retains its finalizer; the controller does
  not remove the finalizer to create an orphan or authorize cleanup from a
  label alone.
- Cleanup requires the canonical auto-created marker and exact immutable
  Cluster owner, and deletes each owned attachment before its owned ExternalIP.

#### TC-R5-03: CaaS dependency guards and NetworkACL associations

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Delete a Subnet referenced by the Cluster's singular attachment and by its
  effective NetworkACL. Verify the Cluster attachment and ACL are reported as
  direct blockers, including a child already `Deleting` but not archived; the
  SecurityGroup is validated as part of the Cluster attachment and is not a
  direct Subnet blocker.
- Delete the VirtualNetwork while its Subnet, SecurityGroup, NetworkACL, or supported
  NATGateway exists. Verify all direct blockers are returned and no resource is
  detached or deleted as a side effect.
- Attempt Subnet and VirtualNetwork deletion while a NetworkACL association
  exists. Verify the ACL is reported as a blocker with its identity and
  relationship. Delete the ACL, verify only the ACL/rules are removed and the
  Subnets and VirtualNetwork are unchanged, then retry the parent deletions
  and verify the ACL is no longer reported as a blocker.
- Run Cluster deletion concurrently with creation of a tenant attachment or a
  private worker reference. Verify the transaction/locking contract prevents
  a deleted Cluster or worker target from retaining a live reference.

##### Expected results

- Every rejected delete returns `FAILED_PRECONDITION` with blocker kind,
  ID/name, relationship field, and required remediation, and leaves the
  Cluster, worker handoff, networking resources, backend state, finalizers,
  and capacity unchanged.
- Deletion never changes the singular Cluster attachment or per-node-set
  resolved interface to bypass a dependency guard.

### R6: Operations, Catalog, and unsupported behavior

#### TC-R6-01: CaaS network-owned fields are immutable

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Update, patch, replace, and field-mask changes to the singular Cluster
  attachment and either nested reference;
- changes to any stored per-node-set `fabric_interface`;
- changes to the `API`/`INGRESS` endpoint binding on an
  ExternalIPAttachment;
- changes to `auto_external_ip_attachment`;
- direct ClusterOrder spec/status attempts that alter network-owned input or
  bypass validated endpoint feedback.

##### Expected results

- Update, patch, replace, and field-mask changes to the network-owned
  attachment, Subnet, stored interfaces, endpoint enum, and
  auto-external switch are rejected.
- Controller-owned endpoint status, conditions, and finalizers can only be
  written through the validated feedback/reconciliation path; direct tenant
  status/spec mutation is rejected.

#### TC-R6-02: Catalog and direct Cluster creates are equivalent

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Expected results

- Execute the shared [TC-R4-04 precedence matrix](../OSAC-1433-unified-networking/testplan.md#tc-r4-04-catalog-template-private-and-direct-default-precedence-match)
  for direct Cluster creation, Catalog/Template materialization, and the
  private ClusterOrder-to-BMaaS worker path. Locked fields reject conflicting
  values; editable Catalog values are overridden only by explicit valid tenant
  values; omitted values fall back Catalog → Template → tenant defaults; and
  explicit invalid, non-Ready, cross-scope, or cross-VirtualNetwork values are
  rejected rather than repaired.
- `fabric_interface` is never Catalog-governed.
- Shared Catalog Items cannot lock/default tenant-local references.
- Catalog edits do not mutate existing Cluster networking or metadata.

#### TC-R6-03: Invalid CaaS surface is rejected; unfinished provider paths no-op

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- VM-based node set;
- multi-NIC or repeated Cluster attachment;
- tenant-selected physical interface/per-node network;
- lifecycle/no-fabric port;
- wrong endpoint enum or duplicate API/Ingress binding;
- direct ClusterOrder bypass;
- invalid SecurityGroup or NetworkACL creation/dispatch, including a partial
  manager profile;
- Cluster creation against a `cudn_evpn` Subnet through the shared contract,
  including a successful no-op provider operation while EVPN-specific worker
  integration is unfinished;
- legacy deployment-wide step collections as a tenant input;
- DNS API, NATGateway, or other non-CaaS network fields embedded in the
  public Cluster request (a standalone NATGateway still follows the shared
  manager and readiness contract).

##### Expected results

- Invalid CaaS input is rejected before persistence and does not create a
  partial Cluster, worker, VIP, IP, or port move.
- The `cudn_evpn` case is admitted through the normal complete-manager target
  plan; an unfinished worker operation completes through the successful no-op
  AAP path and is not exposed as an unsupported manager/service branch.

### R7: Cluster CLI contract

#### TC-R7-01: Singular attachment CLI mapping and rejection

**Unit:** Verify one optional `--network-attachment` maps to singular
`spec.network_attachment` containing `ClusterNetworkAttachment`. Verify
repeated options, the deprecated plural `--network-attachments` option,
`interface=...`, `primary=...`, per-node-set values, unknown keys, invalid
CIDRs, malformed references, and malformed/duplicate `security-groups` values
are rejected.

**Integration:** Verify omitted, partial, and complete CLI attachments use the
shared defaulting/readiness rules and reach the private BMaaS handoff with
one enriched `BareMetalNetworkAttachment` per worker. Verify
`--external-ip-attachment` maps to the create-time boolean and endpoint
validation remains authoritative. Run both flag states: present enables the
two automatic Cluster external-access paths; omitted sets false, creates none,
and consumes no pool capacity. Verify the switch is immutable.

**E2E:** Create a Cluster with explicit and defaulted CLI networking, verify
one shared Subnet, resolved SecurityGroups, and resolved per-node-set interfaces, with the external
access flag both present and omitted, then delete it. Verify the present form
creates API and ingress external access while the omitted form creates none.
Attempt multi-attachment, the deprecated plural `--network-attachments` option,
tenant-selected interface, primary, network-field update, and invalid
target/reference requests; verify no partial Cluster, worker, VIP, IP, or
port-move state.

## Graduation gate

- Every CaaS server-validation and worker-handoff rule has unit/integration
  coverage.
- BM-only and combined-manager supported workflows have E2E coverage.
- Template node-set ownership, direct-route/NAT selection, API/Ingress VIP
  feedback, ExternalIP ordering, cleanup, and retry pass.
- Every user-visible unsupported CaaS path has a negative E2E test.
