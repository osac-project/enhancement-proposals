# UI Design — OSAC-5652

**Story:** OSAC-5652 — UIX - VMaaS Networking
**Parent:** OSAC-1435 — VMaaS Networking
**Updated:** 2026-11-04

## Summary

Extend the existing VM create wizard and details page with tenant networking.
The wizard follows the shared CaaS Networking interaction model for tenant
default or custom networks, dependent VirtualNetwork/Subnet selection, and
Security Groups. [Handoff: CaaS Networking UX] [Design: OSAC-1435 VMaaS Networking]

The current details page is a continuous layout. Its Networking section shows
the resolved VirtualNetwork, Subnet, Security Groups, and internal IP. The
Access & Initial run section shows the External IP value and owns manual attach
and detach actions. [Codebase: `osac-ui/libs/ui-components/src/components/vm/DetailsPage/`]

Auto-attachment is a separate create-time flow. When selected, the UI shows
the address as auto-attached once the system-created ExternalIPAttachment is
READY. The VM remains usable if automatic external access fails. [PRD: OSAC-1435 FR-3]

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
controls; External IP pools and shared network-resource management remain on
their existing networking pages. [PRD: OSAC-1435 tenant-admin stories]

No additional UI is introduced for provider or infrastructure administrators
by this story.

## Behavior

### Create-time networking

- Use the shared CaaS Networking step without a VM-specific interaction model.
- Tenant default shows the resolved read-only VirtualNetwork, Subnet, and
  Security Groups.
- Custom network requires a ready VirtualNetwork, then filters Subnets and
  Security Groups to that network and preserves readiness and tenant scope.
- Network configuration and the auto-attach choice are immutable after create.

### External IP without auto-attachment

- A running VM with no External IP shows `Attach external IP`.
- Attach opens the existing selector for allocated, unattached, tenant-visible
  ExternalIPs and creates an ExternalIPAttachment targeting the VM.
- PENDING shows attaching progress; READY shows the address and `Detach`.
- Detach confirms deletion and shows DELETING until the attachment disappears.
- FAILED shows the backend message and the approved recovery actions for a
  manually created attachment: Retry or Choose another.
- Loading, list errors, empty selector results, and mutation errors remain
  visible and accessible.

### External IP with auto-attachment

The wizard sends `spec.auto_external_ip_attachment=true`. The backend then
allocates an automatic ExternalIP and creates an automatic
ExternalIPAttachment after the VM is running, ready, and its address is known.
The UI does not create or replace this attachment. [Design: OSAC-1435 §Automatic external access]

- Derive the requested state from the immutable ComputeInstance spec and read
  the VM-targeted ExternalIPAttachment from the existing filtered list query.
- Before the automatic attachment is READY, do not display an address or offer
  manual Attach, Retry, Choose another, or Detach actions. The UI does not
  claim a provisioning state that the current API cannot identify reliably.
- When the automatic attachment is READY, show its allocated address with
  `Auto attached`. Do not offer Detach: automatic resources are system-owned
  and are removed with the VM.
- If the automatic ExternalIP or attachment fails, show the available backend
  failure message, keep the VM usable, and keep manual replacement actions
  unavailable. The system-owned provisioning lifecycle remains responsible for
  retrying or cleaning up the automatic resource.
- Never display an address until the API reports it as allocated and attached.

## Data and state

| UI need | Source |
|---|---|
| Auto-attach requested | `ComputeInstance.spec.auto_external_ip_attachment` |
| VM network details | `ComputeInstance.status.compute_network_attachment_statuses[]`, `status.internal_ip_address`, plus Subnet, VirtualNetwork, and Security Group lookups |
| External IP address | `ComputeInstance.status.external_ip_address` or `ExternalIPAttachment.status.external_ip_address` once READY |
| Attachment lifecycle | `ExternalIPAttachments`, filtered to the current ComputeInstance; use `metadata.labels`, `status.state`, and `status.message` |
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
- Manual External IP: no address, attach, PENDING, READY, DELETING, FAILED,
  retry/choose-another, list errors, empty selector, and mutation errors.
- Automatic External IP: spec flag with no attachment, PENDING, READY with
  `Auto attached`, FAILED, no fabricated address before READY, and no Detach
  action for an automatic attachment.

## Acceptance criteria

- The VM Networking wizard matches the shared CaaS interaction and filtering
  model and supports tenant default or custom networking.
- The VM details page shows resolved network resources and internal IP in the
  Networking section.
- Manual External IP attach and detach expose the required lifecycle and error
  states without broadening tenant scope.
- Selecting auto-attach creates no manual UI action: the details page shows no
  address before READY, then shows the allocated address with `Auto attached`;
  automatic attachments cannot be detached by the tenant.
- Automatic external-access failure is visible without blocking VM use or
  fabricating an address.
- Network configuration and auto-attach remain immutable after VM creation;
  no new route is introduced.

## Constraints and open questions

- IPv4 only; no unsupported IPv6 or dual-stack behavior is implied.
- A VM has at most one tenant network attachment.
- Tenant isolation and readiness are enforced by the API; the UI must preserve
  the supplied tenant/project filters.
- Confirm during API review how an automatic ExternalIP allocation failure is
  surfaced when no ExternalIPAttachment exists yet. [Design: OSAC-1435 automatic external access]

---

## Provenance

Authored: revise @ ui-design 0.1.0 - 7b2b8de, workspace OSAC-6054-catalog-item-authoring @ ef918eea4 (60 behind origin/main)
Final: revise @ ui-design 0.1.0 - 7b2b8de (dirty), workspace main @ c5cbb7669

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"7b2b8de (dirty)","source_repo":"c5cbb7669","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
