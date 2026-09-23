# Design — OSAC-4705: Create Windows VMs with a Caller-Supplied Unattend.xml

| Field          | Value                                                  |
|----------------|--------------------------------------------------------|
| Feature        | [OSAC-4705](https://redhat.atlassian.net/browse/OSAC-4705) |
| PRD            | [enhancement-proposals PR #272](https://github.com/osac-project/enhancement-proposals/pull/272), [PR #286](https://github.com/osac-project/enhancement-proposals/pull/286) |
| Service        | VMaaS                                                  |
| Author(s)      | OSAC Team                                              |
| Status         | Draft                                                  |
| Date           | 2026-09-22                                             |

---

## 1. Overview

This design enables OSAC tenants to supply their own Windows Unattend.xml
answer file when creating a Windows ComputeInstance. The tenant's file is
delivered through the existing `user_data` (inline) or `user_data_secret`
(secret reference) fields — no new API surface is introduced. The platform
interprets the content as an Unattend.xml answer file when the
ComputeInstance's DiskImage has `guest_os_family = WINDOWS`, and delivers it to
the guest VM as a KubeVirt sysprep volume (SATA CD-ROM). If neither field is
supplied, the VM boots without any answer file.

The feature touches four layers of the OSAC stack:

1. **Fulfillment service** — adds guest-OS-family-aware XML validation at
   create time
2. **AAP provisioning role** — adds a code path to mount user-supplied content
   as a sysprep volume instead of a cloud-init volume
3. **CLI** — updates help text to document the Unattend.xml use case
4. **UI** — adapts the creation form to present Unattend.xml guidance when a
   Windows DiskImage is selected

The proto definitions, operator CRD, and reconciler require no changes — the
`user_data`, `user_data_secret`, and `guest_os_family` fields already exist.

---

## 2. Goals and Non-Goals

### Design-Scoped Goals (Implementation Constraints)

- G-1: XML validation uses Go's standard `encoding/xml` package exclusively — no
  third-party XML parsers.
- G-2: The AAP role continues to use the existing KubeVirt sysprep volume API
  (Secret + SATA CD-ROM) with no changes to the KubeVirt resource schema.
- G-3: No new proto fields, API parameters, or CLI flags are introduced.
- G-4: The platform-generated Jinja2 Unattend.xml template (`unattend.xml.j2`)
  is NOT rendered when user-supplied content is present; it is only used as a
  fallback when `vm_enable_sysprep` is true and no user data is supplied.
- G-5: XML validation is enforced consistently regardless of delivery method
  (inline `user_data` or resolved `user_data_secret` content).

### Non-Goals

- N-1: Generating Unattend.xml from OSAC-managed fields (hostname, password,
  locale).
- N-2: Validating Unattend.xml against Microsoft's full schema — only XML
  well-formedness is checked.
- N-3: Supporting Unattend.xml updates after ComputeInstance creation.
- N-4: Providing a visual XML editor or form-based Unattend.xml builder in the
  UI.

---

## 3. Motivation / Background

Linux VMs in OSAC accept cloud-init user data through the `user_data` field at
creation time, giving tenants full control over first-boot customization.
Windows VMs have no equivalent self-service path. The platform's AAP role
generates a default Unattend.xml from internal variables (`vm_sysprep_*`), but
tenants cannot supply their own.

This creates three concrete gaps:

1. **Organization-standard answer files** — tenant organizations with mandatory
   locale, product-key, skip-OOBE, or local-user settings cannot enforce those
   standards through OSAC.
2. **Golden-image clones** — pre-configured Windows images that require a
   specific Unattend.xml at first boot cannot be paired with the correct answer
   file at creation time.
3. **Customization parity** — Linux tenants get self-service first-boot
   customization; Windows tenants do not.

Guest OS family is determined by the DiskImage resource (OSAC-2540), not by the
ComputeInstance. Unattend.xml is a per-VM-creation artifact — it customizes the
first boot of a specific VM, not the image itself.

### 3.1 Technical Context

**KubeVirt sysprep volume mechanism.** KubeVirt delivers Windows answer files
through a dedicated `sysprep` volume type. The volume references a Kubernetes
Secret containing a key named `Unattend.xml`. KubeVirt attaches the volume as a
SATA CD-ROM disk, which Windows Setup reads during first boot. Since KubeVirt
v0.52.0, a Secret with only the `Unattend.xml` key (without `Autounattend.xml`)
is accepted. The existing AAP `ocp_virt_vm` role already uses this mechanism for
platform-generated sysprep.

**Existing AAP code paths (`create_secrets.yaml`).** The `ocp_virt_vm` role's
`create_secrets.yaml` currently implements three independent code paths:

| # | Condition | Behavior |
|---|-----------|----------|
| 1 | `guest_os=windows`, `vm_enable_sysprep=true`, no user data | Renders `unattend.xml.j2` Jinja2 template → creates Secret with key `Unattend.xml` → mounts as sysprep volume (SATA CD-ROM) |
| 2 | `vm_user_data_secret_ref` set (any OS) | Copies user data Secret → mounts as `cloudInitNoCloud` volume (virtio disk) |
| 3 | No user data, SSH key present (Linux) | Creates minimal `#cloud-config` for SSH key propagation |

**Missing fourth path.** No code path exists for the combination of
`guest_os_family == 'windows'` AND user-supplied data. Today, if a tenant
supplies `user_data` or `user_data_secret` for a Windows VM, path 2 fires and
the content is mounted as a `cloudInitNoCloud` volume — a Linux delivery
mechanism that Windows cannot consume. This feature adds a fourth path that
reads the tenant's content but delivers it through the sysprep volume machinery
(Secret with key `Unattend.xml`, SATA CD-ROM) instead of the cloud-init
machinery.

---

## 4. Design

### 4.1 Architecture

The change touches four components in the OSAC resource flow. The proto layer,
operator CRD, and reconciler are unaffected — all required fields already exist.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Client (CLI / UI / API)                                               │
│  - user_data (inline XML) or user_data_secret (secret ref)            │
│  - disk_image → guest_os_family (from DiskImage)                      │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Fulfillment Service                                                   │
│  ┌──────────────────────────────────────────────────┐                  │
│  │ Create / Validate                                │                  │
│  │  1. Resolve disk_image → guest_os_family         │                  │
│  │  2. If WINDOWS + user_data present:              │                  │
│  │     → Validate well-formed XML (encoding/xml)    │ ◄── NEW         │
│  │  3. If WINDOWS + user_data_secret present:       │                  │
│  │     → Resolve secret → validate userdata as XML  │ ◄── NEW         │
│  │  4. Existing: mutual exclusion                    │                  │
│  └──────────────────────────────────────────────────┘                  │
│                                                                       │
│  Reconciler (no changes — already passes user_data through)           │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Operator (no changes — CRD already has guestOSFamily,                 │
│                          userDataSecretRef)                            │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ AAP — ocp_virt_vm role                                                │
│  ┌──────────────────────────────────────────────────┐                  │
│  │ create_secrets.yaml                              │                  │
│  │                                                  │                  │
│  │  EXISTING path 1 (platform sysprep):             │                  │
│  │    guest_os=windows + sysprep=true + NO user data│                  │
│  │    → Render unattend.xml.j2 template             │                  │
│  │    → Create Secret with key Unattend.xml         │                  │
│  │    → Mount as sysprep volume (SATA CD-ROM)       │                  │
│  │                                                  │                  │
│  │  NEW path (user-supplied sysprep):               │ ◄── NEW         │
│  │    guest_os=windows + user data present          │                  │
│  │    → Read user data Secret                       │                  │
│  │    → Create Secret with key Unattend.xml         │                  │
│  │    → Mount as sysprep volume (SATA CD-ROM)       │                  │
│  │    → SKIP Jinja2 template rendering              │                  │
│  │                                                  │                  │
│  │  EXISTING path 2 (cloud-init):                   │                  │
│  │    guest_os=linux + user data present             │                  │
│  │    → Copy Secret + cloudInitNoCloud volume       │                  │
│  └──────────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

The architecture follows the existing resource flow. No new services, CRDs, or
inter-component contracts are introduced.

### 4.2 Data Model / Schema Changes

No schema changes are required. All fields already exist in the proto and CRD
definitions:

**Proto (`compute_instance_type.proto`):**
- `user_data` (field 11) — `optional string`, already defined
- `user_data_secret` (field 20) — `SecretLocalReference`, already defined
- `disk_image` (field 19) — `DiskImageReference`, already defined

**DiskImage proto (`disk_image_type.proto`):**
- `guest_os_family` (field 3) — `GuestOSFamily` enum with `LINUX` and `WINDOWS`
  values, already defined

**Operator CRD (`computeinstance_types.go`):**
- `GuestOSFamily string` — freeform string, immutable, already defined
- `UserDataSecretRef *corev1.LocalObjectReference` — already defined

**Secret proto (`secret_type.proto`):**
- `SECRET_TYPE_USER_DATA` (value 3) — with required `userdata` data key, already
  defined

### 4.3 API Changes

No new API parameters or endpoints. The behavioral change is in validation:

**New validation rule for ComputeInstance Create:**

When `disk_image.guest_os_family == WINDOWS`:
- If `user_data` is present: validate content as well-formed XML
- If `user_data_secret` is present: resolve the secret, then validate the
  `userdata` entry as well-formed XML
- If neither is present: no validation (VM boots without answer file)

When `disk_image.guest_os_family != WINDOWS`:
- No XML validation (content treated as opaque, same as today)

**XML validation specification:**

```go
func validateWellFormedXML(content string) error {
    decoder := xml.NewDecoder(strings.NewReader(content))
    for {
        _, err := decoder.Token()
        if err == io.EOF {
            return nil
        }
        if err != nil {
            return fmt.Errorf("user_data is not well-formed XML: %s", err.Error())
        }
    }
}
```

Go's `encoding/xml` package is inherently safe against XXE attacks — it does
not process external entities or DTD declarations. No additional parser
configuration is needed (see Research §RQ-1).

**Error messages:**
- `"user_data is not well-formed XML: <parser error details>"` — for inline
  `user_data` with malformed XML on a Windows DiskImage
- `"secret '<ref>' referenced by user_data_secret contains user data that is not well-formed XML"` — for `user_data_secret` with malformed XML content; error
  does not expose the secret content itself

### 4.4 Scalability and Performance

**Validation cost:** XML well-formedness checking via `xml.NewDecoder().Token()`
is O(n) in document size and runs in-process. For typical Unattend.xml files
(2–20 KB), validation completes in microseconds. No external service calls or
blocking operations are added to the create path.

**Secret resolution:** The existing `user_data_secret` resolution flow already
fetches and validates the secret at create time. Adding XML parsing to the
resolved content adds negligible overhead.

**AAP provisioning:** The change replaces one Secret creation operation with
another (user content vs. template content). The KubeVirt API call pattern is
identical. No additional provisioning latency is introduced.

### 4.5 Security Considerations

**XML External Entity (XXE) prevention:**
Go's `encoding/xml` does not process external entities or DTD declarations by
default. The parser:
- Does not fetch external resources during parsing
- Does not resolve external DTD references
- Does not expand parameter entities
- Has an empty `.Entity` map by default

This satisfies the PRD requirement for a "securely configured parser that
rejects DTD declarations and disables external entity resolution" without any
additional configuration.

**Secret content in error messages:**
When `user_data_secret` validation fails (malformed XML), the error message must
identify the secret reference but MUST NOT include the XML content. The error
format is: `"secret '<name>' referenced by user_data_secret contains user data that is not well-formed XML"`.

**Shared-tenant secret rejection:**
Already enforced by the existing `validateUserDataSecret()` function. No
changes needed.

**Content handling:**
- Inline `user_data` is returned in list/get/create responses (existing behavior)
- `user_data_secret` returns only the reference (existing behavior)
- Both are excluded from watch/event/audit/logs (existing behavior)
- `Cache-Control: no-store` for responses containing `user_data` (new — see §4.8)

### 4.6 Failure Handling and Recovery

**Validation failures (create-time):**
- Malformed XML → create rejected with descriptive error; no resources created
- Missing/empty `userdata` key in secret → create rejected (existing behavior)
- Secret not found → create rejected (existing behavior)

**AAP provisioning failures:**
- Secret creation failure in VM namespace → AAP job fails; operator retries via
  standard reconciliation loop
- Volume mount failure → KubeVirt VMI fails to start; surfaced through
  operator conditions

**No new failure modes.** All failure paths follow existing patterns — the
feature adds a validation check (XML well-formedness) and changes content
routing (sysprep vs. cloud-init) but does not introduce new infrastructure
dependencies or external service calls.

### 4.7 RBAC / Tenancy

No RBAC changes required. The existing authorization model applies:

- Tenants can only reference secrets within their own project
  (`user_data_secret` is project-scoped)
- Shared-tenant secrets are rejected for `user_data_secret` (existing
  validation)
- The operator creates the K8s Secret in the hub namespace with the
  ComputeInstance as the owner reference (existing pattern)
- AAP copies the Secret to the VM namespace on the workload cluster (existing
  pattern)

### 4.8 Extensibility / Future-Proofing

**Cache-Control header for user_data responses:**
The PRD requires `Cache-Control: no-store` on API responses containing inline
`user_data`. This is a cross-cutting concern that applies to all
ComputeInstance responses, not just Windows VMs. Implementation should be in the
REST gateway response interceptor or a gRPC-gateway middleware that sets the
header when `user_data` is present in the response proto.

**Assumption:** This design assumes the `Cache-Control` header requirement is
addressed as a separate infrastructure concern and is not specific to the
Unattend.xml feature. If the team decides to scope it to this feature, it can
be implemented as a response interceptor in the compute instance handler.

**Future Unattend.xml editing:**
If a future feature adds post-creation Unattend.xml editing, the immutability
constraint on `user_data`/`user_data_secret` would need to be relaxed. This
design does not preclude that — the validation and delivery mechanisms are
independent of immutability enforcement.

**Multi-file sysprep volumes:**
The current design supports a single `Unattend.xml` key in the sysprep Secret.
KubeVirt also supports `Autounattend.xml` and arbitrary additional files. A
future enhancement could expose multi-key sysprep Secret support, but this is
out of scope for the current feature.

---

## 5. Interface Changes

### IC-1: Fulfillment Service — XML Validation for Windows user_data

**Component:** `fulfillment-service/internal/servers/private_compute_instances_server.go`

**Change:** Add guest-OS-family-aware XML validation to the ComputeInstance
create path.

**Before:** `user_data` content is accepted as an opaque string regardless of
guest OS family.

**After:** When the resolved DiskImage has `guest_os_family == WINDOWS`:
- Inline `user_data` is validated as well-formed XML
- Resolved `user_data_secret` content is validated as well-formed XML
- Validation errors return clear messages without exposing secret content
- Empty content is rejected when the field is present (existing behavior)

**New function:** `validateWellFormedXML(content string) error` — validates XML
well-formedness using `encoding/xml.NewDecoder`.

### IC-2: AAP Role — User-Supplied Sysprep Path

**Component:** `osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/create_secrets.yaml`

**Change:** Add a code path for user-supplied Windows Unattend.xml that mounts
user data as a sysprep volume instead of a cloud-init volume.

**Before:** User data Secret is always mounted as a `cloudInitNoCloud` volume
(virtio disk). Platform-generated sysprep runs unconditionally for Windows VMs
when `vm_enable_sysprep` is true.

**After:**
- When `guest_os_family == 'windows'` AND `vm_user_data_secret_ref` is set:
  - Read the user data Secret from the management cluster
  - Create a new Secret in the VM namespace with key `Unattend.xml` containing
    the `userdata` value from the source Secret
  - Mount as a `sysprep` volume with a `sata` CD-ROM disk
  - **Skip** the platform-generated Jinja2 template rendering
- When `guest_os_family == 'windows'` AND `vm_user_data_secret_ref` is NOT set
  AND `vm_enable_sysprep` is true:
  - Existing behavior: render `unattend.xml.j2` and mount as sysprep volume
- When `guest_os_family == 'linux'` AND `vm_user_data_secret_ref` is set:
  - Existing behavior: copy Secret and mount as cloudInitNoCloud volume

### IC-3: CLI — Unattend.xml Documentation in Help Text

**Component:** `fulfillment-service/internal/cmd/cli/create/computeinstance/create_compute_instance_cmd.go`

**Change:** Update the `--user-data` and `--user-data-secret` flag help text
and command long description to document the Unattend.xml use case for Windows
DiskImages.

**Before:** Help text references cloud-init and ignition only.

**After:** Help text explains that for Windows DiskImages, the content is
treated as an Unattend.xml answer file and must be well-formed XML.

### IC-4: UI — Windows-Aware User Data Input

**Component:** `osac-ui/` (external repo)

**Change:** Adapt the ComputeInstance creation form to present
Unattend.xml-appropriate guidance when the selected DiskImage has
`guest_os_family = WINDOWS`.

**Before:** The user data input is always labeled for cloud-init.

**After:**
- When the selected DiskImage has `guest_os_family = WINDOWS`:
  - Label the user data input as "Unattend.xml" (instead of "Cloud-init user
    data")
  - Show a hint that content must be well-formed XML
  - Offer both inline and secret reference delivery options
- When the selected DiskImage has `guest_os_family = LINUX` or is unspecified:
  - Existing cloud-init labels and behavior
- The UI MUST NOT persist inline `user_data` content in browser caches, local
  storage, or session storage

---

## 6. Alternatives Considered

### Alternative 1: New Proto Field for Unattend.xml

Instead of reusing `user_data`, add a dedicated `unattend_xml` field to
ComputeInstanceSpec.

**Rejected because:**
- The PRD explicitly requires using the existing `user_data` and
  `user_data_secret` fields — "no new API parameters are introduced"
- A dedicated field would duplicate the delivery and validation infrastructure
- The semantics are identical: "here is my first-boot customization payload"

### Alternative 2: Validate Unattend.xml Against Microsoft Schema

Perform full schema validation against the Microsoft Unattend XML schema, not
just well-formedness checking.

**Rejected because:**
- The PRD explicitly scopes validation to well-formedness only
- Microsoft's schema is version-specific and Windows-edition-specific
- Schema validation would require shipping and maintaining Microsoft schema
  files
- Incorrect settings surface at Windows first boot, which is the expected
  behavior

### Alternative 3: Platform-Generated Unattend.xml With User Overrides

Allow tenants to override specific fields (hostname, locale, etc.) while the
platform generates the rest of the Unattend.xml.

**Rejected because:**
- The PRD explicitly states "OSAC passes the caller's file as-is"
- Field-level overrides would require a domain-specific API for Windows
  configuration
- This approach is out of scope (listed as "Generating Unattend.xml from
  OSAC-managed fields")

---

## 7. Observability and Monitoring

No new metrics, alerts, or dashboards are required. The feature uses existing
observability patterns:

- **Validation failures** are surfaced through gRPC error responses with
  descriptive messages
- **AAP provisioning** is tracked through existing job status polling and
  condition updates
- **KubeVirt VM startup** is reflected in the ComputeInstance conditions
  (Provisioned, Ready)

**Log safety:** XML content from user data must not appear in log messages. The
existing `no_log: true` directive on the AAP secret creation task prevents
logging of secret content. The fulfillment service validation error messages
include parser error descriptions but not the XML content itself.

---

## 8. Impact and Compatibility

### Backward Compatibility

**Fully backward compatible.** No existing behavior changes:

- Linux VMs with `user_data` continue to work identically (cloud-init, no XML
  validation)
- Windows VMs without `user_data` continue to use the platform-generated
  Unattend.xml template (when `vm_enable_sysprep` is true)
- Windows VMs without `user_data` and `vm_enable_sysprep` false continue to
  boot without an answer file
- All existing API, CLI, and UI workflows are unaffected

### New Behavior

- Windows VMs with `user_data` or `user_data_secret`: content is validated as
  well-formed XML and delivered as a sysprep volume (SATA CD-ROM)

### Cross-Component Impact

| Component | Impact |
|-----------|--------|
| `proto/` | None — fields already exist |
| `fulfillment-service` | New XML validation logic for Windows user_data |
| `osac-operator` | None — CRD and reconciler unaffected |
| `osac-aap` | New code path in `ocp_virt_vm` role |
| `osac-installer` | None — no Helm chart changes |
| `osac-ui` | UI form adaptation for Windows DiskImages |
| `tests/e2e` | New e2e test scenarios |

---

## 9. Open Questions

All open questions from the initial draft have been resolved.

| # | Question | Resolution |
|---|----------|------------|
| OQ-1 | Should inline `user_data` have a size limit? | **Resolved — No.** The PRD explicitly excluded size limits from the feature scope. No `computeInstanceUserDataMaxBytes` constant or inline size validation is introduced. The existing `user_data_secret` size limit (enforced by the Secret service) remains unchanged. |
| OQ-2 | Should the UI perform client-side XML well-formedness validation before submission, or rely solely on server-side validation? | **Resolved — Server-side only for MVP.** Server-side XML validation in the fulfillment service is the single enforcement point. Client-side validation in the UI is deferred to the UI team's discretion as a UX enhancement. |
| OQ-3 | Should the `Cache-Control: no-store` header be scoped to this feature or applied broadly to all ComputeInstance responses containing `user_data`? | **Resolved — Applied broadly.** `Cache-Control: no-store` applies to all ComputeInstance responses containing `user_data`, regardless of OS family. This is tracked as a separate implementation task, not part of OSAC-4705. |
