# Test Plan — OSAC-1567 Secret management

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 14

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-SEC-01: Secret data validation applies type-specific key requirements

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 840-842](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L840-L842)
- **Dependencies:** Local validateSecretData helper and synthetic non-secret fixtures; no store or database.
- **Execution:** `fulfillment-service/internal/servers/secret_validation_test.go`
- **Evidence:** `TestValidateSecretData` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/secret_validation_test.go#L26)).
- **Selector:** `go test ./internal/servers -run '^TestValidateSecretData$'` from `fulfillment-service`; named table rows include opaque permits empty data, missing pull secret key and empty value. Source reviewed, test not run.

**Preconditions.** Use fixture values for opaque, pull-secret and value types.

1. Validate the empty opaque fixture, the supplied pull-secret key fixture and the omitted-key/empty-value rows.
2. Compare the named table outcomes.

**Expected results.** Opaque empty data and the supplied key pass, while a missing required key and empty value fail. Proto size and required-field assertions are separate.

#### TC-SEC-02: Private create and read preserve Vault backend metadata

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 842-843](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L842-L843)
- **Dependencies:** In-process private fulfillment, real PostgreSQL, fake Vault store and mocked tenancy; no Vault server.
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`
- **Evidence:** `Creates and gets a Vault secret` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_secrets_server_test.go#L184)).
- **Selector:** `ginkgo run --timeout 10m --focus='Creates and gets a Vault secret' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the private suite's synthetic Vault-backed object.

1. Create the Secret and Get it using the returned ID.
2. Compare the two backend values and Create data field.

**Expected results.** Create and Get agree on ID and Vault backend. Create returns no secret data.

#### TC-SEC-03: Public Secret responses omit private backend and coordinates

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 844-846](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L844-L846)
- **Dependencies:** Public type mapping with synthetic private response; no broker, Kubernetes or store.
- **Gap:** The public Secret descriptor has no backend or coordinates. Private fixture tests assert their presence, and no named public mapping test explicitly compares both omissions.

**Preconditions.** Use a private fixture Secret with backend, synthetic coordinates and ordinary public metadata.

1. Map to the public Get response and serialize using protobuf JSON.
2. Inspect the serialized field set.

**Expected results.** The response contains its public identity and fields and omits backend and coordinates.

