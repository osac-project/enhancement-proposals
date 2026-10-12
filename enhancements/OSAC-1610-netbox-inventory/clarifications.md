# Clarification Log — OSAC-1610

## Status

- Rounds completed: 6
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Scope & Deployment

### R1.Q1: Primary Goal

What are the user-facing outcomes when a Cloud Infrastructure Admin configures NetBox as the inventory backend?

#### Answer

Tenants can allocate and deallocate bare-metal hosts from NetBox inventory transparently. Cloud Infrastructure Admin configures the backend endpoint and credentials, then OSAC handles all allocation/deallocation internally without tenant exposure to NetBox.

#### Impact

Defines primary personas: Cloud Infrastructure Admin (setup and prerequisites) and Tenant User (transparent provisioning). No NetBox-specific UX exposed to tenants.

#### Decision (D1)

NetBox backend is transparent to Tenant Users. Tenant allocates/deallocates hosts via standard BareMetalInstance API. Cloud Infrastructure Admin configures the backend and prerequisites; OSAC handles allocation internally.

---

### R1.Q2: Deployment and Configuration

Should the NetBox backend be compiled into the operator (in-tree) or deployed as a separate service (out-of-tree)? And how should Cloud Infrastructure Admin configure it?

#### Answer

In-tree backend compiled into the operator. Configuration via Helm values processed by the Enclave Wizard pipeline.

#### Impact

NetBox backend is a standard `inventory.Client` implementation constructed by the operator startup factory with its Metal3 manager dependency. No separate sidecar or gRPC service. Configuration follows the standard Helm/Enclave pattern for infrastructure admin setup.

#### Decision (D2)

In-tree backend compiled into the operator. Cloud Infrastructure Admin configures NetBox backend via Helm values (osac-installer), processed through Enclave Wizard pipeline. Structured for future OSAC-3806 out-of-tree extraction.

---

### R1.Q3: Allocation Tracking

When a host is allocated to a BareMetalInstance, how does OSAC track that allocation so the same host isn't offered to another tenant request?

#### Answer

OSAC records an assignment identifier in NetBox when a host is allocated, and clears it when the host is deallocated. This prevents double-allocation. The mechanism (status field, custom field, metadata, etc.) is a design-time decision based on the deployment's NetBox schema.

#### Impact

Tenants can safely request hosts; OSAC guarantees no two instances claim the same hardware. The tracking mechanism is transparent to users — it's an internal concern of how OSAC manages NetBox state.

#### Decision (D3)

OSAC tracks host allocation state in NetBox using a native NetBox field (e.g., device status, tag, or existing metadata field). If a native field is insufficient, the design phase will define a custom field tailored to the deployment's requirements.

---

### R1.Q4: OS Provisioning Scope

Is NetBox responsible for OS provisioning, or is that orthogonal?

#### Answer

Orthogonal. NetBox is inventory only. OS provisioning, BMH readiness, and power management are handled by existing Metal3/BMH integration.

#### Impact

NetBox provides host discovery and allocation only. All other BMaaS concerns (image selection, OS setup, power control) are independent and reuse existing patterns.

#### Decision (D4)

NetBox is inventory-only backend. OS provisioning, BMH readiness, and power management are orthogonal to this feature and handled by existing Metal3/BMH integration.

---

## Round 2 — Custom-Field Selection (2026-09-22)

### Decision (D5)

Use separate provider-created NetBox Community custom fields instead of tags.
Capability selectors retain key/value semantics; the adapter adds the API's
`cf_` prefix to exact field names. The administrator creates and populates
those fields. No capability or pool tag is required. [User direction]

The local design proposes Boolean `osac_managed=true` for pool membership;
native device status and `osac_instance_id` continue to record allocation
state and ownership. This exact pool-field name/type is a design proposal
for review, not a separately approved user requirement.

### Rationale and impact

Both tags and custom fields support server-side filtering. There is no measured
performance result favoring tags; the choice follows the existing OSAC
key/value selector, typed NetBox data, and reuse of compatible field values.
No hardcoded mapping table is needed. Field schemas and scalar types must be
validated, and older tag-based selectors require explicit migration. Design,
test plan, and PRD assumptions use this same contract.

## Historical Round 3 — Unchanged Device Names and Configuration (2026-09-22; superseded by D9)

### Historical Decision (D6 — superseded by D9)

Preserve the existing NetBox device name unchanged as the provider/fabric
hostname. The earlier proposal also used it as the BMH name; that identity
mapping is superseded by D7 below.
[User direction]

### Implementation impact for local review

The earlier design validated names and uniqueness, persisted the separate
numeric device ID with the host ID/name before claiming, and used the original
ID for recovery and release. Those safeguards remain, while D7 separates the
Kubernetes BMH name from the provider hostname.

## Historical Round 4 — Location-Qualified BMH Identity (2026-09-23; superseded by D9)

### Historical Decision (D7 — superseded by D9)

Generate a deterministic BMH name from the native NetBox region path, site
slug, and effective provider hostname, with a fixed alphabetic `bmh-` prefix.
The effective hostname is the exact nonempty `device.name`, or
`netbox-<numeric-id>` when the NetBox name is empty/null. Persist it as
`ExternalHostName` for provider/fabric and DHCP lookups. Use the configured
`options.metal3.namespace` for every NetBox-backed BMH and operator-managed BMC
Secret. Persist the generated host ID, effective provider name, and numeric
NetBox device ID before claiming.

