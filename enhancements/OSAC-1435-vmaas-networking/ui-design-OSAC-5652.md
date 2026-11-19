# UI Design — OSAC-5652

**Story:** OSAC-5652 — UIX - VMaaS Networking
**Parent:** OSAC-1435 — VMaaS Networking
**Updated:** 2026-11-19

## Summary

Extend the existing VM create wizard and details page with tenant networking.
The wizard uses the shared `NetworkAttachmentPickers` component with the VM
configuration of the Unified ui design: VirtualNetwork, Subnet, and Security
Groups are all required, sent as a `network_attachments` list, with the field
omitted when the tenant-default toggle is on (the field is optional; an
omitted or empty list falls through to the catalog default, and a locked
catalog field rejects any value the tenant sends). [Unified UI: Workload network attachment
pickers] [Handoff: CaaS Networking UX] [Design: OSAC-1435 VMaaS Networking]

The details page is a continuous layout. Its Networking section shows the
resolved VirtualNetwork, Subnet, Security Groups, internal IP, and — when
external access is configured — the External IP address as a plain read-only
value, with no badge and no attach or detach actions. The External IP is
managed entirely at create time; this story introduces no post-create IP
attachment UI. [Codebase: `osac-ui/libs/ui-components/src/components/vm/DetailsPage/`]

When auto-attach is selected at create time, the system creates and manages
the ExternalIPAttachment; the UI only displays the resulting address once it
is known. The VM remains usable if automatic external access fails.
[PRD: OSAC-1435 FR-3]

## UI elements by persona

### Tenant user

| Surface | Introduced or changed UI |
|---|---|
| VM create — Networking | Tenant default/custom network choice; VirtualNetwork → Subnet selection; Security Groups; Auto-attach external IP switch and helper text. |
| VM create — Review | Network choice, selected custom-network resources, and Auto attach external IP: Yes/No. |
| VM details — Networking | Read-only resolved network table with VirtualNetwork, Subnet, Security Groups, internal IP, and External IP value. |

### Tenant admin

Tenant admins use the same tenant-scoped create and details surfaces. They can
inspect the resolved network and External IP value but receive no provider-only
controls.

No additional UI is introduced for provider or infrastructure administrators
by this story.

## Behavior

### Create-time networking

- Use the shared networking step with the Unified UI VM configuration:
  all pickers required, `network_attachments` sent as a list, with the field
  omitted when the tenant-default toggle is on (the field is optional; an
  omitted or empty list falls through to the catalog default, and a locked
  catalog field rejects any value the tenant sends).
- Tenant default shows the resolved read-only VirtualNetwork, Subnet, and
  Security Groups. The default resources are listed filtered by
  `metadata.labels['osac.openshift.io/default'] == 'true'` per kind; the
  tenant UI cannot read the private `DefaultNetworkingReady` Tenant
  condition, so each default resource's `state` is shown instead, and the
  server's `FAILED_PRECONDITION` gate error is surfaced when defaults are
  not ready.
- Custom network requires a ready VirtualNetwork, then filters Subnets and
  Security Groups to that network, excluding automatic SecurityGroups (the
  server gate rejects a selected automatic SecurityGroup), and preserves
  readiness and tenant scope. The Subnet picker disables Subnets with public
  `status.compute_instance_supported == false` and shows their
  `compute_instance_unsupported_reason`; the details page shows the same
  reason via `NetworkReady=False` (`SubnetDoesNotSupportVMs`).
- If the catalog item locks `network_attachments`, the custom-network option
  is disabled and the field is omitted from the request; if it has an
  editable default, that default is preselected.
- Network configuration and the auto-attach choice are immutable after create.
- If the create is rejected by the server (for example `FAILED_PRECONDITION`
  for IPv4 pool exhaustion), the wizard shows the backend error; nothing is
  stored. [Design: OSAC-1433 §Automatic external access]

### External IP display

- The External IP address is shown in the details page Networking section as
  a plain read-only value, without any badge, indicator, or action. There are
  no attach, detach, retry, or choose-another controls anywhere in this story.
- The display source is the per-VM `ExternalIPAttachments` list filtered by
  `spec.compute_instance.id == "<vmID>"` (`target` is a protobuf `oneof`, so
  the filter path is `spec.compute_instance`, not `spec.target.compute_instance`),
  each with its `status.external_ip_address`. `ComputeInstance.status.external_ip_address`
  is only a summary of the most recent successful attach and is not a display
  source. When more than one attachment targets the VM, all of their
  addresses are listed.
- While the automatic attachment is not yet READY, no address is shown and no
  action is offered. Once READY, the address is displayed as a plain value.
- If the automatic ExternalIP or attachment FAILED, show the backend
  `status.message`; fabricate no address. The VM remains usable.
- A VM with no attachment shows no External IP value.

### Failure handling

The UI reads error reasons only from `ErrorInfo.reason`.
[Unified UI: error presentation]

