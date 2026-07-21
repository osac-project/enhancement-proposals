# Bare Metal Instance Types

| Field       | Value   |
|-------------|---------|
| Author(s)   | Austin Jamias |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1201 |
| Date        | 2026-07-06 |
| Updated     | 2026-07-21 |

## 1. Problem Statement

OSAC has no concept of host types surfaced from inventory. Without it, Tenant Users cannot express hardware preferences when ordering a BareMetalInstance, and Cloud Admins cannot express which types of hardware should be allocated for provisioning — the platform cannot match requests to available hardware types across backends. This forces users to work with opaque hostType strings that provide no information about underlying hardware capabilities (CPU, memory, accelerators, network ports), making it impossible for them to select appropriate hardware for their workloads through self-service provisioning.

## 2. Goals and Non-Goals

### 2.1 Goals

- Make bare metal hardware selection self-service: Tenant Users should be able to understand and choose hardware based on meaningful specifications rather than opaque type strings
- Simplify hardware exposure for admins: Cloud Provider Admins should have a clear, predictable workflow to surface inventory hardware to tenants without requiring per-host configuration
- Ensure provisioning predictability: the hardware a user selects should be the hardware they receive, with no silent substitution or capability mismatch
- Keep bare metal and virtual instance type management separate to avoid complexity from their differing management characteristics

### 2.3 Non-Goals

- Billing/metering from inventory
- Storage inventory beyond basic local storage information
- Multi-backend inventory collision handling
- Tracking the number of available hosts for each BareMetalInstanceType (deferred to a later PRD)
- InstanceTypes (virtual machine instance types) — this PRD covers BareMetalInstanceTypes only; VM instance types are a separate resource with a separate lifecycle

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** Tenant Users must be able to list available BareMetalInstanceTypes through the CLI and REST/gRPC API [Clarify: R1.Q2]
- **FR-2:** Tenant Users must be able to select a BareMetalInstanceType when creating a BareMetalInstance through the CLI and REST/gRPC API [Clarify: R1.Q2]
- **FR-3:** BareMetalInstanceTypes must expose comprehensive hardware metadata including CPU, RAM, storage, GPU class, accelerators, network ports, local storage, and freeform capabilities field [Clarify: R1.Q3]
- **FR-4:** Cloud Provider Admins must be able to create BareMetalInstanceTypes that specify hardware metadata and label selectors for matching hosts from the inventory backend
- **FR-5:** During BareMetalInstance provisioning, the operator must use the label selector from the selected BareMetalInstanceType to find and allocate matching hosts from the inventory backend

### 3.2 Non-Functional Requirements

- **NFR-1:** BareMetalInstanceType listing operations must provide filtering capabilities without degraded performance

## 4. Acceptance Criteria

- [ ] Tenant Users can list BareMetalInstanceTypes via CLI and API and see hardware specifications (CPU, RAM, storage, GPU, accelerators, network ports, local storage, capabilities)
- [ ] Tenant Users can select a BareMetalInstanceType during BareMetalInstance creation via CLI and API
- [ ] Cloud Provider Admins can create a BareMetalInstanceType in OSAC with a label selector, and the BMaaS operator selects only inventory hosts whose labels match that selector during provisioning
- [ ] Cloud Infrastructure Admins can configure inventory backend connection via inventory.yaml with authentication credentials
- [ ] E2E workflow: Cloud Infra Admin labels hosts → Cloud Provider Admin creates BareMetalInstanceType with matching label selector → Tenant User provisions BareMetalInstance with selected BareMetalInstanceType → operator uses the type's label selector to find and allocate a matching host from inventory
- [ ] BareMetalInstance provisioning consistently delivers hardware that matches the selected BareMetalInstanceType specifications, ensuring users receive the machine capabilities they requested

## 5. Assumptions

- Cloud Infrastructure Admins must be able to map BareMetalInstanceTypes to existing metadata (e.g. labels) in the inventory backend
- The Cloud Infrastructure Admin correctly labeled all OSAC hosts such that there is no hardware difference among hosts with the same label.
- The Cloud Provider Admin correctly creates BareMetalInstanceTypes with hardware information that is consistent with the hardware info on each host that the Cloud Infrastructure Admin applied a label to.
- Single inventory backend deployment - no handling of multiple inventory backends simultaneously [Clarify: R2.Q3]
- The bare-metal-fulfillment-operator has necessary permissions to query the configured inventory backend
- Inventory backends (OpenStack, BCM) provide consistent and accessible APIs for host querying and label-based filtering
- BareMetalInstanceTypes are always created manually by Cloud Provider Admins — there is no automatic discovery or creation of BareMetalInstanceTypes from inventory backends. Cloud Provider Admins are responsible for ensuring BareMetalInstanceType label selectors match the labels applied by Cloud Infrastructure Admins.
- All inventory implementations will have some equivalent concept to host labels that supports the label-based matching model [User]
- The bare-metal-fulfillment-operator's inventory integration must be pluggable to support multiple inventory implementations (e.g., OpenStack, BCM) for label-based host selection during provisioning [User]
- BareMetalInstanceTypes are architecturally separate from InstanceTypes (virtual machine instance types) to avoid complexity from conditional fields and different management characteristics (live migration, snapshots vs. location awareness, networking) [Meeting: Architecture decision]
- GPU configurations will be included within the BareMetalInstanceType definition rather than as separate resource types [Meeting: GPU consideration]

## 6. Dependencies

- **OSAC-1118 (Baremetal OSAC API):** Provides the foundational BareMetalInstance API and lifecycle management that BareMetalInstanceTypes integrate with
- **Inventory backends (OpenStack, BCM):** Provide the source data for host metadata and label-based host filtering during provisioning
- **bare-metal-fulfillment-operator:** Component responsible for label-based host selection and mapping between BareMetalInstanceTypes and inventory hosts

---

## Provenance

Authored: revise @ prd 0.5.0 - 92734a2, workspace main @ 5450556
Phases: revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"5450556","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise"],"authoring_modes":["skill"],"context_changed":false} -->
