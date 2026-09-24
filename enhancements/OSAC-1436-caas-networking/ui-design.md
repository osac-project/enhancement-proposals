---
title: caas-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-09-22
last-updated: 2026-09-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1436
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1436-caas-networking/design.md"
  - "/enhancements/OSAC-1433-unified-networking/ui-design.md"
  - "/enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/design.md"
replaces:
superseded-by:
---

# CaaS Networking — UI Design Addendum

## Summary

Extends the accepted backend design in [design.md](design.md) with the
`osac-ui` work for OSAC-1436: tenant-controlled cluster networking via the
cluster provisioning wizard's Networking step, cluster detail page endpoint
display and per-endpoint External IP attach/detach management,
auto-provisioned resource indicators in existing networking list pages, and
cluster deletion confirmation for auto-provisioned cleanup.

The cluster provisioning wizard
([OSAC-1421](/enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/design.md))
defines a five-step flow (Catalog Item → General → Configuration → Networking →
Review) with the Networking step currently limited to optional `pod_cidr` and
`service_cidr` fields. This design extends that step with `network_attachment`
fields (VN → Subnet → Security Group pickers) and an
`auto_external_ip_attachment` toggle, reusing shared picker components extracted
from the VM networking adapter. It also extends the cluster detail and list pages
to surface the new `api_endpoint`, `ingress_endpoint`, and resolved
`network_attachment` fields from the backend design.

All networking resources and the cluster `network_attachment` field follow the
unified create/read/delete contract: read uses List/Get, and changes require
delete and recreate. The `network_attachment` is immutable after cluster
creation — the UI does not provide an edit form for it.

## Shared Picker Design — `NetworkAttachmentPickers`

`VmNetworkingStep` (OSAC-1421) implements VN → Subnet → SG cascading pickers
but cannot be adopted wholesale for clusters due to four structural differences:

| # | Difference | VM | Cluster |
|---|-----------|-----|---------|
| 1 | Payload shape | `network_attachments` (array) | `network_attachment` (singular) |
| 2 | Optionality | All pickers required | All pickers optional (server defaults) |
| 3 | SG validation | Always required | Required only for non-default VN |
| 4 | Extra fields | None | `auto_external_ip_attachment`, `pod_cidr`, `service_cidr` |

The cascading picker logic is extracted into a shared `NetworkAttachmentPickers`
component in `libs/ui-components/` that both adapters consume:

| Aspect | Shared (`NetworkAttachmentPickers`) | VM adapter | Cluster adapter |
|--------|-------------------------------------|------------|-----------------|
| VN picker | `SelectField`, loads `useVirtualNetworks()` | Required | Optional |
| Subnet picker | `SelectField`, filtered by VN, loads `useSubnets()` | Required | Optional when VN empty; required when VN selected |
| SG multi-select | `MultiSelectField`, filtered by VN, loads `useSecurityGroups()` | Required | Required only for non-default VN |
| Cascade reset | Clearing VN resets Subnet + SGs | Same | Same |
| Auto-select | Single-option list auto-selects | Same | Same |
| Auto External IP | — | — | `SwitchField` below pickers |
| Pod/Service CIDR | — | — | `InputField` × 2 (existing) |
| Payload | — | `network_attachments: [{...}]` | `network_attachment: {...}` |

## Proposal

### Tenant User

#### Cluster Networking Step (Wizard Step 4)

Extends `ClusterNetworkingStep` (`wizard/adapters/cluster/`) with
`network_attachment` pickers above the existing `pod_cidr`/`service_cidr`
fields. All new fields are optional — when omitted, the fulfillment-service
applies the tenant's default Subnet and SecurityGroup
([Default Networking PRD](/enhancements/OSAC-1433-default-networking/prd.md)).

The step is split into two visually distinct sections using
`FormSection` headings within the same wizard step form:

**Infrastructure Networking** (section heading):

- **Use tenant default network** (`SwitchField`): toggle at the top of the
  section. Default: on. When enabled, VN/Subnet/SG pickers are hidden — the
  fulfillment-service uses the tenant's default VirtualNetwork, Subnet, and
  SecurityGroup. When disabled, the full VN → Subnet → SG picker cascade is
  shown for custom network selection. This matches the bare metal wizard
  pattern and will also be added to the VM wizard.

When "Use tenant default network" is disabled, `NetworkAttachmentPickers`
(shared component) renders three cascading pickers bound to the cluster
adapter's Formik paths:

