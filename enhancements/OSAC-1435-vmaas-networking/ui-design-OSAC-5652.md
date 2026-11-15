# UI Design — OSAC-5652

**Story:** OSAC-5652 — UIX - VMaaS Networking
**Parent:** OSAC-1435 — VMaaS Networking
**Updated:** 2026-11-15

## Summary

Extend the existing VM create wizard and details page with tenant networking.
The wizard uses the shared `NetworkAttachmentPickers` component with the VM
configuration of the Unified UI design: VirtualNetwork, Subnet, and Security
Groups are all required, sent as a `network_attachments` list, sending an empty list `[]` when
the tenant-default toggle is on (the field is required). [Unified UI: Workload network attachment
pickers] [Handoff: CaaS Networking UX] [Design: OSAC-1435 VMaaS Networking]

The current details page is a continuous layout. Its Networking section shows
the resolved VirtualNetwork, Subnet, Security Groups, and internal IP. The
Access & Initial run section shows the External IP value and owns manual attach
and detach actions. [Codebase: `osac-ui/libs/ui-components/src/components/vm/DetailsPage/`]

Auto-attachment is a separate create-time flow. When selected, the UI shows
the address with the **Auto** badge once the system-created
ExternalIPAttachment is READY. The VM remains usable if automatic external
access fails. [PRD: OSAC-1435 FR-3]

## UI elements by persona

### Tenant user

| Surface | Introduced or changed UI |
|---|---|
| VM create — Networking | Tenant default/custom network choice; VirtualNetwork → Subnet selection; Security Groups; Auto-attach external IP switch and helper text. |
| VM create — Review | Network choice, selected custom-network resources, and Auto attach external IP: Yes/No. |
| VM details — Networking | Read-only resolved network table with VirtualNetwork, Subnet, Security Groups, and internal IP. |
| VM details — Access & Initial run | External IP value, lifecycle status, manual Attach/Detach actions, and attach/detach modals. |

### Tenant admin

Tenant admins use the same tenant-scoped create and details surfaces. They can
inspect resolved network and External IP state but receive no provider-only
controls.

No additional UI is introduced for provider or infrastructure administrators
by this story.

## Behavior

### Create-time networking

- Use the shared networking step with the Unified UI VM configuration:
  all pickers required, `network_attachments` sent as a list, sending an empty list `[]` when the
  tenant-default toggle is on (the field is required).
- Tenant default shows the resolved read-only VirtualNetwork, Subnet, and
  Security Groups.
- Custom network requires a ready VirtualNetwork, then filters Subnets and
  Security Groups to that network, excluding automatic SecurityGroups (the
  server gate rejects a selected automatic SecurityGroup), and preserves
  readiness and tenant scope.
- Network configuration and the auto-attach choice are immutable after create.
- If the create is rejected by the server (for example `FAILED_PRECONDITION`
  for IPv4 pool exhaustion), the wizard shows the backend error; nothing is
  stored. [Design: OSAC-1433 §Automatic external access]

### External IP without auto-attachment

