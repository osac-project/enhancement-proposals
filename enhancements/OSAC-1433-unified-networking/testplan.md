# Testplan — OSAC-1433 Unified Networking

## Overview

- **Feature:** OSAC-1433 — Unified Networking API for VMaaS, CaaS, and BMaaS
- **Source design:** [design.md](design.md)
- **K8s-only manager plan:** [K8s-only Networking Manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md)
- **Scope:** Shared networking resources, IPv4 field contracts, complete
  manager lifecycle operations, defaulting semantics, dependency
  readiness, allocation transactionality, and cross-service interoperability.
- **Operation contract:** create, read/list, and delete only for network-owned
  fields. Network-owned update, patch, and replace operations are unsupported.
- **Excluded:** East-west networking is not implemented and is governed by its
  own design; this shared plan does not test its update or resize behavior.
  Unsupported in the current boundary: multi-interface, IPv6, dual-stack,
  multi-hub, air-gapped, and VN-peering behavior. These are negative-test
  cases, not supported scenarios.
- **Deployment support boundary:** [Unified Networking deployment support
  boundary](design.md#deployment-support-boundary) is authoritative for all
  manager profiles and service-specific test plans.

## Execution strategy

The test plan uses three layers:

- **Unit:** fast deterministic validator, resolver, transaction-decision,
  controller-state, dispatcher-plan, and status-parser tests using fake
  repositories, Kubernetes clients, managers, and job responses.
- **Integration:** fulfillment-service with real ephemeral PostgreSQL,
  protovalidate, OPA/RBAC, public/private handlers, and an envtest or Kind
  cluster running real CRDs/admission/controllers. Manager and AAP/fabric
  behavior is simulated with contract-compatible fakes.
- **E2E:** the supported connected single-hub deployment with real
  authentication, OSAC components, the applicable manager, and dataplane
  connectivity checks. Both combined-manager and K8s-only/BM-only topologies
  are tested for every configured manager; manager registration does not
  contain a resource, scope, or service capability matrix.

Every negative test verifies both the expected error/condition and the absence
of an invalid parent, child, allocation, backend operation, or orphan.

## Test cases

### R1: NetworkClass manager registration and complete contract

#### TC-R1-01: Combined manager configuration is accepted

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Preconditions

- Provider registers one fabric manager and one K8s manager.
- Both are registered as IPv4 managers and provide the complete
  create/read/delete lifecycle for all canonical networking resources and all
  VMaaS, BMaaS, and CaaS workload flows. No resource or workload capability
  map is present.
- Provider inventory reports exactly one active hub and
  `connectivity_mode=connected`.

##### Steps

1. Create the deployment NetworkClass with both manager references.
2. Resolve a VirtualNetwork and Subnet provisioning plan.
3. Resolve the per-resource dispatch plan for VirtualNetwork and Subnet.

##### Expected results

- NetworkClass is accepted.
- The persisted NetworkClass identifies the single active hub and the
  deployment is admitted as connected.
- The persisted NetworkClass status reports `addressFamily=ipv4` and does not
  expose a per-resource, policy, scope, or service capability matrix.
- The dispatch plan contains both managers for every resource and workload
  operation.
- No tenant-visible implementation-strategy field is created and the tenant
  cannot replace the controller-owned target metadata with an arbitrary value.

#### TC-R1-02: Complete manager profiles and development no-op behavior are evaluated

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Register a K8s-only manager and verify the complete profile is used for
   every canonical resource and all three workload services; run the concrete
   entrypoint matrix in the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
2. Configure a Fabric-only manager and run the same complete resource and
   workload matrix through its Fabric entrypoints.
3. Configure both managers and inspect the dispatch plan for every resource
   and workload operation.
4. Temporarily route one unfinished operation through a successful no-op AAP
   role and create the corresponding API resource.
5. Attempt to register a partial profile containing per-resource, per-policy,
   per-scope, or per-service support declarations.

##### Expected results

- K8s-only VM/shared-resource behavior is admitted under the complete manager
  contract; the concrete shipped K8s-only profile, entrypoints, and workload boundary are
  verified by the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
- The NetworkClass status exposes only `addressFamily=ipv4` and ordinary
  readiness/job status.
- Every selected manager receives every resource and workload operation. In a
  combined deployment both targets must report success before Ready.
- The development no-op AAP role still produces a normal successful target
  result and never creates a tenant-visible unsupported branch.
- A partial registration is rejected as provider configuration; it is not
  accepted as a partial tenant API surface.

#### TC-R1-04: Every networking resource Create uses the complete manager contract

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Resources

Run the matrix for `VirtualNetwork`, `Subnet`, `SecurityGroup`, `NetworkACL`,
`ExternalIPPool`, `ExternalIP`, `ExternalIPAttachment`, and `NATGateway`.
Use valid Ready dependencies for each row so that manager completeness and
dispatch are the only provider variables.

##### Matrix

| Manager configuration | Expected result |
|---|---|
| One complete manager is configured | Create is accepted and dispatched to that manager |
| Two complete managers are configured | Create is accepted and dispatched to both managers; both must report success |
| A registration contains a partial resource, policy, scope, or service declaration | NetworkClass admission rejects the provider configuration; no partial tenant API is exposed |
| A selected manager has an unfinished backend operation | Create is still admitted and dispatched; the development AAP role may complete as a successful no-op |

##### Expected results

- The check occurs before every resource Create, including provider-created
  defaults and Catalog/private service paths.
- A resource becomes Ready only after every selected manager succeeds (or the
  approved development no-op returns success).
- Read and delete use the same persisted manager target plan; no manager is
  silently omitted because of a resource or service subset declaration.

#### TC-R1-06: Dispatch targets and AAP entrypoints match the deployment model

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Resources and target profiles

Run the matrix for `VirtualNetwork`, `Subnet`, `SecurityGroup`, `NetworkACL`,
`ExternalIPPool`, `ExternalIP`, `ExternalIPAttachment`, and `NATGateway`.
Use a valid Ready dependency graph and vary only the manager registrations:

| Profile | Expected target and entrypoint behavior |
|---|---|
| K8s-only | One direct K8s target and one K8s AAP job. The concrete manager entrypoint mapping is defined and tested by the [K8s-only manager proposal](../OSAC-1433-k8s-only-k8s-manager/design.md). |
| Fabric-only | One Fabric target and one Fabric AAP job; no K8s job is created. |
| Combined | Two targets and two jobs, one per manager. Both must report success before Ready. |
| Development no-op | The selected operation still produces its normal target/job and may report successful no-op completion. |

##### Steps

1. For each profile, create every canonical resource and exercise every
   VMaaS, BMaaS, and CaaS workload operation.
2. Capture the internal dispatch plan, persisted controller metadata, AAP
   template name, selected manager role, and `osac_job_vars.resource`.
3. For dual-target resources, make one target Pending, one Ready, then make
   the first Ready; repeat with one target Failed.
4. Attempt to submit tenant-supplied implementation-strategy annotations,
   manager names, combined values such as `fabric+k8s`, and a forged
   K8s-specific annotation on create and update.
5. Delete a successfully provisioned resource after the NetworkClass is
   unavailable and verify deletion still uses the persisted target set.
6. Repeat after a selected manager registration becomes unavailable or
   incomplete between Create and reconciliation.
7. Read and list a previously persisted resource after its manager registration
   is temporarily unavailable.

##### Expected results

- K8s-only dispatch is direct K8s implementation. The generic
  `osac.openshift.io/implementation-strategy` annotation names the K8s
  manager, and `osac.openshift.io/k8s-implementation-strategy` is absent.
  The current profile's resource entrypoints are
  covered by the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
- Fabric-only dispatch uses the generic annotation for the Fabric manager and
  does not add a K8s annotation.
- Dual-target dispatch uses the generic annotation for the Fabric target and
  the K8s-specific annotation for the K8s target. Each AAP job receives a
  per-target copy with the generic annotation overridden to that job's
  manager; the persisted object is not mutated by this override.
- A resource is not Ready until all selected targets succeed. Every selected
  manager receives the operation; an unfinished operation may use the
  development no-op AAP role.
- The action template is selected by operation (`osac-create-*`,
  `osac-delete-*`, or the ExternalIP attachment action), while the manager
  role is selected by the target annotation. No combined strategy string is
  emitted.
- Tenant-supplied manager/strategy metadata is rejected and cannot change the
  target set. Deletion calls exactly the targets that successfully provisioned
  the object; it does not invent a missing target.
- A manager registration change that would make the profile incomplete is a
  provider configuration error; it does not create a partial target plan.
- Read/list returns the persisted resource and controller status without an
  AAP job and without requiring a current manager lookup; reconciliation may
  report the manager/dependency failure separately.

#### TC-R1-03: Invalid or tenant-controlled manager configuration is rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Cases

- neither manager is configured;
- manager is not provider-registered;
- manager registration exists but is disabled;
- manager registration contains a resource, policy, workload-scope, or service
  subset declaration;
- the deployment NetworkClass is absent, Pending, or Failed when a
  networking resource is created;
- the deployment offers the CaaS/MetalLB VIP path but lacks the required
  MetalLB prefix length;
- the MetalLB prefix is zero, outside the IPv4 prefix range, not more specific
  than the participating Subnet prefix, or reserves a range outside the
  Subnet;
- a non-CaaS deployment supplies `metallb_vip_prefix_length`;
- zero hubs, multiple active hubs, or an air-gapped connectivity report;
- a second active NetworkClass exists for the deployment;
- tenant supplies a NetworkClass, manager, implementation strategy, or
  provider-only manager/configuration override;
- tenant attempts to create a resource before the complete NetworkClass is
  Ready.

##### Expected results

- The request is rejected with the documented authorization, validation, or
  failed-precondition status.
- A missing or non-Ready deployment NetworkClass returns
  `FailedPrecondition` before the resource or backend operation is persisted or
  dispatched.
- No networking resource or backend operation is created.

#### TC-R1-05: Provider-owned operations and scope are enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- Tenant attempts to create, update, patch, replace, or delete
  `NetworkClass`.
- Tenant attempts to create, update, patch, replace, or delete
  `ExternalIPPool`.
- Provider attempts to update, patch, or replace NetworkClass network-spec
  fields (managers, implementation strategy, defaults, or
  `metallb_vip_prefix_length`).
- Provider attempts to update, patch, or replace ExternalIPPool network-spec
  fields (IP family, CIDRs, capacity, or lifecycle settings).
- Provider performs a metadata-only update where the standard metadata
  contract permits it; the test confirms this does not mutate the immutable
  network spec.
- Tenant attempts to read or list another tenant's pool or use it through a
  typed reference outside the provider-visible scope.
- Tenant attempts to get or list another tenant's VirtualNetwork, Subnet,
  SecurityGroup, NetworkACL, ExternalIP, ExternalIPAttachment, NATGateway, or workload
  network attachment/status, including through a name filter, label/filter,
  status field, Catalog policy, or typed reference.
- Tenant references a provider-created pool that is explicitly visible to the
  tenant.

##### Expected results

- Provider-only mutations return the platform's authorization/visibility
  error before semantic validation or persistence.
- Provider network-spec mutations are rejected by the immutability guard;
  the stored spec and backend state remain unchanged, including when the
  attempted field is `metallb_vip_prefix_length`. Metadata-only behavior
  follows the standard metadata contract and never changes the network spec.
- A visible provider pool may be read or referenced, but its family, CIDR,
  capacity, and lifecycle cannot be supplied or changed by the tenant.
- Cross-scope reads and references do not reveal the other tenant's resource.
- The same scope result applies to every network resource, attachment, and
  reference: the object is hidden or the request returns the platform's
  non-disclosing visibility error, and no list filter or status field reveals
  its identity or network values.

### R2: Shared resource fields and formats

#### TC-R2-01: Valid IPv4 resources and references are accepted

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Steps

1. Create a Ready VirtualNetwork with canonical IPv4 CIDR.
2. Create a contained non-overlapping Subnet.
3. Create a SecurityGroup with a valid allow-only rule.
4. Create a NetworkACL with a valid rule and associate it with the Subnet.
5. Create a Ready IPv4 ExternalIPPool with one CIDR.
6. Allocate separate, valid ExternalIPs and create an ExternalIPAttachment
   and NATGateway reference.
7. Get and list every created resource, including the VirtualNetwork, Subnet,
   SecurityGroup, NetworkACL, ExternalIPPool, ExternalIP, ExternalIPAttachment, and
   NATGateway.

##### Expected results

- Every create accepts the documented field types and values.
- References are typed, same-scope, and Ready/Allocated before use.
- Tenant-scoped get/list calls return the caller's resources and complete
  network-owned fields; provider-visible pool reads follow the documented
  provider visibility rule.
- Resources with Ready semantics may remain Pending after successful admission
  until their own manager backend operation completes and then become Ready;
  ExternalIP instead transitions from Pending to Allocated before it can be
  consumed. A dependent create never uses this state to wait for its
  reference.

#### TC-R2-02: Invalid formats and relationships are rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- malformed IPv4 address or CIDR;
- IPv6 or dual-stack value;
- host bits set in a network CIDR;
- duplicate VirtualNetwork name in the same tenant/project scope;
- Subnet outside, equal to, or overlapping a sibling Subnet;
- wrong reference type, missing reference, cross-tenant/project reference;
- Pending, Failed, or non-Ready dependency;
- ExternalIPPool with `ip_family=UNSPECIFIED`, zero or multiple CIDRs, a CIDR
  outside the provider-permitted address space, or overlapping allocation
  ownership without an explicit disjoint-ownership declaration;
- duplicate ExternalIP consumer or second NATGateway for one VN;
- exact duplicate ExternalIPAttachment for the same ExternalIP, target, and
  endpoint;
- arbitrary tenant-selected ExternalIP address.
- manager-reported ExternalIP address outside the pool, equal to a network or
  broadcast address, reserved, IPv6, or already allocated;
- direct ExternalIPAttachment with a Pending/Failed ExternalIP or non-Ready
  target;

##### Expected results

- Invalid format/relationship returns `InvalidArgument`.
- Existing but unusable dependency returns `FailedPrecondition`.
- Caller-invalid creates leave no persisted object or backend operation.
- An invalid manager-reported allocation is recorded as a provisioning
  failure, never becomes `Ready`, and does not activate an attachment or leave
  an allocated address/consumer behind.

#### TC-R2-03: Cross-tenant VN CIDR overlap follows the documented isolation rule

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | high | automated |

##### Expected results

- Overlapping VirtualNetwork CIDRs for different tenants are accepted where
  fabric isolation is the declared boundary.
- Subnet overlap within one VirtualNetwork remains rejected.
- Different VirtualNetworks remain isolated; the API does not implement VN
  peering or cross-VN routing.

#### TC-R2-04: ExternalIPPool readiness requires the complete manager lifecycle

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Steps

1. Configure a complete provider manager and attempt to create a
   provider-scoped IPv4 ExternalIPPool.
2. Make the manager return an invalid
   family, range, or lifecycle response during pool reconciliation.
3. Create two pools with overlapping allocation ranges, then configure
   disjoint provider allocation ownership and repeat.

##### Expected results

- A pool is not marked Ready unless allocate, release, and report operations
  all return valid contract responses.
- Invalid manager lifecycle responses leave the pool Pending or Failed and
  prevent ExternalIP allocation.
- Overlapping pools are rejected unless the manager explicitly provides
  disjoint allocation ownership; accepted pools cannot allocate the same
  address.

#### TC-R2-05: Strict dependency-ready admission is enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection and retry | critical | automated |

##### Preconditions

- Use a controllable fake manager so each resource can be held in `Pending`,
  returned as `Failed`, or advanced to `Ready`/`Allocated` independently.
- Create valid provider registrations, an active connected single-hub
  NetworkClass, and canonical IPv4 input data.
- Use public tenant handlers, default/onboarding handlers, Catalog/Template
  materialization, private service handlers, and direct hub-CR admission paths
  where applicable.

##### Cases

| Create request | Blocker state | Required assertion |
|---|---|---|
| `Subnet` or `SecurityGroup` referencing a VirtualNetwork | `Pending`, `Failed`, or `Deleting` | Reject before persistence with `FailedPrecondition` naming `spec.virtual_network`; no Subnet/SG, CR, reservation, or job |
| `NetworkACL` referencing a VirtualNetwork or associated Subnet | Any required reference is not `Ready` | Reject with every blocking field/reference; no ACL, association, CR, or job |
| `ExternalIP` referencing an ExternalIPPool | Pool is not `Ready` or has no capacity | Reject with `FailedPrecondition`; no ExternalIP or allocation reservation |
| Direct `ExternalIPAttachment` referencing an ExternalIP | ExternalIP is not `Allocated`, is consumed, or is `Deleting` | Reject naming `spec.external_ip`; no attachment or DNAT |
| Direct `ExternalIPAttachment` targeting a workload | Target is not `Ready`, endpoint is absent, or target is `Deleting` | Reject naming the target oneof/endpoint; no attachment or DNAT |
| `NATGateway` referencing a VirtualNetwork or ExternalIP | VN is not `Ready`, or IP is not `Allocated`/is consumed | Reject naming each blocker; no NATGateway, CR, or SNAT |
| VM, Cluster, or BM workload with a resolved Subnet, SecurityGroup, or effective ACL | Any resolved dependency is not `Ready` | Reject before workload persistence, auto-child creation, CR, or backend job |
| VM, Cluster, or BM workload with a service profile/template/node-set | Profile/input is missing, `Pending`, or `Failed` | Reject with the profile field and state; no workload or network child |
| Private CaaS worker BMI | Cluster owner's resolved network dependency is not `Ready` | Reject before system-tenant BMI/worker CR; do not apply destination-tenant scope as a workaround |
| Any direct hub-CR create with a referenced dependency | Referenced VN, Subnet, ExternalIPPool, ExternalIP, workload, policy, profile, or NATGateway is not in the matrix-required state | Reject at hub admission with the same field-specific `FailedPrecondition`; no dependent CR/object, reservation, manager call, or AAP job is persisted/dispatched |
| Any create after a dependency becomes `Ready`/`Allocated` | All required references are usable | The same request succeeds; exactly one object/association is persisted and dispatch occurs once |

##### Expected results

- Existing unusable dependencies always return `FailedPrecondition`, never a
  successful create followed by a Pending dependent.
- Each response contains the dependent kind/name, exact request field path,
  dependency kind/name, observed state, required state, and remediation to
  wait and retry. When several dependencies are blocked, all are reported.
- Missing or invisible references retain visibility-safe `NotFound`/
  `InvalidArgument` behavior and do not disclose cross-tenant resources.
- A rejected request performs no database write, child creation, capacity
  reservation, CR creation, AAP dispatch, or manager call.
- Direct hub-CR admission applies the same dependency matrix as the public and
  private APIs; a controller must not accept a CR with a non-Ready dependency
  and later rely on reconciliation to repair it.
- A resource whose own manager operation returns `Pending` may remain Pending
  after successful admission. A dependent create submitted during that period
  is rejected; after the parent reaches the required state, retry succeeds.
- Unit tests cover the matrix and error/status-detail construction; integration
  tests cover transaction rollback, public/private handlers, stale readiness
  re-resolution, and concurrent readiness changes; E2E tests cover one
  rejection-and-retry flow for VN/Subnet, workload/ACL, ExternalIP/attachment,
  and NATGateway.

### R3: SecurityGroup and NetworkACL policy contracts

Positive cases use a NetworkClass whose selected manager(s) are complete
implementation targets for the policy lifecycle. Native Kubernetes
NetworkPolicy alone is not sufficient for either OSAC policy contract.

#### TC-R3-00: SecurityGroup rule, default, and attachment semantics

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- Valid stateful allow rules for ingress/egress, TCP/UDP/ICMP/ANY, optional
  port, and canonical IPv4 source/destination CIDR.
- Tenant-created SecurityGroup with zero rules.
- Auto-created tenant default SecurityGroup with zero rules.
- An action field, deny rule, invalid direction/protocol/port/CIDR, duplicate
  rule, or unsupported priority/most-specific field.
- Multiple SecurityGroups attached to one VM, BM, and Cluster; duplicate,
  cross-tenant, wrong-VN, Pending, and Failed group references.
- Allowed flow with stateful return traffic, unmatched traffic, and a flow
  denied by the ACL layer despite an SG allow.

##### Expected results

- Tenant-created groups require at least one rule; the auto-created default
  group may be empty and means default deny.
- SecurityGroup rules are allow-only, aggregate across attached groups, and
  statefully permit return traffic for an accepted flow.
- Every explicit/default reference is typed, unique, Ready, same-tenant, and
  in the attachment's VirtualNetwork.
- A packet must pass both the workload SecurityGroup layer and the effective
  Subnet NetworkACL layer. No rule is updated or normalized after creation.

#### TC-R3-01: Rule fields and rule-set semantics are enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- valid SecurityGroup allow-only rules and NetworkACL allow/deny rules for
  ingress/egress and tcp/udp/icmp/any;
- optional ports for TCP/UDP, where omission matches all ports, and omitted
  ports for ICMP/any;
- valid direction-specific canonical IPv4 CIDR;
- invalid action, direction, protocol, port range, or source/destination;
- non-canonical enum spelling such as `TCP`, `UDP`, or `Ingress`;
- duplicate normalized rule;
- conflicting equal-specificity rule;
- tenant-created empty rule list;
- NetworkACL with no Subnet association;
- NetworkACL associated with a Subnet from another VirtualNetwork;
- second NetworkACL associated with the same Subnet, including an ordinary
  custom ACL targeting the default Subnet that already has the system-created
  default ACL;
- tenant default NetworkACL containing explicit deny-all ingress and allow-all egress;
- attempted hidden/default policy or implicit connection-tracking behavior.

##### Expected results

- User-created NetworkACLs require at least one valid rule and one or more
  explicit Subnet associations.
- Each tenant's default NetworkACL is associated with its default Subnet and
  contains explicit deny-all ingress and allow-all egress rules.
- Traffic with no matching tenant rule falls through to the provider-owned
  deployment baseline and is permitted; the baseline is not tenant data.
- NetworkACL membership is managed by Subnet association, not by a workload
  attachment field.
- Invalid, duplicate, and conflicting rules are rejected before persistence.
- Enum values are case-sensitive and must use the canonical lower-case
  spellings; the server does not silently case-fold unsupported input.

#### TC-R3-02: Stateless and most-specific rule behavior is verified

| Test type | Priority | Automation |
|---|---|---|
| Unit, E2E | critical | automated |

##### Cases

- Use a custom NetworkACL associated with a non-default Subnet so the tenant
  default ACL's explicit egress allow rule does not participate in the test.
- Allow ingress TCP/443 from `0.0.0.0/0` without a matching egress rule and
  verify that the request is allowed and the return packet is independently
  permitted by the deployment baseline, not by connection tracking.
- Delete the first ACL and create a replacement ACL with a matching egress deny
  rule for the return destination port. Verify that the replacement tenant rule
  overrides the baseline and blocks the return path.
- Delete the replacement ACL and verify that the return path is permitted by
  the deployment baseline again. No rule is added to or removed from an
  existing ACL.
- Create overlapping rules where a narrower CIDR, exact protocol, or exact
  port conflicts with a broader match and verify the narrower match wins.
- Submit contradictory rules with identical CIDR, protocol, and port
  specificity and verify that creation is rejected.

##### Expected results

- Every packet is evaluated independently; the ACL does not track connections
  or permit response packets because of connection state. A response may still
  be permitted by an independent tenant egress rule or by the deployment
  baseline.
- Tenant rules override the deployment baseline whenever they match. A
  tenant-specific opposite-direction rule is required to impose tenant policy
  on return traffic; otherwise the provider-owned baseline currently permits
  it.
- The provider-owned deployment baseline is the least-specific fallback and
  currently permits all traffic; it cannot be changed by tenant input.
- The most-specific matching rule wins: longest matching remote CIDR prefix,
  exact protocol over `any`, then exact port over an omitted port.
- Contradictory equal-specificity rules are rejected before persistence.

#### TC-R3-03: One ACL can protect multiple Subnets

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Steps

1. Create two Ready Subnets in one VirtualNetwork.
2. Create one NetworkACL with explicit ingress and egress rules and associate
   it with both Subnets.
3. Verify both Subnets report the same effective NetworkACL.
4. Delete the ACL and create a replacement ACL with only the remaining
   Subnet association, then verify the old generated policy is gone from the
   disassociated Subnet. No ACL update or association mutation is used.

##### Expected results

- The ACL is applied to both associated Subnets with no duplicate effective
  rules.
- A Subnet cannot have a second effective NetworkACL. The system-created
  default ACL counts, so an ordinary custom ACL cannot target the default
  Subnet while that default ACL exists. Default ACL replacement is tested
  through the default-resource replacement workflow.
- Workload attachments contain the typed Subnet reference and optional typed
  SecurityGroup references; the effective ACL is resolved from the Subnet and
  is never embedded in the attachment.

### R4: Attachment defaulting and cardinality

#### TC-R4-01: Omitted, empty, partial, and complete attachments resolve correctly

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Matrix

| Input | Expected result |
|---|---|
| Missing attachment field | All applicable defaults are resolved |
| Explicit empty list/message | Same default behavior as documented for the resource |
| Only Subnet supplied in the tenant default VirtualNetwork | Preserve Subnet; resolve the tenant default SecurityGroup and the effective ACL from the Subnet |
| Subnet in the default VN supplied with SecurityGroup omitted | Fill only the missing SecurityGroup with the tenant default group |
| Subnet in a non-default VN supplied with SecurityGroup omitted | `InvalidArgument` naming both VirtualNetworks; do not attach the default-VN group or persist the workload |
| Explicit SecurityGroup belongs to a different VN from the selected Subnet | `InvalidArgument`; the resolved attachment must use one VirtualNetwork |
| Attachment supplied with an explicitly empty `security_groups` list | Treat the empty list as missing; resolve the tenant default SecurityGroup only when the supplied/resolved Subnet is in the tenant default VirtualNetwork; otherwise reject with `InvalidArgument` |
| Only compatible SecurityGroup list supplied, Subnet omitted | Preserve groups; resolve the default Subnet and effective ACL when the groups belong to the tenant default VirtualNetwork |
| SecurityGroup list supplied from a non-default VirtualNetwork, Subnet omitted | `InvalidArgument`; the resolved default Subnet and explicit groups would be in different VirtualNetworks, so no defaulting or workload persistence occurs |
| Subnet and SecurityGroup list supplied | Preserve both; resolve effective ACL from the Subnet |
| Selected Subnet has no effective NetworkACL | `FailedPrecondition` identifying the missing Ready ACL; do not fall back to the deployment baseline or persist the workload |
| The same Subnet after a Ready NetworkACL is associated | Workload creation succeeds and uses that ACL as the effective policy |
| NetworkACL supplied inside an attachment | Reject; ACL association belongs to the NetworkACL resource |
| Complete attachment supplied | Preserve every supported supplied value |
| Explicit invalid supplied value | Reject; never repair with a default |

##### Expected results

- Catalog and Template precedence is resolved before tenant defaults.
- Direct tenant creates cannot persist a Pending dependency graph.
- All resolved references are Ready, same-scope, same-VirtualNetwork, and
  unique before persistence. A missing required policy resource or a non-Ready
  policy rejects explicit policy references and does not create a workload.

#### TC-R4-02: Typed local-reference wire format is enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- `subnet` supplied as `{ "name": "subnet-a" }`;
- `subnet` supplied as `{ "id": "subnet-123" }` without `name`;
- `security_groups` supplied as typed `{ "name": "sg-a" }` references;
- raw-string, ID-only, mismatched, duplicate, wrong-scope, and wrong-VN
  SecurityGroup references;
- a NetworkACL reference supplied inside a workload attachment;
- a NetworkACL association supplied without a Subnet;
- `id` and `name` supplied but resolving to different resources;
- typed Subnet references from a different tenant/project;
- typed NetworkACL Subnet associations from a different VirtualNetwork.

##### Expected results

- Local-reference objects require `name`; a name-only reference resolves and
  is canonicalized with the resolved `id`, while a supplied `id` is verified
  against the named resource before persistence.
- ID-only local references, raw strings, mismatched `id`/`name`, wrong
  reference types, and cross-scope references are rejected with a
  field-specific error.
- The same nested representation is used by Compute, Cluster, BMaaS, Catalog
  materialization, private ClusterOrder handoff, and direct CR validation.
- No invalid parent, child, worker request, or backend operation is created.

#### TC-R4-03: Service cardinality restrictions are enforced centrally

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Compute list with more than one entry;
- BM list with more than one entry;
- Compute or BM sole entry with explicit `primary: false`;
- Cluster repeated/multi-attachment representation;
- duplicate Subnet associations in a NetworkACL;
- a second NetworkACL association for the same Subnet;
- direct CR containing values rejected by the public API.

##### Expected results

- Rejection identifies the most specific field path.
- No template, worker, port-move, or backend operation is dispatched.

#### TC-R4-04: Catalog, Template, private, and direct default precedence match

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Matrix

For each workload path (direct API, Catalog Item materialization, Template
materialization, and the private CaaS-to-BMaaS worker request), use the same
tenant default VirtualNetwork and create the following Catalog/Template
policies:

| Catalog policy | Template value | Tenant value | Expected result |
|---|---|---|---|
| Network field locked to a valid value | Conflicting value | Conflicting value | Reject the create with the locked field path; do not repair or persist the workload |
| Network field editable with a valid default | None | Explicit valid value | Tenant value wins; validate the tenant value normally |
| Network field editable with a valid default | None | Omitted | Catalog default is used |
| No Catalog value | Valid Template default | Omitted | Template default is used |
| No Catalog or Template value | None | Omitted | Tenant default fills the missing Subnet/SecurityGroup/interface fields according to the service contract |
| Any policy level | Any | Explicit invalid, non-Ready, wrong-scope, or wrong-VirtualNetwork reference | Reject; never replace the explicit invalid value with a lower-precedence default |
| Shared Catalog policy | Any tenant-local reference | Any | Reject Catalog publication/materialization; shared policy cannot lock or default tenant-local networking references |

##### Expected results

- Resolution order is exactly Catalog policy, Template default, then tenant
  defaulting for missing supported fields only.
- Explicit values are never augmented, replaced, or repaired by a lower
  precedence source. Empty attachment messages/lists follow the service's
  documented missing-input behavior; an explicitly supplied list is not
  silently expanded beyond the supported cardinality.
- Every resolved reference passes the same Ready, scope, VirtualNetwork,
  complete-manager-contract, IPv4, and ACL validation as a direct API request.
- The private CaaS worker request preserves the resolved Cluster values when
  it materializes the BMaaS attachment; it does not reapply a different BM
  default or bypass validation.
- Catalog/template edits do not mutate existing workload specs or metadata.
- Unit tests cover the precedence resolver and each branch; integration tests
  cover public and private persistence paths; E2E tests cover one successful
  defaulted create and one rejection for each locked, invalid, and
  cross-scope branch.

### R5: ExternalIP and NATGateway lifecycle

#### TC-R5-01: Allocation, readiness, and capacity are atomic

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Provide multiple Ready IPv4 pools with different capacity.
2. Request auto external access.
3. Exhaust all pools and repeat the request.
4. Inject a failure after capacity reservation but before parent persistence.

##### Expected results

- Greatest-capacity pool is selected; equal-capacity selection is deterministic.
- Exhaustion returns an API error and persists no parent, child, or capacity
  reservation.
- Rollback releases capacity and leaves no orphan.
- Internal auto-provisioning children begin Pending and activate only after
  the target IP and ExternalIP are ready.

#### TC-R5-02: ExternalIPAttachment and NATGateway endpoint rules are enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- empty or multiply populated ExternalIPAttachment target oneof;
- Compute or BaremetalInstance target with `API` or `INGRESS` endpoint;
- Cluster target with `UNSPECIFIED` or an unsupported endpoint;
- target and endpoint combination that does not match the target type;
- direct attachment using a Pending, Failed, unallocated, or already
  consumed ExternalIP;
- direct attachment targeting a Pending, Failed, or non-Ready resource;
- caller-supplied, malformed, IPv6, out-of-subnet, or duplicate discovered
  endpoint status;
- NATGateway with a non-Ready VirtualNetwork or consumed ExternalIP;
- NATGateway with a Ready VirtualNetwork whose backend segment is absent or
  not ready.

##### Expected results

- Compute/BM attachments use `UNSPECIFIED` endpoint.
- Cluster attachments use exactly `API` or `INGRESS`.
- Target oneof has exactly one arm.
- NATGateway requires a Ready VN and unconsumed Allocated ExternalIP.
- SNAT is not dispatched until the referenced VN segment exists and is ready.
- Malformed manager SNAT/DNAT status never produces Ready.
- Every invalid target, endpoint, dependency, or discovered endpoint is
  rejected or fails closed before DNAT/SNAT dispatch and persistence.

#### TC-R5-03: Automatic external access is disabled by omission or false

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Steps

1. Create a VM, Cluster, and BaremetalInstance with the automatic external
   access field omitted.
2. Create equivalent resources with `auto_external_ip_attachment=false`.
3. Inspect ExternalIP/ExternalIPAttachment resources, pool capacity, and
   backend allocation calls.

##### Expected results

- Omission and explicit `false` both succeed when the ordinary network
  attachment is valid.
- No automatic ExternalIP or ExternalIPAttachment is created, no pool
  capacity is reserved, and no allocation or DNAT backend operation is
  dispatched.
- Changing the switch after creation is rejected by the shared immutability
  rule.

#### TC-R5-04: NATGateway performs successful SNAT

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated for every complete manager profile |

##### Steps

1. Configure a connected single-hub deployment whose selected manager is a
   complete implementation target for the NATGateway/SNAT contract.
2. Create a Ready VirtualNetwork and Subnet, a Ready IPv4 ExternalIPPool, an
   Allocated unconsumed ExternalIP, and a Ready NATGateway referencing them.
3. Start a VM, BM, or Cluster workload in the VirtualNetwork and send traffic
   to an allowed external destination.
4. Inspect the manager's egress flow and the destination's observed source
   address. Repeat with a workload in a VirtualNetwork without a NATGateway.

##### Expected results

- The workload's egress is source-NATted to the NATGateway ExternalIP, and the
  manager reports the SNAT rule Ready only after the VN segment and source IP
  prerequisites are Ready.
- The NAT rule is scoped to the referenced VirtualNetwork and does not affect
  another VirtualNetwork.
- A workload without a NATGateway does not claim a dedicated NAT identity; it
  follows the deployment's ordinary egress behavior or fails according to the
  deployment reachability contract.
- A manager operation that is temporarily unfinished may complete through the
  approved successful no-op AAP role; the tenant resource is not rejected for
  lack of a manager-specific support flag.

#### TC-R5-05: Pending children are restricted to OSAC automatic ExternalIP flow

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Hold a valid ExternalIPPool in `Pending` and attempt a direct ExternalIP
   create; then hold an ExternalIP in `Pending` and attempt a direct
   ExternalIPAttachment and NATGateway create.
2. Attempt a direct attachment to a Pending workload and a workload create that
   resolves a Pending Subnet, SecurityGroup, or effective NetworkACL.
3. Enable `auto_external_ip_attachment` for a VM, BM, and Cluster with a Ready
   pool and available capacity.
4. For default onboarding, hold the auto-created NAT ExternalIP in `Pending`
   and observe onboarding before making the IP `Allocated`.

##### Expected results

- Direct ExternalIP, attachment, NATGateway, and workload creates fail with
  field-specific `FailedPrecondition`; no dependent object, reservation, CR,
  or backend operation is created.
- The automatic workload path creates the parent plus its owned Pending
  ExternalIP/ExternalIPAttachment atomically after pool readiness and capacity
  validation. The attachment controller waits for both IP allocation and the
  workload endpoint before DNAT.
- Default onboarding does not create a Pending NATGateway. It waits for the
  default VN to be Ready and its owned ExternalIP to be Allocated, while the
  tenant remains non-Ready.
- Removing the auto-created marker or owner relationship makes the same
  Pending-child request fail; tenant-created resources cannot claim the
  exception.

### R6: Create/read/delete-only operations and dependency guards

#### TC-R6-01: Network-owned updates are rejected everywhere

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- API update, patch, replace, and field-mask mutation on every tenant-facing
  network resource: VirtualNetwork, Subnet, SecurityGroup, NetworkACL, ExternalIP,
  ExternalIPAttachment, and NATGateway;
- nested Subnet, NetworkACL, CIDR, rule, pool/allocation identity,
  interface, primary, endpoint, target, list-length/order, and
  auto-external mutations on ComputeInstance, Cluster, and
  BaremetalInstance;
- direct hub-CR mutation;
- status write attempting to mutate spec.

##### Expected results

- Every network-owned mutation is rejected.
- Controller may change only status, conditions, timestamps, discovered IPs,
  and finalizers.
- Delete/recreate is the only supported network-spec change path.

#### TC-R6-02: Leaf-first deletion and finalizers protect dependencies

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Unit cases

- Build each direct reverse-reference query with zero, one, and multiple
  blockers. Assert that the query returns all blockers up to the documented
  response limit plus the total count, rather than stopping at the first row.
- Include blockers whose deletion timestamp is set but that are not archived;
  they remain blockers until the API confirms they are absent.
- Verify the dependency-direction table:
  `ExternalIPAttachment -> target workload/ExternalIP`,
  `NATGateway -> ExternalIP/VirtualNetwork`,
  `SecurityGroup -> VirtualNetwork/workload attachments/Catalog Item/Template policy references`,
  `NetworkACL -> VirtualNetwork/Subnets`, workload attachment `-> Subnet`,
  `Subnet -> VirtualNetwork`, and `ExternalIP -> ExternalIPPool`.
- Verify a SecurityGroup owns its rules and workload references: deleting it
  reports each attached workload and governed Catalog Item/Template as a
  blocker and never detaches or changes them. Verify deleting its
  VirtualNetwork reports the SecurityGroup.
- Verify an ACL owns its association and rules: deleting the ACL does not
  delete or detach its Subnets or VirtualNetwork, while deleting a referenced
  Subnet or VirtualNetwork reports the ACL as a direct blocker.
- Verify owner classification requires both the canonical auto-created marker
  and an exact immutable owner kind/ID. A label-only match, wrong owner kind,
  wrong owner ID, missing owner, or mutable/reassigned owner is a tenant
  blocker, not an auto-cleanup candidate.
- Verify a delete decision is atomic: a rejected decision makes no deletion
  timestamp, finalizer change, backend call, child deletion, or capacity
  change.

##### Integration cases

- Create one workload with an auto-created ExternalIPAttachment and ExternalIP
  and one manually created attachment targeting the same workload. Verify the
  manual blocker rejects workload deletion without partially deleting the
  auto-created children.
- Delete an auto-created workload and assert the ordered sequence
  `ExternalIPAttachment -> ExternalIP -> workload`; the ExternalIPPool is
  never deleted and capacity is released only after the ExternalIP is gone.
- Inject transient and permanent cleanup failures. Verify the parent remains
  `Deleting`, its finalizer remains present, retries are idempotent, and no
  orphan is intentionally produced by removing the finalizer.
- Attempt deletion of an ExternalIP consumed by an ExternalIPAttachment and by
  a NATGateway; deletion is rejected with each direct blocker and no manager
  release operation is dispatched.
- Attempt deletion of an ExternalIPPool with one or more ExternalIPs; verify
  all direct ExternalIP blockers are reported. After the ExternalIPs are
  removed, the pool can be deleted.
- Attempt deletion of a Subnet referenced by workload attachments and its
  effective NetworkACL; verify all workload and ACL blockers are reported,
  including children already `Deleting` but not archived. SecurityGroups are
  validated through the workload attachment and are not direct Subnet
  blockers. After the blockers disappear, delete the Subnet and verify the
  ACL and workloads were not mutated.
- Attempt Subnet and VirtualNetwork deletion while a NetworkACL with multiple
  Subnet associations exists; verify the ACL appears in the blocker details.
  Delete the ACL and verify its own rules/backend state are cleaned up, but no
  Subnet or VirtualNetwork is deleted or detached. Then retry the Subnet and
  VirtualNetwork deletes and verify the removed ACL no longer appears as a
  blocker.
- Attempt deletion of a VirtualNetwork with Subnets, SecurityGroups, NetworkACLs, and
  NATGateways; verify all direct child blockers are reported. Remove them in
  leaf-first order, then delete the VirtualNetwork.
- Create a Catalog Item policy containing a governed reference to a networking
  resource and attempt to delete that resource. Verify the policy is reported
  as a blocker and no policy or network resource is partially changed. After
  the policy is removed, materialize a workload from the Catalog Item and
  verify the workload's direct resolved reference is independently enforced by
  the same dependency guard.
- Attempt provider deletion or replacement of a NetworkClass while deployment
  resources or manager integrations depend on its resolved manager targets.
  Verify the provider-only guard reports those blockers and performs no manager
  detach or partial manager-target change; after dependents are removed, the
  NetworkClass operation succeeds.
- Attempt deletion of a workload with a tenant-created ExternalIPAttachment;
  verify the error identifies attachment kind, ID/name, target relationship,
  and the required delete action. Deleting the attachment first must allow
  workload deletion without detaching any unrelated resource.
- Run concurrent reference creation and parent deletion. Verify the database
  transaction/locking contract admits at most one safe outcome: either the
  reference is rejected or the parent deletion is rejected; no dangling
  reference or deleted target is observable.

##### E2E cases

- Exercise the supported connected single-hub deployment through the public API
  and CLI. Create a VirtualNetwork, two Subnets, a SecurityGroup, and a NetworkACL associated
  with both Subnets, plus a NATGateway, an
  ExternalIP, and workload attachments. Attempt every non-leaf deletion and assert
  `FAILED_PRECONDITION` details identify every observed direct blocker.
- Delete the resources in the documented leaf-first order and verify each
  successful deletion does not implicitly delete or detach another
  tenant-managed resource.
- Repeat with an auto-external-access VM, BM, and Cluster. Verify each service
  performs only its allowlisted owned attachment/IP cleanup and retains its
  finalizer on injected failure.

##### Expected results

- Every rejected delete leaves the target, blockers, finalizers, backend
  state, and capacity unchanged.
- Default NATGateway deletion removes its OSAC-owned automatic ExternalIP only
  after NATGateway backend cleanup succeeds; a VirtualNetwork delete never
  directly deletes either resource.
- Every error includes resource kind, ID/name, relationship field, required
  action, and machine-readable status details; the CLI and UI can render the
  same blocker information.
- A resource is physically/semantically absent only after its own finalizer
  completes; a deletion timestamp alone never makes it disappear from parent
  blocker checks.
- No tenant-managed resource is implicitly deleted, detached, retargeted, or
  changed to `Pending`.
- Auto-cleanup is limited to the exact OSAC-owned workload
  ExternalIPAttachment/ExternalIP pair or the exact OSAC-owned default-NAT
  ExternalIP after NATGateway backend cleanup; no pool or unrelated resource
  is cascaded.

### R7: Direct CR bypass, state machine, and recovery

#### TC-R7-01: Admission and controllers enforce the same contract as the API

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Cases

- Submit a new NATGateway create, including a direct hub-CR create, while the
  referenced VirtualNetwork is Pending/Failed/Deleting or the ExternalIP is
  not Allocated/available.
- Admit a valid NATGateway, then hold its own SNAT manager operation Pending
  and separately simulate a temporary dependency-readiness regression before
  the backend dispatch completes.
- Make an admitted NATGateway dependency terminally Failed or Deleting and
  verify the controller's terminal failure behavior.

##### Expected results

- Direct CRs with invalid cardinality, IPv6, bad references, unsupported
  operations, false Ready status, or non-Ready dependencies are rejected or
  fail closed before the dependent CR is persisted or dispatched.
- Every persisted networking resource, including VirtualNetwork, Subnet,
  NetworkACL, ExternalIPPool, ExternalIP, ExternalIPAttachment, and
  NATGateway, carries `status.hub` equal to the single active deployment hub.
- A missing or mismatched `status.hub` cannot be used to report a resource
  Ready or dispatch a backend operation.
- Resource-specific terminal transitions are enforced only through the
  documented reconciliation path: ExternalIP uses `Pending -> Allocated` or
  `Pending -> Failed`, while resources with Ready semantics use
  `Pending -> Ready` or `Pending -> Failed`.
- Attempts to force `Ready -> Pending`, `Allocated -> Pending`, or
  `Failed -> Ready` through a caller or an
  unauthorized controller path are rejected or ignored, and do not dispatch
  a backend operation.
- A new NATGateway with a non-Ready VirtualNetwork or non-Allocated ExternalIP
  returns `FailedPrecondition` before persistence; no NATGateway CR, database
  object, reservation, or SNAT job is created.
- Already-admitted resources may requeue for their own manager operation or an
  allowlisted automatic ExternalIP/ExternalIPAttachment child; an ordinary
  create with a Pending dependency is rejected before persistence.
- An already-admitted NATGateway may requeue while its own SNAT operation or a
  temporary readiness regression is recoverable. A terminally Failed or
  Deleting dependency produces the documented failure and no SNAT dispatch.
- Restarting controllers does not duplicate jobs, allocations, rules,
  segments, or finalizers.

### R8: Cross-service interoperability

#### TC-R8-01: VMaaS, CaaS, and BMaaS consume a shared Ready Subnet

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Data-plane scenarios

Run the matrix in a connected single-hub deployment for every supported
manager topology that can host the workload pair. Use separate test resources
for each row and verify both the positive packet flow and the negative flow
where specified:

| Source and destination | Network placement | Expected result |
|---|---|---|
| VM → BM | Same Ready Subnet and same VirtualNetwork | IPv4 L2/broadcast-domain communication succeeds |
| BM → Cluster worker | Same Ready Subnet and same VirtualNetwork | IPv4 communication succeeds through the shared subnet policy |
| VM → Cluster endpoint/worker | Different Ready Subnets in the same VirtualNetwork | IPv4 L3 routing succeeds when the same-VN route is Ready |
| VM → BM | Different VirtualNetworks | Communication is isolated and fails unless an explicitly supported external path is configured |
| CaaS worker → VM | Same or different supported Subnet according to the service topology | The result matches the selected Subnet/VN policy and no workload receives another workload's attachment or policy |

##### Expected results

- VMaaS uses one virtual interface.
- CaaS uses one cluster attachment and BM worker enrichment.
- BMaaS uses one physical tenant attachment.
- All services preserve shared IPv4, same-VN, readiness, SecurityGroup,
  NetworkACL, and
  create/read/delete-only rules.
- Multiple hosting clusters receive the required overlay for a shared Subnet
  when the selected topology includes the K8s manager target.
- Workloads in different VNs remain isolated.
- The integration suite verifies shared Subnet L2 behavior, same-VN
  cross-Subnet L3 routing, and cross-VN isolation with packet captures or
  equivalent manager flow observations; it does not treat resource readiness
  alone as proof of connectivity.
- Unit tests cover the placement/policy decision for each matrix row,
  integration tests cover manager dispatch and route/policy state, and E2E
  tests exercise VM/BM/Cluster workload pairs where the selected deployment
  topology supports them.

### R9: Explicitly unsupported surface

#### TC-R9-01: Unsupported shared behavior is rejected or excluded

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- IPv6 or dual-stack;
- multi-CIDR pool;
- multi-interface VM/BM or multi-NIC tenant attachment;
- VN peering/cross-VN routing;
- multi-hub or air-gapped deployment;
- tenant-selected provider implementation or arbitrary IP;
- a tenant-selected provider implementation or dispatch target;
- unsafe parent deletion;
- a configurable default ACL policy override.

##### Expected results

- Unsupported user-visible requests fail with the documented error.
- Provider-only or future behavior is not exposed as a manager subset and does
  not dispatch a backend operation.

### R10: CLI contract and validation parity

#### TC-R10-01: Shared resource CLI parsing and typed references

**Unit:** Parse VirtualNetwork, Subnet, SecurityGroup, NetworkACL, ExternalIPPool,
ExternalIP, ExternalIPAttachment, and NATGateway commands. Verify canonical
IPv4 CIDR parsing, `--cidrs` exactly-one behavior, enum values, repeated
`--rule` parsing, typed local/full reference construction, and rejection of
unknown flags or malformed key/value pairs. For the provider-only
`osac admin create networkclass` command, verify that at least one of
`--fabric-manager` and `--k8s-manager` is required, both default CIDRs are
required and canonical/contained, using the exact
  `--virtual-network-cidr` and `--ipv4-subnet-cidr` flags, and `--name` is
  required. Test omission of each required NetworkClass flag, malformed values,
  and a subnet outside the VirtualNetwork. Verify each of fabric-only, k8s-only,
  and combined-manager configurations resolves the documented per-resource
  dispatch plan and target annotations. Verify that neither manager is rejected,
  `--metallb-vip-prefix-length` is required for the CaaS/MetalLB path, and
  dispatch metadata is derived rather than caller-set. Verify tenant
callers cannot invoke this command. Explicitly parse the supported shared
resource command forms and required arguments:

- `virtualnetwork`: required `--name` and canonical `--cidr`;
- `subnet`: required `--name`, `--virtual-network`, and contained `--cidr`;
- `security-group`: required `--name`, `--virtual-network`, and one or more
  allow-only `--rule` values; no action key is accepted;
- `network-acl`: required `--name`, `--virtual-network`, one or more
  `--subnet` references, and at least one `--rule`;
- `externalippool`: required `--name`, exactly one `--cidrs`, and
  `--ip-family ipv4`;
- `externalip`: required `--name` and provider-visible `--pool`;
- `externalipattachment`: required `--name`, `--externalip`, and exactly one
  target flag (`--compute-instance`, `--baremetal-instance`, or `--cluster`);
  `--target-endpoint` is required only for Cluster; and
- `natgateway`: required `--name`, `--virtual-network`, and `--externalip`.

Verify required arguments, wrong target combinations, and unsupported
resource-specific flags are rejected before an API call.

For ExternalIPPool, explicitly test exactly one value for the plural
`--cidrs` option: a single canonical IPv4 CIDR succeeds; repeating the option,
providing a comma-separated/multiple value, omitting it, using an IPv6 or
dual-stack CIDR, using host bits, or passing `--ip-family` other than the
required `ipv4` fails before persistence. Verify separate pools are used for
separate CIDRs rather than encoding multiple CIDRs in one pool.

For SecurityGroup, enumerate the complete allow-only rule grammar:
`ingress`/`egress`, and `tcp`/`udp`/`icmp`/`any` are the only enum values;
TCP/UDP may omit the port or specify one from 1 through 65535, ICMP/any must
omit ports, and ingress requires exactly `source-cidr` while egress requires
exactly `destination-cidr`. Test a supplied action key, deny rule, invalid
direction, protocol, port, CIDR, duplicate normalized rule, and empty tenant
group; the system-created default group may be empty and means deny. Test
typed `security-groups` attachment references, duplicates, wrong scope, wrong
VN, and non-Ready dependencies.

For NetworkACL, enumerate the complete rule grammar: `allow`/`deny`,
`ingress`/`egress`, and `tcp`/`udp`/`icmp`/`any` are the only enum values;
TCP/UDP may omit the port or specify one from 1 through 65535, ICMP/any must
omit ports, and ingress requires exactly `source-cidr` while egress requires exactly
`destination-cidr`. Test missing action, direction, protocol, invalid port,
and required direction-specific CIDR, as well as both source and destination
being supplied. Verify canonical IPv4 CIDRs only, no host bits, duplicate
normalized rules and conflicting equal-specificity rules are rejected, an
  ordinary empty or unassociated NetworkACL is rejected, and the tenant
  default NetworkACL contains explicit deny-all ingress and allow-all egress
  rules. Explicitly test the named
unsupported `--ipv6`, `--dual-stack`, `--hub`, `--air-gapped`, any deployment
  default-policy override flag, and any manager/dispatch-strategy flag.

**Integration:** Submit parsed CLI requests through public REST/gRPC and
private handlers. Verify field paths and `InvalidArgument`,
`FailedPrecondition`, `PermissionDenied`, or visibility-safe `NotFound`
behavior matches direct API requests. Verify no rejected request persists a
resource or invokes a manager. Verify the NetworkClass provider command is
provider-scoped, requires `--name`, `--virtual-network-cidr`, and
`--ipv4-subnet-cidr`, and the CLI and direct API enforce the same conditional
MetalLB/default validation. Verify each shared command's field-specific
validation, readiness, scope, and dependency error without persistence.

**E2E:** In a connected single-hub deployment, execute the supported CLI
resource workflow as a provider admin and tenant user: create/read/list a
NetworkClass and ExternalIPPool as the provider, then create/read/list/delete
a VirtualNetwork, Subnet, SecurityGroup, NetworkACL, ExternalIP, ExternalIPAttachment,
and a NATGateway as the tenant. Use a
Ready dependency at every step and verify the CLI output contains the
resolved typed-reference names.
Exercise ExternalIPAttachment once for each target type, with Cluster API and
ingress endpoints, and verify the wrong endpoint/target combinations fail.
Verify deletion guards for a referenced Subnet, SecurityGroup, NetworkACL, ExternalIP,
ExternalIPPool, VirtualNetwork, and NetworkClass. After all dependents are
deleted, verify provider read/list/delete succeeds for the provider-owned
resources. Before deleting them, attempt provider update, patch, and replace
operations for NetworkClass manager/default fields and ExternalIPPool family,
CIDR, capacity, and lifecycle fields; verify each is rejected, with the
stored spec and backend unchanged. Exercise any separately supported
metadata-only update and verify it cannot alter the network spec. Verify
tenant attempts to create/update/patch/delete NetworkClass or ExternalIPPool
  fail before persistence. Repeat the provider/resource setup for one-manager
  and two-manager deployments. Verify every resource and policy operation is
  dispatched to every selected manager, and that a development no-op still
  uses the normal target/job path. Verify the tenant default ACL is always
  present and distinct from the hard-coded deployment `permit` baseline.

#### TC-R10-02: Workload attachment CLI mapping

**Unit:** Verify one optional `--network-attachment` maps to VM/BM repeated
`network_attachments` or Cluster singular `network_attachment`; repeated
attachment options, the deprecated plural `--network-attachments` option,
unsupported keys, `interface` on VM/Cluster, and `primary` on any workload
are rejected by the CLI (the API-compatibility `primary` field is implicit
and the CLI does not emit it). Verify that `network-acls=<name>` is rejected
inside a workload attachment and that ACL association is performed through
the NetworkACL resource's Subnet references. Verify that
`security-groups=<name>[,...]` maps to typed local SecurityGroup references,
preserves explicit lists, defaults only when omitted, and rejects duplicates,
unknown groups, wrong scope/VN, and non-Ready groups.

**Integration:** Verify omitted and explicit-Subnet/SecurityGroup CLI attachments receive
the same defaulting and readiness validation as direct API requests. Verify
VM/BM use their resource-specific message types and Cluster uses
`ClusterNetworkAttachment`; verify the effective ACL is obtained from the
selected Subnet, and verify combined packet policy requires both layers.

**E2E:** Create one VM, one BM, and one Cluster using explicit and defaulted
CLI attachments, inspect the resolved fields, and verify delete succeeds.
Attempt a second attachment, an invalid interface, `primary=false`, IPv6,
multi-CIDR, the deprecated plural `--network-attachments` option, and a
non-Ready reference; verify the expected error and no partial resource or
backend side effect.

#### TC-R10-03: CLI operation and external-access restrictions

**Integration:** Verify CLI create/get/list/delete succeeds, while update,
patch, replace, network-field mutation, and `auto_external_ip_attachment`
mutation are rejected. Verify `--external-ip-attachment` maps to the boolean
for all three workload types. Run both the present and omitted forms for each
type: present sets the create-time switch and starts the documented automatic
flow; omitted sets it false, creates no automatic ExternalIP/attachment, and
does not consume pool capacity. Verify explicit ExternalIPAttachment requires
exactly one target and the correct Cluster endpoint flags.

**E2E:** Verify VM/BM external access creates one automatic ExternalIP and
Cluster creates API and ingress external access. Repeat all three workload
types with the flag omitted and verify no automatic resources or capacity
consumption. Verify endpoint misuse, unallocated IPs, non-Ready targets,
  unfinished backend operations and cross-scope references fail without
orphaned state.

## Graduation gate

- Every normative shared validation rule maps to a unit or integration test.
- Every supported user workflow maps to an E2E test.
- Every user-visible unsupported workflow maps to an E2E rejection test.
- Negative tests verify no partial persistence or backend side effect.
- Concurrent create/delete, controller restart, manager failure, and cleanup
  tests pass.
