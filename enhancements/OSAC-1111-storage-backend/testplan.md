# Test Plan — OSAC-1111 StorageBackend API

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 17

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

The design calls for a specific stale-write status. The existing server assertion verifies an error only; the exact status remains unverified.

## Test Cases

#### TC-SB-01: Private Create and Get expose configured backend fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Backend CRUD](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L356)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Creates and gets a storage backend` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L335)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Creates and gets a storage backend$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid synthetic backend definition in the real DB server suite.

1. Create the backend and Get the returned ID.
2. Compare the visible fields.

**Expected results.** The returned object has the created identity and the configured provider and endpoint.

#### TC-SB-02: Managed backend Create requires provider

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [StorageBackend validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L357)
- **Dependencies:** Real protobuf validator, called locally. Downstream handler is a stub.
- **Execution:** `fulfillment-service/internal/validation/protovalidate_interceptor_test.go`
- **Evidence:** `TestValidation / Protovalidate interceptor / StorageBackend spec validation / Rejects create request with empty provider` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/validation/protovalidate_interceptor_test.go#L551)).
- **Selector:** `go test ./internal/validation -run '^TestValidation$' -ginkgo.focus='^Protovalidate interceptor StorageBackend spec validation Rejects create request with empty provider$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid synthetic VAST backend request with provider omitted or empty as appropriate.

1. Pass the request through the local protobuf validator interceptor.

**Expected results.** The interceptor returns InvalidArgument and never calls the stub handler.

#### TC-SB-03: Provider cannot change on update

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Provider immutability](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L358)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Immutability / Update changing provider fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L571)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Immutability Update changing provider fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a stored fixture backend with a valid provider.

1. Attempt a masked provider update.
2. Inspect status and diagnostic.

**Expected results.** It returns InvalidArgument mentioning the immutable provider.

#### TC-SB-04: Duplicate active backend name is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Active name uniqueness](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L359)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Name uniqueness / Create with duplicate active name fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L640)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Name uniqueness Create with duplicate active name fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Persist one backend with a unique test name.

1. Create a second with that same name.
2. Inspect the result.

**Expected results.** The duplicate returns AlreadyExists.

#### TC-SB-05: Referenced backend deletion returns FailedPrecondition through the API

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Referential integrity](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L360)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Gap:** Migration 76 verifies database Z0003, and the server fixture verifies unreferenced deletion. The private backend suites do not assert this API status for a referenced backend.

**Preconditions.** Register a fixture backend with an active StorageTier referencing it.

1. Call private Delete for that backend.
2. Inspect its RPC status.

**Expected results.** The delete returns FailedPrecondition.

#### TC-SB-06: CSP-managed backend ownership persists and is immutable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Ownership extension](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L109)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Execution:** `fulfillment-service/it/it_storage_backend_ownership_test.go`
- **Evidence:** `TestIntegration / Storage backend ownership API / persists a credential-free CSP-managed backend and enforces immutable ownership` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_storage_backend_ownership_test.go#L107)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Storage backend ownership API / persists a credential-free CSP-managed backend and enforces immutable ownership` in the service-only phase.

**Preconditions.** Use a credential-free CSP-managed backend in the Kind fixture.

1. Create and Get it through the private service.
2. Request an ownership change.

**Expected results.** The stored ownership is CSP-managed and update cannot change it.

#### TC-SB-07: A locked update rejects the original stale version

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Optimistic locking](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L361)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Optimistic locking / Update with stale version and lock=true fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L679)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Optimistic locking Update with stale version and lock=true fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a backend, retain its version, and update its description once.

1. Update the description again with the first version and lock=true.
2. Inspect the error.

**Expected results.** The stale write returns an error. The test does not assert the design's FailedPrecondition status.

#### TC-SB-08: Backend metadata.name is immutable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Backend name immutability](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L358)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Immutability / Update changing metadata.name fails at DB level` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L591)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Immutability Update changing metadata\.name fails at DB level$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create the synthetic backend through the private server.

1. Send an Update requesting metadata.name=new-name.
2. Inspect the RPC error.

**Expected results.** The database-backed Update returns a non-OK status.

