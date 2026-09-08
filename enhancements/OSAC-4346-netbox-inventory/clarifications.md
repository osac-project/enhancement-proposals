# Clarification Log — OSAC-4346

## Status

- Rounds completed: 1
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

NetBox backend is a standard `inventory.Client` implementation self-registered in the operator binary. No separate sidecar or gRPC service. Configuration follows the standard Helm/Enclave pattern for infrastructure admin setup.

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

## Summary

Four locked decisions:
- **D1:** Transparent NetBox backend; tenants use standard API.
- **D2:** In-tree backend, Helm + Enclave Wizard config.
- **D3:** Reuse NetBox native status field for state.
- **D4:** NetBox inventory-only; OS provisioning orthogonal.

No remaining gaps blocking design phase.
