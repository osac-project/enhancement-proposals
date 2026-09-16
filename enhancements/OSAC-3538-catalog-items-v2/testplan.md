# Testplan — OSAC-3538 Catalog Items v2 Networking Governance

Networking governance inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
these tests cover connected deployments only, with air-gapped and disconnected
networking deployments treated as unsupported.

## Overview

- **Feature:** OSAC-3538 — Catalog Items v2 typed provisioning governance
- **Source design:** [design.md](design.md)
- **Networking scope:** Typed policies for VMaaS, CaaS, and BMaaS networking
  fields, resolution order, reference scope/readiness, cardinality, direct vs
  Catalog parity, and metadata immutability.
- **Owning test plans:** Final resource validation remains owned by the
  [Unified Networking](../OSAC-1433-unified-networking/testplan.md),
  [VMaaS](../OSAC-1435-vmaas-networking/testplan.md),
  [CaaS](../OSAC-1436-caas-networking/testplan.md), and
  [BMaaS](../OSAC-1437-bmaas-networking/testplan.md) plans.

## Execution strategy

- **Unit:** typed policy parsing, presence/empty semantics, precedence,
  reference scope, authoring validation, and resource-specific delegation.
- **Integration:** real PostgreSQL, OPA/protovalidate, public/private
  handlers, Catalog resolution, resource handlers, and CR materialization.
- **E2E:** Catalog-created VM, Cluster, and BM resources through the complete
  supported stack, compared with direct creates.

## Test cases

### R1: Typed network policy authoring

#### TC-R1-01: Valid network policies are accepted

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Cases

- Compute zero-or-one attachment policy;
- Cluster singular attachment policy;
- BM zero-or-one attachment policy;
- locked, editable, and editable-with-default policies;
- valid typed Subnet references visible in the item's scope;
- valid typed `security_groups` references, including an explicitly empty list
  that invokes the tenant default during resource creation;
- compatible `primary: true` or omitted primary;
- `auto_external_ip_attachment` boolean policy.

##### Expected results

- Catalog Item stores typed policy values and preserves normal resource field
  semantics.
- Policy authoring validates the underlying network value before publication.
- Catalog does not accept a generic untyped value as a networking substitute.

#### TC-R1-02: Invalid network policy authoring is rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- more than one Compute/BM attachment;
- empty locked or editable-default Compute/BM attachment-list policy;
- explicit false primary;
- repeated Cluster attachment;
- malformed IPv4/CIDR/reference;
- malformed, duplicate, wrong-scope, or non-Ready SecurityGroup references;
- wrong-type or invisible reference;
- Cluster node-set `baremetal_instance_type` or CaaS physical
  `fabric_interface` governed by Catalog;
- shared Catalog Item locking/defaulting tenant-local reference;
- arbitrary ExternalIP, pool, NATGateway, or target IP policy.

##### Expected results

- Catalog Item create/update returns the documented validation error.
- Empty locked or editable-default Compute/BM attachment-list policies are
  rejected; an empty tenant-supplied list remains distinct and follows the
  documented defaulting/fallthrough behavior.
- No invalid policy is published or used for resource creation.

### R2: Presence, empty values, and precedence

#### TC-R2-01: Presence and empty semantics are preserved

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

##### Cases

- omitted optional field;
- explicit empty repeated attachment list;
- explicit empty singular Cluster attachment message;
- partial singular Cluster attachment with only the Subnet field;
- partial attachments with only `security_groups` or with both Subnet and
  SecurityGroup fields;
- explicit empty string;
- explicit zero;
- explicit false;
- non-empty attachment list.

##### Expected results

- Catalog semantics distinguish omitted from explicit scalar presence.
- An empty repeated network list supplied as tenant resource input follows the
  documented fallthrough behavior; it is not equivalent to an empty
  Catalog-authored locked/default policy, which is rejected.
- An empty Catalog Cluster attachment falls through as unset, while a partial
  Cluster attachment is completed field-by-field without replacing the
  supplied reference.
- Explicit false primary is not rewritten to true.

#### TC-R2-02: Resolution order is deterministic

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Expected results

- Tenant value wins for editable policy.
- Catalog default wins when tenant supplies nothing.
- Template default is considered next.
- Tenant default networking fills only still-missing fields.
- Tenant default SecurityGroup fills only a missing or empty SecurityGroup
  field and only when the resolved Subnet belongs to the tenant default
  VirtualNetwork; explicit SecurityGroup references are preserved. A
  non-default-VirtualNetwork Subnet with no compatible explicit group is
  rejected.
- Requiredness and final VM/CaaS/BM validation run after resolution.
- Invalid explicit Catalog/Template values are rejected, not repaired.

### R3: Direct and Catalog resource parity

#### TC-R3-01: Compute, Cluster, and BM final specs match direct creation

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Steps

