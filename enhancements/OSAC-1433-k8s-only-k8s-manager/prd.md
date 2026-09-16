---
title: K8s-only Networking Manager
authors:
  - dmanor@redhat.com
creation-date: 2026-09-15
last-updated: 2026-09-16
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking: /enhancements/OSAC-1433-unified-networking
  - Default Networking: /enhancements/OSAC-1433-default-networking
  - VMaaS Networking: /enhancements/OSAC-1435-vmaas-networking
  - CaaS Networking: /enhancements/OSAC-1436-caas-networking
  - BMaaS Networking: /enhancements/OSAC-1437-bmaas-networking
  - CUDN EVPN K8s Manager: /enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking
replaces:
  - N/A
superseded-by:
  - N/A
---

# K8s-only Networking Manager

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 (manager split) |
| Date        | 2026-09-16 |

## 1. Problem Statement

The [Unified Networking requirements](../OSAC-1433-unified-networking/prd.md)
define a provider-configured K8s manager as one possible implementation target,
but the current K8s-only profile is mixed into the shared design. That makes it
difficult for operators, service owners, and agents to distinguish the common
networking contract from the behavior of a deployment that has no Fabric
Manager.

The K8s-only deployment needs its own current-state proposal. It must state
which manager registration is installed, how the dispatcher reaches the
complete K8s implementation, and how all workload services use the shared
contract. An unfinished backend operation may be a successful internal AAP
no-op during development; it must not become a tenant-visible unsupported
resource or service path.

## 2. Goals and Non-Goals

### 2.1 Goals

- Define the supported connected, single-hub, IPv4-only K8s-only deployment
  profile with one provider-registered K8s manager and no Fabric Manager.
- Make the manager's complete resource and workload contract and concrete
  implementation entrypoints explicit.
- Define direct K8s dispatch, AAP routing metadata, readiness, failure, and
  deletion behavior for the supported shared resources.
- Define how VMaaS, BMaaS, and CaaS use the K8s-only profile.
- Provide an executable unit, integration, and end-to-end test plan for every
  K8s-only acceptance and rejection path.

### 2.2 Non-Goals

- Redefining shared resource fields, formats, defaults, dependency guards,
  deletion guards, or create/read/delete-only semantics; those are owned by
  [Unified Networking](../OSAC-1433-unified-networking/design.md).
- Defining combined Fabric-plus-K8s dispatch; the shared design owns that
  topology.
- Defining the `cudn_evpn` manager or its east-west/fabric-bridging behavior;
  that manager has its own proposal.
- Designing future backend improvements beyond the complete shared contract.

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** A provider can register and select one K8s-only manager for a
  connected deployment with exactly one active hub and IPv4 networking. [User]
- **FR-2:** The K8s-only manager registration contains only the manager
  identity/type and deployment-wide IPv4 contract. It has no per-resource,
  policy, scope, or service subset declaration. [User]
- **FR-3:** The K8s-only profile is an implementation target for every
  canonical networking resource through concrete entrypoints: `cudn_net` for
  VirtualNetwork/Subnet, policy adapters for SecurityGroup/NetworkACL,
  `metallb_l2` for the ExternalIP family, and `nat_gateway` for NATGateway.
  [User]
- **FR-4:** Every resource operation is dispatched directly to the K8s
  manager without a Fabric fallback. If an operation is still under
  development, its AAP role may complete successfully as a no-op. [User]
- **FR-5:** VMaaS, BMaaS, and CaaS all use the K8s-only manager through the
  shared workload contracts and service-specific attachment validation. [User]
- **FR-6:** Provider-created default networking uses the same complete-profile
  dispatch and readiness rules as tenant-created resources. [User]
- **FR-7:** The K8s-only profile preserves the shared IPv4, connected,
  single-hub, single-interface, and create/read/delete-only constraints. [User]
- **FR-9:** Manager registration, resource dispatch, workload eligibility, and
  direct-CR admission fail closed and expose field-specific errors without
  partial persistence or backend side effects. [User]

### 3.2 Non-Functional Requirements

- **NFR-1:** The K8s-only profile is deterministic: a resource has one K8s
  target, one operation-specific AAP job, and no hidden secondary target.
  [User]
- **NFR-2:** The profile is idempotent across API retries, controller retries,
  and manager failures; retries do not create duplicate network objects,
  allocations, or jobs. [User]
- **NFR-3:** Tenant input cannot select a manager, provide implementation
  annotations, or alter the provider's complete manager profile. [User]
- **NFR-4:** The profile uses the shared create/read/delete-only contract and
  strict Ready-dependency admission defined by Unified Networking. [User]

## 4. Acceptance Criteria

- [ ] **AC-1:** A connected single-hub NetworkClass with only the K8s-only manager is
  accepted and reports `addressFamily: ipv4`.
- [ ] **AC-2:** A zero-hub, multi-hub, air-gapped, IPv6, or dual-stack deployment is
  rejected before K8s-only networking resources are provisioned.
- [ ] **AC-3:** The shipped manager registration contains no per-resource,
  policy, scope, or service subset declaration and selects the complete contract.
- [ ] **AC-4:** Every canonical resource create dispatches to the K8s target and
  uses the documented entrypoint; the resource becomes Ready only after that
  target succeeds or the approved development no-op completes.
- [ ] **AC-5:** VMaaS, BMaaS, and CaaS workload operations dispatch through the
  K8s target and enforce their shared service-specific validation.
- [ ] **AC-6:** Default networking uses the same complete-profile and readiness
  rules as tenant-created resources.
- [ ] **AC-8:** Unit, integration, and E2E tests cover every supported and rejected
  manager, resource, workload, dependency, operation, and failure path in the
  companion [test plan](testplan.md).

## 5. Dependencies

- Unified Networking is the source of truth for resource schemas, field
  formats, reference typing, defaults, complete manager/profile resolution, dependency
  readiness, deletion order, and immutable network fields.
- The selected K8s implementation is validated as a complete OSAC lifecycle
  target for every canonical resource and workload service.
- VMaaS, CaaS, and BMaaS retain ownership of workload-specific placement and
  attachment validation.
- The default-networking flow consumes the resolved complete manager profile
  before creating provider-owned defaults.

## 6. Risks

### 6.1 Incomplete K8s implementation

- **Owner:** K8s networking manager maintainers
- **Mitigation:** Registration validation and E2E tests require the complete
  create/read/delete, readiness, enforcement/allocation, and deletion contract.
  During development, an unfinished operation uses a successful internal AAP
  no-op rather than a partial public API.

### 6.2 Service accidentally treats shared-resource support as workload support

- **Owner:** VMaaS, CaaS, BMaaS maintainers
- **Mitigation:** Workload admission applies the service-specific validation
  for every service; all workload operations are dispatched through the
  complete K8s-only manager profile.