#### TC-SEC-04: Published Secret events contain no data

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 845-846](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L845-L846)
- **Dependencies:** Real PostgreSQL, Kafka test container and in-process publisher; synthetic change row; no Vault or API server.
- **Execution:** `fulfillment-service/internal/servers/event_publisher_test.go`
- **Evidence:** `Redacts secret data before publishing` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/event_publisher_test.go#L521)).
- **Selector:** `ginkgo run --timeout 10m --focus='Redacts secret data before publishing' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the publisher fixture with a synthetic Secret change row and a dedicated tenant topic.

1. Publish the row and read one event from Kafka.
2. Decode its Secret payload and compare identity and data.

**Expected results.** The Secret ID survives and its data map is empty.

#### TC-SEC-05: Tenant-authenticated Secret Get preserves tenant isolation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 850-855](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L850-L855)
- **Dependencies:** Real deployed fulfillment, PostgreSQL, Keycloak and Vault-compatible test store; two isolated fixture users and tenants.
- **Execution:** `fulfillment-service/it/it_public_secrets_test.go`
- **Evidence:** `cross-tenant get returns NotFound` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_public_secrets_test.go#L245)).
- **Selector:** Ginkgo focus `cross-tenant get returns NotFound` in the public Secrets context of the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's separate tenant identities and their synthetic Secrets.

1. Check the ordinary Get results outside each fixture's authorized scope.
2. Inspect the statuses without recording Secret data.

**Expected results.** Both unauthorized reads return NotFound.

#### TC-SEC-06: Public gRPC Get fetches authorized fixture data from the deployed secret store

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 850-853](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L850-L853)
- **Dependencies:** Real deployed fulfillment, Vault-compatible test store, PostgreSQL and Keycloak in Kind; synthetic values and isolated tenant.
- **Execution:** `fulfillment-service/it/it_public_secrets_test.go`
- **Evidence:** `gets the secret with data from vault` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_public_secrets_test.go#L80)).
- **Selector:** Ginkgo focus `Public secrets CRUD lifecycle` to retain the ordered Create prerequisite of the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Create the suite's synthetic Secret using the ordered public CRUD fixture.

1. Get the returned ID under the authorized identity.
2. Compare the result with the fixture values in memory.

**Expected results.** The response contains the fixture ID, name and original synthetic data.

#### TC-SEC-07: Vault write and delete failures preserve metadata consistency

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 842-844](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L842-L844)
- **Dependencies:** Real PostgreSQL and in-process private server; Vault client injects transient write/delete errors; no live store.
- **Gap:** No exact pair of backend-failure consistency assertions identified in canonical private Secret server and store tests.

**Preconditions.** Use an unpersisted fixture object and an existing synthetic Secret.

1. Induce a backend failure during Create, then a separate failure during Delete.
2. Read only metadata after each failure.

**Expected results.** Failed Create leaves no row, while failed Delete leaves the original row available.

#### TC-SEC-08: Credential migration reruns without duplicate payloads

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 848-848](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L848-L848)
- **Dependencies:** Real disposable PostgreSQL and recording destination store; use synthetic source and destination records only.
- **Gap:** Canonical migrations and Secret-related suites did not identify an exact rerun assertion comparing migration outputs.

**Preconditions.** Use a pre-migration synthetic record and its expected output field set.

1. Apply the migration twice.
2. Compare row identity, destination records and generated payload structure in memory.

**Expected results.** The second run adds no duplicate and preserves the same destination identity and payload structure.

#### TC-SEC-09: A value Secret without its required data is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 840-841](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L840-L841)
- **Dependencies:** In-process fulfillment and real PostgreSQL suite fixture; fake Vault and tenancy; no backend write on rejection.
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`
- **Evidence:** `Create value secret without data fails` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_secrets_server_test.go#L426)).
- **Selector:** `ginkgo run --timeout 10m --focus='Create value secret without data fails' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Prepare the suite's value Secret fixture with metadata and no data.

1. Call Create directly on the private server.
2. Check status and diagnostic.

**Expected results.** InvalidArgument identifies the missing data.

#### TC-SEC-10: Secret proto validation enforces the total data size limit

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 659-664](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L659-L664)
- **Dependencies:** Local protobuf and Secret validation only; generated synthetic bytes.
- **Gap:** The type-shape table does not measure the overall 1 MiB limit. Exact below/at/above size assertions were not confirmed in Secret validation tests.

**Preconditions.** Generate synthetic data immediately below, at, and above the documented size cap.

1. Validate the three otherwise valid fixtures.
2. Compare decisions and the reported data field.

**Expected results.** Values below and at the cap pass and the oversized fixture is rejected.

#### TC-SEC-11: A private Hub Secret returns coordinates on Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 842-845](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L842-L845)
- **Dependencies:** In-process private service, real PostgreSQL and fake store/Hub fixture; no Kubernetes Secret read on this assertion.
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`
- **Evidence:** `Creates a Hub secret with coordinates` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_secrets_server_test.go#L225)).
- **Selector:** `ginkgo run --timeout 10m --focus='Creates a Hub secret with coordinates' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the private suite's Hub-backed coordinates fixture.

1. Create the object through the private server.
2. Inspect the returned metadata and data presence.

**Expected results.** The response has a nonempty ID, Hub backend and the fixture hub ID. Data is empty.

#### TC-SEC-12: A masked update replaces synthetic Vault data

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 842-843](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L842-L843)
- **Dependencies:** Real PostgreSQL and in-process private service with fake Vault store and tenancy; no deployed Vault.
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`
- **Evidence:** `Update applies partial changes via field mask` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_secrets_server_test.go#L303)).
- **Selector:** `ginkgo run --timeout 10m --focus='Update applies partial changes via field mask' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use the suite's synthetic Vault-backed Secret.

1. Update its data with the data mask, then Get it by ID.
2. Compare Update response data and the Get readback.

**Expected results.** Update returns no data and Get returns the replacement fixture key and value.

#### TC-SEC-13: Private Delete removes a Vault-backed record

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 842-843](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L842-L843)
- **Dependencies:** In-process private service and real PostgreSQL, with fake Vault and tenancy; no deployed store.
- **Execution:** `fulfillment-service/internal/servers/private_secrets_server_test.go`
- **Evidence:** `Delete removes the object` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_secrets_server_test.go#L326)).
- **Selector:** `ginkgo run --timeout 10m --focus='Private secrets server.*Delete removes the object' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create the suite's Vault-backed fixture record.

1. Delete it through the private API and call Get on its ID.
2. Inspect the final status.

**Expected results.** Get returns NotFound. This spec does not independently inspect the store's Delete call.

#### TC-SEC-14: The deployed identity boundary keeps backend access tenant-scoped

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 850-857](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1567-secret-management/design.md#L850-L857)
- **Dependencies:** Real isolated Keycloak and Vault-compatible test store, deployed fulfillment and fixture tenants; synthetic data.
- **Gap:** Public Secrets tests verify the API isolation result. Exact backend tenant-binding, controller token exchange, namespace lifecycle and TTL assertions need source verification in the canonical secret-store and onboarding suites.

**Preconditions.** Prepare two disposable tenant identities and a synthetic controller identity.

1. Exercise normal tenant and controller Secret operations and observe onboarding, offboarding and token-cache behavior through fixture readback.
2. Compare authorized and unauthorized outcomes.

**Expected results.** The store scopes each authorized request to its tenant, denies unrelated scope, removes offboarded namespaces and expires cached access at the declared TTL.
