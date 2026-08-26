# Clarification Log — OSAC-3046

## Status

- Rounds completed: 2
- Open gaps: 4
- Exit criteria met: Yes (with accepted open items marked TBD for the PRD)

## Round 1 — Service Dependencies & Scope

### R1.Q1: Inter-service dependencies when a service is disabled

CaaS relies on BMaaS for clusters on bare metal (HostTypes with physical network interfaces) and on VMaaS for clusters on VMs (HostTypes without interfaces). If a Cloud Provider Admin disables BMaaS, should CaaS cluster provisioning on bare metal hosts be blocked, or should CaaS still be available but limited to host types that don't depend on the disabled service?

#### Answer

When a service is disabled, no other enabled service can provision resources that would depend on it. CaaS with only virtual HostTypes available would still work when BMaaS is disabled, but bare-metal HostTypes would be blocked. Same for VMaaS — disabling it blocks virtual HostTypes for CaaS. The rationale is compliance: if BMaaS is disabled to exclude it from the compliance surface, CaaS shouldn't be able to provision bare-metal-backed clusters as a side door around that boundary.

#### Impact

The PRD must define the inter-service dependency model: disabled services block dependent resource types in other services. The design will need to specify how HostType filtering works based on enabled services.

#### Decision (D1)

When a service is disabled, no enabled service may provision resources that depend on the disabled service. CaaS with BMaaS disabled blocks bare-metal HostTypes but allows virtual HostTypes (and vice versa for VMaaS).

---

### R1.Q2: Post-installation disablement

The Definition of Done requires "post-installation enablement of additional services." Is post-installation disablement also in scope? If yes, what happens to existing resources when their service is disabled?

#### Answer

Unanswered. Liat Gamliel asked this exact question in the Jira on Aug 19 but it was not answered. The Definition of Done only mentions enablement, not disablement.

#### Impact

The PRD will mark post-installation disablement as TBD. The feature covers enablement at install time and post-installation enablement of additional services.

---

### R1.Q3: Service list completeness

Are networking and storage considered always-on shared infrastructure, or could a deployment disable them independently?

#### Answer

Juan Hernandez's feasibility report in the Jira comments explicitly states: "The remaining services (Tenants, Projects, Users, Roles, Secrets, networking resources, storage resources, Events, Capabilities, etc.) are shared infrastructure and would remain always-on regardless of which features are enabled." The four toggleable services are CaaS, VMaaS, BMaaS, and MaaS.

#### Impact

The PRD scope is limited to four toggleable services. Shared infrastructure (networking, storage, tenants, etc.) is always-on.

#### Decision (D2)

The four toggleable services are CaaS, VMaaS, BMaaS, and MaaS. Networking, storage, tenants, and other platform services are shared infrastructure and always remain enabled.

---

### R1.Q4: Compliance Admin persona

The user stories reference a "Compliance Admin" who needs compliance posture scoped to enabled services. OSAC's canonical personas are Cloud Provider Admin, Cloud Infrastructure Admin, Tenant Admin, and Tenant User. Is "Compliance Admin" a new persona or does it map to an existing one?

#### Answer

Unanswered. Left open — not immediately relevant to the PRD. A question has been flagged for posting to the Jira.

#### Impact

The PRD will use the Jira's original "Compliance Admin" wording with a note that the persona mapping is TBD.

---

### R1.Q5: Compliance integration depth

Is this feature responsible for implementing compliance scoping (conditional scan profiles, filtered dashboards), or limited to providing the enablement signal that downstream features consume?

#### Answer

There is no compliance scoping mechanism in the codebase today. No `enabled_features` proto fields, no compliance scan profiles, no feature flag infrastructure exist. The compliance scanning features (OSAC-3029 for CaaS Compliance Operator, OSAC-3031 for RHEL OpenSCAP) also don't exist in code yet. This feature provides the enablement configuration and exposes it via the Capabilities endpoint. Downstream compliance features consume that signal to scope their scanning.

#### Impact

The PRD scopes compliance integration to: (1) providing the enabled-services configuration, and (2) exposing it via the Capabilities endpoint. Actual compliance scanning scoped to enabled services is a dependency on OSAC-3018, OSAC-3029, and OSAC-3031.

#### Decision (D3)

This feature provides the enablement signal (configuration + Capabilities endpoint). Compliance scanning scoped to enabled services is the responsibility of downstream features (OSAC-3018, OSAC-3029, OSAC-3031), which consume the signal.

---

## Round 2 — Cross-Component Propagation & User Experience

### R2.Q1: Configuration source of truth

Should there be a single source of truth for enablement (e.g., Helm values), or can each layer be configured independently? Can enablement be changed post-installation without a Helm upgrade?

#### Answer

Helm values are the source of truth. The installer already has per-component `enabled` flags (e.g., `bmf.enabled`, `ui.enabled`, `metering.enabled`). Helm templates propagate these to runtime config via container args or environment variables. The fulfillment-service's Capabilities endpoint serves as the read API for clients (UI, CLI) to discover enabled services at runtime. Post-installation changes require `helm upgrade` with updated values.

#### Impact

The PRD defines Helm values as the configuration surface. The Capabilities endpoint is the runtime discovery mechanism. Day-2 enablement changes go through `helm upgrade`, not through the API.

#### Decision (D4)

Helm values are the source of truth for service enablement. The Capabilities endpoint is the read-only runtime API for clients to discover enabled services. Post-installation changes require `helm upgrade`.

---

### R2.Q2: Enclave wizard alignment

The Enclave wizard has "experiences" that select services at install time. Should this feature integrate with that mechanism, replace it, or run alongside it?

#### Answer

Unanswered. Left open for design phase.

#### Impact

The PRD will note the Enclave wizard "experiences" as a related mechanism and flag alignment as a design-phase concern.

---

### R2.Q3: UI behavior for disabled services

When a service is disabled, should its UI pages be completely hidden or shown as disabled/grayed-out?

#### Answer

Unanswered. Left open for design phase.

#### Impact

The PRD will state that the UI must not expose disabled services but defer the specific UX treatment to the design phase.

---

### R2.Q4: Operator controllers for disabled services

When a service is disabled, should its controllers not be deployed at all, or deployed but idle?

#### Answer

The Jira Feature Goal states "Disabled services are fully excluded -- no APIs, no controllers, no compliance scope" and the Definition of Done states "Disabled services have no running controllers, APIs, or UI surfaces." Controllers for disabled services should not be running.

#### Impact

The PRD requires that disabled services have no running controllers, consistent with the Jira.

#### Decision (D5)

Disabled services must have no running controllers, APIs, or UI surfaces — they are fully excluded from the deployment.

---

## Remaining Gaps

- **Post-installation disablement** (R1.Q2): Whether disabling a service after installation is in scope, and what happens to existing resources. Unanswered in Jira.
- **Compliance Admin persona** (R1.Q4): Whether "Compliance Admin" maps to an existing OSAC persona or is new. Flagged for Jira follow-up.
- **Enclave wizard alignment** (R2.Q2): How Enclave "experiences" relate to the per-service enablement flags. Deferred to design phase.
- **UI behavior for disabled services** (R2.Q3): Whether disabled service UI is hidden or shown as unavailable. Deferred to design phase.
