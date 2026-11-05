# BMaaS UEFI Secure Boot Enforcement

| Field | Value |
|---|---|
| Author(s) | Matthieu Bernardin |
| Jira | [OSAC-3035](https://redhat.atlassian.net/browse/OSAC-3035) |
| Date | 2026-11-04 |

## Problem Statement

OSAC currently has no declarations for whether bare-metal hardware and
DiskImages support UEFI Secure Boot, and Tenant Admins and Tenant Users cannot
choose or observe the effective behavior. Secure Boot can therefore remain
disabled when it is available, while incompatible selections may fail only
during provisioning. This leaves tenants without consistent assurance that
unsigned or tampered boot components are rejected on BMaaS instances and CaaS
workers. This capability targets OSAC 0.5.

## In Scope

- **FR-1 — Hardware support declaration:** Cloud Provider Admins can set
  whether a BareMetalInstanceType's hardware supports UEFI Secure Boot. Cloud
  Provider Admins, Tenant Admins, and Tenant Users can inspect the declaration
  through the CLI and API when permitted to view the type.
  [Clarify: R2.Q1, R3.Q2] [User]
- **FR-2 — Image compatibility declaration:** Cloud Provider Admins, Tenant
  Admins, and Tenant Users must declare whether each new DiskImage they create
  is Secure Boot compatible. They can inspect the declaration through the CLI
  and API when permitted to view the image. [Clarify: R1.Q4, R2.Q5] [User]

> **Declaration semantics:** FR-1 is set by the Cloud Provider Admin, and FR-2
> is set by the DiskImage creator. Both are informative declarations that
> represent the declarer's knowledge and are not independently verified at
> creation. When Secure Boot is effective, provisioning confirms it is enabled
> before starting the tenant image, as required by FR-7.

- **FR-3 — Instance intention:** Tenant Admins and Tenant Users can explicitly
  enable or disable Secure Boot for a BareMetalInstance, or omit the choice
  and use the default below. [Clarify: R1.Q5, R2.Q1] [User]

| Tenant intention | Hardware and image declarations | Effective behavior |
|---|---|---|
| Enabled | Hardware declared supported and image declared compatible | Enable Secure Boot |
| Enabled | Hardware declared unsupported, image declared incompatible, or either declaration missing | Reject before host allocation |
| Disabled | Any | Disable Secure Boot |
| Unspecified | Hardware declared supported and image declared compatible | Enable Secure Boot by default |
| Unspecified | Hardware declared unsupported, image declared incompatible, or either declaration missing | Disable Secure Boot |

- **FR-4 — Actionable create-time validation:** Before host allocation,
  explicit enablement is rejected if the selected BareMetalInstanceType
  declares no hardware support, the selected DiskImage declares
  incompatibility, or either declaration is missing. The error identifies each
  blocking declaration and who can correct it. [Clarify: R4.Q1, R4.Q2] [User]
- **FR-5 — Workload consistency:** The same defaults and validation apply to
  tenant-created BMaaS instances and CaaS worker BareMetalInstances.
  [Clarify: R3.Q4]
- **FR-6 — Outcome visibility:** After successful provisioning, Tenant Admins
  and Tenant Users can see through the CLI and API whether an instance they are
  permitted to view completed provisioning after Secure Boot was confirmed
  enabled. Verification is not reported before provisioning succeeds.
  [Clarify: R2.Q2, R5.Q1] [User]
- **FR-7 — Pre-boot enforcement:** When Secure Boot is effective, it must be
  confirmed enabled before the first boot attempt from the tenant-selected
  DiskImage. If it cannot be confirmed, the request fails without starting the
  tenant OS or delivering the host, and the requester can see the provisioning
  error. The failed request is not retried with Secure Boot disabled; the
  tenant may submit a separate request that explicitly disables it.
  [Clarify: R5.Q1, R5.Q2, R5.Q4] [User]
- **NFR-1 — Backward compatibility:** Existing BareMetalInstanceTypes and
  DiskImages without declarations retain Secure Boot disabled after upgrade
  until their owners add declarations; no existing boot behavior changes
  automatically. [Clarify: R3.Q1, R3.Q2]
- **NFR-2 — Backend consistency:** Users receive the same defaults,
  validation, status, and failure behavior across all supported BMaaS
  management implementations. [Clarify: R2.Q2]
- **NFR-3 — Status integrity:** The Secure Boot status shown to users reflects
  the confirmed, completed provisioning outcome and does not report
  verification for incomplete or failed provisioning. [Clarify: R2.Q2]
- **Verification scope:** The default-on success journey and the fail-closed
  pre-boot outcome must be demonstrated end to end in a deployed environment.

## Out of Scope

- TPM measured boot or clearing TPM state between tenants.
- Independent runtime firmware attestation after provisioning.
- Cryptographic inspection of DiskImage contents or independent verification
  of hardware-support and image-compatibility declarations.
- Automatic attribution of a provisioning failure to hardware versus the
  DiskImage, and a Secure Boot-specific host quarantine mechanism.
- UI support in this milestone.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to declare whether each
  BareMetalInstanceType supports Secure Boot so that tenants receive a safe
  default based on the provider's knowledge of its inventory.

### Cloud Provider Admin / Tenant Admin / Tenant User

- As a Cloud Provider Admin, Tenant Admin, or Tenant User, I want to declare
  Secure Boot compatibility when I create a DiskImage so that incompatible
  requests fail before consuming a host.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to see the Secure Boot declarations
  on BareMetalInstanceTypes and DiskImages available to me so that I can
  understand the default and avoid incompatible requests.
- As a Tenant Admin or Tenant User, I want to enable or disable Secure Boot
  explicitly, or accept the safe default, so that I can choose the appropriate
  boot protection for each bare-metal workload.
- As a Tenant Admin or Tenant User, I want the CLI and API to show whether an
  instance I can view completed provisioning with Secure Boot and show the
  provisioning error when it could not, so that I know whether the instance
  is ready to use or provisioning failed.
- As a Tenant Admin or Tenant User, I want my tenant OS to start only after
  Secure Boot is confirmed enabled so that a provisioning failure cannot
  silently downgrade my request.
- As a Tenant Admin or Tenant User, I want BMaaS instances and CaaS workers I
  provision to use the same defaults and validation so that choosing a CaaS
  workflow does not weaken the expected boot protection.

## Dependencies

- **BMaaS provisioning backends:** Each supported backend must enable and
  confirm UEFI Secure Boot before tenant-image boot and report failure when it
  cannot.
- **Resource declarations:** Cloud Provider Admins must provide accurate
  hardware-support declarations, and every DiskImage creator must provide an
  accurate image-compatibility declaration.

---

## Provenance

Authored: revise @ prd 0.11.5 - 7b2b8de, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf
Phases: draft, revise, revise, revise, revise, revise, revise, revise, revise, respond, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"a3ec34fbf","source_repo_branch":"feat/OSAC-3035-UEFI-Secure-Boot","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","respond","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
