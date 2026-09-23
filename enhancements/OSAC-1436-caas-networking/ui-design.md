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
cluster provisioning wizard's Networking step, cluster detail page endpoint and
networking display, auto-provisioned resource indicators in existing networking
list pages, and cluster deletion confirmation for auto-provisioned cleanup.

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

**Layout** (top to bottom):

1. **NetworkAttachmentPickers** (shared component)
2. **Auto External IP Attachment** toggle (cluster-specific)
3. **Pod CIDR** and **Service CIDR** text inputs (existing, unchanged)

**NetworkAttachmentPickers** renders three cascading pickers bound to the
cluster adapter's Formik paths:

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

**Auto External IP Attachment** (`SwitchField`): toggle below the pickers.
Default: off. When enabled, the fulfillment-service auto-provisions ExternalIPs
and ExternalIPAttachments for both API server and ingress endpoints
([design.md](/enhancements/OSAC-1436-caas-networking/design.md)).
Helper text: "Automatically provision external IPs for the cluster API and
ingress endpoints."

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

When all pickers are empty, `network_attachment` is omitted.
`auto_external_ip_attachment` is included only when `true`. The VN selection is
a UI-only filter not included in the payload — the API infers VN from the Subnet.

The VM adapter assembles `network_attachments: [{ subnet, security_groups }]`
(array); the cluster adapter assembles `network_attachment: { subnet,
security_groups }` (singular). Each adapter's `buildCreatePayload` reads the
same Formik values from the shared pickers.

**Review step** additions (via `adapter.getReviewSections()`):
- **Virtual Network**: selected VN name, or "Default" when omitted
- **Subnet**: selected Subnet name, or "Default" when omitted
- **Security Groups**: comma-separated SG names, or "Default" when omitted
- **Auto External IP**: "Enabled" or omitted when disabled

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

#### Cluster List Page

No changes to the cluster list page. Cluster networking details (subnet,
security groups, endpoints) are available on the cluster detail page only.

#### Cluster Deletion Confirmation

When `cluster.auto_external_ip_attachment == true`, the deletion confirmation
dialog adds:

> "Deleting this cluster will also delete the auto-provisioned External IPs and
> External IP Attachments associated with it. Manually created networking
> resources are not affected."

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

**Cluster adapter** renders:
```tsx
<NetworkAttachmentPickers
  fieldPrefix="spec.network_attachment"
  sgRequired="when-non-default-vn"
  defaultVnName={defaultSubnet?.virtualNetworkName}
  allOptional={true}
  showCidr={true}
/>
<AutoExternalIpToggle />
<PodCidrInput />
<ServiceCidrInput />
```

### Hooks

**Reused:** `useVirtualNetworks()`, `useSubnets()`, `useSecurityGroups()`
(OSAC-1421), `useExternalIPs({ filter })`,
`useExternalIPAttachments({ filter })` (OSAC-1433).

**New:** `useDefaultSubnet()` — `Subnets.List` filtered by
`is_default == true`, cached on mount. Provides `defaultVnName` to
`NetworkAttachmentPickers`.

**Extended:** `useCluster()` response type adds `network_attachment`,
`auto_external_ip_attachment`, `api_endpoint`, `ingress_endpoint`.
`buildClusterCreatePayload` includes `network_attachment` (omitted when empty)
and `auto_external_ip_attachment` (included only when `true`).

### Status Labels and Components

- `ExternalIpAttachmentStatusLabel` — wrapper around
  `ResourceStatusLabel`/`StatusKind` for Pending/Ready states.
- `AutoProvisionedBadge` — PatternFly `Label` (compact, blue) with tooltip.
  Accepts `clusterName` prop.

### Test Fixtures

Add to `createMockConnectTransport.ts`:
- Cluster fixtures with/without `network_attachment` and
  `auto_external_ip_attachment`, with populated and empty endpoints.
- `auto-created` labeled ExternalIP and ExternalIPAttachment fixtures.
- Default Subnet fixture (`is_default == true`).

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
| `ClusterNetworkingStep` | Pickers with `allOptional={true}`, `sgRequired="when-non-default-vn"`; auto external IP toggle in payload; empty pickers omit `network_attachment`; `pod_cidr`/`service_cidr` unchanged |
| `VmNetworkingStep` | Existing tests pass after refactor to shared component |
| `ClusterDetailPage` | "Pending" endpoints; auto-provisioned section conditional on `auto_external_ip_attachment`; statuses rendered |
| `ClustersPage` | No new columns added; networking details on detail page only |
| `AutoProvisionedBadge` | Tooltip; delete disabled when parent exists; delete enabled when orphaned |