1. Create equivalent resources directly and through Catalog Items.
2. Use locked, editable, empty, partial, and complete network policies.
3. Include CaaS API/Ingress endpoint binding cases and an automatic-ExternalIP
   create with an exhausted pool.
4. Include a BM policy with a valid interface and a policy with an unknown or
   lifecycle interface against the effective BareMetalInstanceType.
5. Include default and explicit SecurityGroup lists and verify that the
   effective NetworkACL is inherited from the selected Subnet rather than
   materialized as an attachment field.
6. Repeat the defaulting comparison with a Template-provided typed
   SecurityGroup reference and verify Catalog/Template precedence and the same
   final readiness and scope checks.
7. Exercise a partial policy with a custom Subnet in a non-default
   VirtualNetwork and no SecurityGroup, and a custom Subnet in an
   ACL-capable deployment without a Ready effective NetworkACL.
8. Compare resolved resource specs and validation outcomes.

##### Expected results

- Compute remains zero-or-one with primary semantics.
- Cluster remains singular; the authoritative Template retains ownership of
  node-set keys and `baremetal_instance_type`, while only permitted node-set
  sizes may vary, and interfaces are derived from those unchanged types.
- BM remains zero-or-one with interface/lifecycle validation.
- BM interface values are validated against the effective
  BareMetalInstanceType; unknown and lifecycle interfaces fail without
  materializing a resource.
- The owning service's readiness, same-VN, and immutability checks are not
  bypassed by Catalog materialization.
- A partial policy with a non-default-VirtualNetwork Subnet and no compatible
  SecurityGroup fails with `InvalidArgument`; the tenant default-VN group is
  not injected and no parent or auto-created child is persisted.
- A selected Subnet without a Ready effective NetworkACL in an ACL-capable
  deployment fails with `FailedPrecondition`; the deployment baseline is not
  used as a fallback and no parent or auto-created child is persisted.
- SecurityGroup references are materialized as typed local references and are
  validated for readiness, scope, uniqueness, and same-VirtualNetwork
  relationship exactly as direct creates.
- CaaS endpoint bindings remain limited to the matching `API`/`INGRESS`
  ExternalIP attachments; automatic ExternalIP capacity failures leave no
  parent or child resource.

#### TC-R3-02: Catalog updates affect only future resources

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Expected results

- Existing VM/Cluster/BM network specs are unchanged after Catalog update.
- A later create uses the updated policy.
- Catalog Item deletion does not mutate already-created resources.
- Day-2 networking update through Catalog is rejected.

### R4: Reference scope and readiness

#### TC-R4-01: Reference visibility and readiness are enforced

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- tenant-owned item references its own Ready Subnet;
- tenant-owned item references its own Ready SecurityGroup;
- shared item uses editable local reference supplied by tenant;
- shared item attempts locked/default local reference;
- referenced object missing, wrong type, cross-tenant, cross-project,
  Pending, Failed, or wrong VirtualNetwork.
- partial attachment with a custom non-default-VirtualNetwork Subnet and
  missing SecurityGroup;
- custom Subnet in an ACL-capable deployment without a Ready effective
  NetworkACL.

##### Expected results

- Valid references are materialized into the resource.
- Invalid/invisible references are rejected without resource persistence.
- The non-default-VirtualNetwork partial attachment is rejected with
  `InvalidArgument`, and the ACL-less selected Subnet is rejected with
  `FailedPrecondition`; neither path creates a parent or auto-created child.
- Error does not expose another tenant's object identity.

### R5: Metadata and unrelated fields

#### TC-R5-01: Networking does not mutate Catalog metadata

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Expected results

- `metadata.display_name`, `metadata.description`, publication state, ownership,
  metadata, and unrelated Template parameters remain unchanged during
  networking resolution.
- Only an explicit Catalog update changes Catalog metadata.
- Network reconciliation never uses Catalog metadata as an alternate spec
  mutation path.

### R6: Unsupported governance surface

#### TC-R6-01: Catalog does not expose unsupported networking controls

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | high | automated where user-visible |

##### Cases

- day-2 network updates;
- VM/BM multi-interface;
- CaaS per-node tenant interfaces;
- Cluster node-set hardware references or node-set keys supplied by a Catalog
  Item instead of the authoritative ClusterTemplate;
- tenant-selected manager/implementation strategy;
- arbitrary IP/pool/NAT allocation strategy;
- shared-item local reference lock/default;
- metadata mutation through a network policy;
- policy that makes a non-Ready resource usable.

##### Expected results

- Unsupported governance is rejected or delegated to the owning service's
  validation boundary.
- No resource, IP, port, or backend networking side effect is created.

## Graduation gate

- Every in-scope networking policy shape has direct-versus-Catalog parity.
- Every unsupported policy shape has authoring, materialization, or E2E
  negative coverage at the appropriate boundary.
- Catalog metadata remains unchanged during all networking tests.
