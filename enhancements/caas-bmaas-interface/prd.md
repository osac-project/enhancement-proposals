# Cluster-as-a-Service (CaaS) Interface for BMaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Tzu-Mainn Chen |
| Jira        | https://issues.redhat.com/browse/OSAC-1566 |
| Date        | 2026-07-01 |

## 1. Problem Statement

CaaS requires bare metal compute to back cluster worker nodes and currently leverages agents deployed on bare metal hosts. However, there is no formal, standardized workflow for creating these agents that works across multiple bare metal backends managed by OSAC BMaaS. Without a defined integration contract, CaaS and BMaaS teams must rely on ad-hoc coordination, limiting the ability to provision agents consistently across different bare metal infrastructure providers.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Infrastructure Admins can provision bare metal hosts through BMaaS that boot as OpenShift agents ready for CaaS cluster worker node pools
- CaaS can discover and claim agents without directly interacting with BMaaS resources or APIs
- The integration contract between BMaaS and CaaS is documented and agreed upon by both teams

### 2.3 Non-Goals

- CaaS-side Cluster API provider implementation
- CaaS cluster lifecycle management
- Agent claiming/allocation mechanisms (CaaS responsibility)
- Agent release workflows after cluster decommissioning (handled by hosted cluster mechanisms)
- Changes to the BMaaS BareMetalInstance API (existing ISO boot support is sufficient)
- Direct CaaS-to-BMaaS API integration or RBAC configuration

## 3. Requirements

### 3.1 Functional Requirements

#### Agent Provisioning Workflow

- **FR-1:** Cloud Infrastructure Admins must be able to provision bare metal hosts through BMaaS using an ISO URL derived from a pre-existing InfraEnv resource. [Clarify: D4, D8]
- **FR-2:** Hosts provisioned with the InfraEnv discovery ISO must automatically register as Agent CRs when they boot. [Clarify: D5]
- **FR-3:** Cloud Infrastructure Admins must be able to provision multiple agents in a batch operation (exact mechanism is an open question, see Section 8.4). [Clarify: D16]
- **FR-4:** Hosts must transition through network attachments during the provisioning lifecycle: from a provisioning network (for agent boot) to an admin network (post-registration). [Clarify: D15]
- **FR-9:** The agent provisioning workflow (e.g., Ansible playbook orchestrating BMaaS and other steps) must verify that an Agent CR is created and reaches the appropriate state after a host is provisioned with the discovery ISO, enabling detection and reporting of agent registration failures. [User]

#### Agent Discovery and Consumption

- **FR-5:** CaaS must be able to discover available agents by watching or querying Agent CRs directly, without querying BMaaS resources. [Clarify: D5, D11]
- **FR-6:** Agent CRs must exist and be accessible to CaaS with no additional readiness validation required from BMaaS. [Clarify: D13]
- **FR-8:** CaaS must handle network isolation for agents it claims; BMaaS is responsible only for network transitions during the boot workflow (FR-4), not for network isolation of agents backing cluster worker nodes. [User]

#### Error Handling

- **FR-7:** BMaaS must report provisioning failures through the existing BareMetalInstance status contract to the admin workflow that initiated provisioning. [Clarify: D14]

### 3.2 Non-Functional Requirements

- **NFR-1:** The BMaaS provisioning workflow must use existing BareMetalInstance API capabilities without requiring API changes. [Clarify: D6]
- **NFR-2:** Tenants requesting clusters through CaaS must not see or interact with the underlying BMaaS agent provisioning process. [Clarify: D3]

## 4. Acceptance Criteria

- [ ] A Cloud Infrastructure Admin can provision a BareMetalInstance with an InfraEnv-derived ISO URL via BMaaS
- [ ] A host booted with the discovery ISO automatically registers as an Agent CR
- [ ] CaaS can query or watch Agent CRs to discover available agents
- [ ] A Cloud Infrastructure Admin can provision multiple agents in a single workflow
- [ ] Hosts transition from provisioning network to admin network during the agent provisioning workflow
- [ ] BMaaS reports provisioning failures to the admin workflow via BareMetalInstance status

