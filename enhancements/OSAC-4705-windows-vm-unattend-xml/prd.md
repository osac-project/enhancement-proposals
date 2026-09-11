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
  `user_data` field — the same open-text field already used for Linux
  cloud-init data — or through the existing `user_data_secret` field, which
  references a tenant-owned secret containing the content; no new API
  parameters are introduced (`user_data_secret` was added in a prior change,
  PR #736, and is leveraged here as-is)
- When the ComputeInstance's DiskImage has a Windows guest OS family, the
  platform interprets `user_data` (or the content referenced by
  `user_data_secret`) as Unattend.xml content and delivers it to the guest as
  an answer file
- Both `user_data` and `user_data_secret` remain optional; if neither is
  supplied on a Windows VM, the VM boots without an answer file — no
  platform-generated default is substituted
- User data content handling, regardless of guest OS family or delivery
  method:
  - Inline `user_data` is returned as-is in GET responses
  - When `user_data_secret` is used, only the secret reference is returned,
    not the content — following the same pattern as KubeVirt's
    cloudInitNoCloud `userData` vs `userDataSecretRef`
  - `user_data_secret` is the recommended path for sensitive content (product
    keys, admin credentials) since it keeps the data opaque in API responses
  - Content is excluded from watch/event payloads, audit records, logs, and
    error messages
- Validation at creation time when the DiskImage guest OS family is Windows,
  regardless of delivery method:
  - Content must be well-formed XML, parsed with a securely configured parser
    that rejects DTD declarations and disables external entity resolution
  - When `user_data_secret` is used, the platform resolves the secret and
    validates the `userdata` entry the same way it validates inline
    `user_data`
  - Empty payloads are rejected when the field is present
- Immutability: both `user_data` and `user_data_secret` are fully immutable
  after ComputeInstance creation — whichever field is set at create time is
  final; no migration from inline to secret or vice versa is supported
- When `user_data_secret` is used, the platform reads the secret content at
  ComputeInstance creation time only; subsequent modifications to the
  referenced secret's content do not propagate to the running VM
- Secret constraints: shared-tenant secrets are rejected for
  `user_data_secret`; tenant-owned secrets may be reused across multiple
  ComputeInstances
- The CLI and UI offer both delivery options: inline content through the
  existing `user_data` mechanism (file-path flag in the CLI, text input in
  the UI creation form) and secret reference through the `user_data_secret`
  field
- API and user-facing documentation: Unattend.xml usage via both `user_data`
  and `user_data_secret`, sensitive-content handling, and the recommended
  path for different content types

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

- As a Cloud Provider Admin, I want `user_data` content excluded from
  watch/event payloads, audit records, logs, and error messages —
  regardless of guest OS family — so that credentials, product keys, or
  other secrets in cloud-init scripts or Unattend.xml answer files are not
  inadvertently leaked through operational channels. Inline `user_data` is
  returned in list, get, and create responses (the tenant chose the visible
  delivery path); when `user_data_secret` is used, only the secret reference
  is returned, not the content.
- As a Cloud Provider Admin, I want `user_data` validated as well-formed XML
  when the ComputeInstance's DiskImage is Windows, and rejected when the
  payload is empty, so that tenants cannot attach invalid answer files.
- As a Cloud Provider Admin, I want `user_data_secret` content validated the
  same way as inline `user_data` — including XML well-formedness when the
  DiskImage is Windows — so that validation is consistent regardless of
  delivery method.
- As a Cloud Provider Admin, I want shared-tenant secrets rejected for
  `user_data_secret` so that cross-tenant data leakage cannot occur through
  secret sharing.

### Cloud Infrastructure Admin

- Not affected by this feature.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to supply my organization's
  Unattend.xml via the `user_data` field when creating a Windows
  ComputeInstance so that the VM's first boot follows our standard
  configuration (locale, OOBE settings, users, licensing).
- As a Tenant Admin or Tenant User, I want to supply my organization's
  Unattend.xml via the `user_data_secret` field when creating a Windows
  ComputeInstance so that sensitive content (product keys, admin credentials)
  is not exposed in API responses.
- As a Tenant Admin or Tenant User, I want to reuse the same tenant-owned
  secret across multiple ComputeInstances so that I can maintain a single
  source of truth for our standard Unattend.xml.
- As a Tenant Admin or Tenant User, I want to create a Windows
  ComputeInstance without supplying `user_data` or `user_data_secret` so
  that an already-customized golden image boots without an extra answer file.
- As a Tenant Admin or Tenant User, I want creation to fail with a clear
  message if my Unattend.xml content is not well-formed XML or is empty —
  regardless of whether it was supplied inline or via a secret — so that I
  can correct the problem before re-submitting.
- As a Tenant Admin or Tenant User, I want `user_data` and
  `user_data_secret` to be immutable after ComputeInstance creation so that I
  can trust the VM's first-boot configuration will not change unexpectedly.
- As a Tenant Admin or Tenant User, I want to provide Unattend.xml content
  through the existing `user_data` input in the CLI and UI, or by
  referencing a secret through `user_data_secret`, so that both delivery
  options are available without new tooling.

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