| Operation | Failure | UI |
|---|---|---|
| Create VM | `FAILED_PRECONDITION`: Subnet or SecurityGroup not READY, tenant defaults not ready, IPv4 pool exhaustion | Wizard shows the backend error; nothing is stored. |
| Create VM | `INVALID_ARGUMENT`: SecurityGroup from another VirtualNetwork, missing tenant default | Wizard shows the backend error. |
| Delete VM | `FAILED_PRECONDITION`: a manual ExternalIPAttachment still targets the VM | Deletion confirmation names the blocking attachment. [Design: OSAC-1435 §Delete] |

### Auto-attach toggle

The wizard sets the Auto-attach toggle from the catalog item policy (default
or locked value), disables it when locked, and sends
`auto_external_ip_attachment` only when the tenant can edit it — the field is
`optional bool` so an omitted value falls through to the catalog default,
while a locked policy rejects any value the tenant sends. The backend stores
the ComputeInstance and the automatic ExternalIP (PENDING) in one transaction
and allocates it in parallel with VM provisioning; the automatic
ExternalIPAttachment is created only after the VM endpoint is ready and its
address is known. The UI does not create or replace this attachment.
[Design: OSAC-1435 §Create, §Automatic external access]

- Derive the displayed address from the per-VM attachment list (above) and
  the automatic ExternalIP (`ExternalIPs.List` filtered by
  `metadata.labels['osac.openshift.io/auto-created-for'] == "<vmID>"` or by
  name `auto-eip-<vmID>`), never from `ComputeInstance.status.external_ip_address`.
- Before the automatic attachment is READY, do not display an address. Once
  READY, show the allocated address as a plain value with no badge.
- `spec.auto_external_ip_attachment == true` with no `auto-eip-<vmID>` means
  provider networking is disabled; show that external access is unavailable.
- Keep the VM usable and fabricate no address on failure.

## Data and state

| UI need | Source |
|---|---|
| Auto-attach requested | `ComputeInstance.spec.auto_external_ip_attachment` |
| VM network details | `ComputeInstance.spec.network_attachments[0]` for the stored Subnet, VirtualNetwork, and Security Group references; `status.internal_ip_address` and `status.compute_network_attachment_statuses[]` for the live address (the status entry is cleared for a Halted VM). The `NetworkReady` condition appears in the existing conditions display. |
| External IP address | Per-VM `ExternalIPAttachments` list and each attachment's `status.external_ip_address` — the display source; `ComputeInstance.status.external_ip_address` holds only the most recent successful attach and is a summary, not a display source |
| Automatic pending/error | `ExternalIPAttachments` filtered to this VM plus `ExternalIPs.List` filtered by `metadata.labels['osac.openshift.io/auto-created-for'] == "<vmID>"` (or name `auto-eip-<vmID>`): a `FAILED` attachment or ExternalIP shows its `status.message` under the value field; no auto ExternalIP at all means provider networking is disabled (unavailable, not pending); otherwise no address is shown until READY |

Formik owns create-wizard values. Server responses own network and External IP
lifecycle state. No new route, global store, modal, or client-persisted
lifecycle state is needed. [Codebase: existing Formik and shared resource-hook patterns]

## Accessibility

- Use the existing translation hook and PatternFly controls.
- Keep status text adjacent to the External IP value.
- Announce transitions politely; use an assertive alert for actionable
  failures only.

## Testing

- Create wizard: tenant-default/custom selection, dependent filtering,
  validation, auto-attach switch, review value, immutable payload behavior.
- Details networking: resolved resources, internal IP, External IP value,
  empty state, and readiness/error presentation.
- External IP display: no address before the automatic attachment is READY,
  plain address once READY, FAILED `status.message` with no fabricated
  address, and no attach/detach controls on any state.
- Auto ExternalIP `FAILED` with no attachment → its message, no spinner.
- `spec.auto_external_ip_attachment == true` with no `auto-eip-<vmID>` (provider networking disabled) → unavailable.
- VM `FAILED` with the auto attachment not created → no address shown.
- Two attachments on one VM → both addresses listed.
- Catalog item locks `auto_external_ip_attachment` or `network_attachments` → control disabled and field omitted.
- Subnet with `compute_instance_supported == false` disabled in the picker.

---

## Provenance

Authored: revise @ ui-design 0.1.0 - 7b2b8de, workspace OSAC-6054-catalog-item-authoring @ ef918eea4 (60 behind origin/main)
Final: respond @ ui-design 0.1.0 - 7b2b8de (dirty), workspace bugfix/OSAC-7675-catalog-launch-routes-main @ ac9337bb1 (dirty)

> Context changed between revise and respond.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"7b2b8de (dirty)","source_repo":"ac9337bb1 (dirty)","source_repo_branch":"bugfix/OSAC-7675-catalog-launch-routes-main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
