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
bare-metal workers. This capability targets OSAC 0.5.

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

- **FR-3 — Instance intention:** Tenant Admins and Tenant Users select one of
  three Secure Boot intentions for a BareMetalInstance: `required`,
  `preferred`, or `disabled`. `preferred` is the default.
  [Clarify: R1.Q5, R2.Q1, R6.Q1] [User]

| Tenant intention | Hardware and image declarations | Effective behavior |
|---|---|---|
| `required` | Hardware declared supported and image declared compatible | Enable Secure Boot |
| `required` | Hardware declared unsupported, image declared incompatible, or either declaration missing | Reject before host allocation |
| `preferred` | Hardware declared supported and image declared compatible | Enable Secure Boot |
| `preferred` | Hardware declared unsupported, image declared incompatible, or either declaration missing | Disable Secure Boot |
| `disabled` | Any | Disable Secure Boot |

The declarations are evaluated when the BareMetalInstance is created, and the
resolved effective behavior is stored on the instance. Later declaration
updates affect only new instances. [Clarify: R6.Q2] [User]

- **FR-4 — Actionable create-time validation:** Before host allocation,
  `required` is rejected if the selected BareMetalInstanceType
  declares no hardware support, the selected DiskImage declares
  incompatibility, or either declaration is missing. The error identifies each
  blocking declaration and who can correct it. [Clarify: R4.Q1, R4.Q2] [User]
- **FR-5 — Workload consistency:** The same intention resolution, validation,
  effective-behavior visibility, pre-boot enforcement, and failure behavior
  apply to tenant-created BMaaS instances and CaaS worker BareMetalInstances.
  [Clarify: R3.Q4, R6.Q4]
- **FR-6 — Effective behavior visibility:** For a `preferred` request, Tenant
  Admins and Tenant Users can inspect through the CLI and API whether OSAC
  resolved Secure Boot to enabled or disabled. If provisioning succeeds with
  an effective value of enabled, the FR-7 confirmation gate has passed.
  [Clarify: R2.Q2, R6.Q3] [User]
- **FR-7 — Pre-boot enforcement:** For a tenant-created BMaaS instance or CaaS
  worker BareMetalInstance whose effective behavior is enabled, OSAC must
  obtain provider or BMC confirmation that Secure Boot is enabled before the
  first boot attempt from the selected DiskImage. If it cannot, provisioning
  fails without starting the tenant OS or delivering the host, and the
  requester can see the provisioning error. The failed request is not retried
  with Secure Boot disabled; the tenant may submit a separate `disabled`
  request. [Clarify: R5.Q1, R5.Q2, R5.Q4, R6.Q4] [User]
- **NFR-1 — Backward compatibility:** Existing BareMetalInstanceTypes and
  DiskImages without declarations retain Secure Boot disabled after upgrade
  until their owners add declarations; no existing boot behavior changes
  automatically. [Clarify: R3.Q1, R3.Q2]
- **NFR-2 — Backend consistency:** Users receive the same defaults,
  validation, effective behavior, and failure handling across all supported
  BMaaS management implementations. [Clarify: R2.Q2]
- **NFR-3 — Effective behavior integrity:** The effective behavior exposed
  through the API and CLI is the value resolved at instance creation and does
  not change when a source declaration is later updated. [Clarify: R6.Q2]
- **Verification scope:** The default-on success journey and the fail-closed
  pre-boot outcome must be demonstrated end to end in a deployed environment.

## Out of Scope

- TPM measured boot or clearing TPM state between tenants.
- Independent runtime firmware attestation after provisioning.
- Cryptographic inspection of DiskImage contents or independent verification
  of hardware-support and image-compatibility declarations.
- Automatic detection or population of hardware-support and image-compatibility
  declarations; future detection may populate the same declarations without
  changing their meaning.
- Automatic attribution of a provisioning failure to hardware versus the
  DiskImage, and a Secure Boot-specific host quarantine mechanism.
- Secure Boot and persistent boot or security state for virtual machines,
  which are covered by [OSAC-7205](https://redhat.atlassian.net/browse/OSAC-7205).
- UI support in this milestone.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to declare whether each
  BareMetalInstanceType supports Secure Boot so that tenants receive a safe
  default based on the provider's knowledge of its inventory.

### Cloud Provider Admin / Tenant Admin / Tenant User

- As a Cloud Provider Admin, Tenant Admin, or Tenant User, I want to declare
  whether a DiskImage supports Secure Boot when I create it so that users can
  identify images for which Secure Boot is available when selecting an
  instance image.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to see the Secure Boot declarations
  on BareMetalInstanceTypes and DiskImages available to me so that I can
  understand the default and avoid incompatible requests.
- As a Tenant Admin or Tenant User, I want to require, prefer, or disable
  Secure Boot so that I can choose the appropriate protection for each
  bare-metal workload.
- As a Tenant Admin or Tenant User, I want to see whether a `preferred` request
  resolved to Secure Boot enabled or disabled so that the successful outcome
  is unambiguous.
- As a Tenant Admin or Tenant User, when my request resolves Secure Boot to
  enabled, I want my tenant OS to start only after it is confirmed so that a
  provisioning failure cannot silently downgrade my request.
- As a Tenant Admin or Tenant User, I want BMaaS instances and CaaS workers I
  provision to use the same Secure Boot behavior through provisioning so that
  choosing a CaaS workflow does not weaken the expected boot protection.

## Dependencies

- **BMaaS provisioning backends:** For tenant-created BMaaS instances and CaaS
  worker BareMetalInstances whose effective behavior is enabled, each
  supported backend must enable and confirm UEFI Secure Boot before
  tenant-image boot and report failure when it cannot.
- **Resource declarations:** Cloud Provider Admins must provide accurate
  hardware-support declarations, and every DiskImage creator must provide an
  accurate image-compatibility declaration.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf
Final: respond @ prd 0.11.5 - 7b2b8de, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf (33 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"a3ec34fbf","source_repo_branch":"feat/OSAC-3035-UEFI-Secure-Boot","commits_behind_main":33,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","respond","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
