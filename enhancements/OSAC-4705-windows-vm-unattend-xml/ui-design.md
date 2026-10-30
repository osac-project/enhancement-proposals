---
title: windows-vm-unattend-xml-ui
authors:
  - lsoffer
creation-date: 2026-10-29
last-updated: 2026-10-29
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

In scope:

- **Details:** User picks a guest OS (Linux, Windows, or Unspecified), then chooses a disk image from a list filtered to that OS.
- **Access & Initial run:** Step content depends on that choice—Windows shows Sysprep (Unattend.xml); Linux shows SSH key plus cloud-init. User can paste content, upload a file, or select a project secret.
- **Review:** Summarize sysprep or cloud-init without showing pasted inline content again.
- **VM details:** If the VM was created with a user-data secret only, show the secret name—not the file contents.

## Proposal

### Details (`VmGeneralStep`)

Add guest OS selection cards for Linux, Microsoft Windows, and Unspecified. Limit
the disk image list to the chosen OS and clear the current image if the user
switches OS (`GuestOsFamilyField.tsx`, `DiskImageField.tsx`).

### Access (`VmAccessStep`)

Read guest OS from the Details step. For Windows, show the Sysprep section from
UX: paste or upload Unattend.xml, or pick a project `USER_DATA` secret. For
Linux, show SSH public key and cloud-init with the same paste-or-secret pattern.
Use PatternFly source cards instead of radios in `UserDataField.tsx`; keep today’s
Formik fields and create payload.

### Review (`VmReviewStep`)

Under **Access & Initial run**, show rows that match the OS. Pasted inline content
appears as *Provided (hidden)*; a secret shows its name only.

### VM details (`VmUserDataCard`)

Use a Sysprep or cloud-init title by guest OS. When the VM only has
`user_data_secret`, link to the secret by name.

## Validation

On Windows, pasted or uploaded Unattend.xml must pass a client-side
well-formed XML check before the user can submit the create request.

## Failure Handling

- If uploading or reading an Unattend file fails, show a clear error on the Sysprep field.

## Test Plan

- **Details:**
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
  - Inline Unattend shows as *Provided (hidden)*.
  - Secret path shows the secret name and supply method.
- **VM details:** Secret-only VMs show the secret link, not the file contents.