#### TC-SB-09: Backend name can be reused after deletion

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Name reuse](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L359)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Name uniqueness / Create after delete of same name succeeds` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L664)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Name uniqueness Create after delete of same name succeeds$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a backend with name reusable-name.

1. Delete it and create a new one with the same name.
2. Inspect the new metadata.

**Expected results.** The new Create succeeds and returns reusable-name.

#### TC-SB-10: Kind private backend CRUD verifies authenticated gRPC and REST

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Kind gRPC and REST](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L364)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Gap:** Kind ownership checks registration, update and tenant denial over gRPC. The Kind and REST suites do not verify successful dual-protocol CRUD.

**Preconditions.** Use isolated Kind and administrative/public-client fixtures.

1. Run backend CRUD through gRPC then REST.
2. Inspect sorted/filterable results and unauthorized access.

**Expected results.** Both authorized paths round-trip values and deny access to a tenant user. The filtered, sorted list matches seeded names.

#### TC-SB-11: Managed backend Create requires endpoint

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [StorageBackend validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L357)
- **Dependencies:** Real protobuf validator, called locally. Downstream handler is a stub.
- **Execution:** `fulfillment-service/internal/validation/protovalidate_interceptor_test.go`
- **Evidence:** `TestValidation / Protovalidate interceptor / StorageBackend spec validation / Rejects create request with empty endpoint` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/validation/protovalidate_interceptor_test.go#L628)).
- **Selector:** `go test ./internal/validation -run '^TestValidation$' -ginkgo.focus='^Protovalidate interceptor StorageBackend spec validation Rejects create request with empty endpoint$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid synthetic VAST backend request with endpoint omitted or empty as appropriate.

1. Pass the request through the local protobuf validator interceptor.

**Expected results.** The interceptor returns InvalidArgument and never calls the stub handler.

#### TC-SB-12: Managed backend Create requires credentials

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [StorageBackend validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L357)
- **Dependencies:** Real protobuf validator, called locally. Downstream handler is a stub.
- **Execution:** `fulfillment-service/internal/validation/protovalidate_interceptor_test.go`
- **Evidence:** `TestValidation / Protovalidate interceptor / StorageBackend spec validation / Rejects create request with missing credentials` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/validation/protovalidate_interceptor_test.go#L665)).
- **Selector:** `go test ./internal/validation -run '^TestValidation$' -ginkgo.focus='^Protovalidate interceptor StorageBackend spec validation Rejects create request with missing credentials$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid synthetic VAST backend request with credentials omitted or empty as appropriate.

1. Pass the request through the local protobuf validator interceptor.

**Expected results.** The interceptor returns InvalidArgument and never calls the stub handler.

#### TC-SB-13: Private Delete with no tier references removes the backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Backend delete and reference policy](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L360)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Delete removes the object` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L479)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Delete removes the object$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic backend without any associated tier.

1. Delete it through the private server.
2. Get it by the original ID.

**Expected results.** Delete succeeds and Get returns NotFound.

#### TC-SB-14: Backend List orders objects by metadata.name

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Backend List ordering](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L363)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / List objects with order` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L413)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour List objects with order$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed aaa-backend and zzz-backend in the isolated shared catalog.

1. List backends sorted by metadata.name ascending.

**Expected results.** Exactly two items are returned, with aaa-backend before zzz-backend.

#### TC-SB-15: Backend description updates through a field mask

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Backend CRUD](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L356)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`
- **Evidence:** `TestServers / Private storage backends server / Behaviour / Update applies partial changes via field mask` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_backends_server_test.go#L426)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage backends server Behaviour Update applies partial changes via field mask$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic VAST backend.

1. Update only spec.description through the private server.

**Expected results.** The returned description is Updated description and the provider remains vast.

#### TC-SB-16: Backend names comply with the DNS-label contract

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [StorageBackend validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L357)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Gap:** Interceptor name cases exercise other resource request types. The StorageBackend validation and Kind ownership sources do not verify this naming matrix.

**Preconditions.** Prepare otherwise valid backend requests with empty and uppercase fixture names, and a lowercase control.

1. Submit each through the validation-enabled private endpoint.

**Expected results.** The empty and uppercase names return InvalidArgument. The lowercase control succeeds.

#### TC-SB-17: Filter backend List by provider

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Backend CEL filtering](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1111-storage-backend/design.md#L362)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Gap:** Private backend List source filters by ID. The Kind ownership suite does not demonstrate the provider filter contract.

**Preconditions.** Seed one VAST and one CSP-managed NetApp backend under authorized fixture tenancy.

1. Request a provider-filtered list for VAST.

**Expected results.** Only the VAST fixture is returned and the list size is one.
