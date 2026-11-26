# Test Plan — OSAC-24 Tenant onboarding automation

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 9

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-ONB-01: Creating a Tenant projects a hub CR and namespace

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 92-95](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L92-L95)
- **Dependencies:** Real deployed fulfillment, PostgreSQL, Keycloak and management hub Kubernetes; isolated tenant fixture.
- **Execution:** `fulfillment-service/it/it_tenant_onboarding_test.go`
- **Evidence:** `Creates Tenant CR and namespace on hub when tenant is created` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_tenant_onboarding_test.go#L48)).
- **Selector:** Ginkgo focus `Creates Tenant CR and namespace on hub when tenant is created` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's private admin client and disposable hub namespace.

1. Create a uniquely named Tenant and wait for SYNCED.
2. Read its hub Tenant CR and Namespace.

**Expected results.** The configured hub namespace contains one matching Tenant CR with the expected name and tenant labels, and the tenant Namespace is labeled accordingly.

#### TC-ONB-02: A repeat hub reconciliation reuses the existing Tenant CR

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 70-76](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L70-L76)
- **Dependencies:** In-process onboarding reconciler, fake hub Kubernetes client, and mocked service clients. No real hub or identity provider.
- **Execution:** `fulfillment-service/internal/controllers/onboarding/tenant_reconciler_function_test.go`
- **Evidence:** `does not create a duplicate but still ensures namespace` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/controllers/onboarding/tenant_reconciler_function_test.go#L315)).
- **Selector:** Ginkgo focus `does not create a duplicate but still ensures namespace` in `fulfillment-service/internal/controllers/onboarding`. Source reviewed, test not run.

**Preconditions.** Use the suite hub fixture with an already existing Tenant CR for the authoritative tenant.

1. Reconcile the tenant against that hub.
2. Check the existing CR and the tenant Namespace.

**Expected results.** The reconciler reuses the Tenant CR and ensures the tenant Namespace exists.

#### TC-ONB-03: A failed hub Tenant CR create reports failed reconciliation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 65-76](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L65-L76)
- **Dependencies:** In-process onboarding reconciler and controlled hub Create error. Kubernetes and service clients are test doubles.
- **Execution:** `fulfillment-service/internal/controllers/onboarding/tenant_reconciler_function_test.go`
- **Evidence:** `sets status to FAILED and returns the error for requeue` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/controllers/onboarding/tenant_reconciler_function_test.go#L725)).
- **Selector:** Ginkgo focus `sets status to FAILED and returns the error for requeue` in `fulfillment-service/internal/controllers/onboarding`. Source reviewed, test not run.

**Preconditions.** Use the suite one-hub fixture with a pending Tenant and its controlled Create failure.

1. Run tenant-to-hub reconciliation.
2. Inspect the returned error and the public-facing Tenant status.

**Expected results.** Reconciliation returns the fixture error, marks the Tenant FAILED and identifies the hub in its status without exposing the internal error text.

#### TC-ONB-04: Deleting a tenant removes its hub CR and namespace

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 93-97](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L93-L97)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and management hub Kubernetes; fixture tenant and namespace.
- **Execution:** `fulfillment-service/it/it_tenant_onboarding_test.go`
- **Evidence:** `Removes Tenant CR and namespace from hub when tenant is deleted` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_tenant_onboarding_test.go#L91)).
- **Selector:** Ginkgo focus `Removes Tenant CR and namespace from hub when tenant is deleted` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Create the fixture tenant, wait for SYNCED and confirm its Tenant CR exists.

1. Delete the Tenant through the suite's private client.
2. Poll the hub for its CR and Namespace.

**Expected results.** Both the Tenant CR and Namespace are absent within the two-minute poll bounds.

#### TC-ONB-05: Tenant CR admission enforces required fields and email-domain format

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [README.md, lines 86-90](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L86-L90)
- **Dependencies:** Real API server/etcd, installed CRD and configured admission webhook, synthetic records; no deployed identity provider.
- **Gap:** Canonical domain-validation and onboarding suites cover service validation. No exact installed CRD and webhook matrix verified for the legacy fields.

**Preconditions.** Use one valid Tenant fixture with a display name and email domain, then construct independent missing/invalid variants.

1. Submit all fixtures to local admission.
2. Compare accepted CR and field diagnostics.

**Expected results.** Both required fields are enforced and an invalid domain is rejected by the documented admission boundary.

#### TC-ONB-06: Reconciliation recreates a manually removed managed Tenant CR

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 93-97](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L93-L97)
- **Dependencies:** Real fulfillment, PostgreSQL and a disposable management hub; synthetic managed Tenant.
- **Gap:** Current onboarding tests restore deleted labels. No verified test in the canonical onboarding/controller inventory removes and recreates the entire CR.

**Preconditions.** Create a fixture tenant and record its hub Tenant CR metadata.

1. Remove the fixture CR while keeping the service record.
2. Wait for the next reconciliation and read its replacement.

**Expected results.** A new CR UID appears with the same logical tenant, expected namespace and management metadata.

#### TC-ONB-07: A legacy CR with a matching record is adopted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 99-102](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L99-L102)
- **Dependencies:** Real fulfillment, PostgreSQL and isolated hub; old CR fixture and synthetic matching database record.
- **Gap:** Canonical controller sources assert label repair and already-present behavior. The historical managed-by adoption behavior is unverified.

**Preconditions.** Seed an unannotated legacy CR and matching authoritative record.

1. Run reconciliation, then change the record's display name and reconcile again.
2. Read the hub CR.

**Expected results.** The matching CR gains the management annotation and then follows the supported managed update.

#### TC-ONB-08: A legacy CR without an authoritative tenant stays unmanaged

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 97-104](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L97-L104)
- **Dependencies:** Real fulfillment, PostgreSQL and isolated hub with a manually created fixture CR.
- **Gap:** No exact canonical onboarding or reconciliation test found for the no-database-record legacy fixture.

**Preconditions.** Create a legacy fixture CR without a matching fulfillment record.

1. Reconcile through discovery and re-read its metadata.
2. Compare its original content and UID.

**Expected results.** The CR remains present and unchanged without the management annotation.

#### TC-ONB-09: Adoption backfills required legacy fields before marking the CR managed

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 100-104](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-24-tenant-onboarding/README.md#L100-L104)
- **Dependencies:** Real fulfillment, PostgreSQL and disposable hub with an upgrade-compatible historical CR fixture.
- **Gap:** No exact legacy displayName and emailDomains backfill selector found in canonical tenant controller and onboarding suites.

**Preconditions.** Seed one legacy CR missing both fields and a complete matching record, plus a second fixture with incomplete authoritative data.

1. Reconcile both and read their specs and management annotations.
2. Compare the complete record's field values with its adopted CR.

**Expected results.** The first CR acquires the stored display name and domains before management. The second remains unmanaged.
