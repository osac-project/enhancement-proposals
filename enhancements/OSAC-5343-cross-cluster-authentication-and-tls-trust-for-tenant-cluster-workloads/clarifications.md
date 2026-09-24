# Clarification Log — OSAC-5343

## Status

- Rounds completed: 1
- Open gaps: 1
- Exit criteria met: No

## Round 1 — scope, ownership, lifecycle, and interfaces

### R1.Q1: Identity scope

Should the Keycloak service account be one per tenant, reused across that tenant's clusters, or one distinct service account per tenant cluster?

#### Answer

The target state is one Keycloak client per tenant, carrying that tenant's organization claim and reused across the tenant's clusters. The temporary shared CSI client remains only a transition state while tenant-specific identities are introduced.

#### Impact

The PRD must state tenant-scoped service identities and must not require separate identities for every tenant cluster.

#### Decision (D1)

Use one tenant-scoped Keycloak service-account client, reused across the tenant's clusters.

---

### R1.Q2: Ownership of client lifecycle

Does OSAC-1644 create the Keycloak client and credentials, or does OSAC-4197 own client creation while OSAC-1644 only ensures credentials are available to consumers?

#### Answer

OSAC-1644 establishes client-credentials and TLS trust mechanics for consumers. OSAC-4197 owns automated creation of tenant-specific Keycloak clients and synchronization of their credentials during tenant onboarding.

#### Impact

The PRD must list OSAC-4197 as a dependency for tenant-specific identity lifecycle while retaining OSAC-1644 responsibility for consuming those credentials securely.

#### Decision (D2)

OSAC-4197 owns tenant-specific Keycloak-client creation and lifecycle; OSAC-1644 owns secure consumer connectivity and credential consumption.

---

### R1.Q3: CSI delivery boundary

Does OSAC-1644 need to deliver CSI connectivity end-to-end, or establish the trust and credential prerequisites that OSAC-3291 consumes?

#### Answer

OSAC-1644 establishes consumer-agnostic cross-cluster trust and authentication. Success is a supported workload on a tenant cluster using tenant-scoped Keycloak credentials to establish a TLS-authenticated gRPC connection to fulfillment service. The CSI driver is a dependent validation consumer; deploying it, propagating its credential Secret, and vendor-specific volume provisioning are follow-up responsibilities.

#### Impact

The PRD must require a verified secure workload-to-fulfillment-service connection without assigning CSI deployment, CSI Secret propagation, or vendor-storage functionality to this Feature.

#### Decision (D3)

Success requires a supported tenant-cluster workload using tenant-scoped credentials to complete a TLS-authenticated gRPC call to fulfillment service. The CSI driver remains a dependent validation consumer, not a delivered workload.

---

### R1.Q4: Existing clusters and rotation

For existing tenant clusters and credential rotation or revocation, what user-visible outcome is required?

#### Answer

There are no existing tenant clusters. OSAC-1644 requires automatic trust setup only for newly provisioned tenant clusters; upgrade and backward-compatibility handling are not required. OSAC-4197 owns lifecycle and synchronization of rotated Keycloak credentials so consumers receive updates without administrator intervention.

#### Impact

The PRD must cover automatic trust setup for newly provisioned tenant clusters and identify rotated credential propagation as an OSAC-4197 dependency, without adding upgrade or backward-compatibility requirements for nonexistent clusters.

#### Decision (D4)

OSAC-1644 automatically establishes trust for newly provisioned tenant clusters. OSAC-4197 owns rotated credential lifecycle and synchronization. Upgrade and backward-compatibility handling are not required because no existing clusters exist.

---

### R1.Q5: Interfaces and status

Is this administrator-managed installation/provisioning behavior only, or must UI, CLI, status, and troubleshooting support be delivered too?

#### Answer

To be determined — whether dedicated UI, CLI, Kubernetes readiness status, and troubleshooting support are in scope for this Feature.

#### Impact

The PRD must not state a committed interface or status deliverable until the scope decision is made.

## Remaining Gaps

- Whether UI, CLI, Kubernetes readiness status, and troubleshooting support are in scope for this Feature.
