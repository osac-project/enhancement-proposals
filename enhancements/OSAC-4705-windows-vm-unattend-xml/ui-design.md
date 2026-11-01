---
title: windows-vm-unattend-xml-ui
authors:
  - lsoffer
creation-date: 2026-10-29
last-updated: 2026-11-01
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4705
prd:
  - Windows VM Unattend.xml PRD: https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-4705-windows-vm-unattend-xml/prd.md
see-also:
  - https://redhat.atlassian.net/browse/OSAC-4705
  - Full-stack design: [design.md](design.md)
replaces:
  - N/A
superseded-by:
  - N/A
---

# UI Design — OSAC-4705

## Summary

Adapt the ComputeInstance create wizard and VM details page so first-boot
customization matches the selected DiskImage guest OS: **Sysprep / Unattend.xml**
for Windows and **cloud-init** for Linux. Delivery uses `user_data` (inline) and `user_data_secret` (`SecretType.USER_DATA`).

## Scope

Tenants creating a Windows VM can provide an Unattend.xml for first boot by pasting the file, uploading it, or choosing an existing project secret. The UI checks that uploaded or pasted XML is
well-formed before create is allowed.

## Proposal

### Compute configuration (`VmConfigurationStep`)

Add guest OS selection cards for Linux, Microsoft Windows, and Unspecified under
**Disk image**, with **Select the image reference** filtered to the chosen OS;
clear the image when the user switches OS. Move disk image from `VmGeneralStep`
into this step alongside instance type (`GuestOsFamilyField.tsx`,
`DiskImageField.tsx`).

### Access (`VmAccessStep`)

Read guest OS from the Compute configuration step. For Windows, show a Sysprep
section where the tenant can paste or upload Unattend.xml or pick a project
`USER_DATA` secret. For Linux, show SSH public key and cloud-init with the same
paste-or-secret pattern.

### Review (`VmReviewStep`)

On the last wizard step, under **Access & Initial run**, show these read-only
rows for Windows:

- **Access method** — how the tenant will reach the VM after create (for example
  _Password / RDP after create_).
- **Sysprep method** — how Unattend was supplied: paste, file upload, or secret
  (show the secret name when a secret was chosen).
- **Sysprep (Unattend.xml)** — _Provided (hidden)_ when the tenant pasted or
  uploaded XML; never show the file body on Review.

### VM details (`VmUserDataCard`)

Use a Sysprep or cloud-init title by guest OS. When the VM only has
`user_data_secret`, link to the secret by name.

## Validation

On Windows, pasted or uploaded Unattend.xml must be well-formed XML before the
tenant can submit the create request.

## Failure Handling

- If uploading or reading an Unattend file fails, show a clear error on the Sysprep field.

## Test Plan

- **Compute configuration:**
  - Choosing an OS filters the disk image list.
  - Changing OS clears an image that no longer matches.
- **Access (Windows):**
  - Sysprep section is shown.
  - User can upload a file, paste XML, or select a secret.
  - Well-formed XML is accepted.
  - Invalid XML shows a field error and blocks submit.
- **Access (Linux):**
  - SSH public key field is shown.
  - Cloud-init section is shown.
- **Review:**
  - **Access method**, **Sysprep method**, and **Sysprep (Unattend.xml)** rows appear under **Access & Initial run**.
  - Inline Unattend shows _Provided (hidden)_ on the third row; secret path shows the secret name on **Sysprep method**.
- **VM details:** Secret-only VMs show the secret link, not the file contents.
