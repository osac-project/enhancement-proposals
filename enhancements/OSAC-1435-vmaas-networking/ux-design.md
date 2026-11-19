---
title: vmaas-networking-ux
authors:
  - yfrimanm@redhat.com
creation-date: 2026-11-18
last-updated: 2026-11-19
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

![Create VM networking — tenant default](assets/01-create-default-network.png)

The **Auto-attach external IP** toggle default and the network choice come
from the catalog item the VM is launched from. When the catalog item locks
`auto_external_ip_attachment` or `network_attachments`, the control is
disabled and the field is left out of the request.

Custom network lets the user choose a virtual network, subnet, and security
groups. A VM has exactly one network attachment and it cannot change after create.

![Create VM networking — custom network](assets/02-create-custom-network.png)

The Subnet picker shows each Subnet's name and IPv4 CIDR.

---

## 2. VM details page

The details page shows two entries — the External IP and the Networking
entry, whose three fields are the resolved network resources:

- **External IP** — A plain read-only value.
- **Networking** — the resolved network fields as read-only entries:
  VirtualNetwork, Subnet, and Security Groups.

![VM details networking — read-only external IP and network](assets/03-vm-details-networking.png)
