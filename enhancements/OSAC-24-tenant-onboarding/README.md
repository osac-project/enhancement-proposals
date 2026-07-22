# Tenant On-boarding Automation

| Field       | Value   |
|-------------|---------|
| **Status**  | Proposed |
| **Feature** | OSAC-24 |
| **Jira**    | https://redhat.atlassian.net/browse/OSAC-24 |
| **Authors** | Daniel Erez |
| **Date**    | 2026-06-15 |

## Summary

Automate tenant onboarding by extending the Tenant CR schema and automating CR lifecycle management. When a new tenant is added to the fulfillment database, the Tenant controller in osac-operator will automatically create Tenant CRs on management hubs with tenant identity information (`displayName`, `emailDomains`), enabling component controllers (Storage, Networking, Authentication) to provision tenant-specific infrastructure.

## Motivation

Cloud Provider Admins create tenants via the fulfillment API, but there is no automated mechanism to create corresponding Tenant CRs on management hubs. Additionally, the Tenant CR lacks fields for tenant identity (`displayName`, `emailDomains`) that component controllers need for provisioning.

## Proposal

### Two-Part Enhancement

1. **Schema Extension**: Add `spec.displayName` and `spec.emailDomains` fields to Tenant CR
2. **Lifecycle Automation**: Extend the existing Tenant controller to watch the fulfillment database and auto-create/delete Tenant CRs

### Tenant CR Schema

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: Tenant
metadata:
  name: acme-corp
  namespace: default
  annotations:
    osac.openshift.io/managed-by: fulfillment-service
spec:
  displayName: "ACME Corp"
  emailDomains:
    - acme.com
    - acme.net
```

## Implementation

### Epic 1: Tenant CR Schema Extension (Size: S, 3 stories)

**Story 1.1: CRD Field Additions**
- Add `spec.displayName` and `spec.emailDomains` to `api/v1alpha1/tenant_types.go`
- Regenerate CRD manifests and Go types

**Story 1.2: Validation Rules**
- Add kubebuilder validation markers
- Implement admission webhook for email domain validation

**Story 1.3: Integration Tests**
- Test CR creation with valid/invalid spec fields

### Epic 2: Tenant Controller Database Watch (Size: M, 4 stories)

**Story 2.1: Database Watch Mechanism**
- Extend Tenant controller to watch fulfillment database (PostgreSQL LISTEN/NOTIFY or polling)
- Detect tenant INSERT/UPDATE/DELETE events
- **Security Model:** The controller uses read-only database credentials provided via Kubernetes Secret. Authentication, authorization, and tenant resource scoping remain the responsibility of the Fulfillment Service layer. The controller treats the database as an event source only and does not enforce access control or tenant isolation directly—those concerns are managed by the Fulfillment Service API

**Story 2.2: CR CRUD Logic**
- Create Tenant CR when tenant added to DB
- Delete Tenant CR when tenant removed from DB
- Add `osac.openshift.io/managed-by: fulfillment-service` annotation

**Story 2.3: Reconciliation Loop**
- Periodic reconciliation performs a full diff between the authoritative database state and live CRs in the cluster
- Recreate missing CRs that should exist based on DB state
- Delete orphaned CRs that no longer exist in the database (respecting `managed-by` annotation filter)
- Update CRs that exist in both but have diverged (e.g., displayName or emailDomains changed in DB)
- Skip CRs without `managed-by` annotation to avoid interfering with manually created Tenant CRs
- This ensures the cluster state fully converges to the database state of record, even after missed LISTEN/NOTIFY events during reconnects or controller restarts

**Story 2.4: Integration Tests**
- Test full lifecycle: create tenant → CR appears → delete tenant → CR removed
- Test reconciliation recovery (manual CR deletion)

## Requirements

### Functional Requirements

#### Tenant CR Specification
- **FR-1:** `spec.displayName` as required string field
- **FR-2:** `spec.emailDomains` as required list of strings field
- **FR-3:** Kubebuilder validation markers for field requirements
- **FR-4:** Admission webhook validates email domain format

#### Tenant CR Lifecycle
- **FR-5:** Auto-create Tenant CR when tenant added to fulfillment database
- **FR-6:** Tenant CR resides in default namespace on each management hub
- **FR-7:** Auto-delete Tenant CR when tenant deleted from database
- **FR-8:** Recreate manually deleted CRs during reconciliation
- **FR-9:** Only manage CRs with `managed-by: fulfillment-service` annotation

#### Legacy Tenant CR Adoption
- **FR-10:** Pre-existing Tenant CRs without the `managed-by` annotation are adopted during the initial reconciliation pass after controller upgrade
- **FR-11:** Adoption adds the `managed-by: fulfillment-service` annotation to existing CRs if they match a tenant in the database (matched by `metadata.name`)
- **FR-12:** After adoption, legacy tenants participate in full lifecycle management: updates, deletes, and reconciliation recovery
- **FR-13:** Tenant CRs that exist in the cluster but have no corresponding database entry are left unmanaged (no annotation added) to preserve manually created test/development tenants
- **FR-14:** During adoption, if a legacy Tenant CR is missing required fields (`spec.displayName` or `spec.emailDomains`), the controller backfills them from the fulfillment database before adding the `managed-by` annotation. If the corresponding tenant record is not found in the database or lacks the required fields, the CR is left unmanaged (no annotation added)

## Dependencies

- **osac-operator Tenant CRD and controller** (exists at `internal/controller/tenant_controller.go`)
- **Fulfillment Service database schema** (tenant name and email domains)

## Open Questions

### Q1: Database Watch Mechanism
Should the controller use PostgreSQL LISTEN/NOTIFY or polling? What is acceptable delay between DB insert and CR creation?

### Q2: Email Domain Validation
Should webhook support subdomains? Internationalized domain names? DNS lookup validation?

### Q3: Multi-Hub Distribution
Which management hubs should receive Tenant CRs? All hubs or tenant-specific selection?
