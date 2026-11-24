# Test Plan — OSAC-1030 Organizations and authentication

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 5

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-ORG-01: Tenant provisioning creates an enabled Keycloak organization

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 270-280](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1030-organizations/README.md#L270-L280)
- **Dependencies:** Real deployed fulfillment, PostgreSQL, Keycloak and hub; isolated tenant and identity fixtures; no external corporate IdP.
- **Execution:** `tests/e2e/regression/test_tenant_onboarding.py`
- **Evidence:** `test_tenant_onboarding_demo1_milestone_02` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/regression/test_tenant_onboarding.py#L242)).
- **Selector:** `uv run pytest -n 0 tests/e2e/regression/test_tenant_onboarding.py::test_tenant_onboarding_demo1_milestone_02` from OSAC root with the IAM fixture. Source reviewed, test not run.

**Preconditions.** Use a unique fixture tenant and the authorized provider-admin CLI fixture.

1. Create the tenant and wait for SYNCED.
2. Read the corresponding Keycloak organization via the fixture admin interface.

**Expected results.** The tenant reaches SYNCED and Keycloak reports an enabled organization. Current main uses the tenant API and Keycloak organization rather than the legacy organization endpoint and dedicated realm.

#### TC-ORG-02: VirtualNetwork reads observe tenant isolation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 245-258](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1030-organizations/README.md#L245-L258)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and Keycloak with separate fixture tenants; no resource provider.
- **Execution:** `fulfillment-service/it/it_tenant_lifecycle_test.go`
- **Evidence:** `Resources created by tenant-A are not visible to tenant-B` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_tenant_lifecycle_test.go#L1169)).
- **Selector:** Ginkgo focus `Resources created by tenant-A are not visible to tenant-B` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the integration suite's two isolated tenants and their ordinary user sessions.

1. Create a synthetic VirtualNetwork using the owning tenant's public API fixture.
2. Compare the owning tenant Get with the other fixture tenant's List and Get results.

**Expected results.** The owning tenant Get returns the created ID, the other tenant's List omits it, and its Get returns NotFound.

#### TC-ORG-03: Project visibility follows membership and inherited permissions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 624-631](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1030-organizations/README.md#L624-L631)
- **Dependencies:** Real Keycloak, fulfillment, authorization gateway and PostgreSQL; isolated organization, users and parent/child projects.
- **Gap:** Canonical onboarding and IAM journeys cover role assignments. No exact parent/child inheritance versus resource-specific exclusion selector was verified for this legacy scenario.

**Preconditions.** Create parent and child fixture projects with a viewer, project manager and resource creator.

1. List and manage the child under each authorized fixture role.
2. Compare with a fixture holding only the parent resource-specific create permission.

**Expected results.** Viewer and manager permissions inherit to the child as documented. Resource-specific permission requires an explicit child grant.

#### TC-ORG-04: Organization deletion observes project dependency and identity cleanup

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 618-622](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1030-organizations/README.md#L618-L622)
- **Dependencies:** Real deployed fulfillment, PostgreSQL and Keycloak in an isolated cluster; fixture users and projects; no real IdP.
- **Gap:** Canonical Tenant API onboarding tests cover project and tenant removal. The legacy Organizations/cascade and realm teardown contract is not verified and current tenancy uses Keycloak organizations.

**Preconditions.** Create a fixture tenant with a nested project and an identity-provider organization.

1. Request ordinary deletion while the project exists.
2. Complete the supported teardown and read the project and identity organization state.

**Expected results.** Dependency handling preserves the tenant while its project blocks deletion. After teardown the projects and corresponding identity organization are absent.

#### TC-ORG-05: Tenant admins can inspect their configured identity provider

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 286-291](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1030-organizations/README.md#L286-L291)
- **Dependencies:** Real fulfillment authorization and disposable Keycloak with a synthetic configured IdP; external provider stubbed.
- **Gap:** Canonical tenant lifecycle and IAM sources did not identify the legacy identity_provider inspection and test-connectivity interface.

**Preconditions.** Configure an IdP fixture for a disposable organization.

1. Read configuration and check connectivity as its Tenant Admin.
2. Confirm the read result matches the configured provider without exposing credential material.

**Expected results.** The authorized admin sees the configured provider and an observable connectivity result with no credential values.
