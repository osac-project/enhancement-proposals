# Add a Dedicated Secret Type for Windows User Data

| Field | Value |
|-------|-------|
| Author(s) | Ygal Blum |
| Jira | https://redhat.atlassian.net/browse/OSAC-6781 |
| Service | VMaaS |
| Date | 2026-11-06 |

## Problem Statement

Tenant Admins and Tenant Users have no dedicated secret type for XML
intended as Windows user data: the generic USER_DATA category does not
distinguish that purpose from Linux cloud-init. A dedicated type lets
tenants store that XML separately and check its format before using it in
a VM request, without changing Linux user-data behavior.

## In Scope

- A dedicated Windows user-data secret type is available through the API
  and applicable existing CLI workflows. It stores caller-supplied XML
  intended as Windows user data separately from Linux USER_DATA; unrelated
  Linux USER_DATA behavior remains unchanged. Acceptance establishes XML
  well-formedness only, not that the content is a valid or usable
  Unattend.xml or Windows answer file.
- At secret creation, content is required and nonempty, and must be
  well-formed XML. DTD declarations are rejected; external entities are not
  expanded, and network or local-file resources are not resolved. Missing,
  empty, malformed, or prohibited content is rejected with actionable
  errors that do not expose secret contents. These are format and security
  checks only, not validation of Windows settings.
- Windows VM secret references support the new type while retaining
  VM-creation OS compatibility checks against the selected image.
- Existing tenant/project secret access boundaries remain unchanged: the
  secret must be in the same project, and shared-tenant references remain
  rejected. Resolved content is not exposed in VM responses or diagnostics.
- User documentation covers creating and using the new type for Windows
  VM requests, XML format/security restrictions, access and OS compatibility
  restrictions, and the limits of validation across API and applicable
  existing CLI workflows.

## Out of Scope

- Migration of existing secrets.
- Microsoft schema validation; Unattend-specific root, pass, or component
  checks; Windows-edition requirements; credentials, licensing, or other
  semantic validation. Well-formed XML does not guarantee successful guest
  customization.
- Generating or editing answer files for users, or changing Windows
  first-boot customization beyond integrating the new secret type.

## User Stories

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User with permission to create secrets in my
  project, I want to store my supplied XML intended as Windows user data
  using a dedicated secret type through the API or CLI so that I can
  distinguish its intended purpose from Linux cloud-init data before using
  it for a VM.
- As a Tenant Admin or Tenant User creating a Windows user-data secret, I
  want clear, content-free errors for missing, empty, malformed, or
  security-prohibited XML so that I can correct my submission without
  exposing credentials or product keys in diagnostics.
- As a Tenant Admin or Tenant User referencing a Windows user-data secret,
  I want VM creation to retain OS compatibility and project access checks
  so that I cannot attach an incompatible or unauthorized secret.
- As a Tenant Admin or Tenant User, I want documentation explaining secret
  creation, use with Windows VM requests, and the limits of XML validation
  so that I can prepare my XML without mistaking an accepted secret for a
  guarantee that Windows customization will succeed.

## Dependencies

- **Windows answer-file workflow (OSAC-4705):** Integration and user
  documentation remain aligned with its Windows VM secret-reference
  workflow and [XML validation/security contract](https://github.com/osac-project/enhancement-proposals/blob/87fcaaaf9390d471fa30c21cde004d0e3efe776e/enhancements/OSAC-4705-windows-vm-unattend-xml/prd.md).
