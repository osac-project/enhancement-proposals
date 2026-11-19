---
title: vmaas-networking-ux
authors:
  - yfrimanm@redhat.com
creation-date: 2026-11-18
last-updated: 2026-11-18
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5652
see-also:
  - "/enhancements/OSAC-1435-vmaas-networking/prd.md"
  - "/enhancements/OSAC-1435-vmaas-networking/design.md"
  - "/enhancements/OSAC-1435-vmaas-networking/ui-design-OSAC-5652.md"
replaces:
superseded-by:
---

# VMaaS Networking — UX Design

---

## 1. Create VM — Networking

The Networking step offers **Tenant default** and **Custom network**. Tenant
default summarizes virtual network, subnet, and security groups.

The **Auto-attach external IP** toggle default and the network choice come
from the catalog item the VM is launched from. When the catalog item locks
`auto_external_ip_attachment` or `network_attachments`, the control is
disabled and the field is left out of the request.

Custom network lets the user choose a virtual network, subnet, and security
groups; the auto-attach external IP control remains visible. A VM has exactly
one network attachment and it cannot change after create, so there is no
"Additional networks" option.

![Create VM networking — custom network](assets/02-create-custom-network.png)

The Subnet picker shows each Subnet's name and IPv4 CIDR — there is no
tenant-facing VLAN. Subnets that do not support VMs
(`compute_instance_supported == false`) are disabled with their
`compute_instance_unsupported_reason`. Tenant defaults are tenant-wide, not
per-project, and the default SecurityGroup belongs only to the default
VirtualNetwork, so nothing is preselected for another VirtualNetwork; an
option is preselected only when exactly one option is listed.

---

## 2. External IP on VM Overview

The External IP address is displayed as a plain read-only value in the
networking area of VM Overview, alongside the resolved virtual network,
subnet, security groups, and internal IP. It carries no status label or
badge, and there are no attach, detach, retry, or choose-another actions:
the External IP is configured only at create time (via the Auto-attach
toggle) and is released only when the VM is deleted. External IP fields
carry the standard help text *Reachable where your provider routes it.* — an
ExternalIP is external to the VirtualNetwork, not necessarily
Internet-routable, and SSH access depends on the VM's SecurityGroups.

While the automatic attachment is not yet READY, no address is shown.
Attachment failure is shown as inline status text directly below the value:
a fixed message with no retry or job information. Do not present a failed
address as an attached IP. A VM with no attachment shows no External IP
value.

---

## 3. Out of scope

This handoff does not own Virtual networks list/create/detail (including its
pagination), External IP inventory, or subnet/security-group administration.
