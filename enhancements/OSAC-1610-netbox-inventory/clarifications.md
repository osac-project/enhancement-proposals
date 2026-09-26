# Clarification Log — OSAC-1610

## Status

- Rounds completed: 3
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

## Round 3 — Unchanged Device Names and Configuration (2026-09-22)

### Decision (D6)

Use the existing NetBox device name unchanged as the BMH name and return
`<Metal3 namespace>/<device.name>` as the host ID, following the BCM naming
pattern. Do not generate a prefixed name from the numeric device ID.
[User direction]

### Implementation impact for local review

The design validates names and uniqueness, persists the separate numeric
device ID with the host ID/name before claiming, and uses the original ID
for recovery and release. Provider fabric names must agree, and live renames
require a drain. These safeguards and their internal annotation/Go fields are
implementation proposals supporting D6, not previously existing behavior.

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

## Summary

Six locked decisions:
- **D1:** Transparent NetBox backend; tenants use standard API.
- **D2:** In-tree backend, Helm + Enclave Wizard config.
- **D3:** Reuse NetBox native status field for state.
- **D4:** NetBox inventory-only; OS provisioning orthogonal.
- **D5:** Custom fields for pool membership and capability equality; preserve selector values and use only NetBox Community features.
- **D6:** Preserve the NetBox device name as the BMH name; namespace-qualify it for OSAC's host ID.

No remaining gaps blocking design phase.