- **Virtual Network** (`SelectField`): loads from `useVirtualNetworks()`,
  displays Name and IPv4 CIDR. Optional — when left empty, tenant defaults are
  used. Clearing resets Subnet and Security Group pickers. Auto-selects when
  the list returns one option.

- **Subnet** (`SelectField`): loads from `useSubnets()` filtered by
  `this.spec.virtual_network.name == "<selected-vn-name>"`. Disabled until a
  VirtualNetwork is selected. Displays Name and IPv4 CIDR. Optional when VN is
  also empty; required when a VN is selected. Auto-selects when the filtered
  list returns one option.

- **Security Groups** (`MultiSelectField`): loads from `useSecurityGroups()`
  filtered by `this.spec.virtual_network.name == "<selected-vn-name>"`. Disabled
  until a VirtualNetwork is selected. Optional when the selected Subnet belongs
  to the tenant's default VirtualNetwork (server applies default SG). Required
  when the Subnet belongs to a non-default VirtualNetwork — validated
  client-side. The default VN is identified by loading the default Subnet
  (`is_default == true` from `Subnets.List`) on mount via `useDefaultSubnet()`
  and caching its VN reference. The shared component receives this as
  `defaultVnName` and uses it when `sgRequired` is `"when-non-default-vn"`.

- **Auto External IP Attachment** (`SwitchField`): toggle below the pickers.
  Default: off. When enabled, the fulfillment-service auto-provisions
  ExternalIPs and ExternalIPAttachments for both API server and ingress
  endpoints
  ([design.md](/enhancements/OSAC-1436-caas-networking/design.md)).
  Helper text: "Automatically provision external IPs for the cluster API and
  ingress endpoints."

**Cluster Networking** (section heading):

- **Pod CIDR** (`InputField`): existing field, unchanged.
- **Service CIDR** (`InputField`): existing field, unchanged.

**Payload assembly** (`buildClusterCreatePayload`):

When pickers have values:
```json
{
  "network_attachment": {
    "subnet": { "name": "<subnet-name>" },
    "security_groups": [{ "name": "<sg-name>" }]
  },
  "auto_external_ip_attachment": true
}
```

When "Use tenant default network" is enabled (or all pickers are empty),
`network_attachment` is omitted.
`auto_external_ip_attachment` is included only when `true`. The VN selection is
a UI-only filter not included in the payload — the API infers VN from the Subnet.

The VM adapter assembles `network_attachments: [{ subnet, security_groups }]`
(array); the cluster adapter assembles `network_attachment: { subnet,
security_groups }` (singular). Each adapter's `buildCreatePayload` reads the
same Formik values from the shared pickers.

**Review step** additions (via `adapter.getReviewSections()`):
- **Infrastructure Networking**:
  - **Network**: "Tenant default" when `network_attachment` is omitted from the
    payload (toggle on, or toggle off with all pickers empty); "Custom" only
    when `network_attachment` is included in the payload (toggle off and at
    least one picker has a value)
  - **Virtual Network**: selected VN name (shown only when custom)
  - **Subnet**: selected Subnet name (shown only when custom)
  - **Security Groups**: comma-separated SG names (shown only when custom)
  - **Auto External IP**: "Enabled" or omitted when disabled
- **Cluster Networking**:
  - **Pod CIDR**: entered value, or omitted when empty
  - **Service CIDR**: entered value, or omitted when empty

#### Cluster Detail Page

Extends `ClusterDetailPage` at `/clusters/:id`.

**Networking section** (new section or tab):

- **Subnet**: resolved name from `cluster.network_attachment.subnet`, linked to
  the Subnet detail page.
- **Security Groups**: resolved names from
  `cluster.network_attachment.security_groups[]`, each linked to the SG detail
  page.
- **Ingress Endpoint**: `cluster.ingress_endpoint` when populated; "Pending"
  with spinner when empty and cluster is provisioning; dash in terminal state.

**Auto-provisioned resources subsection** (visible only when
`cluster.auto_external_ip_attachment == true`):

- **API External IP**: fetched via `useExternalIPs()` filtered by
  `this.metadata.labels["osac.openshift.io/auto-created-for"] == "<cluster-id>"`,
  matched to the API target. Displays: Name, allocated address, status
  (`ExternalIpStatusLabel`). Linked to the External IP list page.
- **Ingress External IP**: same filter, matched to ingress target.
- **API ExternalIPAttachment**: status (`ExternalIpAttachmentStatusLabel` —
  Pending / Ready).
- **Ingress ExternalIPAttachment**: same pattern.

