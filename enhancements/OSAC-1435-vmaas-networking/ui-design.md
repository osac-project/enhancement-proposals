---
title: vmaas-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-11-19
last-updated: 2026-11-19
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5652
  - https://redhat.atlassian.net/browse/OSAC-1435
see-also:
  - "/enhancements/OSAC-1435-vmaas-networking/ux-design.md"
  - "/enhancements/OSAC-1435-vmaas-networking/prd.md"
  - "/enhancements/OSAC-1435-vmaas-networking/design.md"
replaces:
superseded-by:
---

# VMaaS Networking — UI Design Addendum

This addendum maps the [UX design](ux-design.md) to the `osac-ui`
implementation. It changes no UX decisions; it records where each screen
lives and which API field each UI item reads or writes. [OSAC-5652;
OSAC-1435 design §UX Alignment]

## 1. Create VM wizard — Networking step

Implemented in the existing VM create wizard's Networking step:

- **Tenant default / Custom network** choice, the summarized default
  (VirtualNetwork, Subnet, SecurityGroups), and the Custom pickers follow
  the UX design.
- **Auto-attach external IP** default and the network choice come from the
  catalog item the VM is launched from; when the catalog item locks the
  field, the toggle is disabled and the field is omitted from the request.
- The network selection is immutable after create; the UI offers no edit
  and directs the user to replace the VM.

## 2. VM details page

- **External IP** renders the attached ExternalIP as a read-only value.
- **Networking** renders the resolved network fields as read-only entries.

## 3. Field mapping

| UI item | Screen | API field | Direction |
|---|---|---|---|
| Tenant default / Custom network choice | Wizard, Networking step | `ComputeInstance.spec.network_attachments` presence (omitted = tenant default) | write |
| VirtualNetwork picker | Wizard, Networking step | `ComputeInstance.spec.network_attachments[0].subnet` → owner VirtualNetwork | write |
| Subnet picker (name + IPv4 CIDR) | Wizard, Networking step | `ComputeInstance.spec.network_attachments[0].subnet` | write |
| SecurityGroups picker | Wizard, Networking step | `ComputeInstance.spec.network_attachments[0].security_groups` | write |
| Auto-attach external IP toggle | Wizard, Networking step | `ComputeInstance.spec.auto_external_ip_attachment` | write |
| Second network attachment | Wizard, Networking step | rejected by the CLI before sending (max one entry) | — |
| External IP value | VM details | attached ExternalIP from `ExternalIPAttachments` / `ExternalIPs` | read |
| Networking — VirtualNetwork | VM details | `ComputeInstance.status.compute_network_attachment_statuses[0].subnet_ref` → owner VirtualNetwork | read |
| Networking — Subnet | VM details | `ComputeInstance.status.compute_network_attachment_statuses[0].subnet_ref` | read |
| Networking — SecurityGroups | VM details | `ComputeInstance.spec.network_attachments[0].security_groups` (resolved) | read |
| Networking — IP address | VM details | `ComputeInstance.status.internal_ip_address` | read |

## 4. Errors on VM create

An error returned by the VM create call is shown in the wizard footer.

## 5. Out of scope

Post-create status visibility — error handling and in-progress information
such as network assignment and external IP attachment in progress or
failed, and the VM Details provisioning stepper — is part of the VM status
visibility outcome ([OSAC-6578](https://redhat.atlassian.net/browse/OSAC-6578))
and is covered by:

- [Expose ComputeInstance Provisioning Failures During Retries](/enhancements/OSAC-6008-expose-computeinstance-provisioning-failures/prd.md)
  (Carlo Lobrano, [OSAC-6008](https://redhat.atlassian.net/browse/OSAC-6008))
- [Open PR: Expose VM configuration operation status across UI, API, and CLI](https://github.com/osac-project/enhancement-proposals/pull/466)
  ([OSAC-7158](https://redhat.atlassian.net/browse/OSAC-7158))
- [Show VM provisioning progress and failures](https://redhat.atlassian.net/browse/OSAC-7681)
  ([OSAC-7681](https://redhat.atlassian.net/browse/OSAC-7681)) — the VM
  Details provisioning stepper

No protobuf, endpoint, RBAC, or persistence changes. All data comes from
the existing `ComputeInstances` create/get contract.
