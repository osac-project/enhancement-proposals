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
- **Customization parity with Linux.** Linux VM tenants can supply user data
  at creation time for first-boot customization; Windows VM tenants have no
  equivalent self-service path.

Guest OS family (linux / windows) is determined by the DiskImage resource
(OSAC-2540), not by the ComputeInstance. Unattend.xml is a per-VM-creation
artifact — it customizes the first boot of a specific VM, not the image
itself.

## In Scope

- Supply Unattend.xml content when creating a Windows ComputeInstance via API,
  CLI, and UI; the field is optional
- If Unattend.xml is omitted, the VM boots without an answer file — no
  platform-generated default is substituted
- Answer file content is treated as sensitive: not returned in default list or
  get responses for the ComputeInstance
- Validation at creation time:
  - Accepted only when the ComputeInstance's DiskImage has a Windows guest OS
    family
  - Content must be well-formed XML
  - Empty payloads are rejected when the field is present
  - A documented maximum size is enforced
- CLI accepts a local file path for the Unattend.xml content (e.g.
  `--unattend-xml <path>`)
- UI provides upload or paste for Unattend.xml content during Windows VM
  creation
- API and user-facing documentation: Unattend.xml usage, size limits, and
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

- As a Cloud Provider Admin, I want Unattend.xml content treated as sensitive
  so that answer files containing passwords or product keys are not exposed
  when listing or retrieving ComputeInstances across tenants.
- As a Cloud Provider Admin, I want Unattend.xml rejected when the
  ComputeInstance's DiskImage is not Windows, when the content is not
  well-formed XML, when the payload is empty, or when it exceeds the platform
  size limit, so that tenants cannot attach invalid or unbounded payloads.

### Cloud Infrastructure Admin

- Not affected by this feature.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to supply my organization's
  Unattend.xml when creating a Windows ComputeInstance so that the VM's first
  boot follows our standard configuration (locale, OOBE settings, users,
  licensing).
- As a Tenant Admin or Tenant User, I want to create a Windows
  ComputeInstance without supplying an Unattend.xml so that an
  already-customized golden image boots without an extra answer file.
- As a Tenant Admin or Tenant User, I want creation to fail with a clear
  message if I supply an Unattend.xml for a non-Windows DiskImage, if the XML
  is malformed, if the content is empty, or if it exceeds the size limit, so
  that I can correct the problem before re-submitting.
- As a Tenant Admin or Tenant User, I want to provide Unattend.xml content via
  file upload or paste in the UI, or by referencing a local file path in the
  CLI, so that I can use my preferred workflow.

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
