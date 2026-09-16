# Netris Fabric Manager Integration

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2434 |
| Date        | 2026-09-16 |

## 1. Problem Statement

OSAC needs a provider-configurable fabric manager so networking resources and
workloads can use an existing Netris deployment without manual networking
edits after OSAC installation. Without this integration, a provider cannot
select Netris as the OSAC Fabric Manager, supply the connection and tenancy
information required by Netris, or obtain a deployment whose networking
resources and VMaaS, BMaaS, and CaaS workflows are consistently handled by the
same manager. [Jira: OSAC-2434]

The feature configures an existing Netris deployment; it does not install or
provision Netris. [Jira: OSAC-2434]

## 2. Goals and Non-Goals

### 2.1 Goals

- Allow a provider to select Netris as the Fabric Manager during OSAC
  deployment and provide the Netris connection, credentials, site/tenant, and
  networking-default inputs needed for the deployment. [Jira: OSAC-2434]
- Produce a deployment in which Netris is the complete Fabric Manager for the
  shared networking resources and the VMaaS, BMaaS, and CaaS networking flows;
  tenants do not select manager implementations or partial manager features.
  [Jira: OSAC-2434] [User]
- Make a correctly configured deployment usable without manual post-install
  networking edits. [Jira: OSAC-2434]
- Expose provider configuration failures and Netris-backed resource failures
  through the normal OSAC readiness, status, and error behavior. [User]

### 2.2 Non-Goals

- Installing or provisioning the Netris controller, SoftGate, switches, or
  other Netris infrastructure. [Jira: OSAC-2434]
- Selecting or implementing a Kubernetes manager such as CUDN or EVPN. [Jira: OSAC-2434]
- Changing the shared networking resource model, field contracts, validation
  rules, or tenant operation contract defined by Unified Networking. [User]
- Adding east-west FabricDomain behavior or CUDN-EVPN feature improvements;
  those remain governed by their separate proposals. [User]

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** A provider can select Netris as the Fabric Manager for an OSAC
  deployment. The selection is provider-owned and is not configurable by a
  tenant through a networking resource, workload request, CLI command, or UI
  form. [Jira: OSAC-2434] [User]
- **FR-2:** A provider can supply the Netris controller endpoint, credentials,
  site identifier, tenant identifier, agent server-name label, and networking
  defaults required by the deployment workflow. [Jira: OSAC-2434]
- **FR-3:** The deployment accepts Netris only as a complete Fabric Manager
  contract for all shared networking resources and all three workload services:
  VMaaS, BMaaS, and CaaS. The provider cannot register Netris as supporting
  only selected resources, policies, workload scopes, or services. [User]