- A VM has at most one ExternalIPAttachment. `Attach external IP` is offered
  only when no attachment exists and the VM endpoint is ready per the design's
  full rule: state RUNNING, `READY` condition TRUE,
  internal IP allocated (`status.compute_network_attachment_statuses[0].ip_address` — the VM's private IP, not the external address) set, and not being
  deleted. [Design: OSAC-1435 §ExternalIPAttachment target compute_instance]
  Otherwise the action is disabled with its reason.
- Attach opens the existing selector for allocated, unattached,
  tenant-visible ExternalIPs that are not automatic and not the tenant
  default, and creates an ExternalIPAttachment targeting the VM.
  [Design: OSAC-1433 §Attach ExternalIP selector]
- PENDING shows an in-progress icon with text "Attaching external IP..."; READY shows the address and `Detach`.
- Detach confirms deletion and shows DELETING until the attachment disappears.
- FAILED shows the backend `status.message` with `Detach` as the only action;
  the row stays visible until deletion completes, after which another
  ExternalIP can be attached. The API exposes no retry or update operation
  for an ExternalIPAttachment, so no `Retry` or `Choose another` actions are
  offered. [Design: OSAC-1433 §ExternalIPAttachment]

### Failure handling

The UI reads error reasons only from `ErrorInfo.reason`.
[Unified UI: error presentation]

| Operation | Failure | UI |
|---|---|---|
| Create VM | `FAILED_PRECONDITION`: Subnet or SecurityGroup not READY, tenant defaults not ready, IPv4 pool exhaustion | Wizard shows the backend error; nothing is stored. |
| Create VM | `INVALID_ARGUMENT`: SecurityGroup from another VirtualNetwork, missing tenant default | Wizard shows the backend error. |
| Attach | `FAILED_PRECONDITION`: VM endpoint not ready, ExternalIP already used | Attach modal shows the backend error. |
| Delete VM | `FAILED_PRECONDITION`: a manual ExternalIPAttachment still targets the VM | Deletion confirmation names the blocking attachment. [Design: OSAC-1435 §Delete] |

### External IP with auto-attachment

The wizard sends `spec.auto_external_ip_attachment=true`. The backend stores
the ComputeInstance and the automatic ExternalIP (PENDING) in one transaction
and allocates it in parallel with VM provisioning; the automatic
ExternalIPAttachment is created only after the VM endpoint is ready and its
address is known. The UI does not create or replace this attachment.
[Design: OSAC-1435 §Create, §Automatic external access]

- Derive the requested state from `ComputeInstance.spec.auto_external_ip_attachment` and display `ComputeInstance.status.external_ip_address` when present. If `spec.auto_external_ip_attachment == true` and no `status.external_ip_address` is reported yet, show an in-progress icon with "Attaching external IP...".
- Before the automatic attachment is READY, do not display an address or offer
  manual Attach, Retry, Choose another, or Detach actions.
- When the automatic attachment is READY, show its allocated address with the
  shared **Auto** badge and helper text: "This IP is managed with the VM and is
  detached only when the VM is deleted." Do not offer a Detach action: the
  automatic ExternalIP and its attachment are system-owned,
  `spec.auto_external_ip_attachment` is immutable after create, and the backend
  provisioning loop owns their lifecycle — a tenant-initiated detach would
  conflict with the requested spec state (the system would re-attach to satisfy
  it) and would broaden tenant scope over resources the tenant did not create.
  Automatic resources are removed with the VM.
  [Unified UI: automatic resource indicators]
- If the automatic attachment fails, show the backend failure message as inline helper text underneath the External IP value field, keep the VM usable, and fabricate no address.

## Data and state

| UI need | Source |
|---|---|
| Auto-attach requested | `ComputeInstance.spec.auto_external_ip_attachment` |
| VM network details | `ComputeInstance.spec.network_attachments[0]` for the stored Subnet, VirtualNetwork, and Security Group references; `status.internal_ip_address` and `status.compute_network_attachment_statuses[]` for the live address (the status entry is cleared for a Halted VM). The `NetworkReady` condition appears in the existing conditions display. |
| External IP address | `ComputeInstance.status.external_ip_address` (gated on the VM's ExternalIPAttachment reaching READY) |
| Attachment lifecycle | `ExternalIPAttachments` filtered to the current ComputeInstance; at most one attachment targets a VM |
| Automatic pending | `spec.auto_external_ip_attachment == true` with no `status.external_ip_address` → in-progress icon with "Attaching external IP..." |
| Manual attach | Create `ExternalIPAttachment` with the selected ExternalIP and VM target |
| Manual detach | Delete the manual `ExternalIPAttachment`; show DELETING until it is gone |

Formik owns create-wizard values. Server responses own network and External IP
lifecycle state. Only modal visibility is local component state; no new route,
global store, or client-persisted lifecycle state is needed. [Codebase: existing Formik and shared resource-hook patterns]

## Accessibility

- Use the existing translation hook and PatternFly controls.
- Keep lifecycle text adjacent to the External IP value and action.
- Announce automatic and manual transitions politely; use an assertive alert
  for actionable failures only.
- Preserve modal focus management and return focus to the triggering action when
  a manual attach/detach modal closes.
- Ensure disabled automatic-provisioning actions remain understandable through
  visible status text, not color alone.

## Testing

- Create wizard: tenant-default/custom selection, dependent filtering,
  validation, auto-attach switch, review value, immutable payload behavior.
- Details networking: resolved resources, internal IP, empty state, and
  readiness/error presentation.
- Manual External IP: no address, attach, PENDING (in-progress icon + "Attaching external IP..."), READY, DELETING, FAILED
  message with Detach-only recovery, list errors, empty selector, and
  mutation errors.
- Automatic External IP: spec flag with no `status.external_ip_address` (in-progress icon + "Attaching external IP..."),
  READY with the Auto badge, FAILED, no fabricated address before READY, and no Detach action for
  an automatic attachment.

---

## Provenance

Authored: revise @ ui-design 0.1.0 - 7b2b8de, workspace OSAC-6054-catalog-item-authoring @ ef918eea4 (60 behind origin/main)
Final: respond @ ui-design 0.1.0 - 7b2b8de (dirty), workspace bugfix/OSAC-7675-catalog-launch-routes-main @ ac9337bb1 (dirty)

> Context changed between revise and respond.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"7b2b8de (dirty)","source_repo":"ac9337bb1 (dirty)","source_repo_branch":"bugfix/OSAC-7675-catalog-launch-routes-main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