Fetching: one `ExternalIPs.List` call filtered by label (≤2 results) + one
`ExternalIPAttachments.List` call filtered by target reference (≤2 results). No
N+1 queries.

**External IP Management subsection** (per-endpoint attach/detach):

Provides post-creation per-endpoint External IP management following the
VM/NAT Gateway attach/detach pattern from
[OSAC-1433](/enhancements/OSAC-1433-unified-networking/ui-design.md). Each
endpoint row (API, Ingress) shows its current attachment state and offers a
state-dependent action:

- **API Endpoint** row:
  - **No ExternalIP attached:** displays "Not attached" with an **Attach
    External IP** action button. Opens a modal to select from unattached,
    allocated ExternalIPs (`useExternalIPs({ filter:
    'this.status.state == EXTERNAL_IP_STATE_ALLOCATED &&
    this.status.attached == false' })` — same ownership filter as OSAC-1433
    NAT Gateway attach). On confirm, calls `useCreateExternalIPAttachment()`
    with `target_endpoint: API` and `target_resource` referencing the cluster.
  - **ExternalIP attached:** displays the ExternalIP name, allocated address,
    and status (`ExternalIpStatusLabel`). Shows a **Detach** action button.
    On confirm (confirmation modal), calls `useDeleteExternalIPAttachment()`
    to delete the ExternalIPAttachment. The ExternalIP itself is not deleted —
    it returns to the unattached pool.

- **Ingress Endpoint** row: same pattern as API, with
  `target_endpoint: INGRESS`.

Changing an endpoint's ExternalIP is Detach (delete ExternalIPAttachment)
followed by Attach (create new ExternalIPAttachment) with a different
ExternalIP — not an in-place edit, matching the unified create/read/delete
contract.

Manually created ExternalIPAttachments are **not** auto-deleted on cluster
delete — they are detached and transition back to **Pending** status (the
backend removes the DNAT mapping but preserves the attachment resource). Only
auto-provisioned ones (created via `auto_external_ip_attachment`) are fully
cleaned up by the backend finalizer. The deletion confirmation dialog
mentions this distinction when both auto and manual attachments exist.

Fetching: `ExternalIPAttachments.List` filtered by target cluster reference
(≤2 results, one per endpoint). Shares the query cache with the
auto-provisioned resources subsection above.

#### Cluster List Page

No changes to the cluster list page. Cluster networking details (subnet,
security groups, endpoints) are available on the cluster detail page only.

#### Cluster Deletion Confirmation

When `cluster.auto_external_ip_attachment == true`, the deletion confirmation
dialog adds:

> "Deleting this cluster will also delete the auto-provisioned External IPs and
> External IP Attachments associated with it. Manually created External IP
> Attachments will be detached and return to Pending status."

No additional user action — the backend handles phased cleanup
(ExternalIPAttachments first, then ExternalIPs).

#### Auto-Provisioned Resource Indicators

Extends the **External IP** list page (`ExternalIpsListPage`) and the
**External IP Attachment** list page.

- Resources with label `osac.openshift.io/auto-created: "true"` display an
  **"Auto"** badge (`Label`, compact, blue) next to the Name column. Tooltip:
  "Auto-provisioned for cluster \<cluster-name\>." Cluster name resolved from
  `auto-created-for` label against a cached `Clusters.List` call.

- Auto-provisioned resources are **not deletable** while the parent cluster
  exists — row Delete action disabled with tooltip: "This resource is managed by
  cluster \<name\> and will be deleted when the cluster is deleted." Delete
  enabled when the parent cluster no longer exists (orphaned resource). The
  disable check uses the `auto-created-for` label resolved against a cached
  `Clusters.List` call.

## Failure Handling