- **FR-4:** The deployment uses the shared [Unified Networking deployment
  support boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
  IPv4 only, connected deployments only, one active hub, and no tenant-visible
  network-owned update or patch operations. Tenant networking operations are
  limited to read, create, and delete, subject to the shared dependency and
  readiness validations. [User]
- **FR-5:** When the Netris configuration is valid and the provider-owned
  NetworkClass is Ready, tenants can use the shared VirtualNetwork, Subnet,
  SecurityGroup, NetworkACL, ExternalIPPool, ExternalIP,
  ExternalIPAttachment, and NATGateway APIs through the normal OSAC API, CLI,
  and supported UI flows. [User]
- **FR-6:** When the Netris configuration is valid and the provider-owned
  NetworkClass is Ready, VMaaS, BMaaS, and CaaS workload creation can resolve
  and use the shared networking resources according to each service's current
  single-subnet/single-interface contract. [User]
- **FR-7:** The provider-owned deployment configuration creates the Netris
  manager registration, NetworkClass selection, networking defaults, and
  credentials handoff required for the normal OSAC networking lifecycle. The
  deployment must not require manual edits to those objects after installation.
  [Jira: OSAC-2434]
- **FR-8:** A missing, malformed, unauthorized, unreachable, or incomplete
  Netris configuration prevents the provider-owned NetworkClass from becoming
  Ready and prevents dependent tenant resources or workloads from being
  accepted. The error identifies the failed configuration or readiness
  condition without exposing credentials. [User]
- **FR-9:** Netris-backed creation and deletion obey the shared strict
  dependency contract: user-created resources cannot be created while their
  referenced resources are not Ready, and a resource cannot be deleted while
  another resource references it. Only OSAC-owned automatic ExternalIP and
  ExternalIPAttachment children may be created Pending and cleaned up through
  their owner workflow. [User]
- **FR-10:** Netris-backed operations are idempotent and report success, pending
  reconciliation, or failure through the normal OSAC resource status and error
  surfaces. A failed or unavailable Netris operation does not create a
  tenant-visible partial manager path or silently fall back to another manager.
  [User]

### 3.2 Non-Functional Requirements

- **NFR-1:** Netris credentials are stored and transferred through the
  provider-owned secret mechanism and are never returned in tenant API, CLI,
  UI, resource status, event, or error payloads. [Jira: OSAC-2434] [User]
- **NFR-2:** Provider configuration validation is deterministic and must finish
  before NetworkClass readiness is reported. A deployment must not report a
  usable Netris manager while required configuration is absent or invalid.
  [User]
- **NFR-3:** The integration preserves the shared tenant isolation and
  dependency guarantees across all Netris-backed networking resources and
  workloads. [User]
- **NFR-4:** The integration is testable at unit, integration, and end-to-end
  levels, including successful configuration, every supported resource and
  workload flow, readiness failures, dependency failures, invalid provider
  configuration, and unsupported tenant operations. [User]

## 4. Acceptance Criteria

- [ ] A provider can select Netris and supply all required provider-owned
  configuration through the deployment workflow.
- [ ] A valid Netris configuration produces a Ready provider-owned NetworkClass
  and a complete Netris Fabric Manager registration for the shared networking
  resources and VMaaS, BMaaS, and CaaS.
- [ ] The deployment is IPv4-only, connected-only, single-hub, and does not
  expose tenant configuration for manager selection or manager capability
  subsets.
- [ ] Tenants can use the shared networking APIs, CLI, and supported UI flows
  for read, create, and delete operations after dependencies are Ready.
- [ ] Tenant attempts to update or patch network-owned fields, create a
  dependent object before its reference is Ready, delete a referenced object,
  use IPv6, use unsupported cardinality, or use an air-gapped/multi-hub
  topology are rejected with the shared validation behavior.
- [ ] VMaaS, BMaaS, and CaaS use Netris through their shared networking flows;
  no service is omitted because a provider declared a partial Netris
  capability set.
- [ ] Invalid or unreachable Netris configuration leaves the NetworkClass
  non-Ready, prevents dependent tenant resource/workload creation, and does
  not expose credentials.
- [ ] Netris-backed create and delete reconciliation is idempotent, preserves
  tenant isolation, and reports backend failures without partial tenant-visible
  state.
- [ ] Unit, integration, and end-to-end tests cover the provider configuration,
  every canonical networking resource, all three workload services, readiness
  and dependency failures, supported CLI/UI/API behavior, and rejected
  operations.

## 5. Assumptions

- A Netris deployment, including its controller and required fabric-side
  services, already exists and is reachable from the OSAC management
  environment. [Jira: OSAC-2434]
- The Netris backend roles and generic networking operations referenced by
  OSAC-2043 are available to the implementation work. [Jira: OSAC-2043]
- Unified Networking remains the authoritative source for shared resource
  schemas, field formats, reference typing, defaults, manager dispatch,
  readiness, deletion, and validation behavior. [User]

## 6. Dependencies

- Unified Networking (`OSAC-1433`) for the shared networking and manager
  contracts. [Jira: OSAC-2434] [User]
- Netris backend roles and API integration (`OSAC-2043`). [Jira: OSAC-2043]
- OSAC installer and deployment configuration flow for provider inputs,
  manager registration, NetworkClass defaults, and credential Secret
  handoff. [Jira: OSAC-2434]
- Dispatcher and AAP execution paths for Netris operations. [Jira: OSAC-2043]
- VMaaS, BMaaS, and CaaS networking integrations, which consume the complete
  manager contract. [User]
- Enclave deployment wizard work (`OSAC-2530`) for provider-facing selection
  and configuration UX. [Jira: OSAC-2434]

## 7. Risks

### 7.1 Netris configuration is incomplete or incompatible

- **Owner:** Connectivity and Fabric team
- **Mitigation:** Validate all required provider inputs and Netris connectivity
  before NetworkClass readiness; report actionable non-secret failures and
  prevent tenant resource admission until the configuration is valid.

### 7.2 Netris backend operations are not available for the complete contract

- **Owner:** Connectivity and Fabric team
- **Mitigation:** Admit only a complete manager registration. An unfinished
  operation may use the approved internal successful no-op AAP path during
  development, but no resource, policy, workload-scope, or service subset is
  advertised and no tenant-visible partial-manager flow is exposed.

### 7.3 Netris and OSAC lifecycle state diverge

- **Owner:** Connectivity and Fabric team
- **Mitigation:** Use idempotent operation keys, persisted manager targets,
  readiness checks before dispatch, retryable status transitions, and strict
  deletion blockers. Backend failures must leave the OSAC resource in an
  observable non-Ready state rather than silently changing its requested
  networking configuration.

## 8. Open Questions

Questions for design review:

### 8.1 Netris configuration and credential rotation

- **Owner:** Connectivity and Fabric team
- **Impact:** Determines the provider configuration schema, Secret update
  behavior, manager re-registration behavior, and operational procedures.
- **Question:** Which Netris credential types and rotation trigger are required
  for the initial integration, and must rotation be accepted without changing
  the selected NetworkClass?

### 8.2 Netris API compatibility boundary

- **Owner:** Connectivity and Fabric team
- **Impact:** Determines validation of controller versions and the exact
  supported operation set during provider admission.
- **Question:** Is there a minimum Netris controller/API version that the
  provider configuration must validate?

---

## Provenance

Authored: draft @ prd 0.11.1 - 3f9c3b9, workspace main @ 0ae795e37 (96 behind origin/main)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.1","ai_workflows":"3f9c3b9","source_repo":"0ae795e37","source_repo_branch":"main","commits_behind_main":96,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