The final BMH name is validated by a centralized NetBox-adapter helper using
Kubernetes' `IsDNS1035Label`; it must be a lowercase, 1–63 character label
starting with a letter. There is no existing reusable BMF helper: BCM's private
pattern allows leading digits and remains BCM-specific. Empty provider names
use the current `netbox-<id>` fallback and the BMH form
`bmh-<region>-<site>-netbox-<id>`. Hostname-based fabric integrations must
register the effective fallback; OSAC does not create or rename fabric entries.

Generated names must be unique, case-insensitively, across all devices visible
to the OSAC token, including allocated/unavailable devices, because they share
one Metal3 namespace. The same effective provider names in different locations
are allowed when the generated names differ; the same region/site/effective-name
combination, including across NetBox tenants, is rejected. Different effective
names or hyphenated location components that produce the same joined name are
also rejected; the adapter must validate the complete visible device list, not
only same-name results.

### Impact

D7 supersedes the BMH-name portion of D6 and the related old test expectations.
Numeric device IDs remain the recovery/release identity and NetBox endpoint
selector. Nonempty NetBox names are never modified; an empty name uses the
deterministic fallback. Effective hostname, location, and Metal3 endpoint or
namespace changes require draining pending and active BMIs.

## Historical Round 5 — Empty Device Names (2026-09-23; superseded by D9)

### Historical Decision (D8 — superseded by D9)

`device.name` is optional for an enrolled NetBox device. The adapter resolves
the effective provider hostname as the exact `device.name` when present, or
`netbox-<id>` when it is empty/null. The same value is stored in
`ExternalHostName` and is used as the final component of the generated BMH
name, for example `bmh-region-1-site-a-netbox-42`. The numeric ID remains a
separate backend identity for NetBox REST operations and recovery.

If the fabric performs hostname lookup, the provider must register the
effective hostname, including the `netbox-<id>` fallback. OSAC does not create
fabric entries. A change between an empty name and a nonempty name is an
effective identity change and requires reselection or a drain.

Persisted cleanup intent and resource-absence checkpoints prevent retries
from recreating resources during rollback and allow an old BMI to finish
after release followed by immediate reallocation. Neither checkpoint grants
permission to mutate a different owner's NetBox claim or Kubernetes resources.

The credential-loading contract uses mounted `tokenFile`/`caCertFile` paths;
Secret names remain Helm inputs. NetBox enablement includes Metal3 management
without a second required flag, and provisioning uses the existing `metal3`
host class. The design/test plan also cover installer hooks, scoped BMC Secret
permissions, and explicit restart after configuration or credential updates.
These are local responses to configuration review feedback, not reviewer
approval or published resolutions.

## Round 6 — ID-Derived Host Identity and AAP Networking (2026-09-23)

### Decision (D9)

Use the numeric NetBox device ID as the single canonical OSAC host identity for
both named and unnamed devices. For device ID `42` and configured Metal3
namespace `baremetal`, the existing host-ID contract is
`baremetal/netbox-42`, and the BMH name is `netbox-42`. Persist only
`spec.externalHostID`; remove the proposed `BackendID` field and device-ID
annotation. Leave `spec.externalHostName` empty for the NetBox backend so the
existing AAP networking and DHCP fallback derives `netbox-42` from the final
host-ID segment.

The Metal3 namespace remains in `externalHostID` because the existing
`namespace/name` contract is consumed by Metal3 management and the AAP
provisioning/deprovisioning roles. It scopes the Kubernetes object; it is not a
second NetBox identity. `device.name`, site, and region are not used for
Kubernetes naming, uniqueness, recovery, or networking lookup. A fabric that
uses hostname lookup must register `netbox-<id>`; MAC-based DHCP behavior is
unchanged.

### Impact

D9 supersedes D6, D7, and D8 for host identity, BMH naming, and provider
hostname behavior. No full-inventory name scan, location-qualified name
generation, `ExternalHostName` persistence, `BackendID`, or device-ID
annotation is required. A change to `device.name` does not require reselection
or a drain. A device replacement with a new NetBox ID requires draining its
BMI. Switching the configured NetBox URL to a different inventory requires
draining affected BMIs because their saved host IDs do not record the source
NetBox instance.

## Summary

Nine decisions (D6–D8 are superseded by D9):
- **D1:** Transparent NetBox backend; tenants use standard API.
- **D2:** In-tree backend, Helm + Enclave Wizard config.
- **D3:** Reuse NetBox native status field for state.
- **D4:** NetBox inventory-only; OS provisioning orthogonal.
- **D5:** Custom fields for pool membership and capability equality; preserve selector values and use only NetBox Community features.
- **D6–D8:** Superseded for host identity and name handling by D9.
- **D9:** Use `netbox-<numeric-id>` as the canonical BMH and provider lookup name for every device; persist it through the existing namespace-qualified `externalHostID`, keep `externalHostName` empty, and retain the configured Metal3 namespace for the shared `namespace/name` consumer contract.

No remaining gaps blocking design phase.