| Scenario | UI behavior |
|---|---|
| Cluster create: selected Subnet not Ready | Server's `FAILED_PRECONDITION` shown as form-level error on Networking step. |
| Cluster create: SGs not in same VN as Subnet | Server's `INVALID_ARGUMENT` shown as form-level error on Networking step. |
| Cluster create: non-default VN Subnet without SGs | Client-side validation error: "Security groups are required when using a non-default virtual network." |
| Cluster create: ExternalIPPool exhausted | Server's `RESOURCE_EXHAUSTED` shown as form-level error on Review step. |
| Cluster create: no default Subnet configured | Server's `FAILED_PRECONDITION` shown as form-level error when network_attachment omitted. |
| Cluster create: BareMetalInstanceType missing fabric port | Server's `INVALID_ARGUMENT` shown as form-level error on Review step. |
| Cluster delete: auto-provisioned cleanup failure | Backend retries via finalizer. If permanently orphaned, resources appear in list pages with Delete enabled. |
| Cluster detail: endpoints not yet available | "Pending" with spinner; auto-refreshes via query invalidation. |
| Cluster detail: attach ExternalIP already consumed | Server's `FAILED_PRECONDITION` shown as form-level error in the attach modal. Modal stays open for retry with a different ExternalIP. |
| Cluster detail: attach ExternalIP to endpoint that already has one | Client-side guard: Attach button hidden when endpoint already has an ExternalIPAttachment. |
| Cluster detail: detach ExternalIPAttachment fails | Server error shown in the confirmation modal; Detach action stays available for retry. |
| Cluster detail: no unattached ExternalIPs available | Attach modal shows empty state: "No unattached External IPs available. Create one in Networking → External IPs." |
| Any List/Get failure | Existing `QueryErrorState` handling. |

## Implementation Details

### `NetworkAttachmentPickers` Component

```text
libs/ui-components/src/components/form/
  NetworkAttachmentPickers.tsx
  NetworkAttachmentPickers.test.tsx
```

```typescript
interface NetworkAttachmentPickersProps {
  /** Formik field path prefix. VM: "spec.network_attachments.0", Cluster: "spec.network_attachment" */
  fieldPrefix: string;
  /** When to require security group selection */
  sgRequired: 'always' | 'when-non-default-vn' | 'never';
  /** Default VN name for conditional SG validation (only for 'when-non-default-vn') */
  defaultVnName?: string;
  /** Whether all pickers are optional (cluster: true, VM: false) */
  allOptional?: boolean;
  /** Whether to show VN/Subnet IPv4 CIDR in picker options */
  showCidr?: boolean;
}
```

**Shared component owns:** VN/Subnet/SG pickers with data loading, cascade
reset, auto-select, conditional SG validation, loading/error states.

**Each adapter owns:** Formik field prefix, Yup schema fragment, payload shape
in `buildCreatePayload`, additional fields.

**VM adapter** replaces its inline picker implementation with:
```tsx
<NetworkAttachmentPickers
  fieldPrefix="spec.network_attachments.0"
  sgRequired="always"
  allOptional={false}
  showCidr={true}
/>
```
Existing `VmNetworkingStep.test.tsx` tests validate the refactor.

**Cluster adapter** renders two `FormSection`s within the step:
```tsx
<FormSection title="Infrastructure Networking">
  <UseDefaultNetworkToggle />
  {!useDefaultNetwork && (
    <NetworkAttachmentPickers
      fieldPrefix="spec.network_attachment"
      sgRequired="when-non-default-vn"
      defaultVnName={defaultSubnet?.virtualNetworkName}
      allOptional={true}
      showCidr={true}
    />
  )}
  <AutoExternalIpToggle />
</FormSection>
<FormSection title="Cluster Networking">
  <PodCidrInput />
  <ServiceCidrInput />
</FormSection>
```

### Hooks

**Reused:** `useVirtualNetworks()`, `useSubnets()`, `useSecurityGroups()`
(OSAC-1421), `useExternalIPs({ filter })`,
`useExternalIPAttachments({ filter })` (OSAC-1433).

**New:** `useDefaultSubnet()` — `Subnets.List` filtered by
`is_default == true`, cached on mount. Provides `defaultVnName` to
`NetworkAttachmentPickers`.

**New:** `useClusterEndpointAttachments(clusterId)` —
`ExternalIPAttachments.List` filtered by target cluster reference (≤2
results). Returns `{ api: ExternalIPAttachment | null, ingress:
ExternalIPAttachment | null }`. Used by both the auto-provisioned resources
subsection and the External IP Management subsection. Query key includes
cluster ID for cache isolation.

**New:** `useCreateExternalIPAttachment()` — mutation hook wrapping
`ExternalIPAttachments.Create`. Invalidates `useClusterEndpointAttachments`
and `useExternalIPs` query caches on success.

**New:** `useDeleteExternalIPAttachment()` — mutation hook wrapping
`ExternalIPAttachments.Delete`. Invalidates `useClusterEndpointAttachments`
and `useExternalIPs` query caches on success.