## 5. Assumptions

- InfraEnv resources are pre-existing infrastructure managed outside the scope of this feature
- Provisioning and admin networks required for the agent boot workflow are pre-existing and configured
- CaaS has infrastructure-level RBAC permissions to access Agent CRs
- Hosted cluster mechanisms handle Agent CR lifecycle and return agents to claimable state after cluster decommissioning

## 6. Dependencies

- InfraEnv resource (pre-existing, provides discovery ISO URL)
- Discovery ISO boot process (creates Agent CRs when hosts boot)
- Provisioning network and admin network (pre-existing networking infrastructure)
- Hosted cluster mechanisms (manage Agent CR state transitions and lifecycle)

## 7. Risks

### 7.1 Network transition automation gaps

The workflow requires hosts to transition from provisioning network to admin network during agent registration. If this network transition fails or is not automated, agents may register but be unreachable by CaaS.

- **Owner:** Cloud Infrastructure Admin / BMaaS team
- **Mitigation:** Document network transition requirements clearly in the EP; validate network attachment changes during testing.

## 8. Open Questions

### 8.1 Should the BareMetalInstance be deleted after Agent CR creation, or should it persist?

One perspective: once an Agent CR is created through BMaaS, the underlying BareMetalInstance can be deleted since the external inventory is now marked as `managedBy: agent`. Alternative perspective: the BareMetalInstance should persist to maintain ownership tracking and enable troubleshooting.

- **Owner:** BMaaS team / CaaS team
- **Impact:** Affects resource lifecycle design, garbage collection strategy, and troubleshooting capabilities in Section 3.1 (Functional Requirements).

### 8.2 What interface should Cloud Infrastructure Admins use to provision agents—Ansible playbook, CLI/API, or UI?

The agent provisioning process could be delivered as an Ansible playbook manually run by admins, exposed via CLI/API for automation, or surfaced in the osac-ui console.

- **Owner:** UX team / BMaaS team
- **Impact:** Affects implementation scope (Section 3.1), deliverables, and usability for Cloud Infrastructure Admin persona.

### 8.3 What E2E testing scope is needed in osac-test-infra?

Testing could range from validating that the BMaaS API accepts ISO URLs, to end-to-end validation that hosts boot and register as Agent CRs, to full CaaS cluster creation flows using BMaaS-provisioned agents.

- **Owner:** QE team / BMaaS team / CaaS team
- **Impact:** Affects test deliverables, testing infrastructure requirements, and validation coverage in Section 4 (Acceptance Criteria).

### 8.4 Should Cloud Infrastructure Admins use BareMetalPools or individual BareMetalInstances for batch agent provisioning?

When provisioning multiple agents, should the workflow use BareMetalPools (a CR in bare-metal-fulfillment-operator) to create multiple BareMetalInstances atomically, or should admins create individual BareMetalInstances one at a time?

- **Owner:** BMaaS team / Cloud Infrastructure Admin
- **Impact:** Affects workflow design, automation approach, and operational efficiency in Section 3.1 (Functional Requirements) and Section 4 (Acceptance Criteria).

### 8.5 Should CaaS handle its own resource tracking and reporting, or leverage BMaaS capabilities?

The current integration model implies CaaS will handle network isolation (FR-8) independently from BMaaS. This same pattern may extend to resource tracking and reporting—CaaS would track agent utilization, availability, and metrics without relying on BMaaS capabilities. Is this separation of concerns the right approach, or should CaaS leverage BMaaS for resource tracking and reporting?

- **Owner:** CaaS team / BMaaS team
- **Impact:** Affects architectural boundaries, observability design, and operational tooling requirements for both CaaS and BMaaS teams.
