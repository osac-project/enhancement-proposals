# Serial Numbers in BareMetalInstance Inventory

| Field       | Value |
|-------------|-------|
| Author(s)   | Matthieu Bernardin |
| Jira        | [OSAC-3857](https://redhat.atlassian.net/browse/OSAC-3857) |
| Date        | 2026-10-01 |

## Problem Statement

BMaaS is currently not compliant with NVIDIA Cloud Partner (NCP) requirements, particularly the BFX03-01 serial-number check, because BareMetalInstance inventory does not expose serial numbers for installed hardware. [User] NVIDIA's BFX03 Diagnostics requirement covers serial numbers for chassis, baseboard, network adapters, CPU, and GPU, and permits a stable obfuscated representation. [NVIDIA Requirements for AI Clouds v2.4](https://docs.nvidia.com/dsx/ncp/nvidia-requirements-for-ai-clouds/v2.4). Cloud Provider Admins lack the inventory detail needed to demonstrate compliance and trace physical assets, Cloud Infrastructure Admins cannot correlate a BareMetalInstance with physical equipment through OSAC, and Tenant Admins cannot cross-reference hardware vendor support. [Jira: OSAC-3857]

## In Scope

- Make serial numbers, or stable obfuscated representations, available for installed chassis, baseboards, CPUs, GPUs, and network adapters (NICs) associated with a BMaaS BareMetalInstance. No other hardware categories are included. [Clarify: R1.Q1] [User]
- Make the inventory and serial-number values available in BareMetalInstance status, the OSAC gRPC and REST APIs, the UI detail view, and CLI output. The CLI table view need not display serial-number values. [Clarify: R1.Q4] [User]
- Keep every known in-scope component visible in the inventory when its serial number cannot be read. Leave its serial-number value empty and preserve the actual component count; for example, show three installed network adapters when only two serial numbers can be read. Do not fabricate serial numbers. [Clarify: R1.Q2, R2.Q1]
- All inventory implementations used by the Bare Metal Fulfillment (BMF) controller are expected to provide serial numbers for all five categories when the data is available. [Clarify: R1.Q2] [User]
- Document how Cloud Provider Admins can view the inventory and interpret an empty serial number, which means the component is present but its serial number could not be read. For each BMF controller inventory implementation, list unavailable hardware information and state that it will not be available when that implementation is selected. [Clarify: R2.Q1, R2.Q2] [User]
- Verify the capability with NVIDIA's BFX03-01 validation from the AI Cloud Validation Suite. [Clarify: R1.Q5]

## Out of Scope

- Hardware categories other than chassis, baseboard, CPU, GPU, and network adapters (NICs). Inspection of compute-node and NV switch tray firmware versions under BFX03, including the separate BFX03-02 validation, is also out of scope; this PRD covers BFX03-01 serial-number validation. [Clarify: R1.Q1] [User]
- Serial numbers for non-bare-metal compute resources such as VMs and ClusterOrders. [Jira: OSAC-3857]
- Modifying or overriding hardware serial numbers, or integrating with an external hardware inventory or CMDB. [Jira: OSAC-3857]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view the installed hardware serial numbers for a BareMetalInstance so that I can demonstrate compliance and trace physical assets. [Jira: OSAC-3857]
- As a Cloud Provider Admin, I want to know which serial numbers a BMF inventory implementation cannot provide so that I can assess its inventory coverage. [Clarify: R2.Q2] [User]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to retrieve the hardware serial numbers for a BareMetalInstance through the OSAC API or CLI so that I can correlate the instance with physical hardware inventory. [Jira: OSAC-3857] [Clarify: R1.Q4]

### Tenant Admin

- As a Tenant Admin, I want to view the hardware serial numbers for my BareMetalInstance so that I can cross-reference the hardware with vendor support contracts. [Jira: OSAC-3857]

## Assumptions

- Cloud Provider Admins, Cloud Infrastructure Admins, and Tenant Admins see the same serial-number representation. [Clarify: R1.Q3]
- **Open question:** Should BMaaS expose raw serial numbers, stable obfuscated representations, or make the choice configurable? [Clarify: R1.Q3] [User]
  - **Owner:** Feature owner
  - **Impact:** Determines which serial-number representation users see and whether it can be changed through configuration.

## Dependencies

- **NVIDIA AI Cloud Validation Suite:** Use its [BFX03-01 check](https://github.com/NVIDIA/ai-cloud-validation/issues/320) to verify compliance; the [requirements matrix](https://github.com/NVIDIA/ai-cloud-validation/blob/main/docs/requirements/test-requirements-matrix.adoc) lists full coverage. Run it through [`isvctl`](https://github.com/NVIDIA/ai-cloud-validation/blob/main/docs/packages/isvctl.md) with suitable OSAC provider wiring, and record any BMF controller inventory implementation gaps reported by the suite. [Clarify: R1.Q5] [User]

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ 0d3997211
Phases: draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"0d3997211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