**Extended:** `useCluster()` response type adds `network_attachment`,
`auto_external_ip_attachment`, `api_endpoint`, `ingress_endpoint`.
`buildClusterCreatePayload` includes `network_attachment` (omitted when empty)
and `auto_external_ip_attachment` (included only when `true`).
`adapter.getReviewSections()` derives the Network label from the assembled
payload — not the toggle state — so that "Tenant default" is shown whenever
`network_attachment` is absent (toggle on, or toggle off with all pickers
empty) and "Custom" is shown only when a `network_attachment` object is
present.

### Status Labels and Components

- `ExternalIpAttachmentStatusLabel` — wrapper around
  `ResourceStatusLabel`/`StatusKind` for Pending/Ready states.
- `AutoProvisionedBadge` — PatternFly `Label` (compact, blue) with tooltip.
  Accepts `clusterName` prop.

### External IP Management Components

```text
apps/osac-ui/src/pages/clusters/detail/
  ExternalIpManagementSection.tsx
  ExternalIpManagementSection.test.tsx
  AttachExternalIpModal.tsx
  AttachExternalIpModal.test.tsx
```

- `ExternalIpManagementSection` — renders one row per endpoint (API, Ingress).
  Each row shows the current ExternalIPAttachment state and the
  state-dependent action (Attach / Detach). Consumes
  `useClusterEndpointAttachments(clusterId)` and `useExternalIPs({ filter })`
  for the attached ExternalIP details.

- `AttachExternalIpModal` — modal dialog for selecting an unattached
  ExternalIP. Renders a `SelectField` loaded from `useExternalIPs({ filter:
  'this.status.state == EXTERNAL_IP_STATE_ALLOCATED &&
  this.status.attached == false' })`. Displays Name and allocated address per
  option. On confirm, calls `useCreateExternalIPAttachment()` with the
  selected ExternalIP, `target_endpoint` (API or INGRESS), and the cluster
  target reference. Shows empty state when no unattached ExternalIPs exist.
  Follows the same modal pattern as OSAC-1433 NAT Gateway attach modal.

### Test Fixtures

Add to `createMockConnectTransport.ts`:
- Cluster fixtures with/without `network_attachment` and
  `auto_external_ip_attachment`, with populated and empty endpoints.
- `auto-created` labeled ExternalIP and ExternalIPAttachment fixtures.
- Default Subnet fixture (`is_default == true`).
- Unattached allocated ExternalIP fixtures for attach modal tests.
- ExternalIPAttachment fixtures with `target_endpoint: API` and
  `target_endpoint: INGRESS` for per-endpoint management tests.

### Component Tests

**Shared** (`NetworkAttachmentPickers.test.tsx`):

| Scenario | Assert |
|----------|--------|
| VN selection filters Subnet and SG lists | Options update on VN change |
| Clearing VN resets Subnet and SG values | Formik values cleared |
| Single-option list auto-selects | Value auto-selected |
| `sgRequired="always"` with empty SG | Validation error |
| `sgRequired="when-non-default-vn"` with default VN, empty SG | No error |
| `sgRequired="when-non-default-vn"` with non-default VN, empty SG | Validation error |
| `allOptional={true}` with all pickers empty | No errors |
| `allOptional={false}` with VN empty | Validation error |
| Loading and error states | Pickers disabled during load; error on failure |

**Adapter-specific:**

| Suite | Coverage |
|-------|----------|
| `ClusterNetworkingStep` | Two FormSections rendered ("Infrastructure Networking", "Cluster Networking"); "Use tenant default network" toggle on by default hides pickers; disabling toggle shows pickers with `allOptional={true}`, `sgRequired="when-non-default-vn"`; re-enabling toggle clears picker values; auto external IP toggle in Infrastructure section; `pod_cidr`/`service_cidr` in Cluster section; default-network-on omits `network_attachment`; review step shows "Tenant default" when toggle off and all pickers empty (payload omits `network_attachment`); review step shows "Custom" only when toggle off and at least one picker has a value |
| `VmNetworkingStep` | Existing tests pass after refactor to shared component |
| `ClusterDetailPage` | "Pending" endpoints; auto-provisioned section conditional on `auto_external_ip_attachment`; statuses rendered |
| `ExternalIpManagementSection` | Attach button shown when no attachment; Detach shown when attached; endpoint details rendered; empty state for no unattached IPs |
| `AttachExternalIpModal` | Unattached ExternalIPs listed; confirm creates ExternalIPAttachment with correct `target_endpoint`; server error displayed in modal; empty state message |
| `ClustersPage` | No new columns added; networking details on detail page only |
| `AutoProvisionedBadge` | Tooltip; delete disabled when parent exists; delete enabled when orphaned |
