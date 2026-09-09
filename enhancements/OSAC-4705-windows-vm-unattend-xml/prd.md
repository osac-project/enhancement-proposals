# Create Windows VMs with a Caller-Supplied Unattend.xml

| Field       | Value   |
|-------------|---------|
| Author(s)   | OSAC Team |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4705 |
| Service     | VMaaS |
| Date        | 2026-09-08 |

## Problem Statement

Windows first-boot customization relies on an Unattend.xml answer file — the
Windows equivalent of Linux cloud-init user data. Tenants who create Windows
VMs through OSAC today cannot supply their own Unattend.xml via the API, CLI,
or UI. This blocks several real-world workflows:

- **Organization-standard answer files.** Tenant organizations that mandate
  specific locale, product-key, skip-OOBE, or local-user settings cannot
  enforce those standards through OSAC — they must ask the cloud operations
  team to modify platform-level automation on their behalf.
- **Golden-image clones.** Pre-configured Windows images that require a
  specific Unattend.xml at first boot cannot be paired with the right answer
  file at creation time.
- **Customization parity with Linux.** Linux VM tenants supply cloud-init
  scripts through the ComputeInstance `user-data` field at creation time;
  Windows VM tenants have no equivalent self-service path for Unattend.xml
  through that same field.

Guest OS family (linux / windows) is determined by the DiskImage resource
(OSAC-2540), not by the ComputeInstance. Unattend.xml is a per-VM-creation
artifact — it customizes the first boot of a specific VM, not the image
itself.

## In Scope

- Tenants supply Unattend.xml content through the existing ComputeInstance
  `user-data` field — the same open-text field already used for Linux
  cloud-init data; no new API parameters are introduced
- When the ComputeInstance's DiskImage has a Windows guest OS family, the
  platform interprets `user-data` as Unattend.xml content and delivers it to
  the guest as an answer file
- The `user-data` field remains optional; if omitted on a Windows VM, the VM
  boots without an answer file — no platform-generated default is substituted
- All `user-data` content is treated as sensitive, regardless of guest OS family:
  - Not returned in default list, get, or create responses for the
    ComputeInstance
  - Excluded from watch/event payloads, audit records, logs, and error
    messages
- Validation at creation time when the DiskImage guest OS family is Windows:
  - `user-data` content must be well-formed XML, parsed with a securely
    configured parser that rejects DTD declarations and disables external
    entity resolution
  - Empty payloads are rejected when the field is present
- The CLI and UI supply Unattend.xml through their existing `user-data`
  mechanisms (file-path flag in the CLI, text input in the UI creation form)
- API and user-facing documentation: Unattend.xml usage via `user-data` and
  sensitive-content handling

## Out of Scope

- Generating Unattend.xml from OSAC-managed fields (hostname, password,
  locale, timezone) — OSAC passes the caller's file as-is
- Visual Unattend.xml designer or form-based editor that authors XML for the
  user
- Validating Unattend.xml against Microsoft's full XML schema or
  Windows-edition requirements — only well-formedness is checked
- Windows ISO installation or golden-image build pipelines
- Shipping a default Windows disk image or Microsoft licenses
- Domain join, WSUS, or post-boot configuration management beyond what the
  user's own answer file contains
- Updating Unattend.xml on an existing VM after creation — this feature covers
  create-time only
- Image upload, scanning, and DiskImage CRUD (covered by OSAC-2540 and
  OSAC-979)

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want all `user-data` content treated as
  sensitive — regardless of guest OS family — so that credentials, product
  keys, or other secrets in cloud-init scripts or Unattend.xml answer files
  are not exposed in list, get, create, watch, or audit responses.
- As a Cloud Provider Admin, I want `user-data` validated as well-formed XML
  when the ComputeInstance's DiskImage is Windows, and rejected when the
  payload is empty, so that tenants cannot attach invalid answer files.

### Cloud Infrastructure Admin

- Not affected by this feature.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to supply my organization's
  Unattend.xml via the `user-data` field when creating a Windows
  ComputeInstance so that the VM's first boot follows our standard
  configuration (locale, OOBE settings, users, licensing).
- As a Tenant Admin or Tenant User, I want to create a Windows
  ComputeInstance without supplying `user-data` so that an
  already-customized golden image boots without an extra answer file.
- As a Tenant Admin or Tenant User, I want creation to fail with a clear
  message if my `user-data` content is not well-formed XML or is empty on a
  Windows VM, so that I can correct the problem
  before re-submitting.
- As a Tenant Admin or Tenant User, I want to provide Unattend.xml content
  through the existing `user-data` input in the CLI and UI so that no new
  tooling or flags are required.

## Assumptions

- Guest OS family (linux / windows) is available on the DiskImage resource at
  ComputeInstance creation time, enabling the platform to determine whether an
  Unattend.xml is valid for a given VM.
- OSAC does not validate the semantic correctness of the Unattend.xml content
  against the Windows installation it will configure — if the file is
  well-formed XML but contains incorrect settings, the error surfaces at
  Windows first boot, not at VM creation.

## Dependencies

- **OSAC-2540 (DiskImage resource):** Guest OS family (linux / windows) is a
  property of the DiskImage, not the ComputeInstance. This feature relies on
  the DiskImage's guest OS family to enforce the Windows-only constraint for
  Unattend.xml.
