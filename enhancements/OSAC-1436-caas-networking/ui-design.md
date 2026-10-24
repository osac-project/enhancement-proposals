---
title: caas-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-09-22
last-updated: 2026-10-22
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

## Contents

- [Summary](#summary)
- [Proposal](#proposal)
  - [Tenant Admin and Tenant User](#tenant-admin-and-tenant-user)
    - [Cluster networking step (wizard step 4)](#cluster-networking-step-wizard-step-4)
    - [Cluster detail page](#cluster-detail-page)
    - [Cluster deletion confirmation](#cluster-deletion-confirmation)
    - [Automatic resource indicators](#automatic-resource-indicators)
- [Failure Handling](#failure-handling)
- [Implementation Details](#implementation-details)
  - [Cluster adapter](#cluster-adapter)
  - [Hooks](#hooks)
  - [Status labels and components](#status-labels-and-components)
  - [ExternalIP management components](#externalip-management-components)
  - [Test fixtures](#test-fixtures)
  - [Component tests](#component-tests)

## Summary

The `osac-ui` pages for [CaaS networking](design.md) (OSAC-1436): the `network_attachment` pickers in the wizard's Networking step ([OSAC-1421](/enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/design.md)), the Cluster detail page's endpoints and external access, the delete dialog, and the marks on automatic resources. The wizard has no external-access toggle, because every Cluster gets [automatic external access](design.md#automatic-external-access).

The [rules for every networking page](/enhancements/OSAC-1433-unified-networking/ui-design.md#rules-for-every-networking-page) apply; `network_attachment` is fixed at Cluster creation. An **automatic resource** below is one with the label `osac.openshift.io/auto-created: "true"` ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access)); the UI never offers it for selection, deletion, or rule editing.

## Proposal

### Tenant Admin and Tenant User

#### Cluster networking step (wizard step 4)

`ClusterNetworkingStep` (`wizard/adapters/cluster/`) has two `FormSection`s and uses the [shared pickers](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers) with the [Cluster adapter](#cluster-adapter). Every field is optional, except that a selected VirtualNetwork requires a Subnet and a Subnet outside the tenant's default VirtualNetwork requires at least one SecurityGroup (client-side check); an omitted attachment gets the tenant defaults ([defaulting](/enhancements/OSAC-1433-unified-networking/design.md#network-attachment-field-presence-and-defaulting)).

**Infrastructure Networking:**

- **Use tenant default network** (`SwitchField`, [shared](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers)), on by default. On: the pickers are hidden. Off: `NetworkAttachmentPickers` is shown, bound to the cluster adapter's Formik paths. Turning it back on clears the picker values.
- The Subnet and SecurityGroup pickers stay disabled until a VirtualNetwork is selected. Subnets are filtered by `this.spec.virtual_network.id == "<selected-vn-id>"`, SecurityGroups likewise.
- The tenant's default VirtualNetwork is that of the default Subnet, loaded on mount by `useDefaultSubnet()`.

**Cluster Networking:** **Pod CIDR** and **Service CIDR** (`InputField`).

**Payload** (`buildClusterCreatePayload`). With a picker value:

```json
{
  "network_attachment": {
    "subnet": { "name": "<subnet-name>" },
    "security_groups": [{ "name": "<sg-name>" }]
  }
}
```

With the toggle on, or all pickers empty, `network_attachment` is omitted. The VirtualNetwork is a UI-only filter; the API takes it from the Subnet. The payload never has `auto_external_ip_attachment`.

**Review step** (`adapter.getReviewSections()`), derived from the assembled payload, not the toggle:

- **Infrastructure Networking:** **Network** is "Tenant default" when the payload has no `network_attachment`, else "Custom"; with "Custom", also **Virtual Network**, **Subnet**, and **Security Groups** (comma-separated).
- **Cluster Networking:** **Pod CIDR** and **Service CIDR**, each omitted when empty.

#### Cluster detail page

`ClusterDetailPage` at `/clusters/:id` has a **Networking** section:

- **Subnet:** the name of `cluster.network_attachment.subnet`, linked to its detail page.
- **Security Groups:** the names of `cluster.network_attachment.security_groups[]`, each linked, then the Cluster's [automatic SecurityGroup](design.md#automatic-cluster-securitygroup) (labels `osac.openshift.io/auto-created-for == "<cluster-id>"` and `osac.openshift.io/auto-created-kind == "cluster"`) with the **Auto** badge and no delete.
- **API Endpoint** and **Ingress Endpoint:** `cluster.api_endpoint` and `cluster.ingress_endpoint`; "Pending" with a spinner while empty and the Cluster is PROGRESSING, except the Ingress Endpoint of a Cluster without automatic ExternalIPs, which shows a dash; a dash in a terminal state. While the Cluster is PROGRESSING, the page shows the message of its `CLUSTER_CONDITION_TYPE_PROGRESSING` condition, which names an unfinished or failed endpoint step ([Endpoint status](design.md#endpoint-feedback-and-dns)).
- Each endpoint row shows its automatic ExternalIP (Name, address, `ExternalIpStatusLabel`, linked to the External IP list page), found by `this.metadata.labels["osac.openshift.io/auto-created-for"] == "<cluster-id>"` and the label `osac.openshift.io/auto-created-endpoint` (`api` or `ingress`), and the status of its automatic ExternalIPAttachment (`ExternalIpAttachmentStatusLabel`). With provider networking disabled, a Cluster has none; the row shows a dash.

Fetching: one `ExternalIPs.List` call filtered by that label (at most two results) and `useClusterEndpointAttachments(clusterId)`, shared with the subsection below; no per-row queries.

**External IP Management.** Each endpoint row (API, Ingress) lists the ExternalIPAttachments that target that endpoint, with the ExternalIP name, address, and status, and always offers **Attach External IP**:

- **Attach External IP** opens `AttachExternalIpModal`, whose ExternalIP picker uses the [Attach NAT Gateway](/enhancements/OSAC-1433-unified-networking/ui-design.md#natgateway-field-in-virtualnetwork) filter (ALLOCATED, not automatic, not a tenant default, no consumer). Confirm creates the ExternalIPAttachment with target `cluster: { id: <cluster-id> }` and `target_endpoint: API` (Ingress row: `INGRESS`).
- **Detach** (only for an ExternalIPAttachment that is not automatic) deletes it after confirmation; the ExternalIP stays. Automatic ExternalIPAttachments go with the Cluster.
- Changing an endpoint's ExternalIP is Detach, then Attach with another ExternalIP.

The cluster list page has no networking columns.

#### Cluster deletion confirmation

A manual ExternalIPAttachment blocks the Cluster delete ([deletion guard](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)). When such attachments exist, the dialog lists them and says:

> "Delete these External IP Attachments first; the cluster cannot be deleted while one exists."

The dialog always adds:

> "Deleting this cluster also deletes its automatic resources (its Security Group, External IPs, and External IP Attachments)."

#### Automatic resource indicators

On the **External IP**, **External IP Attachment**, and **Security Group** list pages:

- An automatic resource shows the **Auto** badge (`AutoProvisionedBadge`: PatternFly `Label`, compact, blue) next to its name, with the tooltip "Created automatically for \<kind\> \<name\>." The kind comes from the label `osac.openshift.io/auto-created-kind`, or, for an ExternalIPAttachment (which has no kind label), from its target: `cluster` → "cluster" (name from a cached `Clusters.List`), `compute_instance` → "virtual machine" (`ComputeInstances.List`), `baremetal_instance` → "bare-metal instance" (`BareMetalInstances.List`). The name is matched by the label `osac.openshift.io/auto-created-for`.
- Its row Delete action (and, for a SecurityGroup, **Edit rules**) is disabled, with the tooltip "This resource is managed by \<kind\> \<name\> and will be deleted when it is deleted."

## Failure Handling

[Unified UI failure rules](/enhancements/OSAC-1433-unified-networking/ui-design.md#failure-handling) apply (including `QueryErrorState` for List and Get failures). A create error shows as a form-level error on the Review step, which sends the request.

| Scenario | UI behavior |
|---|---|
| Create: a [creation gate](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates) or the [ExternalIPPool capacity check](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access) fails (`FAILED_PRECONDITION`), or a [defaulting rule](/enhancements/OSAC-1433-unified-networking/design.md#network-attachment-field-presence-and-defaulting) or [CaaS check](design.md#network-attachment-and-validation) fails (`INVALID_ARGUMENT`) | The error on the Review step. |
| Create: Subnet outside the default VirtualNetwork without SecurityGroups | Client-side error on the Networking step: "Security groups are required when using a non-default virtual network." |
| Delete: automatic resource cleanup fails | The Cluster stays DELETING while the backend retries; the detail page shows the message of its PROGRESSING condition, which names the blocking step; its automatic resources stay listed. |
| Detail: endpoints not yet known | "Pending" with a spinner and the PROGRESSING message; refreshed by query invalidation. |
| Detail: attach before the endpoint is ready, or with provider networking disabled | `FAILED_PRECONDITION` in the attach modal. |
| Detail: attach an ExternalIP already in use | `FAILED_PRECONDITION` in the attach modal, which stays open. |
| Detail: detach fails | Error in the confirmation modal; Detach stays available. |
| Detail: no ExternalIP to attach | Empty state: "No unattached External IPs available. Create one in Networking → External IPs." |

## Implementation Details

### Cluster adapter

Pickers: [Unified UI — Workload network attachment pickers](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers); the Cluster adapter is below.

```tsx
<FormSection title="Infrastructure Networking">
  <UseDefaultNetworkToggle />
  {!useDefaultNetwork && (
    <NetworkAttachmentPickers
      fieldPrefix="spec.network_attachment"
      sgRequired="when-non-default-vn"
      defaultVnId={defaultSubnet?.spec.virtual_network.id}
      allOptional={true}
      showCidr={true}
    />
  )}
</FormSection>
<FormSection title="Cluster Networking">
  <PodCidrInput />
  <ServiceCidrInput />
</FormSection>
```

### Hooks

- From OSAC-1421: `useVirtualNetworks()`, `useSubnets()`, `useSecurityGroups()`.
- From the [Unified UI design](/enhancements/OSAC-1433-unified-networking/ui-design.md#implementation-details): `useExternalIPs({ filter })`, `useExternalIPAttachments({ filter })`, `useCreateExternalIPAttachment()`, `useDeleteExternalIPAttachment()`. After a create or delete, the CaaS pages also invalidate `useClusterEndpointAttachments`.
- `useDefaultSubnet()`: `Subnets.List` filtered by `this.metadata.labels['osac.openshift.io/default'] == 'true'`, cached on mount; gives `defaultVnId`.
- `useClusterEndpointAttachments(clusterId)`: `ExternalIPAttachments.List` filtered by the `cluster` target, grouped by `target_endpoint` into `{ api: ExternalIPAttachment[], ingress: ExternalIPAttachment[] }`; the query key includes the Cluster ID.
- `useCluster()` returns `network_attachment`, `api_endpoint`, and `ingress_endpoint`.

### Status labels and components

- `ExternalIpAttachmentStatusLabel`: from the [Unified UI design](/enhancements/OSAC-1433-unified-networking/ui-design.md#implementation-details) (PENDING, READY, FAILED, DELETING).
- `AutoProvisionedBadge` ([indicators](#automatic-resource-indicators)): props `ownerKind` and `ownerName`.

### ExternalIP management components

```text
apps/osac-ui/src/pages/clusters/detail/
  ExternalIpManagementSection.tsx
  ExternalIpManagementSection.test.tsx
  AttachExternalIpModal.tsx
  AttachExternalIpModal.test.tsx
```

- `ExternalIpManagementSection`: one row per endpoint, as in [Cluster detail page](#cluster-detail-page); uses `useClusterEndpointAttachments(clusterId)` and `useExternalIPs({ filter })`.
- `AttachExternalIpModal`: a `SelectField` with the ExternalIP filter above, showing Name and address; on confirm, `useCreateExternalIPAttachment()` with the ExternalIP, the `cluster` target and `target_endpoint`; empty state when none fits. Same modal pattern as Attach NAT Gateway.

### Test fixtures

`createMockConnectTransport.ts` serves:
- Clusters with and without `network_attachment`, with known and empty endpoints, with and without automatic ExternalIPs;
- automatic ExternalIPs, ExternalIPAttachments, and SecurityGroups for each `auto-created-kind`;
- a default Subnet (label `osac.openshift.io/default: "true"`);
- ExternalIPs that are ALLOCATED and unused, and ones used by an ExternalIPAttachment or a NATGateway;
- ExternalIPAttachments with `target_endpoint: API` and `target_endpoint: INGRESS`.

### Component tests

**Shared:** [Unified UI — Component tests](/enhancements/OSAC-1433-unified-networking/ui-design.md#component-tests).

**Adapter-specific:**

| Suite | Coverage |
|-------|----------|
| `ClusterNetworkingStep` | Two FormSections; toggle on by default hides the pickers; toggle off shows them with `allOptional={true}` and `sgRequired="when-non-default-vn"`; toggle back on clears them; no external-access toggle and no `auto_external_ip_attachment` in the payload; `pod_cidr` and `service_cidr` in Cluster Networking; each [Review step](#cluster-networking-step-wizard-step-4) label case |
| `VmNetworkingStep` | "Use tenant default network" toggle on by default hides the pickers and omits the attachment; toggle off renders the shared pickers with `sgRequired="always"` |
| `ClusterDetailPage` | Endpoints, "Pending" and the PROGRESSING message while empty; automatic ExternalIP and attachment status per row, or a dash; automatic SecurityGroup with the Auto badge and no delete |
| `ExternalIpManagementSection` | Attach always shown; Detach for manual attachments only; several attachments per endpoint listed |
| `AttachExternalIpModal` | Only ALLOCATED, non-automatic, unused ExternalIPs listed; confirm creates the attachment with the `cluster` target and `target_endpoint`; server error in the modal; empty state |
| Cluster deletion dialog | Manual-attachment warning when manual attachments exist; automatic-resource note always |
| `ClustersPage` | No networking columns |
| `AutoProvisionedBadge` | Tooltip text and name lookup per kind (ExternalIPAttachment: its target kind); Delete disabled on the three list pages |
